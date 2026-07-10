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

// 主界面预设配置（结构编辑收敛后，每个预设的主界面默认状态）
export const watermarkPresetMetaV3: Record<string, { mainControls: WatermarkPresetV3['mainControls'] }> = {
  default: {
    mainControls: {
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
    },
  },
  minimal: {
    mainControls: {
      size: 'medium',
      color: 'black',
      density: 'standard',
      show_camera: false,
      show_lens: false,
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
    },
  },
  'soft-card': {
    mainControls: {
      size: 'medium',
      color: 'black',
      density: 'loose',
      show_camera: true,
      show_lens: false,
      show_focal: true,
      show_aperture: true,
      show_shutter: false,
      show_iso: true,
      show_datetime: true,
      show_artist: false,
      show_gps: false,
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
    },
  },
};

export const defaultPresetMetaV3 = watermarkPresetMetaV3['default'];
