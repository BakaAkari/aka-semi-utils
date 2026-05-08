#!/bin/bash
# aka-semi-utils 极简水印 — 双击自动启动
# 失败时保留窗口，方便查看错误信息。

set -u

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR" || exit 1

# macOS 双击 .command 时 PATH 往往比交互式终端少，手动补齐常见安装位置。
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "启动 aka-semi-utils..."
echo "项目目录：$APP_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo ""
    echo "启动失败：找不到 uv。"
    echo "请先安装 uv，或确认 uv 所在目录已加入 PATH。"
    echo "当前 PATH：$PATH"
    echo ""
    echo "按回车键关闭..."
    read -r _
    exit 1
fi

uv run python main.py
status=$?

if [ "$status" -ne 0 ]; then
    echo ""
    echo "启动失败，退出码：$status"
    echo "按回车键关闭..."
    read -r _
fi

exit "$status"
