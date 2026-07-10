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

// ── 预设配置 ──────────────────────────────────────────────────────────

export const defaultStyle: StyleConfig = {
  font_size: null,
  font_size_ratio: 0.35,
  size_reference: 'region_height',
  color: '#222222',
  font_family: 'NotoSansCJKsc-Bold.otf',
  bold: true,
  line_height: 1.2,
};

export const presetDefaultV3: WatermarkConfigV3 = {
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

export const presetMinimalV3: WatermarkConfigV3 = {
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

export const presetSoftCardV3: WatermarkConfigV3 = {
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

export const presetSidesV3: WatermarkConfigV3 = {
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

export function createDefaultWatermarkConfigV3(): WatermarkConfigV3 {
  return structuredClone(presetDefaultV3);
}
