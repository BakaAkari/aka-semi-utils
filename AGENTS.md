# aka-semi-utils Agent 指南

本文件是本仓库的项目级 agent 记忆入口。所有 AI/LLM 在协助开发 `aka-semi-utils / 极简水印` 时，应优先遵循这里的项目约定、设计意图和发布流程。

## 项目定位

`aka-semi-utils` 是一个面向摄影照片的 PyQt6 桌面 GUI 批量水印工具。

核心目标：

- 让摄影用户能用图形界面快速批量添加 EXIF 信息水印、品牌 Logo 和签名水印。
- 保持配置体验直观：字段 chip、四角布局、实时预览、高级参数都应围绕“可理解、可恢复、可批处理”设计。
- 保持处理管线稳定：GUI 状态、配置持久化、图片处理和错误呈现要清晰分层。
- Release 包应面向普通用户开箱即用，不包含开发者本机路径、私人签名或私人 Logo。

## 代码结构速览

- `main.py`：PyQt6 GUI 入口。
- `gui/`：界面、状态模型、预览、配置面板、处理线程、错误呈现。
- `processor/`：图片处理管线、滤镜、生成器、批处理、性能工具和 schema。
- `core/`：配置加载、字体、图片 IO、Jinja 渲染、日志和通用工具。
- `config/`：默认配置、字体、Logo、release 默认用户配置。
- `static/`：示例模板和效果图。
- `scripts/build.spec`：PyInstaller 三平台通用打包配置。
- `.github/workflows/build-release.yml`：GitHub Actions 三平台 Release 构建。
- `tests/`：单元测试与集成测试。

## 项目治理文档

- `docs/roadmap.md`：长期路线、阶段拆分、Backlog 和阶段完成定义。
- `docs/development_workflow.md`：需求、文档、实现、测试、版本和发布协作流程。
- `docs/versioning.md`：版本号、开发阶段、changelog、tag 和 Release 追溯规则。
- `docs/changelog.md`：开发过程变更记录，Release notes 的输入来源之一。
- `docs/phase*_design.md`：阶段或专项设计文档。

## 开发工作流

### 默认协作流程

涉及新功能、大改动、体验重构、配置结构调整或发布流程变化时，必须遵循：

```text
需求/方向 → roadmap/设计文档 → 用户确认 → 代码实现 → 自动验证 → 用户手动测试 → bug 迭代 → 文档/版本同步 → commit/tag/release
```

未完成文档对齐前，不要直接开始大规模代码实现；小 bug、文案、明显修复可直接进入实现，但仍需按需补充 changelog 或测试说明。

### 开始修改前

1. 先查看当前 Git 状态：`git status --short`。
2. 阅读治理文档：`docs/roadmap.md`、`docs/development_workflow.md`、`docs/versioning.md`，并确认是否需要更新 `docs/changelog.md`。
3. 理解用户目标对应的层次：
   - GUI 交互 / 状态：优先看 `gui/models.py`、`gui/main_window.py`、`gui/config_panel.py`、`gui/preview_panel.py`。
   - 图片处理：优先看 `processor/core.py`、`processor/filters.py`、`processor/generators.py`、`processor/mergers.py`。
   - 配置路径 / release 资源：优先看 `core/config_loader.py`、`scripts/build.spec`、`config/user.release.json`。
4. 修改前尽量做语义搜索或读取相关上下文，不要凭记忆改关键路径。

### 修改原则

- 保持 GUI 状态单一来源：`AppState` 是 GUI 配置状态的核心。
- 运行时用户配置写入 `config/user.json`；Release 打包默认配置来自 `config/user.release.json`。
- 不要把开发者本机私人路径、签名图片路径、自定义 Logo 路径写入 release 默认配置。
- 避免大范围重写；优先做小而清晰的补丁。
- UI 文案默认使用简体中文，内部代码命名保持现有英文风格。
- 修改处理管线时要考虑批处理、预览、错误汇总三个入口是否一致。
- 新增行为优先补测试；修 bug 至少跑相关测试，发布前跑全量测试。
- 大功能提交必须包含对应 roadmap、阶段设计、changelog 或版本说明更新。
- 用户负责最终 GUI 体验测试；agent 负责自动验证、修复迭代和可追溯记录。

## 常用验证命令

```bash
uv run ruff check .
uv run mypy .
uv run pytest
```

本地验证 PyInstaller：

```bash
uv pip install pyinstaller
uv run pyinstaller scripts/build.spec --clean --noconfirm
python -m json.tool dist/aka-semi-utils/_internal/config/user.json
```

Release 默认配置隐私检查：

```bash
! grep -R "/Users/" -n dist/aka-semi-utils/_internal/config/user.json
! grep -R "signature_path.*Users\|custom_path.*Users" -n config/user.release.json
```

## Commit 与 GitHub 推送约定

当用户要求“提交”、“保存到 GitHub”、“上传 GitHub”、“刚修了 bug 帮我处理一下”时，agent 应主动：

1. 查看 `git status --short` 和 `git diff --stat`。
2. 根据变更生成短 commit message，不要让用户手写。
3. 优先使用 Conventional Commits 的短文本：
   - `fix: ...` 修 bug
   - `feat: ...` 新功能
   - `chore: ...` 版本、构建、杂项
   - `docs: ...` 文档
   - `test: ...` 测试
   - `refactor: ...` 重构
4. commit message 应简短明确，通常不超过 72 字符。
5. 提交后推送 `main`：`git push origin main`。
6. 推送前如果测试失败，先修复或明确说明，不要盲目推送。

## Release 发布流程

当用户要求“发布”、“打包分发”、“创建 release”、“推送 release 包”时，agent 应自动执行完整流程。

### 版本号

- 版本策略以 `docs/versioning.md` 为准。
- 默认做 patch bump，例如 `2.1.7` → `2.1.8`。
- 完整 Phase 或用户可感知大功能通常做 minor bump，例如 `2.1.8` → `2.2.0`。
- 如果用户明确要求 minor/major/pre-release，则按用户要求。
- 同步更新以下位置：
  - `pyproject.toml` 的 `[project].version`
  - `uv.lock` 中本项目 `semi-photo-utils` 版本
  - `README.md` 当前版本
  - `gui/main_window.py` 关于弹窗版本
  - `docs/changelog.md` 对应版本记录

### 发布前检查

1. 确认工作区状态。
2. 确认 `config/user.release.json` 是干净默认配置，不包含私人路径。
3. 跑测试：`uv run pytest`。
4. 如涉及打包配置，跑本地 PyInstaller 验证。

### 发布步骤

```bash
git add pyproject.toml README.md gui/main_window.py uv.lock <其他变更>
git commit -m "chore: bump version to x.y.z"
git push origin main
git tag -a vx.y.z -m "Release vx.y.z"
git push origin vx.y.z
```

推送 tag 后，GitHub Actions 会由 `.github/workflows/build-release.yml` 自动构建三平台包并创建/更新 Release：

- `aka-semi-utils-windows-vx.y.z.zip`
- `aka-semi-utils-macos-vx.y.z.tar.gz`
- `aka-semi-utils-linux-vx.y.z.tar.gz`

### 监控发布

```bash
gh run list --repo BakaAkari/aka-semi-utils --workflow "Build & Release (Windows / macOS / Linux)" --limit 5
gh run watch <run-id> --repo BakaAkari/aka-semi-utils --exit-status
gh release view vx.y.z --repo BakaAkari/aka-semi-utils --json tagName,url,isDraft,isPrerelease,assets,publishedAt
```

## Release Changelog 约定

Release 创建后不要只依赖自动生成说明。应按本次变更合理编辑 changelog。

推荐格式：

```markdown
## Highlights

- 一句话说明本版最重要变化。

## Changes

- 新增/修复/优化的用户可感知变化。
- 构建、打包或兼容性变化。

## Verification

- Tests: `uv run pytest`
- Release build: GitHub Actions Windows / macOS / Linux succeeded

## Assets

- Windows: `aka-semi-utils-windows-vx.y.z.zip`
- macOS: `aka-semi-utils-macos-vx.y.z.tar.gz`
- Linux: `aka-semi-utils-linux-vx.y.z.tar.gz`
```

使用 `gh release edit vx.y.z --notes-file <file>` 更新说明。临时 changelog 文件可放在 `/tmp`，不要提交临时文件。

## 与用户沟通风格

- 默认使用简体中文。
- 用户要的是结果时，不要反复询问；能从仓库判断的就直接执行。
- 涉及新功能方向时，先输出或更新文档方案，等用户确认后再编码。
- 汇报时列出：改了什么、验证结果、commit、tag、release 链接、资产列表。
- 不要把长篇内部推理暴露给用户。
