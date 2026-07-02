import { useContext } from 'react';
import { AppContext } from '../main';

export function TopBar() {
  const ctx = useContext(AppContext);
  if (!ctx) return null;

  const { files, status, message, result, runPreview, runProcess, runProcessAll, progress } = ctx;
  const hasFiles = files.length > 0;
  const isRunning = status === 'running';

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <div className="topbar-brand-icon">W</div>
        <div className="topbar-brand-text">
          <span className="topbar-brand-title">极简水印</span>
          <span className="topbar-brand-sub">aka-semi-utils Web</span>
        </div>
      </div>

      <div className="topbar-actions">
        <div className="topbar-status" data-status={status}>
          {isRunning && <span className="spinner" style={{ width: 14, height: 14 }} />}
          {!isRunning && status === 'success' && <span className="status-dot success" />}
          {!isRunning && status === 'error' && <span className="status-dot error" />}
          {!isRunning && status === 'idle' && <span className="status-dot idle" />}
          <span className={isRunning ? 'text-accent' : status === 'success' ? 'text-success' : status === 'error' ? 'text-error' : 'text-secondary'}>
            {message}
          </span>
          {hasFiles && (
            <span className="text-tertiary" style={{ marginLeft: 4 }}>
              · {files.length} 张
            </span>
          )}
        </div>

        {isRunning && (
          <div style={{ width: 120, display: 'flex', alignItems: 'center' }}>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        <button
          className="ghost"
          disabled={!hasFiles || isRunning}
          onClick={() => void runPreview()}
          title="刷新预览"
        >
          ↻ 预览
        </button>

        <button
          className="primary"
          disabled={!hasFiles || isRunning}
          onClick={() => void runProcess()}
        >
          处理当前
        </button>

        <button
          className="primary"
          disabled={!hasFiles || isRunning}
          onClick={() => void runProcessAll()}
        >
          处理全部
        </button>

        {result && (
          <a
            className="btn success"
            href={result.download_url}
            download={result.filename}
          >
            ↓ 下载
          </a>
        )}
      </div>
    </header>
  );
}
