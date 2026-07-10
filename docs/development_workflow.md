# Development Workflow / 协作开发流程

本文件固化 V3 水印工具的需求、设计、实现、验证、部署和提交流程。

## 核心流程

```text
需求/方向 → 查阅当前文档 → 更新 roadmap/设计文档 → 用户确认 → 小步实现 → 自动验证 → 线上验证 → 用户手动测试 → 文档同步 → commit/push
```

## 角色分工

### 用户负责

- 提供真实需求、使用场景、优先级和审美方向。
- 审阅并确认 roadmap、阶段设计和验收标准。
- 对线上 GUI 做真实图片测试。
- 反馈 bug、体验问题和期望调整。

### Agent 负责

- 先检查当前 repo 状态和相关文档。
- 将需求整理为目标、范围、非目标、风险、验收标准。
- 在文档对齐前，不做大范围 GUI/架构改动。
- 小步修改代码并运行真实验证。
- 部署后检查页面、API、服务、路由和截图。
- 提交前检查 diff、测试结果、隐私路径和旧版本残留。

## 变更类型与要求

### 文档-only

- 可不跑完整测试。
- 必须检查文档引用、过期路径和当前架构一致性。

### 前端 UI

至少运行：

```bash
cd web_frontend && VITE_API_BASE=/tools/watermark-v3 npm run build
```

部署后用浏览器截图检查。

### 后端 / 配置 / 处理管线

至少运行：

```bash
uv run ruff check .
uv run pytest
```

### 部署

必须验证：

```bash
curl -sS https://baka-akari.zone/tools/watermark-v3/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://baka-akari.zone/tools/watermark-v3/
```

并检查旧入口：

```bash
curl -sS -o /dev/null -w 'v1_api:%{http_code}\n' https://baka-akari.zone/tools/watermark/api/health
curl -sS -o /dev/null -w 'v2:%{http_code}\n' https://baka-akari.zone/tools/watermark-v2/
curl -sS -o /dev/null -w 'v3_v2:%{http_code}\n' https://baka-akari.zone/tools/watermark-v3/v2
```

期望：V1 API `410`，V2 `404`，V3 `/v2` `404`。

## 实现原则

- V3 只接受 Region / Slot / Content 配置。
- 不恢复 V1/V2 四角配置模型。
- 不把用户文本送入 Jinja 或动态模板执行器。
- 上传资源只能用服务端不透明 ID。
- 普通用户 UI 走模板驱动，高级结构编辑默认收起。
- 大范围控制面改造前先更新 `design/v3-control-surface-guardrails.md`。

## 提交前检查

```bash
git status --short
git diff --stat
git diff --check
```

提交信息使用 Conventional Commits：

```text
feat: add layout guardrails
fix: prevent v3 resource path injection
docs: refresh v3 roadmap
chore: remove legacy watermark files
```

## 文档组织

- `README.md`：当前项目入口。
- `docs/roadmap.md`：当前路线图。
- `design/v3-region-based-layout.md`：当前 V3 架构说明。
- `design/v3-control-surface-guardrails.md`：下一阶段控制面设计。
- `deploy/README.md`：线上部署和验证。
- `docs/archive/`：历史设计，仅作背景，不作为当前待办。
