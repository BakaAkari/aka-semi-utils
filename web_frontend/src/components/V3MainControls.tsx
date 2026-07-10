import { useCallback, useContext, useRef, useState } from 'react';
import { V3AppContext } from '../V3HomePage';
import {
  applyMainControls,
  createDefaultWatermarkConfigV3,
  type MainControlConfig,
  type PresetColor,
  type PresetDensity,
  type PresetSize,
  type WatermarkConfigV3,
  defaultMainControls,
  sizeVariants,
  colorThemes,
  densityVariants,
  inferMainControls,
} from '../v3Types';
import { uploadResourceV3 } from '../apiV3';

const SIZE_LABELS: Record<PresetSize, string> = {
  small: '小',
  medium: '中',
  large: '大',
};

const COLOR_LABELS: Record<PresetColor, string> = {
  black: '黑',
  white: '白',
  'warm-gray': '暖灰',
  auto: '自动',
};

const DENSITY_LABELS: Record<PresetDensity, string> = {
  compact: '紧凒',
  standard: '标准',
  loose: '宽松',
};

export function V3MainControls() {
  const context = useContext(V3AppContext);
  if (!context) return null;

  const { config, setConfig } = context;

  // 从当前 config 推断 controls
  const controls = inferMainControls(config);

  const update = useCallback(
    (patch: Partial<MainControlConfig>) => {
      const next = { ...controls, ...patch };
      const base = stripMainControls(config);
      const newConfig = applyMainControls(base, next);
      setConfig(newConfig);
    },
    [config, controls, setConfig],
  );

  return (
    <div className="v3-main-controls">
      <ControlGroup title="内容">
        <Toggle label="相机" checked={controls.show_camera} onChange={(v) => update({ show_camera: v })} />
        <Toggle label="镜头" checked={controls.show_lens} onChange={(v) => update({ show_lens: v })} />
        <Toggle label="焦距" checked={controls.show_focal} onChange={(v) => update({ show_focal: v })} />
        <Toggle label="光圈" checked={controls.show_aperture} onChange={(v) => update({ show_aperture: v })} />
        <Toggle label="快门" checked={controls.show_shutter} onChange={(v) => update({ show_shutter: v })} />
        <Toggle label="ISO" checked={controls.show_iso} onChange={(v) => update({ show_iso: v })} />
        <Toggle label="日期" checked={controls.show_datetime} onChange={(v) => update({ show_datetime: v })} />
        <Toggle label="作者" checked={controls.show_artist} onChange={(v) => update({ show_artist: v })} />
        <Toggle label="位置" checked={controls.show_gps} onChange={(v) => update({ show_gps: v })} />
      </ControlGroup>

      <ControlGroup title="自定义">
        <label className="v3-control-label">
          全局自定义文本
          <input
            type="text"
            value={controls.custom_text}
            placeholder="用于替换自定义文本字段"
            onChange={(e) => update({ custom_text: e.target.value })}
          />
        </label>
      </ControlGroup>

      <ControlGroup title="样式">
        <SegmentedControl
          label="大小"
          options={(['small', 'medium', 'large'] as PresetSize[]).map((v) => ({ value: v, label: SIZE_LABELS[v] }))}
          value={controls.size}
          onChange={(v) => update({ size: v })}
        />
        <SegmentedControl
          label="颜色"
          options={(['black', 'white', 'warm-gray', 'auto'] as PresetColor[]).map((v) => ({ value: v, label: COLOR_LABELS[v] }))}
          value={controls.color}
          onChange={(v) => update({ color: v })}
        />
        <SegmentedControl
          label="密度"
          options={(['compact', 'standard', 'loose'] as PresetDensity[]).map((v) => ({ value: v, label: DENSITY_LABELS[v] }))}
          value={controls.density}
          onChange={(v) => update({ density: v })}
        />
      </ControlGroup>

      <ControlGroup title="资源">
        <ResourceUploader
          label="自定义 Logo"
          path={controls.logo_path}
          kind="logo"
          onChange={(path) => update({ logo_path: path })}
        />
        <ResourceUploader
          label="签名"
          path={controls.signature_path}
          kind="signature"
          onChange={(path) => update({ signature_path: path })}
        />
      </ControlGroup>
    </div>
  );
}

function ControlGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="v3-control-group">
      <h4 className="v3-control-group-title">{title}</h4>
      <div className="v3-control-group-body">{children}</div>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="v3-toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="v3-segmented-control">
      <span className="v3-segmented-label">{label}</span>
      <div className="v3-segmented-options">
        {options.map((opt) => (
          <button
            key={opt.value}
            className={`v3-segmented-option ${value === opt.value ? 'active' : ''}`}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ResourceUploader({
  label,
  path,
  kind,
  onChange,
}: {
  label: string;
  path: string;
  kind: 'logo' | 'signature';
  onChange: (path: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState('');

  const handleChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setStatus('上传中...');
    try {
      const result = await uploadResourceV3(file, kind);
      onChange(result.resource_id);
      setStatus('上传完成');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '上传失败');
    }
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="v3-resource-uploader">
      <span className="v3-resource-label">{label}</span>
      <div className="v3-resource-row">
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          hidden
          onChange={handleChange}
        />
        <button className="small" onClick={() => inputRef.current?.click()}>
          {path ? '替换' : '上传'}
        </button>
        {path && (
          <button className="small ghost" onClick={() => onChange('')}>
            清除
          </button>
        )}
      </div>
      {status && <span className="v3-resource-status">{status}</span>}
    </div>
  );
}

// 从一个已经应用过 controls 的 config 中剥离掉主界面参数的影响，
// 使用预设的 base 作为新基准。
// 简化方案：直接用当前 config 作为 base。
function stripMainControls(config: WatermarkConfigV3): WatermarkConfigV3 {
  // 为了避免主界面控制变更叠加后不可逆，
  // 我们在应用 controls 时其实已经修改了 config。
  // 这里返回当前 config 作为 base，允许用户在当前状态上继续调整。
  return structuredClone(config);
}

export function V3ResetToDefault() {
  const context = useContext(V3AppContext);
  if (!context) return null;
  const { setConfig, clearOutputs } = context;
  return (
    <button
      className="small ghost"
      onClick={() => {
        setConfig(createDefaultWatermarkConfigV3());
        clearOutputs();
      }}
    >
      重置
    </button>
  );
}

export { defaultMainControls, sizeVariants, colorThemes, densityVariants };
