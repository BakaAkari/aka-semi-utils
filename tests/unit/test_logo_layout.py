"""Logo 布局行为测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from gui.models import AppState, CornerConfig, FieldChip, LogoConfig
from gui.template_assembler import _build_watermark_config
from processor.core import PipelineContext
from processor.filters import WatermarkFilter


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _make_logo(path: Path) -> Path:
    img = Image.new("RGBA", (40, 20), (0, 0, 255, 255))
    img.save(path)
    return path


def _base_ctx(tmp_path: Path, *, logo_key: str, logo_height: int = 0) -> PipelineContext:
    logo_path = _make_logo(tmp_path / f"{logo_key}.png")
    ctx = PipelineContext({
        "buffer": [Image.new("RGBA", (300, 200), (255, 255, 255, 255))],
        "bottom_margin": 100,
        "left_top": {"processor_name": "rich_text", "text": "LT", "height": 20, "color": "#333333"},
        "left_bottom": {"processor_name": "rich_text", "text": "LB", "height": 20, "color": "#333333"},
        "right_top": {"processor_name": "rich_text", "text": "RT", "height": 20, "color": "#333333"},
        "right_bottom": {"processor_name": "rich_text", "text": "RB", "height": 20, "color": "#333333"},
        "delimiter_color": "#ff0000",
        "delimiter_width": 4,
        logo_key: str(logo_path),
    })
    if logo_height > 0:
        ctx.set("logo_height", logo_height)
    return ctx


def _bbox_for_color(img: Image.Image, color: tuple[int, int, int]) -> tuple[int, int, int, int]:
    pixels = img.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            if a and (r, g, b) == color:
                xs.append(x)
                ys.append(y)
    assert xs and ys
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _right_text_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    pixels = img.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(img.height):
        for x in range(img.width // 2, img.width):
            r, g, b, a = pixels[x, y]
            if a and (r, g, b) == (51, 51, 51):
                xs.append(x)
                ys.append(y)
    assert xs and ys
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _render(ctx: PipelineContext) -> Image.Image:
    WatermarkFilter().process(ctx)
    return ctx.get_buffer()[0]


def test_left_logo_default_height_matches_footer_and_has_delimiter_on_logo_right(tmp_path):
    out = _render(_base_ctx(tmp_path, logo_key="left_logo"))

    logo_bbox = _bbox_for_color(out, (0, 0, 255))
    delimiter_bbox = _bbox_for_color(out, (255, 0, 0))

    assert logo_bbox[3] - logo_bbox[1] == 100
    assert delimiter_bbox[3] - delimiter_bbox[1] == 80
    assert delimiter_bbox[1] - logo_bbox[1] == 10
    assert delimiter_bbox[0] > logo_bbox[2]


def test_right_logo_default_height_matches_footer_and_keeps_old_field_left_alignment(tmp_path):
    out = _render(_base_ctx(tmp_path, logo_key="right_logo"))

    logo_bbox = _bbox_for_color(out, (0, 0, 255))
    delimiter_bbox = _bbox_for_color(out, (255, 0, 0))
    text_bbox = _right_text_bbox(out)

    assert logo_bbox[3] - logo_bbox[1] == 100
    assert delimiter_bbox[3] - delimiter_bbox[1] == 80
    assert delimiter_bbox[1] - logo_bbox[1] == 10
    assert delimiter_bbox[0] > logo_bbox[2]
    assert delimiter_bbox[2] < text_bbox[0]


def test_center_logo_uses_same_logo_height_without_delimiter(tmp_path):
    out = _render(_base_ctx(tmp_path, logo_key="center_logo", logo_height=60))

    logo_bbox = _bbox_for_color(out, (0, 0, 255))
    assert logo_bbox[3] - logo_bbox[1] == 60

    pixels = out.load()
    red_pixels = [
        (x, y)
        for y in range(out.height)
        for x in range(out.width)
        if pixels[x, y][3] and pixels[x, y][:3] == (255, 0, 0)
    ]
    assert red_pixels == []


def test_advanced_logo_height_emits_unified_logo_height_key(qapp):
    state = AppState()
    state.logo = LogoConfig(enabled="custom", position="left", custom_path="/tmp/logo.png")
    state.left_top = CornerConfig(chips=[FieldChip(field_id="camera_model")])
    state.advanced.logo_height_px = 72

    node = _build_watermark_config(state)

    assert node["logo_height"] == 72
    assert "center_logo_height" not in node
