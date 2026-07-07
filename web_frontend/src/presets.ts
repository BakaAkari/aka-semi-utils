import { createDefaultWatermarkConfig, type WatermarkConfig } from './watermarkConfig';

export type WatermarkPreset = {
  id: string;
  name: string;
  description: string;
  config: WatermarkConfig;
};

function base(): WatermarkConfig {
  return createDefaultWatermarkConfig();
}

export const watermarkPresets: WatermarkPreset[] = [
  {
    id: 'default',
    name: '默认排版',
    description: '左上厂商品牌 + 相机型号，左下焦距   光圈   快门   ISO，右侧自动 Logo。经典简洁的摄影水印风格。',
    config: {
      ...base(),
      corners: {
        left_top: { chips: [{ field_id: 'make' }, { field_id: 'camera_model' }], separator: ' ', font_size_ratio: 0.055 },
        left_bottom: { chips: [{ field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'shutter' }, { field_id: 'iso' }], separator: '   ', font_size_ratio: 0.04 },
        right_top: { chips: [], separator: ' ', font_size_ratio: 0.035 },
        right_bottom: { chips: [], separator: ' ', font_size_ratio: 0.035 }
      },
      logo: { enabled: 'auto', position: 'right', color: '#D8D8D6', custom_path: '' },
      advanced: { ...base().advanced, footer_height_px: 0, logo_height_px: 0, global_color: '#222222' }
    }
  },
  {
    id: 'minimal-params',
    name: '极简参数',
    description: '只在右下显示核心拍摄参数，低调不抢画面。',
    config: {
      ...base(),
      corners: {
        left_top: { chips: [], separator: ' ', font_size_ratio: 0.035 },
        left_bottom: { chips: [], separator: ' ', font_size_ratio: 0.035 },
        right_top: { chips: [], separator: ' ', font_size_ratio: 0.035 },
        right_bottom: { chips: [{ field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'shutter' }, { field_id: 'iso' }], separator: '  ', font_size_ratio: 0.034 }
      },
      logo: { enabled: 'disabled', position: 'right', color: '#D8D8D6', custom_path: '' },
      advanced: { ...base().advanced, footer_height_px: 90, global_color: '#2C2C2C' }
    }
  },
  {
    id: 'center-logo',
    name: '中央 Logo',
    description: '中央品牌 Logo，两侧保留 EXIF 信息，适合较正式展示。',
    config: {
      ...base(),
      corners: {
        left_top: { chips: [{ field_id: 'camera_model' }], separator: ' ', font_size_ratio: 0.034 },
        left_bottom: { chips: [{ field_id: 'lens_model' }], separator: ' ', font_size_ratio: 0.03 },
        right_top: { chips: [{ field_id: 'focal_length' }, { field_id: 'aperture' }], separator: '   ', font_size_ratio: 0.034 },
        right_bottom: { chips: [{ field_id: 'shutter' }, { field_id: 'iso' }, { field_id: 'datetime' }], separator: '   ', font_size_ratio: 0.03 }
      },
      logo: { enabled: 'auto', position: 'center', color: '#D8D8D6', custom_path: '' },
      advanced: { ...base().advanced, footer_height_px: 150, logo_height_px: 52, global_color: '#242424' }
    }
  },
  {
    id: 'soft-card',
    name: '圆角阴影卡片',
    description: '加入圆角、阴影和更高底栏，适合社交媒体成片。',
    config: {
      ...base(),
      corners: {
        left_top: { chips: [{ field_id: 'custom_text', custom_text: 'AKARI PHOTO' }], separator: ' ', font_size_ratio: 0.04 },
        left_bottom: { chips: [{ field_id: 'datetime' }], separator: ' ', font_size_ratio: 0.03 },
        right_top: { chips: [{ field_id: 'camera_model' }], separator: ' ', font_size_ratio: 0.034 },
        right_bottom: { chips: [{ field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'iso' }], separator: '   ', font_size_ratio: 0.03 }
      },
      logo: { enabled: 'auto', position: 'right', color: '#D8D8D6', custom_path: '' },
      advanced: { ...base().advanced, footer_height_px: 150, border_radius: 24, shadow_radius: 18, shadow_color: '#000000', global_color: '#242424' }
    }
  }
];

export function findPreset(id: string): WatermarkPreset | undefined {
  return watermarkPresets.find((preset) => preset.id === id);
}
