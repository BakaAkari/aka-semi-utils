# Changelog / 开发变更记录

本文件记录 `aka-semi-utils / 极简水印` 的重要开发变化。正式 Release notes 应以本文件、git diff 和实际验证结果为基础整理。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 `docs/versioning.md`。

## Unreleased

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
- 将后续协作模式固化为“需求/方向 → roadmap/设计文档 → 用户确认 → 代码实现 → 自动验证 → 用户手动测试 → bug 迭代 → 文档/版本同步 → commit/tag/release”。
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