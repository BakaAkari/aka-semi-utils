"""V3 Region-Based PIL Renderer — 后端图像渲染器。

此模块只负责按 LayoutResult 绘制 / 粘贴，不做任何位置计算。
所有坐标、尺寸均来自 V3 layout engine 输出的 LayoutResult。

职责边界：
  - 布局引擎 (shared.v3_layout.layout_engine): 计算每个元素在画布上的绝对位置
  - 本渲染器: 把内容（文本 / Logo / 签名）按指定位置粘贴到画布上
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.config_loader import FONTS_DIR, LOGOS_DIR
from core.image_io import load_logo
from core.logger import logger
from shared.v3_layout.layout_engine import (
    ComputedElement,
    LayoutResult,
    LogoContent,
    SignatureContent,
    TextContent,
)

# ── 颜色解析 ──────────────────────────────────────────────────────────


def _parse_color(color_str: str) -> tuple[int, int, int, int]:
    """将颜色字符串解析为 RGBA 元组。

    支持格式:
      - #RRGGBB
      - #RRGGBBAA
      - 常见 CSS 颜色名（白/黑等通过 Pillow 解析）
    """
    color_str = color_str.strip().lstrip("#")
    if len(color_str) == 6:
        return (
            int(color_str[0:2], 16),
            int(color_str[2:4], 16),
            int(color_str[4:6], 16),
            255,
        )
    if len(color_str) == 8:
        return (
            int(color_str[0:2], 16),
            int(color_str[2:4], 16),
            int(color_str[4:6], 16),
            int(color_str[6:8], 16),
        )
    # 回退: 尝试 Pillow ImageColor
    try:
        from PIL import ImageColor

        rgba = ImageColor.getcolor(f"#{color_str}" if color_str else "white", "RGBA")
        if isinstance(rgba, int):
            return (rgba, rgba, rgba, 255)
        return rgba  # type: ignore[return-value]
    except Exception:
        return (255, 255, 255, 255)


# ── 文本解析（chips → 实际字符串）─────────────────────────────────────


def _resolve_field_value(
    field_id: str, field_values: dict[str, str], custom_text: str
) -> str:
    """将 field_id 解析为实际文本值。"""
    if field_id == "custom_text":
        return custom_text or ""
    if field_id == "empty":
        return ""
    return field_values.get(field_id, "")


def _build_text(
    content: TextContent, field_values: dict[str, str], custom_text: str
) -> str:
    """将 TextContent 的 chips 拼接为实际文本字符串。"""
    texts: list[str] = []
    for chip in content.chips:
        if chip.field_id == "empty":
            continue
        # 优先使用 chip 级别的 custom_text（前端 v3Types 支持）
        chip_custom = getattr(chip, "custom_text", "") or ""
        if chip.field_id == "custom_text" and chip_custom:
            texts.append(chip_custom)
        else:
            texts.append(_resolve_field_value(chip.field_id, field_values, custom_text))
    return content.separator.join(texts)


# ── 字体加载 ──────────────────────────────────────────────────────────


def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """加载指定字体；失败时回退到系统默认字体。"""
    path = Path(font_path)
    if not path.is_absolute():
        path = FONTS_DIR / font_path

    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        for fallback in (
            FONTS_DIR / "AlibabaPuHuiTi-2-45-Light.otf",
            "arial.ttf",
            "Arial.ttf",
            "DejaVuSans.ttf",
        ):
            try:
                return ImageFont.truetype(str(fallback), size)
            except OSError:
                continue
        return ImageFont.load_default()


# ── Anchor → PIL paste 左上角坐标 ─────────────────────────────────────


def _anchor_to_paste_offset(
    anchor: str, element_w: int, element_h: int
) -> tuple[int, int]:
    """将 LayoutResult 中的 anchor 点转换为 PIL paste 所需的左上角偏移量。

    LayoutResult 中 ComputedElement.rect.(x, y) 是 anchor 点的绝对坐标。
    本函数返回从 anchor 点到元素左上角的 (dx, dy) 偏移。
    """
    dx = 0
    dy = 0

    if "center" in anchor:
        dx = -element_w // 2
    elif "right" in anchor:
        dx = -element_w

    if "middle" in anchor:
        dy = -element_h // 2
    elif "bottom" in anchor:
        dy = -element_h

    return dx, dy


# ── 元素渲染 ──────────────────────────────────────────────────────────


def _render_text_element(
    el: ComputedElement,
    field_values: dict[str, str],
    custom_text: str,
) -> Image.Image:
    """将文本元素渲染为透明背景的 PIL Image。"""
    content = el.content
    if not isinstance(content, TextContent):
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    text = _build_text(content, field_values, custom_text)
    if not text:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    style = el.style
    font_size = style.font_size or 16
    font = _load_font(style.font_family, font_size)
    color = _parse_color(style.color)

    # 测量文本尺寸（getbbox 返回 (left, top, right, bottom)）
    bbox = font.getbbox(text)
    if bbox:
        text_w = max(1, int(bbox[2] - bbox[0]))
        text_h = max(1, int(bbox[3] - bbox[1]))
        ascent_offset = int(bbox[1])  # 通常为负值，表示基线以上高度
    else:
        text_w = max(1, font_size * len(text))
        text_h = font_size
        ascent_offset = 0

    img = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # draw.text 的坐标是文本左上角；getbbox 的 top 可能为负（ascent），
    # 因此需要向上偏移以正确对齐基线
    draw.text((0, -ascent_offset), text, font=font, fill=color)

    return img


def _resolve_auto_logo_path(
    content: LogoContent, field_values: dict[str, str]
) -> str | None:
    """解析 auto logo 路径。"""
    if content.path:
        return content.path

    # auto 模式：根据 Make 字段推断品牌 logo
    make = field_values.get("make", "")
    if not make:
        return None

    # 复用 jinja2renders.auto_logo 的匹配逻辑（但不需要 Jinja context）
    brand = make.lower()
    tokens = [t for t in brand.replace("-", " ").split() if len(t) > 2]

    def _matches_stem(stem: str) -> bool:
        stem_lower = stem.lower()
        return any(token in stem_lower for token in tokens)

    def _is_valid_logo(f: Path) -> bool:
        if f.name.startswith(".") or f.name.startswith("._"):
            return False
        return f.suffix.lower() in {".png", ".jpg", ".jpeg"}

    # 1. 优先匹配用户自定义 Logo
    custom_dir = LOGOS_DIR / "custom"
    if custom_dir.exists():
        for f in sorted(custom_dir.iterdir(), key=lambda x: x.name.lower()):
            if _is_valid_logo(f) and _matches_stem(f.stem):
                return str(f.absolute())

    # 2. 回退到内置默认 Logo
    for f in sorted(LOGOS_DIR.iterdir(), key=lambda x: x.name.lower()):
        if f.is_file() and _is_valid_logo(f) and _matches_stem(f.stem):
            return str(f.absolute())

    return None


def _render_logo_element(
    el: ComputedElement,
    field_values: dict[str, str],
) -> Image.Image | None:
    """加载并缩放 Logo 元素。"""
    content = el.content
    if not isinstance(content, LogoContent):
        return None

    logo_path = _resolve_auto_logo_path(content, field_values)
    if not logo_path:
        # 无可用 logo，返回透明占位
        return Image.new("RGBA", (max(1, el.rect.w), max(1, el.rect.h)), (0, 0, 0, 0))

    try:
        logo = load_logo(logo_path)
    except (FileNotFoundError, OSError) as exc:
        logger.warning("[v3_renderer] Logo 加载失败: %s (%s)", logo_path, exc)
        return None

    target_size = (max(1, el.rect.w), max(1, el.rect.h))
    if logo.size != target_size:
        logo = logo.resize(target_size, Image.Resampling.LANCZOS)

    # 若 LogoContent 指定了着色颜色，应用颜色叠加（仅当 logo 为灰度/单色时）
    # 目前保持原样，与 V2 行为一致
    return logo


def _render_signature_element(el: ComputedElement) -> Image.Image | None:
    """加载并处理签名元素。"""
    content = el.content
    if not isinstance(content, SignatureContent):
        return None

    if not content.path:
        return None

    try:
        sig = load_logo(content.path)
    except (FileNotFoundError, OSError) as exc:
        logger.warning("[v3_renderer] 签名加载失败: %s (%s)", content.path, exc)
        return None

    target_size = (max(1, el.rect.w), max(1, el.rect.h))
    if sig.size != target_size:
        sig = sig.resize(target_size, Image.Resampling.LANCZOS)

    # invert_mono: 黑白反转（仅处理 RGB 通道，保留 Alpha）
    if content.invert_mono and sig.mode == "RGBA":
        r, g, b, a = sig.split()
        rgb = Image.merge("RGB", (r, g, b))
        inverted = Image.eval(rgb, lambda x: 255 - x)
        r2, g2, b2 = inverted.split()
        sig = Image.merge("RGBA", (r2, g2, b2, a))

    return sig


# ── 主渲染入口 ────────────────────────────────────────────────────────


def render_pil(
    layout: LayoutResult,
    image: Image.Image,
    *,
    bg_color: str = "#FFFFFF",
    field_values: dict[str, str] | None = None,
    custom_text: str = "",
) -> Image.Image:
    """V3 主渲染函数 — 按 LayoutResult 将水印元素绘制到画布上。

    Args:
        layout: V3 布局引擎输出的 LayoutResult。
        image: 原始照片（将被粘贴到 layout.image_rect 指定位置）。
        bg_color: 画布背景色（CSS 颜色格式，如 "#FFFFFF"）。
        field_values: 字段值映射（field_id → 实际文本），用于解析 chips。
        custom_text: 用户自定义文本（当 chip 的 field_id 为 "custom_text" 时使用）。

    Returns:
        合成后的 PIL Image（RGBA 模式）。
    """
    # 1. 创建画布
    canvas = Image.new(
        "RGBA", (layout.canvas.w, layout.canvas.h), _parse_color(bg_color)
    )

    # 2. 粘贴照片主体
    img = image.convert("RGBA") if image.mode != "RGBA" else image.copy()
    canvas.paste(img, (layout.image_rect.x, layout.image_rect.y))

    # 3. 按 LayoutResult 顺序绘制所有水印元素
    field_values = field_values or {}
    for el in layout.elements:
        if el.type == "text":
            element_img = _render_text_element(el, field_values, custom_text)
        elif el.type == "logo":
            element_img = _render_logo_element(el, field_values)
        elif el.type == "signature":
            element_img = _render_signature_element(el)
        else:
            continue

        if element_img is None:
            continue

        # anchor 点 → PIL paste 左上角坐标
        dx, dy = _anchor_to_paste_offset(el.anchor, element_img.width, element_img.height)
        paste_x = el.rect.x + dx
        paste_y = el.rect.y + dy

        canvas.paste(element_img, (paste_x, paste_y), mask=element_img)

    return canvas
