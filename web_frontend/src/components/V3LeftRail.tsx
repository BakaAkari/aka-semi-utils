import { useCallback, useContext } from 'react';
import { V3AppContext } from '../V3HomePage';
import { createDefaultWatermarkConfigV3, type WatermarkConfigV3, type PreviewAspectRatio } from '../v3Types';
import { watermarkPresetsV3 } from '../v3Presets';
import { ImagePresetRail } from './ImagePresetRail';

interface V3LeftRailProps {
  aspectRatio?: PreviewAspectRatio;
  onAspectRatioChange?: (ratio: PreviewAspectRatio) => void;
}

export function V3LeftRail({ aspectRatio, onAspectRatioChange }: V3LeftRailProps) {
  const context = useContext(V3AppContext);
  if (!context) return null;

  const {
    files,
    activeFileIndex,
    setFiles,
    setActiveFileIndex,
    removeFile,
    setConfig,
    clearOutputs,
    showToast,
  } = context;

  const applyPreset = useCallback((presetConfig: WatermarkConfigV3) => {
    setConfig(structuredClone(presetConfig));
    clearOutputs();
  }, [clearOutputs, setConfig]);

  const resetConfig = useCallback(() => {
    setConfig(createDefaultWatermarkConfigV3());
    clearOutputs();
  }, [clearOutputs, setConfig]);

  return (
    <ImagePresetRail
      files={files}
      activeFileIndex={activeFileIndex}
      setFiles={setFiles}
      setActiveFileIndex={setActiveFileIndex}
      removeFile={removeFile}
      presets={watermarkPresetsV3}
      onApplyPreset={applyPreset}
      onReset={resetConfig}
      showToast={showToast}
      aspectRatio={aspectRatio}
      onAspectRatioChange={onAspectRatioChange}
    />
  );
}
