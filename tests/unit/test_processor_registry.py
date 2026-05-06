"""测试处理器自动注册机制：所有内置处理器都应能被名称查询到。"""
from __future__ import annotations

import pytest

# 触发自动注册（import 副作用）
import processor  # noqa: F401  # type: ignore[unused-ignore]
from processor.core import get_all_processors, get_processor

CORE_PROCESSORS = [
    # filters
    "blur", "resize", "trim", "margin", "margin_with_ratio",
    "watermark", "watermark_with_timestamp", "rounded_corner",
    "shadow", "crop",
    # generators
    "solid_color", "gradient_color", "rich_text", "multi_rich_text", "image",
    # mergers
    "alignment", "concat",
]


@pytest.mark.parametrize("name", CORE_PROCESSORS)
def test_core_processor_is_registered(name: str) -> None:
    assert get_processor(name) is not None, f"处理器 {name!r} 未注册"


def test_registry_is_non_empty() -> None:
    assert len(get_all_processors()) >= len(CORE_PROCESSORS)


def test_unknown_processor_returns_none() -> None:
    assert get_processor("definitely-not-a-real-processor") is None
