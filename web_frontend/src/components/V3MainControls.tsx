import React, { useCallback, useMemo, useRef, useState } from 'react';
import {
  type FieldChip,
  type FieldId,
  type FooterMode,
  type LogoPosition,
  type MainControlConfig,
  type PresetColor,
  type PresetDensity,
  type PresetSize,
  type WatermarkConfigV3,
  FOOTER_MODE_LABELS,
  LOGO_POSITION_LABELS,
  applyMainControls,
  fieldOptionsV3,
  getFieldLabel,
  inferMainControls,
} from '../v3Types';
import type { DiagnosticItem } from '../v3_layout/layoutEngine';

interface V3MainControlsProps {
  config: WatermarkConfigV3;
  onChange: (config: WatermarkConfigV3) => void;
  diagnostics?: DiagnosticItem[];
}

export default function V3MainControls({ config, onChange, diagnostics }: V3MainControlsProps) {
  const controls = useMemo(() => inferMainControls(config), [config]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [addingFor, setAddingFor] = useState<string | null>(null);

  const updateControls = useCallback(
    (patch: Partial<MainControlConfig>) => {
      const next = { ...controls, ...patch };
      onChange(applyMainControls(config, next));
    },
    [config, controls, onChange],
  );

  const rows = useMemo(() => {
    const isDual = controls.footer_mode === 'dual-row';
    return isDual
      ? [
          { id: 'top_left', label: '左上', chips: controls.top_left },
          { id: 'bottom_left', label: '左下', chips: controls.bottom_left },
          { id: 'top_right', label: '右上', chips: controls.top_right },
          { id: 'bottom_right', label: '右下', chips: controls.bottom_right },
        ]
      : [
          { id: 'left_row', label: '左排', chips: controls.left_row },
          { id: 'right_row', label: '右排', chips: controls.right_row },
        ];
  }, [controls]);

  const updateRow = useCallback(
    (rowId: string, chips: FieldChip[]) => {
      const patch: Partial<MainControlConfig> = {};
      patch[rowId as keyof MainControlConfig] = chips as any;
      updateControls(patch);
    },
    [updateControls],
  );

  const handleAddChip = useCallback(
    (rowId: string, fieldId: FieldId) => {
      const row = rows.find(r => r.id === rowId);
      if (!row) return;
      const next = [...row.chips, { field_id: fieldId }];
      updateRow(rowId, next);
      setAddingFor(null);
    },
    [rows, updateRow],
  );

  const handleRemoveChip = useCallback(
    (rowId: string, idx: number) => {
      const row = rows.find(r => r.id === rowId);
      if (!row) return;
      const next = [...row.chips];
      next.splice(idx, 1);
      updateRow(rowId, next);
    },
    [rows, updateRow],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        const path = String(reader.result ?? '');
        updateControls({ logo_path: path });
      };
      reader.readAsDataURL(file);
      e.target.value = '';
    },
    [updateControls],
  );

  return (
    <div className="v3-main-controls">
      <div className="v3-footer-bar">
        <div className="v3-footer-bar-header">
          <div className="v3-footer-bar-title">底部水印栏</div>
          <div className="v3-footer-bar-actions">
            <button
              className="v3-btn v3-btn-sm"
              onClick={() =>
                updateControls({
                  footer_mode: controls.footer_mode === 'dual-row' ? 'single-row' : 'dual-row',
                })
              }
              title="切换左右双排/单排"
            >
              {FOOTER_MODE_LABELS[controls.footer_mode]}
            </button>
          </div>
        </div>
        <div className="v3-footer-bar-rows">
          {rows.map(row => (
            <div key={row.id} className="v3-footer-row">
              <div className="v3-footer-row-label">{row.label}</div>
              <div className="v3-footer-row-chips">
                {row.chips.map((chip: FieldChip, idx: number) => (
                  <div key={`${row.id}-${idx}`} className="v3-field-chip">
                    <span>{getFieldLabel(chip.field_id)}</span>
                    <button
                      className="v3-chip-remove"
                      onClick={() => handleRemoveChip(row.id, idx)}
                      title="移除"
                    >
                      ×
                    </button>
                  </div>
                ))}
                {addingFor === row.id ? (
                  <select
                    className="v3-chip-select"
                    autoFocus
                    value=""
                    onChange={(e) => handleAddChip(row.id, e.target.value as FieldId)}
                    onBlur={() => setAddingFor(null)}
                  >
                    <option value="" disabled>
                      选择字段...
                    </option>
                    {fieldOptionsV3
                      .filter((o: { id: FieldId; label: string }) => !row.chips.some((c: FieldChip) => c.field_id === o.id))
                      .map((o: { id: FieldId; label: string }) => (
                        <option key={o.id} value={o.id}>
                          {o.label}
                        </option>
                      ))}
                  </select>
                ) : (
                  <button className="v3-add-chip" onClick={() => setAddingFor(row.id)}>
                    +
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="v3-hidden-input"
        onChange={handleFileChange}
      />
    </div>
  );
}

export function V3StyleControls({
  controls,
  onChange,
}: {
  controls: MainControlConfig;
  onChange: (patch: Partial<MainControlConfig>) => void;
}) {
  return (
    <div className="v3-right-section">
      <div className="v3-right-section-title">样式</div>
      <div className="v3-right-section-body">
        <div className="v3-form-row">
          <label>大小</label>
          <select
            value={controls.size}
            onChange={(e) => onChange({ size: e.target.value as PresetSize })}
          >
            {(['small', 'medium', 'large'] as PresetSize[]).map(s => (
              <option key={s} value={s}>
                {s === 'small' ? '小' : s === 'medium' ? '中' : '大'}
              </option>
            ))}
          </select>
        </div>
        <div className="v3-form-row">
          <label>颜色</label>
          <select
            value={controls.color}
            onChange={(e) => onChange({ color: e.target.value as PresetColor })}
          >
            {(['black', 'white', 'warm-gray', 'auto'] as PresetColor[]).map(c => (
              <option key={c} value={c}>
                {c === 'black' ? '黑色' : c === 'white' ? '白色' : c === 'warm-gray' ? '暖灰' : '自动'}
              </option>
            ))}
          </select>
        </div>
        <div className="v3-form-row">
          <label>密度</label>
          <select
            value={controls.density}
            onChange={(e) => onChange({ density: e.target.value as PresetDensity })}
          >
            {(['compact', 'standard', 'loose'] as PresetDensity[]).map(d => (
              <option key={d} value={d}>
                {d === 'compact' ? '紧凑' : d === 'standard' ? '标准' : '松散'}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

export function V3ResourceControls({
  controls,
  onChange,
}: {
  controls: MainControlConfig;
  onChange: (patch: Partial<MainControlConfig>) => void;
}) {
  const logoInputRef = useRef<HTMLInputElement>(null);
  const sigInputRef = useRef<HTMLInputElement>(null);

  const handleLogoChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => onChange({ logo_path: String(reader.result ?? '') });
      reader.readAsDataURL(file);
      e.target.value = '';
    },
    [onChange],
  );

  const handleSignatureChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => onChange({ signature_path: String(reader.result ?? '') });
      reader.readAsDataURL(file);
      e.target.value = '';
    },
    [onChange],
  );

  return (
    <div className="v3-right-section">
      <div className="v3-right-section-title">资源</div>
      <div className="v3-right-section-body">
        <div className="v3-form-row">
          <label>Logo</label>
          <div className="v3-file-row">
            <button className="v3-btn v3-btn-sm" onClick={() => logoInputRef.current?.click()}>
              {controls.logo_path ? '更换' : '上传'}
            </button>
            {controls.logo_path && (
              <button className="v3-btn v3-btn-sm v3-btn-ghost" onClick={() => onChange({ logo_path: '' })}>
                清除
              </button>
            )}
            <input ref={logoInputRef} type="file" accept="image/*" className="v3-hidden-input" onChange={handleLogoChange} />
          </div>
        </div>
        <div className="v3-form-row">
          <label>签名</label>
          <div className="v3-file-row">
            <button className="v3-btn v3-btn-sm" onClick={() => sigInputRef.current?.click()}>
              {controls.signature_path ? '更换' : '上传'}
            </button>
            {controls.signature_path && (
              <button className="v3-btn v3-btn-sm v3-btn-ghost" onClick={() => onChange({ signature_path: '' })}>
                清除
              </button>
            )}
            <input ref={sigInputRef} type="file" accept="image/*" className="v3-hidden-input" onChange={handleSignatureChange} />
          </div>
        </div>
      </div>
    </div>
  );
}

export function V3LogoPositionControls({
  controls,
  onChange,
}: {
  controls: MainControlConfig;
  onChange: (patch: Partial<MainControlConfig>) => void;
}) {
  return (
    <div className="v3-right-section">
      <div className="v3-right-section-title">Logo 位置</div>
      <div className="v3-right-section-body">
        <div className="v3-segmented-group">
          {(Object.keys(LOGO_POSITION_LABELS) as LogoPosition[]).map(pos => (
            <button
              key={pos}
              className={`v3-segment ${controls.logo_position === pos ? 'active' : ''}`}
              onClick={() => onChange({ logo_position: pos })}
            >
              {LOGO_POSITION_LABELS[pos]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export type { FieldChip, FieldId, FooterMode, LogoPosition, MainControlConfig, PresetColor, PresetDensity, PresetSize };
