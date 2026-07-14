"""V3 Region-Based Watermark Filter.

此处理器是 V3 架构的后端渲染层：
  - 输入：v3_config (dict) + 原图 PIL Image + EXIF
  - 行为：调用 shared.v3_layout.layout_engine.compute_layout() 获取 LayoutResult
  - 输出：按 LayoutResult 在画布上粘贴/合成所有水印元素

与 V2 WatermarkFilter 的核心区别：
  - 不内联计算坐标，全部委托给纯函数布局引擎
  - 按 LayoutResult 的顺序绘制元素，不做任何位置计算
"""

from __future__ import annotations

from jinja2 import Template
from PIL import Image

from core.jinja2renders import resolve_auto_logo
from processor.core import PipelineContext, register
from processor.filters import FilterProcessor
from processor.generators import RichTextGenerator, TextSegment
from shared.field_registry import get_default_registry
from shared.v3_layout.layout_engine import (
    ComputedElement,
    LogoContent,
    SignatureContent,
    TextContent,
    WatermarkConfig,
    compute_layout,
)

# ── 注册处理器 ──────────────────────────────────────────────────────────

@register("v3_watermark")
class WatermarkV3Filter(FilterProcessor):
    """V3 水印滤镜 — 基于 LayoutResult 的声明式渲染。"""

    def process(self, ctx: PipelineContext):
        config_dict = ctx.get("v3_config")
        if not config_dict:
            ctx.success()
            return

        config = _dict_to_watermark_config(config_dict)
        img = ctx.get_buffer()[0]

        # 1. 计算布局
        layout = compute_layout(config, img.width, img.height)

        # 2. 创建画布并粘贴原图
        canvas = Image.new("RGBA", (layout.canvas.w, layout.canvas.h), config.canvas.background)
        canvas.paste(img, (layout.image_rect.x, layout.image_rect.y))

        # 3. 获取 EXIF / file_path 用于文本值解析
        exif = ctx.get_exif() or {}
        file_path = ctx.get("input_path", "")

        # 4. 按 LayoutResult 顺序渲染每个元素
        for el in layout.elements:
            self._render_element(canvas, el, config, exif, file_path)

        ctx.update_buffer([canvas]).save_buffer(self.name()).success()

    def _render_element(
        self,
        canvas: Image.Image,
        el: ComputedElement,
        config: WatermarkConfig,
        exif: dict,
        file_path: str,
    ) -> None:
        if el.type == "text":
            self._render_text(canvas, el, config, exif, file_path)
        elif el.type == "logo":
            self._render_logo(canvas, el, exif)
        elif el.type == "signature":
            self._render_signature(canvas, el, exif, file_path)

    # ── 文本渲染 ────────────────────────────────────────────────────────

    def _render_text(
        self,
        canvas: Image.Image,
        el: ComputedElement,
        config: WatermarkConfig,
        exif: dict,
        file_path: str,
    ) -> None:
        if not isinstance(el.content, TextContent):
            return

        text = _build_text(el.content, config.custom_text, exif, file_path)
        if not text:
            return

        font_size = el.style.font_size or 16
        segment = TextSegment(
            text=text,
            font_path=el.style.font_family,
            height=font_size,
            color=el.style.color,
            is_bold=el.style.bold,
        )
        text_img = RichTextGenerator.generate(segment)

        x, y = _apply_anchor_for_paste(el.rect, el.anchor, text_img.width, text_img.height)
        canvas.paste(text_img, (x, y), mask=text_img if text_img.mode == "RGBA" else None)

    # ── Logo 渲染 ───────────────────────────────────────────────────────

    def _render_logo(self, canvas: Image.Image, el: ComputedElement, exif: dict) -> None:
        if not isinstance(el.content, LogoContent):
            return

        logo_path = el.content.path
        if not logo_path:
            # 空 path 表示 auto logo；仅根据受控 EXIF 品牌值匹配内置资源。
            logo_path = resolve_auto_logo(exif)

        if not logo_path:
            return

        try:
            from core.image_io import load_logo

            logo = load_logo(logo_path)
        except (FileNotFoundError, OSError):
            return

        logo = logo.resize((el.rect.w, el.rect.h), Image.Resampling.LANCZOS)
        x, y = _apply_anchor_for_paste(el.rect, el.anchor, logo.width, logo.height)
        canvas.paste(logo, (x, y), mask=logo if logo.mode == "RGBA" else None)

    # ── 签名渲染（简化版）────────────────────────────────────────────────

    def _render_signature(
        self,
        canvas: Image.Image,
        el: ComputedElement,
        exif: dict,
        file_path: str,
    ) -> None:
        if not isinstance(el.content, SignatureContent):
            return

        sig_path = el.content.path
        if not sig_path:
            return

        try:
            from core.image_io import load_logo

            sig = load_logo(sig_path)
        except (FileNotFoundError, OSError):
            return

        # 按计算后的 rect 尺寸缩放
        sig = sig.resize((el.rect.w, el.rect.h), Image.Resampling.LANCZOS)
        x, y = _apply_anchor_for_paste(el.rect, el.anchor, sig.width, sig.height)
        canvas.paste(sig, (x, y), mask=sig if sig.mode == "RGBA" else None)


# ── 辅助函数 ────────────────────────────────────────────────────────────


def _build_text(content: TextContent, custom_text: str, exif: dict, file_path: str) -> str:
    """将 TextContent 中的 chips 解析为实际文本字符串。"""
    registry = get_default_registry()
    texts: list[str] = []

    for chip in content.chips:
        if chip.field_id == "empty":
            continue
        if chip.field_id == "custom_text":
            texts.append(chip.custom_text or custom_text or "")
            continue

        field_def = registry.get(chip.field_id)
        if field_def is None or not field_def.jinja_template:
            continue

        template = Template(field_def.jinja_template)
        context = {"exif": exif, "file_path": file_path, "file_dir": ""}
        texts.append(template.render(**context))

    return content.separator.join(texts)


def _apply_anchor_for_paste(
    rect, anchor: str, elem_w: int, elem_h: int
) -> tuple[int, int]:
    """根据 anchor 语义，将元素参考点转换为粘贴用的左上角坐标。

    anchor 语义与 CSS transform-origin 一致：
      top-left     → (rect.x, rect.y) 是元素左上角
      middle-center→ (rect.x, rect.y) 是元素中心
      bottom-right → (rect.x, rect.y) 是元素右下角
      ...
    """
    if "center" in anchor:
        x = rect.x - elem_w // 2
    elif "right" in anchor:
        x = rect.x - elem_w
    else:  # left
        x = rect.x

    if "middle" in anchor:
        y = rect.y - elem_h // 2
    elif "bottom" in anchor:
        y = rect.y - elem_h
    else:  # top
        y = rect.y

    return x, y


def _dict_to_watermark_config(data: dict) -> WatermarkConfig:
    """将前端/API 传来的 plain dict 重建为 layout_engine 的 dataclass。"""
    from shared.v3_layout.layout_engine import (
        CanvasConfig,
        FieldChip,
        LogoContent,
        MarginsConfig,
        RegionConfig,
        SignatureContent,
        SlotConfig,
        StyleConfig,
        TextContent,
    )

    def _style(d: dict | None) -> StyleConfig | None:
        if d is None:
            return None
        return StyleConfig(
            font_size=d.get("font_size"),
            font_size_ratio=d.get("font_size_ratio"),
            size_reference=d.get("size_reference", "region_height"),
            color=d.get("color", "#222222"),
            font_family=d.get("font_family", "NotoSansCJKsc-Bold.otf"),
            bold=d.get("bold", True),
            line_height=d.get("line_height", 1.2),
        )

    def _content(d: dict | None):
        if d is None:
            return None
        # 通过字段存在性判断类型（与 TS 类型守卫 isTextContent/isLogoContent/isSignatureContent 对应）
        if "chips" in d and "separator" in d:
            return TextContent(
                chips=[
                    FieldChip(
                        field_id=c.get("field_id", "empty"),
                        custom_text=c.get("custom_text", ""),
                    )
                    for c in d["chips"]
                ],
                separator=d.get("separator", " "),
            )
        if "path" in d and "size_ratio" in d:
            return SignatureContent(
                path=d.get("path", ""),
                invert_mono=d.get("invert_mono", False),
                size_ratio=d.get("size_ratio", 0.20),
            )
        if "path" in d and "color" in d:
            return LogoContent(
                path=d.get("path", ""),
                color=d.get("color", "#D8D8D6"),
                size_ratio=d.get("size_ratio", 0.6),
            )
        return None

    def _slot(d: dict | None) -> SlotConfig | None:
        if d is None:
            return None
        return SlotConfig(
            enabled=d.get("enabled", False),
            content=_content(d.get("content")),
            style=_style(d.get("style")),
        )

    def _region(d: dict) -> RegionConfig:
        return RegionConfig(
            id=d.get("id", ""),
            type=d.get("type", ""),
            enabled=d.get("enabled", False),
            slots={k: _slot(v) for k, v in (d.get("slots") or {}).items()},
            height=d.get("height"),
            edge=d.get("edge"),
            width=d.get("width"),
            alignment=d.get("alignment", "start"),
            anchor=d.get("anchor"),
            offset_x=d.get("offset_x", 0.0),
            offset_y=d.get("offset_y", 0.0),
            offset_unit=d.get("offset_unit", "short_edge_ratio"),
        )

    canvas = data.get("canvas", {})
    margins = canvas.get("margins", {})

    return WatermarkConfig(
        canvas=CanvasConfig(
            margins=MarginsConfig(
                top=margins.get("top", 0),
                right=margins.get("right", 0),
                bottom=margins.get("bottom", 0),
                left=margins.get("left", 0),
            ),
            background=canvas.get("background", "#FFFFFF"),
            border_radius=canvas.get("border_radius", 0),
        ),
        regions=[_region(r) for r in data.get("regions", [])],
        defaults=_style(data.get("defaults")) or StyleConfig(),
        custom_text=data.get("custom_text", ""),
    )
