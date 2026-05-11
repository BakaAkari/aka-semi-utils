# Changelog / 开发变更记录

本文件记录 `aka-semi-utils / 极简水印` 的重要开发变化。正式 Release notes 应以本文件、git diff 和实际验证结果为基础整理。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 `docs/versioning.md`。

## Unreleased

### Documentation

- 新增项目治理文档入口，明确 roadmap、开发流程、版本追溯和 changelog 的职责分工。
- 将后续协作模式固化为“需求/方向 → roadmap/设计文档 → 用户确认 → 代码实现 → 自动验证 → 用户手动测试 → bug 迭代 → 文档/版本同步 → commit/tag/release”。

## 2.1.8

### Changed

- 当前仓库版本号在 `pyproject.toml`、`uv.lock`、`README.md` 和 `gui/main_window.py` 中保持一致。

### Documentation

- `README.md` 已覆盖项目介绍、下载使用、本地开发、打包发布、效果展示、项目结构和许可证。
- `AGENTS.md` 已覆盖仓库级 Agent 开发、提交和 Release 规则。
- `.agents/skills/aka-semi-utils-dev/SKILL.md` 已覆盖项目专用 Agent Skill 流程。
- `docs/phase6_design.md` 记录 Phase 6 GUI 配置体验重构设计。