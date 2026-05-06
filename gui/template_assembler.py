"""模板组装器 — GUI 状态与 Processor JSON 双向转换。

Phase 6.4 重构：字段映射全部走 :mod:`gui.field_registry`，
不再在本文件硬编码 ``_FIELD_TEMPLATES`` / ``_REVERSE_FIELD_MAP``。
"""

import contextlib
import json
import logging
from pathlib import Path
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
}


def state_to_processors(state: AppState) -> list[dict[str, Any]]:
    """AppState → Processor JSON 列表（正向转换）。"""
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
    
    return processors


def processors_to_state(processors: list[dict[str, Any]], state: AppState):
    """Processor JSON 列表 → AppState（反向转换）。

    Phase 10.1 (P2)：信号契约修正 —— 该函数会改写 watermark / advanced **以及**通过
    上游 ``set_template`` 间接影响的"当前模板"语义。即便调用方再调一次 ``set_template``
    也不影响幂等，但本函数缺失 ``template_changed.emit`` 会让"只调 processors_to_state
    不调 set_template"的隐藏路径破坏订阅者刷新；现统一发齐三个信号，杜绝失同步。
    """
    for processor in processors:
        name = processor.get("processor_name", "")

        # 查找对应的映射
        for _key, mapping in PROCESSOR_MAP.items():
            if mapping["processor_name"] == name:
                target = mapping["target"]
                fields = mapping["fields"]

                if target == "advanced":
                    for field in fields:
                        if field in processor:
                            setattr(state.advanced, field, processor[field])

                elif target == "watermark":
                    _apply_watermark_config(processor, state)

                break

    # 发射信号通知更新（Phase 10.1：补 template_changed 让信号契约自洽）
    state.watermark_changed.emit()
    state.advanced_changed.emit()
    state.template_changed.emit(state.current_template)


def _resolve_chip_style(
    chip: FieldChip, corner: CornerConfig, advanced: AdvancedConfig
) -> tuple[str, str]:
    """按继承链 chip → corner → global 解析 (font, color)。"""
    font = chip.font or corner.font or advanced.global_font
    color = chip.color or corner.color or advanced.global_color
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

        # Phase 11：固定字号 — 把每个 segment 显式带上 height（像素）
        # 0 = 沿用旧自适应（处理器内部仍按 bottom_margin*0.3 推导）。
        fixed_text_h = state.advanced.corner_text_height_px

        # 角级默认样式（用于分隔符 & 单字段路径）
        default_font = corner_cfg.font or state.advanced.global_font
        default_color = corner_cfg.color or state.advanced.global_color

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

        # Phase 11：显式锁高度，处理器侧不再用 bottom_margin*0.3 覆盖
        if fixed_text_h > 0:
            corner_node["height"] = fixed_text_h
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

    # Phase 11：固定水印条高度 + 中央 logo 高度（0 不写入 → 走旧自适应）
    if state.advanced.footer_height_px > 0:
        config["bottom_margin"] = state.advanced.footer_height_px
    if state.advanced.logo_height_px > 0:
        config["center_logo_height"] = state.advanced.logo_height_px

    return config


def _is_separator_text(t: str) -> bool:
    """识别 multi_rich_text 中由 :func:`_build_watermark_config` 生成的分隔符片段。"""
    if not t:
        return False
    stripped = t.strip()
    if stripped == "" or stripped == "·":
        return True
    # 形如 ' · '（前后带空格）
    return bool(t.startswith(" ") and t.endswith(" ") and len(stripped) <= 3)


def _segment_to_chip(seg: dict[str, Any], state: AppState) -> FieldChip | None:
    """把模板 segment 还原为 :class:`FieldChip`（含字体色继承推断）。"""
    registry = get_default_registry()
    text = seg.get("text", "")
    if not text:
        return None
    fdef = registry.get_by_jinja(text)
    if fdef is None:
        # 视为自定义文本
        return FieldChip(
            field_id="custom_text",
            custom_text=text,
            font=seg.get("font_path", ""),
            color=seg.get("color", ""),
        )
    return FieldChip(
        field_id=fdef.field_id,
        font=seg.get("font_path", ""),
        color=seg.get("color", ""),
    )


def _apply_watermark_config(processor: dict[str, Any], state: AppState):
    """从处理器配置还原到 AppState（读取嵌套格式）。

    Phase 6.4：使用 :class:`FieldRegistry` 反查；输出同时填充 ``chips`` 与
    向后兼容的 ``fields`` 中文标签列表。
    """
    registry = get_default_registry()

    for corner, attr in [
        ("left_top", "left_top"),
        ("left_bottom", "left_bottom"),
        ("right_top", "right_top"),
        ("right_bottom", "right_bottom"),
    ]:
        if corner not in processor:
            continue

        corner_cfg: CornerConfig = getattr(state, attr)
        corner_data = processor.get(corner, {})
        pn = corner_data.get("processor_name", "")

        chips: list[FieldChip] = []
        if pn == "rich_text":
            text = corner_data.get("text", "")
            if text:
                fdef = registry.get_by_jinja(text)
                if fdef is not None:
                    chips.append(FieldChip(
                        field_id=fdef.field_id,
                        font=corner_data.get("font_path", ""),
                        color=corner_data.get("color", ""),
                    ))
                else:
                    # 自定义文本
                    state.custom_text = text
                    chips.append(FieldChip(
                        field_id="custom_text",
                        custom_text=text,
                        font=corner_data.get("font_path", ""),
                        color=corner_data.get("color", ""),
                    ))
        elif pn == "multi_rich_text":
            for seg in corner_data.get("text_segments", []):
                t = seg.get("text", "")
                if _is_separator_text(t):
                    continue
                chip = _segment_to_chip(seg, state)
                if chip is not None:
                    chips.append(chip)

        # 写回（同步更新中文 fields 兼容字段）
        corner_cfg.chips = chips
        corner_cfg.fields = []
        for chip in chips:
            fdef = registry.get(chip.field_id)
            corner_cfg.fields.append(fdef.label_zh if fdef else "")

        # 旧扁平格式向后兼容（v1 之前的模板）
        if not chips and f"{corner}_field" in processor:
            corner_cfg.fields = processor.get(f"{corner}_field", [])
            corner_cfg.separator = processor.get(f"{corner}_separator", " · ")
            corner_cfg.font = processor.get(f"{corner}_font", "")
            corner_cfg.color = processor.get(f"{corner}_color", "")
            # 同步生成 chips
            corner_cfg.chips = [
                FieldChip(
                    field_id=(registry.get_by_label(lbl) or registry.get_by_label("空")).field_id
                ) for lbl in corner_cfg.fields
            ]
    
    # Logo — 从嵌套格式读取（right_logo / center_logo / left_logo）
    logo = state.logo
    if "right_logo" in processor or "center_logo" in processor or "left_logo" in processor:
        logo.enabled = "auto"
        if "right_logo" in processor:
            logo.position = "right"
        elif "center_logo" in processor:
            logo.position = "center"
        elif "left_logo" in processor:
            logo.position = "left"
        logo.color = processor.get("delimiter_color", "#FFFFFF")
        # 检查是否是自定义路径（非 Jinja2 表达式）
        for pos in ["right_logo", "center_logo", "left_logo"]:
            if pos in processor:
                val = processor[pos]
                if val and not val.startswith("{{"):
                    logo.enabled = "custom"
                    logo.custom_path = val
                break
    elif "logo_enable" in processor:
        # 旧格式向后兼容
        state.logo.enabled = "auto"
        state.logo.position = processor.get("logo_position", "right")
        state.logo.color = processor.get("logo_color", "#FFFFFF")
        if "logo_custom_path" in processor:
            state.logo.enabled = "custom"
            state.logo.custom_path = processor["logo_custom_path"]
    else:
        state.logo.enabled = "disabled"
    
    # 自定义文本
    state.custom_text = processor.get("custom_text", "")

    # Phase 11：从模板还原"固定像素尺寸"到 AdvancedConfig
    # 字段缺省时保持当前值（默认 0 即自适应）。
    adv = state.advanced
    if "bottom_margin" in processor:
        with contextlib.suppress(TypeError, ValueError):
            adv.footer_height_px = int(processor["bottom_margin"])
    if "center_logo_height" in processor:
        with contextlib.suppress(TypeError, ValueError):
            adv.logo_height_px = int(processor["center_logo_height"])
    # 角落 height 取所有非空 corner 的最大值（多角落不一致时统一向上对齐）
    corner_heights: list[int] = []
    for corner in ("left_top", "left_bottom", "right_top", "right_bottom"):
        cd = processor.get(corner)
        if isinstance(cd, dict) and "height" in cd:
            try:
                corner_heights.append(int(cd["height"]))
            except (TypeError, ValueError):
                continue
    if corner_heights:
        adv.corner_text_height_px = max(corner_heights)


TEMPLATE_VERSION = 1


def load_template(template_path: Path) -> list[dict[str, Any]]:
    """从文件加载模板（支持版本号校验）。"""
    with open(template_path, encoding="utf-8") as f:
        data = json.load(f)
    
    # 如果是带版本号的包装格式，解包
    if isinstance(data, dict) and "version" in data:
        if data.get("version") != TEMPLATE_VERSION:
            logger.warning(
                f"模板版本不匹配: 文件={data.get('version')}, "
                f"当前={TEMPLATE_VERSION}"
            )
        return data.get("processors", [])
    # 兼容旧格式（纯数组）
    if isinstance(data, list):
        return data
    return []


def save_template(processors: list[dict[str, Any]], template_path: Path):
    """保存模板到文件（带版本号）。"""
    data = {
        "version": TEMPLATE_VERSION,
        "processors": processors,
    }
    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
