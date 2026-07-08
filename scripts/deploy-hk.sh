#!/usr/bin/env bash
# deploy-hk.sh - 一键部署 aka-semi-utils Web 到腾讯云香港服务器
# 用法: ./scripts/deploy-hk.sh [remote_host]
# 默认远程主机: tencent-hk (依赖 ~/.ssh/config 中的 Host 别名)

set -euo pipefail

PROJECT_NAME="aka-semi-utils-web"
REMOTE_HOST="${1:-tencent-hk}"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/opt/${PROJECT_NAME}"
REMOTE_DATA_DIR="/var/lib/${PROJECT_NAME}"
REMOTE_WWW_DIR="/var/www/${PROJECT_NAME}"
REMOTE_ENV="/etc/${PROJECT_NAME}.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
info() { echo -e "${BLUE}[info]${NC} $*"; }
err()  { echo -e "${RED}[err]${NC} $*"; exit 1; }

# ---------- 本地构建与验证 ----------
log "Step 1: 本地后端静态检查..."
cd "${LOCAL_DIR}"
uv run ruff check . || err "ruff 检查失败"

log "Step 2: 本地后端测试..."
uv run pytest -q || err "pytest 未通过"

log "Step 3: 本地前端构建..."
cd "${LOCAL_DIR}/web_frontend"
npm ci
npm run build

# ---------- 远程部署 ----------
log "Step 4: 停止远程服务..."
ssh "${REMOTE_HOST}" "sudo systemctl stop ${PROJECT_NAME} || true"

log "Step 5: 同步源码到远程..."
rsync -avz --delete \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='.mypy_cache' \
    --exclude='.ruff_cache' \
    --exclude='node_modules' \
    --exclude='web_frontend/node_modules' \
    --exclude='web_frontend/dist' \
    --exclude='dist' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='aka-semi-utils.app' \
    --exclude='build' \
    --exclude='.tox' \
    --exclude='htmlcov' \
    --exclude='.coverage' \
    --exclude='input' \
    --exclude='output' \
    --exclude='logs' \
    --exclude='tmp' \
    "${LOCAL_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/"

log "Step 6: 同步前端构建产物到远程..."
rsync -avz --delete \
    "${LOCAL_DIR}/web_frontend/dist/" "${REMOTE_HOST}:${REMOTE_WWW_DIR}/"

log "Step 7: 远程安装依赖、修复权限并重启服务..."
ssh "${REMOTE_HOST}" "
set -e

cd ${REMOTE_DIR}

# 确保 uv Python 安装目录可读写
UV_PYTHON_INSTALL_DIR=/opt/uv-python
export UV_PYTHON_INSTALL_DIR
uv sync --frozen --no-dev --python 3.13

# 修复源码与依赖权限，确保 www-data 可读
find ${REMOTE_DIR} -type d -exec chmod 755 {} \\;
find ${REMOTE_DIR} -type f -exec chmod 644 {} \\;
chmod -R 755 ${REMOTE_DIR}/.venv/bin

# 修复 uv Python 目录权限
find \${UV_PYTHON_INSTALL_DIR} -type d -exec chmod 755 {} \\; 2>/dev/null || true
find \${UV_PYTHON_INSTALL_DIR} -type f -exec chmod 644 {} \\; 2>/dev/null || true
chmod -R 755 \${UV_PYTHON_INSTALL_DIR}/*/bin 2>/dev/null || true

# 确保运行时目录存在且对服务可写
sudo mkdir -p ${REMOTE_DATA_DIR}/uploads ${REMOTE_DATA_DIR}/outputs ${REMOTE_DATA_DIR}/tmp ${REMOTE_DATA_DIR}/resources/logo ${REMOTE_DATA_DIR}/resources/signature
sudo chown -R www-data:www-data ${REMOTE_DATA_DIR}

# 如果环境文件不存在，使用示例创建并提示
if [ ! -f ${REMOTE_ENV} ]; then
    sudo cp ${REMOTE_DIR}/deploy/aka-semi-utils-web.env.example ${REMOTE_ENV}
    echo '已创建 ${REMOTE_ENV}，请检查并调整配置后重新部署'
fi

# 安装/更新 systemd unit 与 Caddyfile
sudo cp ${REMOTE_DIR}/deploy/aka-semi-utils-api.service /etc/systemd/system/${PROJECT_NAME}.service
sudo cp ${REMOTE_DIR}/deploy/Caddyfile /etc/caddy/Caddyfile

sudo systemctl daemon-reload
sudo systemctl enable ${PROJECT_NAME}
sudo systemctl restart ${PROJECT_NAME}
sudo systemctl reload-or-restart caddy
"

log "Step 8: 健康检查..."
sleep 2
ssh "${REMOTE_HOST}" "
set -e
curl -s http://127.0.0.1:2189/api/health
echo
curl -s https://photo.baka-akari.icu/api/health
echo
JS_URL=\$(curl -s https://photo.baka-akari.icu/ | grep -oE '/assets/index-[A-Za-z0-9_-]+\.js' | head -1)
curl -sI \"https://photo.baka-akari.icu\${JS_URL}\" | grep -i 'content-type: text/javascript'
"

log "✅ 部署完成: https://photo.baka-akari.icu/"
