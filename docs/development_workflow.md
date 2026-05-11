# Development Workflow / 协作开发流程

本文件固化 `aka-semi-utils / 极简水印` 的需求、文档、实现、测试、版本和发布协作方式。后续涉及新功能、大改动、体验重构或发布时，应优先遵循本流程。

## 核心流程

```text
需求/方向 → roadmap/设计文档 → 用户确认 → 代码实现 → 自动验证 → 用户手动测试 → bug 迭代 → 文档/版本同步 → commit/tag/release
```

## 角色分工

### 用户负责

- 提供真实需求、使用场景、优先级和体验方向。
- 审阅并确认 roadmap、阶段设计和验收标准。
- 对 GUI 功能进行真实操作测试。
- 反馈 bug、体验问题和期望调整。

### Agent 负责

- 将需求整理为 roadmap、阶段设计文档、任务拆分和验收标准。
- 在文档对齐前，不直接进行大规模代码实现。
- 根据确认后的文档进行代码修改、测试和修复。
- 维护版本号、README、Agent 规则、Release notes 等可追溯信息。
- 提交前检查工作区状态、diff、测试结果和隐私路径。

## 工作模式

### 1. 需求整理阶段

适用于：

- 新功能。
- 大范围 GUI 改造。
- 配置结构调整。
- 处理管线变化。
- Release 流程变化。

Agent 应执行：

1. 阅读现有 roadmap 和相关阶段文档。
2. 将用户需求整理为：
   - 背景与目标。
   - 用户场景。
   - 功能范围。
   - 非目标范围。
   - 涉及模块。
   - 风险与兼容性。
   - 验收标准。
3. 更新 `docs/roadmap.md` 或新增/更新阶段设计文档。
4. 等用户确认后再进入实现。

### 2. 实现阶段

实现前应检查：

```bash
git status --short
```

实现原则：

- 优先小补丁，避免无关重构。
- 保持 `AppState` 是 GUI 配置状态单一来源。
- 修改处理管线时，同时考虑预览、批处理和错误汇总入口。
- 修改配置结构时，必须考虑老配置迁移。
- 不把开发者本机路径写入 `config/user.release.json`。

### 3. 自动验证阶段

常用命令：

```bash
uv run ruff check .
uv run mypy .
uv run pytest
```

按变更范围选择：

- 文档-only：可不跑完整测试，但需要检查链接和版本一致性。
- GUI/模型/配置：至少跑相关单测；关键阶段跑全量测试。
- 处理管线：跑相关单测与集成测试。
- Release/打包：跑全量测试，并按需本地 PyInstaller 验证。

### 4. 用户手动测试阶段

GUI 项目必须保留用户手动测试环节。Agent 自动测试不能替代真实体验测试。

建议用户测试：

- 首次打开应用。
- 导入一组真实照片。
- 调整四角字段、字体、颜色、Logo、签名和高级参数。
- 查看实时预览。
- 关闭重启，确认配置恢复。
- 执行批处理，检查输出图和失败详情。
- 使用 Release 包进行冒烟测试。

### 5. Bug 迭代阶段

每个 bug 尽量记录：

- 复现步骤。
- 预期行为。
- 实际行为。
- 影响范围。
- 修复方案。
- 验证方式。

重要 bug 修复应同步更新相关验收标准或测试。

### 6. 版本与提交阶段

大功能或阶段性提交应满足：

- roadmap/阶段文档已同步。
- README 按需更新。
- 版本号策略已确认。
- 自动验证完成。
- 用户测试反馈已处理或记录为后续 backlog。

提交信息使用 Conventional Commits：

```text
feat: add template preset management
fix: restore signature config persistence
docs: add development workflow
chore: bump version to 2.2.0
```

## 文档组织规则

- `README.md`：面向用户和新开发者的项目入口。
- `docs/roadmap.md`：长期路线和阶段拆分。
- `docs/development_workflow.md`：协作开发流程。
- `docs/versioning.md`：版本策略和追溯规则。
- `docs/changelog.md`：开发过程变更记录，Release notes 的输入来源之一。
- `docs/phase*_design.md`：阶段或专项设计文档。
- `AGENTS.md`：仓库级 LLM/Agent 规则入口。
- `.agents/skills/aka-semi-utils-dev/SKILL.md`：项目专用 Agent Skill。

## 大功能启动模板

新增大功能前，建议在阶段文档中包含：

```markdown
# Phase N：功能名称

## 背景

## 目标

## 非目标

## 用户场景

## 设计方案

## 涉及文件

## 数据/配置兼容性

## 实施步骤

## 验收标准

## 风险与回滚
```

## 完成定义

一次功能迭代完成时，应能回答：

- 这次改动解决了什么问题？
- 对应文档在哪里？
- 版本或 changelog 是否更新？
- 自动测试结果如何？
- 用户手动测试结果如何？
- commit/tag/release 是否可追溯？