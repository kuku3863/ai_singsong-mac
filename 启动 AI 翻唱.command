#!/bin/bash

PROJECT_DIR="/Users/liubin/Desktop/ai_singsong"
RVC_SCRIPT="$PROJECT_DIR/rvc/Start_RVC.command"
SVC_SCRIPT="$PROJECT_DIR/so-vits-svc/Start_WebUI_Mac.sh"
UNIFIED_SCRIPT="$PROJECT_DIR/start.sh"
MXGF83_SCRIPT="/Users/liubin/Documents/Mac_AI_Cover/启动Mac_AI翻唱.command"

clear 2>/dev/null || true
echo "========================================================"
echo "AI 翻唱统一启动入口"
echo "========================================================"
echo ""
echo "请选择要启动的项目："
echo ""
echo "  1) RVC 独立 WebUI"
echo "  2) So-VITS-SVC 独立 WebUI"
echo "  3) 混合一体 WebUI (RVC + SVC)"
echo "  4) MXGF 8.3 Mac AI 翻唱工作台"
echo "  5) 混合一体 WebUI - 稳定 CPU 模式"
echo "  q) 退出"
echo ""

read -r -p "请输入数字 [1/2/3/4/5/q]: " choice

case "$choice" in
    1)
        echo ""
        echo "正在启动 RVC 独立 WebUI..."
        exec "$RVC_SCRIPT"
        ;;
    2)
        echo ""
        echo "正在启动 So-VITS-SVC 独立 WebUI..."
        exec "$SVC_SCRIPT"
        ;;
    3)
        echo ""
        echo "正在启动混合一体 WebUI..."
        cd "$PROJECT_DIR" || exit 1
        exec "$UNIFIED_SCRIPT"
        ;;
    4)
        echo ""
        echo "正在启动 MXGF 8.3 Mac AI 翻唱工作台..."
        if [[ ! -x "$MXGF83_SCRIPT" ]]; then
            echo "启动脚本不存在或不可执行: $MXGF83_SCRIPT"
            read -r -p "按Enter键关闭窗口..."
            exit 1
        fi
        exec "$MXGF83_SCRIPT"
        ;;
    5)
        echo ""
        echo "正在启动混合一体 WebUI（稳定 CPU 模式）..."
        cd "$PROJECT_DIR" || exit 1
        exec "$UNIFIED_SCRIPT" --cpu
        ;;
    q|Q)
        echo "已退出。"
        exit 0
        ;;
    *)
        echo "输入无效。"
        read -r -p "按Enter键关闭窗口..."
        exit 1
        ;;
esac
