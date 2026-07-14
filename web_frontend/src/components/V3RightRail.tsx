import { useCallback, useMemo, useState } from 'react';
import {
  type MainControlConfig,
  type WatermarkConfigV3,
  applyMainControls,
  inferMainControls,
} from '../v3Types';
import { InspectorPanelV3 } from './InspectorPanelV3';
import { V3StyleControls, V3ResourceControls, V3LogoPositionControls } from './V3MainControls';

interface V3RightRailProps {
  config: WatermarkConfigV3;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfigV3>>;
  diagnostics?: DiagnosticItem[];
}

export type DiagnosticItem = {
  id: string;
  type: string;
  severity: 'error' | 'warning';
  message: string;
  elementIds?: string[];
};

export function V3RightRail({ config, setConfig, diagnostics }: V3RightRailProps) {
  const controls = useMemo(() => inferMainControls(config), [config]);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const updateControls = useCallback(
    (patch: Partial<MainControlConfig>) => {
      const next = { ...controls, ...patch };
      setConfig(applyMainControls(config, next));
    },
    [config, controls, setConfig],
  );

  return (
    <aside className="v3-right-rail" aria-label="样式、资源和高级设置">
      <V3StyleControls controls={controls} onChange={updateControls} />
      <V3ResourceControls controls={controls} onChange={updateControls} />
      <V3LogoPositionControls controls={controls} onChange={updateControls} />

      <div className="v3-right-section">
        <div className="v3-right-section-title">高级设置</div>
        <div className="v3-right-section-body">
          <button
            className="v3-btn v3-btn-sm v3-btn-ghost"
            onClick={() => setAdvancedOpen(v => !v)}
          >
            {advancedOpen ? '收起高级' : '编辑结构'}
          </button>
          {advancedOpen && (
            <div className="v3-advanced-panel">
              <InspectorPanelV3 config={config} setConfig={setConfig} diagnostics={diagnostics} />
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
