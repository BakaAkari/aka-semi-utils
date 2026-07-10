import { useEffect, useRef } from 'react';
import type { WatermarkConfig, CornerConfig, FieldChip, FieldId } from './watermarkConfig';
import { PLACEHOLDER_EXIF, fieldOptions } from './watermarkConfig';

type SideData = { key: string; config: CornerConfig; x: number; y: number };

// ---------- helpers ----------

function resolveText(chip: FieldChip, customText: string): string {
  if (chip.field_id === 'custom_text') return chip.custom_text || customText || '';
  if (chip.field_id === 'empty') return '';
  return PLACEHOLDER_EXIF[chip.field_id as keyof typeof PLACEHOLDER_EXIF] ?? '';
}

function chipLabel(fieldId: FieldId): string {
  return fieldOptions.find(o => o.id === fieldId)?.label ?? fieldId;
}

function hexToRgba(hex: string, alpha = 1): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function parseColor(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [
    parseInt(h.substring(0, 2), 16),
    parseInt(h.substring(2, 4), 16),
    parseInt(h.substring(4, 6), 16),
  ];
}

// ---------- component ----------

export function WatermarkCanvas({
  config,
  image,
}: {
  config: WatermarkConfig;
  image: HTMLImageElement | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const adv = config.advanced;
    const dpr = window.devicePixelRatio || 1;

    // Determine image area size
    const DEFAULT_W = 900;
    const DEFAULT_H = 1200;
    let imgW: number, imgH: number;
    if (image) {
      imgW = image.naturalWidth;
      imgH = image.naturalHeight;
    } else if (adv.ratio_enabled) {
      const [rw, rh] = adv.ratio.split(':').map(Number);
      const base = 900;
      const ratioVal = rw / rh;
      imgW = ratioVal >= 1 ? base : Math.round(base * ratioVal);
      imgH = ratioVal >= 1 ? Math.round(base / ratioVal) : base;
    } else {
      imgW = DEFAULT_W;
      imgH = DEFAULT_H;
    }

    const leftM = adv.left_margin;
    const rightM = adv.right_margin;
    const topM = adv.top_margin;
    const bottomM = adv.bottom_margin || Math.max(60, Math.round(Math.min(imgW, imgH) * 0.12));

    const canvasW = imgW + leftM + rightM;
    const canvasH = imgH + topM + bottomM;

    canvas.width = canvasW * dpr;
    canvas.height = canvasH * dpr;
    canvas.style.width = `${canvasW}px`;
    canvas.style.height = `${canvasH}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // --- background ---
    const marginColor = adv.margin_color || '#FFFFFF';
    ctx.fillStyle = marginColor;
    ctx.fillRect(0, 0, canvasW, canvasH);

    // --- rounded corners (applied as clip region on the whole canvas) ---
    if (adv.border_radius > 0) {
      ctx.save();
      const r = adv.border_radius;
      ctx.beginPath();
      ctx.moveTo(r, 0);
      ctx.lineTo(canvasW - r, 0);
      ctx.quadraticCurveTo(canvasW, 0, canvasW, r);
      ctx.lineTo(canvasW, canvasH - r);
      ctx.quadraticCurveTo(canvasW, canvasH, canvasW - r, canvasH);
      ctx.lineTo(r, canvasH);
      ctx.quadraticCurveTo(0, canvasH, 0, canvasH - r);
      ctx.lineTo(0, r);
      ctx.quadraticCurveTo(0, 0, r, 0);
      ctx.closePath();
      ctx.clip();

      // Re-fill after clip
      ctx.fillStyle = marginColor;
      ctx.fillRect(0, 0, canvasW, canvasH);
    }

    // --- shadow ---
    if (adv.shadow_radius > 0) {
      const [sr, sg, sb] = parseColor(adv.shadow_color || '#000000');
      ctx.save();
      ctx.shadowColor = `rgba(${sr},${sg},${sb},0.5)`;
      ctx.shadowBlur = adv.shadow_radius;
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 0;
      // Draw a transparent rect to cast the shadow of the entire shape
      ctx.fillStyle = marginColor;
      ctx.fillRect(0, 0, canvasW, canvasH);
      ctx.restore();
    }

    // --- image / placeholder ---
    if (image) {
      ctx.drawImage(image, leftM, topM, imgW, imgH);
    } else {
      // Placeholder "photo" area — subtle gradient
      const grad = ctx.createLinearGradient(leftM, topM, leftM + imgW, topM + imgH);
      grad.addColorStop(0, '#3a3832');
      grad.addColorStop(0.5, '#2a2824');
      grad.addColorStop(1, '#1a1814');
      ctx.fillStyle = grad;
      ctx.fillRect(leftM, topM, imgW, imgH);

      // Optional: diagonal lines or subtle center icon
      ctx.strokeStyle = 'rgba(138,122,92,0.15)';
      ctx.lineWidth = 1;
      for (let i = -canvasW; i < canvasW + canvasH; i += 60) {
        ctx.beginPath();
        ctx.moveTo(leftM + i, topM);
        ctx.lineTo(leftM + i - canvasH, topM + imgH);
        ctx.stroke();
      }
    }

    // --- watermark texts ---
    const layoutMode = config.layout_mode ?? 'corners';
    const globalFont = adv.global_font ?? 'NotoSansCJKsc-Bold.otf';
    const fontFamily = globalFont.includes('Bold')
      ? '"Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
      : '"Noto Sans CJK SC", "Microsoft YaHei", sans-serif';

    if (layoutMode === 'sides') {
      drawSides(ctx, config, canvasW, canvasH, leftM, rightM, topM, imgH, bottomM, fontFamily);
    } else {
      drawCorners(ctx, config, canvasW, canvasH, leftM, rightM, topM, imgH, bottomM, fontFamily);
    }

    // --- restore clip ---
    if (adv.border_radius > 0) ctx.restore();
  }, [config, image]);

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

// ======================== Corner drawing ========================

function drawCorners(
  ctx: CanvasRenderingContext2D,
  config: WatermarkConfig,
  cw: number, ch: number,
  leftM: number, rightM: number, topM: number,
  imgH: number, bottomM: number, fontFamily: string,
) {
  const adv = config.advanced;
  const spacing = Math.round(cw * 0.02);

  const corners = [
    { key: 'left_top', attr: config.corners.left_top, x: leftM + spacing },
    { key: 'left_bottom', attr: config.corners.left_bottom, x: leftM + spacing },
    { key: 'right_top', attr: config.corners.right_top, x: 0 }, // calculated below
    { key: 'right_bottom', attr: config.corners.right_bottom, x: 0 },
  ];

  // calculate font sizes (matching PIL: height = bottom_margin * ratio / 0.12)
  const fontSizes: Record<string, number> = {};
  for (const c of corners) {
    const ratio = c.attr.font_size_ratio || adv.corner_text_ratio || 0.03;
    fontSizes[c.key] = Math.max(8, Math.round(bottomM * ratio / 0.12));
  }

  // Measure text widths
  const textBlocks: Record<string, { lines: string[]; colors: string[]; w: number }> = {};
  for (const c of corners) {
    const chips = c.attr.chips.filter(ch => ch.field_id !== 'empty');
    if (chips.length === 0) { textBlocks[c.key] = { lines: [], colors: [], w: 0 }; continue; }

    const fz = fontSizes[c.key];
    ctx.font = `700 ${fz}px ${fontFamily}`;

    // Build text line: chips joined by separator
    const sep = c.attr.separator || '    ';
    const texts: string[] = [];
    const colors: string[] = [];
    for (const chip of chips) {
      const t = resolveText(chip, '');
      const color = adv.global_color || '#242424';
      texts.push(t);
      colors.push(color);
    }
    const line = texts.join(sep);
    const metrics = ctx.measureText(line);

    textBlocks[c.key] = { lines: [line], colors: [colors[0]], w: metrics.width };
  }

  // Calculate Y positions — matching PIL WatermarkFilter._compute_text_layout
  // Elements stacked: left_top above left_bottom, right_top above right_bottom
  const ltH = textBlocks.left_top.lines.length > 0 ? fontSizes.left_top : 0;
  const lbH = textBlocks.left_bottom.lines.length > 0 ? fontSizes.left_bottom : 0;
  const rtH = textBlocks.right_top.lines.length > 0 ? fontSizes.right_top : 0;
  const rbH = textBlocks.right_bottom.lines.length > 0 ? fontSizes.right_bottom : 0;

  const lStackH = ltH + lbH + (ltH && lbH ? 4 : 0);
  const rStackH = rtH + rbH + (rtH && rbH ? 4 : 0);
  const elemH = Math.max(lStackH, rStackH);
  const elemMargin = Math.round((bottomM - elemH) / 2);
  const footerTop = topM + imgH;

  // Left: stacked from bottom of footer
  const lbY = footerTop + elemMargin + (lbH || 0);
  const ltY = lbY - (lbH ? lbH + 4 : 0) - ltH;

  // Right: aligned to bottom of their stack, same as PIL
  const rbY = footerTop + elemMargin + (rbH || 0);
  const rtY = rbY - (rbH ? rbH + 4 : 0) - rtH;

  // Right X
  const rightX = cw - rightM - spacing;

  // Draw
  const color = adv.global_color || '#242424';
  for (const c of corners) {
    const block = textBlocks[c.key];
    if (block.lines.length === 0) continue;

    const fz = fontSizes[c.key];
    ctx.font = `700 ${fz}px ${fontFamily}`;
    ctx.fillStyle = color;

    let x: number, y: number;
    if (c.key === 'left_top') { x = c.x; y = ltY; }
    else if (c.key === 'left_bottom') { x = c.x; y = lbY - fz; }
    else if (c.key === 'right_top') { x = rightX - block.w; y = rtY; }
    else { x = rightX - block.w; y = rbY - fz; }

    ctx.fillText(block.lines[0], x, y + fz * 0.8);
  }
}

// ======================== Sides drawing ========================

function drawSides(
  ctx: CanvasRenderingContext2D,
  config: WatermarkConfig,
  cw: number, ch: number,
  leftM: number, rightM: number, topM: number,
  imgH: number, bottomM: number, fontFamily: string,
) {
  const adv = config.advanced;
  const spacing = Math.round(cw * 0.02);
  const sides = [
    { key: 'left', config: config.sides.left, alignX: leftM + spacing },
    { key: 'right', config: config.sides.right, alignX: cw - rightM - spacing },
  ];

  for (const side of sides) {
    const chips = side.config.chips.filter(ch => ch.field_id !== 'empty');
    if (chips.length === 0) continue;

    const ratio = side.config.font_size_ratio || adv.corner_text_ratio || 0.04;
    const fz = Math.max(8, Math.round(bottomM * ratio / 0.12));
    ctx.font = `700 ${fz}px ${fontFamily}`;
    const color = adv.global_color || '#242424';

    const lines: { text: string; w: number }[] = [];
    for (const chip of chips) {
      const t = resolveText(chip, '');
      lines.push({ text: t, w: ctx.measureText(t).width });
    }

    const gap = Math.max(2, Math.round(fz / 6));
    const totalH = lines.length * fz + (lines.length - 1) * gap;
    const startY = topM + Math.round((imgH - totalH) / 2);

    ctx.fillStyle = color;
    for (let i = 0; i < lines.length; i++) {
      const y = startY + i * (fz + gap);
      const x = side.alignX;
      const textX = side.key === 'right' ? x - lines[i].w : x;
      ctx.fillText(lines[i].text, textX, y + fz * 0.8);
    }
  }
}
