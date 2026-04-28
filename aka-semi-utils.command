#!/bin/bash
# aka-semi-utils 极简水印 — 双击自动启动
# 关闭时保留窗口 3 秒，方便查看错误信息

cd "$(dirname "$0")"
uv run python main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "启动失败，按回车键关闭..."
    read
fi
