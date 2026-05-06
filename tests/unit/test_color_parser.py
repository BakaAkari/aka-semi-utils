"""测试 [`processor.core._parse_color`](processor/core.py:209) — 颜色解析在多个处理器中被反复使用。"""
from __future__ import annotations

import pytest

from processor.core import _parse_color


class TestTupleAndList:
    def test_rgb_tuple_appends_alpha(self) -> None:
        assert _parse_color((255, 0, 0)) == (255, 0, 0, 255)

    def test_rgba_tuple_unchanged(self) -> None:
        assert _parse_color((255, 0, 0, 128)) == (255, 0, 0, 128)

    def test_list_treated_as_tuple(self) -> None:
        assert _parse_color([0, 128, 255]) == (0, 128, 255, 255)


class TestStringFormats:
    def test_string_tuple_with_parens(self) -> None:
        assert _parse_color("(255,255,255,0)") == (255, 255, 255, 0)

    def test_string_tuple_without_parens(self) -> None:
        assert _parse_color("255,255,255,0") == (255, 255, 255, 0)

    def test_string_tuple_rgb(self) -> None:
        assert _parse_color("10,20,30") == (10, 20, 30, 255)

    def test_hex_six_digits(self) -> None:
        # Pillow ImageColor.getrgb 返回 RGB，函数补 alpha=255
        assert _parse_color("#FFFFFF") == (255, 255, 255, 255)

    def test_hex_short(self) -> None:
        assert _parse_color("#000") == (0, 0, 0, 255)

    def test_named_color(self) -> None:
        assert _parse_color("red") == (255, 0, 0, 255)

    def test_string_with_whitespace(self) -> None:
        assert _parse_color("  red  ") == (255, 0, 0, 255)


class TestErrors:
    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_color("not-a-color")

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_color(12345)  # type: ignore[arg-type]
