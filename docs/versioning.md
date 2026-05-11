# Versioning / 版本与追溯规则

本文件定义 `aka-semi-utils / 极简水印` 的版本号、文档版本、提交、tag 和 Release 追溯规则。

## 当前版本位置

正式应用版本必须在以下位置保持一致：

- `pyproject.toml` 的 `[project].version`
- `uv.lock` 中本项目 `semi-photo-utils` 的版本
- `README.md` 的当前版本
- `gui/main_window.py` 关于弹窗版本

当前版本：`2.1.8`

## 版本类型

### 正式版本

格式：`MAJOR.MINOR.PATCH`

示例：

- `2.1.8`
- `2.2.0`
- `3.0.0`

用途：

- 对应 Git tag：`v2.1.8`
- 对应 GitHub Release
- 对应用户下载包

### 开发阶段

格式：`Phase N` 或专项名称。

示例：

- `Phase 7：可用性与产品化打磨`
- `Phase 8：模板与配置生态`

用途：

- 用于 roadmap、设计文档和任务拆分。
- 不一定直接等于应用版本号。
- 一个 Phase 可以包含多个 commit，也可以最终合并为一次 minor 或 patch release。

## Bump 规则

### Patch

适用于：

- bug 修复。
- 小体验优化。
- 文案和文档补充。
- 不改变核心工作流的小改动。

示例：`2.1.8` → `2.1.9`

### Minor

适用于：

- 用户可感知的新功能。
- 大的 GUI 工作流改进。
- 配置、模板、批处理能力增强。
- 一个完整 Phase 的稳定交付。

示例：`2.1.8` → `2.2.0`

### Major

适用于：

- 破坏性配置变更。
- 大规模架构变化。
- 旧模板或旧配置无法自动兼容。

示例：`2.1.8` → `3.0.0`

## 什么时候必须同步版本号

必须同步版本号的情况：

- 创建正式 Release。
- 完成大功能阶段并准备交付用户测试包。
- 用户明确要求版本可追溯的功能提交。
- 修改了用户可感知行为，并希望后续能通过版本定位。

可以只更新 changelog 而不立即 bump 的情况：

- roadmap 或设计文档整理。
- 未进入发布的中间开发提交。
- 探索性改动。
- 内部测试辅助代码。

## 版本同步步骤

1. 确定目标版本。
2. 同步修改：
   - `pyproject.toml`
   - `uv.lock`
   - `README.md`
   - `gui/main_window.py`
3. 更新 `docs/changelog.md`。
4. 跑相关测试。
5. 提交：

```bash
git add pyproject.toml uv.lock README.md gui/main_window.py docs/changelog.md
git commit -m "chore: bump version to x.y.z"
```

6. 正式发布时创建 tag：

```bash
git tag -a vx.y.z -m "Release vx.y.z"
git push origin main
git push origin vx.y.z
```

## Changelog 规则

`docs/changelog.md` 用于记录开发过程中的用户可感知变化和重要内部变化。

每个版本建议包含：

```markdown
## x.y.z - YYYY-MM-DD

### Added

### Changed

### Fixed

### Documentation

### Verification
```

Release notes 可以基于 `docs/changelog.md` 和 git diff 生成。

## 提交追溯规则

提交信息使用 Conventional Commits：

- `feat: ...` 新功能
- `fix: ...` 修 bug
- `docs: ...` 文档
- `test: ...` 测试
- `refactor: ...` 重构
- `chore: ...` 构建、版本、杂项

建议：

- 大功能提交包含对应文档更新。
- bug 修复提交包含测试或验证说明。
- Release 提交只做版本同步和必要 changelog 更新。

## Release 前检查

```bash
git status --short
uv run pytest
! grep -R "/Users/" -n config/user.release.json
! grep -R "signature_path.*Users\|custom_path.*Users" -n config/user.release.json
```

如涉及打包配置，追加：

```bash
uv pip install pyinstaller
uv run pyinstaller scripts/build.spec --clean --noconfirm
python -m json.tool dist/aka-semi-utils/_internal/config/user.json
! grep -R "/Users/" -n dist/aka-semi-utils/_internal/config/user.json
```

## Release 后检查

```bash
gh run list --repo BakaAkari/aka-semi-utils --workflow "Build & Release (Windows / macOS / Linux)" --limit 5
gh run watch <run-id> --repo BakaAkari/aka-semi-utils --exit-status
gh release view vx.y.z --repo BakaAkari/aka-semi-utils --json tagName,url,isDraft,isPrerelease,assets,publishedAt
```

Release assets 应包含：

- `aka-semi-utils-windows-vx.y.z.zip`
- `aka-semi-utils-macos-vx.y.z.tar.gz`
- `aka-semi-utils-linux-vx.y.z.tar.gz`