"""模板组装器 — GUI 状态与 Processor JSON 双向转换。"""

from typing import List, Dict, Any
from pathlib import Path
import json
import logging

from .models import AppState, CornerConfig, LogoConfig, AdvancedConfig

logger = logging.getLogger(__name__)

# 处理器映射字典 — 新增处理器只需加一行
PROCESSOR_MAP: Dict[str, Dict[str, Any]] = {
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
        "processor_name": "WatermarkFilter",
    },
}


def state_to_processors(state: AppState) -> List[Dict[str, Any]]:
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


def processors_to_state(processors: List[Dict[str, Any]], state: AppState):
    """Processor JSON 列表 → AppState（反向转换）。"""
    for processor in processors:
        name = processor.get("processor_name", "")
        
        # 查找对应的映射
        for key, mapping in PROCESSOR_MAP.items():
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
    
    # 发射信号通知更新
    state.watermark_changed.emit()
    state.advanced_changed.emit()


def _build_watermark_config(state: AppState) -> Dict[str, Any]:
    """从 AppState 构建水印处理器配置。"""
    config = {}
    
    # 四角配置
    for corner, attr in [
        ("left_top", "left_top"),
        ("left_bottom", "left_bottom"),
        ("right_top", "right_top"),
        ("right_bottom", "right_bottom"),
    ]:
        corner_cfg: CornerConfig = getattr(state, attr)
        if corner_cfg.fields:
            config[f"{corner}_field"] = corner_cfg.fields
            config[f"{corner}_separator"] = corner_cfg.separator
            config[f"{corner}_font"] = corner_cfg.font
            config[f"{corner}_color"] = corner_cfg.color
    
    # Logo 配置
    logo = state.logo
    if logo.enabled != "disabled":
        config["logo_enable"] = True
        config["logo_position"] = logo.position
        config["logo_color"] = logo.color
        if logo.enabled == "custom" and logo.custom_path:
            config["logo_custom_path"] = logo.custom_path
    
    # 自定义文本
    if state.custom_text:
        config["custom_text"] = state.custom_text
    
    return config


def _apply_watermark_config(processor: Dict[str, Any], state: AppState):
    """从处理器配置还原到 AppState。"""
    for corner, attr in [
        ("left_top", "left_top"),
        ("left_bottom", "left_bottom"),
        ("right_top", "right_top"),
        ("right_bottom", "right_bottom"),
    ]:
        if f"{corner}_field" in processor:
            corner_cfg = getattr(state, attr)
            corner_cfg.fields = processor.get(f"{corner}_field", [])
            corner_cfg.separator = processor.get(f"{corner}_separator", " · ")
            corner_cfg.font = processor.get(f"{corner}_font", "NotoSansCJKsc-Regular.otf")
            corner_cfg.color = processor.get(f"{corner}_color", "#FFFFFF")
    
    # Logo
    if "logo_enable" in processor:
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


def load_template(template_path: Path) -> List[Dict[str, Any]]:
    """从文件加载模板。"""
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_template(processors: List[Dict[str, Any]], template_path: Path):
    """保存模板到文件。"""
    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(processors, f, indent=2, ensure_ascii=False)
