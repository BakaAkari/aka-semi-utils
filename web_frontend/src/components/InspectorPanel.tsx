import { useCallback, useContext, useRef, useState } from 'react';
import { AppContext } from '../HomePage';
import { uploadResource } from '../api';
import {
  anchorLabels,
  cornerLabels,
  fieldOptions,
  type CornerConfig,
  type CornerKey,
  type FieldChip,
  type FieldId,
  type WatermarkConfig,
} from '../watermarkConfig';

type InspectorTab = 'corners' | 'logo' | 'signature' | 'canvas' | 'output' | 'effects';

const TAB_LABELS: Record<InspectorTab, string> = {
  corners: '四角',
  logo: 'Logo',
  signature: '签名',
  canvas: '画布',
  output: '输出',
  effects: '特效',
};

export function InspectorPanel() {
  const ctx = useContext(AppContext);
  if (!ctx) return null;
  const { config, setConfig } = ctx;
  const [tab, setTab] = useState<InspectorTab>('corners');
  const [activeCorner, setActiveCorner] = useState<CornerKey>('left_top');

  const updateAdvanced = useCallback(
    (patch: Partial<WatermarkConfig['advanced']>) => {
      setConfig((prev) => ({ ...prev, advanced: { ...prev.advanced, ...patch } }));
    },
    [setConfig]
  );

  const updateCorner = useCallback(
    (cornerKey: CornerKey, patch: Partial<CornerConfig>) => {
      setConfig((prev) => ({
        ...prev,
        corners: { ...prev.corners, [cornerKey]: { ...prev.corners[cornerKey], ...patch } },
      }));
    },
    [setConfig]
  );

  const updateChip = useCallback(
    (cornerKey: CornerKey, index: number, patch: Partial<FieldChip>) => {
      setConfig((prev) => {
        const chips = [...prev.corners[cornerKey].chips];
        chips[index] = { ...chips[index], ...patch };
        return { ...prev, corners: { ...prev.corners, [cornerKey]: { ...prev.corners[cornerKey], chips } } };
      });
    },
    [setConfig]
  );

  const addChip = useCallback(
    (cornerKey: CornerKey) => {
      setConfig((prev) => {
        const chips = [...prev.corners[cornerKey].chips, { field_id: 'camera_model' as FieldId }];
        return { ...prev, corners: { ...prev.corners, [cornerKey]: { ...prev.corners[cornerKey], chips } } };
      });
    },
    [setConfig]
  );

  const removeChip = useCallback(
    (cornerKey: CornerKey, index: number) => {
      setConfig((prev) => {
        const chips = prev.corners[cornerKey].chips.filter((_, i) => i !== index);
        return { ...prev, corners: { ...prev.corners, [cornerKey]: { ...prev.corners[cornerKey], chips } } };
      });
    },
    [setConfig]
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
    [setConfig, ctx]
  );

  return (
    <aside className="inspector">
      <div className="inspector-panel">
        <div className="inspector-tabs">
          {(Object.keys(TAB_LABELS) as InspectorTab[]).map((t) => (
            <button
              key={t}
              className={`inspector-tab ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>
        <div className="inspector-body">
          {tab === 'corners' && (
            <CornersTab
              config={config}
              activeCorner={activeCorner}
              setActiveCorner={setActiveCorner}
              updateCorner={updateCorner}
              updateChip={updateChip}
              addChip={addChip}
              removeChip={removeChip}
            />
          )}
          {tab === 'logo' && <LogoTab config={config} setConfig={setConfig} onUpload={handleUploadResource} />}
          {tab === 'signature' && <SignatureTab config={config} setConfig={setConfig} onUpload={handleUploadResource} />}
          {tab === 'canvas' && <CanvasTab config={config} updateAdvanced={updateAdvanced} />}
          {tab === 'output' && <OutputTab config={config} updateAdvanced={updateAdvanced} />}
          {tab === 'effects' && <EffectsTab config={config} updateAdvanced={updateAdvanced} />}
        </div>
      </div>
    </aside>
  );
}

// ==================== Corners Tab ====================
function CornersTab({
  config,
  activeCorner,
  setActiveCorner,
  updateCorner,
  updateChip,
  addChip,
  removeChip,
}: {
  config: WatermarkConfig;
  activeCorner: CornerKey;
  setActiveCorner: (c: CornerKey) => void;
  updateCorner: (k: CornerKey, p: Partial<CornerConfig>) => void;
  updateChip: (k: CornerKey, i: number, p: Partial<FieldChip>) => void;
  addChip: (k: CornerKey) => void;
  removeChip: (k: CornerKey, i: number) => void;
}) {
  const corner = config.corners[activeCorner];

  return (
    <div className="anim-fade-in">
      <div className="corner-tabs">
        {(Object.keys(cornerLabels) as CornerKey[]).map((key) => (
          <button
            key={key}
            className={`corner-tab ${activeCorner === key ? 'active' : ''}`}
            onClick={() => setActiveCorner(key)}
          >
            {cornerLabels[key]}
          </button>
        ))}
      </div>
      <div className="editor-card">
        <div className="editor-card-title">
          <h3>{cornerLabels[activeCorner]} 字段</h3>
          <button className="small" onClick={() => addChip(activeCorner)}>
            + 添加
          </button>
        </div>
        <div className="chip-list">
          {corner.chips.length === 0 && <p className="text-tertiary text-sm">未配置字段</p>}
          {corner.chips.map((chip, i) => (
            <div key={`${activeCorner}-${i}`} className="chip-item">
              <select
                value={chip.field_id}
                onChange={(e) => updateChip(activeCorner, i, { field_id: e.target.value as FieldId })}
              >
                {fieldOptions.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.label}
                  </option>
                ))}
              </select>
              {chip.field_id === 'custom_text' && (
                <input
                  type="text"
                  value={chip.custom_text ?? ''}
                  placeholder="自定义文本"
                  onChange={(e) => updateChip(activeCorner, i, { custom_text: e.target.value })}
                />
              )}
              <button className="chip-remove" onClick={() => removeChip(activeCorner, i)} title="删除">
                ×
              </button>
            </div>
          ))}
        </div>
        <div className="form-row">
          <label>
            分隔符
            <input
              value={corner.separator}
              onChange={(e) => updateCorner(activeCorner, { separator: e.target.value })}
            />
          </label>
          <label>
            字号比例
            <input
              type="number"
              min={0}
              max={0.2}
              step={0.005}
              value={corner.font_size_ratio}
              onChange={(e) => updateCorner(activeCorner, { font_size_ratio: parseFloat(e.target.value) || 0 })}
            />
          </label>
        </div>
      </div>
    </div>
  );
}

// ==================== Logo Tab ====================
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

  return (
    <div className="anim-fade-in">
      <div className="editor-card">
        <h3 style={{ marginTop: 0, fontSize: 13, fontWeight: 600 }}>Logo 设置</h3>
        <label>
          模式
          <select
            value={config.logo.enabled}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, logo: { ...prev.logo, enabled: e.target.value as 'auto' | 'disabled' | 'custom' } }))
            }
          >
            <option value="disabled">关闭</option>
            <option value="auto">自动识别品牌</option>
            <option value="custom">自定义</option>
          </select>
        </label>

        <label>
          位置
          <select
            value={config.logo.position}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, logo: { ...prev.logo, position: e.target.value as 'left' | 'center' | 'right' } }))
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
            value={config.logo.color}
            onChange={(e) => setConfig((prev) => ({ ...prev, logo: { ...prev.logo, color: e.target.value } }))}
            style={{ width: 60, height: 32, padding: 2 }}
          />
        </label>

        <label>
          Logo 高度 (px, 0=自动)
          <input
            type="number"
            min={0}
            max={240}
            step={4}
            value={config.advanced.logo_height_px}
            onChange={(e) => setConfig((prev) => ({ ...prev, advanced: { ...prev.advanced, logo_height_px: Number(e.target.value) } }))}
          />
        </label>

        {config.logo.enabled === 'custom' && (
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
              {config.logo.custom_path ? '已上传自定义 Logo' : '点击上传自定义 Logo'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== Signature Tab ====================
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
    [setConfig]
  );

  return (
    <div className="anim-fade-in">
      <div className="editor-card">
        <h3 style={{ marginTop: 0, fontSize: 13, fontWeight: 600 }}>签名水印</h3>

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
                  min={0}
                  max={100}
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
                <span className="label-note">比例</span>
              </label>
              <label>
                Y 偏移
                <input type="number" min={-0.5} max={0.5} step={0.01} value={sig.margin_y} onChange={(e) => updateSig({ margin_y: parseFloat(e.target.value) || 0 })} />
                <span className="label-note">比例</span>
              </label>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ==================== Canvas Tab ====================
function CanvasTab({
  config,
  updateAdvanced,
}: {
  config: WatermarkConfig;
  updateAdvanced: (patch: Partial<WatermarkConfig['advanced']>) => void;
}) {
  const a = config.advanced;
  return (
    <div className="anim-fade-in">
      <div className="editor-card">
        <h3 style={{ marginTop: 0, fontSize: 13, fontWeight: 600 }}>画布与水印条</h3>
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
    </div>
  );
}

// ==================== Output Tab ====================
function OutputTab({
  config,
  updateAdvanced,
}: {
  config: WatermarkConfig;
  updateAdvanced: (patch: Partial<WatermarkConfig['advanced']>) => void;
}) {
  const a = config.advanced;
  return (
    <div className="anim-fade-in">
      <div className="editor-card">
        <h3 style={{ marginTop: 0, fontSize: 13, fontWeight: 600 }}>输出与变换</h3>
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
    </div>
  );
}

// ==================== Effects Tab ====================
function EffectsTab({
  config,
  updateAdvanced,
}: {
  config: WatermarkConfig;
  updateAdvanced: (patch: Partial<WatermarkConfig['advanced']>) => void;
}) {
  const a = config.advanced;
  return (
    <div className="anim-fade-in">
      <div className="editor-card">
        <h3 style={{ marginTop: 0, fontSize: 13, fontWeight: 600 }}>特效</h3>
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
    </div>
  );
}
