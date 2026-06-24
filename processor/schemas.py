"""处理器参数 schema — 用 dataclass 替代散落的 ``ctx.get("xxx")`` 字符串键。

设计目标：
- **类型安全**：每个 schema 字段都有明确类型，IDE 可补全。
- **可选采纳**：新处理器可用 ``Schema.from_ctx(ctx)`` 把字符串键收拢成对象；
  老处理器**无需修改**，仍可继续用 ``ctx.get(...)``。
- **零运行时开销**：dataclass 仅作为 view，无额外 I/O。

约定：
- 每个 schema 都暴露 ``from_ctx(cls, ctx)`` 类方法
  从 :class:`processor.core.PipelineContext` 读取字段，缺失走默认值。
- 数值字段用 ``ctx.getint`` 或 ``int(ctx.get(..., default))``；
  颜色用 ``ctx.getcolor``；枚举用 ``ctx.getenum``。

后续可逐步把各处理器的 ``process()`` 改造为
``params = XxxParams.from_ctx(ctx)`` 然后引用 ``params.xxx``，
不再到处出现魔法字符串。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from processor.types import Alignment

if TYPE_CHECKING:
    from processor.core import PipelineContext


# ---------------------------------------------------------------- BlurParams
@dataclass(frozen=True)
class BlurParams:
    """``blur`` 处理器的参数。"""

    radius: int = 5

    @classmethod
    def from_ctx(cls, ctx: PipelineContext) -> BlurParams:
        return cls(radius=ctx.getint("blur_radius", 5))


# -------------------------------------------------------------- ResizeParams
@dataclass(frozen=True)
class ResizeParams:
    """``resize`` 处理器的参数（width / height / scale 三选一）。"""

    width: int | None = None
    height: int | None = None
    scale: float | None = None

    @classmethod
    def from_ctx(cls, ctx: PipelineContext) -> ResizeParams:
        w = ctx.get("width")
        h = ctx.get("height")
        s = ctx.get("scale")
        return cls(
            width=int(w) if w is not None else None,
            height=int(h) if h is not None else None,
            scale=float(s) if s is not None else None,
        )


# -------------------------------------------------------------- MarginParams
@dataclass(frozen=True)
class MarginParams:
    """``margin`` 处理器的参数。"""

    left_margin: int = 0
    right_margin: int = 0
    top_margin: int = 0
    bottom_margin: int = 0
    margin_color: Any = "white"

    @classmethod
    def from_ctx(cls, ctx: PipelineContext) -> MarginParams:
        return cls(
            left_margin=ctx.getint("left_margin", 0),
            right_margin=ctx.getint("right_margin", 0),
            top_margin=ctx.getint("top_margin", 0),
            bottom_margin=ctx.getint("bottom_margin", 0),
            margin_color=ctx.get("margin_color", "white"),
        )


# ------------------------------------------------------------- ShadowParams
@dataclass(frozen=True)
class ShadowParams:
    """``shadow`` 处理器的参数。"""

    shadow_color: tuple = (0, 0, 0, 180)
    shadow_radius: int = 30
    falloff: float = 1.5

    @classmethod
    def from_ctx(cls, ctx: PipelineContext) -> ShadowParams:
        return cls(
            shadow_color=ctx.getcolor("shadow_color", (0, 0, 0, 180)),
            shadow_radius=ctx.getint("shadow_radius", 30),
            falloff=1.5,  # 当前未从 ctx 读取，保留硬编码默认
        )


# ----------------------------------------------------------- WatermarkParams
@dataclass(frozen=True)
class WatermarkParams:
    """``watermark`` 处理器的核心参数（不含每角文本/Logo 配置，那些是嵌套 dict）。"""

    color: Any = "white"
    delimiter_color: Any = "black"
    delimiter_width: int = 0
    left_margin: int = 0
    right_margin: int = 0
    top_margin: int = 0
    bottom_margin: int = 0
    middle_spacing: int = 0
    right_alignment: Alignment = Alignment.RIGHT

    @classmethod
    def from_ctx(cls, ctx: PipelineContext, img_width: int, img_height: int) -> WatermarkParams:
        bottom_margin = ctx.getint("bottom_margin", 120)
        return cls(
            color=ctx.get("color", "white"),
            delimiter_color=ctx.get("delimiter_color", "black"),
            delimiter_width=ctx.getint("delimiter_width", int(img_width * 0.003)),
            left_margin=ctx.getint("left_margin", 0),
            right_margin=ctx.getint("right_margin", 0),
            top_margin=ctx.getint("top_margin", 0),
            bottom_margin=bottom_margin,
            middle_spacing=ctx.getint("middle_spacing", int(bottom_margin * 0.05)),
            right_alignment=ctx.getenum("right_alignment", Alignment.RIGHT, Alignment),
        )


__all__ = [
    "BlurParams",
    "MarginParams",
    "ResizeParams",
    "ShadowParams",
    "WatermarkParams",
]
