/**
 * V3 WatermarkConfig 类型定义
 *
 * 与 V2 的区别：
 * - 不再区分 corners/sides，改用 Region 列表
 * - 所有尺寸/位置使用声明式配置
 * - 支持 size_reference 控制字号基准
 */

export type FieldId =
  | 'camera_model'
  | 'lens_model'
  | 'focal_length'
  | 'aperture'
  | 'shutter'
  | 'iso'
  | 'datetime'
  | 'make'
  | 'artist'
  | 'gps'
  | 'custom_text'
  | 'empty';

/** Placeholder values for Canvas skeleton preview when no image EXIF is available. */
export const PLACEHOLDER_EXIF: Record<FieldId, string> = {
  camera_model: 'GFX100S II',
  lens_model: 'GF80mmF1.7 R WR',
  focal_length: '80mm',
  aperture: 'F1.7',
  shutter: '1/250s',
  iso: 'ISO400',
  datetime: '2026.07.10',
  make: 'FUJIFILM',
  artist: 'Baka Akari',
  gps: 'Shanghai',
  custom_text: 'AKARI PHOTO',
  empty: '',
};

export type FieldChip = {
  field_id: FieldId;
  custom_text?: string;
};

export interface TextContent {
  chips: FieldChip[];
  separator: string;
}

export interface LogoContent {
  path: string;
  color: string;
  /** logo 高度占所在区域高度的比例，默认 0.6，用于随底栏等水印条高度缩放。 */
  size_ratio?: number;
}

export interface SignatureContent {
  path: string;
  invert_mono: boolean;
  size_ratio: number;
}

export type Content = TextContent | LogoContent | SignatureContent;

export type SizeReference = 'region_height' | 'short_edge' | 'long_edge';
export type Anchor =
  | 'top-left' | 'top-center' | 'top-right'
  | 'middle-left' | 'middle-center' | 'middle-right'
  | 'bottom-left' | 'bottom-center' | 'bottom-right';
export type FontFamily = 'NotoSansCJKsc-Regular.otf' | 'NotoSansCJKsc-Bold.otf';

export interface StyleConfig {
  font_size: number | null;
  font_size_ratio: number | null;
  size_reference: SizeReference;
  color: string;
  font_family: FontFamily;
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
  slots?: Record<string, SlotConfig>;
  edge?: 'left' | 'right';
  width?: { mode: 'pixel' | 'short_edge_ratio'; value: number };
  alignment?: 'start' | 'center' | 'end';
  anchor?: Anchor;
  offset_x?: number;
  offset_y?: number;
  offset_unit?: 'pixel' | 'short_edge_ratio';
  /** footer-bar 高度占图片短边的比例；由布局引擎解析为实际像素高度。 */
  height?: number;
}

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

export interface WatermarkConfigV3 {
  canvas: CanvasConfig;
  regions: RegionConfig[];
  defaults: StyleConfig;
  custom_text?: string;
  /** 追踪当前应用的预设 id，用于主界面显示和重置。 */
  preset_id?: string;
  /** 底部控制条模式：双排/单排。 */
  footer_mode?: FooterMode;
  /** Logo 在底栏的位置：左/中/右。 */
  logo_position?: LogoPosition;
}

export const fieldOptionsV3: { id: FieldId; label: string }[] = [
  { id: 'camera_model', label: '相机型号' },
  { id: 'lens_model', label: '镜头型号' },
  { id: 'focal_length', label: '焦距' },
  { id: 'aperture', label: '光圈' },
  { id: 'shutter', label: '快门' },
  { id: 'iso', label: 'ISO' },
  { id: 'datetime', label: '拍摄日期' },
  { id: 'make', label: '厂商品牌' },
  { id: 'artist', label: '作者' },
  { id: 'gps', label: '地理位置' },
  { id: 'custom_text', label: '自定义文本' },
];

// 主界面参数化控制类型
export type PresetSize = 'small' | 'medium' | 'large';
export type PresetColor = 'black' | 'white' | 'warm-gray' | 'auto';
export type PresetDensity = 'compact' | 'standard' | 'loose';
export type FooterMode = 'dual-row' | 'single-row';
export type LogoPosition = 'left' | 'center' | 'right';

export type PreviewAspectRatio = '3:2' | '4:3' | '16:9' | '1:1' | '2:3';

export interface AspectRatioOption {
  id: PreviewAspectRatio;
  label: string;
  width: number;
  height: number;
}

export const PREVIEW_ASPECT_RATIOS: AspectRatioOption[] = [
  { id: '3:2', label: '3:2', width: 900, height: 600 },
  { id: '4:3', label: '4:3', width: 800, height: 600 },
  { id: '16:9', label: '16:9', width: 960, height: 540 },
  { id: '1:1', label: '1:1', width: 600, height: 600 },
  { id: '2:3', label: '2:3', width: 600, height: 900 },
];

export const FOOTER_MODE_LABELS: Record<FooterMode, string> = {
  'dual-row': '左右双排',
  'single-row': '左右单排',
};

export const LOGO_POSITION_LABELS: Record<LogoPosition, string> = {
  left: '左',
  center: '中',
  right: '右',
};

export interface MainControlConfig {
  size: PresetSize;
  color: PresetColor;
  density: PresetDensity;
  // 底部控制条模式
  footer_mode: FooterMode;
  // Logo 位置
  logo_position: LogoPosition;
  // 各栏内容（字段 chips）
  top_left: FieldChip[];
  bottom_left: FieldChip[];
  top_right: FieldChip[];
  bottom_right: FieldChip[];
  left_row: FieldChip[];
  right_row: FieldChip[];
  // 自定义
  custom_text: string;
  // 资源
  logo_path: string;
  signature_path: string;
}

export interface WatermarkPresetV3 {
  id: string;
  name: string;
  description: string;
  // 基于中等大小/黑色/标准密度的基准配置
  base: WatermarkConfigV3;
  // 三档大小的参数变体
  sizeVariants: Record<PresetSize, SizeVariant>;
  // 默认主界面控制
  mainControls: MainControlConfig;
}

/** 从字段 id 获取显示标签。 */
export function getFieldLabel(fieldId: FieldId): string {
  const option = fieldOptionsV3.find((o) => o.id === fieldId);
  return option?.label ?? fieldId;
}

/** 快速创建一个字段 chip。 */
export function fieldChip(fieldId: FieldId, customText?: string): FieldChip {
  return customText ? { field_id: fieldId, custom_text: customText } : { field_id: fieldId };
}

/** 将一个 chip 转换为可保存的字符串 key。 */
export function chipKey(chip: FieldChip): string {
  return chip.field_id === 'custom_text' && chip.custom_text
    ? `custom_text:${chip.custom_text}`
    : chip.field_id;
}

export interface SizeVariant {
  fontSizeMultiplier: number;
  footerHeightMultiplier: number;
  logoSizeMultiplier: number;
  signatureSizeMultiplier: number;
  densityMarginMultiplier: number;
}

export const defaultSizeVariant: SizeVariant = {
  fontSizeMultiplier: 1.0,
  footerHeightMultiplier: 0.10,
  logoSizeMultiplier: 1.0,
  signatureSizeMultiplier: 1.0,
  densityMarginMultiplier: 1.0,
};

export const sizeVariants: Record<PresetSize, SizeVariant> = {
  small: {
    fontSizeMultiplier: 0.85,
    footerHeightMultiplier: 0.08,
    logoSizeMultiplier: 0.85,
    signatureSizeMultiplier: 0.85,
    densityMarginMultiplier: 0.75,
  },
  medium: defaultSizeVariant,
  large: {
    fontSizeMultiplier: 1.25,
    footerHeightMultiplier: 0.13,
    logoSizeMultiplier: 1.25,
    signatureSizeMultiplier: 1.25,
    densityMarginMultiplier: 1.3,
  },
};

export const colorThemes: Record<PresetColor, { text: string; logo: string; background: string; }> = {
  black: { text: '#222222', logo: '#D8D8D6', background: '#FFFFFF' },
  white: { text: '#F5F5F5', logo: '#FFFFFF', background: '#1A1A1A' },
  'warm-gray': { text: '#3A3532', logo: '#B0A89A', background: '#EDEAE6' },
  auto: { text: '#222222', logo: '#D8D8D6', background: '#FFFFFF' },
};

export const densityVariants: Record<PresetDensity, number> = {
  compact: 0.08,
  standard: 0.10,
  loose: 0.13,
};

// ── 预设配置 ────────────────────────────────────────────

export const defaultStyle: StyleConfig = {
  font_size: null,
  font_size_ratio: 0.35,
  size_reference: 'region_height',
  color: '#222222',
  font_family: 'NotoSansCJKsc-Bold.otf',
  bold: true,
  line_height: 1.2,
};

export const presetDefaultBaseV3: WatermarkConfigV3 = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 0, left: 0 },
    background: '#FFFFFF',
    border_radius: 0,
  },
  defaults: defaultStyle,
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      // height 由 applyMainControls 统一计算，不在预设中硬编码
      slots: {
        'left-top': {
          enabled: true,
          content: {
            chips: [{ field_id: 'make' }, { field_id: 'camera_model' }],
            separator: ' ',
          },
          style: { ...defaultStyle, font_size_ratio: 0.45, color: '#222222' },
        },
        'left-bottom': {
          enabled: true,
          content: {
            chips: [
              { field_id: 'focal_length' },
              { field_id: 'aperture' },
              { field_id: 'shutter' },
              { field_id: 'iso' },
            ],
            separator: ' ',
          },
          style: { ...defaultStyle, font_size_ratio: 0.35, color: '#222222' },
        },
        'right-top': { enabled: false, content: null, style: null },
        'right-bottom': { enabled: false, content: null, style: null },
        'center': { enabled: false, content: null, style: null },
        'left-logo': { enabled: false, content: null, style: null },
        'right-logo': {
          enabled: true,
          content: { path: '', color: '#D8D8D6', size_ratio: 0.6 },
          style: null,
        },
      },
    },
  ],
};

export const presetDefaultV3: WatermarkConfigV3 = presetDefaultBaseV3;

export const presetMinimalBaseV3: WatermarkConfigV3 = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 0, left: 0 },
    background: '#FFFFFF',
    border_radius: 0,
  },
  defaults: defaultStyle,
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      // height 由 applyMainControls 统一计算，不在预设中硬编码
      slots: {
        'left-top': { enabled: false, content: null, style: null },
        'left-bottom': { enabled: false, content: null, style: null },
        'right-top': { enabled: false, content: null, style: null },
        'right-bottom': {
          enabled: true,
          content: {
            chips: [
              { field_id: 'focal_length' },
              { field_id: 'aperture' },
              { field_id: 'shutter' },
              { field_id: 'iso' },
            ],
            separator: ' ',
          },
          style: { ...defaultStyle, font_size_ratio: 0.32, color: '#2C2C2C' },
        },
        'center': { enabled: false, content: null, style: null },
        'left-logo': { enabled: false, content: null, style: null },
        'right-logo': { enabled: false, content: null, style: null },
      },
    },
  ],
};

export const presetMinimalV3: WatermarkConfigV3 = presetMinimalBaseV3;

export const presetSoftCardBaseV3: WatermarkConfigV3 = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 0, left: 0 },
    background: '#FFFFFF',
    border_radius: 24,
  },
  defaults: defaultStyle,
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      // height 由 applyMainControls 统一计算，不在预设中硬编码
      slots: {
        'left-top': {
          enabled: true,
          content: {
            chips: [{ field_id: 'custom_text', custom_text: 'AKARI PHOTO' }],
            separator: ' ',
          },
          style: { ...defaultStyle, font_size_ratio: 0.40, color: '#242424' },
        },
        'left-bottom': {
          enabled: true,
          content: {
            chips: [{ field_id: 'datetime' }],
            separator: ' ',
          },
          style: { ...defaultStyle, font_size_ratio: 0.30, color: '#242424' },
        },
        'right-top': {
          enabled: true,
          content: {
            chips: [{ field_id: 'camera_model' }],
            separator: ' ',
          },
          style: { ...defaultStyle, font_size_ratio: 0.34, color: '#242424' },
        },
        'right-bottom': {
          enabled: true,
          content: {
            chips: [
              { field_id: 'focal_length' },
              { field_id: 'aperture' },
              { field_id: 'iso' },
            ],
            separator: ' ',
          },
          style: { ...defaultStyle, font_size_ratio: 0.30, color: '#242424' },
        },
        'center': { enabled: false, content: null, style: null },
        'left-logo': { enabled: false, content: null, style: null },
        'right-logo': {
          enabled: true,
          content: { path: '', color: '#D8D8D6', size_ratio: 0.6 },
          style: null,
        },
      },
    },
  ],
};

export const presetSoftCardV3: WatermarkConfigV3 = presetSoftCardBaseV3;

export const presetSidesBaseV3: WatermarkConfigV3 = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 0, left: 0 },
    background: '#FFFFFF',
    border_radius: 0,
  },
  defaults: defaultStyle,
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      // height 由 applyMainControls 统一计算，不在预设中硬编码
      slots: {
        'left-top': { enabled: false, content: null, style: null },
        'left-bottom': { enabled: false, content: null, style: null },
        'right-top': { enabled: false, content: null, style: null },
        'right-bottom': { enabled: false, content: null, style: null },
        'center': { enabled: false, content: null, style: null },
        'left-logo': { enabled: false, content: null, style: null },
        'right-logo': { enabled: false, content: null, style: null },
      },
    },
    {
      id: 'side-left',
      type: 'side-edge',
      enabled: true,
      edge: 'left',
      alignment: 'start',
      slots: {
        line1: {
          enabled: true,
          content: {
            chips: [
              { field_id: 'make' },
              { field_id: 'camera_model' },
              { field_id: 'focal_length' },
              { field_id: 'aperture' },
              { field_id: 'shutter' },
              { field_id: 'iso' },
            ],
            separator: ' / ',
          },
          style: { ...defaultStyle, font_size_ratio: 0.05, size_reference: 'short_edge' },
        },
      },
    },
  ],
};

export const presetSidesV3: WatermarkConfigV3 = presetSidesBaseV3;

export function createDefaultWatermarkConfigV3(): WatermarkConfigV3 {
  return applyMainControls(structuredClone(presetDefaultBaseV3), defaultMainControls);
}

// 主界面控制的缺省值
export const defaultMainControls: MainControlConfig = {
  size: 'medium',
  color: 'black',
  density: 'standard',
  footer_mode: 'dual-row',
  logo_position: 'right',
  top_left: [{ field_id: 'make' }, { field_id: 'camera_model' }],
  bottom_left: [{ field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'shutter' }, { field_id: 'iso' }],
  top_right: [],
  bottom_right: [],
  left_row: [{ field_id: 'make' }, { field_id: 'camera_model' }, { field_id: 'focal_length' }, { field_id: 'aperture' }],
  right_row: [{ field_id: 'shutter' }, { field_id: 'iso' }],
  custom_text: '',
  logo_path: '',
  signature_path: '',
};

/**
 * 将主界面控制应用到 WatermarkConfigV3，生成新的配置。
 */
export function applyMainControls(
  base: WatermarkConfigV3,
  controls: MainControlConfig,
): WatermarkConfigV3 {
  const config = structuredClone(base);
  const theme = colorThemes[controls.color] ?? colorThemes.black;
  const size = sizeVariants[controls.size] ?? sizeVariants.medium;
  const densityHeight = densityVariants[controls.density] ?? densityVariants.standard;

  // 应用颜色
  config.canvas.background = theme.background;
  config.defaults.color = theme.text;

  // 应用大小：字号比例
  const defaults = config.defaults;
  const baseFontRatio = defaults.font_size_ratio ?? 0.35;
  defaults.font_size_ratio = Math.min(0.5, baseFontRatio * (size.fontSizeMultiplier ?? 1.0));

  // 应用颜色到已有 slot 样式
  for (const region of config.regions) {
    if (!region.slots) continue;
    for (const slot of Object.values(region.slots)) {
      if (slot.style) {
        slot.style.color = theme.text;
      }
      if (slot.content && 'color' in slot.content) {
        slot.content.color = theme.logo;
      }
    }
  }

  // 应用密度：将底栏高度以比例形式写入 footer-bar region，由布局引擎按实际短边计算
  let footerRegion = config.regions.find(r => r.type === 'footer-bar' && r.enabled);
  if (footerRegion) {
    // 底栏高度比例 = 密度系数 * 大小系数 / 密度边距系数
    footerRegion.height = densityHeight * (size.footerHeightMultiplier ?? 0.10) / (size.densityMarginMultiplier ?? 1.0);
  }

  // 自定义文本
  config.custom_text = controls.custom_text;

  // 保存主界面模式到配置
  config.footer_mode = controls.footer_mode;
  config.logo_position = controls.logo_position;

  // 找到或创建 footer 区域
  if (!footerRegion) {
    footerRegion = {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      slots: {},
    };
    config.regions.push(footerRegion);
  }
  if (!footerRegion.slots) {
    footerRegion.slots = {};
  }
  const slots = footerRegion.slots;

  // 根据 footer_mode 填充 slots
  const slotRows: [string, FieldChip[]][] =
    controls.footer_mode === 'dual-row'
      ? [
          ['left-top', controls.top_left],
          ['left-bottom', controls.bottom_left],
          ['right-top', controls.top_right],
          ['right-bottom', controls.bottom_right],
        ]
      : [
          ['left-top', controls.left_row],
          ['right-top', controls.right_row],
        ];

  for (const [slotId, chips] of slotRows) {
    slots[slotId] = {
      enabled: chips.length > 0,
      content: chips.length > 0 ? { chips, separator: ' ' } : null,
      style: chips.length > 0 ? { ...config.defaults, font_size_ratio: 0.35 } : null,
    };
  }

  // 移除不用的底栏文本 slot
  const allFooterSlots = ['left-top', 'left-bottom', 'right-top', 'right-bottom', 'center'];
  for (const slotId of allFooterSlots) {
    if (!slotRows.some(([id]) => id === slotId)) {
      slots[slotId] = { enabled: false, content: null, style: null };
    }
  }

  // 应用 Logo 位置
  const logoPath = controls.logo_path || '';
  slots['left-logo'] = { enabled: false, content: null, style: null };
  slots['right-logo'] = { enabled: false, content: null, style: null };
  slots['center'] = { enabled: false, content: null, style: null };

  if (controls.logo_position === 'left') {
    slots['left-logo'] = {
      enabled: true,
      content: { path: logoPath, color: theme.logo, size_ratio: 0.6 * (size.logoSizeMultiplier ?? 1.0) },
      style: null,
    };
  } else if (controls.logo_position === 'right') {
    slots['right-logo'] = {
      enabled: true,
      content: { path: logoPath, color: theme.logo, size_ratio: 0.6 * (size.logoSizeMultiplier ?? 1.0) },
      style: null,
    };
  } else if (controls.logo_position === 'center') {
    slots['center'] = {
      enabled: true,
      content: { path: logoPath, color: theme.logo, size_ratio: 0.6 * (size.logoSizeMultiplier ?? 1.0) },
      style: null,
    };
  }

  // 应用自定义 Logo：更新已启用 logo slot 的 path，保留 size_ratio 不变
  if (controls.logo_path) {
    for (const slotId of ['left-logo', 'right-logo', 'center'] as const) {
      const slot = slots[slotId];
      if (slot?.enabled && slot.content && 'path' in slot.content) {
        slot.content.path = controls.logo_path;
      }
    }
  }

  // 应用签名：在不存在 free region 时创建一个
  if (controls.signature_path) {
    let freeRegion = config.regions.find(r => r.type === 'free');
    if (!freeRegion) {
      freeRegion = {
        id: 'signature',
        type: 'free',
        enabled: true,
        anchor: 'bottom-right',
        offset_x: 0.05,
        offset_y: 0.05,
        offset_unit: 'short_edge_ratio',
        slots: { sig1: { enabled: true, content: { path: controls.signature_path, invert_mono: false, size_ratio: 0.20 * size.signatureSizeMultiplier }, style: null } },
      };
      config.regions.push(freeRegion);
    } else {
      freeRegion.enabled = true;
      if (!freeRegion.slots) freeRegion.slots = {};
      const sigSlot = freeRegion.slots.sig1 ?? { enabled: true, content: { path: '', invert_mono: false, size_ratio: 0.20 }, style: null };
      sigSlot.enabled = true;
      if (sigSlot.content && 'size_ratio' in sigSlot.content) {
        sigSlot.content.size_ratio = 0.20 * size.signatureSizeMultiplier;
      }
      sigSlot.content = { path: controls.signature_path, invert_mono: false, size_ratio: 0.20 * size.signatureSizeMultiplier };
      freeRegion.slots.sig1 = sigSlot;
    }
  }

  return config;
}

// 帮助函数：从 footer slot 提取 chips
function extractFooterSlotChips(config: WatermarkConfigV3, slotId: string): FieldChip[] {
  const footer = config.regions.find(r => r.type === 'footer-bar' && r.enabled);
  const slot = footer?.slots?.[slotId];
  if (slot?.enabled && slot.content && 'chips' in slot.content) {
    return [...slot.content.chips];
  }
  return [];
}

/**
 * 从一个 WatermarkConfigV3 中推断当前主界面控制状态。
 */
export function inferMainControls(config: WatermarkConfigV3): MainControlConfig {
  const controls = structuredClone(defaultMainControls);

  // 直接使用保存在配置中的模式
  if (config.footer_mode) {
    controls.footer_mode = config.footer_mode;
  }
  if (config.logo_position) {
    controls.logo_position = config.logo_position;
  }

  // 从 footer slots 提取各栏内容
  controls.top_left = extractFooterSlotChips(config, 'left-top');
  controls.bottom_left = extractFooterSlotChips(config, 'left-bottom');
  controls.top_right = extractFooterSlotChips(config, 'right-top');
  controls.bottom_right = extractFooterSlotChips(config, 'right-bottom');
  // 单排时，左排 = left-top，右排 = right-top
  controls.left_row = extractFooterSlotChips(config, 'left-top');
  controls.right_row = extractFooterSlotChips(config, 'right-top');

  controls.custom_text = config.custom_text ?? '';

  // Logo 路径和位置
  for (const region of config.regions) {
    if (region.type !== 'footer-bar') continue;
    if (region.slots?.['left-logo']?.enabled) {
      controls.logo_position = 'left';
      const content = region.slots['left-logo'].content;
      if (content && 'path' in content) controls.logo_path = content.path;
    } else if (region.slots?.['right-logo']?.enabled) {
      controls.logo_position = 'right';
      const content = region.slots['right-logo'].content;
      if (content && 'path' in content) controls.logo_path = content.path;
    } else if (region.slots?.['center']?.enabled) {
      const content = region.slots['center'].content;
      if (content && 'path' in content) {
        controls.logo_position = 'center';
        controls.logo_path = content.path;
      }
    }
  }

  // 签名路径
  const freeRegion = config.regions.find(r => r.type === 'free');
  if (freeRegion?.slots) {
    for (const slot of Object.values(freeRegion.slots)) {
      if (slot.enabled && slot.content && 'size_ratio' in slot.content) {
        controls.signature_path = slot.content.path;
      }
    }
  }

  return controls;
}

/**
 * 获取预设的主界面控制。
 * 如果预设定义了 mainControls。
 */
export function getPresetMainControls(preset: WatermarkPresetV3): MainControlConfig {
  return preset.mainControls ? structuredClone(preset.mainControls) : structuredClone(defaultMainControls);
}

/**
 * 获取预设在当前主界面控制下的完整 WatermarkConfigV3。
 */
export function getPresetConfig(preset: WatermarkPresetV3, controls?: Partial<MainControlConfig>): WatermarkConfigV3 {
  const merged = { ...getPresetMainControls(preset), ...controls };
  return applyMainControls(preset.base, merged);
}
