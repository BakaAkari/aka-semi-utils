"""V3 Region-Based Layout Engine — 纯函数布局计算。

此模块不包含任何 PIL/Canvas 依赖，只负责：
  - 输入：WatermarkConfig + image_w/h
  - 输出：LayoutResult（每个水印元素在画布上的绝对位置和尺寸）

前后端共享同一套算法逻辑，通过单元测试保证一致性。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ── 基础几何 ─────────────────────────────────

@dataclass(frozen=True, slots=True)
class Rect:
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def center_x(self) -> int:
        return self.x + self.w // 2

    @property
    def center_y(self) -> int:
        return self.y + self.h // 2


@dataclass(frozen=True, slots=True)
class Point:
    x: int = 0
    y: int = 0


@dataclass(frozen=True, slots=True)
class Size:
    w: int = 0
    h: int = 0


# ── 配置类型 ─────────────────────────────────

@dataclass(slots=True)
class MarginsConfig:
    top: int = 0
    right: int = 0
    bottom: int = 0
    left: int = 0


@dataclass(slots=True)
class CanvasConfig:
    margins: MarginsConfig = field(default_factory=MarginsConfig)
    background: str = "#FFFFFF"
    border_radius: int = 0


@dataclass(slots=True)
class FieldChip:
    field_id: str = "empty"
    custom_text: str = ""


@dataclass(slots=True)
class TextContent:
    chips: list[FieldChip] = field(default_factory=list)
    separator: str = " "


@dataclass(slots=True)
class LogoContent:
    path: str = ""           # 空表示 auto
    color: str = "#D8D8D6"
    size_ratio: float = 0.6  # logo 高度占所在区域高度的比例


@dataclass(slots=True)
class SignatureContent:
    path: str = ""
    invert_mono: bool = False
    size_ratio: float = 0.20


@dataclass(slots=True)
class StyleConfig:
    font_size: int | None = None
    font_size_ratio: float | None = None
    size_reference: Literal["region_height", "short_edge", "long_edge"] = "region_height"
    color: str = "#222222"
    font_family: str = "NotoSansCJKsc-Bold.otf"
    bold: bool = True
    line_height: float = 1.2


@dataclass(slots=True)
class SlotConfig:
    enabled: bool = False
    content: TextContent | LogoContent | SignatureContent | None = None
    style: StyleConfig | None = None


@dataclass(slots=True)
class RegionConfig:
    id: str = ""
    type: str = ""  # 'footer-bar' | 'side-edge' | 'free'
    enabled: bool = False
    # footer-bar 特有
    slots: dict[str, SlotConfig] = field(default_factory=dict)
    height: float | None = None  # 占图片短边的比例，由布局引擎解析为实际像素高度
    # side-edge 特有
    edge: Literal["left", "right"] | None = None
    width: dict[str, float | int] | None = None  # {"mode": "pixel"|"short_edge_ratio", "value": ...}
    alignment: Literal["start", "center", "end"] = "start"
    # free 特有
    anchor: str | None = None  # 九宫格锚点
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_unit: Literal["pixel", "short_edge_ratio"] = "short_edge_ratio"


@dataclass(slots=True)
class WatermarkConfig:
    canvas: CanvasConfig = field(default_factory=CanvasConfig)
    regions: list[RegionConfig] = field(default_factory=list)
    defaults: StyleConfig = field(default_factory=StyleConfig)
    custom_text: str = ""


# ── 布局结果 ─────────────────────────────────

@dataclass(slots=True)
class ComputedElement:
    id: str
    type: Literal["text", "logo", "signature", "divider"]
    rect: Rect
    anchor: str  # 九宫格
    content: TextContent | LogoContent | SignatureContent
    style: StyleConfig


@dataclass(slots=True)
class LayoutResult:
    canvas: Size
    image_rect: Rect
    elements: list[ComputedElement] = field(default_factory=list)


# ── Layout Diagnostics ─────────────────────────────────

@dataclass(slots=True)
class DiagnosticItem:
    id: str
    type: str
    severity: Literal["error", "warning"]
    message: str
    element_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LayoutResultWithDiagnostics:
    layout: LayoutResult
    diagnostics: list[DiagnosticItem] = field(default_factory=list)


# ── 布局引擎 ─────────────────────────────────

def compute_layout(config: WatermarkConfig, image_w: int, image_h: int) -> LayoutResult:
    """主入口：计算每个水印元素在画布上的绝对位置和尺寸。"""

    # ── Step 1: 画布尺寸 ─────────────────────────────
    margins = config.canvas.margins
    short_edge = min(image_w, image_h)
    long_edge = max(image_w, image_h)

    # footer-bar 的 height 为占短边比例，在此解析为实际像素底部边距
    for region in config.regions:
        if region.enabled and region.type == "footer-bar" and region.height is not None:
            margins.bottom = max(20, round(short_edge * region.height))

    canvas_w = image_w + margins.left + margins.right
    canvas_h = image_h + margins.top + margins.bottom

    image_rect = Rect(x=margins.left, y=margins.top, w=image_w, h=image_h)
    canvas = Size(w=canvas_w, h=canvas_h)

    elements: list[ComputedElement] = []
    for region in config.regions:
        if not region.enabled:
            continue

        if region.type == "footer-bar":
            elements.extend(_compute_footer_bar(region, image_rect, canvas, config.defaults, short_edge, long_edge))
        elif region.type == "side-edge":
            elements.extend(_compute_side_edge(region, image_rect, config.defaults, short_edge, long_edge))
        elif region.type == "free":
            elements.extend(_compute_free(region, image_rect, config.defaults, short_edge, long_edge))

    return LayoutResult(canvas=canvas, image_rect=image_rect, elements=elements)


def compute_layout_with_diagnostics(config: WatermarkConfig, image_w: int, image_h: int) -> LayoutResultWithDiagnostics:
    """带诊断的布局计算。"""
    layout = compute_layout(config, image_w, image_h)
    diagnostics = diagnose_layout(layout, config)
    return LayoutResultWithDiagnostics(layout=layout, diagnostics=diagnostics)


def diagnose_layout(layout: LayoutResult, _config: WatermarkConfig) -> list[DiagnosticItem]:
    """布局诊断：检测重叠、越界、空内容、缺资源。"""
    diagnostics: list[DiagnosticItem] = []
    canvas = layout.canvas
    elements = layout.elements

    # 1. 重叠
    for i in range(len(elements)):
        for j in range(i + 1, len(elements)):
            a = elements[i]
            b = elements[j]
            if _rects_overlap(a.rect, b.rect):
                diagnostics.append(DiagnosticItem(
                    id=f"overlap-{a.id}-{b.id}",
                    type="overlap",
                    severity="error",
                    message=f"{a.id} 与 {b.id} 重叠",
                    element_ids=[a.id, b.id],
                ))

    # 2. 越界
    for el in elements:
        if (
            el.rect.x < 0
            or el.rect.y < 0
            or el.rect.right > canvas.w
            or el.rect.bottom > canvas.h
        ):
            diagnostics.append(DiagnosticItem(
                id=f"oob-{el.id}",
                type="out-of-bounds",
                severity="error",
                message=f"{el.id} 越出画布",
                element_ids=[el.id],
            ))

    # 3. 空内容 / 缺资源
    for el in elements:
        if el.type == "text":
            if isinstance(el.content, TextContent):
                non_empty = any(c.field_id != "empty" for c in el.content.chips)
                if not non_empty:
                    diagnostics.append(DiagnosticItem(
                        id=f"empty-{el.id}",
                        type="empty-enabled-slot",
                        severity="warning",
                        message=f"{el.id} 已启用但没有字段",
                        element_ids=[el.id],
                    ))
        elif el.type == "signature" and isinstance(el.content, SignatureContent) and el.content.path == "":
            diagnostics.append(DiagnosticItem(
                id=f"missing-sig-{el.id}",
                type="missing-resource",
                severity="warning",
                message=f"{el.id} 未上传签名",
                element_ids=[el.id],
            ))

    # 4. 字号过大
    for el in elements:
        if el.type == "text" and el.style.font_size is not None and el.style.font_size > el.rect.h:
            diagnostics.append(DiagnosticItem(
                id=f"font-large-{el.id}",
                type="font-too-large",
                severity="warning",
                message=f"{el.id} 字号超过 slot 高度",
                element_ids=[el.id],
            ))

    return diagnostics


def _rects_overlap(a: Rect, b: Rect) -> bool:
    return not (
        a.right <= b.x
        or a.x >= b.right
        or a.bottom <= b.y
        or a.y >= b.bottom
    )


# ── 各区域类型计算 ─────────────────────────────────

def _compute_footer_bar(
    region: RegionConfig,
    image_rect: Rect,
    canvas: Size,
    defaults: StyleConfig,
    short_edge: int,
    long_edge: int,
) -> list[ComputedElement]:
    """底部水印条：7 个槽位（left-logo, left-top, left-bottom, center, right-top, right-bottom, right-logo）。"""

    region_bounds = Rect(
        x=0,
        y=image_rect.bottom,
        w=canvas.w,
        h=canvas.h - image_rect.bottom,
    )

    elements: list[ComputedElement] = []
    slot_layouts = _compute_footer_slots(region_bounds, region.slots)

    for slot_id, slot_bounds in slot_layouts.items():
        slot = region.slots.get(slot_id)
        if not slot or not slot.enabled or slot.content is None:
            continue

        style = _merge_style(defaults, slot.style)
        font_size = _resolve_font_size(style, slot_bounds.h, short_edge, long_edge)

        if isinstance(slot.content, TextContent) and slot.content.chips:
            anchor = _footer_slot_anchor(slot_id)
            pos = _apply_anchor(slot_bounds, anchor)

            elements.append(ComputedElement(
                id=f"{region.id}-{slot_id}",
                type="text",
                rect=Rect(x=pos.x, y=pos.y, w=slot_bounds.w, h=font_size),
                anchor=anchor,
                content=slot.content,
                style=_with_font_size(style, font_size),
            ))

        elif isinstance(slot.content, LogoContent):
            logo_h = _resolve_logo_size(slot.content, region_bounds.h)
            pos = _apply_anchor(slot_bounds, "middle-center")
            elements.append(ComputedElement(
                id=f"{region.id}-{slot_id}",
                type="logo",
                rect=Rect(x=pos.x, y=pos.y, w=logo_h * 3, h=logo_h),
                anchor="middle-center",
                content=slot.content,
                style=defaults,
            ))

    return elements


def _compute_side_edge(
    region: RegionConfig,
    image_rect: Rect,
    defaults: StyleConfig,
    short_edge: int,
    long_edge: int,
) -> list[ComputedElement]:
    """图片主体垂直边缘：单行文本垂直堆叠。"""

    if region.width:
        if region.width.get("mode") == "pixel":
            region_w = int(region.width["value"])
        else:  # short_edge_ratio
            region_w = max(40, round(short_edge * float(region.width["value"])))
    else:
        region_w = max(40, round(short_edge * 0.12))

    if region.edge == "left":
        region_bounds = Rect(
            x=image_rect.x,
            y=image_rect.y,
            w=region_w,
            h=image_rect.h,
        )
    else:  # right
        region_bounds = Rect(
            x=image_rect.right - region_w,
            y=image_rect.y,
            w=region_w,
            h=image_rect.h,
        )

    elements: list[ComputedElement] = []

    if region.slots:
        for slot_id, slot in region.slots.items():
            if not slot.enabled or slot.content is None:
                continue

            style = _merge_style(defaults, slot.style)
            font_size = _resolve_font_size(style, region_bounds.h, short_edge, long_edge)

            if isinstance(slot.content, TextContent) and slot.content.chips:
                line_h = round(font_size * style.line_height)
                n_lines = 1
                total_h = n_lines * line_h
                start_y = region_bounds.y + (region_bounds.h - total_h) // 2

                if region.alignment == "start":
                    x = region_bounds.x + 8
                    anchor = "middle-left"
                elif region.alignment == "end":
                    x = region_bounds.right - 8
                    anchor = "middle-right"
                else:
                    x = region_bounds.center_x
                    anchor = "middle-center"

                elements.append(ComputedElement(
                    id=f"{region.id}-{slot_id}",
                    type="text",
                    rect=Rect(x=x, y=start_y, w=region_bounds.w - 16, h=line_h),
                    anchor=anchor,
                    content=slot.content,
                    style=_with_font_size(style, font_size),
                ))

    return elements


def _compute_free(
    region: RegionConfig,
    image_rect: Rect,
    defaults: StyleConfig,
    short_edge: int,
    long_edge: int,
) -> list[ComputedElement]:
    """自由定位区域（签名等）。"""

    elements: list[ComputedElement] = []

    anchor = region.anchor or "middle-center"
    anchor_x = image_rect.x + image_rect.w * _anchor_col(anchor)
    anchor_y = image_rect.y + image_rect.h * _anchor_row(anchor)

    offset_unit = short_edge if region.offset_unit == "short_edge_ratio" else 1
    final_x = anchor_x + round(region.offset_x * offset_unit)
    final_y = anchor_y + round(region.offset_y * offset_unit)

    for slot_id, slot in region.slots.items():
        if not slot.enabled or slot.content is None:
            continue

        style = _merge_style(defaults, slot.style)

        if isinstance(slot.content, SignatureContent):
            sig_h = round(short_edge * slot.content.size_ratio)
            elements.append(ComputedElement(
                id=f"{region.id}-{slot_id}",
                type="signature",
                rect=Rect(x=final_x, y=final_y, w=sig_h, h=sig_h),
                anchor=anchor,
                content=slot.content,
                style=style,
            ))

    return elements


# ── 辅助函数 ─────────────────────────────────

def _resolve_font_size(
    style: StyleConfig,
    region_height: int,
    short_edge: int,
    long_edge: int,
) -> int:
    """解析字号。"""
    if style.font_size is not None and style.font_size > 0:
        return style.font_size

    ratio = style.font_size_ratio or 0.3

    if style.size_reference == "short_edge":
        ref = short_edge
    elif style.size_reference == "long_edge":
        ref = long_edge
    else:
        ref = region_height

    return max(8, round(ref * ratio))


def _resolve_logo_size(content: LogoContent, region_height: int) -> int:
    """Logo 高度 = 所在区域高度 * size_ratio，随底栏/水印条高度缩放。"""
    return max(16, round(region_height * content.size_ratio))


def _merge_style(defaults: StyleConfig, override: StyleConfig | None) -> StyleConfig:
    """合并默认样式和覆盖样式。"""
    if override is None:
        return StyleConfig(
            font_size=defaults.font_size,
            font_size_ratio=defaults.font_size_ratio,
            size_reference=defaults.size_reference,
            color=defaults.color,
            font_family=defaults.font_family,
            bold=defaults.bold,
            line_height=defaults.line_height,
        )
    return StyleConfig(
        font_size=override.font_size if override.font_size is not None else defaults.font_size,
        font_size_ratio=override.font_size_ratio if override.font_size_ratio is not None else defaults.font_size_ratio,
        size_reference=override.size_reference or defaults.size_reference,
        color=override.color or defaults.color,
        font_family=override.font_family or defaults.font_family,
        bold=override.bold,
        line_height=override.line_height or defaults.line_height,
    )


def _with_font_size(style: StyleConfig, font_size: int) -> StyleConfig:
    """返回一个 font_size 已解析的 StyleConfig 副本。"""
    return StyleConfig(
        font_size=font_size,
        font_size_ratio=None,
        size_reference=style.size_reference,
        color=style.color,
        font_family=style.font_family,
        bold=style.bold,
        line_height=style.line_height,
    )


def _anchor_col(anchor: str) -> float:
    """九宫格锚点的列比例（0=左, 0.5=中, 1=右）。"""
    if "left" in anchor:
        return 0.0
    if "right" in anchor:
        return 1.0
    return 0.5


def _anchor_row(anchor: str) -> float:
    """九宫格锚点的行比例（0=上, 0.5=中, 1=下）。"""
    if "top" in anchor:
        return 0.0
    if "bottom" in anchor:
        return 1.0
    return 0.5


def _apply_anchor(bounds: Rect, anchor: str) -> Point:
    """根据 anchor 将 bounds 的参考点映射到绝对坐标。

    anchor 语义（CSS transform-origin 风格）：
      top-left:     (x, y)       是元素左上角
      top-center:   (x, y)       是元素上边中点
      middle-left:  (x, y)       是元素左边中点
      middle-center:(x, y)       是元素中心
      ...
    """
    ax = bounds.x
    if "center" in anchor or "right" in anchor:
        ax = bounds.center_x if "center" in anchor else bounds.right

    ay = bounds.y
    if "middle" in anchor or "bottom" in anchor:
        ay = bounds.center_y if "middle" in anchor else bounds.bottom

    return Point(x=ax, y=ay)


def _footer_slot_anchor(slot_id: str) -> str:
    """footer-bar 各槽位的默认 anchor。"""
    mapping = {
        "left-logo": "middle-left",
        "left-top": "top-left",
        "left-bottom": "bottom-left",
        "center": "middle-center",
        "right-top": "top-right",
        "right-bottom": "bottom-right",
        "right-logo": "middle-right",
    }
    return mapping.get(slot_id, "middle-center")


def _compute_footer_slots(region_bounds: Rect, slots: dict[str, SlotConfig]) -> dict[str, Rect]:
    """计算 footer-bar 各槽位的 bounds（简化版）。

    当前策略：
    - 左 logo 区：左侧，宽 15%
    - 右 logo 区：右侧，宽 15%
    - 中间文本区：剩余 70%，左右各半
    """
    results: dict[str, Rect] = {}

    total_w = region_bounds.w
    logo_w = max(40, int(total_w * 0.15))
    text_w = (total_w - logo_w * 2) // 2

    results["left-logo"] = Rect(
        x=region_bounds.x,
        y=region_bounds.y,
        w=logo_w,
        h=region_bounds.h,
    )

    left_text_x = region_bounds.x + logo_w
    results["left-top"] = Rect(
        x=left_text_x,
        y=region_bounds.y,
        w=text_w,
        h=region_bounds.h // 2,
    )
    results["left-bottom"] = Rect(
        x=left_text_x,
        y=region_bounds.y + region_bounds.h // 2,
        w=text_w,
        h=region_bounds.h // 2,
    )

    results["center"] = Rect(
        x=left_text_x + text_w,
        y=region_bounds.y,
        w=0,
        h=region_bounds.h,
    )

    right_text_x = left_text_x + text_w
    results["right-top"] = Rect(
        x=right_text_x,
        y=region_bounds.y,
        w=text_w,
        h=region_bounds.h // 2,
    )
    results["right-bottom"] = Rect(
        x=right_text_x,
        y=region_bounds.y + region_bounds.h // 2,
        w=text_w,
        h=region_bounds.h // 2,
    )

    results["right-logo"] = Rect(
        x=region_bounds.right - logo_w,
        y=region_bounds.y,
        w=logo_w,
        h=region_bounds.h,
    )

    return results
