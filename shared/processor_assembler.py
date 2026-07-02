"""Convert shared watermark configuration to processor JSON.

This module is the single source of truth for desktop and Web surfaces when they
need to translate user-facing watermark settings into the processor pipeline.
It intentionally depends only on shared schema/registry modules.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.field_registry import get_default_registry
from shared.render_values import LiteralText
from shared.watermark_schema import AdvancedConfig, CornerConfig, FieldChip, WatermarkConfig

logger = logging.getLogger(__name__)

PROCESSOR_MAP: dict[str, dict[str, Any]] = {
    "margin": {
        "fields": ["left_margin", "right_margin", "top_margin", "bottom_margin", "margin_color"],
        "target": "advanced",
        "processor_name": "margin",
    },
    "rounded_corner": {
        "fields": ["border_radius"],
        "target": "advanced",
        "processor_name": "rounded_corner",
    },
    "shadow": {
        "fields": ["shadow_radius", "shadow_color"],
        "target": "advanced",
        "processor_name": "shadow",
    },
    "blur": {
        "fields": ["blur_radius"],
        "target": "advanced",
        "processor_name": "blur",
    },
    "resize": {
        "fields": ["scale"],
        "target": "advanced",
        "processor_name": "resize",
    },
    "trim": {
        "fields": ["trim_enabled", "trim_threshold"],
        "target": "advanced",
        "processor_name": "trim",
    },
    "margin_with_ratio": {
        "fields": ["ratio"],
        "target": "advanced",
        "processor_name": "margin_with_ratio",
    },
    "concat": {
        "fields": ["concat_direction"],
        "target": "advanced",
        "processor_name": "concat",
    },
    "alignment": {
        "fields": ["alignment_mode"],
        "target": "advanced",
        "processor_name": "alignment",
    },
    "watermark": {
        "fields": ["*"],
        "target": "watermark",
        "processor_name": "watermark",
    },
    "signature": {
        "fields": [
            "signature_enabled",
            "signature_path",
            "signature_invert_mono",
            "signature_enhancement",
            "signature_enhancement_strength",
            "signature_anchor",
            "signature_margin_x",
            "signature_margin_y",
            "signature_size_ratio",
        ],
        "target": "signature",
        "processor_name": "signature",
    },
}


def config_to_processors(config: WatermarkConfig) -> list[dict[str, Any]]:
    """Convert a shared watermark config into processor pipeline JSON."""

    processors: list[dict[str, Any]] = []

    for key, mapping in PROCESSOR_MAP.items():
        processor_name = mapping["processor_name"]
        target = mapping["target"]
        fields = mapping["fields"]

        if target == "advanced":
            params: dict[str, Any] = {}
            advanced = config.advanced
            for field in fields:
                value = getattr(advanced, field, None)
                if value is not None:
                    params[field] = value

            if key == "margin" and all(params.get(f"{d}_margin", 0) == 0 for d in ["left", "right", "top", "bottom"]):
                continue
            if key == "rounded_corner" and params.get("border_radius", 0) == 0:
                continue
            if key == "shadow" and params.get("shadow_radius", 0) == 0:
                continue
            if key == "blur" and params.get("blur_radius", 0) == 0:
                continue
            if key == "resize" and params.get("scale", 1.0) == 1.0:
                continue
            if key == "trim" and not params.get("trim_enabled", False):
                continue
            if key == "margin_with_ratio" and not advanced.ratio_enabled:
                continue
            if key == "concat" and params.get("concat_direction", "vertical") == "vertical":
                continue
            if key == "alignment" and params.get("alignment_mode", "center") == "center":
                continue

            if params:
                processors.append({"processor_name": processor_name, **params})

        elif target == "watermark":
            watermark_config = _build_watermark_config(config)
            if watermark_config:
                processors.append({"processor_name": processor_name, **watermark_config})

        elif target == "signature":
            signature_config = _build_signature_config(config)
            if signature_config:
                processors.append({"processor_name": processor_name, **signature_config})

    return processors


def _resolve_chip_style(
    chip: FieldChip,
    corner: CornerConfig,
    advanced: AdvancedConfig,
) -> tuple[str, str]:
    """Resolve font/color for a chip.

    The current product model uses global font and color. The extra arguments are
    kept to preserve an extension point for future per-corner/per-chip styles.
    """

    _ = (chip, corner)
    return advanced.global_font, advanced.global_color


def _chips_for_corner(corner_cfg: CornerConfig) -> list[FieldChip]:
    """Return effective chips, migrating legacy Chinese fields lazily."""

    if corner_cfg.chips:
        return list(corner_cfg.chips)

    registry = get_default_registry()
    chips: list[FieldChip] = []
    for label in corner_cfg.fields or []:
        field_def = registry.get_by_label(label) or registry.resolve(label)
        chips.append(FieldChip(field_id=field_def.field_id if field_def else "empty"))
    return chips


def _chip_to_text(chip: FieldChip, config: WatermarkConfig) -> str:
    """Render a chip into a Jinja text fragment."""

    registry = get_default_registry()
    field_def = registry.get(chip.field_id)
    if field_def is None or field_def.field_id == "empty":
        return ""
    if field_def.field_id == "custom_text":
        return LiteralText(chip.custom_text or config.custom_text or "")
    return field_def.jinja_template


def _build_watermark_config(config: WatermarkConfig) -> dict[str, Any]:
    """Build the WatermarkFilter configuration node."""

    node: dict[str, Any] = {}

    for corner, attr in [
        ("left_top", "left_top"),
        ("left_bottom", "left_bottom"),
        ("right_top", "right_top"),
        ("right_bottom", "right_bottom"),
    ]:
        corner_cfg: CornerConfig = getattr(config, attr)
        chips = _chips_for_corner(corner_cfg)
        if not chips:
            continue

        segments: list[dict[str, str]] = []
        for chip in chips:
            text = _chip_to_text(chip, config)
            if not text:
                continue
            font, color = _resolve_chip_style(chip, corner_cfg, config.advanced)
            segments.append({"text": text, "color": color, "font_path": font})

        height_ratio = corner_cfg.font_size_ratio or config.advanced.corner_text_ratio
        default_font = config.advanced.global_font
        default_color = config.advanced.global_color

        if not segments:
            corner_node: dict[str, Any] = {
                "processor_name": "rich_text",
                "text": "",
                "color": default_color,
            }
        elif len(segments) == 1:
            segment = segments[0]
            corner_node = {
                "processor_name": "rich_text",
                "text": segment["text"],
                "color": segment["color"],
                "font_path": segment["font_path"],
            }
        else:
            text_segments: list[dict[str, Any]] = []
            for index, segment in enumerate(segments):
                if index > 0:
                    raw_separator = corner_cfg.separator.strip()
                    display_separator = LiteralText(
                        "  " if not raw_separator else f" {corner_cfg.separator} "
                    )
                    text_segments.append({
                        "text": display_separator,
                        "color": default_color,
                        "font_path": default_font,
                    })
                text_segments.append(segment)

            corner_node = {
                "processor_name": "multi_rich_text",
                "text_segments": text_segments,
            }

        if height_ratio > 0:
            corner_node["height_ratio"] = height_ratio
        node[corner] = corner_node

    logo = config.logo
    if logo.enabled != "disabled":
        if logo.enabled == "custom" and logo.custom_path:
            logo_path = logo.custom_path
        else:
            logo_path = "{{auto_logo()|replace('\\\\', '/')}}"

        if logo.position == "right":
            node["right_logo"] = logo_path
        elif logo.position == "center":
            node["center_logo"] = logo_path
        elif logo.position == "left":
            node["left_logo"] = logo_path

        node["delimiter_color"] = logo.color

    if config.custom_text:
        node["custom_text"] = LiteralText(config.custom_text)

    if config.advanced.footer_height_px > 0:
        node["bottom_margin"] = config.advanced.footer_height_px
    if config.advanced.logo_height_px > 0:
        node["logo_height"] = config.advanced.logo_height_px

    node["quality"] = config.advanced.quality
    node["subsampling"] = config.advanced.subsampling

    return node


def _build_signature_config(config: WatermarkConfig) -> dict[str, Any]:
    """Build SignatureFilter configuration, or empty dict when disabled.

    Phase 29: Prefer the dedicated ``config.signature`` field (Web surface),
    falling back to legacy ``config.advanced.signature_*`` for desktop compatibility.
    """

    # Web surface: dedicated signature block
    sig = config.signature
    if sig.enabled and sig.path:
        return {
            "signature_enabled": True,
            "signature_path": sig.path,
            "signature_invert_mono": sig.invert_mono,
            "signature_enhancement": sig.enhancement,
            "signature_enhancement_strength": sig.enhancement_strength,
            "signature_anchor": sig.anchor,
            "signature_margin_x": sig.margin_x,
            "signature_margin_y": sig.margin_y,
            "signature_size_ratio": sig.size_ratio,
        }

    # Legacy desktop surface
    advanced = config.advanced
    if not advanced.signature_enabled or not advanced.signature_path:
        return {}

    return {
        "signature_enabled": True,
        "signature_path": advanced.signature_path,
        "signature_invert_mono": advanced.signature_invert_mono,
        "signature_enhancement": advanced.signature_enhancement,
        "signature_enhancement_strength": advanced.signature_enhancement_strength,
        "signature_anchor": advanced.signature_anchor,
        "signature_margin_x": advanced.signature_margin_x,
        "signature_margin_y": advanced.signature_margin_y,
        "signature_size_ratio": advanced.signature_size_ratio,
    }
