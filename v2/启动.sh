#!/usr/bin/env bash
# 正则表达式编译器 —— 一键启动器（Linux / macOS）
#
# 用法:
#   ./启动.sh                启动 Web 图形界面
#   ./启动.sh --menu         显示功能菜单
#   ./启动.sh --test         运行测试

set -e
cd "$(dirname "$0")"

PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo ""
    echo "  [X] 未找到 Python 3.10+"
    echo "      请先安装 Python 3，并确保 python3 或 python 在 PATH 中。"
    echo ""
    exit 1
fi

exec "$PY" start.py "$@"
