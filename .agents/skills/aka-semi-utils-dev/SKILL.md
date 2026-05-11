# aka-semi-utils-dev

项目专用 Skill：协助开发、提交、发布 `aka-semi-utils / 极简水印`。

## 何时使用

当用户的请求涉及以下任一场景时使用本 Skill：

- 修改极简水印 / aka-semi-utils 的 GUI、图片处理、配置、模板、打包或测试。
- 希望 agent 更理解本项目设计需求、状态模型、release 默认配置或水印处理管线。
- 要求整理需求、更新 roadmap、编写阶段设计或维护开发文档。
- 要求提交代码、生成短 commit 文本、推送到 GitHub。
- 要求发布版本、修改版本号、创建 tag、用 GitHub Actions 打三平台包。
- 要求编辑 Release changelog 或检查 Release assets。

## 项目心智模型

`aka-semi-utils` 是 PyQt6 桌面批量水印工具，主要面向摄影照片。核心能力包括：

- EXIF 字段水印：相机、镜头、焦距、光圈、快门、ISO、拍摄时间等。
- 四角布局：左上、左下、右上、右下各自配置 chip、分隔符、字体、颜色。
- 品牌 Logo 与自定义 Logo。
- 签名水印：九宫格定位、宽度比例、偏移、黑白反转。
- 实时预览、批处理、错误汇总、三平台分发。

关键目录：

- `gui/`：PyQt6 GUI 与 `AppState` 状态。
- `processor/`：图片处理管线。
- `core/`：配置、字体、图片 IO、日志等基础能力。
- `config/user.json`：开发/运行时用户当前配置，可能包含私人路径，不应直接用于 Release 默认配置。
- `config/user.release.json`：面向分发包的干净默认用户配置。
- `scripts/build.spec`：PyInstaller 打包入口。
- `.github/workflows/build-release.yml`：三平台 Release 构建。

## 开发流程

默认协作链路：

```text
需求/方向 → roadmap/设计文档 → 用户确认 → 代码实现 → 自动验证 → 用户手动测试 → bug 迭代 → 文档/版本同步 → commit/tag/release
```

涉及新功能、大改动、体验重构、配置结构调整或发布流程变化时，先更新 `docs/roadmap.md`、`docs/development_workflow.md`、`docs/versioning.md`、`docs/changelog.md` 或对应 `docs/phase*_design.md`，等用户确认后再进行代码实现。

1. 先查看仓库状态：

   ```bash
   git status --short
   ```

2. 阅读治理文档：
   - `docs/roadmap.md`
   - `docs/development_workflow.md`
   - `docs/versioning.md`
   - `docs/changelog.md`

3. 查找相关实现：
   - GUI 状态 / 自动保存：`gui/models.py`
   - 主窗口 / 关于弹窗 / 流程入口：`gui/main_window.py`
   - 配置面板：`gui/config_panel.py`
   - 预览：`gui/preview_panel.py`
   - 字段 chip：`gui/field_registry.py`
   - 处理管线：`processor/core.py`、`processor/filters.py`、`processor/generators.py`、`processor/mergers.py`
   - 配置路径：`core/config_loader.py`
   - 打包资源：`scripts/build.spec`

4. 修改原则：
   - 保持 `AppState` 为 GUI 配置状态单一来源。
   - 小步修改，优先精确补丁。
   - 不要把用户本机路径写进 `config/user.release.json`。
   - 影响行为时补测试或跑相关测试。
   - 大功能提交必须包含对应 roadmap、阶段设计、changelog 或版本说明更新。
   - 用户负责最终 GUI 体验测试；agent 负责自动验证、修复迭代和可追溯记录。

5. 常规验证：

   ```bash
   uv run pytest
   ```

   需要时追加：

   ```bash
   uv run ruff check .
   uv run mypy .
   ```

## 自动 commit / push 流程

当用户要求“提交”、“推送 GitHub”、“刚修了 bug 帮我同步”等，执行：

1. 查看变更：

   ```bash
   git status --short
   git diff --stat
   ```

2. 根据变更自动写短 commit message：
   - bug：`fix: concise description`
   - 功能：`feat: concise description`
   - 发布/版本/构建：`chore: concise description`
   - 文档：`docs: concise description`
   - 测试：`test: concise description`
   - 重构：`refactor: concise description`

3. 跑测试或至少跑相关测试。
4. 提交并推送：

   ```bash
   git add <files>
   git commit -m "fix: concise description"
   git push origin main
   ```

5. 最终告知 commit hash 与推送结果。

## Release 发布流程

当用户要求“发布 release”、“打包分发”、“推送 release 包”时，默认执行 patch 版本发布。

### 1. 计算版本号

- 当前版本从 `pyproject.toml` 读取。
- 默认 patch bump：`x.y.z` → `x.y.(z+1)`。
- 若用户指定版本或 bump 类型，以用户为准。

### 2. 同步版本号

必须同步更新：

- `pyproject.toml`
- `uv.lock`
- `README.md`
- `gui/main_window.py`
- `docs/changelog.md`

版本策略以 `docs/versioning.md` 为准。完整 Phase 或用户可感知大功能通常做 minor bump；普通 bug 修复通常做 patch bump。

### 3. Release 默认配置检查

确认 Release 包使用 `config/user.release.json`，不要使用开发机 `config/user.json`。

本地打包后检查：

```bash
python -m json.tool dist/aka-semi-utils/_internal/config/user.json
! grep -R "/Users/" -n dist/aka-semi-utils/_internal/config/user.json
```

### 4. 发布前验证

```bash
uv run pytest
```

如果改了 `scripts/build.spec` 或 release 配置，追加：

```bash
uv pip install pyinstaller
uv run pyinstaller scripts/build.spec --clean --noconfirm
python -m json.tool dist/aka-semi-utils/_internal/config/user.json
```

### 5. Commit、tag、push

```bash
git add pyproject.toml README.md gui/main_window.py uv.lock <其他变更>
git commit -m "chore: bump version to x.y.z"
git push origin main
git tag -a vx.y.z -m "Release vx.y.z"
git push origin vx.y.z
```

### 6. 等待 GitHub Actions

```bash
gh run list --repo BakaAkari/aka-semi-utils --workflow "Build & Release (Windows / macOS / Linux)" --limit 5
gh run watch <tag-run-id> --repo BakaAkari/aka-semi-utils --exit-status
```

### 7. 检查 Release assets

```bash
gh release view vx.y.z --repo BakaAkari/aka-semi-utils --json tagName,url,isDraft,isPrerelease,assets,publishedAt
```

必须有：

- `aka-semi-utils-linux-vx.y.z.tar.gz`
- `aka-semi-utils-macos-vx.y.z.tar.gz`
- `aka-semi-utils-windows-vx.y.z.zip`

## Release changelog 编辑

Release 成功后，应根据实际 diff 编辑简洁 changelog。

步骤：

1. 获取上一个 tag：

   ```bash
   git tag --sort=-v:refname | head -5
   ```

2. 查看提交范围：

   ```bash
   git log --oneline <previous-tag>..vx.y.z
   ```

3. 生成 `/tmp/aka-semi-utils-vx.y.z-notes.md`，格式：

   ```markdown
   ## Highlights

   - 本版本最重要变化。

   ## Changes

   - 用户可感知的新功能、修复或体验优化。
   - 打包、配置、兼容性或内部质量改进。

   ## Verification

   - Tests: `uv run pytest`
   - Release build: GitHub Actions Windows / macOS / Linux succeeded

   ## Assets

   - Windows: `aka-semi-utils-windows-vx.y.z.zip`
   - macOS: `aka-semi-utils-macos-vx.y.z.tar.gz`
   - Linux: `aka-semi-utils-linux-vx.y.z.tar.gz`
   ```

4. 更新 Release：

   ```bash
   gh release edit vx.y.z --repo BakaAkari/aka-semi-utils --notes-file /tmp/aka-semi-utils-vx.y.z-notes.md
   ```

## 文档整理流程

当用户要求“全面整理项目”、“完善开发文档”、“更新 LLM 规则”、“规划功能路线”等，执行：

1. 盘点现有 `docs/`、`AGENTS.md`、`.agents/skills/aka-semi-utils-dev/SKILL.md`、`README.md` 和版本状态。
2. 新增或更新：
   - `docs/roadmap.md`
   - `docs/development_workflow.md`
   - `docs/versioning.md`
   - `docs/changelog.md`
   - 对应 `docs/phase*_design.md`
3. 同步更新 `AGENTS.md` 与本 Skill，保证后续 agent 遵守同一流程。
4. 检查文档链接、版本一致性和 git diff。
5. 汇报新增/修改文件、验证方式和后续建议。

## 完成汇报模板

完成开发或发布后，用简体中文汇报：

- 修改了哪些文件和核心行为。
- 执行了哪些验证，结果如何。
- commit hash。
- 是否已推送 `main`。
- 如果发布：tag、Release 链接、三平台 assets。
- 当前工作区是否干净。
