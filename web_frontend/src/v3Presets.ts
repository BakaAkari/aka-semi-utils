import type { RailPreset } from './components/ImagePresetRail';
import {
  presetDefaultV3,
  presetMinimalV3,
  presetSidesV3,
  presetSoftCardV3,
  type WatermarkConfigV3,
} from './v3Types';

export const watermarkPresetsV3: RailPreset<WatermarkConfigV3>[] = [
  {
    id: 'default',
    name: '默认排版',
    description: '底部栏：左上品牌+型号，左下参数，右侧自动 Logo',
    config: presetDefaultV3,
  },
  {
    id: 'minimal',
    name: '极简参数',
    description: '仅右下显示核心拍摄参数',
    config: presetMinimalV3,
  },
  {
    id: 'soft-card',
    name: '圆角卡片',
    description: '圆角+高底栏，适合社交媒体',
    config: presetSoftCardV3,
  },
  {
    id: 'sides',
    name: '左右居中',
    description: '底部 Logo + 左侧垂直参数',
    config: presetSidesV3,
  },
];
