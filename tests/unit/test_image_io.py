"""测试 [`core.image_io`](core/image_io.py) — 图像 I/O 安全层。

主要保证：
- ``load_image_safely`` 返回的 Image 已脱离原文件句柄（fp 为 None）；
- 像素数据与原图一致；
- ``transpose_exif=True`` 不影响无 EXIF 图像；
- ``load_logo`` 正确转换 mode 并关闭 fp；
- 不存在的路径抛 FileNotFoundError。
"""

from __future__ import annotations

import pytest
from PIL import Image

from core.image_io import load_image_safely, load_logo, open_image


def _make_jpeg(tmp_path, size=(8, 6), color=(255, 0, 0)):
    p = tmp_path / "sample.jpg"
    img = Image.new("RGB", size, color)
    img.save(p, format="JPEG", quality=95)
    return p


def _make_png_rgba(tmp_path):
    p = tmp_path / "logo.png"
    img = Image.new("RGBA", (4, 4), (0, 255, 0, 128))
    img.save(p, format="PNG")
    return p


def _make_png_rgb(tmp_path):
    p = tmp_path / "logo_rgb.png"
    img = Image.new("RGB", (4, 4), (0, 0, 255))
    img.save(p, format="PNG")
    return p


# ============================================================
# load_image_safely
# ============================================================


def test_load_image_safely_returns_independent_image(tmp_path):
    """加载后的 Image 不持有文件 fp（fp 为 None）。"""
    p = _make_jpeg(tmp_path)
    img = load_image_safely(p)

    # PIL Image.copy() 后的对象 fp 为 None（已脱离文件）
    assert getattr(img, "fp", None) is None
    assert img.size == (8, 6)
    assert img.mode == "RGB"


def test_load_image_safely_pixel_equivalence(tmp_path):
    """脱离 fp 后像素数据保持一致。"""
    p = _make_jpeg(tmp_path, color=(123, 200, 50))
    img = load_image_safely(p)
    # 中心像素近似（JPEG 有损但 8x6 全色块基本无损）
    px = img.getpixel((4, 3))
    # 容许 JPEG 量化偏差
    assert abs(px[0] - 123) < 5
    assert abs(px[1] - 200) < 5
    assert abs(px[2] - 50) < 5


def test_load_image_safely_accepts_str_and_path(tmp_path):
    p = _make_jpeg(tmp_path)
    img1 = load_image_safely(str(p))
    img2 = load_image_safely(p)
    assert img1.size == img2.size


def test_load_image_safely_with_transpose_no_exif(tmp_path):
    """transpose_exif=True 在无 EXIF 时应当无副作用。"""
    p = _make_jpeg(tmp_path, size=(10, 6))
    img = load_image_safely(p, transpose_exif=True)
    assert img.size == (10, 6)


def test_load_image_safely_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_image_safely(tmp_path / "nonexistent.jpg")


def test_load_image_safely_releases_fd_in_loop(tmp_path):
    """关键验证：循环加载 100 张图不应留下打开 fd。

    通过反复加载并丢弃引用，确保不抛 'Too many open files'。
    """
    p = _make_jpeg(tmp_path)
    for _ in range(100):
        img = load_image_safely(p)
        assert img.size == (8, 6)
        del img


# ============================================================
# open_image
# ============================================================


def test_open_image_works_with_context_manager(tmp_path):
    p = _make_jpeg(tmp_path)
    with open_image(p) as img:
        assert img.size == (8, 6)
        # 在 with 内 fp 应非空
        assert getattr(img, "fp", None) is not None


# ============================================================
# load_logo
# ============================================================


def test_load_logo_default_rgba(tmp_path):
    """默认转 RGBA，原图 RGB 应被扩展为 RGBA。"""
    p = _make_png_rgb(tmp_path)
    logo = load_logo(p)
    assert logo.mode == "RGBA"
    assert getattr(logo, "fp", None) is None


def test_load_logo_keeps_rgba(tmp_path):
    p = _make_png_rgba(tmp_path)
    logo = load_logo(p)
    assert logo.mode == "RGBA"
    # 中心像素仍为 (0,255,0,128)
    assert logo.getpixel((2, 2)) == (0, 255, 0, 128)


def test_load_logo_custom_mode(tmp_path):
    p = _make_png_rgba(tmp_path)
    logo = load_logo(p, mode="RGB")
    assert logo.mode == "RGB"


def test_load_logo_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_logo(tmp_path / "nope.png")


# ============================================================
# 像素一致性回归 — 确保 image_io 与裸 Image.open 等价
# ============================================================


def test_load_image_safely_matches_naked_open(tmp_path):
    """``load_image_safely`` 与 ``Image.open(...).load()`` 像素 100% 一致。"""
    p = _make_jpeg(tmp_path, color=(80, 160, 240))

    safe = load_image_safely(p)
    with Image.open(p) as raw:
        raw.load()
        raw_bytes = raw.tobytes()

    assert safe.tobytes() == raw_bytes
