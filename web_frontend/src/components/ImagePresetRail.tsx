import { useCallback, useEffect, useRef, useState } from 'react';
import { PREVIEW_ASPECT_RATIOS, type PreviewAspectRatio } from '../v3Types';

const SUPPORTED_EXTENSIONS = [
  'jpg', 'jpeg', 'png', 'webp', 'heic', 'heif', 'tif', 'tiff',
  'gif', 'bmp', 'avif', 'raw', 'cr2', 'cr3', 'nef', 'arw', 'dng', 'orf', 'rw2', 'raf', 'pef',
] as const;

const EXT_REGEX = new RegExp(`\\.(${SUPPORTED_EXTENSIONS.join('|')})$`, 'i');

export type RailPreset<TConfig> = {
  id: string;
  name: string;
  description: string;
  config: TConfig;
};

type ImagePresetRailProps<TConfig> = {
  files: File[];
  activeFileIndex: number;
  setFiles: React.Dispatch<React.SetStateAction<File[]>>;
  setActiveFileIndex: React.Dispatch<React.SetStateAction<number>>;
  removeFile: (index: number) => void;
  presets: RailPreset<TConfig>[];
  onApplyPreset: (config: TConfig) => void;
  onReset: () => void;
  showToast: (message: string, type: 'success' | 'error' | 'info') => void;
  aspectRatio?: PreviewAspectRatio;
  onAspectRatioChange?: (ratio: PreviewAspectRatio) => void;
};

/**
 * Shared image/preset rail used by the V3 workspace.
 *
 * Object URLs are owned by this component: they are created once per File,
 * revoked when that file is removed, and all revoked again on unmount.
 */
export function ImagePresetRail<TConfig>({
  files,
  activeFileIndex,
  setFiles,
  setActiveFileIndex,
  removeFile,
  presets,
  onApplyPreset,
  onReset,
  showToast,
  aspectRatio,
  onAspectRatioChange,
}: ImagePresetRailProps<TConfig>) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [, setUrlRevision] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const objectUrlsRef = useRef<Map<File, string>>(new Map());

  useEffect(() => {
    const currentFiles = new Set(files);
    const urls = objectUrlsRef.current;
    let changed = false;

    for (const file of files) {
      if (!urls.has(file)) {
        urls.set(file, URL.createObjectURL(file));
        changed = true;
      }
    }

    for (const [file, url] of urls) {
      if (!currentFiles.has(file)) {
        URL.revokeObjectURL(url);
        urls.delete(file);
        changed = true;
      }
    }

    if (changed) setUrlRevision((value) => value + 1);
  }, [files]);

  useEffect(() => () => {
    for (const url of objectUrlsRef.current.values()) URL.revokeObjectURL(url);
    objectUrlsRef.current.clear();
  }, []);

  const handleFiles = useCallback((fileList: FileList | null) => {
    if (!fileList?.length) return;

    const candidates = Array.from(fileList);
    const supported = candidates.filter((file) => EXT_REGEX.test(file.name));
    const unsupportedCount = candidates.length - supported.length;

    if (unsupportedCount > 0) {
      showToast(`${unsupportedCount} 个文件格式不支持，已跳过`, 'info');
    }
    if (supported.length === 0) {
      showToast('不支持的文件格式，请选择图片文件', 'error');
      return;
    }

    const existing = new Set(files.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
    const unique = supported.filter((file) => !existing.has(`${file.name}:${file.size}:${file.lastModified}`));

    if (unique.length === 0) {
      showToast('所选图片已存在', 'info');
    } else {
      setFiles((current) => [...current, ...unique]);
    }

    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [files, setFiles, showToast]);

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);
    handleFiles(event.dataTransfer.files);
  }, [handleFiles]);

  return (
    <aside className="left-rail v3-left-rail" aria-label="图像选择和水印预设">
      <div className="rail-panel rail-panel-upload">
        <div className="rail-panel-header">
          <span className="rail-panel-title">图片</span>
          <span className="text-tertiary text-xs">{files.length} 张</span>
        </div>
        <div className="rail-panel-body">
          <div
            className={`upload-zone ${isDragOver ? 'dragover' : ''}`}
            onDrop={onDrop}
            onDragOver={(event) => { event.preventDefault(); setIsDragOver(true); }}
            onDragLeave={(event) => { event.preventDefault(); setIsDragOver(false); }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={SUPPORTED_EXTENSIONS.map((extension) => `.${extension}`).join(',')}
              multiple
              onChange={(event) => handleFiles(event.target.files)}
            />
            <span className="upload-zone-icon">📷</span>
            <span className="upload-zone-text">拖拽或点击上传</span>
            <span className="upload-zone-hint">JPG / PNG / WebP / HEIC / TIFF / GIF / BMP / RAW</span>
          </div>
        </div>
      </div>

      {files.length === 0 && onAspectRatioChange && (
        <div className="rail-panel rail-panel-aspect">
          <div className="rail-panel-header">
            <span className="rail-panel-title">预览比例</span>
          </div>
          <div className="rail-panel-body">
            <div className="aspect-ratio-grid">
              {PREVIEW_ASPECT_RATIOS.map((ratio) => (
                <button
                  key={ratio.id}
                  className={`aspect-ratio-btn ${aspectRatio === ratio.id ? 'active' : ''}`}
                  onClick={() => onAspectRatioChange(ratio.id)}
                  title={ratio.label}
                >
                  <span className="aspect-ratio-frame" style={{ aspectRatio: ratio.width / ratio.height }} />
                  <span className="aspect-ratio-label">{ratio.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {files.length > 0 && (
        <div className="rail-panel rail-panel-thumbnails">
          <div className="rail-panel-header">
            <span className="rail-panel-title">缩略图</span>
          </div>
          <div className="rail-panel-body scroll">
            <div className="thumb-grid">
              {files.map((file, index) => {
                const objectUrl = objectUrlsRef.current.get(file);
                return (
                  <div
                    key={`${file.name}-${file.size}-${file.lastModified}`}
                    className={`thumb-item ${index === activeFileIndex ? 'active' : ''}`}
                    onClick={() => setActiveFileIndex(index)}
                    title={file.name}
                  >
                    {objectUrl && <img src={objectUrl} alt={file.name} />}
                    <button
                      className="thumb-remove"
                      onClick={(event) => { event.stopPropagation(); removeFile(index); }}
                      title="移除"
                      aria-label={`移除 ${file.name}`}
                    >
                      ×
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="rail-panel rail-panel-presets">
        <div className="rail-panel-header">
          <span className="rail-panel-title">水印预设</span>
          <button className="small ghost" onClick={onReset}>重置</button>
        </div>
        <div className="rail-panel-body scroll">
          <div className="preset-list">
            {presets.map((preset) => (
              <button
                key={preset.id}
                className="preset-card"
                onClick={() => onApplyPreset(preset.config)}
              >
                <span className="preset-card-name">{preset.name}</span>
                <span className="preset-card-desc">{preset.description}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}
