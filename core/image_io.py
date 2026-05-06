"""图像 I/O 安全层 — 统一管理 PIL Image 资源生命周期。

PIL ``Image.open()`` 是惰性的：返回的对象内部仍持有文件句柄（fp），
只有在调用 ``load()`` 或访问像素后，句柄才可关闭，但 PIL 默认不会
主动关闭原 fp（即使 GC 也得等到对象析构）。在批处理（成百上千张图）
或 ``ProcessPoolExecutor`` 跨进程传递 Image 对象时，悬挂的 fd 会引发：

- macOS / Linux 的 *Too many open files* 错误；
- pickle 失败（fp 无法序列化）；
- HEIC 等格式的解码后内存与文件双倍占用。

本模块提供两条主路径：

1. :func:`load_image_safely`  — 立即 ``load()`` 并 ``copy()``，返回完全
   脱离 fp 的纯内存 Image。**适用于** 进入 pipeline 之前的图像加载、
   pickle 跨进程发送、长生命周期持有。
2. :func:`open_image`         — 返回标准 ``Image.open()`` 的句柄，**调用方负责**
   用 ``with`` 包裹。**适用于** 一次性快速读取（如缩略图扫描）。

设计原则：
- **零行为变更**：返回的 Image 对象与原 ``Image.open()`` 在 mode/size 上完全等价；
- **idempotent**：对已 load 的图像再次调用 ``load_image_safely`` 不报错；
- **可选 EXIF 转向**：常见 pipeline 入口需要 ``ImageOps.exif_transpose``，
  通过 ``transpose_exif=True`` 一行触发。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

PathLike = str | Path


def load_image_safely(
    path: PathLike,
    *,
    transpose_exif: bool = False,
) -> Image.Image:
    """安全加载图像 — 立即关闭文件句柄并返回独立的内存 Image。

    流程::

        with Image.open(path) as src:
            src.load()
            img = src.copy()

    然后（可选）施加 EXIF 方向旋转。

    Args:
        path: 图像文件路径（str 或 Path）。
        transpose_exif: 是否根据 EXIF Orientation 标签自动旋转图像。
            管线入口应当传 ``True`` 以保持 :class:`processor.core.PipelineContext`
            旧行为；缩略图等场景可保留 ``False``。

    Returns:
        已脱离文件句柄的 PIL Image。可安全 pickle / 长期持有。

    Raises:
        FileNotFoundError: 路径不存在。
        PIL.UnidentifiedImageError: 文件不是有效图像。
    """
    p = Path(path)
    with Image.open(p) as src:
        src.load()
        img = src.copy()

    if transpose_exif:
        # exif_transpose 会返回新对象（可能是原对象，若无需旋转），
        # 但已脱离 fp，因此安全。
        img = ImageOps.exif_transpose(img)

    return img


def open_image(path: PathLike) -> Image.Image:
    """返回 ``Image.open()`` 的句柄 — 调用方**必须**用 ``with`` 包裹。

    适用于无需跨进程传递、希望惰性解码的场景（如缩略图）。

    Examples::

        with open_image(p) as img:
            img.thumbnail((200, 200))
            ...
    """
    return Image.open(Path(path))


def load_logo(path: PathLike, *, mode: str = "RGBA") -> Image.Image:
    """加载 logo 图像并立即转换到指定 mode（默认 RGBA），关闭原 fp。

    封装常见的 ``Image.open(p).convert('RGBA')`` 反模式（会泄漏 fp）。

    Args:
        path: logo 路径。
        mode: 目标 PIL mode，默认 RGBA。

    Raises:
        FileNotFoundError: 路径不存在。
    """
    p = Path(path)
    with Image.open(p) as src:
        src.load()
        return src.convert(mode)
