/**
 * V3 Inspector Panel — 产品化控制面：主界面参数化 + 高级结构编辑
 *
 * 与之前的区别：
 * - 主界面不再直接编辑 Region/Slot，只提供高频参数。
 * - 高级设置默认折叠，点击后才能编辑原有结构。
 * - 隐藏新增 Region / 删除 Region / 新增 Slot/Line/Signature 等危险入口。
 */

import { useCallback, useRef, useState } from 'react';
import { uploadResourceV3 } from '../apiV3';
import type {
  WatermarkConfigV3,
  RegionConfig,
  SlotConfig,
  TextContent,
  LogoContent,
  SignatureContent,
  Content,
  StyleConfig,
  FieldChip,
  RegionType,
  FieldId,
} from '../v3Types';
import { fieldOptionsV3, defaultStyle } from '../v3Types';

// ── 类型守卫 ────────────────────────────────────────────

function isTextContent(c: Content): c is TextContent {
  return 'chips' in c && 'separator' in c;
}

function isLogoContent(c: Content): c is LogoContent {
  return 'path' in c && 'color' in c && !('size_ratio' in c) && !('chips' in c);
}

function isSignatureContent(c: Content): c is SignatureContent {
  return 'path' in c && 'size_ratio' in c && !('chips' in c);
}

// ── 默认 Slot 内容工厂 ─────────────────────────────────

function defaultTextContent(): TextContent {
  return { chips: [], separator: ' ' };
}

function defaultLogoContent(): LogoContent {
  return { path: '', color: '#D8D8D6' };
}

function defaultSignatureContent(): SignatureContent {
  return { path: '', invert_mono: false, size_ratio: 0.20 };
}

function createDefaultSlot(type: 'text' | 'logo' | 'signature'): SlotConfig {
  return {
    enabled: false,
    content: type === 'text' ? defaultTextContent() : type === 'logo' ? defaultLogoContent() : defaultSignatureContent(),
    style: null,
  };
}

// ── Slot 标签 ──────────────────────────────────────────────

const FOOTER_SLOT_LABELS: Record<string, string> = {
  'left-logo': '左 Logo',
  'left-top': '左上文本',
  'left-bottom': '左下文本',
  'center': '中间文本',
  'right-top': '右上文本',
  'right-bottom': '右下文本',
  'right-logo': '右 Logo',
};

const ANCHOR_LABELS: Record<string, string> = {
  'top-left': '左上',
  'top-center': '上方居中',
  'top-right': '右上',
  'middle-left': '左侧居中',
  'middle-center': '正中心',
  'middle-right': '右侧居中',
  'bottom-left': '左下',
  'bottom-center': '下方居中',
  'bottom-right': '右下',
};

// ── 组件 Props ────────────────────────────────────────────

interface InspectorPanelV3Props {
  config: WatermarkConfigV3;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfigV3>>;
  diagnostics?: DiagnosticItem[];
}

// ── 布局诊断类型 ──────────────────────────────────────

export type DiagnosticSeverity = 'error' | 'warning';

export interface DiagnosticItem {
  id: string;
  type: string;
  severity: DiagnosticSeverity;
  message: string;
  elementIds?: string[];
}

// ── 主组件 ────────────────────────────────────────────

export function InspectorPanelV3({ config, setConfig, diagnostics = [] }: InspectorPanelV3Props) {
  const errors = diagnostics.filter((d) => d.severity === 'error');
  const warnings = diagnostics.filter((d) => d.severity === 'warning');

  return (
    <section className="inspector inspector-v3" aria-label="高级结构编辑">
      <div className="inspector-panel">
        <div className="inspector-tabs">
          <span className="inspector-heading">高级结构编辑</span>
        </div>

        <div className="inspector-body">
          <div className="v3-settings-content">
            {/* Diagnostics summary */}
            {errors.length > 0 && (
              <div className="v3-diagnostics v3-diagnostics-error">
                <strong>布局错误：</strong>
                <ul>
                  {errors.map((d) => (
                    <li key={d.id}>{d.message}</li>
                  ))}
                </ul>
              </div>
            )}
            {warnings.length > 0 && (
              <div className="v3-diagnostics v3-diagnostics-warning">
                <strong>布局警告：</strong>
                <ul>
                  {warnings.map((d) => (
                    <li key={d.id}>{d.message}</li>
                  ))}
                </ul>
              </div>
            )}

            <AdvancedStructureEditor config={config} setConfig={setConfig} diagnostics={diagnostics} />
          </div>
        </div>
      </div>
    </section>
  );
}

// ── 高级结构编辑器 ─────────────────────────────────

function AdvancedStructureEditor({
  config,
  setConfig,
  diagnostics,
}: {
  config: WatermarkConfigV3;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfigV3>>;
  diagnostics: DiagnosticItem[];
}) {
  const updateRegion = useCallback((regionId: string, patch: Partial<RegionConfig>) => {
    setConfig((prev) => ({
      ...prev,
      regions: prev.regions.map((r) => (r.id === regionId ? { ...r, ...patch } : r)),
    }));
  }, [setConfig]);

  const updateSlot = useCallback((regionId: string, slotId: string, patch: Partial<SlotConfig>) => {
    setConfig((prev) => ({
      ...prev,
      regions: prev.regions.map((r) => {
        if (r.id !== regionId) return r;
        const slots = { ...r.slots };
        const slot = slots[slotId] ?? createDefaultSlot('text');
        slots[slotId] = { ...slot, ...patch };
        return { ...r, slots };
      }),
    }));
  }, [setConfig]);

  return (
    <div className="anim-fade-in v3-advanced-editor">
      <div className="editor-card">
        <h3 className="editor-card-h3">高级结构编辑</h3>
        <p className="text-tertiary text-xs">
          以下设置会改变布局结构，请谨慎调整。
        </p>
      </div>

      {config.regions.map((region) => (
        <RegionEditor
          key={region.id}
          region={region}
          diagnostics={diagnostics}
          onUpdate={(patch) => updateRegion(region.id, patch)}
          onUpdateSlot={(slotId, patch) => updateSlot(region.id, slotId, patch)}
        />
      ))}

      <AdvancedTab config={config} setConfig={setConfig} />
    </div>
  );
}

// ── Region Editor ──────────────────────────────────────────

function RegionEditor({
  region,
  diagnostics,
  onUpdate,
  onUpdateSlot,
}: {
  region: RegionConfig;
  diagnostics: DiagnosticItem[];
  onUpdate: (patch: Partial<RegionConfig>) => void;
  onUpdateSlot: (slotId: string, patch: Partial<SlotConfig>) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const typeLabel =
    region.type === 'footer-bar' ? '底部水印条' :
    region.type === 'side-edge' ? '垂直边缘' :
    '自由定位';

  const regionErrors = diagnostics.filter((d) =>
    d.elementIds?.some((id) => id.startsWith(`${region.id}-`))
  );

  return (
    <div className={`editor-card ${regionErrors.length > 0 ? 'diagnostic-error' : ''}`}>
      <div className="editor-card-title">
        <h3>
          {region.id} <span className="text-tertiary text-xs">({typeLabel})</span>
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <label className="inline">
            <input
              type="checkbox"
              checked={region.enabled}
              onChange={(e) => onUpdate({ enabled: e.target.checked })}
            />
            <span className="text-xs">启用</span>
          </label>
          <button className="micro ghost" onClick={() => setExpanded((v) => !v)}>
            {expanded ? '收起' : '展开'}
          </button>
        </div>
      </div>

      {regionErrors.length > 0 && (
        <div className="v3-region-diagnostics">
          {regionErrors.map((d) => (
            <span key={d.id} className={`v3-diag-${d.severity}`}>{d.message}</span>
          ))}
        </div>
      )}

      {expanded && (
        <>
          {region.type === 'footer-bar' && (
            <FooterBarEditor region={region} diagnostics={diagnostics} onUpdateSlot={onUpdateSlot} />
          )}
          {region.type === 'side-edge' && (
            <SideEdgeEditor region={region} onUpdate={onUpdate} onUpdateSlot={onUpdateSlot} />
          )}
          {region.type === 'free' && (
            <FreeEditor region={region} onUpdate={onUpdate} onUpdateSlot={onUpdateSlot} />
          )}
        </>
      )}
    </div>
  );
}

// ── Footer Bar Editor ───────────────────────────────────

function FooterBarEditor({
  region,
  diagnostics,
  onUpdateSlot,
}: {
  region: RegionConfig;
  diagnostics: DiagnosticItem[];
  onUpdateSlot: (slotId: string, patch: Partial<SlotConfig>) => void;
}) {
  const slotOrder = ['left-logo', 'left-top', 'left-bottom', 'center', 'right-top', 'right-bottom', 'right-logo'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {slotOrder.map((slotId) => {
        const slot = region.slots?.[slotId];
        if (!slot) return null;
        const slotErrors = diagnostics.filter((d) =>
          d.elementIds?.includes(`${region.id}-${slotId}`)
        );
        return (
          <SlotRow
            key={slotId}
            label={FOOTER_SLOT_LABELS[slotId] ?? slotId}
            slot={slot}
            hasErrors={slotErrors.length > 0}
            onUpdate={(patch) => onUpdateSlot(slotId, patch)}
            defaultContentType={slotId.includes('logo') ? 'logo' : 'text'}
          />
        );
      })}
    </div>
  );
}

// ── Side Edge Editor ───────────────────────────────────

function SideEdgeEditor({
  region,
  onUpdate,
  onUpdateSlot,
}: {
  region: RegionConfig;
  onUpdate: (patch: Partial<RegionConfig>) => void;
  onUpdateSlot: (slotId: string, patch: Partial<SlotConfig>) => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="form-row" style={{ gap: 8 }}>
        <label>
          边缘
          <select value={region.edge ?? 'left'} onChange={(e) => onUpdate({ edge: e.target.value as 'left' | 'right' })}>
            <option value="left">左侧</option>
            <option value="right">右侧</option>
          </select>
        </label>
        <label>
          对齐
          <select value={region.alignment ?? 'start'} onChange={(e) => onUpdate({ alignment: e.target.value as 'start' | 'center' | 'end' })}>
            <option value="start">靠边缘</option>
            <option value="center">居中</option>
            <option value="end">远离边缘</option>
          </select>
        </label>
      </div>
      <label>
        区域宽度
        <div className="form-row" style={{ gap: 8 }}>
          <select
            value={region.width?.mode ?? 'short_edge_ratio'}
            onChange={(e) =>
              onUpdate({
                width: { mode: e.target.value as 'pixel' | 'short_edge_ratio', value: region.width?.value ?? 0.12 },
              })
            }
          >
            <option value="short_edge_ratio">短边比例</option>
            <option value="pixel">固定像素</option>
          </select>
          <input
            type="number"
            min={0}
            max={region.width?.mode === 'pixel' ? 500 : 0.5}
            step={region.width?.mode === 'pixel' ? 1 : 0.01}
            value={region.width?.value ?? 0.12}
            onChange={(e) =>
              onUpdate({
                width: { mode: region.width?.mode ?? 'short_edge_ratio', value: parseFloat(e.target.value) || 0 },
              })
            }
          />
        </div>
      </label>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Object.entries(region.slots ?? {}).map(([slotId, slot]) => (
          <SlotRow
            key={slotId}
            label={slotId}
            slot={slot}
            hasErrors={false}
            onUpdate={(patch) => onUpdateSlot(slotId, patch)}
            defaultContentType="text"
          />
        ))}
      </div>
    </div>
  );
}

// ── Free Editor ───────────────────────────────────────

function FreeEditor({
  region,
  onUpdate,
  onUpdateSlot,
}: {
  region: RegionConfig;
  onUpdate: (patch: Partial<RegionConfig>) => void;
  onUpdateSlot: (slotId: string, patch: Partial<SlotConfig>) => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <label>
        锚点
        <select
          value={region.anchor ?? 'bottom-right'}
          onChange={(e) => onUpdate({ anchor: e.target.value as RegionConfig['anchor'] })}
        >
          {Object.entries(ANCHOR_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <div className="form-row" style={{ gap: 8 }}>
        <label>
          X 偏移
          <input
            type="number"
            step={0.01}
            value={region.offset_x ?? 0}
            onChange={(e) => onUpdate({ offset_x: parseFloat(e.target.value) || 0 })}
          />
        </label>
        <label>
          Y 偏移
          <input
            type="number"
            step={0.01}
            value={region.offset_y ?? 0}
            onChange={(e) => onUpdate({ offset_y: parseFloat(e.target.value) || 0 })}
          />
        </label>
      </div>
      <label>
        偏移单位
        <select
          value={region.offset_unit ?? 'short_edge_ratio'}
          onChange={(e) => onUpdate({ offset_unit: e.target.value as 'pixel' | 'short_edge_ratio' })}
        >
          <option value="short_edge_ratio">短边比例</option>
          <option value="pixel">像素</option>
        </select>
      </label>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Object.entries(region.slots ?? {}).map(([slotId, slot]) => (
          <SlotRow
            key={slotId}
            label={slotId}
            slot={slot}
            hasErrors={false}
            onUpdate={(patch) => onUpdateSlot(slotId, patch)}
            defaultContentType="signature"
          />
        ))}
      </div>
    </div>
  );
}

// ── Slot Row ──────────────────────────────────────────

function SlotRow({
  label,
  slot,
  hasErrors,
  onUpdate,
  defaultContentType,
}: {
  label: string;
  slot: SlotConfig;
  hasErrors: boolean;
  onUpdate: (patch: Partial<SlotConfig>) => void;
  defaultContentType: 'text' | 'logo' | 'signature';
}) {
  const [expanded, setExpanded] = useState(false);

  const handleToggle = (checked: boolean) => {
    if (checked && !slot.content) {
      const defaultContent =
        defaultContentType === 'text'
          ? defaultTextContent()
          : defaultContentType === 'logo'
            ? defaultLogoContent()
            : defaultSignatureContent();
      onUpdate({ enabled: true, content: defaultContent });
    } else {
      onUpdate({ enabled: checked });
    }
  };

  return (
    <div className={`corner-block ${hasErrors ? 'diagnostic-error' : ''}`}>
      <div className="corner-block-header">
        <span className="corner-block-title">{label}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <label className="inline">
            <input type="checkbox" checked={slot.enabled} onChange={(e) => handleToggle(e.target.checked)} />
            <span className="text-xs">启用</span>
          </label>
          {slot.enabled && (
            <button className="micro ghost" onClick={() => setExpanded((v) => !v)}>
              {expanded ? '收起' : '编辑'}
            </button>
          )}
        </div>
      </div>

      {slot.enabled && expanded && slot.content && (
        <div style={{ marginTop: 8 }}>
          <ContentEditor
            content={slot.content}
            style={slot.style}
            onUpdateContent={(c) => onUpdate({ content: c })}
            onUpdateStyle={(s) => onUpdate({ style: s })}
          />
        </div>
      )}
    </div>
  );
}

// ── Content Editor ───────────────────────────────────────

function ContentEditor({
  content,
  style,
  onUpdateContent,
  onUpdateStyle,
}: {
  content: Content;
  style: StyleConfig | null;
  onUpdateContent: (c: Content) => void;
  onUpdateStyle: (s: StyleConfig | null) => void;
}) {
  const mergedStyle: StyleConfig = style ?? defaultStyle;
  const logoInputRef = useRef<HTMLInputElement>(null);
  const signatureInputRef = useRef<HTMLInputElement>(null);
  const [resourceStatus, setResourceStatus] = useState('');

  const uploadResource = async (file: File, kind: 'logo' | 'signature') => {
    setResourceStatus('上传中...');
    try {
      const result = await uploadResourceV3(file, kind);
      if (kind === 'logo' && isLogoContent(content)) {
        onUpdateContent({ ...content, path: result.resource_id });
      } else if (kind === 'signature' && isSignatureContent(content)) {
        onUpdateContent({ ...content, path: result.resource_id });
      }
      setResourceStatus('上传完成');
    } catch (error) {
      setResourceStatus(error instanceof Error ? error.message : '上传失败');
    }
  };

  if (isTextContent(content)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <ChipListEditor
          chips={content.chips}
          separator={content.separator}
          onUpdate={(chips, separator) => onUpdateContent({ chips, separator })}
        />
        <StyleEditor style={mergedStyle} onUpdate={onUpdateStyle} />
      </div>
    );
  }

  if (isLogoContent(content)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <label className="inline">
          <span className="text-sm" style={{ minWidth: 60 }}>
            颜色
          </span>
          <input
            type="color"
            value={content.color}
            onChange={(e) => onUpdateContent({ ...content, color: e.target.value })}
            style={{ width: 60, height: 32, padding: 2 }}
          />
        </label>
        <div className="resource-upload-row">
          <input
            ref={logoInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void uploadResource(file, 'logo');
              event.target.value = '';
            }}
          />
          <button className="small" onClick={() => logoInputRef.current?.click()}>
            {content.path ? '替换自定义 Logo' : '上传自定义 Logo'}
          </button>
          {content.path && (
            <button className="small ghost" onClick={() => onUpdateContent({ ...content, path: '' })}>
              使用自动 Logo
            </button>
          )}
          {resourceStatus && <span className="text-tertiary text-xs">{resourceStatus}</span>}
        </div>
      </div>
    );
  }

  if (isSignatureContent(content)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="resource-upload-row">
          <input
            ref={signatureInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void uploadResource(file, 'signature');
              event.target.value = '';
            }}
          />
          <button className="small" onClick={() => signatureInputRef.current?.click()}>
            {content.path ? '替换签名' : '上传签名'}
          </button>
          {content.path && (
            <button className="small ghost" onClick={() => onUpdateContent({ ...content, path: '' })}>
              清除
            </button>
          )}
          {resourceStatus && <span className="text-tertiary text-xs">{resourceStatus}</span>}
        </div>
        <label className="inline">
          <input
            type="checkbox"
            checked={content.invert_mono}
            onChange={(e) => onUpdateContent({ ...content, invert_mono: e.target.checked })}
          />
          <span className="text-sm">反色（白底）</span>
        </label>
        <label className="inline" style={{ flexDirection: 'row', gap: 8 }}>
          <span className="text-sm" style={{ minWidth: 60 }}>
            大小比例
          </span>
          <input
            type="number"
            min={0.01}
            max={1}
            step={0.01}
            value={content.size_ratio}
            onChange={(e) => onUpdateContent({ ...content, size_ratio: parseFloat(e.target.value) || 0.2 })}
            style={{ width: 100 }}
          />
        </label>
      </div>
    );
  }

  return null;
}

// ── Chip List Editor ───────────────────────────────────────

function ChipListEditor({
  chips,
  separator,
  onUpdate,
}: {
  chips: FieldChip[];
  separator: string;
  onUpdate: (chips: FieldChip[], separator: string) => void;
}) {
  const updateChip = (index: number, patch: Partial<FieldChip>) => {
    const next = chips.map((c, i) => (i === index ? { ...c, ...patch } : c));
    onUpdate(next, separator);
  };

  const addChip = () => {
    onUpdate([...chips, { field_id: 'camera_model' as FieldId }], separator);
  };

  const removeChip = (index: number) => {
    onUpdate(chips.filter((_, i) => i !== index), separator);
  };

  return (
    <div>
      <div className="chip-list">
        {chips.length === 0 && <p className="text-tertiary text-sm">— 无字段 —</p>}
        {chips.map((chip, i) => (
          <div key={`${chip.field_id}-${i}`} className="chip-item">
            <select
              value={chip.field_id}
              onChange={(e) => updateChip(i, { field_id: e.target.value as FieldId })}
            >
              {fieldOptionsV3.map((opt) => (
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
                onChange={(e) => updateChip(i, { custom_text: e.target.value })}
              />
            )}
            <button className="chip-remove" onClick={() => removeChip(i)}>
              ×
            </button>
          </div>
        ))}
      </div>
      <div className="form-row" style={{ gap: 8, marginTop: 8 }}>
        <button className="small" onClick={addChip}>
          + 字段
        </button>
        <label className="small-label">
          分隔符
          <input
            type="text"
            value={separator}
            onChange={(e) => onUpdate(chips, e.target.value)}
            style={{ width: 80 }}
          />
        </label>
      </div>
    </div>
  );
}

// ── Style Editor ───────────────────────────────────────

function StyleEditor({
  style,
  onUpdate,
}: {
  style: StyleConfig;
  onUpdate: (s: StyleConfig | null) => void;
}) {
  return (
    <div className="form-row" style={{ gap: 8, flexWrap: 'wrap' }}>
      <label className="small-label">
        字号比例
        <input
          type="number"
          min={0}
          max={0.5}
          step={0.005}
          value={style.font_size_ratio ?? 0}
          onChange={(e) => onUpdate({ ...style, font_size_ratio: parseFloat(e.target.value) || 0 })}
          style={{ width: 90 }}
        />
      </label>
      <label className="small-label">
        字号基准
        <select
          value={style.size_reference}
          onChange={(e) => onUpdate({ ...style, size_reference: e.target.value as StyleConfig['size_reference'] })}
          style={{ width: 110 }}
        >
          <option value="region_height">区域高度</option>
          <option value="short_edge">照片短边</option>
          <option value="long_edge">照片长边</option>
        </select>
      </label>
      <label className="small-label">
        颜色
        <input
          type="color"
          value={style.color}
          onChange={(e) => onUpdate({ ...style, color: e.target.value })}
          style={{ width: 50, height: 28, padding: 2 }}
        />
      </label>
      <label className="small-label">
        行高
        <input
          type="number"
          min={1}
          max={2}
          step={0.1}
          value={style.line_height}
          onChange={(e) => onUpdate({ ...style, line_height: parseFloat(e.target.value) || 1.2 })}
          style={{ width: 60 }}
        />
      </label>
    </div>
  );
}

// ── Advanced Tab ───────────────────────────────────────

function AdvancedTab({
  config,
  setConfig,
}: {
  config: WatermarkConfigV3;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfigV3>>;
}) {
  const updateCanvas = useCallback(
    (patch: Partial<WatermarkConfigV3['canvas']>) => {
      setConfig((prev) => ({ ...prev, canvas: { ...prev.canvas, ...patch } }));
    },
    [setConfig],
  );

  const updateDefaults = useCallback(
    (patch: Partial<StyleConfig>) => {
      setConfig((prev) => ({ ...prev, defaults: { ...prev.defaults, ...patch } }));
    },
    [setConfig],
  );

  const margins = config.canvas.margins;

  return (
    <div className="anim-fade-in v3-advanced-content">
      <div className="editor-card">
        <h3 className="editor-card-h3">画布</h3>
        <div className="form-row" style={{ gap: 8 }}>
          <label className="small-label">
            上边距
            <input
              type="number"
              min={0}
              max={500}
              value={margins.top}
              onChange={(e) => updateCanvas({ margins: { ...margins, top: Number(e.target.value) } })}
            />
          </label>
          <label className="small-label">
            下边距
            <input
              type="number"
              min={0}
              max={500}
              value={margins.bottom}
              onChange={(e) => updateCanvas({ margins: { ...margins, bottom: Number(e.target.value) } })}
            />
          </label>
        </div>
        <div className="form-row" style={{ gap: 8 }}>
          <label className="small-label">
            左边距
            <input
              type="number"
              min={0}
              max={500}
              value={margins.left}
              onChange={(e) => updateCanvas({ margins: { ...margins, left: Number(e.target.value) } })}
            />
          </label>
          <label className="small-label">
            右边距
            <input
              type="number"
              min={0}
              max={500}
              value={margins.right}
              onChange={(e) => updateCanvas({ margins: { ...margins, right: Number(e.target.value) } })}
            />
          </label>
        </div>
        <label className="inline">
          <span className="text-sm" style={{ minWidth: 60 }}>
            背景色
          </span>
          <input
            type="color"
            value={config.canvas.background}
            onChange={(e) => updateCanvas({ background: e.target.value })}
            style={{ width: 60, height: 32, padding: 2 }}
          />
        </label>
        <label className="small-label">
          圆角半径
          <input
            type="number"
            min={0}
            max={160}
            step={2}
            value={config.canvas.border_radius}
            onChange={(e) => updateCanvas({ border_radius: Number(e.target.value) })}
          />
        </label>
      </div>

      <div className="editor-card">
        <h3 className="editor-card-h3">全局默认样式</h3>
        <div className="form-row" style={{ gap: 8 }}>
          <label className="small-label">
            字号比例
            <input
              type="number"
              min={0}
              max={0.5}
              step={0.005}
              value={config.defaults.font_size_ratio ?? 0}
              onChange={(e) => updateDefaults({ font_size_ratio: parseFloat(e.target.value) || 0 })}
            />
          </label>
          <label className="small-label">
            颜色
            <input
              type="color"
              value={config.defaults.color}
              onChange={(e) => updateDefaults({ color: e.target.value })}
              style={{ width: 50, height: 28, padding: 2 }}
            />
          </label>
        </div>
        <div className="form-row" style={{ gap: 8 }}>
          <label className="small-label">
            字体
            <select
              value={config.defaults.font_family}
              onChange={(e) => updateDefaults({ font_family: e.target.value as StyleConfig['font_family'] })}
            >
              <option value="NotoSansCJKsc-Regular.otf">Noto Sans CJK SC Regular</option>
              <option value="NotoSansCJKsc-Bold.otf">Noto Sans CJK SC Bold</option>
            </select>
          </label>
          <label className="inline">
            <input type="checkbox" checked={config.defaults.bold} onChange={(e) => updateDefaults({ bold: e.target.checked })} />
            <span className="text-sm">加粗</span>
          </label>
        </div>
      </div>
    </div>
  );
}
