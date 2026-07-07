#!/usr/bin/env bash
# start.sh - 启动 aka-semi-utils Web 后端服务
# 用法: ./scripts/start.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PORT=2189
HOST=127.0.0.1
LOG_FILE="/tmp/semi-utils.log"
PID_FILE="/tmp/semi-utils.pid"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[start]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[err]${NC} $*"; }
info() { echo -e "${BLUE}[info]${NC} $*"; }

# 检查是否已在运行
check_running() {
    if [ -f "${PID_FILE}" ]; then
        local pid
        pid="$(cat "${PID_FILE}" 2>/dev/null || echo '')"
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            info "服务已在运行 (PID: ${pid})"
            info "访问地址: http://${HOST}:${PORT}/semi-utils/"
            info "API 文档: http://${HOST}:${PORT}/docs"
            info "日志文件: ${LOG_FILE}"
            echo ""
            info "停止服务: ./scripts/stop.sh"
            exit 0
        fi
    fi

    # 也检查端口占用
    local port_pid
    port_pid="$(lsof -ti :${PORT} 2>/dev/null || netstat -anv 2>/dev/null | grep "\.${PORT} " | awk '{print $9}' | head -1 || echo '')"
    if [ -n "${port_pid}" ]; then
        warn "端口 ${PORT} 已被 PID ${port_pid} 占用"
        warn "如需强制启动，先执行: ./scripts/stop.sh"
        exit 1
    fi
}

# 检查 Python 环境
check_env() {
    cd "${PROJECT_DIR}"

    if [ ! -d ".venv" ]; then
        err "虚拟环境不存在，请先运行: uv sync"
        exit 1
    fi

    if [ ! -f ".venv/bin/uvicorn" ]; then
        err "uvicorn 未安装，请先运行: uv sync"
        exit 1
    fi

    # 检查前端构建产物
    if [ ! -f "web_frontend/dist/index.html" ]; then
        warn "前端构建产物不存在，正在构建..."
        cd "${PROJECT_DIR}/web_frontend"
        npm run build
        cd "${PROJECT_DIR}"
    fi
}

# 启动服务
start_server() {
    cd "${PROJECT_DIR}"

    log "启动 aka-semi-utils Web 后端..."
    log "端口: ${PORT}"
    log "日志: ${LOG_FILE}"
    log "项目目录: ${PROJECT_DIR}"
    echo ""

    # 清理旧日志
    > "${LOG_FILE}"

    # 启动 uvicorn（后台）
    nohup .venv/bin/python -m uvicorn web_api.main:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --workers 1 \
        > "${LOG_FILE}" 2>&1 &

    local pid=$!
    echo "${pid}" > "${PID_FILE}"

    # 等待启动
    log "等待服务启动..."
    local attempts=0
    local max_attempts=30

    while [ ${attempts} -lt ${max_attempts} ]; do
        sleep 0.5

        # 检查进程是否存活
        if ! kill -0 "${pid}" 2>/dev/null; then
            err "进程已退出，请查看日志: ${LOG_FILE}"
            cat "${LOG_FILE}" | tail -20
            rm -f "${PID_FILE}"
            exit 1
        fi

        # 检查健康接口
        if curl -s "http://${HOST}:${PORT}/api/health" > /dev/null 2>&1; then
            echo ""
            log "✅ 服务启动成功！"
            echo ""
            info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            info "  🌐 前端界面: http://${HOST}:${PORT}/semi-utils/"
            info "  📚 API 文档: http://${HOST}:${PORT}/docs"
            info "  ❤️  健康检查: http://${HOST}:${PORT}/api/health"
            info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            info "  实时日志: tail -f ${LOG_FILE}"
            info "  停止服务: ./scripts/stop.sh"
            echo ""
            exit 0
        fi

        attempts=$((attempts + 1))
        echo -n "."
    done

    err "服务启动超时 (${max_attempts}s)"
    err "请查看日志: ${LOG_FILE}"
    cat "${LOG_FILE}" | tail -20
    rm -f "${PID_FILE}"
    exit 1
}

# 主流程
check_running
check_env
start_server
