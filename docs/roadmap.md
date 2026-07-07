# Roadmap / 开发路线图

本文件记录 `aka-semi-utils / 极简水印` 的长期方向、阶段拆分和当前开发优先级。任何较大的功能开发都应先更新本文件或对应阶段设计文档，再进入代码实现。

## 项目目标

`aka-semi-utils / 极简水印` 已转向公开 Web 图片水印工具。桌面版冻结在
`v2.1.9`，完整源码与发布历史保存在 `archive/desktop-v2` 分支；`main` 后续只推进
Web 产品、共享图片处理核心与服务端部署。

- 让普通摄影用户能稳定、直观地批量添加 EXIF 信息水印、品牌 Logo 和签名水印。
- 让配置系统可理解、可保存、可迁移、可恢复。
- 让预览、批处理、错误反馈和部署具备可用的产品质量。
- 让每个重要功能阶段都有文档、版本、提交和验证记录，保证开发过程可追溯。

## 开发原则

1. **先文档后实现**：新功能或大改动必须先形成目标、范围、验收标准。
2. **小步可验证**：每个阶段尽量拆成可测试、可提交的小闭环。
3. **用户体验优先**：GUI 文案、默认值、错误提示和恢复能力优先面向普通用户。
4. **状态单一来源**：前端配置状态以 React Context 为核心，后端配置以共享 schema 为准。
5. **Release 干净可复现**：部署包不包含开发者本机路径、私人签名或私人 Logo。

## 当前状态概览

- 桌面最终版：`v2.1.9`（归档分支 `archive/desktop-v2`）。
- Web 当前版本：`0.1.0`（开发中，未发布 tag）。
- 当前主线：React/Vite 前端、FastAPI 后端、共享图片处理核心。
- 当前阶段：Web MVP 前端功能开发（阶段 4）→ 部署与安全加固（阶段 5）。
- 发布门槛：严格输入校验、无服务端模板注入、无任意路径读取、有界并发、文件自动过期、HTTPS 与限流。

## 阶段路线

### Web MVP Phase 1：文档与边界 ✅ 已完成

- 编写 `docs/web_mvp_design.md`，明确 shared / web_api / web_frontend 边界。
- 确定桌面版冻结策略：`v2.1.9` + `archive/desktop-v2` 分支。

### Web MVP Phase 2：一致性核心 ✅ 已完成

- 抽出 `shared/` 层：`watermark_schema.py`、`field_registry.py`、`processor_assembler.py`。
- 共享配置 schema 同时服务 Web API 和桌面端（桌面端通过 `archive/desktop-v2` 引用）。
- 统一 EXIF 字段渲染规则（Jinja 模板）。

### Web MVP Phase 3：后端 MVP ✅ 已完成

- FastAPI 后端：`web_api/main.py`
- API：`GET /api/health`、`POST /api/preview`、`POST /api/process`
- 文件上传：`POST /api/upload-resource`（Logo/签名）
- 配置解析：`web_api/schemas.py` 从 JSON payload 构建 `WatermarkConfig`
- 图片处理：`web_api/processing.py` 调用共享 `start_process()`
- 输入校验：大小限制、像素限制、格式校验
- 自动过期：上传/输出/临时文件 TTL 清理

### Web MVP Phase 4：前端 MVP ✅ 已完成（持续优化中）

- React 19 + Vite + TypeScript 前端：`web_frontend/`
- 上传：拖拽 + 点击，支持 20+ 图片格式
- 配置面板：6 个 Tab（四角芯片、Logo、签名、画布、输出、特效）
- 实时预览：防抖请求，状态反馈
- 批量处理：多文件选择，缩略图网格，处理当前/处理全部
- 预设：4 个内置模板（白边参数、白底参数、黑边参数、横排参数）
- macOS/iOS 玻璃质感 UI：玻璃面板、微动效、排版层级
- Toast 反馈系统

**已知问题（待优化）：**
- 预览失败时的非阻塞错误提示可更友好。
- 批处理结果汇总和失败详情待优化。
- 首次使用引导缺失。

### Web MVP Phase 5：部署与安全加固 🔄 进行中

**目标：**
- 完成腾讯云/NAS 服务器部署。
- systemd + nginx 反向代理配置。
- HTTPS 配置。
- 限流、并发控制、安全加固验证。

**待办：**
- [ ] 服务器环境准备（Python 3.13 + uv）。
- [ ] 上传部署脚本和 systemd/nginx 配置。
- [ ] 域名解析与 HTTPS 证书。
- [ ] 上传大小、像素、并发压力测试。
- [ ] 文件 TTL 自动清理验证。
- [ ] 防火墙与安全组配置。

### Web MVP Phase 6：产品化增强 📋 计划中

**目标：**
- 批量 job 队列（异步处理 + 进度推送）。
- ZIP 打包下载。
- 用户配置持久化（localStorage + 后端用户配置）。
- 访问控制（可选：简单 API Key 或 IP 白名单）。

### Archived：桌面 GUI Phase 1–10

状态：已冻结，不再进入 Web 主线开发；历史设计仅供归档查阅。

参考文档：`docs/phase6_design.md`（如存在），`archive/desktop-v2` 分支。

后续整理要求：
- 桌面版设计文档不应再被误读为当前待办清单。
- 桌面版 bug 不再修复，功能不再新增。

## Backlog / 待评估事项

以下事项暂不进入具体 Phase，需等需求明确后再设计：

- 多语言 GUI。
- 所见即所得模板编辑器。
- 撤销/重做。
- 多模板批量应用。
- 用户自定义品牌 Logo 库。
- 更完整的水印样式市场或模板分享机制。
- 移动端适配（响应式优化）。

## 每个阶段的完成定义

一个阶段只有在满足以下条件后才能视为完成：

1. roadmap 或阶段设计文档已更新。
2. 需求范围、非目标、验收标准已明确。
3. 代码实现完成并通过相关自动化测试。
4. 用户完成真实 GUI 功能测试，关键 bug 已修复。
5. README、版本号、Agent 规则或 Release notes 已按需同步。
6. 变更已形成清晰 commit；正式发布时已创建 tag 和 Release。
