# Changelog / 开发变更记录

本文件记录 `aka-semi-utils / 极简水印` 的重要开发变化。正式 Release notes 应以本文件、git diff 和实际验证结果为基础整理。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 `docs/versioning.md`。

## Unreleased — Web MVP 开发中

### Added

- **Web 端 MVP 架构**：React 19 + Vite + TypeScript 前端 + FastAPI 后端。
  - 新增 `web_frontend/`：React 应用，6 个配置 Tab、4 个预设模板、批量处理入口。
  - 新增 `web_api/`：FastAPI 后端，提供 `/api/health`、`/api/preview`、`/api/process`、`/api/upload-resource`。
  - 新增 `shared/`：纯 Python 共享层，`watermark_schema.py`、`field_registry.py`、`processor_assembler.py`。
- **前端 UI**：macOS/iOS 玻璃质感设计系统。
  - 玻璃面板（`backdrop-filter: blur(24px)`）、微动效、排版层级。
  - Toast 反馈系统、进度条、骨架屏。
  - 响应式布局，支持桌面端和窄屏。
- **后端处理管线**：复用现有 `processor/core.py`，通过 `web_api/processing.py` 桥接。
  - 预览模式：限制最大像素，快速返回。
  - 正式处理：完整水印渲染，返回下载 URL。
- **Logo / 签名上传**：`POST /api/upload-resource`，随机文件名存储，前端通过 `/api/files/` 访问。
- **EXIF 读取 Pillow fallback**：当 `exiftool` 不可用时，自动回退到 Pillow 读取 EXIF。
  - 完整映射 Pillow 键名 → exiftool 格式（焦距 → `50mm`、光圈 → `f/2.8`、快门 → `1/80s`）。
  - 修复有理数格式化和 null 字节残留问题。
- **部署配置**：
  - `scripts/aka-semi-utils-web.service`：systemd 服务配置，含安全限制。
  - `scripts/semi-utils.nginx.conf`：nginx 反向代理配置。
  - `scripts/deploy.sh`：一键部署脚本（本地构建 + 远程 rsync + 服务重启）。

### Changed

- **项目主线转向 Web**：桌面版冻结在 `v2.1.9`，归档至 `archive/desktop-v2` 分支。
- **默认水印排版**：左上 → 厂商品牌 + 相机型号；左下 → 焦距 | 光圈 | 快门 | ISO；Logo → 右侧。
- **前端构建产物**：`web_frontend/dist/` 自动挂载到 `/semi-utils/`，SPA fallback 支持。
- **配置 schema**：`WatermarkConfig` 新增 `signature` 一级字段，同时保留 `AdvancedConfig` 中的 legacy 字段向后兼容。

### Fixed

- **上传无反应**：修复 `removeFile` 索引越界、`label` 点击冲突、不支持格式静默过滤、重复选择相同文件不触发。
- **签名配置被忽略**：`web_api/schemas.py` 遗漏 `signature` 参数，导致前端签名配置被后端忽略。
- **EXIF 完全无法读取**：`exiftool` 缺失时 `get_exif()` 直接返回 `{}`；Pillow fallback 中 `Any` 未导入导致 `NameError`。
- **预设布局**：描述文字换行、容器高度增加、卡片最小宽度限制。

### Security

- 用户自定义文本不再作为 Jinja 模板执行。
- Web 配置改为严格类型、范围和枚举校验。
- 自定义 Logo/签名只接受服务端资源 ID，禁止任意本地路径。
- 上传、输出和临时资源增加大小、像素、并发和自动过期保护。
- systemd service 配置 `NoNewPrivileges=true`、`ProtectSystem=strict`。

## 2.1.9 - 2026-06-24

### Changed

- Phase 28：字号系统从固定像素（px）全面重构为相对比例（占图片短边比例）。
  - 角级字号 `font_size`（int，px）→ `font_size_ratio`（float，比例），UI 下拉菜单改为百分比选项（1%~15%）。
  - 全局角字号 `corner_text_height_px`（int，px）→ `corner_text_ratio`（float，比例），高级面板改为 `QDoubleSpinBox`。
  - 处理器渲染时按 `short_edge * ratio` 计算实际像素，横竖屏字号视觉大小一致。
  - 修复误导性注释：`0 = 继承 advanced.global_font_size` 修正为实际语义。
- 签名水印偏移从像素值改为照片主体宽/高比例，UI 使用百分比输入，横竖图定位更一致。
- 底部水印条默认高度改为固定像素默认值，减少不同图片尺寸间的视觉漂移。
- 将本地 `.app` 打包产物加入忽略规则，避免误提交构建产物。

### Documentation

- 新增项目治理文档入口，明确 roadmap、开发流程、版本追溯和 changelog 的职责分工。
- 将后续协作模式固化为"需求/方向 → roadmap/设计文档 → 用户确认 → 代码实现 → 自动验证 → 用户手动测试 → bug 迭代 → 文档/版本同步 → commit/tag/release"。
- 新增项目架构与 UI/UX 分析文档，辅助后续维护与产品化迭代。

### Verification

- `uv run ruff check .`
- `uv run pytest`

## 2.1.8

### Changed

- 当前仓库版本号在 `pyproject.toml`、`uv.lock`、`README.md` 和 `gui/main_window.py` 中保持一致。

### Documentation

- `README.md` 已覆盖项目介绍、下载使用、本地开发、打包发布、效果展示、项目结构和许可证。
- `AGENTS.md` 已覆盖仓库级 Agent 开发、提交和 Release 规则。
- `.agents/skills/aka-semi-utils-dev/SKILL.md` 已覆盖项目专用 Agent Skill 流程。
- `docs/phase6_design.md` 记录 Phase 6 GUI 配置体验重构设计。
