import { useCallback, useContext, useRef, useState } from 'react';
import { AppContext } from '../HomePage';
import { uploadResource } from '../api';
import {
  anchorLabels,
  cornerLabels,
  sideLabels,
  fieldOptions,
  type CornerConfig,
  type CornerKey,
  type SideKey,
  type FieldChip,
  type FieldId,
  type WatermarkConfig,
} from '../watermarkConfig';

type MainTab = 'corners' | 'logo' | 'signature';

const MAIN_TAB_LABELS: Record<MainTab, string> = {
  corners: '四角',
  logo: 'Logo',
  signature: '签名',
};

const MAIN_TAB_ORDER: MainTab[] = ['corners', 'logo', 'signature'];

export function InspectorPanel() {
  const ctx = useContext(AppContext);
  if (!ctx) return null;
  const { config, setConfig } = ctx;
  const [tab, setTab] = useState<MainTab>('corners');
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // --- Helpers ---
  const updateAdvanced = useCallback(
    (patch: Partial<WatermarkConfig['advanced']>) => {
      setConfig((prev) => ({ ...prev, advanced: { ...prev.advanced, ...patch } }));
    },
    [setConfig],
  );

  const updateCorner = useCallback(
    (cornerKey: CornerKey, patch: Partial<CornerConfig>) => {
      setConfig((prev) => ({
        ...prev,
        corners: { ...prev.corners, [cornerKey]: { ...prev.corners[cornerKey], ...patch } },
      }));
    },
    [setConfig],
  );

  const updateChip = useCallback(
    (cornerKey: CornerKey, index: number, patch: Partial<FieldChip>) => {
      setConfig((prev) => {
        const chips = [...prev.corners[cornerKey].chips];
        chips[index] = { ...chips[index], ...patch };
        return { ...prev, corners: { ...prev.corners, [cornerKey]: { ...prev.corners[cornerKey], chips } } };
      });
    },
    [setConfig],
  );

  const addChip = useCallback(
    (cornerKey: CornerKey) => {
      setConfig((prev) => {
        const chips = [...prev.corners[cornerKey].chips, { field_id: 'camera_model' as FieldId }];
        return { ...prev, corners: { ...prev.corners, [cornerKey]: { ...prev.corners[cornerKey], chips } } };
      });
    },
    [setConfig],
  );

  const removeChip = useCallback(
    (cornerKey: CornerKey, index: number) => {
      setConfig((prev) => {
        const chips = prev.corners[cornerKey].chips.filter((_, i) => i !== index);
        return { ...prev, corners: { ...prev.corners, [cornerKey]: { ...prev.corners[cornerKey], chips } } };
      });
    },
    [setConfig],
  );

  const handleUploadResource = useCallback(
    async (file: File, kind: 'logo' | 'signature') => {
      try {
        const res = await uploadResource(file, kind);
        if (kind === 'logo') {
          setConfig((prev) => ({
            ...prev,
            logo: { ...prev.logo, enabled: 'custom', custom_path: res.resource_id },
          }));
          ctx.showToast('Logo 上传成功', 'success');
        } else {
          setConfig((prev) => ({
            ...prev,
            signature: { ...prev.signature, path: res.resource_id },
          }));
          ctx.showToast('签名上传成功', 'success');
        }
      } catch (err) {
        ctx.showToast(err instanceof Error ? err.message : '上传失败', 'error');
      }
    },
    [setConfig, ctx],
  );

  return (
    <aside className="inspector">
      <div className="inspector-panel">
        {/* --- Main tabs --- */}
        <div className="inspector-tabs">
          {MAIN_TAB_ORDER.map((t) => (
            <button
              key={t}
              className={`inspector-tab ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}
            >
              {MAIN_TAB_LABELS[t]}
            </button>
          ))}
        </div>

        <div className="inspector-body">
          {/* ==== 四角 ==== */}
          <div className={`tab-panel ${tab === 'corners' ? 'active' : ''}`}>
            <CornersTab
              config={config}
              setConfig={setConfig}
              updateCorner={updateCorner}
              updateChip={updateChip}
              addChip={addChip}
              removeChip={removeChip}
            />
          </div>

          {/* ==== Logo ==== */}
          <div className={`tab-panel ${tab === 'logo' ? 'active' : ''}`}>
            <LogoTab config={config} setConfig={setConfig} onUpload={handleUploadResource} />
          </div>

          {/* ==== 签名 ==== */}
          <div className={`tab-panel ${tab === 'signature' ? 'active' : ''}`}>
            <SignatureTab config={config} setConfig={setConfig} onUpload={handleUploadResource} />
          </div>
        </div>

        {/* --- 高级 (collapsible) --- */}
        <div className="advanced-section">
          <button
            className="advanced-toggle"
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            <span className={`advanced-arrow ${advancedOpen ? 'open' : ''}`}>▸</span>
            高级设置
          </button>
          {advancedOpen && (
            <div className="advanced-body">
              <CanvasTab config={config} updateAdvanced={updateAdvanced} />
              <OutputTab config={config} updateAdvanced={updateAdvanced} />
              <EffectsTab config={config} updateAdvanced={updateAdvanced} />
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

// ============================ 四角 Tab ============================

function CornersTab({
  config,
  setConfig,
  updateCorner,
  updateChip,
  addChip,
  removeChip,
}: {
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
  updateCorner: (k: CornerKey, p: Partial<CornerConfig>) => void;
  updateChip: (k: CornerKey, i: number, p: Partial<FieldChip>) => void;
  addChip: (k: CornerKey) => void;
  removeChip: (k: CornerKey, i: number) => void;
}) {
  const cornerKeys: CornerKey[] = ['left_top', 'left_bottom', 'right_top', 'right_bottom'];
  const sideKeys: SideKey[] = ['left', 'right'];
  const isSides = (config.layout_mode ?? 'corners') === 'sides';
  const isFramed = (config.layout_mode ?? 'corners') === 'framed';

  const updateSide = useCallback(
    (sideKey: SideKey, patch: Partial<CornerConfig>) => {
      setConfig((prev) => ({
        ...prev,
        sides: { ...prev.sides, [sideKey]: { ...prev.sides[sideKey], ...patch } },
      }));
    },
    [setConfig],
  );

  const updateSideChip = useCallback(
    (sideKey: SideKey, index: number, patch: Partial<FieldChip>) => {
      setConfig((prev) => {
        const chips = [...prev.sides[sideKey].chips];
        chips[index] = { ...chips[index], ...patch };
        return { ...prev, sides: { ...prev.sides, [sideKey]: { ...prev.sides[sideKey], chips } } };
      });
    },
    [setConfig],
  );

  const addSideChip = useCallback(
    (sideKey: SideKey) => {
      setConfig((prev) => {
        const chips = [...prev.sides[sideKey].chips, { field_id: 'camera_model' as FieldId }];
        return { ...prev, sides: { ...prev.sides, [sideKey]: { ...prev.sides[sideKey], chips } } };
      });
    },
    [setConfig],
  );

  const removeSideChip = useCallback(
    (sideKey: SideKey, index: number) => {
      setConfig((prev) => {
        const chips = prev.sides[sideKey].chips.filter((_, i) => i !== index);
        return { ...prev, sides: { ...prev.sides, [sideKey]: { ...prev.sides[sideKey], chips } } };
      });
    },
    [setConfig],
  );

  return (
    <div className="anim-fade-in corners-all">
      {/* --- Footer bar config --- */}
      <div className="editor-card">
        <div className="form-row" style={{ gap: 12 }}>
          <label>
            底条位置
            <select
              value={config.footer_position ?? 'bottom'}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, footer_position: e.target.value as 'bottom' | 'top' | 'left' | 'right' }))
              }
            >
              <option value="bottom">底部</option>
              <option value="top">顶部</option>
              <option value="left">左侧</option>
              <option value="right">右侧</option>
            </select>
          </label>
          <label>
            布局方案
            <select
              value={config.layout_mode ?? 'corners'}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, layout_mode: e.target.value as 'corners' | 'sides' | 'framed' }))
              }
            >
              <option value="corners">四角</option>
              <option value="sides">左右居中</option>
              <option value="framed">白边相框</option>
            </select>
          </label>
        </div>
      </div>

      {/* --- Corner blocks (四角模式) --- */}
      {!isSides && cornerKeys.map((key) => {
        const corner = config.corners[key];
        return (
          <CornerBlock
            key={key}
            label={cornerLabels[key]}
            corner={corner}
            cornerKey={key}
            updateCorner={(k, p) => updateCorner(k as CornerKey, p)}
            updateChip={(k, i, p) => updateChip(k as CornerKey, i, p)}
            addChip={(k) => addChip(k as CornerKey)}
            removeChip={(k, i) => removeChip(k as CornerKey, i)}
          />
        );
      })}

      {/* --- Side blocks (左右居中模式) --- */}
      {isSides && sideKeys.map((key) => {
        const side = config.sides[key];
        return (
          <CornerBlock
            key={key}
            label={sideLabels[key]}
            corner={side}
            cornerKey={key}
            updateCorner={(k, p) => updateSide(k as SideKey, p)}
            updateChip={(k, i, p) => updateSideChip(k as SideKey, i, p)}
            addChip={(k) => addSideChip(k as SideKey)}
            removeChip={(k, i) => removeSideChip(k as SideKey, i)}
          />
        );
      })}

      {/* --- Framed blocks (白边相框模式) --- */}
      {isFramed && (
        <FrameConfigPanel
          config={config}
          setConfig={setConfig}
          sideKeys={sideKeys}
          updateSide={updateSide}
          updateSideChip={updateSideChip}
          addSideChip={addSideChip}
          removeSideChip={removeSideChip}
        />
      )}
    </div>
  );
}

// ============================ Frame config panel (白边相框) ============================

const FRAME_COLOR_PRESETS = [
  { label: '经典白', bg: '#FFFFFF', primary: '#333333', secondary: '#888888' },
  { label: '暗夜黑', bg: '#1C1C1E', primary: '#FFFFFF', secondary: '#AAAAAA' },
  { label: '暖纸', bg: '#FAF8F5', primary: '#2C2C2C', secondary: '#888888' },
  { label: '透明', bg: 'rgba(0,0,0,0.5)', primary: '#FFFFFF', secondary: '#CCCCCC' },
];

function FrameConfigPanel({
  config,
  setConfig,
  sideKeys,
  updateSide,
  updateSideChip,
  addSideChip,
  removeSideChip,
}: {
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
  sideKeys: SideKey[];
  updateSide: (k: SideKey, p: Partial<CornerConfig>) => void;
  updateSideChip: (k: SideKey, i: number, p: Partial<FieldChip>) => void;
  addSideChip: (k: SideKey) => void;
  removeSideChip: (k: SideKey, i: number) => void;
}) {
  const adv = config.advanced;

  return (
    <>
      <div className="editor-card">
        <h3 className="editor-card-h3">相框设置</h3>
        <label>
          白边宽度 (px)
          <input
            type="number"
            min={0} max={200} step={4}
            value={adv.frame_border_width ?? 40}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, advanced: { ...prev.advanced, frame_border_width: Number(e.target.value) } }))
            }
          />
        </label>
        <div style={{ marginTop: 8 }}>
          <span className="text-secondary text-sm">配色方案</span>
          <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
            {FRAME_COLOR_PRESETS.map((preset) => (
              <button
                key={preset.label}
                className="small"
                style={{
                  background: preset.bg,
                  color: preset.primary,
                  border: adv.frame_bar_bg === preset.bg ? '2px solid var(--accent)' : '1px solid var(--line)',
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-xs)',
                  fontSize: 12,
                }}
                onClick={() =>
                  setConfig((prev) => ({
                    ...prev,
                    advanced: {
                      ...prev.advanced,
                      frame_bar_bg: preset.bg,
                      frame_text_primary: preset.primary,
                      frame_text_secondary: preset.secondary,
                    },
                  }))
                }
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
        <div className="form-row" style={{ marginTop: 8 }}>
          <label>
            底条底色
            <input
              type="color"
              value={adv.frame_bar_bg?.startsWith('#') ? adv.frame_bar_bg : '#FFFFFF'}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, advanced: { ...prev.advanced, frame_bar_bg: e.target.value } }))
              }
              style={{ width: 60, height: 32, padding: 2 }}
            />
          </label>
          <label>
            型号颜色
            <input
              type="color"
              value={adv.frame_text_primary ?? '#333333'}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, advanced: { ...prev.advanced, frame_text_primary: e.target.value } }))
              }
              style={{ width: 60, height: 32, padding: 2 }}
            />
          </label>
          <label>
            参数颜色
            <input
              type="color"
              value={adv.frame_text_secondary ?? '#888888'}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, advanced: { ...prev.advanced, frame_text_secondary: e.target.value } }))
              }
              style={{ width: 60, height: 32, padding: 2 }}
            />
          </label>
        </div>
      </div>

      {/* Left / Right field config — same as sides mode */}
      {sideKeys.map((key) => {
        const side = config.sides[key];
        return (
          <CornerBlock
            key={key}
            label={key === 'left' ? '左侧（型号/镜头）' : '右侧（参数行）'}
            corner={side}
            cornerKey={key}
            updateCorner={(k, p) => updateSide(k as SideKey, p)}
            updateChip={(k, i, p) => updateSideChip(k as SideKey, i, p)}
            addChip={(k) => addSideChip(k as SideKey)}
            removeChip={(k, i) => removeSideChip(k as SideKey, i)}
          />
        );
      })}

      {/* Info: 签名显示区 */}
      <div className="editor-card">
        <label>
          署名（底部 © 文字）
          <input
            type="text"
            value={config.custom_text ?? ''}
            placeholder="留空则不显示"
            maxLength={80}
            onChange={(e) => setConfig((prev) => ({ ...prev, custom_text: e.target.value }))}
          />
        </label>
      </div>
    </>
  );
}

// ============================ CornerBlock ============================

function CornerBlock({
  label,
  cornerKey,
  corner,
  updateCorner,
  updateChip,
  addChip,
  removeChip,
}: {
  label: string;
  cornerKey: string;
  corner: CornerConfig;
  updateCorner: (k: string, p: Partial<CornerConfig>) => void;
  updateChip: (k: string, i: number, p: Partial<FieldChip>) => void;
  addChip: (k: string) => void;
  removeChip: (k: string, i: number) => void;
}) {
  return (
    <div className="corner-block">
      <div className="corner-block-header">
        <span className="corner-block-title">{label}</span>
        <button className="small" onClick={() => addChip(cornerKey)}>+</button>
      </div>
      <div className="chip-list">
        {corner.chips.length === 0 && <p className="text-tertiary text-sm">—</p>}
        {corner.chips.map((chip, i) => (
          <div key={`${cornerKey}-${i}`} className="chip-item">
            <select
              value={chip.field_id}
              onChange={(e) => updateChip(cornerKey, i, { field_id: e.target.value as FieldId })}
            >
              {fieldOptions.map((opt) => (
                <option key={opt.id} value={opt.id}>{opt.label}</option>
              ))}
            </select>
            {chip.field_id === 'custom_text' && (
              <input
                type="text"
                value={chip.custom_text ?? ''}
                placeholder="自定义文本"
                onChange={(e) => updateChip(cornerKey, i, { custom_text: e.target.value })}
              />
            )}
            <button className="chip-remove" onClick={() => removeChip(cornerKey, i)}>×</button>
          </div>
        ))}
      </div>
      <div className="form-row" style={{ gap: 8, marginTop: 8 }}>
        <label className="small-label">
          字号
          <input
            type="number"
            min={0}
            max={0.2}
            step={0.005}
            value={corner.font_size_ratio}
            onChange={(e) => updateCorner(cornerKey, { font_size_ratio: parseFloat(e.target.value) || 0 })}
            style={{ width: 110 }}
          />
        </label>
      </div>
    </div>
  );
}

// ============================ Logo Tab ============================

function LogoTab({
  config,
  setConfig,
  onUpload,
}: {
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
  onUpload: (file: File, kind: 'logo' | 'signature') => Promise<void>;
}) {
  const logoInputRef = useRef<HTMLInputElement>(null);
  const logo = config.logo;

  return (
    <div className="anim-fade-in">
      <div className="editor-card">
        <h3 className="editor-card-h3">Logo 设置</h3>

        <label>
          模式
          <select
            value={logo.enabled}
            onChange={(e) =>
              setConfig((prev) => ({
                ...prev,
                logo: { ...prev.logo, enabled: e.target.value as 'auto' | 'disabled' | 'custom' },
              }))
            }
          >
            <option value="disabled">关闭</option>
            <option value="auto">自动识别品牌</option>
            <option value="custom">自定义</option>
          </select>
        </label>

        {/* Free positioning toggle */}
        <label className="inline">
          <input
            type="checkbox"
            checked={logo.free_position ?? false}
            onChange={(e) =>
              setConfig((prev) => ({
                ...prev,
                logo: { ...prev.logo, free_position: e.target.checked },
              }))
            }
          />
          <span>自由定位</span>
        </label>

        {logo.free_position ? (
          <>
            <label>
              位置锚点
              <select
                value={logo.anchor ?? 'middle_center'}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    logo: { ...prev.logo, anchor: e.target.value },
                  }))
                }
              >
                {(Object.keys(anchorLabels) as Array<keyof typeof anchorLabels>).map((a) => (
                  <option key={a} value={a}>{anchorLabels[a]}</option>
                ))}
              </select>
            </label>
            <div className="form-row">
              <label>
                X 偏移
                <input
                  type="number"
                  min={-0.5} max={0.5} step={0.01}
                  value={logo.margin_x ?? 0}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      logo: { ...prev.logo, margin_x: parseFloat(e.target.value) || 0 },
                    }))
                  }
                />
              </label>
              <label>
                Y 偏移
                <input
                  type="number"
                  min={-0.5} max={0.5} step={0.01}
                  value={logo.margin_y ?? 0}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      logo: { ...prev.logo, margin_y: parseFloat(e.target.value) || 0 },
                    }))
                  }
                />
              </label>
            </div>
            <label>
              大小比例
              <input
                type="number"
                min={0.01} max={1} step={0.01}
                value={logo.size_ratio ?? 0.2}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    logo: { ...prev.logo, size_ratio: parseFloat(e.target.value) || 0.2 },
                  }))
                }
              />
              <span className="label-note">占照片短边比例</span>
            </label>
          </>
        ) : (
          <>
            <label>
              位置
              <select
                value={logo.position}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    logo: { ...prev.logo, position: e.target.value as 'left' | 'center' | 'right' },
                  }))
                }
              >
                <option value="left">左侧</option>
                <option value="center">中间</option>
                <option value="right">右侧</option>
              </select>
            </label>
            <label className="inline">
              分隔线颜色
              <input
                type="color"
                value={logo.color}
                onChange={(e) => setConfig((prev) => ({ ...prev, logo: { ...prev.logo, color: e.target.value } }))}
                style={{ width: 60, height: 32, padding: 2 }}
              />
            </label>
            <label>
              Logo 高度 (px, 0=自动)
              <input
                type="number"
                min={0} max={240} step={4}
                value={config.advanced.logo_height_px}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    advanced: { ...prev.advanced, logo_height_px: Number(e.target.value) },
                  }))
                }
              />
            </label>
          </>
        )}

        {logo.enabled === 'custom' && (
          <div className="file-upload-item" onClick={() => logoInputRef.current?.click()}>
            <input
              ref={logoInputRef}
              type="file"
              accept="image/png,image/jpeg"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void onUpload(file, 'logo');
              }}
            />
            <span className="text-secondary text-sm">
              {logo.custom_path ? '已上传自定义 Logo' : '点击上传自定义 Logo'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================ 签名 Tab ============================

function SignatureTab({
  config,
  setConfig,
  onUpload,
}: {
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
  onUpload: (file: File, kind: 'logo' | 'signature') => Promise<void>;
}) {
  const sigInputRef = useRef<HTMLInputElement>(null);
  const sig = config.signature;

  const updateSig = useCallback(
    (patch: Partial<WatermarkConfig['signature']>) => {
      setConfig((prev) => ({ ...prev, signature: { ...prev.signature, ...patch } }));
    },
    [setConfig],
  );

  return (
    <div className="anim-fade-in">
      <div className="editor-card">
        <h3 className="editor-card-h3">签名水印</h3>

        <label className="inline">
          <input
            type="checkbox"
            checked={sig.enabled}
            onChange={(e) => updateSig({ enabled: e.target.checked })}
          />
          <span>启用签名</span>
        </label>

        {sig.enabled && (
          <>
            <div className="file-upload-item" onClick={() => sigInputRef.current?.click()}>
              <input
                ref={sigInputRef}
                type="file"
                accept="image/png,image/jpeg"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void onUpload(file, 'signature');
                }}
              />
              <span className="text-secondary text-sm">
                {sig.path ? '已上传签名图' : '点击上传签名图片 (PNG/JPG)'}
              </span>
            </div>

            <label className="inline">
              <input type="checkbox" checked={sig.invert_mono} onChange={(e) => updateSig({ invert_mono: e.target.checked })} />
              <span>反色（白字）</span>
            </label>

            <label>
              增强效果
              <select value={sig.enhancement} onChange={(e) => updateSig({ enhancement: e.target.value as 'none' | 'soft_shadow' | 'soft_glow' | 'soft_outline' })}>
                <option value="none">关闭</option>
                <option value="soft_shadow">柔和投影</option>
                <option value="soft_glow">轻微外发光</option>
                <option value="soft_outline">柔和描边</option>
              </select>
            </label>

            {sig.enhancement !== 'none' && (
              <label>
                增强强度
                <input
                  type="range"
                  min={0} max={100}
                  value={sig.enhancement_strength}
                  onChange={(e) => updateSig({ enhancement_strength: Number(e.target.value) })}
                />
                <span className="label-note">{sig.enhancement_strength}%</span>
              </label>
            )}

            <label>
              位置锚点
              <select value={sig.anchor} onChange={(e) => updateSig({ anchor: e.target.value as WatermarkConfig['signature']['anchor'] })}>
                {(Object.keys(anchorLabels) as Array<keyof typeof anchorLabels>).map((a) => (
                  <option key={a} value={a}>{anchorLabels[a]}</option>
                ))}
              </select>
            </label>

            <div className="form-row">
              <label>
                大小比例
                <input type="number" min={0.01} max={1} step={0.01} value={sig.size_ratio} onChange={(e) => updateSig({ size_ratio: parseFloat(e.target.value) || 0.2 })} />
                <span className="label-note">占照片短边比例</span>
              </label>
              <label>
                X 偏移
                <input type="number" min={-0.5} max={0.5} step={0.01} value={sig.margin_x} onChange={(e) => updateSig({ margin_x: parseFloat(e.target.value) || 0 })} />
              </label>
              <label>
                Y 偏移
                <input type="number" min={-0.5} max={0.5} step={0.01} value={sig.margin_y} onChange={(e) => updateSig({ margin_y: parseFloat(e.target.value) || 0 })} />
              </label>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================ Canvas / Output / Effects (高级) ============================

function CanvasTab({
  config,
  updateAdvanced,
}: {
  config: WatermarkConfig;
  updateAdvanced: (patch: Partial<WatermarkConfig['advanced']>) => void;
}) {
  const a = config.advanced;
  return (
    <div className="editor-card">
      <h3 className="editor-card-h3">画布与水印条</h3>
      <label>
        底部水印条高度 (px)
        <input type="number" min={40} max={500} step={10} value={a.footer_height_px} onChange={(e) => updateAdvanced({ footer_height_px: Number(e.target.value) })} />
      </label>
      <label>
        全局角字号比例
        <input type="number" min={0} max={0.2} step={0.005} value={a.corner_text_ratio} onChange={(e) => updateAdvanced({ corner_text_ratio: parseFloat(e.target.value) || 0 })} />
      </label>
      <label className="inline">
        文字颜色
        <input type="color" value={a.global_color} onChange={(e) => updateAdvanced({ global_color: e.target.value })} style={{ width: 60, height: 32, padding: 2 }} />
      </label>
      <label className="inline">
        留白颜色
        <input type="color" value={a.margin_color} onChange={(e) => updateAdvanced({ margin_color: e.target.value })} style={{ width: 60, height: 32, padding: 2 }} />
      </label>
      <div className="form-row">
        <label>左边距 <input type="number" min={0} max={500} value={a.left_margin} onChange={(e) => updateAdvanced({ left_margin: Number(e.target.value) })} /></label>
        <label>右边距 <input type="number" min={0} max={500} value={a.right_margin} onChange={(e) => updateAdvanced({ right_margin: Number(e.target.value) })} /></label>
      </div>
      <div className="form-row">
        <label>上边距 <input type="number" min={0} max={500} value={a.top_margin} onChange={(e) => updateAdvanced({ top_margin: Number(e.target.value) })} /></label>
        <label>下边距 <input type="number" min={0} max={500} value={a.bottom_margin} onChange={(e) => updateAdvanced({ bottom_margin: Number(e.target.value) })} /></label>
      </div>
    </div>
  );
}

function OutputTab({
  config,
  updateAdvanced,
}: {
  config: WatermarkConfig;
  updateAdvanced: (patch: Partial<WatermarkConfig['advanced']>) => void;
}) {
  const a = config.advanced;
  return (
    <div className="editor-card">
      <h3 className="editor-card-h3">输出与变换</h3>
      <label>
        JPEG 质量
        <input type="number" min={1} max={100} value={a.quality} onChange={(e) => updateAdvanced({ quality: Number(e.target.value) })} />
      </label>
      <label>
        色度采样
        <select value={a.subsampling} onChange={(e) => updateAdvanced({ subsampling: Number(e.target.value) })}>
          <option value={0}>0 — 高质量</option>
          <option value={1}>1</option>
          <option value={2}>2 — 文件更小</option>
        </select>
      </label>
      <label>
        缩放比例
        <input type="number" min={0.05} max={3} step={0.05} value={a.scale} onChange={(e) => updateAdvanced({ scale: parseFloat(e.target.value) || 1 })} />
      </label>
      <div className="form-row">
        <label>
          拼接方向
          <select value={a.concat_direction} onChange={(e) => updateAdvanced({ concat_direction: e.target.value as 'horizontal' | 'vertical' })}>
            <option value="vertical">垂直</option>
            <option value="horizontal">水平</option>
          </select>
        </label>
        <label>
          对齐方式
          <select value={a.alignment_mode} onChange={(e) => updateAdvanced({ alignment_mode: e.target.value as 'top' | 'center' | 'bottom' })}>
            <option value="top">顶部</option>
            <option value="center">居中</option>
            <option value="bottom">底部</option>
          </select>
        </label>
      </div>
    </div>
  );
}

function EffectsTab({
  config,
  updateAdvanced,
}: {
  config: WatermarkConfig;
  updateAdvanced: (patch: Partial<WatermarkConfig['advanced']>) => void;
}) {
  const a = config.advanced;
  return (
    <div className="editor-card">
      <h3 className="editor-card-h3">特效</h3>
      <label>
        圆角半径
        <input type="number" min={0} max={160} step={2} value={a.border_radius} onChange={(e) => updateAdvanced({ border_radius: Number(e.target.value) })} />
      </label>
      <label>
        阴影半径
        <input type="number" min={0} max={160} step={2} value={a.shadow_radius} onChange={(e) => updateAdvanced({ shadow_radius: Number(e.target.value) })} />
      </label>
      <label className="inline">
        阴影颜色
        <input type="color" value={a.shadow_color} onChange={(e) => updateAdvanced({ shadow_color: e.target.value })} style={{ width: 60, height: 32, padding: 2 }} />
      </label>
      <label>
        背景模糊
        <input type="number" min={0} max={80} step={1} value={a.blur_radius} onChange={(e) => updateAdvanced({ blur_radius: Number(e.target.value) })} />
      </label>
      <label className="inline">
        <input type="checkbox" checked={a.trim_enabled} onChange={(e) => updateAdvanced({ trim_enabled: e.target.checked })} />
        <span>启用裁边</span>
      </label>
      <label>
        裁边阈值
        <input type="number" min={0} max={255} step={1} value={a.trim_threshold} onChange={(e) => updateAdvanced({ trim_threshold: Number(e.target.value) })} />
      </label>
      <label className="inline">
        <input type="checkbox" checked={a.ratio_enabled} onChange={(e) => updateAdvanced({ ratio_enabled: e.target.checked })} />
        <span>启用比例画布</span>
      </label>
      <label>
        目标比例
        <input value={a.ratio} onChange={(e) => updateAdvanced({ ratio: e.target.value })} placeholder="如 3:4 或 16:9" />
      </label>
    </div>
  );
}
