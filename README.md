# aka-semi-utils / V3 水印工具

> **本仓库已归档。** 后续开发已迁移至 [BakaAkari/kari-imprint](https://github.com/BakaAkari/kari-imprint)。
> 此处的 `v0.9.0-final` tag 是 aka-semi-utils 的最后一个版本，仅作为历史参考。

公开 Web 摄影水印工具。当前主线是 **V3 Region-Based Layout**：用声明式 Region / Slot / Content 配置生成水印，前端 Canvas 与后端 PIL 共享同一套布局语义。

旧版本状态：

- 桌面版冻结在 `v2.1.9`，源码保存在 `archive/desktop-v2` 分支。
- V1 Web 入口 `/tools/watermark/` 只保留“回炉重塑中”占位页。
- V2 Web 已移除；V3 SPA 不再提供 `/v2` fallback。

线上 V3：

```text
https://baka-akari.zone/tools/watermark-v3/
```

## 当前架构

```text
Config Layer  ->  Layout Layer  ->  Render Layer
V3 config         compute_layout     Canvas / PIL
```

核心文件：

- `web_frontend/src/v3Types.ts`：V3 前端配置类型和预设。
- `web_frontend/src/v3_layout/layoutEngine.ts`：前端布局引擎。
- `shared/v3_layout/layout_engine.py`：后端布局引擎。
- `processor/v3_watermark.py`：后端 V3 水印处理器。
- `web_api/schemas_v3.py`：V3 API 严格校验。
- `web_api/main.py`：FastAPI 上传、预览、处理、下载接口。

## 本地开发

后端：

```bash
uv sync --dev
AKA_SEMI_API_PREFIX=/tools/watermark-v3/api uv run uvicorn web_api.main:app --host 127.0.0.1 --port 2190 --reload
```

前端：

```bash
cd web_frontend
npm ci
VITE_API_BASE=/tools/watermark-v3 npm run dev
```

## 验证

```bash
uv run ruff check .
uv run pytest
cd web_frontend && VITE_API_BASE=/tools/watermark-v3 npm run build
```

部署后还要验证线上页面、API health、字体文件、V1/V2 旧入口状态和浏览器截图。

## 当前文档入口

- `docs/roadmap.md`：当前路线图和阶段状态。
- `design/v3-region-based-layout.md`：当前 V3 架构说明。
- `design/v3-control-surface-guardrails.md`：下一阶段：控制面收敛与布局防重叠。
- `docs/development_workflow.md`：协作开发流程。
- `deploy/README.md`：腾讯云 V3 部署和验证。

## 安全模型

- 用户文本不得作为 Jinja 或其他动态模板执行。
- Logo / 签名只使用服务端签发的不透明资源 ID。
- API 严格校验类型、枚举、长度、范围和非有限数值。
- 上传大小、图片像素、并发和文件保留时间均有硬限制。
- 不返回内部路径、异常堆栈或敏感 EXIF 日志。

## 许可证

GPL-3.0，见 [`LICENSE`](LICENSE)。
