import type { RailPreset } from './components/ImagePresetRail';
import {
  presetDefaultBaseV3,
  presetMinimalBaseV3,
  presetSidesBaseV3,
  presetSoftCardBaseV3,
  type WatermarkPresetV3,
  type WatermarkConfigV3,
} from './v3Types';

export const watermarkPresetsV3: RailPreset<WatermarkConfigV3>[] = [
  {
    id: 'default',
    name: '默认排版',
    description: '底部栏：左上品牌+型号，左下参数，右侧自动 Logo',
    config: presetDefaultBaseV3,
  },
  {
    id: 'minimal',
    name: '极简参数',
    description: '仅右下显示核心拍摄参数',
    config: presetMinimalBaseV3,
  },
  {
    id: 'soft-card',
    name: '圆角卡片',
    description: '圆角+高底栏，适合社交媒体',
    config: presetSoftCardBaseV3,
  },
  {
    id: 'sides',
    name: '左右居中',
    description: '底部 Logo + 左侧垂直参数',
    config: presetSidesBaseV3,
  },
];

// 主界面预设配置（模板默认的底部栏位、Logo 位置等主界面状态）
export const watermarkPresetMetaV3: Record<string, { mainControls: WatermarkPresetV3['mainControls'] }> = {
  default: {
    mainControls: {
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
    },
  },
  minimal: {
    mainControls: {
      size: 'medium',
      color: 'black',
      density: 'standard',
      footer_mode: 'dual-row',
      logo_position: 'right',
      top_left: [],
      bottom_left: [],
      top_right: [],
      bottom_right: [{ field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'shutter' }, { field_id: 'iso' }],
      left_row: [],
      right_row: [{ field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'shutter' }, { field_id: 'iso' }],
      custom_text: '',
      logo_path: '',
      signature_path: '',
    },
  },
  'soft-card': {
    mainControls: {
      size: 'medium',
      color: 'black',
      density: 'loose',
      footer_mode: 'dual-row',
      logo_position: 'right',
      top_left: [{ field_id: 'custom_text', custom_text: 'AKARI PHOTO' }],
      bottom_left: [{ field_id: 'datetime' }],
      top_right: [{ field_id: 'camera_model' }],
      bottom_right: [{ field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'iso' }],
      left_row: [{ field_id: 'custom_text', custom_text: 'AKARI PHOTO' }],
      right_row: [{ field_id: 'camera_model' }, { field_id: 'focal_length' }, { field_id: 'aperture' }, { field_id: 'iso' }],
      custom_text: 'AKARI PHOTO',
      logo_path: '',
      signature_path: '',
    },
  },
  sides: {
    mainControls: {
      size: 'medium',
      color: 'black',
      density: 'standard',
      footer_mode: 'dual-row',
      logo_position: 'left',
      top_left: [],
      bottom_left: [],
      top_right: [],
      bottom_right: [],
      left_row: [],
      right_row: [],
      custom_text: '',
      logo_path: '',
      signature_path: '',
    },
  },
};

export const defaultPresetMetaV3 = watermarkPresetMetaV3['default'];
