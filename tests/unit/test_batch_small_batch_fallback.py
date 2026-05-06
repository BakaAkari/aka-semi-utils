"""Phase 5.7 — ProcessPool 小批量串行 fallback 单元测试。

覆盖 [`processor.batch._resolve_max_workers()`](processor/batch.py:216) 的
Phase 5.4 行为：

- 自动模式 (``requested < 0``) 下任务数 < ``SMALL_BATCH_THRESHOLD`` → 返回 0；
- 自动模式且任务数 ≥ 阈值 → 返回 ``cpu_count() - 1``；
- 显式 ``requested > 0`` 不做 fallback，尊重用户意图（即使 1 个任务）。
"""
from __future__ import annotations

import multiprocessing

from processor.batch import SMALL_BATCH_THRESHOLD, _resolve_max_workers


class TestSmallBatchFallback:
    def test_threshold_is_positive_int(self):
        assert isinstance(SMALL_BATCH_THRESHOLD, int)
        assert SMALL_BATCH_THRESHOLD >= 2

    def test_auto_mode_below_threshold_returns_zero(self):
        # 任务数 < 阈值 → 串行
        assert _resolve_max_workers(-1, SMALL_BATCH_THRESHOLD - 1) == 0
        assert _resolve_max_workers(-1, 1) == 0

    def test_auto_mode_at_threshold_uses_pool(self):
        # 等于阈值已不属"小批量"，走并行
        result = _resolve_max_workers(-1, SMALL_BATCH_THRESHOLD)
        assert result >= 1
        assert result <= multiprocessing.cpu_count()

    def test_auto_mode_above_threshold_uses_cpu_minus_one(self):
        result = _resolve_max_workers(-1, 100)
        assert result == max(1, multiprocessing.cpu_count() - 1)

    def test_explicit_one_worker_no_fallback(self):
        """显式 max_workers=1 即使 1 个任务也不 fallback。"""
        # 注意 _resolve_max_workers 还会把上限封顶到 num_tasks
        # 显式 requested=1 + num_tasks=1 → 1
        assert _resolve_max_workers(1, 1) == 1

    def test_explicit_workers_capped_to_tasks(self):
        # requested=8 但只有 2 个任务 → ≤ 2
        assert _resolve_max_workers(8, 2) <= 2
        assert _resolve_max_workers(8, 2) >= 1

    def test_zero_request_always_serial(self):
        assert _resolve_max_workers(0, 100) == 0
        assert _resolve_max_workers(0, 1) == 0
        assert _resolve_max_workers(0, 0) == 0

    def test_zero_tasks_returns_zero(self):
        assert _resolve_max_workers(-1, 0) == 0
        assert _resolve_max_workers(4, 0) == 0
