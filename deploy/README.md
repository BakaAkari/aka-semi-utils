# 腾讯云 V3 部署

当前线上 V3：

```text
https://baka-akari.zone/tools/watermark-v3/
```

## 路径与服务

- 前端静态文件：`/var/www/personal-home/tools/watermark-v3/`
- 后端代码：`/opt/aka-semi-utils-web-v2/`（历史目录名，当前运行 V3）
- systemd：`watermark-v3.service`
- 端口：`127.0.0.1:2190`
- API prefix：`/tools/watermark-v3/api`
- 数据目录：`/var/lib/aka-semi-utils-web-v3/`

旧入口：

- `/tools/watermark/`：静态占位页“回炉重塑中”。
- `/tools/watermark/api/*`：`410 Gone`。
- `/tools/watermark-v2/*`：不存在，返回 `404`。
- `/tools/watermark-v3/v2`：返回 `404`。

## 前端部署

```bash
cd web_frontend
VITE_API_BASE=/tools/watermark-v3 npm run build
cd dist
tar czf - . | ssh tencent-ubuntu "sudo tar xzf - -C /var/www/personal-home/tools/watermark-v3/ && sudo chown -R www-data:www-data /var/www/personal-home/tools/watermark-v3/"
```

## 后端部署

```bash
rsync -avz --delete \
  --exclude='web_frontend/node_modules' --exclude='web_frontend/dist' \
  --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
  --exclude='*.pyc' --exclude='.DS_Store' \
  --exclude='archive' --exclude='design' --exclude='docs' \
  --exclude='.pytest_cache' --exclude='.ruff_cache' --exclude='.mypy_cache' \
  --exclude='build' --exclude='static' --exclude='gui' \
  --exclude='aka-semi-utils-web-v2.env' \
  --rsync-path='sudo rsync' \
  ./ tencent-ubuntu:/opt/aka-semi-utils-web-v2/
```

注意：`config/logos/` 是 V3 自动 Logo 资源目录，保留在源码中并同步到线上，不要排除。如需排除 `config/` 中其他内容，请显式列出子目录。

```bash
ssh tencent-ubuntu "sudo chown -R www-data:www-data /opt/aka-semi-utils-web-v2/ && sudo chmod 755 /opt/aka-semi-utils-web-v2 && sudo systemctl restart watermark-v3.service"
```

重启后验证：

```bash
ssh tencent-ubuntu "systemctl is-active watermark-v3.service && curl -sS -o /dev/null -w 'api:%{http_code}\n' https://baka-akari.zone/tools/watermark-v3/api/health && curl -sS -o /dev/null -w 'logo:%{http_code}\n' https://baka-akari.zone/tools/watermark-v3/api/logos/default.png"
```

## V1 占位页部署

源文件：`deploy/legacy-watermark-placeholder/index.html`。

```bash
tar czf - -C deploy/legacy-watermark-placeholder . | ssh tencent-ubuntu "sudo rm -rf /var/www/personal-home/tools/watermark && sudo mkdir -p /var/www/personal-home/tools/watermark && sudo tar xzf - -C /var/www/personal-home/tools/watermark/ && sudo chown -R www-data:www-data /var/www/personal-home/tools/watermark/ && sudo chmod -R u=rwX,go=rX /var/www/personal-home/tools/watermark"
```

## 验证

```bash
curl -sS -o /tmp/wm_v1.html -w 'v1:%{http_code}\n' https://baka-akari.zone/tools/watermark/
grep -o '回炉重塑中' /tmp/wm_v1.html | head -1
curl -sS -o /dev/null -w 'v1_api:%{http_code}\n' https://baka-akari.zone/tools/watermark/api/health
curl -sS -o /dev/null -w 'v2:%{http_code}\n' https://baka-akari.zone/tools/watermark-v2/
curl -sS -o /dev/null -w 'v3_v2:%{http_code}\n' https://baka-akari.zone/tools/watermark-v3/v2
curl -sS -o /dev/null -w 'v3:%{http_code}\n' https://baka-akari.zone/tools/watermark-v3/
curl -sS -w '\nv3_api:%{http_code}\n' https://baka-akari.zone/tools/watermark-v3/api/health
```

期望：

```text
v1:200 + 回炉重塑中
v1_api:410
v2:404
v3_v2:404
v3:200
v3_api:200
```

服务器侧：

```bash
ssh tencent-ubuntu '
  systemctl list-units --type=service --all "*watermark*" "*aka-semi*" --no-pager
  sudo ss -ltnp | grep -E ":2189|:2190" || true
  sudo test ! -e /opt/aka-semi-utils-web-v2/web_api/schemas.py && echo no_old_schema
  sudo test ! -e /opt/aka-semi-utils-web-v2/shared/watermark_schema.py && echo no_old_watermark_schema
  sudo test ! -e /opt/aka-semi-utils-web-v2/shared/processor_assembler.py && echo no_old_assembler
  sudo test ! -d /var/www/personal-home/tools/watermark-v2 && echo no_v2_static
'
```

期望只剩 `watermark-v3.service` active，只有 `127.0.0.1:2190` 监听。
