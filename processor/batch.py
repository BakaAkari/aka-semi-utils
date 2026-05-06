"""并行批处理模块（Phase 2.1）。

把"逐文件 watermark pipeline"拆成 **可分发到 ``ProcessPoolExecutor``**
的独立任务单元，达成：

- **CPU 并行**：PIL/numpy 像素操作是纯 CPU 密集，跨进程并行近线性加速；
- **错误隔离**：单文件异常被 worker 捕获，不影响整批；
- **EXIF 一次读**：在主进程用 :func:`core.util.get_exif_batch` 一次拉齐所有文件，
  再分发给 worker，避免 N 次 fork exiftool；
- **可配置并发度**：``max_workers=0`` 走单进程模式（便于调试/测试 / 关闭并发）；
- **流式进度**：通过 ``on_progress(idx, total, item)`` 回调，主线程可以直
  接转给 PyQt 信号。

设计约束：
- worker 函数 :func:`_worker_process_one` 必须是**模块级函数**，否则 ``fork``
  方式 spawn 时无法 pickle；
- 任务参数 :class:`BatchTask` 仅含原始 dict / str / list 等可序列化字段；
- 处理器注册依赖 :mod:`processor` 的副作用导入（worker 入口处显式 import）。

向后兼容：本模块**新增**，不修改 :func:`processor.core.start_process` 的签名。
"""

from __future__ import annotations

import multiprocessing
import os
import traceback
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field

from core.logger import logger
from processor.perf import (
    DEFAULT_SLOW_THRESHOLD_MS,
    BatchPerfReport,
    PerfRecord,
    aggregate,
)

# Phase 5.4：小批量并行 fallback 阈值。
# ProcessPoolExecutor 启动一次开销约 50–200ms（fork + 模块 import + 注册副作用），
# 当任务数 < 该阈值时，启动开销往往超过并行收益，直接走串行更快。
SMALL_BATCH_THRESHOLD = 3


@dataclass
class BatchTask:
    """单个批处理任务（必须 pickle-safe）。"""

    input_path: str
    output_path: str
    processors: list[dict]
    pre_loaded_exif: dict = field(default_factory=dict)
    emit_exif_json: bool = False


@dataclass
class BatchResultItem:
    """单个任务的执行结果（成功 / 失败一致结构，便于聚合）。

    Phase 4：增加结构化错误字段以支撑 GUI 分级展示。错误来自 worker 子进程时
    必须 pickle-safe — 故只保留**原始异常的元数据**（类名 / 字段 dict / 字符串
    化的消息），不直接持有 Exception 对象。

    Phase 5.1：增加 ``perf`` 字段，承载该文件管道的 :class:`PerfRecord`
    （pickle-safe — 仅含 list[tuple[str, float]] 与 float），主进程在
    :class:`BatchResult` 层聚合为 :class:`BatchPerfReport`。
    """

    input_path: str
    output_path: str
    success: bool
    error: str | None = None
    traceback: str | None = None
    # ---- Phase 4 结构化错误字段（成功时全部 None / 空） ----
    error_kind: str | None = None      # "processor" / "resource" / "config" / "unknown"
    error_class: str | None = None     # 原始异常类名，如 "ProcessorRuntimeError"
    error_context: dict = field(default_factory=dict)  # 异常 context 字段
    # ---- Phase 5.1 性能采样（失败任务也可能产出部分采样） ----
    perf: PerfRecord | None = None


@dataclass
class BatchResult:
    """整批结果汇总。"""

    items: list[BatchResultItem]

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.items if r.success)

    @property
    def fail_count(self) -> int:
        return self.total - self.success_count

    @property
    def all_success(self) -> bool:
        return self.fail_count == 0

    @property
    def perf_report(self) -> BatchPerfReport:
        """Phase 5.1：把所有 item 的 :class:`PerfRecord` 聚合为批级报告。

        - 仅成功项的样本会被纳入（失败项可能因异常打断采样不完整）；
        - 无任何 perf 数据时返回 ``BatchPerfReport(file_count=0)``。
        """
        records = [r.perf for r in self.items if r.success and r.perf is not None]
        return aggregate(records)


def _classify_error(e: BaseException) -> tuple[str, str, dict]:
    """把任意异常归类为 (kind, class_name, context_dict)。

    - kind: ``"processor"`` / ``"resource"`` / ``"config"`` / ``"unknown"``；
    - class_name: 原始异常的 ``__class__.__name__``；
    - context: 若是 ``AkaSemiUtilsError`` 子类则取其 ``.context`` 副本（pickle-safe
      — 浅拷贝且只含基础类型）；否则空 dict。

    保留 import 在函数内部以避免 worker 子进程模块级循环导入。
    """
    cls_name = type(e).__name__
    try:
        from core.exceptions import (
            AkaSemiUtilsError,
            ConfigError,
            ProcessorError,
            ResourceError,
        )
    except ImportError:
        return ("unknown", cls_name, {})

    if isinstance(e, ProcessorError):
        kind = "processor"
    elif isinstance(e, ResourceError):
        kind = "resource"
    elif isinstance(e, ConfigError):
        kind = "config"
    else:
        kind = "unknown"

    context: dict = {}
    if isinstance(e, AkaSemiUtilsError):
        # context 的 value 可能含非 pickle-safe 对象（如 Exception 实例）— 全部转 str
        context = {k: _to_safe(v) for k, v in (e.context or {}).items()}
    return (kind, cls_name, context)


def _to_safe(v):
    """把 context value 转换成 pickle-safe 形式（基础类型保留，其他 ``str(v)``）。"""
    if isinstance(v, (str, int, float, bool, type(None))):
        return v
    if isinstance(v, (list, tuple)):
        return [_to_safe(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _to_safe(val) for k, val in v.items()}
    return str(v)


def _worker_process_one(task: BatchTask) -> BatchResultItem:
    """worker 入口（模块级，**pickle-safe**）。

    - 显式 ``import processor`` 触发处理器装饰器注册（每个 worker 进程独立一份注册表）；
    - 调用 :func:`processor.core.start_process` 完成 pipeline；
    - 任何异常都被捕获并塞进 :class:`BatchResultItem`，永远不抛回主进程；
    - **Phase 4**：识别项目自定义异常并填充 ``error_kind`` / ``error_class`` /
      ``error_context``，供主进程 GUI 做分级展示。
    - **Phase 5.1**：创建 :class:`PerfRecord` 并随结果返回，主进程聚合为
      :class:`BatchPerfReport`。
    """
    perf = PerfRecord()
    try:
        # 触发副作用导入（每个 worker 都需独立注册）
        import processor  # noqa: F401
        from processor.core import start_process

        # 确保输出目录存在（worker 内做，避免主进程对每个 task 都判断）
        out_dir = os.path.dirname(task.output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        start_process(
            data=task.processors,
            input_path=task.input_path,
            output_path=task.output_path,
            pre_loaded_exif=task.pre_loaded_exif or None,
            emit_exif_json=task.emit_exif_json,
            perf_record=perf,
        )

        return BatchResultItem(
            input_path=task.input_path,
            output_path=task.output_path,
            success=True,
            perf=perf,
        )
    except Exception as e:
        kind, cls_name, ctx = _classify_error(e)
        return BatchResultItem(
            input_path=task.input_path,
            output_path=task.output_path,
            success=False,
            error=str(e),
            traceback=traceback.format_exc(),
            error_kind=kind,
            error_class=cls_name,
            error_context=ctx,
            perf=perf,  # 即使失败也保留已采样部分
        )


def _resolve_max_workers(requested: int, num_tasks: int) -> int:
    """决定实际使用的 worker 数。

    - ``requested == 0`` → 单进程模式（返回 0，调用方走串行分支）；
    - ``requested < 0``  → 自动（小批量 fallback 串行；否则 ``cpu_count() - 1``）；
    - 其他              → ``min(requested, cpu_count(), num_tasks)``。

    Phase 5.4：在自动模式 (``requested < 0``) 且任务数 < ``SMALL_BATCH_THRESHOLD``
    时直接返回 0（串行）。原因：``ProcessPoolExecutor`` 单次启动需 fork worker +
    重新 import 整个 processor 包（约 50–200ms × N），单文件场景下这部分开销
    远超并行收益；显式 ``requested > 0`` 时尊重用户意图，不做 fallback。
    """
    if requested == 0:
        return 0
    if num_tasks == 0:
        return 0

    cpu = multiprocessing.cpu_count()
    if requested < 0:
        # 小批量自动 fallback：跑串行避开 ProcessPool 启动开销
        if num_tasks < SMALL_BATCH_THRESHOLD:
            return 0
        return max(1, cpu - 1)
    return max(1, min(requested, cpu, num_tasks))


def process_batch(
    tasks: list[BatchTask],
    max_workers: int = -1,
    on_progress: Callable[[int, int, BatchResultItem], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    *,
    emit_perf_log: bool = True,
    slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS,
) -> BatchResult:
    """并行执行一批 watermark pipeline 任务。

    Args:
        tasks: 任务列表（已包含 EXIF 等所有 worker 所需输入）。
        max_workers: 并发度策略 — ``-1`` 自动，``0`` 串行，``>0`` 显式上限。
        on_progress: 每完成一项时调用 ``(done_idx, total, item)``。在主进程线程
            执行，可直接 emit Qt 信号。
        cancel_check: 取消轮询函数；返回 ``True`` 时主循环停止收集（已 dispatch
            的任务仍会跑完）。
        emit_perf_log: Phase 5.3 — 批处理结束后是否自动记录性能报告与慢节点
            warning（默认开启；测试时可关闭以保持日志干净）。
        slow_threshold_ms: Phase 5.3 — P95 超过该值视为慢节点（毫秒）。

    Returns:
        :class:`BatchResult`，含每项详细结果与汇总。
    """
    workers = _resolve_max_workers(max_workers, len(tasks))
    items: list[BatchResultItem] = []
    total = len(tasks)

    # ----------------- 串行模式（max_workers=0 或 任务为 0） -----------------
    if workers == 0:
        for idx, task in enumerate(tasks, start=1):
            if cancel_check and cancel_check():
                break
            item = _worker_process_one(task)
            items.append(item)
            if on_progress:
                on_progress(idx, total, item)
        result = BatchResult(items=items)
        if emit_perf_log:
            _log_perf_report(result, slow_threshold_ms)
        return result

    # ----------------- 并行模式（ProcessPoolExecutor） -----------------------
    # Phase 10.1 (P0)：取消按钮在并行模式下生效。
    # 设计要点：
    #   1. 每完成一个 future 就检查一次 cancel — 命中后立刻 break，停止收集后续结果；
    #   2. 调用 ``executor.shutdown(wait=False, cancel_futures=True)`` (Py3.9+)
    #      撤销尚未启动的 future（已开始执行的 worker 进程仍会跑完，无法中断）；
    #   3. 退出 ``with`` 块会 ``shutdown(wait=True)``，自动等待已运行的 worker 收尾，
    #      确保不出现僵尸子进程。
    cancelled = False
    with ProcessPoolExecutor(max_workers=workers) as ex:
        future_to_task = {ex.submit(_worker_process_one, t): t for t in tasks}
        for done, fut in enumerate(as_completed(future_to_task), start=1):
            if cancel_check and cancel_check():
                cancelled = True
                # 撤销所有未启动的 future；已运行的让其自然完成
                ex.shutdown(wait=False, cancel_futures=True)
                break
            item = fut.result()
            items.append(item)
            if on_progress:
                on_progress(done, total, item)
    if cancelled:
        logger.info("批处理被取消：已收集 %d/%d 项后停止", len(items), total)

    result = BatchResult(items=items)
    if emit_perf_log:
        _log_perf_report(result, slow_threshold_ms)
    return result


def _log_perf_report(result: BatchResult, slow_threshold_ms: float) -> None:
    """Phase 5.3：把 :attr:`BatchResult.perf_report` 输出到 logger。

    - 整体报告走 ``logger.info``（多行文本，便于 grep）；
    - 慢节点逐个走 ``logger.warning`` 由 :meth:`BatchPerfReport.emit_warnings` 发出。
    任何异常都吞掉 —— 性能日志绝不影响主流程。
    """
    try:
        report = result.perf_report
        if report.file_count == 0:
            return
        logger.info(report.format_text())
        report.emit_warnings(logger, slow_threshold_ms)
    except Exception as e:
        logger.debug(f"emit perf report failed (ignored): {e}")


# --------------------------------------------------------------------------
# 便捷构造器：把 ProcessThread 旧调用模式（files + processors + output_pattern）
# 转成 BatchTask 列表（在主进程预读 EXIF）。
# --------------------------------------------------------------------------


def build_tasks(
    files: list[str],
    processors_template: list[dict],
    resolve_output: Callable[[str], str],
    *,
    render_per_file: Callable[[list[dict], dict, str], list[dict]] | None = None,
    emit_exif_json: bool = False,
    pre_loaded_exif_map: dict[str, dict] | None = None,
) -> list[BatchTask]:
    """根据文件列表 + 处理器模板批量构造 :class:`BatchTask`。

    Args:
        files: 输入文件路径列表。
        processors_template: 未经 Jinja 渲染的处理器模板（dict 列表）。
        resolve_output: ``input_path -> output_path`` 解析函数。
        render_per_file: 可选 — 每个文件的模板渲染函数
            ``(template, exif, file_path) -> rendered_processors``。
            若为 None，则模板直接作为 processors 使用。
        emit_exif_json: 是否对每个任务启用 sidecar 输出。
        pre_loaded_exif_map: 已读取好的 ``path -> exif`` 映射；若为 None，
            则在内部调用 :func:`core.util.get_exif_batch` 一次性读取。

    Returns:
        BatchTask 列表（顺序保留）。
    """
    if pre_loaded_exif_map is None:
        # 延迟导入避免循环依赖
        from core.util import get_exif_batch

        pre_loaded_exif_map = get_exif_batch(files)

    tasks: list[BatchTask] = []
    for f in files:
        exif = pre_loaded_exif_map.get(f, {}) or {}
        rendered = (
            render_per_file(processors_template, exif, f)
            if render_per_file is not None
            else processors_template
        )

        tasks.append(
            BatchTask(
                input_path=f,
                output_path=resolve_output(f),
                processors=rendered,
                pre_loaded_exif=exif,
                emit_exif_json=emit_exif_json,
            )
        )
    return tasks
