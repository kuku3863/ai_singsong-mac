#!/bin/bash

# macOS启动脚本 - So-VITS-SVC WebUI (本地版本)
# 适配Apple M5 GPU (MPS) 和 macOS环境

echo "========================================================"
echo "启动 So-VITS-SVC WebUI (macOS版本)"
echo "环境: /opt/miniconda3/envs/sovits_env_mac"
echo "脚本: webUI_local.py"
echo "GPU加速: Apple M5 GPU (MPS) 已启用"
echo "========================================================"
echo ""
echo "重要提示: 关闭此窗口将自动终止进程。"
echo "Web界面: http://127.0.0.1:7860"
echo ""
echo "正在启动..."

# 设置工作目录
cd "/Users/liubin/Desktop/ai_singsong/so-vits-svc"

# 检查目录是否存在
if [ ! -d "/Users/liubin/Desktop/ai_singsong/so-vits-svc" ]; then
    echo "错误: 找不到项目目录!"
    echo "请检查路径: /Users/liubin/Desktop/ai_singsong/so-vits-svc"
    exit 1
fi

# 检查conda环境是否存在
if [ ! -f "/opt/miniconda3/envs/sovits_env_mac/bin/python" ]; then
    echo "错误: 找不到Conda环境!"
    echo "请先创建环境: conda create -n sovits_env_mac python=3.10.20"
    exit 1
fi

# 避免把 conda base 的动态库注入到子环境。
# macOS 的 _scproxy 模块会加载 iconv；强制使用 /opt/miniconda3/lib
# 可能导致 libiconv/libunistring 版本不匹配，从而让 gradio/httpx 导入失败。
unset DYLD_LIBRARY_PATH
echo "已清理库路径: DYLD_LIBRARY_PATH 未设置"

# 设置FFmpeg路径（解决音频转换问题）
export FFMPEG_PATH="/opt/miniconda3/bin/ffmpeg"
export PATH="/opt/miniconda3/bin:$PATH"
echo "已设置FFmpeg路径: FFMPEG_PATH=/opt/miniconda3/bin/ffmpeg"

# 设置本地缓存目录，避免 matplotlib/numba 因用户缓存目录权限或定位问题启动失败。
mkdir -p "temp/runtime_cache/matplotlib" "temp/runtime_cache/numba"
export MPLCONFIGDIR="$PWD/temp/runtime_cache/matplotlib"
export NUMBA_CACHE_DIR="$PWD/temp/runtime_cache/numba"
echo "已设置运行缓存目录: temp/runtime_cache"

# 避免 httpx 在导入 gradio 时继承系统代理而尝试初始化代理传输。
unset ALL_PROXY all_proxy
unset HTTP_PROXY http_proxy
unset HTTPS_PROXY https_proxy
unset FTP_PROXY ftp_proxy
echo "已禁用代理环境变量: ALL_PROXY/HTTP_PROXY/HTTPS_PROXY"

# 本地WebUI不应经过代理。
export NO_PROXY="127.0.0.1,localhost,::1${NO_PROXY:+,$NO_PROXY}"
export no_proxy="127.0.0.1,localhost,::1${no_proxy:+,$no_proxy}"
echo "已设置本地直连: NO_PROXY=127.0.0.1,localhost,::1"

# 运行WebUI
echo "正在启动WebUI服务..."
echo "========================================================"

# 使用完整路径运行Python
/opt/miniconda3/envs/sovits_env_mac/bin/python -u webUI_local.py

# 脚本结束后显示消息
echo ""
echo "========================================================"
echo "WebUI服务已停止。"
echo "如果要重新启动，请再次运行此脚本。"
echo "========================================================"

# 等待用户按Enter键，防止窗口立即关闭
read -p "按Enter键关闭窗口..."
