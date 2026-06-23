"""模板组装器 — GUI 状态 → Processor JSON 的正向转换器。

Phase 15：模板系统已移除，本模块只保留 START 按钮所需的"AppState → 处理器列表"正向流。
反向流（processors_to_state / _apply_watermark_config / load_template / save_template）
连同模板文件加载、JSON 双向编辑器一同被删除，不再需要。
"""

import logging
from typing import Any

from .field_registry import get_default_registry
from .models import AdvancedConfig, AppState, CornerConfig, FieldChip

logger = logging.getLogger(__name__)

# 处理器映射字典 — 新增处理器只需加一行
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
        "fields": ["*"],  # 特殊：处理所有四角+Logo
        "target": "watermark",
        "processor_name": "watermark",
    },
    # 签名 — 串接在 watermark 之后，仅当 signature_enabled 时生成。
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


def state_to_processors(state: AppState) -> list[dict[str, Any]]:
    """AppState → Processor JSON 列表（正向转换，仅用于 START 按钮）。"""
    processors = []

    for key, mapping in PROCESSOR_MAP.items():
        processor_name = mapping["processor_name"]
        target = mapping["target"]
        fields = mapping["fields"]

        if target == "advanced":
            # 从 AdvancedConfig 读取字段
            config = state.advanced
            params = {}
            for field in fields:
                value = getattr(config, field, None)
                if value is not None:
                    params[field] = value

            # 跳过默认值（避免无意义处理器）
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
            if key == "margin_with_ratio" and not config.ratio_enabled:
                continue
            if key == "concat" and params.get("concat_direction", "vertical") == "vertical":
                # 默认 vertical，不生成处理器
                continue
            if key == "alignment" and params.get("alignment_mode", "center") == "center":
                # 默认 center，不生成处理器
                continue

            if params:
                processors.append({
                    "processor_name": processor_name,
                    **params,
                })

        elif target == "watermark":
            # 构建水印处理器（WatermarkFilter）
            watermark_config = _build_watermark_config(state)
            if watermark_config:
                processors.append({
                    "processor_name": processor_name,
                    **watermark_config,
                })

        elif target == "signature":
            # Phase 17：签名 processor — 仅在启用且路径非空时输出
            signature_config = _build_signature_config(state)
            if signature_config:
                processors.append({
                    "processor_name": processor_name,
                    **signature_config,
                })

    return processors


def _resolve_chip_style(
    chip: FieldChip, corner: CornerConfig, advanced: AdvancedConfig
) -> tuple[str, str]:
    """解析 (font, color)：字体和颜色统一由全局参数决定。"""
    font = advanced.global_font
    color = advanced.global_color
    return font, color


def _chips_for_corner(corner_cfg: CornerConfig) -> list[FieldChip]:
    """返回有效 chips：优先 ``chips`` 字段；空时退回中文 ``fields`` 兼容。"""
    if corner_cfg.chips:
        return list(corner_cfg.chips)
    # 旧 fields 路径：把每个中文字段 lazy 转 chip
    registry = get_default_registry()
    out: list[FieldChip] = []
    for label in corner_cfg.fields or []:
        fdef = registry.get_by_label(label) or registry.resolve(label)
        out.append(FieldChip(field_id=fdef.field_id if fdef else "empty"))
    return out


def _chip_to_text(chip: FieldChip, state: AppState) -> str:
    """把 chip 渲染成 Jinja 文本片段；空字段返回空串。"""
    registry = get_default_registry()
    fdef = registry.get(chip.field_id)
    if fdef is None or fdef.field_id == "empty":
        return ""
    if fdef.field_id == "custom_text":
        # 优先使用 chip 自带文本；否则退回全局 custom_text（向后兼容）
        return chip.custom_text or state.custom_text or ""
    return fdef.jinja_template


def _build_watermark_config(state: AppState) -> dict[str, Any]:
    """从 AppState 构建水印处理器配置（嵌套格式，兼容 WatermarkFilter）。

    Phase 6.4：字段映射统一从 :class:`FieldRegistry` 读取，不再硬编码。
    Phase 6.3：每个 chip 可独立指定 font/color，缺失时按继承链回落。
    """
    config: dict[str, Any] = {}

    for corner, attr in [
        ("left_top", "left_top"),
        ("left_bottom", "left_bottom"),
        ("right_top", "right_top"),
        ("right_bottom", "right_bottom"),
    ]:
        corner_cfg: CornerConfig = getattr(state, attr)
        chips = _chips_for_corner(corner_cfg)
        if not chips:
            continue

        # 构建 text segments（每个 chip 独立 font/color）
        segments: list[dict[str, str]] = []
        for chip in chips:
            text = _chip_to_text(chip, state)
            if not text:
                continue
            font, color = _resolve_chip_style(chip, corner_cfg, state.advanced)
            segments.append({
                "text": text,
                "color": color,
                "font_path": font,
            })

        # Phase 28：相对比例字号 — 传递 height_ratio，由处理器按图片短边计算实际像素。
        # 0 = 沿用旧自适应（处理器内部仍按 bottom_margin*0.3 推导）。
        height_ratio = corner_cfg.font_size_ratio or state.advanced.corner_text_ratio

        # 角级默认样式（用于分隔符 & 单字段路径）
        default_font = state.advanced.global_font
        default_color = state.advanced.global_color

        if not segments:
            corner_node: dict[str, Any] = {
                "processor_name": "rich_text",
                "text": "",
                "color": default_color,
            }
        elif len(segments) == 1:
            seg = segments[0]
            corner_node = {
                "processor_name": "rich_text",
                "text": seg["text"],
                "color": seg["color"],
                "font_path": seg["font_path"],
            }
        else:
            # 多字段：multi_rich_text，分隔符使用「角级」样式
            text_segments: list[dict[str, Any]] = []
            for i, seg in enumerate(segments):
                if i > 0:
                    raw_sep = corner_cfg.separator.strip()
                    display_sep = "  " if not raw_sep else f" {corner_cfg.separator} "
                    text_segments.append({
                        "text": display_sep,
                        "color": default_color,
                        "font_path": default_font,
                    })
                text_segments.append(seg)

            corner_node = {
                "processor_name": "multi_rich_text",
                "text_segments": text_segments,
            }

        # Phase 28：传递比例，处理器在渲染时根据图片短边计算实际像素高度
        if height_ratio > 0:
            corner_node["height_ratio"] = height_ratio
        config[corner] = corner_node

    # Logo 配置
    logo = state.logo
    if logo.enabled != "disabled":
        logo_path = ""
        if logo.enabled == "custom" and logo.custom_path:
            logo_path = logo.custom_path
        else:
            # 自动匹配：使用 Jinja2 表达式，运行时由 auto_logo() 解析
            logo_path = "{{auto_logo()|replace('\\\\', '/')}}"

        if logo.position == "right":
            config["right_logo"] = logo_path
        elif logo.position == "center":
            config["center_logo"] = logo_path
        elif logo.position == "left":
            config["left_logo"] = logo_path

        # 分隔线颜色
        config["delimiter_color"] = logo.color

    # 自定义文本（已包含在四角配置里，这里保留向后兼容）
    if state.custom_text:
        config["custom_text"] = state.custom_text

    # Phase 28：固定水印条高度 + 中央 logo 高度（0 不写入 → 走旧自适应）
    if state.advanced.footer_height_px > 0:
        config["bottom_margin"] = state.advanced.footer_height_px
    if state.advanced.logo_height_px > 0:
        config["logo_height"] = state.advanced.logo_height_px

    return config


def _build_signature_config(state: AppState) -> dict[str, Any]:
    """Phase 18：从 AppState 构建 SignatureFilter 配置。

    返回空 dict 表示不应生成此 processor（未启用 / 无路径）。

    SignatureFilter 在【原图区域】内定位 — 区域由 ctx 中的
    top/bottom/left/right_margin 计算（由 WatermarkFilter / MarginFilter
    在前序节点写入）。本函数无需透传任何 margin 字段。
    """
    cfg = state.advanced
    if not cfg.signature_enabled:
        return {}
    if not cfg.signature_path:
        return {}

    return {
        "signature_enabled": True,
        "signature_path": cfg.signature_path,
        # 黑↔白笔画切换；彩色像素永远保留原色（详见 SignatureFilter）
        "signature_invert_mono": cfg.signature_invert_mono,
        "signature_enhancement": cfg.signature_enhancement,
        "signature_enhancement_strength": cfg.signature_enhancement_strength,
        "signature_anchor": cfg.signature_anchor,
        "signature_margin_x": cfg.signature_margin_x,
        "signature_margin_y": cfg.signature_margin_y,
        # 尺寸 = 签名宽度占照片主体短边比例（0.01~1.0）
        "signature_size_ratio": cfg.signature_size_ratio,
    }
