# Web 版本与追溯规则

桌面最终版为 `v2.1.9`，保存在 `archive/desktop-v2`，不再更新。

Web/V3 使用独立 SemVer 版本线，从 `0.1.0` 开始：

- `0.x`：公开测试前及公开测试阶段，API 和配置允许破坏性调整。
- `1.0.0`：公开服务稳定、隐私与运维流程完成后发布。
- Patch：兼容修复。
- Minor：用户能力或 API 增量。
- Major：稳定版破坏性变更。

版本同步位置：

- `pyproject.toml`
- `uv.lock`
- `web_frontend/package.json`
- `docs/changelog.md`

正式 tag 前必须完成：

```bash
uv run ruff check .
uv run pytest
cd web_frontend && VITE_API_BASE=/tools/watermark-v3 npm run build
```

以及线上验证：

- V3 页面 200。
- V3 API health 200。
- 上传、预览、处理、下载冒烟测试。
- V1 页面为“回炉重塑中”。
- V1 API 410。
- V2 404。
- `watermark-v3.service` active，只有 2190 监听。
