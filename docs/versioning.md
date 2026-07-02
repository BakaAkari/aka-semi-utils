# Web 版本与追溯规则

桌面版最终版本为 `v2.1.9`，保存在 `archive/desktop-v2`，不再更新。

Web 使用独立 SemVer 版本线，从 `0.1.0` 开始：

- `0.x`：公开测试前及公开测试阶段，API 允许调整。
- `1.0.0`：公开服务稳定、隐私与运维流程完成后发布。
- Patch：兼容修复；Minor：用户能力或 API 增量；Major：稳定版破坏性变更。

版本同步位置：`pyproject.toml`、`uv.lock`、`web_frontend/package.json` 和 changelog。

所有 PR 必须通过 Python lint/tests 与前端生产构建。正式 tag 前还需完成腾讯云健康检查、上传处理下载冒烟测试、TTL 清理和限流验证。
