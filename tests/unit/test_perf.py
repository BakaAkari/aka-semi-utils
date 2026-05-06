"""Phase 5.7 — 性能统计模块单元测试。

覆盖 [`processor.perf`](processor/perf.py:1) 的全部公共 API：

- ``_percentile`` 线性插值（与 ``numpy.percentile`` 对照到 1e-9 精度）；
- ``PerfRecord.add`` / ``by_processor``（多次同名 processor 的样本分桶）；
- ``aggregate`` 跨 record 聚合 + ``ProcessorStat`` 字段正确性；
- ``BatchPerfReport.slowest`` / ``slow_processors`` / ``format_text`` /
  ``emit_warnings``；
- ``measure`` 上下文管理器；
- ``DEFAULT_SLOW_THRESHOLD_MS`` 默认阈值导出。
"""
from __future__ import annotations

import time

import pytest

from processor.perf import (
    DEFAULT_SLOW_THRESHOLD_MS,
    BatchPerfReport,
    PerfRecord,
    ProcessorStat,
    _percentile,
    aggregate,
    measure,
)

# ============================================================
# _percentile
# ============================================================


class TestPercentile:
    def test_empty_returns_zero(self):
        assert _percentile([], 50) == 0.0
        assert _percentile([], 95) == 0.0

    def test_single_value(self):
        assert _percentile([42.0], 50) == 42.0
        assert _percentile([42.0], 95) == 42.0
        assert _percentile([42.0], 0) == 42.0

    def test_p50_two_values_is_midpoint(self):
        # 线性插值：p50 of [10, 20] → 10*(1-0.5) + 20*0.5 = 15
        assert _percentile([10.0, 20.0], 50) == pytest.approx(15.0)

    def test_p100_returns_max(self):
        assert _percentile([1.0, 5.0, 9.0], 100) == 9.0

    def test_p0_returns_min(self):
        assert _percentile([1.0, 5.0, 9.0], 0) == 1.0

    def test_unsorted_input(self):
        """入参顺序不影响结果（内部排序）。"""
        a = _percentile([3.0, 1.0, 2.0, 5.0, 4.0], 50)
        b = _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50)
        assert a == pytest.approx(b)

    def test_p95_classic_dataset(self):
        # 21 个等距值 0..20，P95 → 95% 位 = 19.0
        values = [float(i) for i in range(21)]
        assert _percentile(values, 95) == pytest.approx(19.0)

    @pytest.mark.parametrize(
        "values,pct",
        [
            ([1.0, 2.0, 3.0, 4.0, 5.0], 50),
            ([1.0, 2.0, 3.0, 4.0, 5.0], 95),
            ([10.0, 11.0, 12.0, 100.0], 75),
            ([0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5], 25),
            ([100.0, 200.0, 300.0], 90),
        ],
    )
    def test_matches_numpy_percentile(self, values, pct):
        """与 numpy.percentile(linear) 对照（容差 1e-9）。"""
        np = pytest.importorskip("numpy")
        ours = _percentile(values, pct)
        ref = float(np.percentile(values, pct, method="linear"))
        assert ours == pytest.approx(ref, abs=1e-9)


# ============================================================
# PerfRecord
# ============================================================


class TestPerfRecord:
    def test_default_empty(self):
        r = PerfRecord()
        assert r.samples == []
        assert r.total_ms == 0.0

    def test_add_appends_in_order(self):
        r = PerfRecord()
        r.add("blur", 1.0)
        r.add("resize", 2.5)
        r.add("blur", 0.5)
        assert r.samples == [("blur", 1.0), ("resize", 2.5), ("blur", 0.5)]

    def test_by_processor_buckets_same_name(self):
        r = PerfRecord()
        r.add("blur", 1.0)
        r.add("resize", 2.0)
        r.add("blur", 3.0)
        bucket = r.by_processor()
        assert bucket == {"blur": [1.0, 3.0], "resize": [2.0]}

    def test_by_processor_empty_record(self):
        assert PerfRecord().by_processor() == {}

    def test_pickle_safe(self):
        """worker 子进程通过 pickle 把 PerfRecord 传回主进程。"""
        import pickle

        r = PerfRecord()
        r.add("blur", 1.5)
        r.add("resize", 2.5)
        r.total_ms = 10.0
        recovered: PerfRecord = pickle.loads(pickle.dumps(r))
        assert recovered.samples == r.samples
        assert recovered.total_ms == r.total_ms


# ============================================================
# aggregate / ProcessorStat
# ============================================================


class TestAggregate:
    def test_empty_records(self):
        report = aggregate([])
        assert report.file_count == 0
        assert report.total_pipeline_ms == 0.0
        assert report.per_processor == []
        assert report.mean_pipeline_ms == 0.0

    def test_single_record(self):
        r = PerfRecord()
        r.add("blur", 10.0)
        r.add("resize", 20.0)
        r.total_ms = 35.0

        report = aggregate([r])
        assert report.file_count == 1
        assert report.total_pipeline_ms == 35.0
        # 按 total_ms 降序：resize > blur
        names = [s.name for s in report.per_processor]
        assert names == ["resize", "blur"]

        resize_stat = report.per_processor[0]
        assert isinstance(resize_stat, ProcessorStat)
        assert resize_stat.count == 1
        assert resize_stat.mean_ms == pytest.approx(20.0)
        assert resize_stat.p50_ms == pytest.approx(20.0)
        assert resize_stat.p95_ms == pytest.approx(20.0)
        assert resize_stat.max_ms == 20.0
        assert resize_stat.total_ms == 20.0

    def test_multiple_records_cross_aggregation(self):
        r1 = PerfRecord(samples=[("blur", 5.0), ("resize", 10.0)], total_ms=20.0)
        r2 = PerfRecord(samples=[("blur", 15.0), ("resize", 20.0)], total_ms=40.0)
        r3 = PerfRecord(samples=[("blur", 25.0)], total_ms=30.0)

        report = aggregate([r1, r2, r3])
        assert report.file_count == 3
        assert report.total_pipeline_ms == pytest.approx(90.0)
        assert report.mean_pipeline_ms == pytest.approx(30.0)

        bucket = {s.name: s for s in report.per_processor}
        assert bucket["blur"].count == 3
        assert bucket["blur"].mean_ms == pytest.approx(15.0)
        assert bucket["blur"].max_ms == 25.0
        assert bucket["blur"].total_ms == 45.0

        assert bucket["resize"].count == 2
        assert bucket["resize"].total_ms == 30.0
        assert bucket["resize"].max_ms == 20.0

    def test_sort_descending_by_total(self):
        r = PerfRecord(
            samples=[("a", 1.0), ("b", 100.0), ("c", 50.0)],
            total_ms=151.0,
        )
        report = aggregate([r])
        names = [s.name for s in report.per_processor]
        assert names == ["b", "c", "a"]

    def test_same_processor_called_multiple_times_in_one_record(self):
        """同一 record 内重复出现的同名 processor 被累加为多条样本。"""
        r = PerfRecord()
        r.add("merge", 1.0)
        r.add("filter", 5.0)
        r.add("merge", 2.0)
        r.add("merge", 3.0)
        report = aggregate([r])
        merge_stat = next(s for s in report.per_processor if s.name == "merge")
        assert merge_stat.count == 3
        assert merge_stat.total_ms == pytest.approx(6.0)


# ============================================================
# BatchPerfReport.slowest / slow_processors / format_text
# ============================================================


class TestBatchPerfReport:
    def _make_report(self) -> BatchPerfReport:
        r1 = PerfRecord(
            samples=[("fast", 1.0), ("slow", 1500.0), ("medium", 200.0)],
            total_ms=1701.0,
        )
        r2 = PerfRecord(
            samples=[("fast", 2.0), ("slow", 2500.0), ("medium", 300.0)],
            total_ms=2802.0,
        )
        return aggregate([r1, r2])

    def test_slowest_topn(self):
        report = self._make_report()
        top1 = report.slowest(1)
        assert len(top1) == 1
        assert top1[0].name == "slow"

        top2 = report.slowest(2)
        assert [s.name for s in top2] == ["slow", "medium"]

    def test_slowest_more_than_available(self):
        report = self._make_report()
        # 仅 3 个 processor，请求 10 应返回全部
        all_stats = report.slowest(10)
        assert len(all_stats) == 3

    def test_slow_processors_default_threshold(self):
        report = self._make_report()
        slows = report.slow_processors()  # 默认 1000ms 阈值
        assert [s.name for s in slows] == ["slow"]

    def test_slow_processors_custom_threshold(self):
        report = self._make_report()
        # 100ms 阈值 → slow + medium 都算慢节点
        slows = report.slow_processors(threshold_ms=100.0)
        names = sorted(s.name for s in slows)
        assert names == ["medium", "slow"]

    def test_slow_processors_high_threshold_returns_empty(self):
        report = self._make_report()
        slows = report.slow_processors(threshold_ms=10_000.0)
        assert slows == []

    def test_format_text_empty_report(self):
        empty = BatchPerfReport()
        assert "无性能数据" in empty.format_text()

    def test_format_text_contains_processor_names(self):
        report = self._make_report()
        text = report.format_text(top_n=5)
        assert "slow" in text
        assert "medium" in text
        # 文件总数与平均耗时 / 条目数
        assert "2" in text  # 2 个文件
        # 表头列名
        assert "mean" in text
        assert "P50" in text
        assert "P95" in text

    def test_mean_pipeline_ms_no_div_by_zero(self):
        empty = BatchPerfReport()
        assert empty.mean_pipeline_ms == 0.0

    def test_pickle_safe(self):
        import pickle

        report = self._make_report()
        recovered: BatchPerfReport = pickle.loads(pickle.dumps(report))
        assert recovered.file_count == report.file_count
        assert recovered.total_pipeline_ms == report.total_pipeline_ms
        assert len(recovered.per_processor) == len(report.per_processor)


# ============================================================
# emit_warnings
# ============================================================


class _FakeLogger:
    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, msg: str) -> None:  # 与 loguru / logging 兼容
        self.warnings.append(msg)


class TestEmitWarnings:
    def _make_report(self) -> BatchPerfReport:
        r = PerfRecord(
            samples=[("a", 100.0), ("b", 1500.0), ("c", 2000.0)],
            total_ms=3600.0,
        )
        return aggregate([r])

    def test_emit_returns_count_default_threshold(self):
        report = self._make_report()
        fake = _FakeLogger()
        n = report.emit_warnings(fake)
        assert n == 2  # b 和 c 超 1000ms
        assert len(fake.warnings) == 2
        joined = "\n".join(fake.warnings)
        assert "b" in joined and "c" in joined
        assert "P95" in joined

    def test_emit_with_custom_threshold(self):
        report = self._make_report()
        fake = _FakeLogger()
        n = report.emit_warnings(fake, threshold_ms=200.0)
        assert n == 2  # b 和 c 都 > 200ms

    def test_emit_no_slow_no_warnings(self):
        report = self._make_report()
        fake = _FakeLogger()
        n = report.emit_warnings(fake, threshold_ms=10_000.0)
        assert n == 0
        assert fake.warnings == []

    def test_emit_warnings_message_format(self):
        report = self._make_report()
        fake = _FakeLogger()
        report.emit_warnings(fake)
        for msg in fake.warnings:
            assert "[perf]" in msg
            assert "慢节点" in msg
            assert "阈值" in msg


# ============================================================
# measure 上下文管理器
# ============================================================


class TestMeasure:
    def test_records_elapsed(self):
        r = PerfRecord()
        with measure(r, "sleep_block"):
            time.sleep(0.01)
        assert len(r.samples) == 1
        name, ms = r.samples[0]
        assert name == "sleep_block"
        # 至少 5ms（留松弛防 CI 抖动），至多 200ms（防误差爆炸）
        assert 5.0 < ms < 200.0

    def test_records_even_on_exception(self):
        r = PerfRecord()
        with pytest.raises(RuntimeError):
            with measure(r, "boom"):
                raise RuntimeError("expected")
        assert len(r.samples) == 1
        assert r.samples[0][0] == "boom"

    def test_multiple_blocks_accumulate(self):
        r = PerfRecord()
        with measure(r, "a"):
            pass
        with measure(r, "b"):
            pass
        with measure(r, "a"):
            pass
        names = [s[0] for s in r.samples]
        assert names == ["a", "b", "a"]


# ============================================================
# 模块导出
# ============================================================


def test_default_slow_threshold_constant():
    assert DEFAULT_SLOW_THRESHOLD_MS == 1000.0
    assert isinstance(DEFAULT_SLOW_THRESHOLD_MS, float)


def test_public_exports():
    import processor.perf as perf

    assert "PerfRecord" in perf.__all__
    assert "BatchPerfReport" in perf.__all__
    assert "ProcessorStat" in perf.__all__
    assert "aggregate" in perf.__all__
    assert "measure" in perf.__all__
    assert "DEFAULT_SLOW_THRESHOLD_MS" in perf.__all__
