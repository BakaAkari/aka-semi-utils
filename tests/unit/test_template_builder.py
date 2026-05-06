"""测试 [`core.template_builder.build_watermark_processor`](core/template_builder.py:39) 的关键分支。"""
from __future__ import annotations

from configparser import ConfigParser

import pytest

from core.template_builder import build_watermark_processor


@pytest.fixture
def basic_ini() -> ConfigParser:
    cp = ConfigParser()
    cp["DEFAULT"] = {
        "author_name": "Tester",
        "logo_path": "",
    }
    cp["custom_text"] = {"text": ""}
    return cp


def _user_template(layout: dict | None = None, logo_enabled: bool = True) -> dict:
    layout = layout or {
        "left_top":     {"sources": ["exif:CameraModelName"]},
        "left_bottom":  {"sources": ["exif:params"]},
        "right_top":    {"sources": ["author"]},
        "right_bottom": {"sources": ["exif:DateTimeOriginal"]},
    }
    return {
        "layout": layout,
        "logo": {"enabled": logo_enabled, "delimiter_color": "#D8D8D6"},
        "background": {"color": "white"},
    }


class TestBuildWatermarkProcessor:
    def test_returns_single_watermark_node(self, basic_ini: ConfigParser) -> None:
        result = build_watermark_processor(_user_template(), basic_ini)
        assert isinstance(result, list) and len(result) == 1
        assert result[0]["processor_name"] == "watermark"

    def test_all_four_corners_present(self, basic_ini: ConfigParser) -> None:
        node = build_watermark_processor(_user_template(), basic_ini)[0]
        for key in ("left_top", "left_bottom", "right_top", "right_bottom"):
            assert key in node, f"缺少四角字段: {key}"

    def test_logo_disabled_means_no_right_logo(self, basic_ini: ConfigParser) -> None:
        node = build_watermark_processor(_user_template(logo_enabled=False), basic_ini)[0]
        assert "right_logo" not in node

    def test_logo_enabled_inserts_jinja_expression(self, basic_ini: ConfigParser) -> None:
        node = build_watermark_processor(_user_template(logo_enabled=True), basic_ini)[0]
        # 未配置 logo_path 时，应是 auto_logo() Jinja2 表达式占位
        assert "right_logo" in node
        assert "auto_logo" in node["right_logo"]

    def test_empty_corner_falls_back_to_empty_text(self, basic_ini: ConfigParser) -> None:
        layout = {
            "left_top":     {"sources": ["empty"]},
            "left_bottom":  {"sources": ["empty"]},
            "right_top":    {"sources": ["empty"]},
            "right_bottom": {"sources": ["empty"]},
        }
        node = build_watermark_processor(_user_template(layout), basic_ini)[0]
        # 实现里 empty 会落到 rich_text 空文本
        assert node["left_top"]["processor_name"] == "rich_text"
        assert node["left_top"]["text"] == ""

    def test_multi_source_corner_uses_multi_rich_text(self, basic_ini: ConfigParser) -> None:
        layout = {
            "left_top":     {"sources": ["exif:CameraModelName", "exif:LensModel"], "separator": "|"},
            "left_bottom":  {"sources": ["empty"]},
            "right_top":    {"sources": ["empty"]},
            "right_bottom": {"sources": ["empty"]},
        }
        node = build_watermark_processor(_user_template(layout), basic_ini)[0]
        assert node["left_top"]["processor_name"] == "multi_rich_text"
        assert "text_segments" in node["left_top"]
        # 至少 2 个真实 segment + 1 个分隔符 segment
        assert len(node["left_top"]["text_segments"]) >= 3
