#!/usr/bin/env bash
# deploy.sh - Semi-Utils Web 部署脚本
# 用法: ./scripts/deploy.sh [user@host]

set -euo pipefail

PROJECT_NAME="aka-semi-utils-web"
REMOTE_HOST="${1:-}"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/opt/${PROJECT_NAME}"
REMOTE_DATA_DIR="/var/lib/${PROJECT_NAME}"
REMOTE_WWW_DIR="/var/www/personal-home/semi-utils"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[err]${NC} $*"; exit 1; }

# ---------- 本地构建 ----------
log "Step 1: 本地构建前端..."
cd "${LOCAL_DIR}/web_frontend"
npm run build

log "Step 2: 验证后端测试..."
cd "${LOCAL_DIR}"
uv run pytest tests/ -q || warn "测试未全部通过，继续部署..."

# ---------- 远程部署 ----------
if [ -n "${REMOTE_HOST}" ]; then
    log "Step 3: 准备远程目录..."
    ssh "${REMOTE_HOST}" "sudo mkdir -p ${REMOTE_DIR} ${REMOTE_DATA_DIR}/uploads ${REMOTE_DATA_DIR}/outputs ${REMOTE_DATA_DIR}/tmp ${REMOTE_DATA_DIR}/resources/logo ${REMOTE_DATA_DIR}/resources/signature ${REMOTE_WWW_DIR}"

    log "Step 4: 上传代码..."
    rsync -avz --delete \
        --exclude='.git' --exclude='.venv' --exclude='node_modules' \
        --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' \
        --exclude='dist/' --exclude='*.log' \
        "${LOCAL_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/"

    log "Step 5: 上传前端构建产物..."
    rsync -avz --delete \
        "${LOCAL_DIR}/web_frontend/dist/" "${REMOTE_HOST}:${REMOTE_WWW_DIR}/"

    log "Step 6: 上传 systemd + nginx 配置..."
    scp "${LOCAL_DIR}/scripts/aka-semi-utils-web.service" "${REMOTE_HOST}:/tmp/"
    scp "${LOCAL_DIR}/scripts/semi-utils.nginx.conf" "${REMOTE_HOST}:/tmp/"
    ssh "${REMOTE_HOST}" "sudo mv /tmp/aka-semi-utils-web.service /etc/systemd/system/ && sudo mv /tmp/semi-utils.nginx.conf /etc/nginx/conf.d/ && sudo nginx -t && sudo systemctl reload nginx"

    log "Step 7: 安装依赖并启动..."
    ssh "${REMOTE_HOST}" "cd ${REMOTE_DIR} && python3 -m venv .venv && .venv/bin/pip install -e '.[web]' && sudo systemctl daemon-reload && sudo systemctl enable ${PROJECT_NAME} && sudo systemctl restart ${PROJECT_NAME}"

    log "Step 8: 健康检查..."
    sleep 3
    ssh "${REMOTE_HOST}" "curl -s http://127.0.0.1:2189/api/health" || err "健康检查失败"

    log "✅ 部署完成！"
    log "访问: https://photo.baka-akari.icu/semi-utils/"
else
    log "未指定远程主机，仅生成本地部署配置。"
    log "配置文件位置:"
    log "  systemd: ${LOCAL_DIR}/scripts/aka-semi-utils-web.service"
    log "  nginx:   ${LOCAL_DIR}/scripts/semi-utils.nginx.conf"
    log ""
    log "手动启动: uv run python -m uvicorn web_api.main:app --host 127.0.0.1 --port 2189"
fi
