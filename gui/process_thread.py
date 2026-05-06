"""处理线程 — 在后台运行图像处理管道（已接入 ProcessPoolExecutor 并行）。

- 主进程读 EXIF + 渲染模板 → 构造 :class:`processor.batch.BatchTask` 列表；
- 派发给 :func:`processor.batch.process_batch`（自动选择串行/并行）；
- ``on_progress`` 回调直接 emit Qt 信号，UI 线程同步刷新；
- 取消通过 ``threading.Event`` + ``cancel_check`` 透传给批处理引擎。
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from core.config_loader import load_config_ini
from core.template_builder import render_processors
from core.util import get_exif_batch
from gui.error_presenter import BatchSummary, summarize
from processor.batch import BatchResultItem, build_tasks, process_batch

logger = logging.getLogger(__name__)


class ProcessThread(QThread):
    """后台处理线程 — 批量执行 watermark pipeline（CPU 并行）。"""

    progress = pyqtSignal(int, str)          # 进度百分比, 状态文字
    # Phase 4：file_done 增加 error_kind / error_class / error_context（向后兼容
    # 旧 3-arg 信号 — 我们保留 file_done，新增 file_failed_detail 给关心结构化错误的订阅者）
    file_done = pyqtSignal(str, bool, str)   # 文件路径, 是否成功, 消息
    file_failed_detail = pyqtSignal(object)  # PresentedError（仅失败时 emit）
    finished_all = pyqtSignal(bool, str)     # 是否全部成功, 汇总消息
    finished_summary = pyqtSignal(object)    # BatchSummary（结构化汇总）

    def __init__(
        self,
        files: list[str],
        processors: list[dict[str, Any]],
        output_pattern: str,
        override: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.files = files
        self.processors = processors
        self.output_pattern = output_pattern
        self.override = override
        self._cancelled = threading.Event()

        # 从 config.ini 读取并发与 sidecar 开关（向后兼容：无 [performance] 段时取默认）
        cfg = load_config_ini()
        self._max_workers = cfg.getint("performance", "max_workers", fallback=-1)
        self._emit_exif_json = cfg.getboolean(
            "performance", "emit_exif_json", fallback=False
        )

    # ------------------------------------------------------------------ API
    def cancel(self):
        """请求取消（运行中的 worker 会跑完，下一个不再启动）。"""
        self._cancelled.set()

    # ----------------------------------------------------------- QThread.run
    def run(self):
        total = len(self.files)
        if total == 0:
            self.finished_all.emit(True, "无文件需要处理")
            return

        self.progress.emit(0, f"读取 EXIF 中（{total} 张）...")

        # 1) 主进程一次性批量读 EXIF（远比每文件 fork 高效）
        try:
            exif_map = get_exif_batch(self.files)
        except Exception as e:
            logger.exception("批量读取 EXIF 失败")
            # 构造一个 fatal 级别 summary 给订阅者
            from gui.error_presenter import BatchSummary, PresentedError, Severity
            summary = BatchSummary(
                total=total,
                success=0,
                failed=total,
                errors=[PresentedError(
                    severity=Severity.FATAL,
                    title="读取 EXIF 失败",
                    detail=str(e),
                    raw_class=type(e).__name__,
                )],
            )
            self.finished_summary.emit(summary)
            self.finished_all.emit(False, f"读取 EXIF 失败: {e}")
            return

        # 2) 过滤已存在且不允许覆盖的输出，构造 BatchTask
        skipped: list[str] = []

        def _resolve(input_path: str) -> str:
            return str(self._resolve_output_path(Path(input_path)))

        files_to_process: list[str] = []
        for f in self.files:
            out = _resolve(f)
            if Path(out).exists() and not self.override:
                skipped.append(f)
                self.file_done.emit(f, False, f"输出已存在: {out}")
                continue
            files_to_process.append(f)

        if not files_to_process:
            self.progress.emit(100, "完成（全部跳过）")
            self.finished_all.emit(
                False, f"无新任务可执行（跳过 {len(skipped)} 项）"
            )
            return

        tasks = build_tasks(
            files=files_to_process,
            processors_template=self.processors,
            resolve_output=_resolve,
            render_per_file=render_processors,
            emit_exif_json=self._emit_exif_json,
            pre_loaded_exif_map={f: exif_map.get(f, {}) for f in files_to_process},
        )

        # 3) 并行/串行执行
        result = process_batch(
            tasks,
            max_workers=self._max_workers,
            on_progress=self._on_progress,
            cancel_check=self._cancelled.is_set,
        )

        # 4) 汇总（构造结构化 BatchSummary）
        summary: BatchSummary = summarize(
            result.items,
            skipped_count=len(skipped),
            cancelled=self._cancelled.is_set(),
        )
        self.finished_summary.emit(summary)

        if self._cancelled.is_set():
            self.progress.emit(100, "已取消")
            self.finished_all.emit(False, summary.headline)
            return

        self.progress.emit(100, "完成")
        self.finished_all.emit(summary.is_all_success, summary.headline)

    # --------------------------------------------------------------- helpers
    def _on_progress(self, done: int, total: int, item: BatchResultItem) -> None:
        """批处理进度回调 — 主进程线程内执行，可直接 emit Qt 信号。"""
        pct = int(done / total * 100) if total else 100
        self.progress.emit(pct, f"处理中 {done}/{total}...")
        self.file_done.emit(
            item.input_path,
            item.success,
            "成功" if item.success else (item.error or "未知错误"),
        )
        # Phase 4：失败时同步 emit 结构化错误，关心详情的订阅者可订阅
        if not item.success:
            from gui.error_presenter import present_item
            pe = present_item(item)
            if pe is not None:
                self.file_failed_detail.emit(pe)
            if item.traceback:
                logger.error(
                    "处理失败 %s [%s/%s]\n%s",
                    item.input_path, item.error_kind, item.error_class, item.traceback
                )

    def _resolve_output_path(self, input_path: Path) -> Path:
        """根据模式解析输出路径。"""
        source_dir = input_path.parent
        stem = input_path.stem

        pattern = self.output_pattern
        # 使用 str.format() 替代字符串替换，更规范且可扩展
        pattern = pattern.replace("{", "{{").replace("}", "}}")
        pattern = pattern.replace("{{source_dir}}", str(source_dir))
        pattern = pattern.replace("{{filename}}", stem)
        # 还原真实占位符
        pattern = pattern.replace("{{", "{").replace("}}", "}")

        # 保留未知占位符原样（KeyError / IndexError 时不替换）
        with contextlib.suppress(KeyError, IndexError):
            pattern = pattern.format(source_dir=str(source_dir), filename=stem)

        # 如果以目录结尾（不含扩展名），追加 _logo.jpg
        if not Path(pattern).suffix:
            pattern = os.path.join(pattern, f"{stem}_logo.jpg")

        return Path(pattern)
