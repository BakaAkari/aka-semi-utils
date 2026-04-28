#!/bin/bash
# aka-semi-utils 极简水印启动脚本

cd "$(dirname "$0")"
uv run python main.py
