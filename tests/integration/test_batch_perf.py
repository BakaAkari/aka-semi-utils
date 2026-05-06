"""Phase 5.7 — 批处理端到端性能数据流集成测试。

覆盖：

- 串行模式下 ``BatchResultItem.perf`` 被填充，``BatchResult.perf_report``
  能聚合产出非零 P95；
- 并行模式（``ProcessPoolExecutor``）下 PerfRecord 能跨进程 pickle 回主进程；
- ``emit_perf_log=False`` 抑制日志输出（不影响功能）；
- 慢节点 warning 由 :meth:`BatchPerfReport.emit_warnings` 正确发出；
- ``PipelineEngine`` 直接调用模式下 PerfRecord 也能正确累加 ``total_ms``。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

import processor  # noqa: F401  - 触发处理器注册
from processor.batch import BatchTask, process_batch
from processor.core import PipelineEngine, start_process
from processor.perf import BatchPerfReport, PerfRecord

# ============================================================
# 公用辅助
# ============================================================


def _make_input(tmp_path: Path, name: str, color=(180, 90, 40), size=(64, 48)) -> Path:
    p = tmp_path / name
    Image.new("RGB", size, color).save(p, format="JPEG", quality=92)
    return p


def _minimal_processors():
    # resize + blur — 两个不同的 processor，便于聚合分桶检验
    return [
        {"processor_name": "resize", "ratio": 0.5},
        {"processor_name": "blur", "radius": 1},
    ]


def _build_tasks(tmp_path: Path, n: int) -> list[BatchTask]:
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    return [
        BatchTask(
            input_path=str(_make_input(tmp_path, f"src_{i}.jpg")),
            output_path=str(out_dir / f"out_{i}.jpg"),
            processors=_minimal_processors(),
        )
        for i in range(n)
    ]


# ============================================================
# 串行模式（避开 ProcessPool）
# ============================================================


def test_serial_perf_records_populated(tmp_path):
    tasks = _build_tasks(tmp_path, 2)
    result = process_batch(tasks, max_workers=0, emit_perf_log=False)

    assert result.success_count == 2
    for item in result.items:
        assert item.perf is not None
        assert isinstance(item.perf, PerfRecord)
        # AOP wrapper 应写入两个 processor 样本
        names = {n for n, _ in item.perf.samples}
        assert "resize" in names
        assert "blur" in names
        # total_ms 应被 PipelineEngine.execute 写入 > 0
        assert item.perf.total_ms > 0.0


def test_batch_perf_report_aggregates_serial(tmp_path):
    tasks = _build_tasks(tmp_path, 3)
    result = process_batch(tasks, max_workers=0, emit_perf_log=False)

    report = result.perf_report
    assert isinstance(report, BatchPerfReport)
    assert report.file_count == 3
    assert report.total_pipeline_ms > 0.0
    assert report.mean_pipeline_ms > 0.0

    proc_names = {s.name for s in report.per_processor}
    assert "resize" in proc_names
    assert "blur" in proc_names

    # 每个 processor 至少被 3 次调用（每个文件一次）
    for stat in report.per_processor:
        if stat.name in {"resize", "blur"}:
            assert stat.count >= 3
            assert stat.mean_ms >= 0.0
            assert stat.p95_ms >= stat.p50_ms or stat.p95_ms == stat.p50_ms


def test_perf_report_format_text_serial(tmp_path):
    tasks = _build_tasks(tmp_path, 2)
    result = process_batch(tasks, max_workers=0, emit_perf_log=False)
    text = result.perf_report.format_text()
    assert "批处理性能报告" in text
    # 至少能找到一种 processor 名
    assert "resize" in text or "blur" in text


# ============================================================
# 并行模式（跨进程 pickle 回传）
# ============================================================


@pytest.mark.slow
def test_parallel_perf_records_survive_pickle(tmp_path):
    """worker 子进程产生的 PerfRecord 必须能 pickle 回主进程。"""
    tasks = _build_tasks(tmp_path, 4)
    result = process_batch(tasks, max_workers=2, emit_perf_log=False)

    assert result.success_count == 4
    for item in result.items:
        assert item.perf is not None
        # 跨进程回传后 samples 不为空
        assert len(item.perf.samples) >= 2
        assert item.perf.total_ms > 0.0

    report = result.perf_report
    assert report.file_count == 4
    assert report.total_pipeline_ms > 0.0


# ============================================================
# emit_perf_log 开关
# ============================================================


def test_emit_perf_log_false_suppresses_logging(tmp_path, caplog):
    """关闭 emit_perf_log 后不应输出"批处理性能报告"日志。"""
    import logging

    caplog.set_level(logging.INFO)
    tasks = _build_tasks(tmp_path, 2)
    process_batch(tasks, max_workers=0, emit_perf_log=False)
    joined = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "批处理性能报告" not in joined


# ============================================================
# emit_warnings 行为（人为构造慢节点）
# ============================================================


class _CapturingLogger:
    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)


def test_emit_warnings_triggers_when_p95_exceeds_threshold(tmp_path):
    """构造一个 slow=2000ms 的合成 record，验证慢节点告警链路。"""
    from processor.perf import aggregate

    rec = PerfRecord(
        samples=[("fast", 5.0), ("very_slow", 2000.0)],
        total_ms=2005.0,
    )
    report = aggregate([rec])
    fake = _CapturingLogger()
    n = report.emit_warnings(fake, threshold_ms=1000.0)
    assert n == 1
    assert any("very_slow" in w for w in fake.warnings)


# ============================================================
# PipelineEngine / start_process 直接调用模式
# ============================================================


def test_pipeline_engine_perf_record_total_ms(sample_image, tmp_path):
    """直接通过 PipelineEngine 调用，PerfRecord.total_ms 应被填充。"""
    out_path = tmp_path / "out.jpg"
    perf = PerfRecord()
    engine = PipelineEngine(
        data=[{"processor_name": "resize", "ratio": 0.5}],
        input_path=str(sample_image),
        output_path=str(out_path),
        perf_record=perf,
    )
    engine.execute()
    assert perf.total_ms > 0.0
    names = {n for n, _ in perf.samples}
    assert "resize" in names


def test_start_process_accepts_perf_record(sample_image, tmp_path):
    """``start_process(perf_record=...)`` 应将 timing 写入传入的 record。"""
    out_path = tmp_path / "out.jpg"
    perf = PerfRecord()
    start_process(
        data=[{"processor_name": "resize", "ratio": 0.5}],
        input_path=str(sample_image),
        output_path=str(out_path),
        perf_record=perf,
    )
    assert perf.total_ms > 0.0
    assert any(n == "resize" for n, _ in perf.samples)


def test_pipeline_engine_without_perf_record_still_works(sample_image, tmp_path):
    """不传 perf_record 时不应抛错（向后兼容）。"""
    out_path = tmp_path / "out.jpg"
    engine = PipelineEngine(
        data=[{"processor_name": "resize", "ratio": 0.5}],
        input_path=str(sample_image),
        output_path=str(out_path),
    )
    engine.execute()
    assert out_path.exists()
