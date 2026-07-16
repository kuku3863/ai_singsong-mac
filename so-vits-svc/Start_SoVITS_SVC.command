#!/bin/bash

# macOS桌面快捷方式 - So-VITS-SVC WebUI启动器
# 双击此文件启动So-VITS-SVC WebUI服务

echo "========================================================"
echo "So-VITS-SVC WebUI 启动器"
echo "版本: macOS GPU加速版 (Apple M5 MPS)"
echo "========================================================"
echo ""
echo "正在启动主程序..."

# 桌面快捷方式固定指向当前整合项目内的独立 So-VITS-SVC。
PROJECT_DIR="/Users/liubin/Desktop/ai_singsong/so-vits-svc"
MAIN_SCRIPT="$PROJECT_DIR/Start_WebUI_Mac.sh"

# 检查主脚本是否存在
if [ ! -f "$MAIN_SCRIPT" ]; then
    echo "错误: 找不到主启动脚本!"
    echo "请检查路径: $MAIN_SCRIPT"
    echo "请确保Start_WebUI_Mac.sh文件存在。"
    echo ""
    read -p "按Enter键退出..." 
    exit 1
fi

# 检查脚本是否可执行
if [ ! -x "$MAIN_SCRIPT" ]; then
    echo "警告: 主脚本没有执行权限，正在添加..."
    chmod +x "$MAIN_SCRIPT"
fi

echo "项目目录: $PROJECT_DIR"
echo "主脚本: $MAIN_SCRIPT"
echo ""
echo "正在启动So-VITS-SVC WebUI..."
echo "Web界面将在浏览器中打开: http://127.0.0.1:7860"
echo ""
echo "注意: 关闭此窗口将终止WebUI服务。"
echo "========================================================"

# 优先使用 Ghostty 打开独立终端窗口运行主脚本。
if [ -d "/Applications/Ghostty.app" ]; then
    osascript <<EOF
tell application "Ghostty"
    activate
end tell
tell application "System Events"
    keystroke "n" using command down
    delay 0.3
    keystroke "cd \"$PROJECT_DIR\" && \"$MAIN_SCRIPT\""
    key code 36
end tell
EOF
    exit 0
fi

# 未安装 Ghostty 时，退回当前终端执行主脚本。
exec "$MAIN_SCRIPT"
