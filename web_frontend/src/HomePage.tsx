import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { processImage, type ApiFile } from './api';
import { InspectorPanel } from './components/InspectorPanel';
import { LeftRail } from './components/LeftRail';
import { PreviewStage } from './components/PreviewStage';
import { TopBar } from './components/TopBar';
import { createDefaultWatermarkConfig, sanitizeConfig, type WatermarkConfig } from './watermarkConfig';
import './styles.css';

type ActionState = 'idle' | 'running' | 'success' | 'error';

export type ToastItem = {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
};

export type AppContextType = {
  files: File[];
  activeFileIndex: number;
  config: WatermarkConfig;
  setConfig: React.Dispatch<React.SetStateAction<WatermarkConfig>>;
  preview: ApiFile | null;
  result: ApiFile | null;
  batchResults: ApiFile[];
  status: ActionState;
  message: string;
  progress: number;
  toasts: ToastItem[];
  showToast: (message: string, type: ToastItem['type']) => void;
  removeToast: (id: number) => void;
  runPreview: (opts?: { silent?: boolean }) => Promise<void>;
  runProcess: () => Promise<void>;
  runProcessAll: () => Promise<void>;
  cancelProcessAll: () => void;
  setFiles: React.Dispatch<React.SetStateAction<File[]>>;
  setActiveFileIndex: React.Dispatch<React.SetStateAction<number>>;
  removeFile: (index: number) => void;
  clearOutputs: () => void;
  clearBatchResults: () => void;
};

export const AppContext = createContext<AppContextType | null>(null);

let toastIdCounter = 0;

export function HomePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  const [config, setConfig] = useState<WatermarkConfig>(() => createDefaultWatermarkConfig());
  const [result, setResult] = useState<ApiFile | null>(null);
  const [batchResults, setBatchResults] = useState<ApiFile[]>([]);
  const [preview, setPreview] = useState<ApiFile | null>(null);
  const [status, setStatus] = useState<ActionState>('idle');
  const [message, setMessage] = useState('拖拽图片或点击上传开始');
  const [progress, setProgress] = useState(0);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const previewRequestId = useRef(0);
  const previewAbort = useRef<AbortController | null>(null);
  const processingAbort = useRef<AbortController | null>(null);
  const previewDebounceTimer = useRef<number | null>(null);

  const sanitizedConfig = useMemo(() => sanitizeConfig(config), [config]);

  const showToast = useCallback((message: string, type: ToastItem['type']) => {
    const id = ++toastIdCounter;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const clearOutputs = useCallback(() => {
    previewRequestId.current += 1;
    setPreview(null);
    setResult(null);
    setProgress(0);
  }, []);

  const clearBatchResults = useCallback(() => {
    setBatchResults([]);
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles(prev => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) {
        clearOutputs();
        setStatus('idle');
        setMessage('拖拽图片或点击上传开始');
        setActiveFileIndex(0);
      } else {
        setActiveFileIndex(prevIdx => (prevIdx >= next.length ? next.length - 1 : prevIdx));
      }
      return next;
    });
  }, [clearOutputs]);

  const runPreview = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    const file = files[activeFileIndex];
    if (!file) {
      setPreview(null);
      if (!silent) {
        setStatus('idle');
        setMessage('拖拽图片或点击上传开始');
      }
      return;
    }

    const requestId = ++previewRequestId.current;
    previewAbort.current?.abort();
    const abortController = new AbortController();
    previewAbort.current = abortController;
    if (!silent) {
      setStatus('running');
      setMessage('正在生成预览...');
    } else {
      setMessage('参数已修改，正在刷新预览...');
    }

    try {
      const response = await processImage('preview', file, sanitizedConfig, abortController.signal);
      if (requestId !== previewRequestId.current || abortController.signal.aborted) return;
      setPreview(response.file);
      setStatus('success');
      setMessage(silent ? '预览已更新' : '预览完成');
    } catch (error) {
      if (requestId !== previewRequestId.current) return;
      setStatus('error');
      setMessage(error instanceof Error ? error.message : '未知错误');
      showToast(error instanceof Error ? error.message : '预览生成失败', 'error');
    }
  }, [files, activeFileIndex, sanitizedConfig, showToast]);

  // Ref to always access the latest runPreview without triggering effect re-runs
  const runPreviewRef = useRef(runPreview);
  runPreviewRef.current = runPreview;

  const runProcess = useCallback(async () => {
    const file = files[activeFileIndex];
    if (!file) {
      showToast('请先选择图片', 'error');
      return;
    }

    setStatus('running');
    setMessage('正在处理原图...');
    setProgress(0);
    try {
      const response = await processImage('process', file, sanitizedConfig);
      setResult(response.file);
      setStatus('success');
      setMessage('处理完成');
      setProgress(100);
      showToast('图片处理完成', 'success');
    } catch (error) {
      setStatus('error');
      const msg = error instanceof Error ? error.message : '处理失败';
      setMessage(msg);
      showToast(msg, 'error');
    }
  }, [files, activeFileIndex, sanitizedConfig, showToast]);

  const runProcessAll = useCallback(async () => {
    if (files.length === 0) {
      showToast('请先选择图片', 'error');
      return;
    }

    processingAbort.current?.abort();
    const abortController = new AbortController();
    processingAbort.current = abortController;
    setStatus('running');
    setMessage(`正在处理 0/${files.length}...`);
    setProgress(0);
    setBatchResults([]);
    const results: ApiFile[] = [];

    for (let i = 0; i < files.length; i++) {
      if (abortController.signal.aborted) break;
      try {
        const response = await processImage('process', files[i], sanitizedConfig, abortController.signal);
        results.push(response.file);
        setBatchResults(prev => [...prev, response.file]);
        setProgress(Math.round(((i + 1) / files.length) * 100));
        setMessage(`正在处理 ${i + 1}/${files.length}...`);
      } catch (error) {
        if (abortController.signal.aborted) break;
        const msg = error instanceof Error ? error.message : '处理失败';
        showToast(`第 ${i + 1} 张处理失败: ${msg}`, 'error');
      }
    }

    if (abortController.signal.aborted) {
      setStatus('idle');
      setMessage('已取消');
      return;
    }

    setStatus('success');
    setMessage(`完成 ${results.length}/${files.length}`);
    setProgress(100);
    showToast(`批量处理完成: ${results.length}/${files.length}`, 'success');
  }, [files, sanitizedConfig, showToast]);

  const cancelProcessAll = useCallback(() => {
    processingAbort.current?.abort();
    processingAbort.current = null;
    setStatus('idle');
    setMessage('已取消');
  }, []);

  // Debounced auto-preview: only trigger after 800ms of no changes.
  // Use runPreviewRef to avoid including runPreview in deps, preventing
  // unnecessary timer resets when the callback identity changes.
  useEffect(() => {
    if (files.length === 0) return;
    if (previewDebounceTimer.current !== null) {
      window.clearTimeout(previewDebounceTimer.current);
    }
    previewDebounceTimer.current = window.setTimeout(() => {
      previewDebounceTimer.current = null;
      void runPreviewRef.current({ silent: true });
    }, 800);
    return () => {
      if (previewDebounceTimer.current !== null) {
        window.clearTimeout(previewDebounceTimer.current);
        previewDebounceTimer.current = null;
      }
    };
  }, [files, activeFileIndex, sanitizedConfig]);

  const contextValue = useMemo<AppContextType>(
    () => ({
      files, activeFileIndex, config, setConfig,
      preview, result, batchResults, status, message, progress, toasts,
      showToast, removeToast,
      runPreview, runProcess, runProcessAll, cancelProcessAll,
      setFiles, setActiveFileIndex, removeFile, clearOutputs, clearBatchResults
    }),
    [files, activeFileIndex, config, preview, result, batchResults, status, message, progress, toasts, showToast, removeToast, runPreview, runProcess, runProcessAll, cancelProcessAll, clearOutputs, removeFile, clearBatchResults]
  );

  return (
    <AppContext.Provider value={contextValue}>
      <div className="app-shell">
        <TopBar />
        <div className="workspace">
          <LeftRail />
          <PreviewStage />
          <InspectorPanel />
        </div>
        <div className="toast-container">
          {toasts.map(t => (
            <div key={t.id} className={`toast toast-${t.type}`} onClick={() => removeToast(t.id)}>
              {t.type === 'success' && '✓ '}
              {t.type === 'error' && '✗ '}
              {t.type === 'info' && 'ⓘ '}
              {t.message}
            </div>
          ))}
        </div>
      </div>
    </AppContext.Provider>
  );
}
