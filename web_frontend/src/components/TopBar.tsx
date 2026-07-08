import { useCallback, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppContext } from '../HomePage';

export function TopBar() {
  const ctx = useContext(AppContext);
  const navigate = useNavigate();
  if (!ctx) return null;

  const { files, status, message, result, batchResults, runPreview, runProcess, runProcessAll, progress, clearBatchResults } = ctx;
  const hasFiles = files.length > 0;
  const isRunning = status === 'running';

  const downloadBatch = useCallback(() => {
    batchResults.forEach((file, i) => {
      const a = document.createElement('a');
      a.href = file.download_url;
      a.download = file.download_filename || file.filename;
      a.style.display = 'none';
      document.body.appendChild(a);
      setTimeout(() => {
        a.click();
        document.body.removeChild(a);
      }, i * 300); // stagger downloads to avoid browser blocking
    });
  }, [batchResults]);

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

        {batchResults.length > 0 && (
          <>
            <button
              className="success"
              onClick={downloadBatch}
              title={`下载全部 ${batchResults.length} 张已处理图片`}
            >
              ↓ 下载全部 ({batchResults.length})
            </button>
            <button
              className="ghost micro"
              onClick={clearBatchResults}
              title="清除下载列表"
            >
              ✕
            </button>
          </>
        )}

        {result && (
          <a
            className="btn success"
            href={result.download_url}
            download={result.filename}
          >
            ↓ 下载
          </a>
        )}

        <button
          className="dev-entry-btn"
          onClick={() => navigate('/_dev')}
          title="开发者面板"
          aria-label="开发者面板"
        />
      </div>
    </header>
  );
}
