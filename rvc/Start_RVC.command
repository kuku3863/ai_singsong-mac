#!/bin/bash

# macOS desktop launcher - standalone RVC WebUI.

PROJECT_DIR="/Users/liubin/Desktop/ai_singsong"
RVC_DIR="$PROJECT_DIR/rvc"
PYTHON="$PROJECT_DIR/.venv/bin/python"

echo "========================================================"
echo "RVC WebUI 启动器"
echo "项目目录: $RVC_DIR"
echo "Web界面: 自动选择 7865 起的可用端口"
echo "========================================================"
echo ""

if [ ! -d "$RVC_DIR" ]; then
    echo "错误: 找不到 RVC 目录: $RVC_DIR"
    read -p "按Enter键退出..."
    exit 1
fi

if [ ! -x "$PYTHON" ]; then
    echo "错误: 找不到项目虚拟环境 Python: $PYTHON"
    echo "请先运行: $PROJECT_DIR/install.sh"
    read -p "按Enter键退出..."
    exit 1
fi

unset ALL_PROXY all_proxy
unset HTTP_PROXY http_proxy
unset HTTPS_PROXY https_proxy
unset FTP_PROXY ftp_proxy
echo "已禁用代理环境变量: ALL_PROXY/HTTP_PROXY/HTTPS_PROXY"
export NO_PROXY="127.0.0.1,localhost,::1${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"

mkdir -p "$RVC_DIR/TEMP/runtime_cache/matplotlib" "$RVC_DIR/TEMP/runtime_cache/numba"
export MPLCONFIGDIR="$RVC_DIR/TEMP/runtime_cache/matplotlib"
export NUMBA_CACHE_DIR="$RVC_DIR/TEMP/runtime_cache/numba"
export PATH="/opt/homebrew/bin:/opt/miniconda3/bin:$PATH"

cd "$RVC_DIR" || exit 1
echo "正在启动 RVC WebUI..."
echo "页面就绪后会自动打开；如果没有弹出，请手动打开终端中显示的地址。"
echo "========================================================"
RVC_PORT=$((7865 + RANDOM % 35))
"$PYTHON" -u infer-web.py --noautoopen --port "$RVC_PORT" &
RVC_PID=$!

(
    for _ in {1..60}; do
        for PORT in "$RVC_PORT" {7865..7899}; do
            if curl --noproxy '*' -fsS "http://127.0.0.1:${PORT}" >/dev/null 2>&1; then
                FRESH_TOKEN="$(date +%s)"
                open "http://127.0.0.1:${PORT}/?fresh=${FRESH_TOKEN}"
                exit 0
            fi
        done
        sleep 1
    done
) &

wait "$RVC_PID"

echo ""
echo "========================================================"
echo "RVC WebUI 已停止。"
echo "========================================================"
read -p "按Enter键关闭窗口..."
