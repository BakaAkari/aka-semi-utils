# aka-semi-utils Web Agent 指南

## 项目定位

当前主线是公开 Web 摄影水印工具：React/Vite 前端、FastAPI API 和 Python 图片处理核心。
桌面版冻结在 `v2.1.9` 与 `archive/desktop-v2`，禁止在 `main` 恢复 PyQt、PyInstaller 或桌面发布流程。

## 结构

- `web_frontend/`：React/Vite UI。
- `web_api/`：HTTP API、安全校验、上传和输出生命周期。
- `shared/`：纯领域 schema、字段注册和处理器组装。
- `core/`、`processor/`：图片、EXIF 与处理管线。
- `deploy/`：腾讯云 systemd/Caddy 部署配置。
- `tests/`：单元、集成和 Web API 测试。

## 强制约束

- 用户文本不得进入 Jinja 或其他动态模板执行器。
- API 不得接受服务端路径；上传资源只能通过不透明 ID 引用。
- 所有公开参数必须严格校验类型、枚举、长度和数值范围。
- 图片处理必须限制上传大小、解码像素、并发和文件保留时间。
- 不向客户端返回内部路径、异常堆栈或敏感 EXIF 日志。
- 前端不得提交 `node_modules`、`dist`、`*.tsbuildinfo` 或编译后的 Vite 配置。

## 工作流

较大改动遵循：设计文档 → 用户确认 → 小步实现 → 自动验证 → 提交/PR → 部署验证。

开始修改前执行：

```bash
git status --short
```

提交前执行：

```bash
uv run ruff check .
uv run pytest
cd web_frontend && npm ci && npm run build
```

提交信息使用 Conventional Commits。正式 Web 发布使用独立 `v0.x` 版本线；桌面 `v2.x` tag 不得移动或覆盖。
