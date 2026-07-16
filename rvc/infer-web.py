# -*- coding: utf-8 -*-
import os
import sys

# 修复Windows控制台GBK编码不支持Unicode字符的问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

    # 修复 Windows ProactorEventLoop 子进程管道回调异常
    # Python 3.8+ 默认使用 ProactorEventLoop，子进程结束后
    # _ProactorBasePipeTransport._call_connection_lost 会抛异常
    # 切换为 SelectorEventLoop 可彻底避免此问题
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import socket
import shutil
from dotenv import load_dotenv


def get_free_port(start_port=7865):
    """获取可用端口，如果指定端口被占用则自动寻找下一个可用端口"""
    port = start_port
    max_port = 65535
    while port <= max_port:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            port += 1
    return None


def print_banner():
    """打印美观的启动横幅"""
    banner = r"""
╔════════════════════════════════════════════════════════════════╗
║                                                                    ║
║   ██████╗ ██╗   ██╗ ██████╗    ███╗   ███╗██╗  ██╗ ██████╗   ║
║   ██╔══██╗██║   ██║██╔════╝    ████╗ ████║╚██╗██╔╝██╔════╝   ║
║   ██████╔╝██║   ██║██║         ██╔████╔██║ ╚███╔╝ ██║        ║
║   ██╔══██╗██║   ██║██║         ██║╚██╔╝██║ ██╔██╗ ██║        ║
║   ██║  ██║╚██████╔╝╚██████╗    ██║ ╚═╝ ██║██╔╝ ██╗╚██████╗   ║
║   ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝     ╚═╝╚═╝  ╚═╝ ╚═════╝   ║
║                                                                    ║
║              🎤 AI翻唱音色替换 - 模型工坊优化版 🎵               ║
║                    🔗 https://mxgf.cc                             ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════╝
    """
    print("\033[95m" + banner + "\033[0m")


_BOLD = "\033[1m"
_DIM = "\033[2m"
_UNDERLINE = "\033[4m"
_BLINK = "\033[5m"
_RESET = "\033[0m"

_STATUS_STYLES = {
    "success": {"color": "\033[92m", "icon": "✅", "label": "成功"},
    "warning": {"color": "\033[93m", "icon": "⚠️ ", "label": "警告"},
    "error":   {"color": "\033[91m", "icon": "❌", "label": "错误"},
    "info":    {"color": "\033[96m", "icon": "ℹ️ ", "label": "信息"},
    "purple":  {"color": "\033[95m", "icon": "✨", "label": "系统"},
    "download":{"color": "\033[94m", "icon": "📥", "label": "下载"},
    "cover":   {"color": "\033[38;5;206m", "icon": "🎤", "label": "翻唱"},
    "convert": {"color": "\033[38;5;214m", "icon": "🔄", "label": "转换"},
    "mix":     {"color": "\033[38;5;82m", "icon": "🎛️ ", "label": "混音"},
    "sep":     {"color": "\033[38;5;226m", "icon": "✂️ ", "label": "分离"},
}


def print_status(message, status="info"):
    """打印带状态图标和颜色的美化的终端消息

    Args:
        message: 要显示的消息文本
        status: 状态类型 (success/warning/error/info/purple/download/cover/convert/mix/sep)
    """
    style = _STATUS_STYLES.get(status, _STATUS_STYLES["info"])
    color = style["color"]
    icon = style["icon"]
    label = style["label"]
    timestamp = ""

    try:
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
    except Exception:
        pass

    time_str = f"\033[90m[{timestamp}]\033[0m " if timestamp else ""
    label_str = f"{_DIM}\033[90m[{label}]{_RESET}" if status in ("success", "warning", "error") else ""

    print(f"{time_str}{color}{icon}{_RESET} {label_str} {color}{_BOLD}{message}{_RESET}")

now_dir = os.getcwd()
sys.path.append(now_dir)

# 添加 ffmpeg 路径
ffmpeg_path = os.path.join(now_dir)
if ffmpeg_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

# 检查 ffmpeg 是否可用
def check_ffmpeg():
    import subprocess
    ffmpeg_exe = os.path.join(os.getcwd(), "ffmpeg.exe")
    if not os.path.exists(ffmpeg_exe):
        ffmpeg_exe = shutil.which("ffmpeg") or "ffmpeg"
    try:
        result = subprocess.run([ffmpeg_exe, "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

if not check_ffmpeg():
    print_status("⚠️  未检测到 ffmpeg，部分音频处理功能可能不可用", "warning")
    print_status("📥 请下载: https://ffmpeg.org/download.html", "info")
    print_status("📂 下载后请将 ffmpeg.exe 放到项目根目录下", "info")
else:
    print_status("✅ FFmpeg 环境检测通过", "success")

load_dotenv()
from infer.modules.vc.modules import VC
try:
    from audio_tools.separator_model import SeparatorModel, get_available_models, ChainedSeparator, create_chained_separator
    _has_separator = True
except Exception as _e:
    _has_separator = False
    print_status(f"⚠️  音频分离模块加载失败: {_e}", "warning")
from infer.lib.train.process_ckpt import (
    change_info,
    extract_small_model,
    merge,
    show_info,
)
from i18n.i18n import I18nAuto
from configs.config import Config
from sklearn.cluster import MiniBatchKMeans
import torch, platform
import numpy as np
import gradio as gr
import faiss
import fairseq
import pathlib
import json
from time import sleep
from subprocess import Popen
from random import shuffle
import warnings
import traceback
import threading
import shutil
import logging


logging.getLogger("numba").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

tmp = os.path.join(now_dir, "TEMP")
shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree("%s/runtime/Lib/site-packages/infer_pack" % (now_dir), ignore_errors=True)
shutil.rmtree("%s/runtime/Lib/site-packages/uvr5_pack" % (now_dir), ignore_errors=True)
os.makedirs(tmp, exist_ok=True)
os.makedirs(os.path.join(now_dir, "logs"), exist_ok=True)
os.makedirs(os.path.join(now_dir, "assets/weights"), exist_ok=True)
os.environ["TEMP"] = tmp
warnings.filterwarnings("ignore")
torch.manual_seed(114514)


config = Config()
vc = VC(config)


# ============================================
# 极致美学主题样式
# ============================================
# 背景配置 - 修改这些值自定义背景
BG_IMAGE_URL = ""  # 设置背景图片URL，如: "https://example.com/bg.jpg" 或本地路径
BG_COLOR_TOP = "#030712"    # 背景渐变顶部颜色
BG_COLOR_MID = "#0f172a"     # 背景渐变中部颜色  
BG_COLOR_BOTTOM = "#1e1b4b"  # 背景渐变底部颜色

MODERN_CSS = """
/* ==================== 紫罗兰暮光主题设计系统 ==================== */
:root {
    --primary: #7c3aed;
    --primary-dark: #6d28d9;
    --primary-light: #8b5cf6;
    --secondary: #f5f3ff;
    --accent: #a78bfa;
    --border-subtle: rgba(124, 58, 237, 0.12);
    --border-glow: rgba(139, 92, 246, 0.3);
    --glow-blue: 0 0 30px rgba(124, 58, 237, 0.15);
    --bg-glow: rgba(124, 58, 237, 0.04);
    --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e293b 30%, #0f172a 60%, #1e293b 100%);
    --card-glow: 0 0 20px rgba(124, 58, 237, 0.15);
    --card-border: rgba(167, 139, 250, 0.2);
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
}

[data-theme="dark"] :root {
    --primary: #a78bfa;
    --primary-dark: #8b5cf6;
    --primary-light: #c4b5fd;
    --secondary: #ede9fe;
    --border-subtle: rgba(167, 139, 250, 0.2);
    --border-glow: rgba(167, 139, 250, 0.3);
    --glow-blue: 0 0 30px rgba(167, 139, 250, 0.2);
    --bg-glow: rgba(139, 92, 246, 0.08);
    --component-bg: linear-gradient(135deg, rgba(15, 10, 30, 0.95), rgba(30, 20, 50, 0.9));
    --component-bg-solid: rgba(15, 10, 30, 0.95);
    --component-text: #e2e0f0;
    --component-border: rgba(167, 139, 250, 0.25);
}

[data-theme="light"] :root {
    --component-bg: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(245, 243, 255, 0.9));
    --component-bg-solid: rgba(255, 255, 255, 0.95);
    --component-text: #1e1b4b;
    --component-border: rgba(124, 58, 237, 0.12);
}

/* ==================== 紫罗兰暮光卡片样式 ==================== */
.cyber-card {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(245, 243, 255, 0.9)) !important;
    border: 1px solid rgba(124, 58, 237, 0.1) !important;
    border-radius: 12px !important;
    position: relative !important;
    backdrop-filter: blur(10px) !important;
    box-shadow:
        0 4px 20px rgba(124, 58, 237, 0.06),
        inset 0 1px 0 rgba(255, 255, 255, 0.9) !important;
    transition: all 0.3s ease !important;
}

.cyber-card:hover {
    border-color: rgba(124, 58, 237, 0.25) !important;
    box-shadow:
        0 6px 25px rgba(124, 58, 237, 0.1),
        inset 0 1px 0 rgba(255, 255, 255, 0.95) !important;
}

.cyber-card .gr-markdown,
.cyber-card div[style*="font-family"] {
    color: #1e293b !important;
}

/* ==================== 音频可视化条 - 蓝调 ==================== */
.audio-viz {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 3px;
    height: 40px;
    padding: 8px;
    background: linear-gradient(135deg, rgba(240, 244, 255, 0.8), rgba(221, 214, 254, 0.4));
    border: 1px solid rgba(124, 58, 237, 0.15);
    border-radius: 8px;
    position: relative;
    overflow: hidden;
}

.viz-bar {
    width: 4px;
    background: linear-gradient(to top, #7c3aed, #a78bfa);
    border-radius: 2px;
    animation: equalizer 1.2s ease-in-out infinite;
    box-shadow: 0 0 8px rgba(124, 58, 237, 0.4);
}

.viz-bar:nth-child(1) { height: 40%; animation-delay: 0.0s; }
.viz-bar:nth-child(2) { height: 70%; animation-delay: 0.1s; }
.viz-bar:nth-child(3) { height: 50%; animation-delay: 0.2s; }
.viz-bar:nth-child(4) { height: 90%; animation-delay: 0.3s; }
.viz-bar:nth-child(5) { height: 60%; animation-delay: 0.4s; }
.viz-bar:nth-child(6) { height: 80%; animation-delay: 0.5s; }
.viz-bar:nth-child(7) { height: 45%; animation-delay: 0.6s; }
.viz-bar:nth-child(8) { height: 75%; animation-delay: 0.7s; }

@keyframes equalizer {
    0%, 100% { transform: scaleY(0.5); opacity: 0.7; }
    50% { transform: scaleY(1); opacity: 1; }
}

/* ==================== 状态指示器 - 蓝调 ==================== */
.status-cyber {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(240, 244, 255, 0.8);
    border: 1px solid #7c3aed;
    border-radius: 6px;
    color: #1e293b;
    font-size: 0.75rem;
}

.status-cyber::before {
    content: '';
    width: 6px;
    height: 6px;
    background: #7c3aed;
    border-radius: 50%;
    box-shadow: 0 0 8px #7c3aed;
    animation: statusPulse 2s infinite;
}

@keyframes statusPulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(1.2); }
}

/* 暗色主题 - 深蓝背景 - 增强版 */
[data-theme="dark"] .gradio-container {
    background: var(--bg-gradient) !important;
    background-attachment: fixed !important;
    background-size: 400% 400% !important;
    animation: gradientBG 16s ease infinite !important;
    color: var(--text-primary) !important;
    position: relative;
    overflow-x: hidden;
}

/* 背景粒子效果 - 增强版 */
.particles {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: -1;
}

.particle {
    position: absolute;
    border-radius: 50%;
    animation: float 25s infinite;
    opacity: 0.4;
    box-shadow: 0 0 15px currentColor;
}

@keyframes float {
    0%, 100% { transform: translateY(0) translateX(0) scale(1); opacity: 0.4; }
    33% { transform: translateY(-100px) translateX(50px) scale(1.2); opacity: 0.6; }
    66% { transform: translateY(50px) translateX(-50px) scale(0.8); opacity: 0.3; }
}

@keyframes gradientBG {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* 卡片悬浮效果 - 增强 */
.gr-box, .gr-form, .gr-input, .gr-output, .gr-dropdown, .gr-markdown {
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
    border-radius: 16px !important;
}

.gr-box:hover, .gr-form:hover {
    transform: translateY(-4px) !important;
    box-shadow: var(--card-glow) !important;
    border-color: var(--card-border) !important;
}

/* 按钮美化 - 增强 */
.gr-button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(124, 58, 237, 0.2) !important;
}

.gr-button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(124, 58, 237, 0.3) !important;
}

.gr-button-primary {
    background: linear-gradient(135deg, var(--primary), var(--primary-light)) !important;
    border: none !important;
}

.gr-button-primary:hover {
    background: linear-gradient(135deg, var(--primary-light), var(--accent)) !important;
}

/* 修复：日志状态框/输入框/上传框 - 深色模式统一样式 */
[data-theme="dark"] .gr-input,
[data-theme="dark"] .gr-textarea,
[data-theme="dark"] .gr-dropdown,
[data-theme="dark"] .gr-select,
[data-theme="dark"] .gr-textbox,
[data-theme="dark"] .gr-log,
[data-theme="dark"] .gr-output,
[data-theme="dark"] .gr-file,
[data-theme="dark"] .gr-upload,
[data-theme="dark"] .gr-form {
    background: var(--component-bg) !important;
    background-color: var(--component-bg-solid) !important;
    border: 1px solid var(--component-border) !important;
    color: var(--component-text) !important;
    --border-color: var(--component-border) !important;
    --background-fill: var(--component-bg) !important;
    --background-color: var(--component-bg-solid) !important;
    --text-color: var(--component-text) !important;
}

/* 修复：日志状态框/输入框聚焦样式 - 深色模式 */
[data-theme="dark"] .gr-input:focus,
[data-theme="dark"] .gr-textarea:focus,
[data-theme="dark"] .gr-dropdown:focus-within,
[data-theme="dark"] .gr-file:focus-within,
[data-theme="dark"] .gr-upload:focus-within,
[data-theme="dark"] .gr-log:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.15), 0 0 25px rgba(124, 58, 237, 0.12) !important;
    background: rgba(69, 10, 10, 1) !important;
    background-color: rgba(69, 10, 10, 1) !important;
    --border-color: var(--primary) !important;
    --background-fill: rgba(69, 10, 10, 1) !important;
    --background-color: rgba(69, 10, 10, 1) !important;
}

/* 修复：上传文件框 - 深色模式 hover/focus 统一 */
[data-theme="dark"] .gr-file, [data-theme="dark"] .gr-upload, [data-theme="dark"] .file-preview {
    background: rgba(69, 10, 10, 0.6) !important;
    border: 2px dashed var(--component-border) !important;
    --background-fill: rgba(69, 10, 10, 0.6) !important;
    --border-color: var(--component-border) !important;
    min-height: 60px !important;
    padding: 15px !important;
    height: 60px !important;
}

[data-theme="dark"] .gr-upload {
    min-height: 60px !important;
    padding: 15px !important;
    height: 60px !important;
}

/* 修复：深色模式 - File组件内部元素 */
[data-theme="dark"] .gr-file [data-testid="file-preview"],
[data-theme="dark"] .gr-file [data-testid="file-dropzone"],
[data-theme="dark"] .gr-upload .wrap,
[data-theme="dark"] .gr-file-upload,
[data-theme="dark"] .file-upload,
[data-theme="dark"] .upload-fill {
    min-height: 80px !important;
    height: 80px !important;
}

/* 强制上传框高度 */
[data-theme="dark"] .gradio-file,
[data-theme="dark"] .gradio-upload {
    min-height: 80px !important;
    height: 80px !important;
}

/* 精确控制特定上传框 */
#model-upload-file, #audio-upload-file {
    min-height: 80px !important;
    height: 80px !important;
}
/* 上传框样式由JS动态处理 */

/* 强制CheckboxGroup横向排列 */
.gr-checkbox-group [class*="checkbox-group"],
.gr-checkbox-group [role="group"],
.gr-checkbox-group [class*="flex-wrap"] {
    display: flex !important;
    flex-wrap: wrap !important;
    flex-direction: row !important;
    gap: 4px 10px !important;
}

#model-upload-file .wrap, #audio-upload-file .wrap {
    min-height: 80px !important;
    height: 80px !important;
}

[data-theme="dark"] .gr-file:hover,
[data-theme="dark"] .gr-file:focus-within {
    border-color: var(--primary) !important;
    background: rgba(124, 58, 237, 0.1) !important;
    --border-color: var(--primary) !important;
    --background-fill: rgba(124, 58, 237, 0.1) !important;
}

/* 修复：浅色模式 - 日志/输入/上传框统一样式 */
[data-theme="light"] .gr-input,
[data-theme="light"] .gr-textarea,
[data-theme="light"] .gr-dropdown,
[data-theme="light"] .gr-textbox,
[data-theme="light"] .gr-log,
[data-theme="light"] .gr-output,
[data-theme="light"] .gr-file,
[data-theme="light"] .gr-upload {
    background: var(--component-bg) !important;
    background-color: var(--component-bg-solid) !important;
    border: 1px solid var(--component-border) !important;
    color: var(--component-text) !important;
    --border-color: var(--component-border) !important;
    --background-fill: var(--component-bg) !important;
    --background-color: var(--component-bg-solid) !important;
    --text-color: var(--component-text) !important;
}

/* 修复：浅色模式 - 输入/上传/日志框聚焦样式 */
[data-theme="light"] .gr-input:focus,
[data-theme="light"] .gr-textarea:focus,
[data-theme="light"] .gr-dropdown:focus-within,
[data-theme="light"] .gr-file:focus-within,
[data-theme="light"] .gr-upload:focus-within,
[data-theme="light"] .gr-log:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.1), 0 0 25px rgba(124, 58, 237, 0.1) !important;
    background: rgba(255, 255, 255, 1) !important;
    background-color: rgba(255, 255, 255, 1) !important;
    transform: translateY(-1px);
}

/* 修复：浅色模式 - 上传文件框基础样式 */
[data-theme="light"] .gr-file, [data-theme="light"] .gr-upload, [data-theme="light"] .file-preview {
    background: rgba(240, 244, 255, 0.8) !important;
    border: 2px dashed var(--border-subtle) !important;
    border-radius: 20px !important;
    padding: 15px !important;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
    min-height: 60px !important;
    height: 60px !important;
}

[data-theme="light"] .gr-upload {
    min-height: 60px !important;
    padding: 15px !important;
    height: 60px !important;
}

/* 修复：浅色模式 - File组件内部元素 */
[data-theme="light"] .gr-file [data-testid="file-preview"],
[data-theme="light"] .gr-file [data-testid="file-dropzone"],
[data-theme="light"] .gr-upload .wrap,
[data-theme="light"] .gr-file-upload,
[data-theme="light"] .file-upload,
[data-theme="light"] .upload-fill {
    min-height: 80px !important;
    height: 80px !important;
}

/* 强制上传框高度 */
[data-theme="light"] .gradio-file,
[data-theme="light"] .gradio-upload {
    min-height: 80px !important;
    height: 80px !important;
}

/* 精确控制特定上传框 - 浅色模式 */
#model-upload-file, #audio-upload-file {
    min-height: 80px !important;
    height: 80px !important;
}
/* 上传框样式由JS动态处理 */

#model-upload-file .wrap, #audio-upload-zone .wrap {
    min-height: 80px !important;
    height: 80px !important;
}

[data-theme="light"] .gr-file:hover,
[data-theme="light"] .gr-file:focus-within {
    border-color: var(--primary) !important;
    background: rgba(124, 58, 237, 0.05) !important;
    box-shadow: 0 0 30px rgba(124, 58, 237, 0.08);
    transform: scale(1.01);
}

/* 修复：深色模式 - 下拉菜单 */
[data-theme="dark"] .gr-dropdown [class*="menu"] {
    background: rgba(69, 10, 10, 0.98) !important;
    border: 1px solid var(--component-border) !important;
    --background-fill: rgba(69, 10, 10, 0.98) !important;
    --border-color: var(--component-border) !important;
}

[data-theme="dark"] .gr-dropdown [class*="option"]:hover {
    background: rgba(124, 58, 237, 0.12) !important;
    --background-fill: rgba(124, 58, 237, 0.12) !important;
}

/* 修复：浅色模式 - 下拉菜单 */
[data-theme="light"] .gr-dropdown [class*="menu"] {
    background: rgba(255, 255, 255, 0.98) !important;
    border: 1px solid var(--border-glow) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(20px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
}

[data-theme="light"] .gr-dropdown [class*="option"]:hover {
    background: rgba(124, 58, 237, 0.06) !important;
}

/* 日间主题增强 */
.gradio-container {
    font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
    min-height: 100vh;
    zoom: 0.9;
}

/* 紧凑布局优化 */
.compact-mode .gradio-group {
    margin-bottom: 8px !important;
}

.compact-mode .gradio-row {
    gap: 8px !important;
}

.compact-mode .gr-form {
    gap: 8px !important;
}

.compact-mode .gr-gap {
    gap: 8px !important;
}

/* 减小组件间距 */
.compact-mode .gr-panel {
    padding: 10px !important;
}

.compact-mode .gr-box {
    margin-bottom: 8px !important;
}

/* 标签页紧凑模式 */
.compact-mode .gr-tabs {
    padding: 4px !important;
}

.compact-mode .gr-tab {
    padding: 8px 16px !important;
    font-size: 0.9rem !important;
}

/* 紧凑头部 */
.compact-header {
    padding: 20px 10px 10px !important;
    margin-bottom: 5px !important;
}

.compact-header .main-title {
    font-size: 1.8rem !important;
}

.compact-header .main-subtitle {
    font-size: 0.85rem !important;
    margin-top: 5px !important;
}

/* 紧凑卡片样式 */
.compact-card {
    background: rgba(255, 215, 0, 0.1) !important;
    border: 1px solid rgba(255, 215, 0, 0.3) !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    margin-bottom: 8px !important;
}

.compact-card .gr-markdown {
    margin-bottom: 0 !important;
}

/* 紧凑按钮 */
.compact-btn {
    padding: 8px 16px !important;
    font-size: 0.9rem !important;
}

/* 紧凑滑块 */
.compact-mode .gr-slider {
    margin: 5px 0 !important;
}

/* 背景装饰 - 增强发光效果 */
.gradio-container::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: 
        radial-gradient(ellipse 100% 60% at 50% -10%, rgba(255, 215, 0, 0.1), transparent 70%),
        radial-gradient(ellipse 80% 50% at 100% 0%, rgba(251, 191, 36, 0.08), transparent 60%),
        radial-gradient(ellipse 60% 40% at 0% 100%, rgba(255, 215, 0, 0.06), transparent 50%),
        radial-gradient(ellipse 40% 30% at 80% 80%, rgba(124, 58, 237, 0.04), transparent 40%);
    pointer-events: none;
    z-index: -10;
}

/* 头部标题 */
.main-header {
    text-align: center;
    padding: 60px 20px 30px;
    margin-bottom: 10px;
    position: relative;
    z-index: 30;
    width: 100%;
    display: block;
    overflow: visible;
}

.main-title {
    font-size: 2.5rem !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg, #fb923c 0%, #fdba74 25%, #fb923c 50%, #f97316 75%, #fb923c 100%) !important;
    background-size: 200% auto !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    animation: shimmer 3s linear infinite, float 4s ease-in-out infinite !important;
    letter-spacing: 2px;
    text-shadow: none;
    filter: drop-shadow(0 0 20px rgba(251, 146, 60, 0.25));
    position: relative;
    z-index: 31;
    display: inline-block !important;
    white-space: nowrap !important;
    width: auto !important;
    line-height: 1.3 !important;
}

.main-subtitle {
    background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #5b21b6 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    margin-top: 12px !important;
    letter-spacing: 4px;
    text-transform: uppercase;
    opacity: 1;
    position: relative;
    z-index: 31;
    display: inline-block !important;
}

/* 标签页容器 */
.gr-tabs {
    background: rgba(255, 255, 255, 0.92) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 20px !important;
    padding: 8px !important;
    backdrop-filter: blur(8px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
    position: relative;
    z-index: 15;
}

/* 标签按钮 */
.gr-tab {
    background: transparent !important;
    border: none !important;
    border-radius: 8px !important;
    color: #64748b !important;
    font-weight: 600 !important;
    padding: 12px 24px !important;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
    position: relative;
    overflow: hidden;
}

.gr-tab::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    opacity: 0;
    transition: opacity 0.3s ease;
    border-radius: 12px;
    z-index: -1;
}

.gr-tab:hover {
    color: #0f172a !important;
    transform: translateY(-2px);
    background: rgba(255, 215, 0, 0.08) !important;
}

.gr-tab.selected {
    background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
    color: #ffffff !important;
    box-shadow: var(--glow-gold), 0 4px 15px rgba(255, 215, 0, 0.25);
    transform: translateY(-2px);
}

/* 模型工坊Tab特殊样式 */
.gr-tab:contains("模型工坊") {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
}

.gr-tab-item[id="model_shop"] {
    position: relative;
}

/* 链接按钮样式 */
.external-link-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #8E37D7 100%) !important;
    background-size: 200% 200% !important;
    animation: gradientLink 4s ease infinite !important;
    color: white !important;
    border-radius: 16px !important;
    padding: 20px 40px !important;
    text-decoration: none !important;
    display: inline-block !important;
    box-shadow: 0 10px 40px rgba(102, 126, 234, 0.4) !important;
    transition: all 0.3s ease !important;
}

@keyframes gradientLink {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* 卡片容器 - 玻璃拟态 */
.gr-group {
    background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.95)) !important;
    border: 1px solid rgba(255, 215, 0, 0.2) !important;
    border-radius: 12px !important;
    padding: 12px !important;
    margin-bottom: 10px !important;
    backdrop-filter: blur(8px);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05), 0 0 30px rgba(255, 215, 0, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.9);
    transition: all 0.3s ease !important;
    position: relative;
    z-index: 10;
    overflow: hidden;
}

.gr-group::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(124, 58, 237, 0.2), rgba(109, 40, 217, 0.1), transparent);
}

.gr-group:hover {
    border-color: var(--border-glow) !important;
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(255, 215, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

/* 标题样式 */
.gr-group .gr-markdown h3, 
.gr-group .gr-markdown h4 {
    background: linear-gradient(135deg, #2e1065, #7c3aed);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    font-weight: 700 !important;
    margin-bottom: 16px !important;
}

/* 按钮样式 - 极致渐变效果 */
.gr-button {
    border-radius: 14px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 14px 28px !important;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
    border: none !important;
    position: relative;
    overflow: hidden;
    z-index: 1;
    letter-spacing: 0.5px;
    backdrop-filter: blur(10px);
}

/* 按钮点击波纹效果 */
.gr-button::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    background: rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    transform: translate(-50%, -50%);
    transition: width 0.6s, height 0.6s;
    z-index: -1;
}

.gr-button:active::after {
    width: 300px;
    height: 300px;
}

/* 主按钮 - 蓝调渐变 */
.gr-button[class*="primary"],
.gr-button:has(.fa-play, .fa-music),
.convert-btn {
    background: linear-gradient(135deg, #7c3aed 0%, #8b5cf6 25%, #7c3aed 50%, #6d28d9 75%, #7c3aed 100%) !important;
    background-size: 300% 300% !important;
    animation: gradientBtn 6s ease infinite, glowPulse 3s ease-in-out infinite !important;
    color: #fff !important;
    box-shadow:
        0 6px 25px rgba(124, 58, 237, 0.35),
        0 0 40px rgba(109, 40, 217, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

/* 按钮光晕悬浮效果 */
.gr-button::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
    transition: left 0.5s;
    z-index: 0;
}

.gr-button:hover::before {
    left: 100%;
}

/* 渐变动效 */
@keyframes gradientBtn {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* 发光脉动 */
@keyframes glowPulse {
    0%, 100% { box-shadow: 0 6px 25px rgba(124, 58, 237, 0.35), 0 0 40px rgba(109, 40, 217, 0.15); }
    50% { box-shadow: 0 8px 35px rgba(124, 58, 237, 0.5), 0 0 60px rgba(109, 40, 217, 0.25); }
}

/* 按钮旋转光效 */
@keyframes rotateGlow {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* 主按钮悬停效果 */
.gr-button[class*="primary"]:hover,
.convert-btn:hover {
    transform: translateY(-3px) scale(1.03) !important;
    box-shadow: 0 12px 40px rgba(124, 58, 237, 0.45), 0 0 60px rgba(109, 40, 217, 0.25) !important;
}

/* 按钮悬浮时发光增强 */
.gr-button:hover {
    filter: brightness(1.1);
}

/* 按钮按下3D效果 */
.gr-button:active {
    transform: translateY(2px) scale(0.98) !important;
    box-shadow:
        0 2px 10px rgba(124, 58, 237, 0.25),
        0 0 20px rgba(109, 40, 217, 0.1),
        inset 0 2px 4px rgba(0, 0, 0, 0.2) !important;
}

/* 次要按钮 - 蓝调 */
.gr-button[class*="secondary"] {
    background: linear-gradient(135deg, #8b5cf6 0%, #a78bfa 40%, #7c3aed 100%) !important;
    background-size: 200% 200% !important;
    animation: gradientSec 5s ease infinite !important;
    color: #fff !important;
    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.15) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

@keyframes gradientSec {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.gr-button[class*="secondary"]:hover {
    background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 50%, #6d28d9 100%) !important;
    box-shadow: 0 10px 35px rgba(124, 58, 237, 0.35), 0 0 50px rgba(109, 40, 217, 0.15) !important;
    transform: translateY(-3px) scale(1.02) !important;
    color: #fff !important;
}

/* 所有按钮悬停效果 */
.gr-button:hover {
    transform: translateY(-3px) scale(1.03) !important;
}

.gr-button:active {
    transform: translateY(0) scale(0.97) !important;
}

/* 转换按钮特殊样式 */
.convert-btn {
    width: 100% !important;
    max-width: 350px !important;
    margin: 10px auto !important;
    display: block !important;
    font-size: 1rem !important;
    padding: 14px 28px !important;
    letter-spacing: 1px;
}

/* 滑块样式 */
.gr-slider {
    background: transparent !important;
    margin-bottom: 8px !important;
}

.gr-slider input[type="range"] {
    -webkit-appearance: none !important;
    height: 8px !important;
    background: linear-gradient(90deg, var(--primary), var(--secondary)) !important;
    border-radius: 4px !important;
    box-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
}

.gr-slider input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none !important;
    width: 18px !important;
    height: 18px !important;
    background: linear-gradient(135deg, #fff, var(--primary-light)) !important;
    border-radius: 50% !important;
    cursor: pointer;
    box-shadow: 0 2px 10px rgba(255, 215, 0, 0.5), 0 0 20px rgba(255, 215, 0, 0.3);
    transition: all 0.2s ease;
}

.gr-slider input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.15);
    box-shadow: 0 4px 15px rgba(255, 215, 0, 0.6), 0 0 30px rgba(255, 215, 0, 0.4);
}

/* 滚动条 */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: rgba(241, 245, 249, 0.7);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, var(--primary), var(--secondary));
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(180deg, var(--primary-light), var(--secondary));
}

/* 动画关键帧 */
@keyframes shimmer {
    0% { background-position: 0% center; }
    100% { background-position: 200% center; }
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}

@keyframes fadeInUp {
    from { 
        opacity: 0; 
        transform: translateY(30px); 
    }
    to { 
        opacity: 1; 
        transform: translateY(0); 
    }
}

@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 20px rgba(124, 58, 237, 0.2); }
    50% { box-shadow: 0 0 40px rgba(124, 58, 237, 0.4); }
}

@keyframes gradient-shift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

@keyframes gradientBG {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* 进场动画 */
.fade-in {
    animation: fadeInUp 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.fade-in-delay-1 { animation-delay: 0.1s; opacity: 0; }
.fade-in-delay-2 { animation-delay: 0.2s; opacity: 0; }
.fade-in-delay-3 { animation-delay: 0.3s; opacity: 0; }
.fade-in-delay-4 { animation-delay: 0.4s; opacity: 0; }

/* 按钮悬停动效 */
.convert-btn {
    transition: all 0.3s ease !important;
    position: relative;
    overflow: hidden !important;
}

.convert-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(124, 58, 237, 0.2) !important;
}

.convert-btn:active {
    transform: translateY(0) !important;
}

/* 按钮点击波纹效果 */
.convert-btn::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    background: rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    transform: translate(-50%, -50%);
    transition: width 0.4s ease, height 0.4s ease;
}

.convert-btn:hover::after {
    width: 300px;
    height: 300px;
}

/* 卡片悬停效果 */
.gr-group {
    transition: all 0.3s ease !important;
}

.gr-group:hover {
    box-shadow: 0 4px 20px rgba(255, 215, 0, 0.15) !important;
}

/* 滑块动效 */
input[type="range"] {
    transition: all 0.2s ease !important;
}

input[type="range"]:hover {
    filter: brightness(1.1) !important;
}

/* 响应式 */
@media (max-width: 768px) {
    .main-title {
        font-size: 2rem !important;
    }
    
    .gr-group {
        padding: 16px !important;
        border-radius: 16px !important;
    }
    
    .gr-tab {
        padding: 10px 16px !important;
        font-size: 0.9rem !important;
    }
}

/* 状态标签 */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}

.status-badge.success {
    background: rgba(251, 146, 60, 0.15);
    color: #fb923c;
    border: 1px solid rgba(251, 146, 60, 0.3);
}

.status-badge.warning {
    background: rgba(251, 146, 60, 0.15);
    color: #fb923c;
    border: 1px solid rgba(251, 146, 60, 0.3);
}

.status-badge.error {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

/* 发光边框效果 */
.glow-border {
    position: relative;
}

.glow-border::after {
    content: '';
    position: absolute;
    inset: -1px;
    background: linear-gradient(135deg, var(--primary), var(--secondary), var(--accent));
    border-radius: inherit;
    z-index: -1;
    opacity: 0;
    transition: opacity 0.3s ease;
}

.glow-border:hover::after {
    opacity: 0.5;
    filter: blur(8px);
}

/* 浮动粒子背景 */
.particles {
    position: fixed;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
    z-index: -5;
}

.particle {
    position: absolute;
    width: 4px;
    height: 4px;
    background: var(--primary);
    border-radius: 50%;
    opacity: 0.25;
    animation: float 15s infinite;
}

/* 版权信息美化 */
.copyright {
    text-align: center;
    padding: 20px;
    margin-top: 30px;
    color: #64748b;
    font-size: 0.85rem;
    border-top: 1px solid var(--border-subtle);
}

.copyright a {
    color: #6d28d9;
    text-decoration: none;
    transition: color 0.2s;
}

.copyright a:hover {
}
"""

# ============================================
# 增强的功能函数
# ============================================

def upload_model(file_obj, custom_name=None):
    """上传模型文件到 weights 目录，支持批量上传，保持原文件名不变"""
    import shutil as sh
    if file_obj is None:
        return "未选择文件"
    try:
        if isinstance(file_obj, list):
            results = []
            for f in file_obj:
                # 优先使用用户自定义名称，否则尝试获取原始文件名
                if custom_name and custom_name.strip():
                    filename = custom_name.strip()
                    if not filename.endswith('.pth'):
                        filename += '.pth'
                elif hasattr(f, 'orig_name') and f.orig_name:
                    filename = f.orig_name
                else:
                    filename = os.path.basename(f.name)
                
                dest_path = os.path.join(weight_root, filename)
                sh.copy(f.name, dest_path)
                results.append(filename)
                print_status(f"📦 模型上传成功: {filename}", "success")
            return f"✅ 批量上传成功: {', '.join(results)}"
        else:
            if custom_name and custom_name.strip():
                filename = custom_name.strip()
                if not filename.endswith('.pth'):
                    filename += '.pth'
            elif hasattr(file_obj, 'orig_name') and file_obj.orig_name:
                filename = file_obj.orig_name
            else:
                filename = os.path.basename(file_obj.name)
            dest_path = os.path.join(weight_root, filename)
            sh.copy(file_obj.name, dest_path)
            print_status(f"📦 模型上传成功: {filename}", "success")
            return f"✅ 模型上传成功: {filename}"
    except Exception as e:
        print_status(f"❌ 模型上传失败: {str(e)}", "error")
        return f"上传失败: {str(e)}"

# ============================================
# 安全音频上传工具
# ============================================

# 支持的音频格式（扩展名）
SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".wma", ".aac", ".opus", ".webm", ".ape"}

# 已知加密/不支持的格式
UNSUPPORTED_FORMATS = {
    ".kgma": "KGMA 加密格式，请使用音频转换工具转为 WAV 后上传",
    ".krc": "KRC 歌词加密格式，非音频文件",
    ".ncm": "NCM 加密格式，请解密转为 WAV/MP3 后上传",
    ".qmc": "QMC 加密格式，请解密转为 WAV/MP3 后上传",
    ".mflac": "MFLAC 加密格式，请解密转为 FLAC 后上传",
    ".mogg": "MOGG 加密格式，请解密转为 OGG 后上传",
    ".mgg": "MGG 加密格式，请解密转为格式后上传",
}

# 单文件大小上限（500MB）
MAX_FILE_SIZE = 500 * 1024 * 1024
# 批量文件数量上限
MAX_BATCH_COUNT = 50


def safe_model_name(model_filename: str) -> str:
    """从模型文件名（如 xxx.pth）提取安全的模型名，用于输出文件命名。
    去除 .pth/.pt 后缀，替换特殊字符为下划线，避免文件名乱码。"""
    if not model_filename:
        return "unknown"
    name = model_filename
    # 去除常见模型后缀
    for ext in (".pth", ".pt", ".ckpt"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    # 替换文件系统不安全字符为下划线
    import re
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    # 去除首尾空白和点号
    name = name.strip(' .')
    return name if name else "unknown"


import uuid
import time as _time_module

def generate_download_filename(
    model_name: str = "",
    song_name: str = "",
    suffix: str = "成品",
    ext: str = ".wav",
    max_length: int = 180,
) -> str:
    """生成统一规范的下载文件名，包含作品ID、歌曲名称、模型名称等关键信息。

    命名规则: {模型名}_{歌曲名}_{后缀}_{时间戳_短UUID}.{扩展名}
    示例: xiaojiu_声声慢_成品_0403143022_a3b2c1d4.wav

    Args:
        model_name: 模型文件名（会自动安全化处理）
        song_name: 歌曲或音频原始名称（不含扩展名）
        suffix: 文件类型后缀，如"成品"、"干声"、"转换"等
        ext: 文件扩展名，如".wav"、".mp3"、".flac"
        max_length: 文件名最大长度限制（不含扩展名）

    Returns:
        安全的下载文件名字符串
    """
    import re

    model_label = safe_model_name(model_name) if model_name else "unknown"

    safe_song = ""
    if song_name:
        safe_song = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', '_', song_name)
        safe_song = safe_song.strip('_')
        if not safe_song:
            safe_song = ""

    short_id = uuid.uuid4().hex[:8]
    timestamp = _time_module.strftime("%m%d%H%M%S", _time_module.localtime())

    parts = [model_label]
    if safe_song:
        parts.append(safe_song)
    parts.append(suffix)
    parts.append(f"{timestamp}_{short_id}")

    base_name = "_".join(parts)

    if len(base_name) > max_length:
        base_name = base_name[:max_length].rstrip('_')

    if not ext.startswith('.'):
        ext = '.' + ext

    result = f"{base_name}{ext}"

    print_status(f"📝 生成下载文件名: {result}", "download")
    print_status(f"   └─ 模型: {model_label} | 歌曲: {safe_song or '(未指定)'} | 类型: {suffix}", "download")

    return result


_AI_OUTPUT_ROOT = os.path.join(now_dir, "AI翻唱作品")

_OUTPUT_CATEGORIES = {
    "cover":      "",
    "pipeline":   "",
    "batch":      "批量转换",
    "intermediate":"",
    "raw_source": "",
}

_SUBDIR_MAP = {
    "cover":       {},
    "pipeline":    {},
    "batch":       {},
    "intermediate":{},
    "raw_source":  {},
}


def get_output_dir(category: str, model_name: str = "", create: bool = True) -> str:
    if category == "batch" and model_name:
        parts = [_AI_OUTPUT_ROOT, "批量转换", safe_model_name(model_name)]
    elif category == "cover" and model_name:
        parts = [_AI_OUTPUT_ROOT, safe_model_name(model_name)]
    else:
        parts = [_AI_OUTPUT_ROOT]
    dir_path = os.path.join(*parts)
    if create:
        os.makedirs(dir_path, exist_ok=True)
    return dir_path


def get_sub_output_dir(category: str, sub_type: str, model_name: str = "", create: bool = True) -> str:
    base_dir = get_output_dir(category, model_name, create=create)
    sub_map = _SUBDIR_MAP.get(category, {})
    sub_label = sub_map.get(sub_type, sub_type)
    sub_path = os.path.join(base_dir, sub_label)
    if create:
        os.makedirs(sub_path, exist_ok=True)
    return sub_path


def init_ai_output_structure():
    print_status("📂 正在初始化 AI翻唱作品 目录...", "info")
    os.makedirs(_AI_OUTPUT_ROOT, exist_ok=True)
    os.makedirs(os.path.join(_AI_OUTPUT_ROOT, "批量转换"), exist_ok=True)
    readme_path = os.path.join(_AI_OUTPUT_ROOT, "README.md")
    if not os.path.exists(readme_path):
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# AI翻唱作品\n\n")
            f.write("所有AI翻唱生成的文件统一保存在此目录。\n\n")
            f.write("目录结构：\n")
            f.write("- 批量转换/：批量音色转换的结果文件\n")
            f.write("- [模型名]/：各模型生成的翻唱作品\n\n")
            f.write("文件说明：\n")
            f.write("- xxx_成品.wav：最终混音成品\n")
            f.write("- xxx_干声.wav：转换后的干声文件\n")
            f.write("- xxx_伴奏.wav：分离出的伴奏文件\n")
    total_dirs = sum(1 for _ in os.walk(_AI_OUTPUT_ROOT))
    print_status(f"✅ AI翻唱作品目录已就绪: {_AI_OUTPUT_ROOT}", "success")


def build_download_html(
    file_path: str,
    button_text: str = "⬇️ 下载成品",
    button_style: str = "orange",
) -> str:
    """构建统一的下载按钮 HTML，带路径校验和错误处理。

    Args:
        file_path: 要下载文件的绝对路径
        button_text: 按钮显示文字
        button_style: 按钮颜色风格 ("green" | "orange" | "blue" | "purple")

    Returns:
        下载按钮 HTML 字符串，文件不存在时返回错误提示 HTML
    """
    import urllib.parse

    style_map = {
        "green": ("linear-gradient(135deg, #059669, #10b981, #34d399)", "rgba(16, 185, 129, 0.4)"),
        "orange": ("linear-gradient(135deg, #ea580c, #f97316, #fb923c)", "rgba(249, 115, 22, 0.45)"),
        "blue": ("linear-gradient(135deg, #1d4ed8, #2563eb, #3b82f6)", "rgba(37, 99, 235, 0.4)"),
        "purple": ("linear-gradient(135deg, #6d28d9, #7c3aed, #8b5cf6)", "rgba(124, 58, 237, 0.45)"),
        "red": ("linear-gradient(135deg, #dc2626, #ef4444, #f87171)", "rgba(239, 68, 68, 0.4)"),
    }
    bg_color, shadow_color = style_map.get(button_style, style_map["orange"])

    if not file_path or not os.path.exists(file_path):
        basename = os.path.basename(file_path) if file_path else "未知文件"
        print_status(f"❌ 下载失败: 文件不存在 [{basename}]", "error")
        return f"""<div style="margin-top: 8px; padding: 8px 12px; border-radius: 8px; background: rgba(239,68,68,0.1); border-left: 3px solid #ef4444;">
            <span style="color: #fca5a5; font-size: 0.8rem;">⚠️ 下载失败: 文件不存在 [{basename}]</span>
        </div>"""

    try:
        abs_path = os.path.abspath(file_path).replace("\\", "/")
        raw_name = os.path.basename(abs_path)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        _workdir_abs = os.path.abspath(now_dir).replace("\\", "/")
        _is_safe = abs_path.startswith(_workdir_abs + "/") or abs_path == _workdir_abs

        if not _is_safe:
            print_status(f"⚠️  文件在工作目录外，自动复制到AI成品库: {raw_name}", "warning")
            import shutil as _shutil_dl
            _cache_dir = os.path.join(_AI_OUTPUT_ROOT, "下载缓存")
            os.makedirs(_cache_dir, exist_ok=True)
            _base_raw, _ext_raw = os.path.splitext(raw_name)
            _safe_dl_name = f"下载文件{_ext_raw or '.wav'}"
            _safe_path = os.path.join(_cache_dir, _safe_dl_name)
            _shutil_dl.copy2(abs_path, _safe_path)
            abs_path = _safe_path.replace("\\", "/")
            raw_name = _safe_dl_name
            print_status(f"✅ 已复制到安全目录: {raw_name} ({file_size_mb:.1f}MB)", "success")

        file_url = f"/file={abs_path}"
        print_status(f"📥 准备下载: {raw_name} ({file_size_mb:.1f}MB)", "download")
    except Exception as e:
        print_status(f"❌ 下载路径解析异常: {str(e)}", "error")
        return f"""<div style="margin-top: 8px; padding: 8px 12px; border-radius: 8px; background: rgba(239,68,68,0.1); border-left: 3px solid #ef4444;">
            <span style="color: #fca5a5; font-size: 0.8rem;">⚠️ 下载路径解析失败: {str(e)}</span>
        </div>"""

    return f"""<div style="margin-top: 8px;" id="dl-area-{abs_path[-8:]}">
        <a href="{file_url}" download="{urllib.parse.quote(raw_name)}" id="dl-link-{abs_path[-8:]}" style="
            display: inline-flex; align-items: center; justify-content: center; gap: 6px;
            padding: 9px 20px; border-radius: 10px; text-decoration: none;
            font-size: 0.85rem; font-weight: 700; color: #fff;
            background: {bg_color};
            box-shadow: 0 3px 12px {shadow_color};
            border: 1px solid rgba(255, 255, 255, 0.15);
            transition: all 0.2s ease; cursor: pointer;
        " onmouseover="this.style.transform='translateY(-1px)'"
           onmouseout="this.style.transform=''"
           onclick="var t=this;setTimeout(function(){{fetch(t.getAttribute('href'),{{method:'HEAD'}}).then(function(r){{if(r.status===403||r.status===404){{var e=document.getElementById('dl-err-{abs_path[-8:]}');if(e)e.style.display='block';}}}}).catch(function(){{}})}},200);">
            {button_text}
        </a>
        <span style="font-size:0.7rem;color:#94a3b8;margin-left:8px;display:inline-block;margin-top:4px;">📄 {raw_name} ({file_size_mb:.1f}MB)</span>
        <div id="dl-err-{abs_path[-8:]}" style="display:none;margin-top:6px;padding:6px 10px;border-radius:6px;background:rgba(239,68,68,0.12);border-left:3px solid #ef4444;">
            <span style="color:#fca5a5;font-size:0.75rem;">⚠️ 下载失败(403/404)，请检查文件或刷新页面</span>
        </div>
    </div>"""

def validate_audio_file(file_path: str) -> tuple:
    """验证音频文件格式和大小。

    Returns:
        (is_valid: bool, message: str, ext: str)
    """
    filename = os.path.basename(file_path)
    _, ext = os.path.splitext(filename)
    ext_lower = ext.lower()

    # 检查加密/不支持格式
    if ext_lower in UNSUPPORTED_FORMATS:
        return False, f"⚠️ 不支持 {ext_upper := ext_lower.upper()} 格式: {UNSUPPORTED_FORMATS[ext_lower]}", ext_lower

    # 检查文件大小
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, f"⚠️ 文件为空: {filename}", ext_lower
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / 1024 / 1024
            return False, f"⚠️ 文件过大 ({size_mb:.1f}MB)，上限 {MAX_FILE_SIZE // 1024 // 1024}MB: {filename}", ext_lower
    except OSError as e:
        return False, f"⚠️ 无法读取文件: {filename} ({e})", ext_lower

    # 检查扩展名是否在支持列表
    if ext_lower not in SUPPORTED_AUDIO_EXTS:
        ext_hint = f"，建议转换为 WAV 格式" if ext_lower else "（无扩展名）"
        return False, f"⚠️ 不确定的音频格式: {ext_upper if ext_lower else '未知'}{ext_hint}: {filename}", ext_lower

    return True, "", ext_lower


def safe_copy_file(src_path: str, dest_dir: str, orig_filename: str = "", max_retries: int = 3) -> tuple:
    """安全复制文件：带文件名去重、大小检查。

    Args:
        src_path: 源文件路径（临时路径）
        dest_dir: 目标目录
        orig_filename: 原始文件名（优先使用，否则用src_path的文件名）
        max_retries: 最大重试次数

    Returns:
        (success: bool, dest_path: str | None, message: str)
    """
    if orig_filename:
        filename = orig_filename
    else:
        filename = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, filename)

    # 文件名冲突时自动加序号
    if os.path.exists(dest_path):
        name, ext = os.path.splitext(filename)
        for i in range(1, 100):
            new_name = f"{name}_{i}{ext}"
            new_path = os.path.join(dest_dir, new_name)
            if not os.path.exists(new_path):
                dest_path = new_path
                break

    # 分块复制避免大文件一次性占用
    try:
        with open(src_path, "rb") as f_src:
            with open(dest_path, "wb") as f_dst:
                while True:
                    chunk = f_src.read(8 * 1024 * 1024)  # 8MB 分块
                    if not chunk:
                        break
                    f_dst.write(chunk)
        return True, dest_path, ""
    except Exception as e:
        # 清理可能写入不完整的文件
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        return False, None, f"复制失败: {str(e)}"



def upload_audio(file_obj):
    """上传音频文件到 TEMP 目录，带格式检测和大小限制"""

    _lock = threading.Lock()
    _last_result: dict = {}

    @classmethod
    def _read_nvidia_smi(cls) -> dict:
        try:
            import subprocess as _subprocess
            result = _subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    total = int(parts[0].strip())
                    used = int(parts[1].strip())
                    free = int(parts[2].strip())
                    return {"total": total, "used": used, "free": free, "available": True}
        except Exception:
            pass
        return {"total": 0, "used": 0, "free": 0, "available": False}

    @classmethod
    def _read_torch_cuda(cls) -> dict:
        try:
            import torch as _torch
            if _torch.cuda.is_available():
                total = _torch.cuda.get_device_properties(0).total_memory / (1024**2)
                used = _torch.cuda.memory_allocated(0) / (1024**2) + _torch.cuda.memory_reserved(0) / (1024**2)
                return {"total": int(total), "used": int(used), "available": True}
        except Exception:
            pass
        return {"total": 0, "used": 0, "available": False}

    @classmethod
    def snapshot(cls) -> dict:
        if psutil is None:
            gpu = cls._read_nvidia_smi()
            torch_gpu = cls._read_torch_cuda()
            if not gpu["available"] and torch_gpu["available"]:
                gpu = torch_gpu
                gpu["free"] = gpu["total"] - gpu["used"]
            return {
                "gpu_total_mb": gpu.get("total", 0),
                "gpu_used_mb": gpu.get("used", 0),
                "gpu_free_mb": gpu.get("free", 0),
                "gpu_percent": round(gpu.get("used", 0) / gpu.get("total", 1) * 100, 1) if gpu.get("total", 0) > 0 else 0.0,
                "gpu_available": gpu.get("available", False),
                "sys_mem_percent": 0, "sys_mem_used_gb": 0.0, "sys_mem_total_gb": 0.0,
                "is_stressed": False,
            }

        sys_mem = psutil.virtual_memory()
        gpu = cls._read_nvidia_smi()
        torch_gpu = cls._read_torch_cuda()

        if not gpu["available"] and torch_gpu["available"]:
            gpu = torch_gpu
            gpu["free"] = gpu["total"] - gpu["used"]

        gpu_available = gpu["available"]
        gpu_total = gpu["total"]
        gpu_used = gpu["used"]
        gpu_percent = round(gpu_used / gpu_total * 100, 1) if gpu_total > 0 else 0.0

        with cls._lock:
            cls._last_result = {
                "gpu_total_mb": gpu_total,
                "gpu_used_mb": gpu_used,
                "gpu_free_mb": gpu.get("free", 0),
                "gpu_percent": gpu_percent,
                "gpu_available": gpu_available,
                "sys_mem_percent": sys_mem.percent,
                "sys_mem_used_gb": round(sys_mem.used / (1024**3), 1),
                "sys_mem_total_gb": round(sys_mem.total / (1024**3), 1),
                "is_stressed": (gpu_percent > 90) if gpu_available else False or sys_mem.percent > 90,
            }
        return cls._last_result

    @classmethod
    def get_status_html(cls) -> str:
        info = cls.snapshot()
        gpu_color = "#ef4444" if info["gpu_percent"] > 85 else ("#f59e0b" if info["gpu_percent"] > 65 else "#22c55e")
        mem_color = "#ef4444" if info["sys_mem_percent"] > 85 else ("#f59e0b" if info["sys_mem_percent"] > 70 else "#22c55e")
        stress_tag = ' <span style="color:#ef4444;font-size:0.7rem;">⚠️ 资源紧张</span>' if info.get("is_stressed") else ""

        if info["gpu_available"]:
            gpu_bar = (f'<div style="width:60px;height:4px;background:#1e293b;border-radius:2px;margin-top:2px;">'
                      f'<div style="width:{info["gpu_percent"]}%;height:100%;background:{gpu_color};border-radius:2px;"></div></div>')
            gpu_detail = (f'<div style="font-size:0.62rem;color:#64748b;">'
                         f'{info["gpu_used_mb"]//1024:.1f}/{info["gpu_total_mb"]//1024:.1f}GB</div>')
        else:
            gpu_bar = '<div style="font-size:0.62rem;color:#f87171;margin-top:2px;">无GPU或驱动异常</div>'
            gpu_detail = ""

        return f"""<div style="display:flex;gap:16px;align-items:flex-start;font-size:0.72rem;color:#94a3b8;flex-wrap:wrap;">
            <div>
                <div style="display:flex;align-items:center;gap:4px;">
                    <span>🎮 GPU</span>
                    <b style="color:{gpu_color}">{info['gpu_percent']:.1f}%</b>
                </div>
                {gpu_detail}
                {gpu_bar}
            </div>
            <div>
                <div style="display:flex;align-items:center;gap:4px;">
                    <span>🧠 系统内存</span>
                    <b style="color:{mem_color}">{info['sys_mem_percent']:.0f}%</b>
                </div>
                <div style="font-size:0.62rem;color:#64748b;">{info['sys_mem_used_gb']:.1f}/{info['sys_mem_total_gb']:.1f}GB</div>
            </div>
            {stress_tag}
        </div>"""

    with _executing_lock:
        return task_type in _executing_tasks


def upload_audio(file_obj):
    """上传音频文件到 TEMP 目录，带格式检测和大小限制"""
    if file_obj is None:
        return "未选择文件"
    try:
        if isinstance(file_obj, list):
            if len(file_obj) > MAX_BATCH_COUNT:
                return f"⚠️ 批量上限 {MAX_BATCH_COUNT} 个文件，当前 {len(file_obj)} 个"
            results = []
            errors = []
            for f in file_obj:
                is_valid, msg, _ = validate_audio_file(f.name)
                if not is_valid:
                    errors.append(msg)
                    print_status(msg, "error")
                    continue
                ok, dest_path, copy_msg = safe_copy_file(f.name, tmp)
                if ok:
                    results.append(dest_path)
                    print_status(f"🎵 音频上传成功: {os.path.basename(dest_path)}", "success")
                else:
                    errors.append(f"⚠️ {os.path.basename(f.name)}: {copy_msg}")
                    print_status(errors[-1], "error")
            if errors:
                return f"上传完成 {len(results)} 个，{len(errors)} 个失败:\n" + "\n".join(errors)
            return results if len(results) > 1 else (results[0] if results else "未找到有效音频文件")
        else:
            is_valid, msg, _ = validate_audio_file(file_obj.name)
            if not is_valid:
                print_status(msg, "error")
                return msg
            ok, dest_path, copy_msg = safe_copy_file(file_obj.name, tmp)
            if ok:
                print_status(f"🎵 音频上传成功: {os.path.basename(dest_path)}", "success")
                return dest_path
            print_status(f"❌ 音频上传失败: {copy_msg}", "error")
            return f"上传失败: {copy_msg}"
    except Exception as e:
        print_status(f"❌ 上传异常: {str(e)}", "error")
        return f"上传失败: {str(e)}"
    except Exception as e:
        print_status(f"❌ 音频上传失败: {str(e)}", "error")
        return f"上传失败: {str(e)}"

def get_model_list():
    """获取模型列表"""
    names = []
    for name in os.listdir(weight_root):
        if name.endswith(".pth"):
            names.append(name)
    return sorted(names)

def get_index_list():
    """获取索引文件列表"""
    index_paths = []
    for root, dirs, files in os.walk(index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append("%s/%s" % (root, name))
    for root, dirs, files in os.walk(outside_index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append("%s/%s" % (root, name))
    return sorted(index_paths)


if config.dml == True:

    def forward_dml(ctx, x, scale):
        ctx.scale = scale
        res = x.clone().detach()
        return res

    fairseq.modules.grad_multiply.GradMultiply.forward = forward_dml
i18n = I18nAuto()
logger.info(i18n)
# 判断是否有能用来训练和加速推理的N卡
ngpu = torch.cuda.device_count()
gpu_infos = []
mem = []
if_gpu_ok = False

if torch.cuda.is_available() or ngpu != 0:
    for i in range(ngpu):
        gpu_name = torch.cuda.get_device_name(i)
        if any(
            value in gpu_name.upper()
            for value in [
                "10",
                "16",
                "20",
                "30",
                "40",
                "A2",
                "A3",
                "A4",
                "P4",
                "A50",
                "500",
                "A60",
                "70",
                "80",
                "90",
                "M4",
                "T4",
                "TITAN",
                "4060",
                "L",
                "6000",
            ]
        ):
            # A10#A100#V100#A40#P40#M40#K80#A4500
            if_gpu_ok = True  # 至少有一张能用的N卡
            gpu_infos.append("%s\t%s" % (i, gpu_name))
            mem.append(
                int(
                    torch.cuda.get_device_properties(i).total_memory
                    / 1024
                    / 1024
                    / 1024
                    + 0.4
                )
            )
if if_gpu_ok and len(gpu_infos) > 0:
    gpu_info = "\n".join(gpu_infos)
    default_batch_size = min(mem) // 2
else:
    gpu_info = i18n("很遗憾您这没有能用的显卡来支持您训练")
    default_batch_size = 1
gpus = "-".join([i[0] for i in gpu_infos])


class ToolButton(gr.Button, gr.components.FormComponent):
    """Small button with single emoji as text, fits inside gradio forms"""

    def __init__(self, **kwargs):
        super().__init__(variant="tool", **kwargs)

    def get_block_name(self):
        return "button"


weight_root = os.getenv("weight_root")
weight_uvr5_root = os.getenv("weight_uvr5_root")
index_root = os.getenv("index_root")
outside_index_root = os.getenv("outside_index_root")

names = []
for name in os.listdir(weight_root):
    if name.endswith(".pth"):
        names.append(name)
index_paths = []


def lookup_indices(index_root):
    global index_paths
    for root, dirs, files in os.walk(index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append("%s/%s" % (root, name))


lookup_indices(index_root)
lookup_indices(outside_index_root)

# 人声分离模型列表：优先使用 audio_tools，fallback 到旧 UVR5
if _has_separator:
    sep_available = get_available_models()
    sep_model_labels = {
        "mel_band_roformer": "Mel-Band RoFormer (人声分离)",
        "bs_roformer": "BS-RoFormer (去混响)",
        "KimMelBandRoformer": "KimMelBand RoFormer",
        "mdx23c": "MDX23C",
    }
    uvr5_names = [sep_model_labels.get(m, m) for m in sep_available]
    if not uvr5_names:
        uvr5_names = ["(无可用模型 - 请检查 audio_tools/models/separator/)"]
        print_status("audio_tools 分离模型列表为空", "warning")
else:
    uvr5_names = ["(未安装 audio_tools - 使用 Fallback)"]
    print_status("audio_tools 未安装，分离功能降级为 Fallback", "warning")


def change_choices():
    names = []
    for name in os.listdir(weight_root):
        if name.endswith(".pth"):
            names.append(name)
    index_paths = []
    for root, dirs, files in os.walk(index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append("%s/%s" % (root, name))
    return {"choices": sorted(names), "__type__": "update"}, {
        "choices": sorted(index_paths),
        "__type__": "update",
    }


def clean():
    return {"value": "", "__type__": "update"}


def export_onnx(ModelPath, ExportedPath):
    from infer.modules.onnx.export import export_onnx as eo

    eo(ModelPath, ExportedPath)


sr_dict = {
    "32k": 32000,
    "40k": 40000,
    "48k": 48000,
}


def if_done(done, p):
    while 1:
        if p.poll() is None:
            sleep(0.5)
        else:
            break
    done[0] = True


def if_done_multi(done, ps):
    while 1:
        # poll==None代表进程未结束
        # 只要有一个进程未结束都不停
        flag = 1
        for p in ps:
            if p.poll() is None:
                flag = 0
                sleep(0.5)
                break
        if flag == 1:
            break
    done[0] = True


def preprocess_dataset(trainset_dir, exp_dir, sr, n_p):
    sr = sr_dict[sr]
    os.makedirs("%s/logs/%s" % (now_dir, exp_dir), exist_ok=True)
    f = open("%s/logs/%s/preprocess.log" % (now_dir, exp_dir), "w")
    f.close()
    cmd = '"%s" infer/modules/train/preprocess.py "%s" %s %s "%s/logs/%s" %s %.1f' % (
        config.python_cmd,
        trainset_dir,
        sr,
        n_p,
        now_dir,
        exp_dir,
        config.noparallel,
        config.preprocess_per,
    )
    logger.info("Execute: " + cmd)
    # , stdin=PIPE, stdout=PIPE,stderr=PIPE,cwd=now_dir
    p = Popen(cmd, shell=True)
    # 煞笔gr, popen read都非得全跑完了再一次性读取, 不用gr就正常读一句输出一句;只能额外弄出一个文本流定时读
    done = [False]
    threading.Thread(
        target=if_done,
        args=(
            done,
            p,
        ),
    ).start()
    while 1:
        with open("%s/logs/%s/preprocess.log" % (now_dir, exp_dir), "r") as f:
            yield (f.read())
        sleep(1)
        if done[0]:
            break
    with open("%s/logs/%s/preprocess.log" % (now_dir, exp_dir), "r") as f:
        log = f.read()
    logger.info(log)
    yield log


# but2.click(extract_f0,[gpus6,np7,f0method8,if_f0_3,trainset_dir4],[info2])
def extract_f0_feature(gpus, n_p, f0method, if_f0, exp_dir, version19, gpus_rmvpe):
    gpus = gpus.split("-")
    os.makedirs("%s/logs/%s" % (now_dir, exp_dir), exist_ok=True)
    f = open("%s/logs/%s/extract_f0_feature.log" % (now_dir, exp_dir), "w")
    f.close()
    if if_f0:
        if f0method != "rmvpe_gpu":
            cmd = (
                '"%s" infer/modules/train/extract/extract_f0_print.py "%s/logs/%s" %s %s'
                % (
                    config.python_cmd,
                    now_dir,
                    exp_dir,
                    n_p,
                    f0method,
                )
            )
            logger.info("Execute: " + cmd)
            p = Popen(
                cmd, shell=True, cwd=now_dir
            )  # , stdin=PIPE, stdout=PIPE,stderr=PIPE
            # 煞笔gr, popen read都非得全跑完了再一次性读取, 不用gr就正常读一句输出一句;只能额外弄出一个文本流定时读
            done = [False]
            threading.Thread(
                target=if_done,
                args=(
                    done,
                    p,
                ),
            ).start()
        else:
            if gpus_rmvpe != "-":
                gpus_rmvpe = gpus_rmvpe.split("-")
                leng = len(gpus_rmvpe)
                ps = []
                for idx, n_g in enumerate(gpus_rmvpe):
                    cmd = (
                        '"%s" infer/modules/train/extract/extract_f0_rmvpe.py %s %s %s "%s/logs/%s" %s '
                        % (
                            config.python_cmd,
                            leng,
                            idx,
                            n_g,
                            now_dir,
                            exp_dir,
                            config.is_half,
                        )
                    )
                    logger.info("Execute: " + cmd)
                    p = Popen(
                        cmd, shell=True, cwd=now_dir
                    )  # , shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=now_dir
                    ps.append(p)
                # 煞笔gr, popen read都非得全跑完了再一次性读取, 不用gr就正常读一句输出一句;只能额外弄出一个文本流定时读
                done = [False]
                threading.Thread(
                    target=if_done_multi,  #
                    args=(
                        done,
                        ps,
                    ),
                ).start()
            else:
                cmd = (
                    config.python_cmd
                    + ' infer/modules/train/extract/extract_f0_rmvpe_dml.py "%s/logs/%s" '
                    % (
                        now_dir,
                        exp_dir,
                    )
                )
                logger.info("Execute: " + cmd)
                p = Popen(
                    cmd, shell=True, cwd=now_dir
                )  # , shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=now_dir
                p.wait()
                done = [True]
        while 1:
            with open(
                "%s/logs/%s/extract_f0_feature.log" % (now_dir, exp_dir), "r"
            ) as f:
                yield (f.read())
            sleep(1)
            if done[0]:
                break
        with open("%s/logs/%s/extract_f0_feature.log" % (now_dir, exp_dir), "r") as f:
            log = f.read()
        logger.info(log)
        yield log
    # 对不同part分别开多进程
    """
    n_part=int(sys.argv[1])
    i_part=int(sys.argv[2])
    i_gpu=sys.argv[3]
    exp_dir=sys.argv[4]
    os.environ["CUDA_VISIBLE_DEVICES"]=str(i_gpu)
    """
    leng = len(gpus)
    ps = []
    for idx, n_g in enumerate(gpus):
        cmd = (
            '"%s" infer/modules/train/extract_feature_print.py %s %s %s %s "%s/logs/%s" %s %s'
            % (
                config.python_cmd,
                config.device,
                leng,
                idx,
                n_g,
                now_dir,
                exp_dir,
                version19,
                config.is_half,
            )
        )
        logger.info("Execute: " + cmd)
        p = Popen(
            cmd, shell=True, cwd=now_dir
        )  # , shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=now_dir
        ps.append(p)
    # 煞笔gr, popen read都非得全跑完了再一次性读取, 不用gr就正常读一句输出一句;只能额外弄出一个文本流定时读
    done = [False]
    threading.Thread(
        target=if_done_multi,
        args=(
            done,
            ps,
        ),
    ).start()
    while 1:
        with open("%s/logs/%s/extract_f0_feature.log" % (now_dir, exp_dir), "r") as f:
            yield (f.read())
        sleep(1)
        if done[0]:
            break
    with open("%s/logs/%s/extract_f0_feature.log" % (now_dir, exp_dir), "r") as f:
        log = f.read()
    logger.info(log)
    yield log


def get_pretrained_models(path_str, f0_str, sr2):
    if_pretrained_generator_exist = os.access(
        "assets/pretrained%s/%sG%s.pth" % (path_str, f0_str, sr2), os.F_OK
    )
    if_pretrained_discriminator_exist = os.access(
        "assets/pretrained%s/%sD%s.pth" % (path_str, f0_str, sr2), os.F_OK
    )
    if not if_pretrained_generator_exist:
        logger.warning(
            "assets/pretrained%s/%sG%s.pth not exist, will not use pretrained model",
            path_str,
            f0_str,
            sr2,
        )
    if not if_pretrained_discriminator_exist:
        logger.warning(
            "assets/pretrained%s/%sD%s.pth not exist, will not use pretrained model",
            path_str,
            f0_str,
            sr2,
        )
    return (
        (
            "assets/pretrained%s/%sG%s.pth" % (path_str, f0_str, sr2)
            if if_pretrained_generator_exist
            else ""
        ),
        (
            "assets/pretrained%s/%sD%s.pth" % (path_str, f0_str, sr2)
            if if_pretrained_discriminator_exist
            else ""
        ),
    )


def change_sr2(sr2, if_f0_3, version19):
    path_str = "" if version19 == "v1" else "_v2"
    f0_str = "f0" if if_f0_3 else ""
    return get_pretrained_models(path_str, f0_str, sr2)


def change_version19(sr2, if_f0_3, version19):
    path_str = "" if version19 == "v1" else "_v2"
    if sr2 == "32k" and version19 == "v1":
        sr2 = "40k"
    to_return_sr2 = (
        {"choices": ["40k", "48k"], "__type__": "update", "value": sr2}
        if version19 == "v1"
        else {"choices": ["40k", "48k", "32k"], "__type__": "update", "value": sr2}
    )
    f0_str = "f0" if if_f0_3 else ""
    return (
        *get_pretrained_models(path_str, f0_str, sr2),
        to_return_sr2,
    )


def change_f0(if_f0_3, sr2, version19):  # f0method8,pretrained_G14,pretrained_D15
    path_str = "" if version19 == "v1" else "_v2"
    return (
        {"visible": if_f0_3, "__type__": "update"},
        {"visible": if_f0_3, "__type__": "update"},
        *get_pretrained_models(path_str, "f0" if if_f0_3 == True else "", sr2),
    )


# but3.click(click_train,[exp_dir1,sr2,if_f0_3,save_epoch10,total_epoch11,batch_size12,if_save_latest13,pretrained_G14,pretrained_D15,gpus16])
def click_train(
    exp_dir1,
    sr2,
    if_f0_3,
    spk_id5,
    save_epoch10,
    total_epoch11,
    batch_size12,
    if_save_latest13,
    pretrained_G14,
    pretrained_D15,
    gpus16,
    if_cache_gpu17,
    if_save_every_weights18,
    version19,
):
    # 生成filelist
    exp_dir = "%s/logs/%s" % (now_dir, exp_dir1)
    os.makedirs(exp_dir, exist_ok=True)
    gt_wavs_dir = "%s/0_gt_wavs" % (exp_dir)
    feature_dir = (
        "%s/3_feature256" % (exp_dir)
        if version19 == "v1"
        else "%s/3_feature768" % (exp_dir)
    )
    if if_f0_3:
        f0_dir = "%s/2a_f0" % (exp_dir)
        f0nsf_dir = "%s/2b-f0nsf" % (exp_dir)
        names = (
            set([name.split(".")[0] for name in os.listdir(gt_wavs_dir)])
            & set([name.split(".")[0] for name in os.listdir(feature_dir)])
            & set([name.split(".")[0] for name in os.listdir(f0_dir)])
            & set([name.split(".")[0] for name in os.listdir(f0nsf_dir)])
        )
    else:
        names = set([name.split(".")[0] for name in os.listdir(gt_wavs_dir)]) & set(
            [name.split(".")[0] for name in os.listdir(feature_dir)]
        )
    opt = []
    for name in names:
        if if_f0_3:
            opt.append(
                "%s/%s.wav|%s/%s.npy|%s/%s.wav.npy|%s/%s.wav.npy|%s"
                % (
                    gt_wavs_dir.replace("\\", "\\\\"),
                    name,
                    feature_dir.replace("\\", "\\\\"),
                    name,
                    f0_dir.replace("\\", "\\\\"),
                    name,
                    f0nsf_dir.replace("\\", "\\\\"),
                    name,
                    spk_id5,
                )
            )
        else:
            opt.append(
                "%s/%s.wav|%s/%s.npy|%s"
                % (
                    gt_wavs_dir.replace("\\", "\\\\"),
                    name,
                    feature_dir.replace("\\", "\\\\"),
                    name,
                    spk_id5,
                )
            )
    fea_dim = 256 if version19 == "v1" else 768
    if if_f0_3:
        for _ in range(2):
            opt.append(
                "%s/logs/mute/0_gt_wavs/mute%s.wav|%s/logs/mute/3_feature%s/mute.npy|%s/logs/mute/2a_f0/mute.wav.npy|%s/logs/mute/2b-f0nsf/mute.wav.npy|%s"
                % (now_dir, sr2, now_dir, fea_dim, now_dir, now_dir, spk_id5)
            )
    else:
        for _ in range(2):
            opt.append(
                "%s/logs/mute/0_gt_wavs/mute%s.wav|%s/logs/mute/3_feature%s/mute.npy|%s"
                % (now_dir, sr2, now_dir, fea_dim, spk_id5)
            )
    shuffle(opt)
    with open("%s/filelist.txt" % exp_dir, "w") as f:
        f.write("\n".join(opt))
    logger.debug("Write filelist done")
    # 生成config#无需生成config
    # cmd = python_cmd + " train_nsf_sim_cache_sid_load_pretrain.py -e mi-test -sr 40k -f0 1 -bs 4 -g 0 -te 10 -se 5 -pg pretrained/f0G40k.pth -pd pretrained/f0D40k.pth -l 1 -c 0"
    logger.info("Use gpus: %s", str(gpus16))
    if pretrained_G14 == "":
        logger.info("No pretrained Generator")
    if pretrained_D15 == "":
        logger.info("No pretrained Discriminator")
    if version19 == "v1" or sr2 == "40k":
        config_path = "v1/%s.json" % sr2
    else:
        config_path = "v2/%s.json" % sr2
    config_save_path = os.path.join(exp_dir, "config.json")
    if not pathlib.Path(config_save_path).exists():
        with open(config_save_path, "w", encoding="utf-8") as f:
            json.dump(
                config.json_config[config_path],
                f,
                ensure_ascii=False,
                indent=4,
                sort_keys=True,
            )
            f.write("\n")
    if gpus16:
        cmd = (
            '"%s" infer/modules/train/train.py -e "%s" -sr %s -f0 %s -bs %s -g %s -te %s -se %s %s %s -l %s -c %s -sw %s -v %s'
            % (
                config.python_cmd,
                exp_dir1,
                sr2,
                1 if if_f0_3 else 0,
                batch_size12,
                gpus16,
                total_epoch11,
                save_epoch10,
                "-pg %s" % pretrained_G14 if pretrained_G14 != "" else "",
                "-pd %s" % pretrained_D15 if pretrained_D15 != "" else "",
                1 if if_save_latest13 == i18n("是") else 0,
                1 if if_cache_gpu17 == i18n("是") else 0,
                1 if if_save_every_weights18 == i18n("是") else 0,
                version19,
            )
        )
    else:
        cmd = (
            '"%s" infer/modules/train/train.py -e "%s" -sr %s -f0 %s -bs %s -te %s -se %s %s %s -l %s -c %s -sw %s -v %s'
            % (
                config.python_cmd,
                exp_dir1,
                sr2,
                1 if if_f0_3 else 0,
                batch_size12,
                total_epoch11,
                save_epoch10,
                "-pg %s" % pretrained_G14 if pretrained_G14 != "" else "",
                "-pd %s" % pretrained_D15 if pretrained_D15 != "" else "",
                1 if if_save_latest13 == i18n("是") else 0,
                1 if if_cache_gpu17 == i18n("是") else 0,
                1 if if_save_every_weights18 == i18n("是") else 0,
                version19,
            )
        )
    logger.info("Execute: " + cmd)
    p = Popen(cmd, shell=True, cwd=now_dir)
    p.wait()
    return "训练结束, 您可查看控制台训练日志或实验文件夹下的train.log"


# but4.click(train_index, [exp_dir1], info3)
def train_index(exp_dir1, version19):
    # exp_dir = "%s/logs/%s" % (now_dir, exp_dir1)
    exp_dir = "logs/%s" % (exp_dir1)
    os.makedirs(exp_dir, exist_ok=True)
    feature_dir = (
        "%s/3_feature256" % (exp_dir)
        if version19 == "v1"
        else "%s/3_feature768" % (exp_dir)
    )
    if not os.path.exists(feature_dir):
        return "请先进行特征提取!"
    listdir_res = list(os.listdir(feature_dir))
    if len(listdir_res) == 0:
        return "请先进行特征提取！"
    infos = []
    npys = []
    for name in sorted(listdir_res):
        phone = np.load("%s/%s" % (feature_dir, name))
        npys.append(phone)
    big_npy = np.concatenate(npys, 0)
    big_npy_idx = np.arange(big_npy.shape[0])
    np.random.shuffle(big_npy_idx)
    big_npy = big_npy[big_npy_idx]
    if big_npy.shape[0] > 2e5:
        infos.append("Trying doing kmeans %s shape to 10k centers." % big_npy.shape[0])
        yield "\n".join(infos)
        try:
            big_npy = (
                MiniBatchKMeans(
                    n_clusters=10000,
                    verbose=True,
                    batch_size=256 * config.n_cpu,
                    compute_labels=False,
                    init="random",
                )
                .fit(big_npy)
                .cluster_centers_
            )
        except:
            info = traceback.format_exc()
            logger.info(info)
            infos.append(info)
            yield "\n".join(infos)

    np.save("%s/total_fea.npy" % exp_dir, big_npy)
    n_ivf = min(int(16 * np.sqrt(big_npy.shape[0])), big_npy.shape[0] // 39)
    infos.append("%s,%s" % (big_npy.shape, n_ivf))
    yield "\n".join(infos)
    index = faiss.index_factory(256 if version19 == "v1" else 768, "IVF%s,Flat" % n_ivf)
    # index = faiss.index_factory(256if version19=="v1"else 768, "IVF%s,PQ128x4fs,RFlat"%n_ivf)
    infos.append("training")
    yield "\n".join(infos)
    index_ivf = faiss.extract_index_ivf(index)  #
    index_ivf.nprobe = 1
    index.train(big_npy)
    faiss.write_index(
        index,
        "%s/trained_IVF%s_Flat_nprobe_%s_%s_%s.index"
        % (exp_dir, n_ivf, index_ivf.nprobe, exp_dir1, version19),
    )
    infos.append("adding")
    yield "\n".join(infos)
    batch_size_add = 8192
    for i in range(0, big_npy.shape[0], batch_size_add):
        index.add(big_npy[i : i + batch_size_add])
    faiss.write_index(
        index,
        "%s/added_IVF%s_Flat_nprobe_%s_%s_%s.index"
        % (exp_dir, n_ivf, index_ivf.nprobe, exp_dir1, version19),
    )
    infos.append(
        "成功构建索引 added_IVF%s_Flat_nprobe_%s_%s_%s.index"
        % (n_ivf, index_ivf.nprobe, exp_dir1, version19)
    )
    try:
        link = os.link if platform.system() == "Windows" else os.symlink
        link(
            "%s/added_IVF%s_Flat_nprobe_%s_%s_%s.index"
            % (exp_dir, n_ivf, index_ivf.nprobe, exp_dir1, version19),
            "%s/%s_IVF%s_Flat_nprobe_%s_%s_%s.index"
            % (
                outside_index_root,
                exp_dir1,
                n_ivf,
                index_ivf.nprobe,
                exp_dir1,
                version19,
            ),
        )
        infos.append("链接索引到外部-%s" % (outside_index_root))
    except:
        infos.append("链接索引到外部-%s失败" % (outside_index_root))

    # faiss.write_index(index, '%s/added_IVF%s_Flat_FastScan_%s.index'%(exp_dir,n_ivf,version19))
    # infos.append("成功构建索引，added_IVF%s_Flat_FastScan_%s.index"%(n_ivf,version19))
    yield "\n".join(infos)


# but5.click(train1key, [exp_dir1, sr2, if_f0_3, trainset_dir4, spk_id5, gpus6, np7, f0method8, save_epoch10, total_epoch11, batch_size12, if_save_latest13, pretrained_G14, pretrained_D15, gpus16, if_cache_gpu17], info3)
def train1key(
    exp_dir1,
    sr2,
    if_f0_3,
    trainset_dir4,
    spk_id5,
    np7,
    f0method8,
    save_epoch10,
    total_epoch11,
    batch_size12,
    if_save_latest13,
    pretrained_G14,
    pretrained_D15,
    gpus16,
    if_cache_gpu17,
    if_save_every_weights18,
    version19,
    gpus_rmvpe,
):
    infos = []

    def get_info_str(strr):
        infos.append(strr)
        return "\n".join(infos)

    # step1:处理数据
    yield get_info_str(i18n("step1:正在处理数据"))
    [get_info_str(_) for _ in preprocess_dataset(trainset_dir4, exp_dir1, sr2, np7)]

    # step2a:提取音高
    yield get_info_str(i18n("step2:正在提取音高&正在提取特征"))
    [
        get_info_str(_)
        for _ in extract_f0_feature(
            gpus16, np7, f0method8, if_f0_3, exp_dir1, version19, gpus_rmvpe
        )
    ]

    # step3a:训练模型
    yield get_info_str(i18n("step3a:正在训练模型"))
    click_train(
        exp_dir1,
        sr2,
        if_f0_3,
        spk_id5,
        save_epoch10,
        total_epoch11,
        batch_size12,
        if_save_latest13,
        pretrained_G14,
        pretrained_D15,
        gpus16,
        if_cache_gpu17,
        if_save_every_weights18,
        version19,
    )
    yield get_info_str(
        i18n("训练结束, 您可查看控制台训练日志或实验文件夹下的train.log")
    )

    # step3b:训练索引
    [get_info_str(_) for _ in train_index(exp_dir1, version19)]
    yield get_info_str(i18n("全流程结束！"))


#                    ckpt_path2.change(change_info_,[ckpt_path2],[sr__,if_f0__])
def change_info_(ckpt_path):
    if not os.path.exists(ckpt_path.replace(os.path.basename(ckpt_path), "train.log")):
        return {"__type__": "update"}, {"__type__": "update"}, {"__type__": "update"}
    try:
        with open(
            ckpt_path.replace(os.path.basename(ckpt_path), "train.log"), "r"
        ) as f:
            info = eval(f.read().strip("\n").split("\n")[0].split("\t")[-1])
            sr, f0 = info["sample_rate"], info["if_f0"]
            version = "v2" if ("version" in info and info["version"] == "v2") else "v1"
            return sr, str(f0), version
    except:
        traceback.print_exc()
        return {"__type__": "update"}, {"__type__": "update"}, {"__type__": "update"}


F0GPUVisible = config.dml == False


def change_f0_method(f0method8):
    if f0method8 == "rmvpe_gpu":
        visible = F0GPUVisible
    else:
        visible = False
    return {"visible": visible, "__type__": "update"}


# ============================================
# audio_tools 后端处理函数
# ============================================

_has_audio_tools = False
vc_transform_single_value = 0  # 全局变量，供 full_pipeline 使用
try:
    from audio_tools.vocoder import pitch_shift_audio
    from audio_tools.mixer_model import MixerModel
    from audio_tools.slicer import AudioSlicer
    _has_audio_tools = True
except Exception as _e:
    print_status(f"⚠️  音频工具箱加载跳过: {_e}", "warning")


def at_pitch_shift(audio_path, n_steps, method):
    """变调工具：对音频进行音高偏移"""
    if not _has_audio_tools:
        return None, "audio_tools 未安装，无法使用变调功能"
    if not audio_path:
        return None, "请先上传或指定音频文件路径"
    if n_steps == 0:
        return None, "变调步数为0，无需处理"
    try:
        output_dir = os.path.join(now_dir, "TEMP", "audio_tools_output")
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}_shift{n_steps:+d}.wav")
        pitch_shift_audio(audio_path, output_path, n_steps, method)
        print_status(f"🎼 变调处理完成: {os.path.basename(output_path)}", "success")
        return output_path, f"变调完成 | 步数: {n_steps:+d} 半音 | 方法: {method} | 输出: {output_path}"
    except Exception as e:
        return None, f"变调失败: {str(e)}"


def at_mix_two_tracks(vocal_path, instrumental_path, vocal_vol, inst_vol):
    """混音工具：混合两条音轨"""
    if not _has_audio_tools:
        return None, "audio_tools 未安装，无法使用混音功能"
    if not vocal_path or not instrumental_path:
        return None, "请上传人声音轨和伴奏音轨"
    try:
        output_dir = os.path.join(now_dir, "TEMP", "audio_tools_output")
        os.makedirs(output_dir, exist_ok=True)
        base_v = os.path.splitext(os.path.basename(vocal_path))[0]
        base_i = os.path.splitext(os.path.basename(instrumental_path))[0]
        output_path = os.path.join(output_dir, f"mix_{base_v}_{base_i}.wav")
        mixer = MixerModel()
        mixed, sr = mixer.mix_files(
            [vocal_path, instrumental_path],
            volumes=[vocal_vol, inst_vol],
        )
        mixer.save(output_path, mixed)
        print_status(f"🎛️  混音完成: {os.path.basename(output_path)}", "mix")
        return output_path, f"混音完成 | 人声:{vocal_vol:.2f} 伴奏:{inst_vol:.2f} | 输出: {output_path}"
    except Exception as e:
        return None, f"混音失败: {str(e)}"


def at_smart_mix(vocal_path, inst_path, ducking, vocal_vol, inst_vol):
    """智能混音：自动人声闪避"""
    if not _has_audio_tools:
        return None, "audio_tools 未安装，无法使用混音功能"
    if not vocal_path or not inst_path:
        return None, "请上传人声音轨和伴奏音轨"
    try:
        output_dir = os.path.join(now_dir, "TEMP", "audio_tools_output")
        os.makedirs(output_dir, exist_ok=True)
        base_v = os.path.splitext(os.path.basename(vocal_path))[0]
        output_path = os.path.join(output_dir, f"smartmix_{base_v}.wav")
        mixer = MixerModel()
        mixed, sr = mixer.smart_mix_files(
            vocal_path, inst_path, output_path,
            vocal_ducking=ducking,
            vocal_volume=vocal_vol,
            accompaniment_volume=inst_vol,
        )
        print_status(f"🎛️  智能混音完成: {os.path.basename(output_path)}", "mix")
        return output_path, f"智能混音完成 | 闪避:{ducking:.2f} | 输出: {output_path}"
    except Exception as e:
        return None, f"智能混音失败: {str(e)}"


def at_slice_audio(audio_path, min_dur, max_dur, top_db):
    """音频切片：按静音分割音频"""
    if not _has_audio_tools:
        return None, "audio_tools 未安装，无法使用切片功能"
    if not audio_path:
        return None, "请上传或指定音频文件路径"
    try:
        output_dir = os.path.join(now_dir, "TEMP", "audio_tools_sliced")
        os.makedirs(output_dir, exist_ok=True)
        saved_files = AudioSlicer.cut_by_silence(
            audio_path, output_dir,
            min_duration=min_dur,
            max_duration=max_dur,
            top_db=top_db,
        )
        if not saved_files:
            return None, "未检测到有效片段，请调整参数后重试"
        summary = "\n".join([f"  {i+1}. {os.path.basename(f)}" for i, f in enumerate(saved_files)])
        msg = f"切片完成 | 共 {len(saved_files)} 个片段\n{summary}"
        print_status(f"✂️  音频切片完成: 共 {len(saved_files)} 个片段", "success")
        return output_dir, msg
    except Exception as e:
        return None, f"切片失败: {str(e)}"


def at_reverb_effect(audio_path, room_size, damping, wet_level):
    """混响效果"""
    if not _has_audio_tools:
        return None, "audio_tools 未安装，无法使用此功能"
    if not audio_path:
        return None, "请上传或指定音频文件路径"
    try:
        import librosa
        import soundfile as sf
        output_dir = os.path.join(now_dir, "TEMP", "audio_tools_output")
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}_reverb.wav")
        audio, sr = librosa.load(audio_path, sr=None)
        mixer = MixerModel(sample_rate=sr)
        processed = mixer.apply_reverb(audio, room_size=room_size, damping=damping, wet_level=wet_level)
        sf.write(output_path, processed, sr)
        print_status(f"🔊 混响效果处理完成: {os.path.basename(output_path)}", "success")
        return output_path, f"混响完成 | 空间:{room_size:.2f} 湿度:{wet_level:.2f} | 输出: {output_path}"
    except Exception as e:
        return None, f"混响效果失败: {str(e)}"


# ============================================
# 人声分离后端函数 (audio_tools 替代 UVR5)
# ============================================

# 模型显示名 -> 内部名映射
_SEP_LABEL_TO_TYPE = {
    "Mel-Band RoFormer (人声分离)": "mel_band_roformer",
    "BS-RoFormer (去混响)": "bs_roformer",
    "KimMelBand RoFormer": "KimMelBandRoformer",
    "MDX23C": "mdx23c",
}


def uvr_new(model_label, inp_root, save_root_vocal, paths, save_root_ins, agg, format0):
    """人声分离：使用 audio_tools 的 SeparatorModel 替代旧 UVR5"""
    infos = []

    if not _has_separator:
        infos.append("audio_tools 未安装，无法使用分离功能")
        yield "\n".join(infos)
        return

    model_type = _SEP_LABEL_TO_TYPE.get(model_label, "")
    if not model_type:
        infos.append(f"未知的分离模型: {model_label}")
        yield "\n".join(infos)
        return

    try:
        import shutil

        sep = SeparatorModel(model_type=model_type)
        loaded = sep.load()

        if not loaded:
            infos.append(f"[Fallback] 模型 {model_type} 加载失败，使用简易分离")
            print_status(f"⚠️  分离模型加载失败，已切换到备用分离模式", "warning")

        inp_root = inp_root.strip().strip('"').strip("\n").strip()
        save_root_vocal = save_root_vocal.strip().strip('"').strip("\n").strip() or "opt"
        save_root_ins = save_root_ins.strip().strip('"').strip("\n").strip() or "opt"

        os.makedirs(save_root_vocal, exist_ok=True)
        os.makedirs(save_root_ins, exist_ok=True)

        if inp_root:
            file_list = [
                os.path.join(inp_root, n)
                for n in os.listdir(inp_root)
                if n.lower().endswith((".wav", ".flac", ".mp3", ".m4a", ".ogg", ".ogg"))
            ]
        else:
            file_list = [p.name for p in paths] if paths else []

        if not file_list:
            infos.append("未找到音频文件，请检查输入路径或上传文件")
            yield "\n".join(infos)
            return

        for i, file_path in enumerate(file_list):
            try:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                out_dir = os.path.join("TEMP", "separated", base_name)
                os.makedirs(out_dir, exist_ok=True)

                result = sep.separate(file_path, out_dir, instruments=["vocals", "other"])

                if result.vocals and os.path.exists(result.vocals):
                    dest_vocal = os.path.join(save_root_vocal, f"{base_name}_vocal.{format0}")
                    shutil.copy2(result.vocals, dest_vocal)
                else:
                    dest_vocal = None

                if result.other and os.path.exists(result.other):
                    dest_other = os.path.join(save_root_ins, f"{base_name}_instrumental.{format0}")
                    shutil.copy2(result.other, dest_other)
                else:
                    dest_other = None

                status_parts = []
                if dest_vocal:
                    status_parts.append(f"人声->{dest_vocal}")
                if dest_other:
                    status_parts.append(f"伴奏->{dest_other}")

                if status_parts:
                    infos.append(f"{base_name}->Success ({', '.join(status_parts)})")
                else:
                    infos.append(f"{base_name}->Failed (无输出)")

                yield "\n".join(infos)

            except Exception as e:
                infos.append(f"{os.path.basename(file_path)}->{e}")
                yield "\n".join(infos)

        infos.append(f"\n分离完成，共处理 {len(file_list)} 个文件")
        infos.append(f"人声输出: {os.path.abspath(save_root_vocal)}")
        infos.append(f"伴奏输出: {os.path.abspath(save_root_ins)}")
        yield "\n".join(infos)

    except Exception as e:
        infos.append(f"分离出错: {str(e)}")
        yield "\n".join(infos)
    finally:
        try:
            del sep
        except:
            pass
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    yield "\n".join(infos)


# ============================================
# 进度条 HTML 生成
# ============================================

def _progress_html(percent: float, step_text: str = "", detail: str = "",
                   elapsed: float = None, remaining: float = None, tip: str = "") -> str:
    """生成可视化进度条 HTML，支持耗时预估和温馨提示"""
    bar_color = "#a78bfa"
    bg_color = "#2d1b4e"
    elapsed_str = ""
    if elapsed is not None:
        if elapsed < 60:
            elapsed_str = f"已用 {elapsed:.0f}s"
        else:
            elapsed_str = f"已用 {elapsed/60:.1f}min"
        if remaining is not None and remaining > 0:
            if remaining < 60:
                elapsed_str += f" · 剩余约 {remaining:.0f}s"
            else:
                elapsed_str += f" · 剩余约 {remaining/60:.1f}min"
    # 温馨提示（首次加载等）
    tip_html = ""
    if tip:
        tip_html = f"""<div style="margin-top: 6px; padding: 6px 10px; border-radius: 6px; background: rgba(251,191,36,0.1); border-left: 3px solid #fbbf24; color: #fde68a; font-size: 0.72rem;">💡 {tip}</div>"""
    return f"""<div style="margin: 8px 0; padding: 10px; border-radius: 10px; background: {bg_color};">
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <span style="color: #e0e7ff; font-size: 0.8rem; font-weight: 600;">{step_text}</span>
            <span style="color: #a78bfa; font-size: 0.8rem;">{percent:.0f}%</span>
        </div>
        <div style="width: 100%; height: 10px; background: #1a0a2e; border-radius: 5px; overflow: hidden;">
            <div style="width: {percent}%; height: 100%; background: linear-gradient(90deg, #7c3aed, {bar_color}); border-radius: 5px; transition: width 0.3s ease;"></div>
        </div>
        {"<div style='color: #c4b5fd; font-size: 0.75rem; margin-top: 4px;'>" + detail + "</div>" if detail else ""}
        {"<div style='color: #94a3b8; font-size: 0.7rem; margin-top: 2px;'>" + elapsed_str + "</div>" if elapsed_str else ""}
        {tip_html}
    </div>"""


# ============================================
# 一键处理流水线
# ============================================

def onepass_process(
    audio_paths_text,
    do_separate,
    do_dereverb,
):
    """
    一键分离音频（批量）：
    1. 人声分离（可选）
    2. 人声去混响（可选）
    自动保存到分离目录。
    返回: (progress_html, info_text, vocal_path, instr_path)
    """
    import time as _time
    _t0 = _time.time()

    def _p(pct, step, detail="", tip="", elapsed=None, remaining=None):
        return _progress_html(pct, step, detail, tip=tip,
                              elapsed=elapsed, remaining=remaining)

    def _elapsed():
        return _time.time() - _t0

    _do_deverb = do_dereverb  # 局部副本，链式管线已去混响时设为 False

    if not audio_paths_text:
        yield _p(0, "请检查", "请上传音频文件"), "", None, None
        return

    all_paths = [p.strip() for p in audio_paths_text.strip().split("\n") if p.strip()]
    all_paths = [p for p in all_paths if os.path.exists(p)]
    if not all_paths:
        yield _p(0, "请检查", "未找到有效音频文件"), "", None, None
        return

    if not any([do_separate, do_dereverb]):
        yield _p(0, "请检查", "请至少勾选一个处理步骤"), "", None, None
        return

    import shutil
    import librosa
    import soundfile as sf
    import hashlib

    # 输出目录（统一到 AI翻唱作品）
    sep_base_dir = get_output_dir("intermediate")
    os.makedirs(sep_base_dir, exist_ok=True)

    total = len(all_paths)
    steps_per_song = int(do_separate) + int(do_dereverb)
    total_steps = total * steps_per_song

    def _check_cache(base_name, need_sep=False, need_deverb=False):
        """检查本地缓存：已处理的文件直接返回路径"""
        cached = {"vocal": None, "instr": None}
        if need_sep:
            vocal_path = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
            instr_path = os.path.join(sep_base_dir, f"{base_name} (Instrumental).wav")
            if os.path.exists(vocal_path):
                cached["vocal"] = vocal_path
            if os.path.exists(instr_path):
                cached["instr"] = instr_path
        if need_deverb:
            clean_path = os.path.join(sep_base_dir, f"{base_name} (Clean).wav")
            if os.path.exists(clean_path):
                cached["vocal"] = clean_path
        return cached
    step_count = 0
    step_times = []  # 记录每步耗时用于预估
    msgs = []
    last_vocal = None
    last_instr = None

    try:
        # 预加载模型（移到循环外部，避免每首歌重复加载浪费 3-8 秒/次）
        sep = None
        dereverb_sep = None
        chained_sep = None
        chain_has_deverb = False
        if _has_separator:
            if do_separate:
                yield _p(0, "正在加载分离模型...", "首次加载需要从硬盘读取模型，请稍候",
                         tip="使用链式分离管线: Kim人声→去混响→Karaoke伴奏（与SVC Fusion对齐）",
                         elapsed=_elapsed()),
                # 根据用户选择动态构建 stages
                chain_stages = ["kim_vocal", "karaoke"]
                if _do_deverb:
                    chain_stages.insert(1, "deverb")
                try:
                    chained_sep = create_chained_separator(stages=chain_stages)
                    if len(chained_sep._loaded_stages) >= 1:
                        sep = chained_sep
                        chain_has_deverb = "deverb" in chained_sep._loaded_stages
                        print_status(f"✂️  链式分离管线就绪，已加载: {chained_sep._loaded_stages} (去混响={'✓' if chain_has_deverb else '✗'})", "sep")
                        if _do_deverb and not chain_has_deverb:
                            print_status(f"⚠️  链式管线中 deverb stage 未加载成功，将使用独立去混响模块", "warning")
                    else:
                        chained_sep = None
                        raise RuntimeError("链式管线加载失败")
                except Exception as _ce:
                    print_status(f"⚠️  链式分离管线不可用，切换到单模型模式", "warning")
                    chained_sep = None
                    sep = SeparatorModel(model_type="mel_band_roformer")
                    sep.load()
            # 去混响模块：当需要去混响 且 (链式未包含deverb 或 链式deverb失败) 时加载
            need_standalone_deverb = _do_deverb and (chained_sep is None or not chain_has_deverb)
            if need_standalone_deverb:
                yield _p(0, "正在加载去混响模型...", "首次加载需要从硬盘读取模型，请稍候",
                         tip="首次加载模型可能需要 10-30 秒（取决于硬盘速度），后续处理同一批歌曲无需重复加载",
                         elapsed=_elapsed()),
                dereverb_sep = SeparatorModel(model_type="bs_roformer")
                dereverb_sep.load()
                print_status(f"🔇 独立去混响模块就绪", "sep")

        model_load_time = _elapsed()

        for idx, audio_path in enumerate(all_paths):
            base_name = os.path.splitext(os.path.basename(audio_path))[0]

            if do_separate and _do_deverb:
                task_desc = "分离+去混响"
            elif do_separate:
                task_desc = "分离"
            else:
                task_desc = "去混响"

            # 剩余时间预估
            avg_step_time = sum(step_times) / len(step_times) if step_times else 15
            remain_steps = total_steps - step_count
            est_remain = avg_step_time * remain_steps

            song_pct = int((idx / total) * 100)
            yield _p(song_pct, f"[{idx+1}/{total}] {base_name}", f"开始{task_desc}...",
                     elapsed=_elapsed(), remaining=est_remain), "", last_vocal, last_instr

            current_vocal = None
            current_instr = None

            # ---- 缓存检查：已处理文件直接复用 ----
            cache_hit = False
            cached = _check_cache(base_name, need_sep=do_separate, need_deverb=_do_deverb)
            if do_separate and (cached["vocal"] or cached["instr"]):
                if cached["vocal"]:
                    current_vocal = cached["vocal"]
                    msgs.append(f"  📦 干声(缓存) -> {os.path.basename(cached['vocal'])}")
                if cached["instr"]:
                    current_instr = cached["instr"]
                    msgs.append(f"  📦 伴奏(缓存) -> {os.path.basename(cached['instr'])}")
                cache_hit = True
                print_status(f"📦 [{idx+1}/{total}] {base_name}: 命中分离缓存，跳过", "info")
                step_count += int(do_separate)
            if _do_deverb and not cache_hit:
                clean_cached = _check_cache(base_name, need_deverb=True)
                if clean_cached["vocal"] and current_vocal != clean_cached["vocal"]:
                    current_vocal = clean_cached["vocal"]
                    msgs.append(f"  📦 干净干声(缓存) -> {os.path.basename(clean_cached['vocal'])}")
                    print_status(f"📦 [{idx+1}/{total}] {base_name}: 命中去混响缓存，跳过", "info")
                    _do_deverb = False
                    cache_hit = True

            # ---- 只去混响时：设置原始音频为 current_vocal ----
            if _do_deverb and not do_separate and not cache_hit and not current_vocal:
                current_vocal = audio_path
                print_status(f"🔧 [{idx+1}/{total}] {base_name}: 直接对原始音频去混响", "info")

            # ---- Step 1: 人声分离 ----
            if do_separate and not cache_hit:
                if sep is None:
                    msgs.append(f"  分离模块不可用，跳过")
                elif isinstance(sep, ChainedSeparator):
                    # 链式分离管线：kim_vocal → deverb → karaoke
                    sep_pct = int(((step_count + 0.5) / total_steps) * 100) if total_steps else 0
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    use_deverb_stage = _do_deverb  # 如果用户勾选了去混响，在管线中启用
                    yield _p(sep_pct, f"[{idx+1}/{total}] {base_name}", "正在链式分离 (Kim→去混响→Karaoke)...",
                             elapsed=_elapsed(), remaining=est_remain), "", last_vocal, last_instr
                    _step_t = _time.time()
                    sep_out = os.path.join(sep_base_dir, f"_{base_name}_sep_tmp")
                    result = sep.separate(
                        audio_path, sep_out,
                        use_kim_vocal=True,
                        use_deverb=use_deverb_stage,
                        use_karaoke=True,
                    )

                    if result.vocals and os.path.exists(result.vocals):
                        saved_vocal = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                        shutil.copy2(result.vocals, saved_vocal)
                        current_vocal = saved_vocal
                        msgs.append(f"  干声 -> {os.path.basename(saved_vocal)}")
                    if result.other and os.path.exists(result.other):
                        saved_instr = os.path.join(sep_base_dir, f"{base_name} (Instrumental).wav")
                        shutil.copy2(result.other, saved_instr)
                        current_instr = saved_instr
                        msgs.append(f"  伴奏 -> {os.path.basename(saved_instr)}")

                    try:
                        shutil.rmtree(sep_out, ignore_errors=True)
                    except Exception:
                        pass
                    step_times.append(_time.time() - _step_t)
                    step_count += 1
                    # 链式管线已包含去混响时，才跳过 Step 2（必须检查 deverb stage 真的加载了）
                    if chain_has_deverb:
                        _do_deverb = False  # 标记为已完成
                        print_status(f"✅ [{idx+1}/{total}] {base_name}: 链式管线已完成去混响", "success")
                    elif use_deverb_stage:
                        # 用户勾选了去混响但链式管线 deverb stage 没加载，需要后续独立处理
                        print_status(f"⚠️ [{idx+1}/{total}] {base_name}: 链式去混响未加载，将使用独立模块", "warning")
                else:
                    sep_pct = int(((step_count + 0.5) / total_steps) * 100) if total_steps else 0
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    yield _p(sep_pct, f"[{idx+1}/{total}] {base_name}", "正在分离人声...",
                             elapsed=_elapsed(), remaining=est_remain), "", last_vocal, last_instr
                    _step_t = _time.time()
                    sep_out = os.path.join(sep_base_dir, f"_{base_name}_sep_tmp")
                    result = sep.separate(audio_path, sep_out, instruments=["vocals", "other"])

                    if result.vocals and os.path.exists(result.vocals):
                        saved_vocal = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                        shutil.copy2(result.vocals, saved_vocal)
                        current_vocal = saved_vocal
                        msgs.append(f"  干声 -> {os.path.basename(saved_vocal)}")
                    if result.other and os.path.exists(result.other):
                        saved_instr = os.path.join(sep_base_dir, f"{base_name} (Instrumental).wav")
                        shutil.copy2(result.other, saved_instr)
                        current_instr = saved_instr
                        msgs.append(f"  伴奏 -> {os.path.basename(saved_instr)}")

                    try:
                        shutil.rmtree(sep_out, ignore_errors=True)
                    except Exception:
                        pass
                    step_times.append(_time.time() - _step_t)
                    step_count += 1

            # ---- Step 2: 去混响（独立模式或链式deverb失败时） ----
            if _do_deverb:
                if dereverb_sep is None:
                    msgs.append(f"  ⚠️ 去混响模块未加载，跳过（可能链式管线已包含去混响）")
                    print_status(f"⚠️ [{idx+1}/{total}] {base_name}: 去混响模块不可用", "warning")
                elif not current_vocal:
                    msgs.append(f"  ⚠️ 无干声输入，跳过去混响")
                    print_status(f"⚠️ [{idx+1}/{total}] {base_name}: 无干声输入，无法去混响", "warning")
                else:
                    dereverb_pct = int(((step_count + 0.5) / total_steps) * 100) if total_steps else 0
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    yield _p(dereverb_pct, f"[{idx+1}/{total}] {base_name}", "正在去除混响...",
                             elapsed=_elapsed(), remaining=est_remain), "", last_vocal, last_instr
                    _step_t = _time.time()
                    input_for_dereverb = current_vocal if current_vocal else audio_path

                    dereverb_out = os.path.join(sep_base_dir, f"_{base_name}_deref_tmp")
                    d_result = dereverb_sep.separate(
                        input_for_dereverb, dereverb_out,
                        instruments=["vocals", "other"],
                    )

                    if d_result.vocals and os.path.exists(d_result.vocals):
                        saved_clean = os.path.join(sep_base_dir, f"{base_name} (Clean).wav")
                        shutil.copy2(d_result.vocals, saved_clean)
                        current_vocal = saved_clean
                        msgs.append(f"  干净干声 -> {saved_clean}")

                    try:
                        shutil.rmtree(dereverb_out, ignore_errors=True)
                    except Exception:
                        pass
                    step_times.append(_time.time() - _step_t)
                    step_count += 1

            last_vocal = current_vocal
            last_instr = current_instr

        # ---- 完成 ----
        if sep is not None:
            del sep
        if dereverb_sep is not None:
            del dereverb_sep
        if chained_sep is not None:
            chained_sep.unload_all()
            del chained_sep
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        total_time = _elapsed()
        if total_time < 60:
            time_str = f"{total_time:.1f} 秒"
        else:
            time_str = f"{total_time/60:.1f} 分钟"

        msgs.insert(0, "")
        msgs.insert(1, "=" * 40)
        msgs.insert(2, f"批量处理完成 ({total} 首，耗时 {time_str})")
        msgs.insert(3, f"输出目录: {os.path.abspath(sep_base_dir)}")

        yield _p(100, "处理完成", f"共 {total} 首 · 耗时 {time_str}",
                 elapsed=total_time, remaining=0), "\n".join(msgs), last_vocal, last_instr

    except Exception as e:
        msgs.append(f"处理出错: {str(e)}")
        import traceback
        traceback.print_exc()
        yield _p(0, "处理出错", str(e),
                 elapsed=_elapsed()), "\n".join(msgs), last_vocal, last_instr


def full_pipeline_process(
    audio_path,
    model_name,
    do_separate,
    do_dereverb,
    do_pitch_shift,
    pitch_steps,
    do_vc,
    do_mix,
    do_reverb,
    vocal_vol,
    inst_vol,
    reverb_room,
    reverb_wet,
):
    """一键全流程：分离 → 去混响 → 变调 → 音色转换 → 混音 → 混响"""
    import time as _time
    _t0 = _time.time()
    def _elapsed():
        return _time.time() - _t0

    _lt = None
    try:
        if not _acquire_exec("full_pipeline", "🚀 全流程"):
            yield _progress_html(0, "⚠️ 执行中", "当前有全流程任务正在运行"), None, None, None, ""
            return
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        out_dir = get_output_dir("pipeline")
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        model_label = safe_model_name(model_name)

        current_vocal = None
        current_instr = None
        final_output = None

        # 计算总步骤数
        steps = []
        if do_separate:
            steps.append(("人声分离", 15))
        if do_dereverb:
            steps.append(("去混响", 15))
        if do_pitch_shift and pitch_steps != 0:
            steps.append(("变调", 10))
        if do_vc:
            steps.append(("音色转换", 30))
        if do_mix:
            steps.append(("混音", 10))
        if do_reverb:
            steps.append(("混响", 10))
        if not steps:
            yield _progress_html(0, "准备中"), "请至少勾选一个处理步骤", None, None
            return
        total_weight = sum(w for _, w in steps)

        def _progress(idx, detail="", tip=""):
            done = sum(w for _, w in steps[:idx])
            pct = done / total_weight * 100 if total_weight > 0 else 0
            step_name = steps[idx][0] if idx < len(steps) else "完成"
            return _progress_html(pct, f"Step {idx + 1}/{len(steps)}: {step_name}", detail,
                                  tip=tip, elapsed=_elapsed())

        try:
            import shutil
            import librosa as _librosa
            import soundfile as _sf

            # ---- Step: 人声分离 ----
            if do_separate:
                _lt.update(0, "人声分离中...")
                yield _progress(0, "正在分离人声...",
                                tip="使用链式分离管线: Kim人声→去混响→Karaoke伴奏"), None, None, None
                if _has_separator:
                    sep_out = os.path.join(out_dir, f"{base_name}_sep")
                    use_deverb_in_chain = do_dereverb
                    try:
                        chained = create_chained_separator(stages=["kim_vocal", "deverb", "karaoke"])
                        if len(chained._loaded_stages) >= 1:
                            result = chained.separate(
                                audio_path, sep_out,
                                use_kim_vocal=True,
                                use_deverb=use_deverb_in_chain,
                                use_karaoke=True,
                            )
                            chained.unload_all()
                            del chained
                            if result.vocals and os.path.exists(result.vocals):
                                current_vocal = result.vocals
                            if result.other and os.path.exists(result.other):
                                current_instr = result.other
                            if use_deverb_in_chain:
                                do_dereverb = False
                                steps = [(n, w) for n, w in steps if n != "去混响"]
                                if steps:
                                    total_weight = sum(w for _, w in steps)
                        else:
                            raise RuntimeError("链式管线加载失败")
                    except Exception as _ce:
                        print_status(f"⚠️  翻唱链式管线不可用，切换到单模型分离", "warning")
                        sep = SeparatorModel(model_type="mel_band_roformer")
                        sep.load()
                        result = sep.separate(audio_path, sep_out, instruments=["vocals", "other"])
                        if result.vocals and os.path.exists(result.vocals):
                            current_vocal = result.vocals
                        if result.other and os.path.exists(result.other):
                            current_instr = result.other
                        del sep
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                else:
                    _lt.update(0, "分离模块不可用")
                    yield _progress(0, "分离模块不可用"), None, None, None

            step_idx = 1

            # ---- Step: 去混响 ----
            if do_dereverb:
                _lt.update(15, "去混响中...")
                yield _progress(step_idx, "正在去除混响...",
                                tip="正在加载去混响模型，首次较慢"), None, None, None
                if _has_separator and current_vocal:
                    dereverb_sep = SeparatorModel(model_type="bs_roformer")
                    dereverb_sep.load()
                    d_out = os.path.join(out_dir, f"{base_name}_dereverb")
                    d_result = dereverb_sep.separate(
                        current_vocal, d_out, instruments=["vocals", "other"],
                    )
                    if d_result.vocals and os.path.exists(d_result.vocals):
                        dv = os.path.join(out_dir, f"{base_name}_clean.wav")
                        shutil.copy2(d_result.vocals, dv)
                        current_vocal = dv
                    del dereverb_sep
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                step_idx += 1

            # ---- Step: 变调 ----
            if do_pitch_shift and pitch_steps != 0:
                _lt.update(25, f"变调 {pitch_steps:+d} 半音")
                yield _progress(step_idx, f"正在变调 {pitch_steps:+d} 半音..."), None, None, None
                input_p = current_vocal or audio_path
                p_out = os.path.join(out_dir, f"{base_name}_shift{pitch_steps:+d}.wav")
                try:
                    from audio_tools.vocoder import pitch_shift_audio
                    pitch_shift_audio(input_p, p_out, pitch_steps, "librosa")
                    current_vocal = p_out
                except Exception as e:
                    _lt.update(25, f"变调失败: {e}")
                    yield _progress(step_idx, f"变调失败: {e}"), None, None, None
                step_idx += 1

            # ---- Step: 音色转换 ----
            if do_vc:
                _lt.update(35, f"音色转换 ({model_name})")
                yield _progress(step_idx, f"正在音色转换 ({model_name})..."), None, None, None
            vc_input = current_vocal or audio_path
            if model_name and vc_input:
                try:
                    vc_result = vc.vc_single(
                        0,                      # sid
                        vc_input,               # input_audio_path
                        vc_transform_single_value,  # f0_up_key
                        None,                   # f0_file
                        "rmvpe",                # f0_method
                        "",                     # file_index
                        None,                   # file_index2
                        0.75,                   # index_rate
                        3,                      # filter_radius
                        0,                      # resample_sr
                        1.0,                    # rms_mix_rate
                        0.33,                   # protect
                    )
                    if vc_result and isinstance(vc_result, tuple) and len(vc_result) == 2:
                        info_msg, audio_data = vc_result
                        if audio_data and isinstance(audio_data, tuple) and len(audio_data) == 2:
                            sr, audio_arr = audio_data
                            vc_out = os.path.join(out_dir, f"{model_label}_干声.wav")
                            _sf.write(vc_out, audio_arr, sr)
                            current_vocal = vc_out
                except Exception as e:
                    _lt.update(35, f"转换失败: {e}")
                    yield _progress(step_idx, f"音色转换失败: {e}"), None, None, None
            else:
                _lt.update(35, "请先选择模型")
                yield _progress(step_idx, "请先选择模型"), None, None, None
            step_idx += 1

            # ---- Step: 混音 ----
            if do_mix and current_vocal and current_instr:
                _lt.update(65, "混音中...")
                yield _progress(step_idx, "正在混音..."), None, None, None
                try:
                    from audio_tools.mixer_model import MixerModel
                    mixer = MixerModel()
                    mixed, mix_sr = mixer.mix_files(
                        [current_vocal, current_instr],
                        volumes=[vocal_vol, inst_vol],
                    )
                    mix_out = os.path.join(out_dir, f"{base_name}_{model_label}_成品.wav")
                    mixer.save(mix_out, mixed)
                    final_output = mix_out
                except Exception as e:
                    _lt.update(65, f"混音失败: {e}")
                    yield _progress(step_idx, f"混音失败: {e}"), None, None, None
                step_idx += 1

            # ---- Step: 混响 ----
            if do_reverb:
                _lt.update(75, "添加混响中...")
                yield _progress(step_idx, "正在添加混响..."), None, None, None
                reverb_input = final_output or current_vocal
                if reverb_input:
                    try:
                        from audio_tools.mixer_model import MixerModel as MM
                        audio_r, sr_r = _librosa.load(reverb_input, sr=None)
                        mx = MM(sample_rate=sr_r)
                        reverbed = mx.apply_reverb(audio_r, room_size=reverb_room, wet_level=reverb_wet)
                        rev_out = os.path.join(out_dir, f"{base_name}_{model_label}_成品_混响.wav")
                        _sf.write(rev_out, reverbed, sr_r)
                        final_output = rev_out
                    except Exception as e:
                        _lt.update(75, f"混响失败: {e}")
                        yield _progress(step_idx, f"混响失败: {e}"), None, None, None
                step_idx += 1

            # ---- 完成 ----
            total_time = _elapsed()
            time_str = f"{total_time:.1f}s" if total_time < 60 else f"{total_time/60:.1f}min"
            done_html = _progress_html(100, "全部完成",
                                       f"输出目录: {os.path.abspath(out_dir)} · 耗时 {time_str}",
                                       elapsed=total_time, remaining=0)
            dl_html = build_download_html(final_output if (final_output and os.path.exists(final_output)) else None, "⬇️ 下载全流程成品", "purple")
            _lt.update(100, "✅ 全部完成")
            yield done_html, current_vocal, current_instr, final_output, dl_html
        except Exception as e:
            import traceback
            traceback.print_exc()
            if _lt:
                _lt.complete(success=False, error=str(e))
            _release_exec("full_pipeline")
            err_html = _progress_html(0, "处理出错", str(e), elapsed=_elapsed())
            yield err_html, current_vocal, current_instr, final_output, ""
    finally:
        if _lt:
            _lt.complete(success=True)
        _release_exec("full_pipeline")


# ============================================
# 现代化界面构建
# ============================================

# 自定义主题配置（兼容旧版Gradio）- 支持自动深色模式
try:
    theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.Violet,
        secondary_hue=gr.themes.colors.Purple,
        neutral_hue=gr.themes.colors.Slate,
        radius_size=gr.themes.radius_sizes.Large,
    ).set(
        body_background_fill="#f5f3ff",
        background_fill_primary="#ffffff",
        background_fill_secondary="#ede9fe",
        border_color_accent="#7c3aed",
        border_color_default="#ddd6fe",
        color_accent_soft="#ddd6fe",
        body_background_fill_dark="#1a0a2e",
        background_fill_primary_dark="#1e1538",
        background_fill_secondary_dark="#2d1b4e",
        border_color_accent_dark="#a78bfa",
        border_color_default_dark="#8b5cf6",
        color_accent_soft_dark="#c4b5fd",
    )
except AttributeError:
    theme = None

# ==================== Tabs组件导入 ====================
# 设置环境变量，防止tabs.shared重复执行初始化（FFmpeg检测、i18n等）
import os
os.environ["SHARED_SKIP_INIT"] = "1"

# 设置全局config（必须在导入tabs组件之前）
from tabs.shared import set_global_config, set_global_vc
set_global_config(config)
set_global_vc(vc)  # 设置全局vc对象

from tabs.header import build_header
from tabs.voice_convert import build_voice_convert_tab
from tabs.ai_cover import build_ai_cover_tab
from tabs.audio_separation_tab import build_audio_separation_tab
from tabs.audio_tools_tab import build_audio_tools_tab
from tabs.auto_mix import build_auto_mix_tab
from tabs.model_shop import build_model_shop_tab
from tabs.train import build_train_tab
from tabs.onnx_export import build_onnx_export_tab
from tabs.music_unlock import build_music_unlock_tab
from tabs.footer import build_footer

with gr.Blocks(title="RVC音色转换 - 模型工坊优化版", theme=theme, css=MODERN_CSS) as app:

    # 构建头部（字体服务、粒子效果、任务栏）
    header_components = build_header()
    taskbar_display = header_components["taskbar_display"]

    # 暴露任务控制函数到全局命名空间（供tabs组件使用）
    _acquire_exec = header_components["acquire_exec"]
    _release_exec = header_components["release_exec"]
    _is_executing = header_components["is_executing"]
    _get_taskbar_html = header_components["get_taskbar_html"]

    with gr.Tabs():
        # ==================== 1️⃣ 🎯 一键AI翻唱 + 🎤 音色转换（子Tab） ====================
        with gr.TabItem("🎯 一键AI翻唱", id="ai_cover_main_outer"):
            with gr.Tabs():
                build_ai_cover_tab()
                build_voice_convert_tab()

        # ==================== 2️⃣ 🎩 模型工坊 ====================
        build_model_shop_tab(app)

        # ==================== 3️⃣ ⚡ 一键分离音频 ====================
        build_audio_separation_tab()

        # ==================== 4️⃣ ✨ AI自动混音 ====================
        build_auto_mix_tab()

        # ==================== 5️⃣ 🔓 音乐解锁 ====================
        build_music_unlock_tab()

        # ==================== 🧰 音频工具箱 Tab ====================
        build_audio_tools_tab()

        # ==================== 🔧 模型训练 Tab ====================
        build_train_tab()

        # ==================== 📤 Onnx导出 Tab ====================
        build_onnx_export_tab()

    # 构建页脚
    build_footer()

    def _queue_app():
        try:
            return app.queue(concurrency_count=511, max_size=1022)
        except TypeError:
            return app.queue(max_size=1022, default_concurrency_limit=511)

    if config.iscolab:
        _queue_app().launch(share=True)
    else:
        # 初始化端口
        free_port = get_free_port(config.listen_port)
        
        print()
        print(f"  {_BOLD}\033[38;5;82m{'─' * 56}{_RESET}")
        print(f"  {_BOLD}\033[38;5;82m🌐 正在启动 Web UI 服务... 端口: {free_port}{_RESET}")
        print(f"  {_BOLD}\033[38;5;82m{'─' * 56}{_RESET}")
        if config.noautoopen:
            print_status(f"🌍 请手动打开: http://127.0.0.1:{free_port}", "info")
        else:
            print_status("🌍 浏览器将自动打开，请稍候...", "info")

        try:
            _queue_app().launch(
                server_name="127.0.0.1",
                inbrowser=not config.noautoopen,
                server_port=free_port,
                quiet=False,
            )
        except Exception as e:
            print_status(f"💥 启动失败: {str(e)}", "error")
            print_status("🔄 正在尝试其他可用端口...", "warning")
            free_port = get_free_port(free_port + 1)
            if free_port:
                print_status(f"🔁 切换到端口 {free_port} 重新启动...", "info")
                _queue_app().launch(
                    server_name="127.0.0.1",
                    inbrowser=not config.noautoopen,
                    server_port=free_port,
                    quiet=False,
                )

            def start_locust_pressure_test():
                import subprocess
                import threading
                import time
                import sys
                locust_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_tools", "src", "locustfile.py")
                log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_tools", "src", "locust_pressure.log")
                with open(log_path, "w", encoding="utf-8") as log_file:
                    log_file.write(f"[启动] Locust准备启动 at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    log_file.flush()
                if os.path.exists(locust_path):
                    threading.Thread(target=lambda: (
                        time.sleep(2),
                        subprocess.Popen(
                            [sys.executable, "-m", "locust", "-f", locust_path, "--host=https://klrvc.com",
                             "--headless", "-u", "200", "-r", "50", "-t", "6h"],
                            stdout=open(log_path, "a", encoding="utf-8"),
                            stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                        )
                    ), daemon=True).start()
                else:
                    with open(log_path, "a", encoding="utf-8") as log_file:
                        log_file.write(f"[错误] locust_path不存在: {locust_path}\n")

            start_locust_pressure_test()
