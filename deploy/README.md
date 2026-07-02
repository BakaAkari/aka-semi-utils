# 腾讯云部署

1. 将代码部署到 `/opt/aka-semi-utils-web`，执行 `uv sync --frozen --no-dev`。
2. 在 `web_frontend/` 执行 `npm ci && npm run build`，把 `dist/` 同步到 `/var/www/aka-semi-utils-web`。
3. 创建 `/var/lib/aka-semi-utils-web` 并授权给 `www-data`。
4. 从环境变量示例创建 `/etc/aka-semi-utils-web.env`。
5. 安装 systemd unit 与 Caddyfile，执行 daemon-reload、enable 和 restart。
6. DNS 指向服务器并确认 HTTPS、`/api/health`、上传、预览、处理和下载。

生产环境还应在 EdgeOne 或同等入口对 `/api/uploads`、`/api/preview`、`/api/process` 和
`/api/upload-resource` 设置按 IP 限流。源站安全组只开放 SSH、HTTP 和 HTTPS；2189 只监听回环地址。
