import type { V3AppContextType } from '../V3HomePage';

export type TopBarController = Pick<
  V3AppContextType,
  | 'files'
  | 'status'
  | 'message'
  | 'result'
  | 'batchResults'
  | 'progress'
  | 'runProcess'
  | 'runProcessAll'
  | 'clearBatchResults'
  | 'loadPreview'
>;

export function TopBar({ controller: ctx }: { controller: TopBarController }) {

  const { files, status, message, result, batchResults, progress, runProcess, runProcessAll, clearBatchResults, loadPreview } = ctx;
  const hasFiles = files.length > 0;
  const isRunning = status === 'running';
  const isMulti = files.length > 1;

  const handleProcess = () => {
    if (isMulti) {
      void runProcessAll();
    } else {
      void runProcess();
    }
  };

  const downloadBatch = () => {
    batchResults.forEach((file, i) => {
      const a = document.createElement('a');
      a.href = file.download_url;
      a.download = file.download_filename || file.filename;
      a.style.display = 'none';
      document.body.appendChild(a);
      setTimeout(() => {
        a.click();
        document.body.removeChild(a);
      }, i * 300);
    });
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <a href="/" className="topbar-nav">← Baka Akari</a>
        <span className="topbar-nav-sep" />
        <a href="/tools/" className="topbar-nav">← Tools</a>
        <span className="topbar-nav-sep" />
        <div className="topbar-brand">
          <div className="topbar-brand-text">
            <span className="topbar-brand-title">WATERMARK</span>
            <span className="topbar-brand-sub">T-001</span>
          </div>
        </div>
      </div>

      <div className="topbar-actions">
        <div className="topbar-status" data-status={status}>
          {isRunning && <span className="spinner" style={{ width: 12, height: 12 }} />}
          {!isRunning && status === 'success' && <span className="status-dot success" />}
          {!isRunning && status === 'error' && <span className="status-dot error" />}
          {!isRunning && status === 'idle' && <span className="status-dot idle" />}
          <span>{message}</span>
          {hasFiles && (
            <span style={{ color: 'var(--text-faint)' }}>
              · {files.length} files
            </span>
          )}
        </div>

        {isRunning && (
          <div style={{ width: 100, display: 'flex', alignItems: 'center' }}>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
        <button
          disabled={!hasFiles || isRunning}
          onClick={loadPreview}
        >
          预览
        </button>
        <button
          className="primary"
          disabled={!hasFiles || isRunning}
          onClick={handleProcess}
        >
          {isMulti ? `Process All (${files.length})` : 'Process'}
        </button>

        {batchResults.length > 0 && (
          <>
            <button className="success" onClick={downloadBatch} title={`下载全部 ${batchResults.length} 张`}>
              ↓ All ({batchResults.length})
            </button>
            <button className="ghost micro" onClick={clearBatchResults} title="清除">✕</button>
          </>
        )}

        {result && !isMulti && (
          <a className="btn success" href={result.download_url} download={result.download_filename || result.filename}>
            ↓ Download
          </a>
        )}
      </div>
    </header>
  );
}
