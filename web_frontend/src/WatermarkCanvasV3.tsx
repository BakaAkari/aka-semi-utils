/**
 * V3 WatermarkCanvas — 使用 Region-Based Layout Engine 的 Canvas 渲染器
 *
 * 与 V2 的区别：
 * - 不内联计算坐标，全部委托给 computeLayout()
 * - 按 LayoutResult 的顺序绘制元素
 * - 支持 footer-bar / side-edge / free 三种区域类型
 *
 * 显示策略：
 * - canvas 内部逻辑分辨率始终等于布局像素，保证输出质量。
 * - 在页面上 canvas 铺满外层容器，按 CSS `contain` 比例缩放，因此修改参数时
 *   预览区（白色边框/画布背景）在容器内的显示尺寸保持不变，只改变内部比例。
 */

import { useEffect, useRef, useState } from 'react';
import type { WatermarkConfigV3, FieldChip, TextContent, PreviewAspectRatio } from './v3Types';
import { PLACEHOLDER_EXIF, PREVIEW_ASPECT_RATIOS } from './v3Types';
import { computeLayout } from './v3_layout/layoutEngine';
import type { LayoutResult, ComputedElement } from './v3_layout/layoutEngine';
import { API_BASE } from './env';

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

// ── Logo 缓存 ─────────────────────────────────────────────────────────

const logoCache = new Map<string, HTMLImageElement>();

function loadLogo(path: string): Promise<HTMLImageElement> {
  const cached = logoCache.get(path);
  if (cached) return Promise.resolve(cached);

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      logoCache.set(path, img);
      resolve(img);
    };
    img.onerror = reject;
    img.src = path;
  });
}

// ── 渲染函数 ──────────────────────────────────────────────────────────

function renderCanvas(
  ctx: CanvasRenderingContext2D,
  layout: LayoutResult,
  image: HTMLImageElement | null,
  logos: Map<string, HTMLImageElement>,
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
      image_rect.x + image_rect.w, image_rect.y + image_rect.h,
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
    drawElement(ctx, el, logos, _config.custom_text ?? '');
  }

  // 4. 全局效果（圆角裁剪）— 需要在最外层 clip
  // 圆角裁剪在组件层通过 clip 设置
}

function drawElement(
  ctx: CanvasRenderingContext2D,
  el: ComputedElement,
  logos: Map<string, HTMLImageElement>,
  customText: string,
) {
  const { type, rect, anchor, content, style } = el;

  switch (type) {
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
      if (!('path' in content)) return;
      const logoPath = content.path || `${API_BASE}/api/logos/default.png`;
      const img = logos.get(logoPath);
      if (img) {
        const origin = anchorOrigin(rect, anchor);
        drawImageContain(ctx, img, origin.x, origin.y, rect.w, rect.h, anchor);
      } else {
        // 加载中/失败占位
        const origin = anchorOrigin(rect, anchor);
        ctx.fillStyle = '#888888';
        ctx.fillRect(origin.x, origin.y, rect.w, rect.h);
      }
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

function drawImageContain(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  x: number,
  y: number,
  w: number,
  h: number,
  anchor: string,
) {
  const imgRatio = img.naturalWidth / img.naturalHeight;
  const boxRatio = w / h;
  let drawW: number;
  let drawH: number;
  if (boxRatio > imgRatio) {
    // 盒子更宽，按高度缩放
    drawH = h;
    drawW = h * imgRatio;
  } else {
    // 盒子更高或相等，按宽度缩放
    drawW = w;
    drawH = w / imgRatio;
  }

  let drawX = x;
  if (anchor.includes('right')) {
    drawX = x + w - drawW;
  } else if (anchor.includes('center')) {
    drawX = x + (w - drawW) / 2;
  }

  let drawY = y;
  if (anchor.includes('bottom')) {
    drawY = y + h - drawH;
  } else if (anchor.includes('middle')) {
    drawY = y + (h - drawH) / 2;
  }

  ctx.drawImage(img, drawX, drawY, drawW, drawH);
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
  placeholderAspectRatio = '3:2',
}: {
  config: WatermarkConfigV3;
  image: HTMLImageElement | null;
  imageSize?: { width: number; height: number } | null;
  placeholderAspectRatio?: PreviewAspectRatio;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [logoImages, setLogoImages] = useState<Map<string, HTMLImageElement>>(new Map());

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 确定图片尺寸（无图时使用所选预览比例）
    let imgW: number, imgH: number;
    if (image) {
      imgW = image.naturalWidth;
      imgH = image.naturalHeight;
    } else if (imageSize) {
      imgW = imageSize.width;
      imgH = imageSize.height;
    } else {
      const ratio = PREVIEW_ASPECT_RATIOS.find(r => r.id === placeholderAspectRatio) ?? PREVIEW_ASPECT_RATIOS[0];
      imgW = ratio.width;
      imgH = ratio.height;
    }

    // 计算布局
    const layout = computeLayout(config, imgW, imgH);

    // 容器显示尺寸
    const rect = container.getBoundingClientRect();
    const containerW = rect.width;
    const containerH = rect.height;

    // 按 contain 模式在容器内计算缩放后的显示尺寸
    const layoutRatio = layout.canvas.w / layout.canvas.h;
    const containerRatio = containerW / containerH;
    let displayW: number;
    let displayH: number;
    if (containerRatio > layoutRatio) {
      // 容器更宽，按高度缩放
      displayH = containerH;
      displayW = containerH * layoutRatio;
    } else {
      // 容器更高或相等，按宽度缩放
      displayW = containerW;
      displayH = containerW / layoutRatio;
    }

    // 设置 canvas 显示尺寸为 contain 计算结果，居中由外层 flex 保证
    canvas.style.width = `${displayW}px`;
    canvas.style.height = `${displayH}px`;

    // DPR 处理：逻辑分辨率固定为布局尺寸，保证绘制质量
    const dpr = window.devicePixelRatio || 1;
    canvas.width = layout.canvas.w * dpr;
    canvas.height = layout.canvas.h * dpr;
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

    // 收集需要加载的 logo 路径
    const logoPaths: string[] = [];
    for (const el of layout.elements) {
      if (el.type === 'logo' && 'path' in el.content) {
        const path = el.content.path || `${API_BASE}/api/logos/default.png`;
        if (!logoImages.has(path)) {
          logoPaths.push(path);
        }
      }
    }

    // 绘制（可能尚未加载 logo，先占位）
    renderCanvas(ctx, layout, image, logoImages, config);

    // 恢复 clip
    if (config.canvas.border_radius > 0) {
      ctx.restore();
    }

    // 异步加载缺失的 logo 并重新渲染
    if (logoPaths.length > 0) {
      Promise.all(logoPaths.map(p => loadLogo(p).then(img => ({ p, img }))))
        .then(results => {
          setLogoImages(prev => {
            const next = new Map(prev);
            for (const { p, img } of results) {
              next.set(p, img);
            }
            return next;
          });
        })
        .catch(() => {
          // 失败时保持占位状态
        });
    }
  }, [config, image, imageSize, placeholderAspectRatio, logoImages]);

  return (
    <div ref={containerRef} className="canvas-scaler">
      <canvas ref={canvasRef} />
    </div>
  );
}
