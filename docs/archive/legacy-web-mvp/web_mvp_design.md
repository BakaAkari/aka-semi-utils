# Web MVP Design / 极简水印 Web 端设计

## 结论

Web 端可行，但不直接迁移 PyQt GUI。最佳路线是在现有仓库 `feat/web-mvp` 分支中推进 MVP：复用现有 Python 图片处理核心，新增低耦合的共享配置层、FastAPI 后端与 React/Vite 前端。

当前阶段不新开 GitHub 仓库，避免核心逻辑复制和版本漂移。桌面最终版通过
`v2.1.9` 与 `archive/desktop-v2` 冻结，Web 进入独立版本线。

## 一致性原则

Web 端与桌面端必须共享同一套核心事实：

- 同一套处理管线：`processor.core.PipelineEngine` / `start_process()`。
- 同一套 processor JSON 格式。
- 同一套水印配置 schema：字段 chip、四角布局、Logo、签名、高级参数。
- 同一套默认资源：字体、Logo、模板配置。
- 同一套 EXIF 字段渲染规则。
- 同一套关键测试和验收标准。

一致性基准：同一输入图片 + 同一水印配置，应生成同一份 processor JSON，并产出视觉一致的水印结果。

## 目标仓库结构

```text
aka-semi-utils/
  core/                  # 共享：配置、EXIF、字体、图片 IO
  processor/             # 共享：图片处理管线
  config/                # 共享：字体、Logo、默认配置
  shared/                # 新增：纯 schema + field registry + processor assembler
  web_api/               # 新增：FastAPI 后端
  web_frontend/          # 新增：React/Vite 前端
  tests/
    unit/
    integration/
    web_api/
```

## 分层边界

### shared/

只放纯 Python 共享逻辑，不依赖 PyQt、FastAPI、React 或服务器路径。

建议模块：

```text
shared/
  __init__.py
  watermark_schema.py
  field_registry.py
  processor_assembler.py
  validation.py
```

职责：

- 定义纯配置模型。
- 定义字段 registry 与 Jinja 模板映射。
- 将配置对象转换为 processor JSON。
- 提供 Web / Desktop 共享的配置校验。

### 桌面归档

PyQt GUI、PyInstaller 和三平台桌面发布流程只保留在 `archive/desktop-v2`，不再作为
Web 主线依赖或测试目标。

### web_api/

FastAPI 后端。只依赖：

- `shared/`
- `core/`
- `processor/`
- 必要的 Python Web 依赖

禁止依赖 `gui/*`。

### web_frontend/

React/Vite 前端。通过 HTTP API 与后端交互，不直接接触 Python 内部结构。

## MVP API

```text
GET  /api/health
POST /api/preview
POST /api/process
```

### GET /api/health

健康检查，返回：

```json
{ "status": "ok" }
```

### POST /api/preview

输入：单张图片 + 配置 JSON。

目标：快速返回缩小版预览图。

限制：预览应限制最大边长，避免大图频繁请求拖垮服务器。

### POST /api/process

输入：单张图片 + 配置 JSON。

目标：生成正式输出图片，返回图片或下载 URL。

## 腾讯云部署目标

推荐使用独立子域名，降低子路径、缓存与安全策略的耦合：

```text
https://photo.baka-akari.icu/
```

服务器路径：

```text
/opt/aka-semi-utils-web/              # 后端代码与运行环境
/var/www/personal-home/semi-utils/    # 前端静态产物
/var/lib/aka-semi-utils-web/          # 上传、输出、临时文件
/etc/systemd/system/aka-semi-utils-web.service
/etc/caddy/Caddyfile
```

## 风险与约束

- `gui.models.AppState` 依赖 PyQt，不应被 Web 直接引用。
- 腾讯云服务器内存约 1.6G，必须限制上传大小、最大像素和并发处理数。
- 项目要求 Python 3.13，服务器系统 Python 当前为 3.12，需要 uv / Docker / 独立 Python 环境。
- Web API 不允许用户传入服务端任意路径；Logo / 签名只能使用服务端签发的资源 ID。
- 用户文本必须始终按纯文本处理，不允许进入服务端 Jinja 模板执行。
- 上传、预览和输出必须按 TTL 自动删除，并限制全局图片处理并发。
- MVP 不做账号系统、模板市场、多租户、完整批量队列。

## 开发阶段

| 阶段 | 目标 | 状态 | 说明 |
|------|------|------|------|
| 1 | 文档与边界：写入本设计文档，明确 shared / gui / web_api / web_frontend 边界。 | ✅ 已完成 | `docs/web_mvp_design.md` 已编写，桌面版冻结策略已确定。 |
| 2 | 一致性核心：抽出 shared schema、field registry、processor assembler，并让桌面端继续通过共享 assembler 生成 processor JSON。 | ✅ 已完成 | `shared/` 目录已创建，`watermark_schema.py`、`field_registry.py`、`processor_assembler.py` 已实现。 |
| 3 | 后端 MVP：实现 health、preview、process，并用真实图片跑通。 | ✅ 已完成 | API：`/api/health`、`/api/preview`、`/api/process`、`/api/upload-resource`。输入校验、TTL 清理、大小/像素限制已实现。 |
| 4 | 前端 MVP：实现上传、配置、预览、下载。 | ✅ 已完成 | React 19 + Vite 前端，6 个配置 Tab，4 个预设，批量处理入口，玻璃质感 UI。 |
| 5 | 腾讯云部署：systemd + nginx 路由 + 公网验证。 | 🔄 进行中 | 部署脚本和配置文件已生成，待实际上线。 |
| 6 | 产品化增强：批量 job、zip 下载、自定义资源、访问控制、HTTPS。 | 📋 计划中 | 未开始。 |

1. 文档与边界：写入本设计文档，明确 shared / gui / web_api / web_frontend 边界。
2. 一致性核心：抽出 shared schema、field registry、processor assembler，并让桌面端继续通过共享 assembler 生成 processor JSON。
3. 后端 MVP：实现 health、preview、process，并用真实图片跑通。
4. 前端 MVP：实现上传、配置、预览、下载。
5. 腾讯云部署：systemd + Caddy 路由 + 公网验证。
6. 产品化增强：批量 job、zip 下载、自定义资源、访问控制、HTTPS。
