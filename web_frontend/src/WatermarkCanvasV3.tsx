/**
 * V3 WatermarkCanvas — 使用 Region-Based Layout Engine 的 Canvas 渲染器
 *
 * 与 V2 的区别：
 * - 不内联计算坐标，全部委托给 computeLayout()
 * - 按 LayoutResult 的顺序绘制元素
 * - 支持 footer-bar / side-edge / free 三种区域类型
 */

import { useEffect, useRef } from 'react';
import type { WatermarkConfigV3, FieldChip, TextContent } from './v3Types';
import { PLACEHOLDER_EXIF } from './v3Types';
import { computeLayout } from './v3_layout/layoutEngine';
import type { LayoutResult, ComputedElement } from './v3_layout/layoutEngine';

// ── 文本解析（chips → 实际文本）───────────────────────────────────────

function resolveText(chip: FieldChip, customText: string): string {
  if (chip.field_id === 'custom_text') return chip.custom_text || customText || '';
  if (chip.field_id === 'empty') return '';
  return PLACEHOLDER_EXIF[chip.field_id] ?? '';
}

function buildText(content: TextContent, customText: string): string {
  const texts = content.chips
    .filter(c => c.field_id !== 'empty')
    .map(c => resolveText(c, customText));
  return texts.join(content.separator);
}

// ── 渲染函数 ──────────────────────────────────────────────────────────

function renderCanvas(
  ctx: CanvasRenderingContext2D,
  layout: LayoutResult,
  image: HTMLImageElement | null,
  _config: WatermarkConfigV3,
) {
  const { canvas, image_rect, elements } = layout;

  // 1. 绘制画布背景
  ctx.fillStyle = _config.canvas.background;
  ctx.fillRect(0, 0, canvas.w, canvas.h);

  // 2. 绘制照片主体（或占位）
  if (image) {
    ctx.drawImage(image, image_rect.x, image_rect.y, image_rect.w, image_rect.h);
  } else {
    // Placeholder
    const grad = ctx.createLinearGradient(
      image_rect.x, image_rect.y,
      image_rect.x + image_rect.w, image_rect.y + image_rect.h
    );
    grad.addColorStop(0, '#3a3832');
    grad.addColorStop(0.5, '#2a2824');
    grad.addColorStop(1, '#1a1814');
    ctx.fillStyle = grad;
    ctx.fillRect(image_rect.x, image_rect.y, image_rect.w, image_rect.h);

    ctx.strokeStyle = 'rgba(138,122,92,0.15)';
    ctx.lineWidth = 1;
    for (let i = -canvas.w; i < canvas.w + canvas.h; i += 60) {
      ctx.beginPath();
      ctx.moveTo(image_rect.x + i, image_rect.y);
      ctx.lineTo(image_rect.x + i - canvas.h, image_rect.y + image_rect.h);
      ctx.stroke();
    }
  }

  // 3. 绘制水印元素
  for (const el of elements) {
    drawElement(ctx, el, _config.custom_text ?? '');
  }

  // 4. 全局效果（圆角裁剪）— 需要在最外层 clip
  // 注意：圆角应该在绘制背景之前应用，这里简化处理
  // 实际应用中，clip 应该在步骤 1 之前设置
}

function drawElement(ctx: CanvasRenderingContext2D, el: ComputedElement, customText: string) {
  const { rect, anchor, content, style } = el;

  switch (el.type) {
    case 'text': {
      if (!('chips' in content)) return;
      const text = buildText(content as TextContent, customText);
      if (!text) return;

      const fontWeight = style.bold ? '700' : '400';
      const fontSize = style.font_size ?? 16;
      ctx.save();
      ctx.font = `${fontWeight} ${fontSize}px "AkaSemiNoto", "Microsoft YaHei", sans-serif`;
      ctx.fillStyle = style.color;
      ctx.textAlign = anchor.includes('right') ? 'right' : anchor.includes('center') ? 'center' : 'left';
      ctx.textBaseline = anchor.includes('bottom') ? 'bottom' : anchor.includes('middle') ? 'middle' : 'top';
      ctx.fillText(text, rect.x, rect.y);
      ctx.restore();
      break;
    }

    case 'logo': {
      // Logo 绘制：简化为矩形占位，实际应加载图片
      const origin = anchorOrigin(rect, anchor);
      ctx.fillStyle = '#cccccc';
      ctx.fillRect(origin.x, origin.y, rect.w, rect.h);
      break;
    }

    case 'signature': {
      // 签名绘制：简化为矩形占位
      const origin = anchorOrigin(rect, anchor);
      ctx.fillStyle = '#aaaaaa';
      ctx.fillRect(origin.x, origin.y, rect.w, rect.h);
      break;
    }
  }
}

function anchorOrigin(rect: ComputedElement['rect'], anchor: string): { x: number; y: number } {
  const x = anchor.includes('right')
    ? rect.x - rect.w
    : anchor.includes('center')
      ? rect.x - rect.w / 2
      : rect.x;
  const y = anchor.includes('bottom')
    ? rect.y - rect.h
    : anchor.includes('middle')
      ? rect.y - rect.h / 2
      : rect.y;
  return { x, y };
}

// ── 组件 ──────────────────────────────────────────────────────────────

export function WatermarkCanvasV3({
  config,
  image,
  imageSize,
}: {
  config: WatermarkConfigV3;
  image: HTMLImageElement | null;
  imageSize?: { width: number; height: number } | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 确定图片尺寸
    let imgW: number, imgH: number;
    if (image) {
      imgW = image.naturalWidth;
      imgH = image.naturalHeight;
    } else if (imageSize) {
      imgW = imageSize.width;
      imgH = imageSize.height;
    } else {
      imgW = 900;
      imgH = 675;
    }

    // 计算布局
    const layout = computeLayout(config, imgW, imgH);

    // DPR 处理
    const dpr = window.devicePixelRatio || 1;
    canvas.width = layout.canvas.w * dpr;
    canvas.height = layout.canvas.h * dpr;
    canvas.style.width = `${layout.canvas.w}px`;
    canvas.style.height = `${layout.canvas.h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // 圆角裁剪（如果需要）
    if (config.canvas.border_radius > 0) {
      ctx.save();
      const r = config.canvas.border_radius;
      const cw = layout.canvas.w;
      const ch = layout.canvas.h;
      ctx.beginPath();
      ctx.moveTo(r, 0);
      ctx.lineTo(cw - r, 0);
      ctx.quadraticCurveTo(cw, 0, cw, r);
      ctx.lineTo(cw, ch - r);
      ctx.quadraticCurveTo(cw, ch, cw - r, ch);
      ctx.lineTo(r, ch);
      ctx.quadraticCurveTo(0, ch, 0, ch - r);
      ctx.lineTo(0, r);
      ctx.quadraticCurveTo(0, 0, r, 0);
      ctx.closePath();
      ctx.clip();
    }

    // 绘制
    renderCanvas(ctx, layout, image, config);

    // 恢复 clip
    if (config.canvas.border_radius > 0) {
      ctx.restore();
    }
  }, [config, image, imageSize]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        display: 'block',
        maxWidth: '100%',
        maxHeight: '100%',
        objectFit: 'contain',
        margin: '0 auto',
      }}
    />
  );
}
