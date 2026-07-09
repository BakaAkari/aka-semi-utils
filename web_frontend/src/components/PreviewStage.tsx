import { useContext } from 'react';
import { AppContext } from '../HomePage';

export function PreviewStage() {
  const ctx = useContext(AppContext);
  if (!ctx) return null;

  const { preview, files, activeFileIndex, status } = ctx;
  const activeFile = files[activeFileIndex];
  const isRunning = status === 'running';

  return (
    <section className="preview-stage">
      <div className="preview-panel">
        <div className="preview-frame">
          {preview ? (
            <img
              key={preview.download_url}
              src={preview.download_url}
              alt="预览"
              className="anim-fade-in-scale"
            />
          ) : (
            <div className="preview-empty">
              {isRunning && activeFile ? (
                <>
                  <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} />
                  <span className="preview-empty-title">正在渲染...</span>
                  <span className="preview-empty-sub">请稍候，水印预览生成中</span>
                </>
              ) : (
                <>
                  <span className="preview-empty-icon">🖼</span>
                  <span className="preview-empty-title">
                    {activeFile ? '等待预览' : '上传图片开始'}
                  </span>
                  <span className="preview-empty-sub">
                    {activeFile
                      ? '修改水印参数后预览会自动刷新，也可以点击顶部刷新按钮'
                      : '拖拽图片到左侧，或点击上传区域选择照片'}
                  </span>
                </>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="preview-toolbar">
        <div className="preview-toolbar-left">
          {activeFile && (
            <>
              <span className="truncate" style={{ maxWidth: 200 }} title={activeFile.name}>
                {activeFile.name}
              </span>
              <span className="text-tertiary">·</span>
              <span className="text-tertiary">{(activeFile.size / 1024 / 1024).toFixed(2)} MB</span>
            </>
          )}
          {!activeFile && <span className="text-tertiary">未选择图片</span>}
        </div>
        {preview && (
          <a
            className="btn link"
            href={preview.download_url}
            download={preview.download_filename || preview.filename}
          >
            下载预览 ↓
          </a>
        )}
      </div>
    </section>
  );
}
