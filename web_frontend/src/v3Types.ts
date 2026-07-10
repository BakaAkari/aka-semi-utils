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

export interface MainControlConfig {
  size: PresetSize;
  color: PresetColor;
  density: PresetDensity;
  // 内容开关
  show_camera: boolean;
  show_lens: boolean;
  show_focal: boolean;
  show_aperture: boolean;
  show_shutter: boolean;
  show_iso: boolean;
  show_datetime: boolean;
  show_artist: boolean;
  show_gps: boolean;
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
    margins: { top: 0, right: 0, bottom: 80, left: 0 },
    background: '#FFFFFF',
    border_radius: 0,
  },
  defaults: defaultStyle,
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
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
          content: { path: '', color: '#D8D8D6' },
          style: null,
        },
      },
    },
  ],
};

export const presetDefaultV3: WatermarkConfigV3 = presetDefaultBaseV3;

export const presetMinimalBaseV3: WatermarkConfigV3 = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 90, left: 0 },
    background: '#FFFFFF',
    border_radius: 0,
  },
  defaults: defaultStyle,
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
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
    margins: { top: 0, right: 0, bottom: 150, left: 0 },
    background: '#FFFFFF',
    border_radius: 24,
  },
  defaults: defaultStyle,
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
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
          content: { path: '', color: '#D8D8D6' },
          style: null,
        },
      },
    },
  ],
};

export const presetSoftCardV3: WatermarkConfigV3 = presetSoftCardBaseV3;

export const presetSidesBaseV3: WatermarkConfigV3 = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 80, left: 0 },
    background: '#FFFFFF',
    border_radius: 0,
  },
  defaults: defaultStyle,
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      slots: {
        'left-logo': {
          enabled: true,
          content: { path: '', color: '#D8D8D6' },
          style: null,
        },
        'center': { enabled: false, content: null, style: null },
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
  return structuredClone(presetDefaultV3);
}

// 主界面控制的缺省值
export const defaultMainControls: MainControlConfig = {
  size: 'medium',
  color: 'black',
  density: 'standard',
  show_camera: true,
  show_lens: true,
  show_focal: true,
  show_aperture: true,
  show_shutter: true,
  show_iso: true,
  show_datetime: false,
  show_artist: false,
  show_gps: false,
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

  // 应用密度：底栏高度（当前底层底栏高度等于 canvas bottom margin）
  const footerRegion = config.regions.find(r => r.type === 'footer-bar' && r.enabled);
  if (footerRegion) {
    // 底栏高度 = 密度系数 * 短边 * 大小系数
    // 由于计算完整后才知道短边，这里设置一个基于密度的高度
    const footerHeight = Math.round(800 * densityHeight * (size.footerHeightMultiplier ?? 0.10) / (size.densityMarginMultiplier ?? 1.0));
    config.canvas.margins.bottom = footerHeight;
  }

  // 应用字段开关：在所有 text slot 的 chips 中添加/移除字段
  for (const region of config.regions) {
    if (!region.slots) continue;
    for (const slot of Object.values(region.slots)) {
      if (!slot.content || !('chips' in slot.content)) continue;
      const chips = slot.content.chips;
      // 移除已禁用字段
      slot.content.chips = chips.filter(chip => {
        if (chip.field_id === 'camera_model') return controls.show_camera;
        if (chip.field_id === 'lens_model') return controls.show_lens;
        if (chip.field_id === 'focal_length') return controls.show_focal;
        if (chip.field_id === 'aperture') return controls.show_aperture;
        if (chip.field_id === 'shutter') return controls.show_shutter;
        if (chip.field_id === 'iso') return controls.show_iso;
        if (chip.field_id === 'datetime') return controls.show_datetime;
        if (chip.field_id === 'artist') return controls.show_artist;
        if (chip.field_id === 'gps') return controls.show_gps;
        if (chip.field_id === 'custom_text') return true;
        return true;
      });
    }
  }

  // 自定义文本
  config.custom_text = controls.custom_text;

  // 应用自定义 Logo：填充到 footer 的 right-logo 或 left-logo
  if (controls.logo_path) {
    for (const region of config.regions) {
      if (region.type !== 'footer-bar') continue;
      if (region.slots?.['right-logo']) {
        region.slots['right-logo'].enabled = true;
        if (region.slots['right-logo'].content && 'path' in region.slots['right-logo'].content) {
          region.slots['right-logo'].content.path = controls.logo_path;
        }
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

/**
 * 从一个 WatermarkConfigV3 中推断当前主界面控制状态。
 */
export function inferMainControls(config: WatermarkConfigV3): MainControlConfig {
  const controls = structuredClone(defaultMainControls);

  // 推断字段开关
  for (const region of config.regions) {
    if (!region.slots) continue;
    for (const slot of Object.values(region.slots)) {
      if (!slot.content || !('chips' in slot.content)) continue;
      for (const chip of slot.content.chips) {
        if (chip.field_id === 'camera_model') controls.show_camera = true;
        if (chip.field_id === 'lens_model') controls.show_lens = true;
        if (chip.field_id === 'focal_length') controls.show_focal = true;
        if (chip.field_id === 'aperture') controls.show_aperture = true;
        if (chip.field_id === 'shutter') controls.show_shutter = true;
        if (chip.field_id === 'iso') controls.show_iso = true;
        if (chip.field_id === 'datetime') controls.show_datetime = true;
        if (chip.field_id === 'artist') controls.show_artist = true;
        if (chip.field_id === 'gps') controls.show_gps = true;
      }
    }
  }

  controls.custom_text = config.custom_text ?? '';

  // Logo 路径
  for (const region of config.regions) {
    if (region.type !== 'footer-bar') continue;
    const logoSlot = region.slots?.['right-logo'] ?? region.slots?.['left-logo'];
    if (logoSlot?.enabled && logoSlot.content && 'path' in logoSlot.content) {
      controls.logo_path = logoSlot.content.path;
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
