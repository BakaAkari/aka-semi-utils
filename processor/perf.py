"""性能统计模块（Phase 5.1）。

提供**轻量、零依赖**的运行时计时设施，让上层（PipelineEngine / BatchResult）可以：

- 在管道运行时累计每个 processor 的耗时；
- 跨多个文件（批处理）聚合各处理器的 P50/P95 / mean / max；
- 渲染人类可读的性能报告（控制台 / 日志 / 完成对话框 detail）。

设计要点：
- **进程隔离**：累加器是普通 dict，不跨 ProcessPool 边界；
  worker 进程产生的 timing 通过 :class:`PerfRecord` **随结果返回**，
  主进程在 :class:`processor.batch.BatchResult` 层做聚合；
- **零运行时开销**：单条样本是 ``(name, ms_float)`` tuple，写入 list 即可；
- **pickle-safe**：所有公开 dataclass 字段均为基础类型，可直接跨进程返回。
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 单文件 / 单管道的样本累加器
# ---------------------------------------------------------------------------
@dataclass
class PerfRecord:
    """单次 PipelineEngine 运行的全部 processor 耗时（pickle-safe）。

    ``samples`` 是 ``(processor_name, milliseconds)`` 的有序列表；
    一个文件可能多次调用同名 processor（例如 multi-stage merge），故用 list
    而非 dict — 聚合时再按 name 分桶。
    """

    samples: list[tuple[str, float]] = field(default_factory=list)
    total_ms: float = 0.0
    """整条管道的端到端耗时（含 IO + 节点+ 装配）。"""

    def add(self, name: str, ms: float) -> None:
        self.samples.append((name, ms))

    def by_processor(self) -> dict[str, list[float]]:
        """按 processor 名分组的耗时列表（聚合用）。"""
        bucket: dict[str, list[float]] = {}
        for name, ms in self.samples:
            bucket.setdefault(name, []).append(ms)
        return bucket


# ---------------------------------------------------------------------------
# 跨文件（整批）的聚合统计
# ---------------------------------------------------------------------------
@dataclass
class ProcessorStat:
    """单个 processor 在整批中的统计快照。"""

    name: str
    count: int  # 调用次数（≥ 处理的文件数，因可能一文件多调用）
    mean_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float
    total_ms: float

    def slow_warning(self, threshold_ms: float) -> bool:
        """P95 是否超过给定阈值（用于发出"慢节点"警告）。"""
        return self.p95_ms > threshold_ms


# Phase 5.3：默认"慢节点"P95 阈值（毫秒）。
# 经验值：超过 1s 的单 processor 几乎肯定值得优化（属人眼可感知延迟级别）。
DEFAULT_SLOW_THRESHOLD_MS = 1000.0


@dataclass
class BatchPerfReport:
    """整批 :class:`PerfRecord` 聚合后的报告（pickle-safe）。"""

    file_count: int = 0
    total_pipeline_ms: float = 0.0
    """所有文件管道耗时之和（用于对比串/并行加速比）。"""

    per_processor: list[ProcessorStat] = field(default_factory=list)

    @property
    def mean_pipeline_ms(self) -> float:
        return self.total_pipeline_ms / self.file_count if self.file_count else 0.0

    def slowest(self, n: int = 5) -> list[ProcessorStat]:
        """按 ``total_ms`` 降序的 Top-N 慢节点。"""
        return sorted(self.per_processor, key=lambda s: s.total_ms, reverse=True)[:n]

    def slow_processors(
        self, threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS
    ) -> list[ProcessorStat]:
        """Phase 5.3：返回所有 P95 超过阈值的处理器（可作为 warning 来源）。"""
        return [s for s in self.per_processor if s.slow_warning(threshold_ms)]

    def format_text(self, top_n: int = 5) -> str:
        """渲染为多行文本（控制台 / 日志 / dialog detailedText 用）。"""
        if self.file_count == 0:
            return "（无性能数据）"
        lines: list[str] = [
            f"批处理性能报告（{self.file_count} 个文件，总管道耗时 "
            f"{self.total_pipeline_ms:.0f}ms，平均 {self.mean_pipeline_ms:.0f}ms/文件）",
            "—" * 60,
            f"{'处理器':<24}{'次数':>6}{'mean':>10}{'P50':>10}{'P95':>10}{'max':>10}",
        ]
        for stat in self.slowest(top_n):
            lines.append(
                f"{stat.name:<24}{stat.count:>6}"
                f"{stat.mean_ms:>9.1f}m{stat.p50_ms:>9.1f}m"
                f"{stat.p95_ms:>9.1f}m{stat.max_ms:>9.1f}m"
            )
        return "\n".join(lines)

    def emit_warnings(
        self,
        logger,  # 不在模块顶部 import logger，保持 perf 模块对 logger 实现解耦
        threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS,
    ) -> int:
        """Phase 5.3：把超过阈值的处理器逐个 ``logger.warning`` 输出。

        Returns:
            发出的 warning 条数（便于测试断言）。
        """
        slows = self.slow_processors(threshold_ms)
        for s in slows:
            logger.warning(
                f"[perf]慢节点 {s.name}: P95={s.p95_ms:.0f}ms "
                f"mean={s.mean_ms:.0f}ms count={s.count} "
                f"(阈值 {threshold_ms:.0f}ms)"
            )
        return len(slows)


# ---------------------------------------------------------------------------
# 核心计算
# ---------------------------------------------------------------------------
def _percentile(values: list[float], pct: float) -> float:
    """无外部依赖的百分位实现（线性插值，与 numpy.percentile 一致到 1e-9）。"""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_v) - 1)
    frac = k - lo
    return sorted_v[lo] * (1 - frac) + sorted_v[hi] * frac


def aggregate(records: list[PerfRecord]) -> BatchPerfReport:
    """把多份 :class:`PerfRecord` 聚合为 :class:`BatchPerfReport`。"""
    file_count = len(records)
    total_pipeline = sum(r.total_ms for r in records)

    # 跨所有文件，按 processor 名汇总样本
    bucket: dict[str, list[float]] = {}
    for rec in records:
        for name, samples in rec.by_processor().items():
            bucket.setdefault(name, []).extend(samples)

    stats: list[ProcessorStat] = []
    for name, vals in bucket.items():
        stats.append(
            ProcessorStat(
                name=name,
                count=len(vals),
                mean_ms=statistics.fmean(vals),
                p50_ms=_percentile(vals, 50),
                p95_ms=_percentile(vals, 95),
                max_ms=max(vals),
                total_ms=sum(vals),
            )
        )
    # 默认按总耗时降序便于直接渲染
    stats.sort(key=lambda s: s.total_ms, reverse=True)
    return BatchPerfReport(
        file_count=file_count,
        total_pipeline_ms=total_pipeline,
        per_processor=stats,
    )


# ---------------------------------------------------------------------------
# 工具：上下文管理器（用于显式区段计时，例如非 processor 步骤）
# ---------------------------------------------------------------------------
@contextmanager
def measure(record: PerfRecord, name: str) -> Iterator[None]:
    """显式计时一段代码，把结果写入 ``record``。

    用法::

        rec = PerfRecord()
        with measure(rec, "save_output"):
            engine.save_output()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        record.add(name, (time.perf_counter() - start) * 1000.0)


__all__ = [
    "DEFAULT_SLOW_THRESHOLD_MS",
    "BatchPerfReport",
    "PerfRecord",
    "ProcessorStat",
    "aggregate",
    "measure",
]
