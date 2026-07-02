# 极简水印 Web

面向摄影照片的公开 Web 水印工具。支持 EXIF 字段、品牌 Logo、签名水印、实时预览与批量处理。

桌面版已冻结在 `v2.1.9`，源码位于 `archive/desktop-v2` 分支；当前 `main` 只维护 Web 产品。

## 本地开发

后端：

```bash
uv sync --dev
uv run uvicorn web_api.main:app --host 127.0.0.1 --port 2189 --reload
```

前端：

```bash
cd web_frontend
npm ci
npm run dev
```

访问 `http://127.0.0.1:5173/`。

## 验证

```bash
uv run ruff check .
uv run pytest
cd web_frontend && npm ci && npm run build
```

## 安全模型

- 用户文本按纯文本处理，不能作为 Jinja 模板执行。
- Logo 和签名只使用服务端签发的资源 ID。
- 上传大小、图片像素、配置数值和处理并发均有硬限制。
- 匿名上传、输出和资源默认一小时后删除。
- 生产环境必须启用 HTTPS、请求体限制和按 IP 限流。

详细设计见 [`docs/web_mvp_design.md`](docs/web_mvp_design.md)。

## 许可证

GPL-3.0，见 [`LICENSE`](LICENSE)。
