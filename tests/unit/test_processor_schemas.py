"""Phase 3.3 — 处理器参数 dataclass schema 单元测试。"""

from __future__ import annotations

import pytest

from processor.core import PipelineContext
from processor.schemas import (
    BlurParams,
    MarginParams,
    ResizeParams,
    ShadowParams,
    WatermarkParams,
)
from processor.types import Alignment


class TestBlurParams:
    def test_default(self):
        p = BlurParams.from_ctx(PipelineContext({}))
        assert p.radius == 5

    def test_custom(self):
        p = BlurParams.from_ctx(PipelineContext({"blur_radius": 12}))
        assert p.radius == 12

    def test_frozen(self):
        from dataclasses import FrozenInstanceError
        p = BlurParams()
        with pytest.raises(FrozenInstanceError):
            p.radius = 99  # type: ignore


class TestResizeParams:
    def test_all_none(self):
        p = ResizeParams.from_ctx(PipelineContext({}))
        assert p.width is None and p.height is None and p.scale is None

    def test_width_only(self):
        p = ResizeParams.from_ctx(PipelineContext({"width": 800}))
        assert p.width == 800
        assert p.height is None

    def test_scale_float(self):
        p = ResizeParams.from_ctx(PipelineContext({"scale": "0.5"}))
        assert p.scale == 0.5


class TestMarginParams:
    def test_defaults_zero(self):
        p = MarginParams.from_ctx(PipelineContext({}))
        assert p.left_margin == 0 and p.right_margin == 0
        assert p.top_margin == 0 and p.bottom_margin == 0
        assert p.margin_color == "white"

    def test_full_config(self):
        p = MarginParams.from_ctx(PipelineContext({
            "left_margin": 10,
            "right_margin": 20,
            "top_margin": 30,
            "bottom_margin": 40,
            "margin_color": "black",
        }))
        assert (p.left_margin, p.right_margin, p.top_margin, p.bottom_margin) == (10, 20, 30, 40)
        assert p.margin_color == "black"


class TestShadowParams:
    def test_defaults(self):
        p = ShadowParams.from_ctx(PipelineContext({}))
        assert p.shadow_radius == 30
        assert p.falloff == 1.5
        # 默认颜色应为 4-tuple RGBA
        assert len(p.shadow_color) == 4

    def test_custom_color(self):
        p = ShadowParams.from_ctx(PipelineContext({
            "shadow_color": (255, 0, 0, 128),
            "shadow_radius": 10,
        }))
        assert p.shadow_color == (255, 0, 0, 128)
        assert p.shadow_radius == 10


class TestWatermarkParams:
    def test_defaults_with_image_size(self):
        p = WatermarkParams.from_ctx(PipelineContext({}), img_width=1000, img_height=1000)
        assert p.color == "white"
        assert p.delimiter_color == "black"
        # delimiter_width = int(1000 * 0.003) = 3
        assert p.delimiter_width == 3
        # bottom_margin 默认固定值 120px
        assert p.bottom_margin == 120
        # middle_spacing = int(120 * 0.05) = 6
        assert p.middle_spacing == 6
        assert p.right_alignment == Alignment.RIGHT

    def test_explicit_overrides(self):
        ctx = PipelineContext({
            "color": "blue",
            "left_margin": 5,
            "bottom_margin": 200,
            "right_alignment": "LEFT",
        })
        p = WatermarkParams.from_ctx(ctx, img_width=500, img_height=500)
        assert p.color == "blue"
        assert p.left_margin == 5
        assert p.bottom_margin == 200
        assert p.right_alignment == Alignment.LEFT
