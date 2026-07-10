"""Integration tests for V3 watermark API pipeline.

Validates that V3 payloads are correctly validated, assembled, and processed
through the full backend pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from shared.v3_assembler import v3_config_to_processors
from web_api.schemas_v3 import validate_v3_payload

SAMPLE_V3_CONFIG = {
    "canvas": {
        "margins": {"top": 0, "right": 0, "bottom": 0, "left": 0},
        "background": "#FFFFFF",
        "border_radius": 0,
    },
    "regions": [
        {
            "id": "footer",
            "type": "footer-bar",
            "enabled": True,
            "slots": {
                "left-top": {
                    "enabled": True,
                    "content": {
                        "chips": [{"field_id": "make"}, {"field_id": "camera_model"}],
                        "separator": " ",
                    },
                    "style": {
                        "font_size": None,
                        "font_size_ratio": 0.45,
                        "size_reference": "region_height",
                        "color": "#222222",
                        "font_family": "NotoSansCJKsc-Bold.otf",
                        "bold": True,
                        "line_height": 1.2,
                    },
                },
                "left-bottom": {
                    "enabled": True,
                    "content": {
                        "chips": [
                            {"field_id": "focal_length"},
                            {"field_id": "aperture"},
                            {"field_id": "shutter"},
                            {"field_id": "iso"},
                        ],
                        "separator": " ",
                    },
                    "style": {
                        "font_size": None,
                        "font_size_ratio": 0.35,
                        "size_reference": "region_height",
                        "color": "#222222",
                        "font_family": "NotoSansCJKsc-Bold.otf",
                        "bold": True,
                        "line_height": 1.2,
                    },
                },
                "right-logo": {
                    "enabled": True,
                    "content": {"path": "", "color": "#D8D8D6"},
                    "style": None,
                },
            },
        }
    ],
    "defaults": {
        "font_size": None,
        "font_size_ratio": 0.35,
        "size_reference": "region_height",
        "color": "#222222",
        "font_family": "NotoSansCJKsc-Bold.otf",
        "bold": True,
        "line_height": 1.2,
    },
    "custom_text": "",
}


class TestV3PayloadValidation:
    """Test schemas_v3 validation."""

    def test_valid_default_payload(self):
        result = validate_v3_payload(SAMPLE_V3_CONFIG)
        assert result["canvas"]["background"] == "#FFFFFF"
        assert len(result["regions"]) == 1
        assert result["regions"][0]["id"] == "footer"

    def test_empty_dict_defaults(self):
        result = validate_v3_payload({})
        assert result["canvas"]["background"] == "#FFFFFF"
        assert result["regions"] == []

    def test_invalid_color_rejected(self):
        bad = {"canvas": {"background": "not-a-color"}}
        with pytest.raises(Exception) as exc:
            validate_v3_payload(bad)
        assert "颜色" in (exc.value.detail or "")

    def test_invalid_font_size_ratio_rejected(self):
        bad = {
            "defaults": {"font_size_ratio": 0.99}
        }
        with pytest.raises(Exception) as exc:
            validate_v3_payload(bad)
        assert "less than or equal" in (exc.value.detail or "").lower() or "不合法" in (exc.value.detail or "")


class TestV3Assembler:
    """Test v3_config_to_processors produces correct pipeline JSON."""

    def test_assembler_produces_single_node(self):
        processors = v3_config_to_processors(SAMPLE_V3_CONFIG)
        assert len(processors) == 1
        assert processors[0]["processor_name"] == "v3_watermark"
        assert "v3_config" in processors[0]

    def test_empty_config_returns_empty_list(self):
        assert v3_config_to_processors({}) == []

    def test_nested_config_preserved(self):
        processors = v3_config_to_processors(SAMPLE_V3_CONFIG)
        v3_config = processors[0]["v3_config"]
        assert v3_config["regions"][0]["slots"]["left-top"]["enabled"] is True


class TestV3EndToEndProcessing:
    """Test the full V3 pipeline with a real image."""

    @pytest.fixture
    def sample_image(self, tmp_path: Path) -> Path:
        path = tmp_path / "test.jpg"
        img = Image.new("RGB", (1200, 800), color="#3A3832")
        img.save(path, quality=95)
        return path

    def test_v3_watermark_filter_runs(self, sample_image: Path, tmp_path: Path):
        """End-to-end: v3_watermark processor runs and produces output."""
        import processor  # registers processors
        import processor.v3_watermark  # noqa: F401  # registers v3_watermark
        from core.template_builder import render_processors
        from processor.core import start_process

        processors_template = v3_config_to_processors(SAMPLE_V3_CONFIG)
        processors = render_processors(processors_template, {}, str(sample_image))

        output_path = tmp_path / "output.jpg"
        start_process(
            data=processors,
            input_path=str(sample_image),
            output_path=str(output_path),
        )

        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.width > 0 and img.height > 0

    def test_v3_layout_result_matches_expected_structure(self):
        """Verify layout engine produces expected canvas structure for 16:9."""
        from processor.v3_watermark import _dict_to_watermark_config
        from shared.v3_layout.layout_engine import compute_layout

        config = validate_v3_payload(SAMPLE_V3_CONFIG)
        watermark_config = _dict_to_watermark_config(config)

        layout = compute_layout(watermark_config, 1920, 1080)

        # Canvas should be wider than image (margins)
        assert layout.canvas.w >= 1920
        assert layout.canvas.h >= 1080
        # Image should be centered
        assert layout.image_rect.x >= 0
        assert layout.image_rect.y >= 0
        # Should have text elements
        text_elements = [e for e in layout.elements if e.type == "text"]
        assert len(text_elements) >= 2  # left-top + left-bottom

    def test_v3_portrait_layout(self):
        """Verify 9:16 portrait orientation is handled correctly."""
        from processor.v3_watermark import _dict_to_watermark_config
        from shared.v3_layout.layout_engine import compute_layout

        config = validate_v3_payload(SAMPLE_V3_CONFIG)
        watermark_config = _dict_to_watermark_config(config)

        # 9:16 portrait (e.g., 1080x1920)
        layout = compute_layout(watermark_config, 1080, 1920)

        assert layout.canvas.w >= 1080
        assert layout.canvas.h >= 1920
        assert layout.image_rect.w == 1080
        assert layout.image_rect.h == 1920

        # Footer bar should be at bottom
        footer_elements = [e for e in layout.elements if e.type == "text"]
        assert len(footer_elements) >= 2
