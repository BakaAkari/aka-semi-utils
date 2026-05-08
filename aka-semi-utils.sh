#!/bin/bash
# aka-semi-utils 极简水印启动脚本

set -u

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR" || exit 1

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "启动失败：找不到 uv。当前 PATH：$PATH" >&2
    exit 1
fi

uv run python main.py
