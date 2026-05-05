"""模板构建器 — 将 user.json + config.ini 转换为 watermark processor JSON。"""

import json
import logging
from pathlib import Path

from jinja2 import Template

from core.config_loader import FONTS_DIR, get_custom_text, get_logo_path
from core.jinja2renders import auto_logo, vh, vw

logger = logging.getLogger(__name__)

FALLBACK_FONT = "NotoSansCJKsc-Regular.otf"


def _font(name: str) -> str:
    """验证字体存在性，回退到内置字体。"""
    if (FONTS_DIR / name).is_file():
        return name
    logger.warning(f"字体 '{name}' 不存在，回退到 '{FALLBACK_FONT}'")
    return FALLBACK_FONT


def _format_params() -> str:
    """拍摄参数 Jinja2 拼接公式。"""
    focal = "{{exif.FocalLengthIn35mmFormat|replace(' ', '')|default('-')}}"
    aperture = "{{exif.ApertureValue or exif.FNumber|default('-')}}"
    shutter = "{{exif.ShutterSpeed or exif.ShutterSpeedValue|default('-')}}"
    iso = "{{exif.ISO|default('0')}}"
    return f"{focal} f/{aperture} {shutter}s ISO{iso}"


def _format_date() -> str:
    """日期 Jinja2 公式（带 fallback 链）。"""
    return "{{(exif.DateTimeOriginal or exif.CreateDate or exif.DigitalCreationDate or exif.DateCreated or exif.DateTimeCreated or exif.DigitalCreationDateTime|default('0'))[:16]}}"


def build_watermark_processor(user_template: dict, config_ini) -> list:
    """
    根据 user.json 和 config.ini 构建 processor 配置列表（含 Jinja2 模板表达式）。
    返回可直接经 render_processors 渲染后传给 start_process 的列表。
    """
    layout = user_template.get("layout", {})
    logo_cfg = user_template.get("logo", {})
    bg = user_template.get("background", {})

    # 构建四角（必须确保 4 个 key 都存在，防止 WatermarkFilter 崩溃）
    corners: dict[str, dict] = {}
    for corner in ("left_top", "left_bottom", "right_top", "right_bottom"):
        cfg = layout.get(corner, {})
        # 兼容新版多字段和旧版单字段
        sources = cfg.get("sources", [cfg.get("source", "empty")])
        separator = cfg.get("separator", "")
        font = _font(cfg.get("font", FALLBACK_FONT))
        color = cfg.get("color", "#242424")
        corners[corner] = _build_corner_multi(corner, sources, separator, font, color, config_ini)

    # Logo
    right_logo = ""
    if logo_cfg.get("enabled", True):
        custom_logo = get_logo_path(config_ini)
        if custom_logo:
            right_logo = str(custom_logo).replace("\\", "/")
        else:
            # Jinja2 表达式，运行时由 auto_logo() 解析
            right_logo = "{{auto_logo()|replace('\\\\', '/')}}"

    watermark = {
        "processor_name": "watermark",
        "left_top": corners["left_top"],
        "left_bottom": corners["left_bottom"],
        "right_top": corners["right_top"],
        "right_bottom": corners["right_bottom"],
        "color": bg.get("color", "white"),
        "delimiter_color": logo_cfg.get("delimiter_color", "#D8D8D6"),
        "right_alignment": "left",
    }
    if right_logo:
        watermark["right_logo"] = right_logo

    return [watermark]


def _build_source_segment(source: str, font: str, color: str, config_ini, corner: str) -> dict | None:
    """构建单个 source 的 text segment。"""
    if source == "empty":
        return None

    if source == "exif:CameraModelName":
        text = "{{ exif.CameraModelName|default('-') | replace('_', '') }}"
        return {"text": text, "color": color, "font_path": font}

    if source == "exif:LensModel":
        text = "{{ exif.LensModel | default('-')}}"
        return {"text": text, "color": color, "font_path": font}

    if source == "exif:params":
        text = _format_params()
        return {"text": text, "color": color, "font_path": font}

    if source == "exif:DateTimeOriginal":
        text = _format_date()
        return {"text": text, "color": color, "font_path": font}

    if source == "exif:Make":
        text = "{{ exif.Make|default('-') }}"
        return {"text": text, "color": color, "font_path": font}

    if source == "exif:GPSInfo":
        text = "{{ exif.GPSLatitude|default('-') }}, {{ exif.GPSLongitude|default('-') }}"
        return {"text": text, "color": color, "font_path": font}

    if source == "author":
        name = config_ini.get("DEFAULT", "author_name", fallback="").strip()
        text = name if name else ""
        return {"text": text, "color": color, "font_path": font}

    if source == "custom":
        text = get_custom_text(config_ini, corner)
        return {"text": text, "color": color, "font_path": font}

    logger.warning(f"未知 source '{source}'，忽略")
    return None


def _build_corner_multi(corner: str, sources: list[str], separator: str, font: str, color: str, config_ini) -> dict:
    """根据 source 列表构建单个角的 processor 配置，支持多字段叠加。"""
    segments = []
    for src in sources:
        seg = _build_source_segment(src, font, color, config_ini, corner)
        if seg:
            segments.append(seg)

    if not segments:
        return {"processor_name": "rich_text", "text": "", "color": color}

    if len(segments) == 1:
        # 单字段：保持原来格式（兼容原有渲染逻辑）
        seg = segments[0]
        return {
            "processor_name": "rich_text",
            "text": seg["text"],
            "color": color,
            "font_path": font,
        }

    # 多字段：用 multi_rich_text，中间插入分隔符（自动包装空格）
    text_segments = []
    for i, seg in enumerate(segments):
        if i > 0:
            # 分隔符包装规则：空→两个空格；有内容→空格+内容+空格
            raw_sep = separator.strip()
            display_sep = "  " if not raw_sep else f" {separator} "
            text_segments.append({
                "text": display_sep,
                "color": color,
                "font_path": font,
            })
        text_segments.append(seg)

    return {
        "processor_name": "multi_rich_text",
        "text_segments": text_segments,
    }


def _render_value(value, context, template_globals):
    """递归渲染值中的 Jinja2 模板表达式。"""
    if isinstance(value, str):
        template = Template(value)
        for k, v in template_globals.items():
            template.globals[k] = v
        return template.render(**context)
    elif isinstance(value, list):
        return [_render_value(item, context, template_globals) for item in value]
    elif isinstance(value, dict):
        return {k: _render_value(v, context, template_globals) for k, v in value.items()}
    return value


def render_processors(processors: list, exif: dict, file_path: str) -> list:
    """
    将 processor 列表中的 Jinja2 模板表达式递归渲染为实际值。
    调用 start_process 之前必须先执行此函数。
    """
    template_globals = {
        "vh": vh,
        "vw": vw,
        "auto_logo": auto_logo,
    }
    context = {
        "exif": exif,
        "file_path": file_path,
        "file_dir": str(Path(file_path).parent),
    }
    return _render_value(processors, context, template_globals)
