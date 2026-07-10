/**
 * V3 Inspector Panel — Region/Slot 模型配置面板
 *
 * 与 V2 的区别：
 * - 不再使用 corners/sides，改用 Region 列表
 * - 每个 Region 包含若干 Slot
 * - 声明式配置，与渲染解耦
 */

import { useCallback, useState } from 'react';
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
} from '../v3Types';
import {
  fieldOptionsV3,
  presetDefaultV3,
  presetMinimalV3,
  presetSoftCardV3,
  presetSidesV3,
  defaultStyle,
} from '../v3Types';
import type { FieldId } from '../watermarkConfig';

// ── 预设列表 ──────────────────────────────────────────────────────────

const V3_PRESETS: { id: string; name: string; description: string; config: WatermarkConfigV3 }[] = [
  { id: 'default', name: '默认排版', description: '底部栏：左上品牌+型号，左下参数，右侧自动 Logo', config: presetDefaultV3 },
  { id: 'minimal', name: '极简参数', description: '仅右下显示核心拍摄参数', config: presetMinimalV3 },
  { id: 'soft-card', name: '圆角卡片', description: '圆角+高底栏，适合社交媒体', config: presetSoftCardV3 },
  { id: 'sides', name: '左右居中', description: '底部 Logo + 左侧垂直参数', config: presetSidesV3 },
];

// ── 类型守卫 ──────────────────────────────────────────────────────────

function isTextContent(c: Content): c is TextContent {
  return 'chips' in c && 'separator' in c;
}

function isLogoContent(c: Content): c is LogoContent {
  return 'path' in c && 'color' in c && !('size_ratio' in c) && !('chips' in c);
}

function isSignatureContent(c: Content): c is SignatureContent {
  return 'path' in c && 'size_ratio' in c && !('chips' in c);
}

// ── 默认 Slot 内容工厂 ────────────────────────────────────────────────

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

// ── Slot 标签 ─────────────────────────────────────────────────────────

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
  top_left: '左上',
  top_center: '上方居中',
  top_right: '右上',
  middle_left: '左侧居中',
  middle_center: '正中心',
  middle_right: '右侧居中',
  bottom_left: '左下',
  bottom_center: '下方居中',
  bottom_right: '右下',
};

// ── 组件 Props ────────────────────────────────────────────────────────

interface InspectorPanelV3Props {
  config: WatermarkConfigV3;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfigV3>>;
}

// ── 主组件 ────────────────────────────────────────────────────────────

export function InspectorPanelV3({ config, setConfig }: InspectorPanelV3Props) {
  const [tab, setTab] = useState<'regions' | 'advanced'>('regions');

  const applyPreset = useCallback((presetConfig: WatermarkConfigV3) => {
    setConfig(structuredClone(presetConfig));
  }, [setConfig]);

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

  const removeRegion = useCallback((regionId: string) => {
    setConfig((prev) => ({
      ...prev,
      regions: prev.regions.filter((r) => r.id !== regionId),
    }));
  }, [setConfig]);

  const addRegion = useCallback((type: RegionType) => {
    const id = `${type}-${Date.now()}`;
    const base: RegionConfig = {
      id,
      type,
      enabled: true,
    };
    if (type === 'footer-bar') {
      base.slots = {
        'left-logo': createDefaultSlot('logo'),
        'left-top': createDefaultSlot('text'),
        'left-bottom': createDefaultSlot('text'),
        'center': createDefaultSlot('text'),
        'right-top': createDefaultSlot('text'),
        'right-bottom': createDefaultSlot('text'),
        'right-logo': createDefaultSlot('logo'),
      };
    } else if (type === 'side-edge') {
      base.edge = 'left';
      base.width = { mode: 'short_edge_ratio', value: 0.12 };
      base.alignment = 'start';
      base.slots = { line1: createDefaultSlot('text') };
    } else if (type === 'free') {
      base.anchor = 'bottom_right';
      base.offset_x = 0.05;
      base.offset_y = 0.05;
      base.offset_unit = 'short_edge_ratio';
      base.slots = { sig1: createDefaultSlot('signature') };
    }
    setConfig((prev) => ({ ...prev, regions: [...prev.regions, base] }));
  }, [setConfig]);

  return (
    <aside className="inspector">
      <div className="inspector-panel">
        {/* Tabs */}
        <div className="inspector-tabs">
          <button className={`inspector-tab ${tab === 'regions' ? 'active' : ''}`} onClick={() => setTab('regions')}>
            区域
          </button>
          <button className={`inspector-tab ${tab === 'advanced' ? 'active' : ''}`} onClick={() => setTab('advanced')}>
            高级
          </button>
        </div>

        {/* Body */}
        <div className="inspector-body">
          {/* Regions Tab */}
          <div className={`tab-panel ${tab === 'regions' ? 'active' : ''}`}>
            <div className="anim-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {/* Presets */}
              <div className="editor-card">
                <h3 className="editor-card-h3">预设</h3>
                <div className="preset-list">
                  {V3_PRESETS.map((p) => (
                    <button key={p.id} className="preset-card" onClick={() => applyPreset(p.config)}>
                      <span className="preset-card-name">{p.name}</span>
                      <span className="preset-card-desc">{p.description}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Global custom text */}
              <div className="editor-card">
                <label>
                  全局自定义文本
                  <input
                    type="text"
                    value={config.custom_text ?? ''}
                    placeholder="用于替换自定义文本字段"
                    onChange={(e) => setConfig((prev) => ({ ...prev, custom_text: e.target.value }))}
                  />
                </label>
              </div>

              {/* Region list */}
              {config.regions.map((region) => (
                <RegionEditor
                  key={region.id}
                  region={region}
                  onUpdate={(patch) => updateRegion(region.id, patch)}
                  onRemove={() => removeRegion(region.id)}
                  onUpdateSlot={(slotId, patch) => updateSlot(region.id, slotId, patch)}
                />
              ))}

              {/* Add Region */}
              <div className="form-row" style={{ gap: 8 }}>
                <button className="small" onClick={() => addRegion('footer-bar')}>+ 底栏</button>
                <button className="small" onClick={() => addRegion('side-edge')}>+ 侧边</button>
                <button className="small" onClick={() => addRegion('free')}>+ 自由</button>
              </div>
            </div>
          </div>

          {/* Advanced Tab */}
          <div className={`tab-panel ${tab === 'advanced' ? 'active' : ''}`}>
            <AdvancedTab config={config} setConfig={setConfig} />
          </div>
        </div>
      </div>
    </aside>
  );
}

// ── Region Editor ─────────────────────────────────────────────────────

function RegionEditor({
  region,
  onUpdate,
  onRemove,
  onUpdateSlot,
}: {
  region: RegionConfig;
  onUpdate: (patch: Partial<RegionConfig>) => void;
  onRemove: () => void;
  onUpdateSlot: (slotId: string, patch: Partial<SlotConfig>) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  const typeLabel =
    region.type === 'footer-bar' ? '底部水印条' :
    region.type === 'side-edge' ? '垂直边缘' :
    '自由定位';

  return (
    <div className="editor-card">
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
          <button className="micro danger" onClick={onRemove}>
            删除
          </button>
        </div>
      </div>

      {expanded && (
        <>
          {region.type === 'footer-bar' && (
            <FooterBarEditor region={region} onUpdateSlot={onUpdateSlot} />
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

// ── Footer Bar Editor ─────────────────────────────────────────────────

function FooterBarEditor({
  region,
  onUpdateSlot,
}: {
  region: RegionConfig;
  onUpdateSlot: (slotId: string, patch: Partial<SlotConfig>) => void;
}) {
  const slotOrder = ['left-logo', 'left-top', 'left-bottom', 'center', 'right-top', 'right-bottom', 'right-logo'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {slotOrder.map((slotId) => {
        const slot = region.slots?.[slotId];
        if (!slot) return null;
        return (
          <SlotRow
            key={slotId}
            label={FOOTER_SLOT_LABELS[slotId] ?? slotId}
            slot={slot}
            onUpdate={(patch) => onUpdateSlot(slotId, patch)}
            defaultContentType={slotId.includes('logo') ? 'logo' : 'text'}
          />
        );
      })}
    </div>
  );
}

// ── Side Edge Editor ──────────────────────────────────────────────────

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

      {/* Slots */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Object.entries(region.slots ?? {}).map(([slotId, slot]) => (
          <SlotRow
            key={slotId}
            label={slotId}
            slot={slot}
            onUpdate={(patch) => onUpdateSlot(slotId, patch)}
            defaultContentType="text"
          />
        ))}
      </div>

      <button
        className="small"
        onClick={() => {
          const newId = `line${Object.keys(region.slots ?? {}).length + 1}`;
          onUpdateSlot(newId, { enabled: true, content: defaultTextContent(), style: null });
        }}
      >
        + 添加文本行
      </button>
    </div>
  );
}

// ── Free Editor ───────────────────────────────────────────────────────

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
        <select value={region.anchor ?? 'bottom_right'} onChange={(e) => onUpdate({ anchor: e.target.value })}>
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

      {/* Slots */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Object.entries(region.slots ?? {}).map(([slotId, slot]) => (
          <SlotRow
            key={slotId}
            label={slotId}
            slot={slot}
            onUpdate={(patch) => onUpdateSlot(slotId, patch)}
            defaultContentType="signature"
          />
        ))}
      </div>

      <button
        className="small"
        onClick={() => {
          const newId = `sig${Object.keys(region.slots ?? {}).length + 1}`;
          onUpdateSlot(newId, { enabled: true, content: defaultSignatureContent(), style: null });
        }}
      >
        + 添加签名
      </button>
    </div>
  );
}

// ── Slot Row ──────────────────────────────────────────────────────────

function SlotRow({
  label,
  slot,
  onUpdate,
  defaultContentType,
}: {
  label: string;
  slot: SlotConfig;
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
    <div className="corner-block">
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

// ── Content Editor ────────────────────────────────────────────────────

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
        <label className="inline">
          <span className="text-sm" style={{ minWidth: 60 }}>
            路径
          </span>
          <input
            type="text"
            value={content.path}
            placeholder="空 = 自动识别"
            onChange={(e) => onUpdateContent({ ...content, path: e.target.value })}
          />
        </label>
      </div>
    );
  }

  if (isSignatureContent(content)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
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

// ── Chip List Editor ──────────────────────────────────────────────────

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

// ── Style Editor ──────────────────────────────────────────────────────

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

// ── Advanced Tab ──────────────────────────────────────────────────────

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
    <div className="anim-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Canvas */}
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

      {/* Defaults */}
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
            <input
              type="text"
              value={config.defaults.font_family}
              onChange={(e) => updateDefaults({ font_family: e.target.value })}
            />
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
