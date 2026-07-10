/**
 * V3 Region-Based Layout Engine — 纯函数布局计算（TypeScript 版）
 *
 * 此模块不包含任何 Canvas/DOM 依赖，只负责：
 *   - 输入：WatermarkConfig + imageW/H
 *   - 输出：LayoutResult（每个元素在画布上的绝对位置和尺寸）
 *
 * 与 Python 版本共享同一套算法逻辑，通过单元测试保证一致性。
 */

// ── 基础几何 ──────────────────────────────────────────────────────────

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Size {
  w: number;
  h: number;
}

export function rect(x = 0, y = 0, w = 0, h = 0): Rect {
  return { x, y, w, h };
}

export function rectRight(r: Rect): number { return r.x + r.w; }
export function rectBottom(r: Rect): number { return r.y + r.h; }
export function rectCenterX(r: Rect): number { return r.x + Math.floor(r.w / 2); }
export function rectCenterY(r: Rect): number { return r.y + Math.floor(r.h / 2); }

// ── 配置类型 ──────────────────────────────────────────────────────────

export interface MarginsConfig {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface CanvasConfig {
  margins: MarginsConfig;
  background: string;
  border_radius: number;
}

export interface FieldChip {
  field_id: string;
  custom_text?: string;
}

export interface TextContent {
  chips: FieldChip[];
  separator: string;
}

export interface LogoContent {
  path: string;           // 空表示 auto
  color: string;
}

export interface SignatureContent {
  path: string;
  invert_mono: boolean;
  size_ratio: number;
}

export type Content = TextContent | LogoContent | SignatureContent;

export type SizeReference = 'region_height' | 'short_edge' | 'long_edge';

export interface StyleConfig {
  font_size: number | null;
  font_size_ratio: number | null;
  size_reference: SizeReference;
  color: string;
  font_family: string;
  bold: boolean;
  line_height: number;
}

export interface SlotConfig {
  enabled: boolean;
  content: Content | null;
  style: StyleConfig | null;
}

export type RegionType = 'footer-bar' | 'side-edge' | 'free';

export interface RegionConfig {
  id: string;
  type: RegionType;
  enabled: boolean;
  // footer-bar 特有
  slots?: Record<string, SlotConfig>;
  // side-edge 特有
  edge?: 'left' | 'right';
  width?: { mode: 'pixel' | 'short_edge_ratio'; value: number };
  alignment?: 'start' | 'center' | 'end';
  // free 特有
  anchor?: string;        // 九宫格锚点
  offset_x?: number;
  offset_y?: number;
  offset_unit?: 'pixel' | 'short_edge_ratio';
}

export interface WatermarkConfig {
  canvas: CanvasConfig;
  regions: RegionConfig[];
  defaults: StyleConfig;
}

// ── 布局结果 ──────────────────────────────────────────────────────────

export type ElementType = 'text' | 'logo' | 'signature' | 'divider';

export interface ComputedElement {
  id: string;
  type: ElementType;
  rect: Rect;
  anchor: string;         // 九宫格
  content: Content;
  style: StyleConfig;
}

export interface LayoutResult {
  canvas: Size;
  image_rect: Rect;
  elements: ComputedElement[];
}

// ── 布局引擎 ──────────────────────────────────────────────────────────

export function computeLayout(config: WatermarkConfig, imageW: number, imageH: number): LayoutResult {
  // Step 1: 画布尺寸
  const margins = config.canvas.margins;
  const canvasW = imageW + margins.left + margins.right;
  const canvasH = imageH + margins.top + margins.bottom;

  const imageRect = rect(margins.left, margins.top, imageW, imageH);
  const canvas = { w: canvasW, h: canvasH };

  const elements: ComputedElement[] = [];
  const shortEdge = Math.min(imageW, imageH);
  const longEdge = Math.max(imageW, imageH);

  // Step 2: 遍历区域
  for (const region of config.regions) {
    if (!region.enabled) continue;

    switch (region.type) {
      case 'footer-bar':
        elements.push(...computeFooterBar(region, imageRect, canvas, config.defaults, shortEdge, longEdge));
        break;
      case 'side-edge':
        elements.push(...computeSideEdge(region, imageRect, config.defaults, shortEdge, longEdge));
        break;
      case 'free':
        elements.push(...computeFree(region, imageRect, config.defaults, shortEdge, longEdge));
        break;
    }
  }

  return { canvas, image_rect: imageRect, elements };
}

// ── 各区域类型计算 ────────────────────────────────────────────────────

function computeFooterBar(
  region: RegionConfig,
  imageRect: Rect,
  canvas: Size,
  defaults: StyleConfig,
  shortEdge: number,
  longEdge: number,
): ComputedElement[] {
  const regionBounds = rect(
    0,
    rectBottom(imageRect),
    canvas.w,
    canvas.h - rectBottom(imageRect),
  );

  const elements: ComputedElement[] = [];
  const slotLayouts = computeFooterSlots(regionBounds, region.slots ?? {});

  for (const [slotId, slotBounds] of Object.entries(slotLayouts)) {
    const slot = region.slots?.[slotId];
    if (!slot || !slot.enabled || !slot.content) continue;

    const style = mergeStyle(defaults, slot.style);
    const fontSize = resolveFontSize(style, slotBounds.h, shortEdge, longEdge);

    if (isTextContent(slot.content) && slot.content.chips.length > 0) {
      const anchor = footerSlotAnchor(slotId);
      const pos = applyAnchor(slotBounds, anchor);

      elements.push({
        id: `${region.id}-${slotId}`,
        type: 'text',
        rect: rect(pos.x, pos.y, slotBounds.w, fontSize),
        anchor,
        content: slot.content,
        style: withFontSize(style, fontSize),
      });
    } else if (isLogoContent(slot.content)) {
      const logoH = resolveLogoSize(slot.content, shortEdge);
      const pos = applyAnchor(slotBounds, 'middle-center');
      elements.push({
        id: `${region.id}-${slotId}`,
        type: 'logo',
        rect: rect(pos.x, pos.y, logoH * 3, logoH),
        anchor: 'middle-center',
        content: slot.content,
        style: defaults,
      });
    }
  }

  return elements;
}

function computeSideEdge(
  region: RegionConfig,
  imageRect: Rect,
  defaults: StyleConfig,
  shortEdge: number,
  longEdge: number,
): ComputedElement[] {
  // 区域宽度
  let regionW: number;
  if (region.width) {
    if (region.width.mode === 'pixel') {
      regionW = Math.round(region.width.value);
    } else {
      regionW = Math.max(40, Math.round(shortEdge * region.width.value));
    }
  } else {
    regionW = Math.max(40, Math.round(shortEdge * 0.12));
  }

  // 区域位置
  const regionBounds: Rect = region.edge === 'left'
    ? rect(imageRect.x, imageRect.y, regionW, imageRect.h)
    : rect(rectRight(imageRect) - regionW, imageRect.y, regionW, imageRect.h);

  const elements: ComputedElement[] = [];

  if (region.slots) {
    for (const [slotId, slot] of Object.entries(region.slots)) {
      if (!slot.enabled || !slot.content) continue;

      const style = mergeStyle(defaults, slot.style);
      const fontSize = resolveFontSize(style, regionBounds.h, shortEdge, longEdge);

      if (isTextContent(slot.content) && slot.content.chips.length > 0) {
        const lineH = Math.round(fontSize * style.line_height);
        const totalH = lineH;
        const startY = regionBounds.y + Math.floor((regionBounds.h - totalH) / 2);

        let x: number;
        let anchor: string;
        if (region.alignment === 'start') {
          x = regionBounds.x + 8;
          anchor = 'middle-left';
        } else if (region.alignment === 'end') {
          x = rectRight(regionBounds) - 8;
          anchor = 'middle-right';
        } else {
          x = rectCenterX(regionBounds);
          anchor = 'middle-center';
        }

        elements.push({
          id: `${region.id}-${slotId}`,
          type: 'text',
          rect: rect(x, startY, regionBounds.w - 16, lineH),
          anchor,
          content: slot.content,
          style: withFontSize(style, fontSize),
        });
      }
    }
  }

  return elements;
}

function computeFree(
  region: RegionConfig,
  imageRect: Rect,
  defaults: StyleConfig,
  shortEdge: number,
  _longEdge: number,
): ComputedElement[] {
  const elements: ComputedElement[] = [];

  const anchor = region.anchor ?? 'middle-center';
  const anchorX = imageRect.x + imageRect.w * anchorCol(anchor);
  const anchorY = imageRect.y + imageRect.h * anchorRow(anchor);

  const offsetUnit = region.offset_unit === 'short_edge_ratio' ? shortEdge : 1;
  const finalX = anchorX + Math.round((region.offset_x ?? 0) * offsetUnit);
  const finalY = anchorY + Math.round((region.offset_y ?? 0) * offsetUnit);

  if (region.slots) {
    for (const [slotId, slot] of Object.entries(region.slots)) {
      if (!slot.enabled || !slot.content) continue;

      const style = mergeStyle(defaults, slot.style);

      if (isSignatureContent(slot.content)) {
        const sigH = Math.round(shortEdge * slot.content.size_ratio);
        elements.push({
          id: `${region.id}-${slotId}`,
          type: 'signature',
          rect: rect(finalX, finalY, sigH, sigH),
          anchor,
          content: slot.content,
          style,
        });
      }
    }
  }

  return elements;
}

// ── 辅助函数 ──────────────────────────────────────────────────────────

function resolveFontSize(
  style: StyleConfig,
  regionHeight: number,
  shortEdge: number,
  longEdge: number,
): number {
  if (style.font_size !== null && style.font_size > 0) {
    return style.font_size;
  }

  const ratio = style.font_size_ratio ?? 0.3;

  let ref: number;
  switch (style.size_reference) {
    case 'short_edge':
      ref = shortEdge;
      break;
    case 'long_edge':
      ref = longEdge;
      break;
    default:
      ref = regionHeight;
  }

  return Math.max(8, Math.round(ref * ratio));
}

function resolveLogoSize(_content: LogoContent, shortEdge: number): number {
  return Math.max(16, Math.round(shortEdge * 0.10));
}

function mergeStyle(defaults: StyleConfig, override: StyleConfig | null): StyleConfig {
  if (!override) {
    return {
      font_size: defaults.font_size,
      font_size_ratio: defaults.font_size_ratio,
      size_reference: defaults.size_reference,
      color: defaults.color,
      font_family: defaults.font_family,
      bold: defaults.bold,
      line_height: defaults.line_height,
    };
  }
  return {
    font_size: override.font_size !== null ? override.font_size : defaults.font_size,
    font_size_ratio: override.font_size_ratio !== null ? override.font_size_ratio : defaults.font_size_ratio,
    size_reference: override.size_reference || defaults.size_reference,
    color: override.color || defaults.color,
    font_family: override.font_family || defaults.font_family,
    bold: override.bold,
    line_height: override.line_height || defaults.line_height,
  };
}

function withFontSize(style: StyleConfig, fontSize: number): StyleConfig {
  return {
    font_size: fontSize,
    font_size_ratio: null,
    size_reference: style.size_reference,
    color: style.color,
    font_family: style.font_family,
    bold: style.bold,
    line_height: style.line_height,
  };
}

function anchorCol(anchor: string): number {
  if (anchor.includes('left')) return 0.0;
  if (anchor.includes('right')) return 1.0;
  return 0.5;
}

function anchorRow(anchor: string): number {
  if (anchor.includes('top')) return 0.0;
  if (anchor.includes('bottom')) return 1.0;
  return 0.5;
}

function applyAnchor(bounds: Rect, anchor: string): Point {
  let ax = bounds.x;
  if (anchor.includes('center') || anchor.includes('right')) {
    ax = anchor.includes('center') ? rectCenterX(bounds) : rectRight(bounds);
  }

  let ay = bounds.y;
  if (anchor.includes('middle') || anchor.includes('bottom')) {
    ay = anchor.includes('middle') ? rectCenterY(bounds) : rectBottom(bounds);
  }

  return { x: ax, y: ay };
}

function footerSlotAnchor(slotId: string): string {
  const mapping: Record<string, string> = {
    'left-logo': 'middle-left',
    'left-top': 'top-left',
    'left-bottom': 'bottom-left',
    'center': 'middle-center',
    'right-top': 'top-right',
    'right-bottom': 'bottom-right',
    'right-logo': 'middle-right',
  };
  return mapping[slotId] ?? 'middle-center';
}

function computeFooterSlots(regionBounds: Rect, _slots: Record<string, SlotConfig>): Record<string, Rect> {
  const results: Record<string, Rect> = {};

  const totalW = regionBounds.w;
  const logoW = Math.max(40, Math.floor(totalW * 0.15));
  const textW = Math.floor((totalW - logoW * 2) / 2);

  results['left-logo'] = rect(regionBounds.x, regionBounds.y, logoW, regionBounds.h);

  const leftTextX = regionBounds.x + logoW;
  results['left-top'] = rect(leftTextX, regionBounds.y, textW, Math.floor(regionBounds.h / 2));
  results['left-bottom'] = rect(leftTextX, regionBounds.y + Math.floor(regionBounds.h / 2), textW, Math.floor(regionBounds.h / 2));

  results['center'] = rect(leftTextX + textW, regionBounds.y, 0, regionBounds.h);

  const rightTextX = leftTextX + textW;
  results['right-top'] = rect(rightTextX, regionBounds.y, textW, Math.floor(regionBounds.h / 2));
  results['right-bottom'] = rect(rightTextX, regionBounds.y + Math.floor(regionBounds.h / 2), textW, Math.floor(regionBounds.h / 2));

  results['right-logo'] = rect(rectRight(regionBounds) - logoW, regionBounds.y, logoW, regionBounds.h);

  return results;
}

// ── 类型守卫 ──────────────────────────────────────────────────────────

function isTextContent(c: Content): c is TextContent {
  return 'chips' in c && 'separator' in c;
}

function isLogoContent(c: Content): c is LogoContent {
  return 'path' in c && 'color' in c && !('size_ratio' in c);
}

function isSignatureContent(c: Content): c is SignatureContent {
  return 'path' in c && 'size_ratio' in c;
}
