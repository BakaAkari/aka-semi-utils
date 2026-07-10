import { useCallback } from 'react';
import type { CornerConfig, CornerKey, FieldChip, FieldId, SideKey, WatermarkConfig } from '../watermarkConfig';
import { cornerLabels, sideLabels, fieldOptions } from '../watermarkConfig';

// ==================== WatermarkBar ====================

export function WatermarkBar({
  config,
  setConfig,
}: {
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
}) {
  const isSides = (config.layout_mode ?? 'corners') === 'sides';

  return (
    <div className="watermark-bar">
      {!isSides && <CornersBar config={config} setConfig={setConfig} />}
      {isSides && <SidesBar config={config} setConfig={setConfig} />}

      <div className="watermark-bar-footer">
        <LayoutToggle config={config} setConfig={setConfig} />
      </div>
    </div>
  );
}

function LayoutToggle({
  config,
  setConfig,
}: {
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
}) {
  return (
    <label className="layout-toggle">
      布局
      <select
        value={config.layout_mode ?? 'corners'}
        onChange={e =>
          setConfig(prev => ({ ...prev, layout_mode: e.target.value as 'corners' | 'sides' }))
        }
      >
        <option value="corners">四角</option>
        <option value="sides">左右居中</option>
      </select>
    </label>
  );
}

// ==================== Corners bar ====================

function CornersBar({
  config,
  setConfig,
}: {
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
}) {
  const cornerKeys: CornerKey[] = ['left_top', 'left_bottom', 'right_top', 'right_bottom'];

  const updateCorner = useCallback(
    (k: CornerKey, patch: Partial<CornerConfig>) => {
      setConfig(prev => ({
        ...prev,
        corners: { ...prev.corners, [k]: { ...prev.corners[k], ...patch } },
      }));
    },
    [setConfig],
  );

  const updateChip = useCallback(
    (k: CornerKey, i: number, patch: Partial<FieldChip>) => {
      setConfig(prev => {
        const chips = [...prev.corners[k].chips];
        chips[i] = { ...chips[i], ...patch };
        return { ...prev, corners: { ...prev.corners, [k]: { ...prev.corners[k], chips } } };
      });
    },
    [setConfig],
  );

  const addChip = useCallback(
    (k: CornerKey) => {
      setConfig(prev => {
        const chips = [...prev.corners[k].chips, { field_id: 'camera_model' as FieldId }];
        return { ...prev, corners: { ...prev.corners, [k]: { ...prev.corners[k], chips } } };
      });
    },
    [setConfig],
  );

  const removeChip = useCallback(
    (k: CornerKey, i: number) => {
      setConfig(prev => {
        const chips = prev.corners[k].chips.filter((_, idx) => idx !== i);
        return { ...prev, corners: { ...prev.corners, [k]: { ...prev.corners[k], chips } } };
      });
    },
    [setConfig],
  );

  return (
    <div className="corners-grid">
      {cornerKeys.map(key => (
        <ChipEditor
          key={key}
          label={cornerLabels[key]}
          corner={config.corners[key]}
          updateCorner={patch => updateCorner(key, patch)}
          updateChip={(i, p) => updateChip(key, i, p)}
          addChip={() => addChip(key)}
          removeChip={i => removeChip(key, i)}
        />
      ))}
    </div>
  );
}

// ==================== Sides bar ====================

function SidesBar({
  config,
  setConfig,
}: {
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
}) {
  const sideKeys: SideKey[] = ['left', 'right'];

  const updateSide = useCallback(
    (k: SideKey, patch: Partial<CornerConfig>) => {
      setConfig(prev => ({
        ...prev,
        sides: { ...prev.sides, [k]: { ...prev.sides[k], ...patch } },
      }));
    },
    [setConfig],
  );

  const updateSideChip = useCallback(
    (k: SideKey, i: number, patch: Partial<FieldChip>) => {
      setConfig(prev => {
        const chips = [...prev.sides[k].chips];
        chips[i] = { ...chips[i], ...patch };
        return { ...prev, sides: { ...prev.sides, [k]: { ...prev.sides[k], chips } } };
      });
    },
    [setConfig],
  );

  const addSideChip = useCallback(
    (k: SideKey) => {
      setConfig(prev => {
        const chips = [...prev.sides[k].chips, { field_id: 'camera_model' as FieldId }];
        return { ...prev, sides: { ...prev.sides, [k]: { ...prev.sides[k], chips } } };
      });
    },
    [setConfig],
  );

  const removeSideChip = useCallback(
    (k: SideKey, i: number) => {
      setConfig(prev => {
        const chips = prev.sides[k].chips.filter((_, idx) => idx !== i);
        return { ...prev, sides: { ...prev.sides, [k]: { ...prev.sides[k], chips } } };
      });
    },
    [setConfig],
  );

  return (
    <div className="sides-grid">
      {sideKeys.map(key => (
        <ChipEditor
          key={key}
          label={sideLabels[key]}
          corner={config.sides[key]}
          updateCorner={patch => updateSide(key, patch)}
          updateChip={(i, p) => updateSideChip(key, i, p)}
          addChip={() => addSideChip(key)}
          removeChip={i => removeSideChip(key, i)}
        />
      ))}
    </div>
  );
}

// ==================== Chip editor (reusable) ====================

function ChipEditor({
  label,
  corner,
  updateCorner,
  updateChip,
  addChip,
  removeChip,
}: {
  label: string;
  corner: CornerConfig;
  updateCorner: (patch: Partial<CornerConfig>) => void;
  updateChip: (index: number, patch: Partial<FieldChip>) => void;
  addChip: () => void;
  removeChip: (index: number) => void;
}) {
  return (
    <div className="chip-editor">
      <div className="chip-editor-header">
        <span className="chip-editor-label">{label}</span>
        <button className="micro ghost" onClick={addChip}>+</button>
      </div>
      <div className="chip-editor-chips">
        {corner.chips.length === 0 && <span className="chip-empty">—</span>}
        {corner.chips.map((chip, i) => (
          <div key={i} className="chip-row">
            <select
              value={chip.field_id}
              onChange={e => updateChip(i, { field_id: e.target.value as FieldId })}
            >
              {fieldOptions.map(opt => (
                <option key={opt.id} value={opt.id}>{opt.label}</option>
              ))}
            </select>
            {chip.field_id === 'custom_text' && (
              <input
                type="text"
                value={chip.custom_text ?? ''}
                onChange={e => updateChip(i, { custom_text: e.target.value })}
                placeholder="输入文本"
                style={{ width: 80 }}
              />
            )}
            <button className="micro ghost" onClick={() => removeChip(i)}>×</button>
          </div>
        ))}
      </div>
    </div>
  );
}
