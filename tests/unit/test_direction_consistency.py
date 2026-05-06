"""保证 ``Direction`` 枚举只有一份"权威定义"。

历史上 [`processor/core.py:201`](processor/core.py:201) 与 [`processor/types.py:8`](processor/types.py:8)
两处都定义过 ``Direction``，导致跨模块 ``isinstance`` 失败。
此测试持续守护合并后只有一份的状态。
"""
from __future__ import annotations

from processor import core as processor_core
from processor.types import Direction


def test_processor_core_direction_is_types_direction() -> None:
    """processor.core.Direction 必须与 processor.types.Direction 同一对象（兼容别名）。"""
    assert processor_core.Direction is Direction


def test_direction_values_complete() -> None:
    expected = {"horizontal", "vertical", "diagonal", "radial"}
    assert {d.value for d in Direction} == expected


def test_direction_horizontal_is_singleton() -> None:
    """无论从哪里 import，HORIZONTAL 都应当是同一对象。"""
    from processor.core import Direction as D1
    from processor.types import Direction as D2

    assert D1.HORIZONTAL is D2.HORIZONTAL
