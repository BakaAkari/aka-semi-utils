"""字体管理器 — 扫描 fonts 目录、生成预览、加载字体（带回退）。"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# 使用基于项目根目录的绝对路径
_PROJECT_ROOT = Path(__file__).parent.parent
FONTS_DIR = _PROJECT_ROOT / "config" / "fonts"
PREVIEW_TEXT = "字体预览"
PREVIEW_SIZE = (80, 30)
FALLBACK_FONT = "NotoSansCJKsc-Regular.otf"


def list_fonts() -> list[str]:
    """扫描 fonts 目录，返回所有 .ttf/.otf 文件名（排序）。"""
    if not FONTS_DIR.exists():
        return [FALLBACK_FONT]
    fonts = sorted(
        f.name for f in FONTS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in (".ttf", ".otf")
    )
    return fonts if fonts else [FALLBACK_FONT]


def font_exists(name: str) -> bool:
    return (FONTS_DIR / name).is_file()


def refresh_fonts() -> list[str]:
    """重新扫描 fonts 目录，返回更新后的文件名列表。"""
    return list_fonts()


def import_font(source_path: Path) -> str | None:
    """将外部字体文件复制到 config/fonts/。

    Args:
        source_path: 源字体文件路径（.ttf / .otf）。

    Returns:
        复制后的文件名；若校验失败或已存在则返回 ``None``。
    """
    if not source_path.is_file():
        return None
    suffix = source_path.suffix.lower()
    if suffix not in (".ttf", ".otf"):
        return None

    target = FONTS_DIR / source_path.name
    if target.exists():
        return None

    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source_path.read_bytes())
    return target.name


def resolve_font(name: str) -> Path:
    """
    解析字体路径。若指定字体不存在则回退到内置字体。
    """
    path = FONTS_DIR / name
    if path.is_file():
        return path
    fallback = FONTS_DIR / FALLBACK_FONT
    if fallback.is_file():
        logger.warning(f"字体 '{name}' 不存在，回退到 '{FALLBACK_FONT}'")
        return fallback
    raise FileNotFoundError(f"字体缺失: {name} 且回退字体 {FALLBACK_FONT} 也不存在")


def generate_preview(name: str, text: str = "") -> Image.Image:
    """
    为指定字体生成 80x30 预览图。
    返回 Pillow Image 对象（RGBA）。
    """
    display_text = text.strip() if text else PREVIEW_TEXT
    try:
        font_path = resolve_font(name)
        font = ImageFont.truetype(str(font_path), 14)
    except Exception as e:
        logger.warning(f"预览生成失败 ({name}): {e}")
        # 回退：用默认字体
        font = ImageFont.load_default()

    img = Image.new("RGBA", PREVIEW_SIZE, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), display_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(0, (PREVIEW_SIZE[0] - text_w) // 2)
    y = max(0, (PREVIEW_SIZE[1] - text_h) // 2 - bbox[1])
    draw.text((x, y), display_text, fill="black", font=font)
    return img
