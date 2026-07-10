export type CornerKey = 'left_top' | 'left_bottom' | 'right_top' | 'right_bottom';
export type SideKey = 'left' | 'right';

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

export type FieldChip = {
  field_id: FieldId;
  custom_text?: string;
};

export type CornerConfig = {
  chips: FieldChip[];
  separator: string;
  font_size_ratio: number;
};

export type LogoConfig = {
  enabled: 'auto' | 'disabled' | 'custom';
  position: 'left' | 'center' | 'right';
  color: string;
  custom_path: string;
  // Free-positioning mode (脱离底条自由定位)
  free_position?: boolean;
  anchor?: string;
  margin_x?: number;
  margin_y?: number;
  size_ratio?: number;
};

export type SignatureConfig = {
  enabled: boolean;
  path: string;
  invert_mono: boolean;
  enhancement: 'none' | 'soft_shadow' | 'soft_glow' | 'soft_outline';
  enhancement_strength: number;
  anchor: 'top_left' | 'top_center' | 'top_right' | 'middle_left' | 'middle_center' | 'middle_right' | 'bottom_left' | 'bottom_center' | 'bottom_right';
  margin_x: number;
  margin_y: number;
  size_ratio: number;
};

export type AdvancedConfig = {
  footer_height_px: number;
  logo_height_px: number;
  corner_text_ratio: number;
  global_font: string;
  global_color: string;
  margin_color: string;
  left_margin: number;
  right_margin: number;
  top_margin: number;
  bottom_margin: number;
  border_radius: number;
  shadow_radius: number;
  shadow_color: string;
  blur_radius: number;
  quality: number;
  subsampling: number;
  scale: number;
  trim_enabled: boolean;
  trim_threshold: number;
  ratio_enabled: boolean;
  ratio: string;
  concat_direction: 'horizontal' | 'vertical';
  alignment_mode: 'top' | 'center' | 'bottom';
};

export type WatermarkConfig = {
  corners: Record<CornerKey, CornerConfig>;
  sides: Record<SideKey, CornerConfig>;
  logo: LogoConfig;
  signature: SignatureConfig;
  advanced: AdvancedConfig;
  // Footer bar position and layout mode
  footer_position?: 'bottom' | 'top' | 'left' | 'right';
  layout_mode?: 'corners' | 'sides';
};

export type FieldOption = {
  id: FieldId;
  label: string;
  category: 'exif' | 'custom' | 'empty';
};

export const cornerLabels: Record<CornerKey, string> = {
  left_top: '左上',
  left_bottom: '左下',
  right_top: '右上',
  right_bottom: '右下'
};

export const sideLabels: Record<SideKey, string> = {
  left: '左侧',
  right: '右侧'
};

export const anchorLabels: Record<SignatureConfig['anchor'], string> = {
  top_left: '左上',
  top_center: '上方居中',
  top_right: '右上',
  middle_left: '左侧居中',
  middle_center: '正中心',
  middle_right: '右侧居中',
  bottom_left: '左下',
  bottom_center: '下方居中',
  bottom_right: '右下'
};

export const fieldOptions: FieldOption[] = [
  { id: 'camera_model', label: '相机型号', category: 'exif' },
  { id: 'lens_model', label: '镜头型号', category: 'exif' },
  { id: 'focal_length', label: '焦距', category: 'exif' },
  { id: 'aperture', label: '光圈', category: 'exif' },
  { id: 'shutter', label: '快门', category: 'exif' },
  { id: 'iso', label: 'ISO', category: 'exif' },
  { id: 'datetime', label: '拍摄日期', category: 'exif' },
  { id: 'make', label: '厂商品牌', category: 'exif' },
  { id: 'artist', label: '作者', category: 'exif' },
  { id: 'gps', label: '地理位置', category: 'exif' },
  { id: 'custom_text', label: '自定义文本', category: 'custom' }
];

/** Placeholder values for Canvas skeleton preview when no image EXIF is available. */
export const PLACEHOLDER_EXIF: Record<string, string> = {
  camera_model: 'GFX100S II',
  lens_model: 'GF110mmF5.6',
  focal_length: '110mm',
  aperture: 'f/5.6',
  shutter: '1/500s',
  iso: 'ISO100',
  datetime: '2025-06-15',
  make: 'FUJIFILM',
  artist: 'AKARI',
  gps: 'Tokyo, Japan',
};

export function createDefaultWatermarkConfig(): WatermarkConfig {
  return {
    corners: {
      left_top: {
        chips: [{ field_id: 'make' }, { field_id: 'camera_model' }],
        separator: '    ',
        font_size_ratio: 0.055
      },
      left_bottom: {
        chips: [{ field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'shutter' }, { field_id: 'iso' }],
        separator: '    ',
        font_size_ratio: 0.04
      },
      right_top: {
        chips: [],
        separator: '    ',
        font_size_ratio: 0.035
      },
      right_bottom: {
        chips: [],
        separator: '    ',
        font_size_ratio: 0.035
      }
    },
    sides: {
      left: {
        chips: [{ field_id: 'make' }, { field_id: 'camera_model' }, { field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'shutter' }, { field_id: 'iso' }],
        separator: '    ',
        font_size_ratio: 0.04
      },
      right: {
        chips: [],
        separator: '    ',
        font_size_ratio: 0.035
      }
    },
    logo: {
      enabled: 'auto',
      position: 'right',
      color: '#D8D8D6',
      custom_path: ''
    },
    signature: {
      enabled: false,
      path: '',
      invert_mono: false,
      enhancement: 'none',
      enhancement_strength: 50,
      anchor: 'middle_center',
      margin_x: 0,
      margin_y: 0,
      size_ratio: 0.20
    },
    advanced: {
      footer_height_px: 0,
      logo_height_px: 0,
      corner_text_ratio: 0,
      global_font: 'NotoSansCJKsc-Bold.otf',
      global_color: '#222222',
      margin_color: '#FFFFFF',
      left_margin: 0,
      right_margin: 0,
      top_margin: 0,
      bottom_margin: 0,
      border_radius: 0,
      shadow_radius: 0,
      shadow_color: '#000000',
      blur_radius: 0,
      quality: 95,
      subsampling: 0,
      scale: 1,
      trim_enabled: false,
      trim_threshold: 0,
      ratio_enabled: false,
      ratio: '3:4',
      concat_direction: 'vertical',
      alignment_mode: 'center'
    }
  };
}

export function sanitizeConfig(config: WatermarkConfig): WatermarkConfig {
  const next = structuredClone(config);
  for (const corner of Object.values(next.corners)) {
    corner.chips = corner.chips.filter((chip) => chip.field_id !== 'empty');
  }
  for (const side of Object.values(next.sides)) {
    side.chips = side.chips.filter((chip) => chip.field_id !== 'empty');
  }
  return next;
}
