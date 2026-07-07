#!/usr/bin/env bash
# stop.sh - 停止 aka-semi-utils Web 后端服务
# 用法: ./scripts/stop.sh

set -euo pipefail

PORT=2189
PID_FILE="/tmp/semi-utils.pid"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[stop]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[err]${NC} $*"; }

# 从 PID 文件停止
stop_by_pid_file() {
    if [ -f "${PID_FILE}" ]; then
        local pid
        pid="$(cat "${PID_FILE}" 2>/dev/null || echo '')"
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            log "正在停止服务 (PID: ${pid})..."
            kill "${pid}" 2>/dev/null || true
            sleep 1

            # 确认已停止
            if kill -0 "${pid}" 2>/dev/null; then
                warn "服务未响应，强制终止..."
                kill -9 "${pid}" 2>/dev/null || true
            fi

            log "✅ 服务已停止"
            rm -f "${PID_FILE}"
            return 0
        fi
        rm -f "${PID_FILE}"
    fi
    return 1
}

# 从端口查找并停止
stop_by_port() {
    local pid
    pid="$(lsof -ti :${PORT} 2>/dev/null || echo '')"
    if [ -n "${pid}" ]; then
        log "正在停止端口 ${PORT} 的进程 (PID: ${pid})..."
        kill "${pid}" 2>/dev/null || true
        sleep 1
        if kill -0 "${pid}" 2>/dev/null; then
            kill -9 "${pid}" 2>/dev/null || true
        fi
        log "✅ 服务已停止"
        return 0
    fi
    return 1
}

# 主流程
if stop_by_pid_file; then
    exit 0
fi

if stop_by_port; then
    exit 0
fi

warn "没有找到运行中的服务"
