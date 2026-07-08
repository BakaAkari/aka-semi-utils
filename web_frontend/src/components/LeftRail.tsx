import { useCallback, useContext, useRef, useState } from 'react';
import { AppContext } from '../HomePage';
import { watermarkPresets } from '../presets';
import type { WatermarkConfig } from '../watermarkConfig';

const SUPPORTED_EXTENSIONS = [
  'jpg', 'jpeg', 'png', 'webp', 'heic', 'heif', 'tif', 'tiff',
  'gif', 'bmp', 'avif', 'raw', 'cr2', 'cr3', 'nef', 'arw', 'dng', 'orf', 'rw2', 'raf', 'pef'
];

const EXT_REGEX = new RegExp(`\\.(${SUPPORTED_EXTENSIONS.join('|')})$`, 'i');

export function LeftRail() {
  const ctx = useContext(AppContext);
  if (!ctx) return null;

  const { files, setFiles, activeFileIndex, setActiveFileIndex, removeFile, setConfig, clearOutputs, showToast } = ctx;
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback((fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const newFiles = Array.from(fileList).filter(f => EXT_REGEX.test(f.name));
    if (newFiles.length === 0) {
      showToast('不支持的文件格式，请选择图片文件', 'error');
      return;
    }
    const filtered = newFiles.filter(f => {
      const ext = f.name.split('.').pop()?.toLowerCase() || '';
      return SUPPORTED_EXTENSIONS.includes(ext);
    });
    if (filtered.length === 0) {
      showToast('不支持的文件格式', 'error');
      return;
    }
    const duplicates = newFiles.length - filtered.length;
    if (duplicates > 0) {
      showToast(`${duplicates} 个文件格式不支持，已跳过`, 'info');
    }
    setFiles(prev => {
      const set = new Set(prev.map(f => f.name + f.size));
      const unique = filtered.filter(f => !set.has(f.name + f.size));
      if (unique.length === 0) {
        showToast('所有文件已存在', 'info');
        return prev;
      }
      return [...prev, ...unique];
    });
    // Reset input so same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [setFiles, showToast]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const onApplyPreset = useCallback((presetConfig: WatermarkConfig) => {
    setConfig(structuredClone(presetConfig));
    clearOutputs();
  }, [setConfig, clearOutputs]);

  const onReset = useCallback(() => {
    setConfig({
      corners: {
        left_top: { chips: [], separator: ' ', font_size_ratio: 0.035 },
        left_bottom: { chips: [], separator: ' ', font_size_ratio: 0.035 },
        right_top: { chips: [], separator: ' ', font_size_ratio: 0.035 },
        right_bottom: { chips: [], separator: ' ', font_size_ratio: 0.035 },
      },
      logo: { enabled: 'disabled', position: 'right', color: '#D8D8D6', custom_path: '' },
      signature: {
        enabled: false,
        path: '',
        invert_mono: false,
        enhancement: 'none',
        enhancement_strength: 50,
        anchor: 'middle_center',
        margin_x: 0,
        margin_y: 0,
        size_ratio: 0.20,
      },
      advanced: {
        footer_height_px: 120,
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
        alignment_mode: 'center',
      },
    });
    clearOutputs();
  }, [setConfig, clearOutputs]);

  return (
    <aside className="left-rail">
      <div className="rail-panel" style={{ flexShrink: 0 }}>
        <div className="rail-panel-header">
          <span className="rail-panel-title">图片</span>
          <span className="text-tertiary text-xs">{files.length} 张</span>
        </div>
        <div className="rail-panel-body">
          <div
            className={`upload-zone ${isDragOver ? 'dragover' : ''}`}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={SUPPORTED_EXTENSIONS.map(e => `image/${e}`).join(',')}
              multiple
              onChange={(e) => handleFiles(e.target.files)}
            />
            <span className="upload-zone-icon">📷</span>
            <span className="upload-zone-text">拖拽或点击上传</span>
            <span className="upload-zone-hint">JPG / PNG / WebP / HEIC / TIFF / GIF / BMP / RAW</span>
          </div>
        </div>
      </div>

      {files.length > 0 && (
        <div className="rail-panel" style={{ flex: 1, minHeight: 0 }}>
          <div className="rail-panel-header">
            <span className="rail-panel-title">缩略图</span>
          </div>
          <div className="rail-panel-body">
            <div className="thumb-grid">
              {files.map((file, i) => (
                <div
                  key={`${file.name}-${i}`}
                  className={`thumb-item ${i === activeFileIndex ? 'active' : ''}`}
                  onClick={() => setActiveFileIndex(i)}
                  title={file.name}
                >
                  <img src={URL.createObjectURL(file)} alt={file.name} />
                  <div className="thumb-overlay">
                    <button
                      className="thumb-remove"
                      onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                      title="移除"
                    >
                      ×
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="rail-panel" style={{ flexShrink: 0, maxHeight: 380 }}>
        <div className="rail-panel-header">
          <span className="rail-panel-title">水印预设</span>
          <button className="small ghost" onClick={onReset}>重置</button>
        </div>
        <div className="rail-panel-body">
          <div className="preset-list">
            {watermarkPresets.map((preset) => (
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
