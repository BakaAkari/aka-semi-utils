from __future__ import annotations

from shared.processor_assembler import config_to_processors
from shared.watermark_schema import AdvancedConfig, CornerConfig, FieldChip, LogoConfig, WatermarkConfig


def _sample_config() -> WatermarkConfig:
    return WatermarkConfig(
        left_top=CornerConfig(chips=[FieldChip("camera_model")]),
        left_bottom=CornerConfig(
            chips=[FieldChip("focal_length"), FieldChip("aperture"), FieldChip("iso")],
            separator="/",
            font_size_ratio=0.025,
        ),
        right_bottom=CornerConfig(chips=[FieldChip("custom_text", "AKARI")]),
        logo=LogoConfig(enabled="auto", position="right", color="#D8D8D6"),
        custom_text="fallback text",
        advanced=AdvancedConfig(
            footer_height_px=160,
            logo_height_px=48,
            corner_text_ratio=0.02,
            blur_radius=8,
            border_radius=12,
            shadow_radius=10,
            shadow_color="#101010",
            left_margin=11,
            right_margin=12,
            top_margin=13,
            bottom_margin=14,
            quality=88,
            subsampling=1,
            scale=0.5,
            trim_enabled=True,
            trim_threshold=8,
            ratio_enabled=True,
            ratio="4:5",
            concat_direction="horizontal",
            alignment_mode="bottom",
        ),
    )


def test_shared_assembler_builds_expected_processors() -> None:
    processors = config_to_processors(_sample_config())

    assert [p["processor_name"] for p in processors] == [
        "margin",
        "rounded_corner",
        "shadow",
        "blur",
        "resize",
        "trim",
        "margin_with_ratio",
        "concat",
        "alignment",
        "watermark",
    ]

    margin = processors[0]
    assert margin["left_margin"] == 11
    assert margin["right_margin"] == 12
    assert margin["top_margin"] == 13
    assert margin["bottom_margin"] == 14
    assert processors[4]["scale"] == 0.5
    assert processors[5]["trim_enabled"] is True
    assert processors[5]["trim_threshold"] == 8
    assert processors[6]["ratio"] == "4:5"
    assert processors[7]["concat_direction"] == "horizontal"
    assert processors[8]["alignment_mode"] == "bottom"

    watermark = processors[-1]
    assert watermark["processor_name"] == "watermark"
    assert watermark["bottom_margin"] == 160
    assert watermark["logo_height"] == 48
    assert watermark["quality"] == 88
    assert watermark["subsampling"] == 1
    assert watermark["right_logo"].count("\\") == 4
    assert watermark["delimiter_color"] == "#D8D8D6"
    assert watermark["left_top"]["text"] == "{{ exif.CameraModelName|default('-') | replace('_', '') }}"
    assert watermark["left_bottom"]["processor_name"] == "multi_rich_text"
    assert watermark["right_bottom"]["text"] == "AKARI"
