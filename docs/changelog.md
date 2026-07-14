# Changelog / 开发变更记录

本文件记录当前 Web/V3 主线的重要变化。正式 Release notes 应以本文件、git diff 和实际验证结果为基础整理。

## Unreleased — V3 开发中

### Added

- V3 Region-Based Layout 架构：Region / Slot / Content 声明式配置。
- 前端布局引擎：`web_frontend/src/v3_layout/layoutEngine.ts`。
- 后端布局引擎：`shared/v3_layout/layout_engine.py`。
- 后端 V3 渲染处理器：`processor/v3_watermark.py`。
- V3 API schema：`web_api/schemas_v3.py`。
- V3 左侧 rail 工作台布局和预设 rail。
- V1 占位页：`deploy/legacy-watermark-placeholder/index.html`。
- 下一阶段设计入口：`design/v3-control-surface-guardrails.md`。

### Changed

- 项目主线从 Web MVP/V1-V2 迁移到 V3。
- 线上 V3 固定入口：`/tools/watermark-v3/`。
- API prefix：`/tools/watermark-v3/api`。
- `/tools/watermark/` 改为“回炉重塑中”静态页。
- README、roadmap、部署文档和协作流程同步到 V3 当前状态。

### Removed

- V2 SPA route `/v2`。
- V2 静态入口 `/tools/watermark-v2/`。
- V1/V2 前端文件：`HomePage.tsx`、`WatermarkCanvas.tsx`、`api.ts`、`presets.ts`、`watermarkConfig.ts`、旧 Inspector/LeftRail/WatermarkBar 等。
- V1/V2 后端兼容模型：`web_api/schemas.py`、`shared/watermark_schema.py`、`shared/processor_assembler.py`。
- 旧 V1/V2 服务和 2189 端口对外路由。
- 过期 Web MVP / dev-stats 设计文档已归档至 `docs/archive/legacy-web-mvp/`。

### Security

- API 只接受 V3 payload；旧 config 返回 `410 legacy_config_removed`。
- V3 resource path 只接受不透明资源 ID。
- 禁止 NaN / Infinity 等非有限数值。
- 配置 JSON 大小限制为 64KB。
- 字体、资源、slot id、region id、anchor 等均加强枚举/格式校验。

### Verification

- `uv run ruff check .`
- `uv run pytest`
- `VITE_API_BASE=/tools/watermark-v3 npm run build`
- 线上 V1/V2/V3 路由和浏览器截图检查。

## 2.1.9 - 2026-06-24

桌面最终版。源码和历史文档保存在 `archive/desktop-v2` 分支，不再进入当前 Web/V3 主线。
