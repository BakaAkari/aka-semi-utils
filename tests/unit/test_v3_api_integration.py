"""Integration tests for V3 watermark API pipeline.

Validates that V3 payloads are correctly validated, assembled, and processed
through the full backend pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from shared.v3_assembler import v3_config_to_processors
from web_api.errors import ApiError
from web_api.schemas_v3 import validate_v3_payload

SAMPLE_V3_CONFIG = {
    "canvas": {
        "margins": {"top": 0, "right": 0, "bottom": 80, "left": 0},
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

    @pytest.mark.parametrize(
        ("patch_path", "value"),
        [
            (("defaults", "font_family"), "/etc/passwd"),
            (("regions", 0, "anchor"), "not-an-anchor"),
            (("regions", 0, "slots", "right-logo", "content", "path"), "/etc/passwd"),
        ],
    )
    def test_server_paths_and_unknown_anchors_rejected(self, patch_path, value):
        from copy import deepcopy

        bad = deepcopy(SAMPLE_V3_CONFIG)
        target = bad
        for part in patch_path[:-1]:
            target = target[part]
        target[patch_path[-1]] = value

        with pytest.raises(ApiError):
            validate_v3_payload(bad)

    def test_pixel_width_uses_pixel_range(self):
        from copy import deepcopy

        config = deepcopy(SAMPLE_V3_CONFIG)
        config["regions"] = [{
            "id": "side-left",
            "type": "side-edge",
            "enabled": True,
            "edge": "left",
            "width": {"mode": "pixel", "value": 240.0},
            "slots": {},
        }]

        parsed = validate_v3_payload(config)
        assert parsed["regions"][0]["width"] == {"mode": "pixel", "value": 240.0}

    def test_ratio_width_above_one_rejected(self):
        from copy import deepcopy

        config = deepcopy(SAMPLE_V3_CONFIG)
        config["regions"] = [{
            "id": "side-left",
            "type": "side-edge",
            "enabled": True,
            "edge": "left",
            "width": {"mode": "short_edge_ratio", "value": 1.1},
            "slots": {},
        }]

        with pytest.raises(ApiError):
            validate_v3_payload(config)

    def test_non_finite_offset_rejected(self):
        from copy import deepcopy

        config = deepcopy(SAMPLE_V3_CONFIG)
        config["regions"] = [{
            "id": "free-1",
            "type": "free",
            "enabled": True,
            "anchor": "bottom-right",
            "offset_x": float("nan"),
            "slots": {},
        }]

        with pytest.raises(ApiError):
            validate_v3_payload(config)


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


class TestV3ResourceResolution:
    def test_opaque_logo_id_is_resolved_without_mutating_public_config(self, tmp_path: Path):
        from copy import deepcopy

        from web_api.processing import _resolve_v3_resources
        from web_api.settings import WebApiSettings

        resource_id = f"{'a' * 20}.png"
        logo_dir = tmp_path / "resources" / "logo"
        logo_dir.mkdir(parents=True)
        Image.new("RGBA", (8, 8)).save(logo_dir / resource_id)
        settings = WebApiSettings(
            data_dir=tmp_path,
            upload_dir=tmp_path / "uploads",
            output_dir=tmp_path / "outputs",
            resources_dir=tmp_path / "resources",
            tmp_dir=tmp_path / "tmp",
        )
        config = deepcopy(SAMPLE_V3_CONFIG)
        config["regions"][0]["slots"]["right-logo"]["content"]["path"] = resource_id
        validated = validate_v3_payload(config)

        resolved = _resolve_v3_resources(validated, settings)

        assert resolved["regions"][0]["slots"]["right-logo"]["content"]["path"] == str(logo_dir / resource_id)
        assert validated["regions"][0]["slots"]["right-logo"]["content"]["path"] == resource_id


class TestV3EndToEndProcessing:
    """Test the full V3 pipeline with a real image."""

    @pytest.fixture
    def sample_image(self, tmp_path: Path) -> Path:
        path = tmp_path / "test.jpg"
        img = Image.new("RGB", (1200, 800), color="#3A3832")
        img.save(path, quality=95)
        return path

    def test_v3_watermark_filter_runs(self, sample_image: Path, tmp_path: Path):
        """Production registration runs V3 directly without generic Jinja rendering."""
        import processor  # noqa: F401  # registers production processors
        from processor.core import get_all_processors, start_process

        assert "v3_watermark" in get_all_processors()
        processors = v3_config_to_processors(SAMPLE_V3_CONFIG)

        output_path = tmp_path / "output.jpg"
        start_process(
            data=processors,
            input_path=str(sample_image),
            output_path=str(output_path),
        )

        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.width > 0 and img.height > 0

    def test_v3_custom_text_stays_literal(self):
        from processor.v3_watermark import _build_text
        from shared.v3_layout.layout_engine import FieldChip, TextContent

        content = TextContent(
            chips=[FieldChip(field_id="custom_text", custom_text="probe={{ 7 * 7 }}")],
            separator=" ",
        )

        assert _build_text(content, "", {}, "image.jpg") == "probe={{ 7 * 7 }}"

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
