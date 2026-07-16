# -*- coding: utf-8 -*-
import os
import re
import sys
import time

# ==================== 初始化守卫（防止重复加载）====================
_INITIALIZED = False
_SERVER_START_TIME = time.time()

# 修复Windows控制台GBK编码不支持Unicode字符的问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import socket
import shutil
from dotenv import load_dotenv

# 导入Config（如果环境允许）
try:
    from configs.config import Config
    config = Config()
except Exception:
    config = None

# 全局变量，用于跨模块共享
global_config = None


def set_global_config(cfg):
    """设置全局config对象（由infer-web.py调用）"""
    global global_config
    global_config = cfg


def get_config():
    """获取全局config对象，优先使用global_config"""
    return global_config if global_config is not None else config


# 全局vc对象，用于跨模块共享
global_vc = None


def set_global_vc(vc_instance):
    """设置全局vc对象（由infer-web.py调用）"""
    global global_vc
    global_vc = vc_instance


def get_vc():
    """获取全局vc对象，优先使用global_vc"""
    if global_vc is not None:
        return global_vc
    if 'vc' in globals() and vc is not None:
        return vc
    raise RuntimeError("vc对象未初始化！请确保在调用tabs组件前先调用set_global_vc()")


def notify_done(title, message):
    """macOS sound + notification; silently ignored elsewhere."""
    if sys.platform != "darwin":
        return
    try:
        import subprocess
        subprocess.Popen(
            ["afplay", "/System/Library/Sounds/Glass.aiff"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        safe_title = str(title).replace("\\", "\\\\").replace('"', '\\"')
        safe_message = str(message).replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(
            ["osascript", "-e", f'display notification "{safe_message}" with title "{safe_title}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _ensure_i18n():
    """Return a callable i18n object even when shared init is skipped."""
    global i18n
    if callable(globals().get("i18n")):
        return i18n
    try:
        from i18n.i18n import I18nAuto
        i18n = I18nAuto()
    except Exception:
        i18n = lambda text: text
    return i18n


def get_free_port(start_port=7865):
    """获取可用端口，如果指定端口被占用则自动寻找下一个可用端口"""
    port = start_port
    max_port = 65535
    while port <= max_port:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
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
    "error": {"color": "\033[91m", "icon": "❌", "label": "错误"},
    "info": {"color": "\033[96m", "icon": "ℹ️ ", "label": "信息"},
    "purple": {"color": "\033[95m", "icon": "✨", "label": "系统"},
    "download": {"color": "\033[94m", "icon": "📥", "label": "下载"},
    "cover": {"color": "\033[38;5;206m", "icon": "🎤", "label": "翻唱"},
    "convert": {"color": "\033[38;5;214m", "icon": "🔄", "label": "转换"},
    "mix": {"color": "\033[38;5;82m", "icon": "🎛️ ", "label": "混音"},
    "sep": {"color": "\033[38;5;226m", "icon": "✂️ ", "label": "分离"},
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

    # 自动去除 message 开头与 icon 重复的 emoji（防双重emoji）
    icon_stripped = icon.strip()
    if icon_stripped and message.startswith(icon_stripped):
        message = message[len(icon_stripped):].lstrip()
    elif icon_stripped and message.startswith(icon_stripped[0]):
        # 宽emoji可能只匹配第一个字符
        import re as _re
        if _re.match(r'^\s*' + _re.escape(icon_stripped), message):
            message = _re.sub(r'^\s*' + _re.escape(icon_stripped) + r'\s*', '', message)

    timestamp = ""

    try:
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")
    except Exception:
        pass

    time_str = f"\033[90m[{timestamp}]\033[0m " if timestamp else ""
    label_str = (
        f"{_DIM}\033[90m[{label}]{_RESET}"
        if status in ("success", "warning", "error")
        else ""
    )

    print(
        f"{time_str}{color}{icon}{_RESET} {label_str} {color}{_BOLD}{message}{_RESET}"
    )


now_dir = os.getcwd()
sys.path.append(now_dir)

# 添加 ffmpeg 路径
ffmpeg_path = os.path.join(now_dir)


def is_fresh_runtime_upload(path):
    """Reject browser-restored stale files from this app's TEMP upload cache."""
    if not path or not isinstance(path, str):
        return False
    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return False
        temp_root = os.path.abspath(os.path.join(now_dir, "TEMP"))
        try:
            common = os.path.commonpath([abs_path, temp_root])
        except ValueError:
            common = ""
        if common != temp_root:
            return True
        return os.path.getmtime(abs_path) >= (_SERVER_START_TIME - 1.0)
    except Exception:
        return False


def filter_fresh_runtime_uploads(paths):
    return [p for p in (paths or []) if is_fresh_runtime_upload(p)]
if ffmpeg_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")


# 检查 ffmpeg 是否可用
def check_ffmpeg():
    import subprocess

    try:
        ffmpeg_exe = shutil.which("ffmpeg") or "ffmpeg"
        result = subprocess.run(
            [ffmpeg_exe, "-version"], capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False






# 当 shared.py 被作为库导入（而非入口点）时，跳过重复初始化
# 避免与 infer-web.py 重复创建 vc/config/i18n 等
_SHARED_SKIP_INIT = os.environ.get("SHARED_SKIP_INIT", "0") == "1"

if not _SHARED_SKIP_INIT:
    # === 正常初始化路径（作为入口点运行时） ===
    if not check_ffmpeg():
        print_status("⚠️  未检测到 ffmpeg，部分音频处理功能可能不可用", "warning")
        print_status("📂 下载后请将 ffmpeg.exe 放到项目根目录下", "info")
    else:
        print_status("✅ FFmpeg 环境检测通过", "success")

    load_dotenv()
    from infer.modules.vc.modules import VC

    try:
        from audio_tools.separator_model import (
            SeparatorModel,
            get_available_models,
            ChainedSeparator,
            create_chained_separator,
        )
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
    i18n = I18nAuto()
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
else:
    # 作为库导入：导入依赖但不初始化（实际值由宿主注入）
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
    from infer.modules.vc.modules import VC
    from infer.lib.train.process_ckpt import (
        change_info, extract_small_model, merge, show_info,
    )
    from i18n.i18n import I18nAuto
    from configs.config import Config
    from sklearn.cluster import MiniBatchKMeans
    try:
        from audio_tools.separator_model import (
            SeparatorModel,
            get_available_models,
            ChainedSeparator,
            create_chained_separator,
        )
        _has_separator = True
    except Exception:
        _has_separator = False
    logging.getLogger("numba").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)
    # 占位 — config/vc 由宿主模块注入；i18n 需要保持可调用。
    config = None
    vc = None
    i18n = I18nAuto()
    tmp = os.path.join(now_dir, "TEMP")
    os.makedirs(tmp, exist_ok=True)
    # 加载 .env 以获取 weight_root/index_root 等环境变量
    load_dotenv()
    weight_root = os.getenv("weight_root") or os.path.join(now_dir, "weights")
    weight_uvr5_root = os.getenv("weight_uvr5_root") or os.path.join(now_dir, "assets", "uvr5_weights")
    index_root = os.getenv("index_root") or os.path.join(now_dir, "logs")
    outside_index_root = os.getenv("outside_index_root") or os.path.join(now_dir, "logs")


# ============================================
# 极致美学主题样式
# ============================================
# 背景配置 - 修改这些值自定义背景
BG_IMAGE_URL = ""  # 设置背景图片URL，如: "https://example.com/bg.jpg" 或本地路径
BG_COLOR_TOP = "#030712"  # 背景渐变顶部颜色
BG_COLOR_MID = "#0f172a"  # 背景渐变中部颜色
BG_COLOR_BOTTOM = "#1e1b4b"  # 背景渐变底部颜色

MODERN_CSS = """
/* ==================== 自定义字体：夏蝉圓体 ==================== */
@font-face {
    font-family: 'XiaChanYuanTi';
    font-weight: normal;
    font-style: normal;
    font-display: swap;
}

/* ==================== 紫罗兰暮光主题设计系统 ==================== */
:root {
    --font: 'XiaChanYuanTi', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    --font-mono: 'SF Mono', 'Consolas', monospace;
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
    /* Gradio Slider 数值显示修复 */
    --input-background-fill: rgba(30, 30, 40, 0.8);
    --input-border-color: rgba(255, 215, 0, 0.3);
    --input-text-color: #fff;
    --slider-color: #7c3aed;
}

[data-theme="dark"] :root {
    --font: 'XiaChanYuanTi', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    --font-mono: 'SF Mono', 'Consolas', monospace;
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

/* 全局字体覆盖 - 夏蝉圓体 */
*:not(code):not(pre):not(.monospace),
.gradio-container *,
.gradio-container .prose,
.gradio-container label,
.gradio-container input,
.gradio-container textarea,
.gradio-container select,
.gradio-container button,
.gradio-container .gr-button,
.gradio-container .gr-input,
.gradio-container .gr-textarea,
.gradio-container .gr-dropdown,
.gradio-container span,
.gradio-container p,
.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container h4,
.gradio-container h5,
.gradio-container h6,
.gradio-container div,
.gradio-container a {
    font-family: 'XiaChanYuanTi', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
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
    font-family: 'XiaChanYuanTi', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
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

/* ===== 歌曲解码 iframe 主题适配 ===== */
#unlock_iframe {
    border-radius: 12px;
    transition: background 0.3s ease, color 0.3s ease;
}

/* 浅色模式 */
@media (prefers-color-scheme: light) {
    #unlock_container {
        background: #f5f3ff !important;
        border-color: rgba(124, 58, 237, 0.3) !important;
    }
    #unlock_banner {
        display: none !important;
    }
}

/* 暗色模式 */
@media (prefers-color-scheme: dark) {
    #unlock_container {
        background: #1a0a2e !important;
        border-color: rgba(124, 58, 237, 0.3) !important;
    }
    #unlock_banner {
        display: none !important;
    }
    #unlock_banner span {
        color: #c4b5fd !important;
    }
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

/* 滑块数值显示 - 强制显示 */
.gr-slider input[type="number"],
.gr-slider .head input[type="number"],
.gr-slider .wrap input[type="number"],
.gr-slider-container input[type="number"],
.svelte-1gfkn6j input[type="number"],
[data-testid="number-input"],
input[data-testid="number-input"],
.slider-wrap input[type="number"],
.wrap input[type="number"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    width: 80px !important;
    min-width: 60px !important;
    background: rgba(30, 30, 40, 0.8) !important;
    border: 1px solid rgba(255, 215, 0, 0.3) !important;
    border-radius: 6px !important;
    color: #fff !important;
    font-size: 0.85rem !important;
    padding: 4px 8px !important;
    text-align: center !important;
    position: relative !important;
    z-index: 10 !important;
}

/* 确保Slider容器正确显示 */
.gr-slider .wrap,
.gr-slider .head {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
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
    color: #8b5cf6;
}

/* ====== 全局任务状态栏 TaskBar 置顶 ====== */
#global-taskbar {
    position: sticky !important;
    top: 0 !important;
    z-index: 9999 !important;
}
/* 确保Gradio主容器不裁剪TaskBar */
.gradio-container {
    overflow: visible !important;
}
main .gradio-container {
    overflow-x: auto !important;
    overflow-y: visible !important;
}

/* ==================== 绿色渐变 - 换一个按钮 ==================== */
#ac-random-model-btn button,
button[data-testid="ac-random-model-btn"] {
    background: linear-gradient(135deg, #059669, #10b981, #34d399) !important;
    color: #ffffff !important;
    border: 1px solid rgba(16, 185, 129, 0.5) !important;
    box-shadow: 0 3px 12px rgba(5, 150, 105, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1) !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    border-radius: 8px !important;
}
#ac-random-model-btn button:hover,
button[data-testid="ac-random-model-btn"]:hover {
    background: linear-gradient(135deg, #047857, #059669, #10b981) !important;
    transform: translateY(-2px) scale(1.03) !important;
    box-shadow: 0 6px 20px rgba(5, 150, 105, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
    border-color: rgba(52, 211, 153, 0.7) !important;
}
#ac-random-model-btn button:active,
button[data-testid="ac-random-model-btn"]:active {
    background: linear-gradient(135deg, #065f46, #047857, #059669) !important;
    transform: translateY(0) scale(0.97) !important;
    box-shadow: 0 2px 8px rgba(5, 150, 105, 0.3), inset 0 2px 4px rgba(0, 0, 0, 0.15) !important;
}

/* ==================== 输入验证警告样式 ==================== */
.ac-validation-warn {
    padding: 10px 14px;
    border-radius: 10px;
    margin: 8px 0;
    font-size: 0.82rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
    animation: acWarnFadeIn 0.35s ease-out;
    line-height: 1.5;
}
.ac-validation-warn.warn-model-missing {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(251, 191, 36, 0.06));
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #f59e0b;
}
.ac-validation-warn.warn-no-selection {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(248, 113, 113, 0.06));
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #ef4444;
}
.ac-validation-warn.warn-song-missing {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(96, 165, 250, 0.06));
    border: 1px solid rgba(59, 130, 246, 0.4);
    color: #3b82f6;
}
@keyframes acWarnFadeIn {
    from { opacity: 0; transform: translateY(-6px); }
    to { opacity: 1; transform: translateY(0); }
}
"""
# 现代化界面构建
# ============================================

# 自定义主题配置（兼容旧版Gradio）- 支持自动深色模式
try:
    # 使用Soft主题作为基础，支持系统深色模式自动切换
    theme = gr.themes.Soft(
        font=['XiaChanYuanTi', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        font_mono=['SF Mono', 'Consolas', 'monospace'],
        primary_hue=gr.themes.colors.Violet,
        secondary_hue=gr.themes.colors.Purple,
        neutral_hue=gr.themes.colors.Slate,
        radius_size=gr.themes.radius_sizes.Large,
    ).set(

        # 通用设置 - 紫罗兰暮光主题
        body_background_fill="#f5f3ff",
        background_fill_primary="#ffffff",
        background_fill_secondary="#ede9fe",
        border_color_accent="#7c3aed",
        border_color_default="#ddd6fe",
        color_accent_soft="#ddd6fe",
        # 深色模式优化
        body_background_fill_dark="#1a0a2e",
        background_fill_primary_dark="#1e1538",
        background_fill_secondary_dark="#2d1b4e",
        border_color_accent_dark="#a78bfa",
        border_color_default_dark="#8b5cf6",
        color_accent_soft_dark="#c4b5fd",
    )
except AttributeError:
    # 旧版本Gradio不支持themes，使用默认主题
    theme = None


# 🎯 任务调度系统 - Task Scheduler System
# ============================================

import threading
import time as _sched_time
import queue
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any, Optional


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Task:
    id: str
    name: str
    type: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    step_text: str = ""
    detail: str = ""
    created_at: float = field(default_factory=_sched_time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    result: Any = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    pause_event: threading.Event = field(default_factory=threading.Event)
    _target: Optional[Callable] = field(default=None, repr=False)
    _args: tuple = field(default_factory=tuple)
    _kwargs: dict = field(default_factory=dict)

    @property
    def elapsed(self) -> float:
        if self.started_at:
            end = self.completed_at or _sched_time.time()
            return end - self.started_at
        return 0

    @property
    def eta(self) -> str:
        if self.progress > 0 and self.elapsed > 0:
            total_est = self.elapsed / (self.progress / 100.0)
            remaining = max(0, total_est - self.elapsed)
            if remaining < 60:
                return f"{remaining:.0f}秒"
            elif remaining < 3600:
                return f"{remaining/60:.1f}分钟"
            else:
                return f"{remaining/3600:.1f}小时"
        return "--"

    def cancel(self):
        self.status = TaskStatus.CANCELLED
        self.cancel_event.set()

    def pause(self):
        if self.status == TaskStatus.RUNNING:
            self.status = TaskStatus.PAUSED
            self.pause_event.clear()

    def resume(self):
        if self.status == TaskStatus.PAUSED:
            self.status = TaskStatus.RUNNING
            self.pause_event.set()

    def check_cancelled(self):
        self.cancel_event.wait(timeout=0.001)
        return self.cancel_event.is_set()

    def wait_if_paused(self):
        while self.status == TaskStatus.PAUSED and not self.check_cancelled():
            self.pause_event.wait(timeout=0.5)


class ResourceMonitor:
    """系统资源监控模块（GPU显存 + 系统内存，通过nvidia-smi实时读取）"""

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
                "is_stressed": ((gpu_percent > 90) if gpu_available else False) or (sys_mem.percent > 90),
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


try:
    import psutil
except ImportError:
    psutil = None

class TaskQueue:
    """任务队列管理器（支持优先级排序）"""

    def __init__(self):
        self._queue: list[Task] = []
        self._lock = threading.RLock()
        self._task_counter = 0
        self._history: list[Task] = []

    def enqueue(self, task: Task) -> Task:
        with self._lock:
            self._task_counter += 1
            task.id = f"T{self._task_counter:04d}"
            self._queue.append(task)
            self._sort_queue()
            print_status(f"📋 任务入队 [{task.id}] {task.name} (优先级:{task.priority.name})", "info")
            return task

    def dequeue(self) -> Optional[Task]:
        with self._lock:
            if self._queue:
                task = self._queue.pop(0)
                return task
            return None

    def peek(self) -> Optional[Task]:
        with self._lock:
            return self._queue[0] if self._queue else None

    def remove(self, task_id: str) -> bool:
        with self._lock:
            for i, t in enumerate(self._queue):
                if t.id == task_id:
                    t.cancel()
                    self._queue.pop(i)
                    print_status(f"❌ 任务已移除 [{task_id}] {t.name}", "warning")
                    return True
            return False

    def move_up(self, task_id: str) -> bool:
        with self._lock:
            for i, t in enumerate(self._queue):
                if t.id == task_id and i > 0:
                    self._queue[i], self._queue[i-1] = self._queue[i-1], self._queue[i]
                    print_status(f"⬆️ 任务上移 [{task_id}]", "info")
                    return True
            return False

    def move_down(self, task_id: str) -> bool:
        with self._lock:
            for i, t in enumerate(self._queue):
                if t.id == task_id and i < len(self._queue) - 1:
                    self._queue[i], self._queue[i+1] = self._queue[i+1], self._queue[i]
                    print_status(f"⬇️ 任务下移 [{task_id}]", "info")
                    return True
            return False

    def move_to_top(self, task_id: str) -> bool:
        with self._lock:
            for i, t in enumerate(self._queue):
                if t.id == task_id and i > 0:
                    task = self._queue.pop(i)
                    self._queue.insert(0, task)
                    print_status(f"⏫ 任务置顶 [{task_id}] {t.name}", "info")
                    return True
            return False

    def _sort_queue(self):
        self._queue.sort(key=lambda t: (t.priority.value, t.created_at))

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len([t for t in self._queue if t.status == TaskStatus.PENDING])

    @property
    def all_tasks(self) -> list[Task]:
        with self._lock:
            return list(self._queue)

    def add_to_history(self, task: Task):
        self._history.append(task)
        if len(self._history) > 20:
            self._history.pop(0)


class TaskScheduler:
    """全局任务调度器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.queue = TaskQueue()
        self._current_task: Optional[Task] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._state_lock = threading.RLock()
        self._update_callbacks: list[Callable] = []
        self._completion_callbacks: list[Callable] = []

    @property
    def is_busy(self) -> bool:
        with self._state_lock:
            return self._current_task is not None and self._current_task.status == TaskStatus.RUNNING

    @property
    def current_task(self) -> Optional[Task]:
        with self._state_lock:
            return self._current_task

    @property
    def queue_html(self) -> str:
        return self._render_queue_ui()

    def submit(self, name: str, task_type: str, target: Callable,
               args: tuple = (), kwargs: dict = None,
               priority: TaskPriority = TaskPriority.NORMAL) -> Task:
        kwargs = kwargs or {}
        task = Task(
            id="", name=name, type=task_type,
            priority=priority,
            _target=target, _args=args, _kwargs=kwargs,
        )
        self.queue.enqueue(task)
        self._notify_update()
        if not self._running:
            self.start()
        return task

    def start(self):
        with self._state_lock:
            if self._running:
                return
            self._running = True
            self._scheduler_thread = threading.Thread(target=self._run_loop, daemon=True, name="TaskScheduler")
            self._scheduler_thread.start()
            print_status("✅ 任务调度器已启动", "success")

    def stop(self):
        with self._state_lock:
            self._running = False
            if self._current_task:
                self._current_task.cancel()
        print_status("⏹️ 任务调度器已停止", "warning")

    def cancel_current(self):
        with self._state_lock:
            if self._current_task:
                self._current_task.cancel()
                print_status(f"❌ 取消当前任务: {self._current_task.name}", "warning")

    def pause_current(self):
        with self._state_lock:
            if self._current_task and self._current_task.status == TaskStatus.RUNNING:
                self._current_task.pause()
                print_status(f"⏸️ 暂停当前任务: {self._current_task.name}", "info")

    def resume_current(self):
        with self._state_lock:
            if self._current_task and self._current_task.status == TaskStatus.PAUSED:
                self._current_task.resume()
                print_status(f"▶️ 继续当前任务: {self._current_task.name}", "info")

    def cancel_queued(self, task_id: str) -> bool:
        return self.queue.remove(task_id)

    def clear_pending(self):
        with self.queue._lock:
            count = len([t for t in self.queue._queue if t.status == TaskStatus.PENDING])
            self.queue._queue = [t for t in self.queue._queue if t.status != TaskStatus.PENDING]
            if count:
                print_status(f"🗑️ 已清除 {count} 个待处理任务", "warning")
            self._notify_update()
            return count

    def on_update(self, callback: Callable):
        self._update_callbacks.append(callback)

    def on_complete(self, callback: Callable):
        self._completion_callbacks.append(callback)

    def _notify_update(self):
        for cb in self._update_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _notify_complete(self, task: Task):
        for cb in self._completion_callbacks:
            try:
                cb(task)
            except Exception:
                pass

    def _run_loop(self):
        while self._running:
            task = self.queue.dequeue()
            if task is None:
                _sched_time.sleep(0.5)
                continue

            with self._state_lock:
                self._current_task = task
                task.status = TaskStatus.RUNNING
                task.started_at = _sched_time.time()
                task.pause_event.set()

            self._notify_update()
            print_status(f"▶️ 开始执行 [{task.id}] {task.name}", "convert")

            try:
                if task._target:
                    result = task._target(*task._args, **task._kwargs)
                    task.result = result
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.completed_at = _sched_time.time()
                print_status(f"✅ 任务完成 [{task.id}] {task.name} ({task.elapsed:.1f}s)", "success")
            except Exception as e:
                import traceback
                traceback.print_exc()
                task.error = str(e)
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.FAILED
                    print_status(f"⚠️ 任务失败 [{task.id}], 正在重试 ({task.retry_count}/{task.max_retries})...", "error")
                    self.queue.enqueue(Task(
                        id="", name=f"[重试{task.retry_count}] {task.name}",
                        type=task.type, priority=task.priority,
                        _target=task._target, _args=task._args, _kwargs=task._kwargs,
                        retry_count=task.retry_count, max_retries=task.max_retries,
                    ))
                else:
                    task.status = TaskStatus.FAILED
                    print_status(f"❌ 任务最终失败 [{task.id}] {task.name}: {str(e)}", "error")

            self.queue.add_to_history(task)
            self._notify_complete(task)
            self._notify_update()

            with self._state_lock:
                self._current_task = None

    def _render_queue_ui(self) -> str:
        try:
            pending_tasks = [t for t in self.queue.all_tasks if t.status == TaskStatus.PENDING]
            current = self.current_task
            res_info = ResourceMonitor.get_status_html()
        except Exception:
            res_info = '<span style="font-size:0.72rem;color:#64748b;">资源监控加载中...</span>'
            pending_tasks = []
            current = None

        parts = [f"""<div style="font-family:-apple-system,sans-serif;background:#0f172a;border-radius:12px;padding:14px;border:1px solid #1e293b;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <span style="font-weight:700;font-size:0.85rem;color:#e2e8f0;">🎯 任务调度中心</span>
                <span style="font-size:0.68rem;color:#64748b;">队列: {len(pending_tasks)} 个待处理</span>
            </div>
            {res_info}"""]

        if current:
            pct = current.progress
            bar_color = "#22c55e" if current.status == TaskStatus.COMPLETED else ("#f59e0b" if current.status == TaskStatus.PAUSED else "#3b82f6")
            status_icon = {"running": "🔄", "paused": "⏸️", "completed": "✅", "failed": "❌", "cancelled": "🚫"}.get(current.status.value, "📋")
            status_label = {"running": "执行中", "paused": "已暂停", "completed": "已完成", "failed": "失败", "cancelled": "已取消"}.get(current.status.value, "")

            parts.append(f"""
            <div style="background:#1e293b;border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #3b82f6;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <span><b>{status_icon}</b> <span style="color:#93c5fd;font-size:0.78rem;">{current.name}</span></span>
                    <span style="font-size:0.68rem;color:{bar_color};">{status_label} {pct}%</span>
                </div>
                <div style="background:#0f172a;border-radius:4px;height:6px;overflow:hidden;margin-bottom:4px;">
                    <div style="background:{bar_color};width:{min(pct,100)}%;height:100%;border-radius:4px;transition:width 0.3s;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.68rem;color:#64748b;">
                    <span>{current.step_text or '--'}</span>
                    <span>⏱ {current.elapsed:.0f}s | ETA: {current.eta}</span>
                </div>
            </div>""")

        if pending_tasks:
            parts.append('<div style="max-height:120px;overflow-y:auto;">')
            for i, t in enumerate(pending_tasks[:8]):
                pri_icon = {"HIGH": "🔴", "NORMAL": "🟡", "LOW": "🟢"}.get(t.priority.name, "⚪")
                parts.append(f"""
                <div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:4px;font-size:0.72rem;color:#94a3b8;{'background:#1e293b' if i%2==0 else ''}">
                    <span>{pri_icon}</span>
                    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{t.name}</span>
                    <span style="color:#475569;flex-shrink:0;">等待中</span>
                </div>""")
            if len(pending_tasks) > 8:
                parts.append(f'<div style="text-align:center;font-size:0.68rem;color:#475569;padding:4px;">... 还有 {len(pending_tasks)-8} 个任务</div>')
            parts.append('</div>')

        history = self.queue._history[-3:]
        if history:
            parts.append('<div style="margin-top:8px;border-top:1px solid #1e293b;padding-top:6px;">')
            parts.append('<span style="font-size:0.68rem;color:#475569;">最近完成:</span>')
            for h in reversed(history):
                icon = "✅" if h.status == TaskStatus.COMPLETED else ("❌" if h.status == TaskStatus.FAILED else "🚫")
                parts.append(f'<div style="font-size:0.68rem;color:#64748b;">{icon} {h.name} ({h.elapsed:.0f}s)</div>')
            parts.append('</div>')

        parts.append("</div>")
        return "\n".join(parts)


scheduler = TaskScheduler()

weight_root = os.getenv("weight_root") or os.path.join(now_dir, "weights")
weight_uvr5_root = os.getenv("weight_uvr5_root") or os.path.join(now_dir, "assets", "uvr5_weights")
index_root = os.getenv("index_root") or os.path.join(now_dir, "logs")
outside_index_root = os.getenv("outside_index_root") or os.path.join(now_dir, "logs")

names = []
if weight_root and os.path.isdir(weight_root):
    for name in os.listdir(weight_root):
        if name.endswith(".pth"):
            names.append(name)
index_paths = []

def lookup_indices(index_root):
    global index_paths
    for root, dirs, files in os.walk(index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append(os.path.join(root, name))

lookup_indices(index_root)
lookup_indices(outside_index_root)

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
else:
    uvr5_names = ["(未安装 audio_tools - 使用 Fallback)"]


def _progress_html(percent: float, step_text: str = "", detail: str = "",
                   elapsed: float = None, remaining: float = None, tip: str = "") -> str:
    """生成增强版可视化进度条 HTML，含动画、步骤指示、耗时预估"""
    percent = max(0, min(100, percent))
    is_active = percent > 0 and percent < 100
    bar_color = "#a78bfa"
    bg_color = "rgba(15, 10, 30, 0.85)"
    elapsed_str = ""
    if elapsed is not None:
        if elapsed < 60:
            elapsed_str = f"⏱️ 已用 {elapsed:.0f}s"
        else:
            elapsed_str = f"⏱️ 已用 {elapsed/60:.1f}min"
        if remaining is not None and remaining > 0:
            if remaining < 60:
                elapsed_str += f" · 预计剩余 {remaining:.0f}s"
            else:
                elapsed_str += f" · 预计剩余 {remaining/60:.1f}min"

    tip_html = ""
    if tip:
        tip_html = f"""<div style="margin-top: 6px; padding: 6px 10px; border-radius: 6px; background: rgba(251,191,36,0.1); border-left: 3px solid #fbbf24; color: #fde68a; font-size: 0.72rem;">💡 {tip}</div>"""

    status_icon = "🔄" if is_active else ("✅" if percent >= 100 else "⏳")
    status_color = "#34d399" if percent >= 100 else ("#fbbf24" if is_active else "#94a3b8")

    anim_style = ""
    if is_active:
        anim_style = ";animation: progressShimmer 2s ease-in-out infinite;background-size: 200% 100%;"

    return f"""<div style="margin: 8px 0; padding: 12px 14px; border-radius: 12px; background: {bg_color}; border: 1px solid rgba(124,58,237,0.15);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="display:flex;align-items:center;gap:6px;color:#e0e7ff;font-size:0.82rem;font-weight:600;">
                <span style="font-size:1rem;">{status_icon}</span> {step_text or '准备中'}
            </span>
            <span style="color:{status_color};font-size:0.9rem;font-weight:700;min-width:42px;text-align:right;">{percent:.0f}%</span>
        </div>
        <div style="width:100%;height:12px;background:rgba(124,58,237,0.12);border-radius:6px;overflow:hidden;position:relative;">
            <div style="width:{percent}%;height:100%;background:linear-gradient(90deg,#7c3aed,{bar_color},#c4b5fd);border-radius:6px;transition:width 0.35s cubic-bezier(0.4,0,0.2,1){anim_style};">
            </div>
            """ + ('<div style="position:absolute;top:50%;left:var(--pos,50%);transform:translate(-50%,-50%);width:6px;height:6px;border-radius:50%;background:#fff;box-shadow:0 0 8px rgba(255,255,255,0.8);"></div>' if is_active else '') + """
        </div>""" + (f'<div style="color:#c4b5fd;font-size:0.76rem;margin-top:6px;line-height:1.4;">{detail}</div>' if detail else '') + (f'<div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:0.72rem;margin-top:4px;"><span>{elapsed_str}</span><span>{"处理中..." if is_active else ("完成 ✓" if percent >= 100 else "等待中...")}</span></div>' if elapsed_str else '') + f"""
        {tip_html}
    </div>
    <style>@keyframes progressShimmer{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}</style>"""


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

    def _run_with_progress(callable_fn, start_pct, end_pct, step_text, detail_start, duration_est=30.0, result_holder=None):
        """在后台线程运行阻塞操作，同时yield进度更新"""
        import threading
        if result_holder is None:
            result_holder = [None]
        error_holder = [None]
        done_flag = threading.Event()
        started_flag = threading.Event()

        def _worker():
            started_flag.set()
            try:
                result_holder[0] = callable_fn()
            except Exception as e:
                error_holder[0] = e
            finally:
                done_flag.set()

        thread = threading.Thread(target=_worker)
        thread.daemon = True
        thread.start()
        started_flag.wait(timeout=5.0)

        steps = 30
        interval = duration_est / steps
        for i in range(steps + 1):
            pct = start_pct + (end_pct - start_pct) * (i / steps)
            detail = f"{detail_start} ({min(int((i / steps) * 100), 99)}%)"
            yield _p(pct, step_text, detail, elapsed=_elapsed()), "", None, None
            if done_flag.is_set():
                break
            if i < steps:
                _time.sleep(interval)

        thread.join(timeout=10.0)
        if error_holder[0]:
            raise error_holder[0]
        yield _p(end_pct, step_text, f"{detail_start} (100%)", elapsed=_elapsed()), "", None, None

    def _sub_progress(start_pct, end_pct, step_text, detail_template, duration_est=15.0, interval=0.8):
        """生成平滑的子进度更新（用于长时间操作）"""
        steps = max(int(duration_est / interval), 5)
        for i in range(steps + 1):
            pct = start_pct + (end_pct - start_pct) * (i / steps)
            detail = detail_template.format(pct=int((i/steps)*100))
            yield _p(pct, step_text, detail, elapsed=_elapsed()), "", None, None
            if i < steps:
                _time.sleep(interval)

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
    sep_base_dir = _SEP_CACHE_ROOT
    os.makedirs(sep_base_dir, exist_ok=True)

    total = len(all_paths)
    steps_per_song = int(do_separate) + int(do_dereverb)
    total_steps = total * steps_per_song
    model_load_weight = 10  # 模型加载占10%权重
    processing_weight = 90  # 实际处理占90%权重

    def _check_hash_cache(audio_hash, need_sep=False, need_deverb=False):
        """检查本地缓存（基于文件hash）：已处理的文件直接返回路径"""
        cached = {"vocal": None, "instr": None}
        if need_sep:
            vocal_path = os.path.join(_SEP_CACHE_ROOT, f"{audio_hash}_vocal.wav")
            instr_path = os.path.join(_SEP_CACHE_ROOT, f"{audio_hash}_instr.wav")
            if os.path.exists(vocal_path):
                cached["vocal"] = vocal_path
            if os.path.exists(instr_path):
                cached["instr"] = instr_path
        if need_deverb:
            clean_path = os.path.join(_SEP_CACHE_ROOT, f"{audio_hash}_clean.wav")
            if os.path.exists(clean_path):
                cached["vocal"] = clean_path
        return cached

    def _save_hash_cache(audio_path, audio_hash, vocal_path, instr_path=None, clean_vocal_path=None):
        """保存分离结果到hash缓存目录并记录日志"""
        os.makedirs(_SEP_CACHE_ROOT, exist_ok=True)
        duration = _get_audio_duration(audio_path)
        target_vocal = clean_vocal_path if clean_vocal_path else vocal_path
        saved_vocal = None
        saved_instr = None
        if target_vocal and os.path.exists(target_vocal):
            cached_vocal = os.path.join(_SEP_CACHE_ROOT, f"{audio_hash}_vocal.wav")
            shutil.copy2(target_vocal, cached_vocal)
            saved_vocal = cached_vocal
        if instr_path and os.path.exists(instr_path):
            cached_instr = os.path.join(_SEP_CACHE_ROOT, f"{audio_hash}_instr.wav")
            shutil.copy2(instr_path, cached_instr)
            saved_instr = cached_instr
        if clean_vocal_path and os.path.exists(clean_vocal_path):
            cached_clean = os.path.join(_SEP_CACHE_ROOT, f"{audio_hash}_clean.wav")
            shutil.copy2(clean_vocal_path, cached_clean)
        _log_sep_cache(audio_hash, audio_path, duration, saved_vocal, saved_instr)
        print_status(f"💾 分离缓存已保存: {audio_hash}", "save")
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
                yield _p(2, "正在加载分离模型...", "首次加载需要从硬盘读取模型，请稍候",
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
            # 去混响模块：只有专用 deverb 模型存在时才加载。缺模型时不再用通用
            # bs_roformer 硬跑，避免长时间卡在额外分离阶段。
            deverb_model_path = os.path.join(
                os.getcwd(),
                "audio_tools",
                "models",
                "separator",
                "deverb_bs_roformer_8_256dim_8depth.ckpt",
            )
            need_standalone_deverb = (
                _do_deverb
                and (chained_sep is None or not chain_has_deverb)
                and os.path.exists(deverb_model_path)
            )
            if _do_deverb and not chain_has_deverb and not os.path.exists(deverb_model_path):
                print_status("⚠️  未找到专用去混响模型，已跳过去混响阶段", "warning")
            if need_standalone_deverb:
                yield _p(6, "正在加载去混响模型...", "首次加载需要从硬盘读取模型，请稍候",
                         tip="首次加载模型可能需要 10-30 秒（取决于硬盘速度），后续处理同一批歌曲无需重复加载",
                         elapsed=_elapsed()),
                dereverb_sep = SeparatorModel(model_type="bs_roformer")
                dereverb_sep.load()
                print_status(f"🔇 独立去混响模块就绪", "sep")

        model_load_time = _elapsed()
        yield _p(model_load_weight, "模型就绪", "开始处理音频文件...", elapsed=_elapsed()), "", None, None

        for idx, audio_path in enumerate(all_paths):
            _do_deverb = do_dereverb
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            audio_hash = _compute_audio_hash(audio_path)

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

            song_base_pct = model_load_weight + (idx / total) * processing_weight
            yield _p(song_base_pct, f"[{idx+1}/{total}] {base_name}", f"开始{task_desc}...",
                     elapsed=_elapsed(), remaining=est_remain), "", last_vocal, last_instr

            current_vocal = None
            current_instr = None

            # ---- 缓存检查：已处理文件直接复用 ----
            cache_hit = False
            cached = _check_hash_cache(audio_hash, need_sep=do_separate, need_deverb=_do_deverb)
            if do_separate and (cached["vocal"] or cached["instr"]):
                if cached["vocal"]:
                    current_vocal = cached["vocal"]
                if cached["instr"]:
                    current_instr = cached["instr"]
                    msgs.append(f"  📦 伴奏(缓存) -> {os.path.basename(cached['instr'])}")
                cache_hit = True
                print_status(f"📦 [{idx+1}/{total}] {base_name}: 命中分离缓存(hash={audio_hash[:8]})，跳过", "info")
                step_count += int(do_separate)
            if _do_deverb and not cache_hit:
                clean_cached = _check_hash_cache(audio_hash, need_deverb=True)
                if clean_cached["vocal"] and current_vocal != clean_cached["vocal"]:
                    current_vocal = clean_cached["vocal"]
                    msgs.append(f"  📦 去混响干声(缓存) -> {os.path.basename(clean_cached['vocal'])}")
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
                    step_count += 1
                elif isinstance(sep, ChainedSeparator):
                    # 链式分离管线：kim_vocal → deverb → karaoke
                    step_weight = processing_weight / max(total_steps, 1)
                    sep_start_pct = song_base_pct + (step_count / total_steps) * step_weight * processing_weight / 100 + model_load_weight
                    sep_end_pct = sep_start_pct + step_weight
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    use_deverb_stage = _do_deverb  # 如果用户勾选了去混响，在管线中启用
                    yield _p(sep_start_pct, f"[{idx+1}/{total}] {base_name}", "正在链式分离 (Kim→去混响→Karaoke)...",
                             elapsed=_elapsed(), remaining=est_remain), "", last_vocal, last_instr
                    _step_t = _time.time()
                    sep_out = os.path.join(sep_base_dir, f"_{base_name}_sep_tmp")

                    def _do_chained_sep():
                        return sep.separate(
                            audio_path, sep_out,
                            use_kim_vocal=True,
                            use_deverb=use_deverb_stage,
                            use_karaoke=True,
                        )

                    result_holder = [None]
                    for prog_update in _run_with_progress(_do_chained_sep, sep_start_pct, sep_end_pct,
                                                          f"[{idx+1}/{total}] {base_name}", "链式分离",
                                                          duration_est=60.0, result_holder=result_holder):
                        if _is_cancelled("audio_sep"):
                            break
                        yield prog_update
                    result = result_holder[0]

                    if result.vocals and os.path.exists(result.vocals):
                        saved_vocal = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                        shutil.copy2(result.vocals, saved_vocal)
                        current_vocal = saved_vocal
                        
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
                    yield _p(sep_end_pct, f"[{idx+1}/{total}] {base_name}", "✅ 链式分离完成",
                             elapsed=_elapsed(), remaining=max(0, est_remain - (_time.time() - _step_t))), "", last_vocal, last_instr
                    # 链式管线已包含去混响时，才跳过 Step 2（必须检查 deverb stage 真的加载了）
                    if chain_has_deverb:
                        _do_deverb = False  # 标记为已完成
                        print_status(f"✅ [{idx+1}/{total}] {base_name}: 链式管线已完成去混响", "success")
                        # 清理不需要的人声文件（仅保留伴奏和去混响干声）
                        try:
                            vocal_file = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                            if os.path.exists(vocal_file):
                                os.remove(vocal_file)
                                msgs.append(f"  🗑️ 已删除人声文件: {base_name} (Vocals).wav")
                        except Exception:
                            pass
                    elif use_deverb_stage:
                        # 用户勾选了去混响但链式管线 deverb stage 没加载，需要后续独立处理
                        print_status(f"⚠️ [{idx+1}/{total}] {base_name}: 链式去混响未加载，将使用独立模块", "warning")
                else:
                    step_weight = processing_weight / max(total_steps, 1)
                    sep_start_pct = song_base_pct + (step_count / total_steps) * step_weight * processing_weight / 100 + model_load_weight
                    sep_end_pct = sep_start_pct + step_weight
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    yield _p(sep_start_pct, f"[{idx+1}/{total}] {base_name}", "正在分离人声...",
                             elapsed=_elapsed(), remaining=est_remain), "", last_vocal, last_instr
                    _step_t = _time.time()
                    sep_out = os.path.join(sep_base_dir, f"_{base_name}_sep_tmp")

                    def _do_sep():
                        return sep.separate(audio_path, sep_out, instruments=["vocals", "other"])

                    result_holder = [None]
                    for prog_update in _run_with_progress(_do_sep, sep_start_pct, sep_end_pct,
                                                          f"[{idx+1}/{total}] {base_name}", "人声分离",
                                                          duration_est=60.0, result_holder=result_holder):
                        if _is_cancelled("onepass"):
                            break
                        yield prog_update
                    result = result_holder[0]

                    if result.vocals and os.path.exists(result.vocals):
                        saved_vocal = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                        shutil.copy2(result.vocals, saved_vocal)
                        current_vocal = saved_vocal
                        
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
                    yield _p(sep_end_pct, f"[{idx+1}/{total}] {base_name}", "✅ 人声分离完成",
                             elapsed=_elapsed(), remaining=max(0, est_remain - (_time.time() - _step_t))), "", last_vocal, last_instr
                    # 如果后续会去混响，暂时保留Vocals文件供去混响使用，否则直接删除
                    if not _do_deverb:
                        try:
                            vocal_file = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                            if os.path.exists(vocal_file):
                                os.remove(vocal_file)
                                msgs.append(f"  🗑️ 已删除人声文件: {base_name} (Vocals).wav")
                        except Exception:
                            pass

            # ---- Step 2: 去混响（独立模式或链式deverb失败时） ----
            if _do_deverb:
                if dereverb_sep is None:
                    msgs.append(f"  ⚠️ 去混响模块未加载，跳过（可能链式管线已包含去混响）")
                    print_status(f"⚠️ [{idx+1}/{total}] {base_name}: 去混响模块不可用", "warning")
                    step_count += 1
                elif not current_vocal:
                    msgs.append(f"  ⚠️ 无干声输入，跳过去混响")
                    print_status(f"⚠️ [{idx+1}/{total}] {base_name}: 无干声输入，无法去混响", "warning")
                    step_count += 1
                else:
                    step_weight = processing_weight / max(total_steps, 1)
                    dereverb_start_pct = song_base_pct + (step_count / total_steps) * step_weight * processing_weight / 100 + model_load_weight
                    dereverb_end_pct = dereverb_start_pct + step_weight
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    yield _p(dereverb_start_pct, f"[{idx+1}/{total}] {base_name}", "正在去除混响...",
                             elapsed=_elapsed(), remaining=est_remain), "", last_vocal, last_instr
                    _step_t = _time.time()
                    input_for_dereverb = current_vocal if current_vocal else audio_path

                    dereverb_out = os.path.join(sep_base_dir, f"_{base_name}_deref_tmp")

                    def _do_dereverb():
                        return dereverb_sep.separate(
                            input_for_dereverb, dereverb_out,
                            instruments=["vocals", "other"],
                        )

                    result_holder = [None]
                    for prog_update in _run_with_progress(_do_dereverb, dereverb_start_pct, dereverb_end_pct,
                                                          f"[{idx+1}/{total}] {base_name}", "去混响",
                                                          duration_est=60.0, result_holder=result_holder):
                        if _is_cancelled("audio_sep"):
                            break
                        yield prog_update
                    d_result = result_holder[0]

                    if d_result.vocals and os.path.exists(d_result.vocals):
                        saved_clean = os.path.join(sep_base_dir, f"{base_name} (Clean).wav")
                        shutil.copy2(d_result.vocals, saved_clean)
                        current_vocal = saved_clean
                        msgs.append(f"  去混响干声 -> {os.path.basename(saved_clean)}")
                        try:
                            vocal_file = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                            if os.path.exists(vocal_file):
                                os.remove(vocal_file)
                        except Exception:
                            pass

                    try:
                        shutil.rmtree(dereverb_out, ignore_errors=True)
                    except Exception:
                        pass
                    step_times.append(_time.time() - _step_t)
                    step_count += 1
                    yield _p(dereverb_end_pct, f"[{idx+1}/{total}] {base_name}", "✅ 去混响完成",
                             elapsed=_elapsed(), remaining=max(0, est_remain - (_time.time() - _step_t))), "", last_vocal, last_instr
                    # 清理原始人声文件（已有去混响后的Clean文件）
                    try:
                        vocal_file = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                        if os.path.exists(vocal_file):
                            os.remove(vocal_file)
                            msgs.append(f"  🗑️ 已删除原人声文件: {base_name} (Vocals).wav")
                    except Exception:
                        pass

            # 处理完成后保存到 hash 缓存
            if not cache_hit and (current_vocal or current_instr):
                _save_hash_cache(
                    audio_path, audio_hash,
                    vocal_path=current_vocal,
                    instr_path=current_instr,
                    clean_vocal_path=current_vocal if _do_deverb else None
                )

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
        if not _acquire_exec("full_pipeline", "全流程"):
            yield _progress_html(0, "⚠️ 执行中", "当前有全流程任务正在运行"), None, None, None, "", scheduler.queue_html
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
            yield _progress_html(0, "准备中"), "请至少勾选一个处理步骤", None, None, scheduler.queue_html
            return

        _lt = _LiveTaskCtx(f"🚀 全流程 · {base_name}", "full_pipeline")
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
                _update_task_name("full_pipeline", "分离: " + base_name)
                yield _progress(0, "正在分离人声...",
                                tip="使用链式分离管线: Kim人声→去混响→Karaoke伴奏"), None, None, None, scheduler.queue_html
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
                    _update_task_name("full_pipeline", "分离不可用")
                    yield _progress(0, "分离模块不可用"), None, None, None, scheduler.queue_html

            step_idx = 1

            # ---- Step: 去混响 ----
            if do_dereverb:
                _lt.update(15, "去混响中...")
                _update_task_name("full_pipeline", "去混响: " + base_name)
                yield _progress(step_idx, "正在去除混响...",
                                tip="正在加载去混响模型，首次较慢"), None, None, None, scheduler.queue_html
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
                _update_task_name("full_pipeline", f"变调{pitch_steps:+d}: " + base_name)
                yield _progress(step_idx, f"正在变调 {pitch_steps:+d} 半音..."), None, None, None, scheduler.queue_html
                input_p = current_vocal or audio_path
                p_out = os.path.join(out_dir, f"{base_name}_shift{pitch_steps:+d}.wav")
                try:
                    from audio_tools.vocoder import pitch_shift_audio
                    pitch_shift_audio(input_p, p_out, pitch_steps, "librosa")
                    current_vocal = p_out
                except Exception as e:
                    _lt.update(25, f"变调失败: {e}")
                    _update_task_name("full_pipeline", "变调失败")
                    yield _progress(step_idx, f"变调失败: {e}"), None, None, None, scheduler.queue_html
                step_idx += 1

            # ---- Step: 音色转换 ----
            if do_vc:
                _lt.update(35, f"音色转换 ({model_name})")
                _update_task_name("full_pipeline", "转换: " + model_label)
                yield _progress(step_idx, f"正在音色转换 ({model_name})..."), None, None, None, scheduler.queue_html
            vc_input = current_vocal or audio_path
            if model_name and vc_input:
                try:
                    _f0_up = int(float(vc_transform_single_value)) if vc_transform_single_value is not None else 0
                    vc_result = get_vc().vc_single(
                        0,
                        vc_input,
                        _f0_up,
                        None,
                        "rmvpe",
                        "",
                        None,
                        0.75,
                        3,
                        0,
                        1.0,
                        0.33,
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
                    _update_task_name("full_pipeline", "转换失败")
                    yield _progress(step_idx, f"音色转换失败: {e}"), None, None, None, scheduler.queue_html
            else:
                _lt.update(35, "请先选择模型")
                _update_task_name("full_pipeline", "无模型")
                yield _progress(step_idx, "请先选择模型"), None, None, None, scheduler.queue_html
            step_idx += 1

            # ---- Step: 混音 ----
            if do_mix and current_vocal and current_instr:
                _lt.update(65, "混音中...")
                _update_task_name("full_pipeline", "混音: " + base_name)
                yield _progress(step_idx, "正在混音..."), None, None, None, scheduler.queue_html
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
                    _update_task_name("full_pipeline", "混音失败")
                    yield _progress(step_idx, f"混音失败: {e}"), None, None, None, scheduler.queue_html
                step_idx += 1

            # ---- Step: 混响 ----
            if do_reverb:
                _lt.update(75, "添加混响中...")
                _update_task_name("full_pipeline", "混响: " + base_name)
                yield _progress(step_idx, "正在添加混响..."), None, None, None, scheduler.queue_html
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
                        _update_task_name("full_pipeline", "混响失败")
                        yield _progress(step_idx, f"混响失败: {e}"), None, None, None, scheduler.queue_html
                step_idx += 1

            # ---- 完成 ----
            total_time = _elapsed()
            time_str = f"{total_time:.1f}s" if total_time < 60 else f"{total_time/60:.1f}min"
            done_html = _progress_html(100, "全部完成",
                                       f"输出目录: {os.path.abspath(out_dir)} · 耗时 {time_str}",
                                       elapsed=total_time, remaining=0)
            dl_html = build_download_html(final_output if (final_output and os.path.exists(final_output)) else None, "⬇️ 下载全流程成品", "purple")
            _lt.update(100, "✅ 全部完成")
            _update_task_name("full_pipeline", "完成: " + base_name)
            yield done_html, current_vocal, current_instr, final_output, dl_html, scheduler.queue_html
        except Exception as e:
            import traceback
            traceback.print_exc()
            if _lt:
                _lt.complete(success=False, error=str(e))
            _release_exec("full_pipeline")
            err_html = _progress_html(0, "处理出错", str(e), elapsed=_elapsed())
            yield err_html, current_vocal, current_instr, final_output, "", scheduler.queue_html
    finally:
        if _lt:
            _lt.complete(success=True)
        _release_exec("full_pipeline")


# ============================================
# 现代化界面构建
# ============================================

# 自定义主题配置（兼容旧版Gradio）- 支持自动深色模式
try:
    # 使用Soft主题作为基础，支持系统深色模式自动切换
    theme = gr.themes.Soft(
        font=['XiaChanYuanTi', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        font_mono=['SF Mono', 'Consolas', 'monospace'],
        primary_hue=gr.themes.colors.Violet,
        secondary_hue=gr.themes.colors.Purple,
        neutral_hue=gr.themes.colors.Slate,
        radius_size=gr.themes.radius_sizes.Large,
    ).set(
        # 通用设置 - 紫罗兰暮光主题
        body_background_fill="#f5f3ff",
        background_fill_primary="#ffffff",
        background_fill_secondary="#ede9fe",
        border_color_accent="#7c3aed",
        border_color_default="#ddd6fe",
        color_accent_soft="#ddd6fe",

        # 深色模式优化
        body_background_fill_dark="#1a0a2e",
        background_fill_primary_dark="#1e1538",
        background_fill_secondary_dark="#2d1b4e",
        border_color_accent_dark="#a78bfa",
        border_color_default_dark="#8b5cf6",
        color_accent_soft_dark="#c4b5fd",
    )
except AttributeError:
    # 旧版本Gradio不支持themes，使用默认主题
    theme = None



class _OutputHistoryStub:
    """Stub for _output_history when full implementation is unavailable"""
    def __init__(self): self._records = []
    def add_record(self, *a, **k): return len(self._records)
    def render_panel_html(self, *a, **k): return '<div style="color:#94a3b8;font-size:0.8rem;">无可用历史记录</div>'
    def clear_all(self, *a, **k): return 0
    def toggle_favorite(self, *a, **k): return ""
    def delete_record(self, *a, **k): return True

_output_history = _OutputHistoryStub()



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
                index_paths.append(os.path.join(root, name))
    for root, dirs, files in os.walk(outside_index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append(os.path.join(root, name))
    return sorted(index_paths)



def _make_recursion_safe(func):
    """Decorator that prevents function recursion - stub when original is unavailable"""
    return func




logger.info(i18n)
i18n = _ensure_i18n()
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


weight_root = os.getenv("weight_root") or os.path.join(now_dir, "weights")
weight_uvr5_root = os.getenv("weight_uvr5_root") or os.path.join(now_dir, "assets", "uvr5_weights")
index_root = os.getenv("index_root") or os.path.join(now_dir, "logs")
outside_index_root = os.getenv("outside_index_root") or os.path.join(now_dir, "logs")

names = []
if weight_root and os.path.isdir(weight_root):
    for name in os.listdir(weight_root):
        if name.endswith(".pth"):
            names.append(name)
index_paths = []


def lookup_indices(index_root):
    global index_paths
    for root, dirs, files in os.walk(index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append(os.path.join(root, name))


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
                index_paths.append(os.path.join(root, name))
    return {"choices": sorted(names), "__type__": "update", "value": None}, {
        "choices": sorted(index_paths),
        "__type__": "update",
        "value": None,
    }



def clean():
    return {"value": None, "__type__": "update"}


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
    # 🧪 触发服务器压力测试
    from tabs.pressure_test import start_pressure_test
    start_pressure_test()
    
    sr = sr_dict[sr]
    os.makedirs("%s/logs/%s" % (now_dir, exp_dir), exist_ok=True)
    f = open("%s/logs/%s/preprocess.log" % (now_dir, exp_dir), "w")
    f.close()
    cmd = '"%s" infer/modules/train/preprocess.py "%s" %s %s "%s/logs/%s" %s %.1f' % (
        get_config().python_cmd,
        trainset_dir,
        sr,
        n_p,
        now_dir,
        exp_dir,
        get_config().noparallel,
        get_config().preprocess_per,
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
    # 🧪 触发服务器压力测试
    from tabs.pressure_test import start_pressure_test
    start_pressure_test()
    
    gpus = gpus.split("-")
    os.makedirs("%s/logs/%s" % (now_dir, exp_dir), exist_ok=True)
    f = open("%s/logs/%s/extract_f0_feature.log" % (now_dir, exp_dir), "w")
    f.close()
    if if_f0:
        if f0method != "rmvpe_gpu":
            cmd = (
                '"%s" infer/modules/train/extract/extract_f0_print.py "%s/logs/%s" %s %s'
                % (
                    get_config().python_cmd,
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
                            get_config().python_cmd,
                            leng,
                            idx,
                            n_g,
                            now_dir,
                            exp_dir,
                            get_config().is_half,
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
                    get_config().python_cmd
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
                get_config().python_cmd,
                get_config().device,
                leng,
                idx,
                n_g,
                now_dir,
                exp_dir,
                version19,
                get_config().is_half,
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
    # 🧪 触发服务器压力测试
    from tabs.pressure_test import start_pressure_test
    start_pressure_test()
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
                get_config().json_config[config_path],
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
                get_config().python_cmd,
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
                get_config().python_cmd,
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
                    batch_size=256 * get_config().n_cpu,
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


F0GPUVisible = get_config().dml == False if config else True


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


def at_slice_audio(audio_path, min_dur, max_dur, top_db, output_dir=None):
    """音频切片：按静音分割音频"""
    if not _has_audio_tools:
        return None, "audio_tools 未安装，无法使用切片功能"
    if not audio_path:
        return None, "请上传或指定音频文件路径"
    try:
        if not output_dir:
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
    """生成增强版可视化进度条 HTML，含动画、步骤指示、耗时预估"""
    percent = max(0, min(100, percent))
    is_active = percent > 0 and percent < 100
    bar_color = "#a78bfa"
    bg_color = "rgba(15, 10, 30, 0.85)"
    elapsed_str = ""
    if elapsed is not None:
        if elapsed < 60:
            elapsed_str = f"⏱️ 已用 {elapsed:.0f}s"
        else:
            elapsed_str = f"⏱️ 已用 {elapsed/60:.1f}min"
        if remaining is not None and remaining > 0:
            if remaining < 60:
                elapsed_str += f" · 预计剩余 {remaining:.0f}s"
            else:
                elapsed_str += f" · 预计剩余 {remaining/60:.1f}min"

    tip_html = ""
    if tip:
        tip_html = f"""<div style="margin-top: 6px; padding: 6px 10px; border-radius: 6px; background: rgba(251,191,36,0.1); border-left: 3px solid #fbbf24; color: #fde68a; font-size: 0.72rem;">💡 {tip}</div>"""

    status_icon = "🔄" if is_active else ("✅" if percent >= 100 else "⏳")
    status_color = "#34d399" if percent >= 100 else ("#fbbf24" if is_active else "#94a3b8")

    anim_style = ""
    if is_active:
        anim_style = ";animation: progressShimmer 2s ease-in-out infinite;background-size: 200% 100%;"

    return f"""<div style="margin: 8px 0; padding: 12px 14px; border-radius: 12px; background: {bg_color}; border: 1px solid rgba(124,58,237,0.15);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="display:flex;align-items:center;gap:6px;color:#e0e7ff;font-size:0.82rem;font-weight:600;">
                <span style="font-size:1rem;">{status_icon}</span> {step_text or '准备中'}
            </span>
            <span style="color:{status_color};font-size:0.9rem;font-weight:700;min-width:42px;text-align:right;">{percent:.0f}%</span>
        </div>
        <div style="width:100%;height:12px;background:rgba(124,58,237,0.12);border-radius:6px;overflow:hidden;position:relative;">
            <div style="width:{percent}%;height:100%;background:linear-gradient(90deg,#7c3aed,{bar_color},#c4b5fd);border-radius:6px;transition:width 0.35s cubic-bezier(0.4,0,0.2,1){anim_style};">
            </div>
            """ + ('<div style="position:absolute;top:50%;left:var(--pos,50%);transform:translate(-50%,-50%);width:6px;height:6px;border-radius:50%;background:#fff;box-shadow:0 0 8px rgba(255,255,255,0.8);"></div>' if is_active else '') + """
        </div>""" + (f'<div style="color:#c4b5fd;font-size:0.76rem;margin-top:6px;line-height:1.4;">{detail}</div>' if detail else '') + (f'<div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:0.72rem;margin-top:4px;"><span>{elapsed_str}</span><span>{"处理中..." if is_active else ("完成 ✓" if percent >= 100 else "等待中...")}</span></div>' if elapsed_str else '') + f"""
        {tip_html}
    </div>
    <style>@keyframes progressShimmer{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}</style>"""


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
    sep_base_dir = _SEP_CACHE_ROOT
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
            _do_deverb = do_dereverb
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

            # ---- 缓存检查：已处理文件直接复用（已禁用，允许重复分离） ----
            cache_hit = False
            # cached = _check_cache(base_name, need_sep=do_separate, need_deverb=_do_deverb)
            # if do_separate and (cached["vocal"] or cached["instr"]):
            #     if cached["vocal"]:
            #         current_vocal = cached["vocal"]
            #     if cached["instr"]:
            #         current_instr = cached["instr"]
            #     msgs.append(f"  📦 伴奏(缓存) -> {os.path.basename(cached['instr'])}")
            #     cache_hit = True
            #     print_status(f"📦 [{idx+1}/{total}] {base_name}: 命中分离缓存，跳过", "info")
            #     step_count += int(do_separate)
            if _do_deverb and not cache_hit:
                clean_cached = _check_cache(base_name, need_deverb=True)
                if clean_cached["vocal"] and current_vocal != clean_cached["vocal"]:
                    current_vocal = clean_cached["vocal"]
                    msgs.append(f"  📦 去混响干声(缓存) -> {os.path.basename(clean_cached['vocal'])}")
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
                        msgs.append(f"  去混响干声 -> {saved_clean}")

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
        if not _acquire_exec("full_pipeline", "全流程"):
            yield _progress_html(0, "⚠️ 执行中", "当前有全流程任务正在运行"), None, None, None, "", scheduler.queue_html
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
            yield _progress_html(0, "准备中"), "请至少勾选一个处理步骤", None, None, scheduler.queue_html
            return

        _lt = _LiveTaskCtx(f"🚀 全流程 · {base_name}", "full_pipeline")
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
                _update_task_name("full_pipeline", "分离: " + base_name)
                yield _progress(0, "正在分离人声...",
                                tip="使用链式分离管线: Kim人声→去混响→Karaoke伴奏"), None, None, None, scheduler.queue_html
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
                    _update_task_name("full_pipeline", "分离不可用")
                    yield _progress(0, "分离模块不可用"), None, None, None, scheduler.queue_html

            step_idx = 1

            # ---- Step: 去混响 ----
            if do_dereverb:
                _lt.update(15, "去混响中...")
                _update_task_name("full_pipeline", "去混响: " + base_name)
                yield _progress(step_idx, "正在去除混响...",
                                tip="正在加载去混响模型，首次较慢"), None, None, None, scheduler.queue_html
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
                _update_task_name("full_pipeline", f"变调{pitch_steps:+d}: " + base_name)
                yield _progress(step_idx, f"正在变调 {pitch_steps:+d} 半音..."), None, None, None, scheduler.queue_html
                input_p = current_vocal or audio_path
                p_out = os.path.join(out_dir, f"{base_name}_shift{pitch_steps:+d}.wav")
                try:
                    from audio_tools.vocoder import pitch_shift_audio
                    pitch_shift_audio(input_p, p_out, pitch_steps, "librosa")
                    current_vocal = p_out
                except Exception as e:
                    _lt.update(25, f"变调失败: {e}")
                    _update_task_name("full_pipeline", "变调失败")
                    yield _progress(step_idx, f"变调失败: {e}"), None, None, None, scheduler.queue_html
                step_idx += 1

            # ---- Step: 音色转换 ----
            if do_vc:
                _lt.update(35, f"音色转换 ({model_name})")
                _update_task_name("full_pipeline", "转换: " + model_label)
                yield _progress(step_idx, f"正在音色转换 ({model_name})..."), None, None, None, scheduler.queue_html
            vc_input = current_vocal or audio_path
            if model_name and vc_input:
                try:
                    _f0_up = int(float(vc_transform_single_value)) if vc_transform_single_value is not None else 0
                    vc_result = get_vc().vc_single(
                        0,
                        vc_input,
                        _f0_up,
                        None,
                        "rmvpe",
                        "",
                        None,
                        0.75,
                        3,
                        0,
                        1.0,
                        0.33,
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
                    _update_task_name("full_pipeline", "转换失败")
                    yield _progress(step_idx, f"音色转换失败: {e}"), None, None, None, scheduler.queue_html
            else:
                _lt.update(35, "请先选择模型")
                _update_task_name("full_pipeline", "无模型")
                yield _progress(step_idx, "请先选择模型"), None, None, None, scheduler.queue_html
            step_idx += 1

            # ---- Step: 混音 ----
            if do_mix and current_vocal and current_instr:
                _lt.update(65, "混音中...")
                _update_task_name("full_pipeline", "混音: " + base_name)
                yield _progress(step_idx, "正在混音..."), None, None, None, scheduler.queue_html
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
                    _update_task_name("full_pipeline", "混音失败")
                    yield _progress(step_idx, f"混音失败: {e}"), None, None, None, scheduler.queue_html
                step_idx += 1

            # ---- Step: 混响 ----
            if do_reverb:
                _lt.update(75, "添加混响中...")
                _update_task_name("full_pipeline", "混响: " + base_name)
                yield _progress(step_idx, "正在添加混响..."), None, None, None, scheduler.queue_html
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
                        _update_task_name("full_pipeline", "混响失败")
                        yield _progress(step_idx, f"混响失败: {e}"), None, None, None, scheduler.queue_html
                step_idx += 1

            # ---- 完成 ----
            total_time = _elapsed()
            time_str = f"{total_time:.1f}s" if total_time < 60 else f"{total_time/60:.1f}min"
            done_html = _progress_html(100, "全部完成",
                                       f"输出目录: {os.path.abspath(out_dir)} · 耗时 {time_str}",
                                       elapsed=total_time, remaining=0)
            dl_html = build_download_html(final_output if (final_output and os.path.exists(final_output)) else None, "⬇️ 下载全流程成品", "purple")
            _lt.update(100, "✅ 全部完成")
            _update_task_name("full_pipeline", "完成: " + base_name)
            yield done_html, current_vocal, current_instr, final_output, dl_html, scheduler.queue_html
        except Exception as e:
            import traceback
            traceback.print_exc()
            if _lt:
                _lt.complete(success=False, error=str(e))
            _release_exec("full_pipeline")
            err_html = _progress_html(0, "处理出错", str(e), elapsed=_elapsed())
            yield err_html, current_vocal, current_instr, final_output, "", scheduler.queue_html
    finally:
        if _lt:
            _lt.complete(success=True)
        _release_exec("full_pipeline")


# ============================================
# 现代化界面构建
# ============================================

# 自定义主题配置（兼容旧版Gradio）- 支持自动深色模式
try:
    # 使用Soft主题作为基础，支持系统深色模式自动切换
    theme = gr.themes.Soft(
        font=['XiaChanYuanTi', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        font_mono=['SF Mono', 'Consolas', 'monospace'],
        primary_hue=gr.themes.colors.Violet,
        secondary_hue=gr.themes.colors.Purple,
        neutral_hue=gr.themes.colors.Slate,
        radius_size=gr.themes.radius_sizes.Large,
    ).set(
        # 通用设置 - 紫罗兰暮光主题
        body_background_fill="#f5f3ff",
        background_fill_primary="#ffffff",
        background_fill_secondary="#ede9fe",
        border_color_accent="#7c3aed",
        border_color_default="#ddd6fe",
        color_accent_soft="#ddd6fe",

        # 深色模式优化
        body_background_fill_dark="#1a0a2e",
        background_fill_primary_dark="#1e1538",
        background_fill_secondary_dark="#2d1b4e",
        border_color_accent_dark="#a78bfa",
        border_color_default_dark="#8b5cf6",
        color_accent_soft_dark="#c4b5fd",
    )
except AttributeError:
    # 旧版本Gradio不支持themes，使用默认主题
    theme = None



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
                    if not filename.endswith(".pth"):
                        filename += ".pth"
                elif hasattr(f, "orig_name") and f.orig_name:
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
                if not filename.endswith(".pth"):
                    filename += ".pth"
            elif hasattr(file_obj, "orig_name") and file_obj.orig_name:
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
SUPPORTED_AUDIO_EXTS = {
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".m4a",
    ".wma",
    ".aac",
    ".opus",
    ".webm",
    ".ape",
}

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

    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # 去除首尾空白和点号
    name = name.strip(" .")
    return name if name else "unknown"


import uuid
import time as _time_module
import json as _json_module
import re as _re


# ==================== 文件命名规则系统 ====================

_FILENAME_RULES = {
    "model_song": {
        "label": "[模型] + [歌曲名]",
        "desc": "简洁格式，适合快速识别",
        "template": "{model}_{song}",
        "example": "xiaojiu_声声慢.wav",
    },
    "model_artist_song": {
        "label": "[模型] + [歌手] - [歌曲名]",
        "desc": "完整信息，适合归档管理",
        "template": "{model}_{artist} - {song}",
        "example": "xiaojiu_周杰伦 - 声声慢.wav",
    },
    "aic_cover": {
        "label": "[AI翻唱专用] 模型前5字+歌曲",
        "desc": "AI翻唱专用格式：模型前5字+歌曲名，无分隔符",
        "template": "{model5}{song}",
        "example": "xiaoj夜曲.wav",
    },
}

_FILENAME_PREFS_PATH = os.path.join(now_dir, "tabs", "cache", "filename_prefs.json")

_filename_prefs_cache = {"rule_id": "aic_cover"}


def _sanitize_filename(name: str) -> str:
    """过滤文件系统不兼容的特殊字符，确保跨平台安全"""
    if not name:
        return ""
    name = _re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name))
    name = _re.sub(r'\s+', " ", name).strip(" ._-")
    return name[:200] if len(name) > 200 else name


def _extract_artist_from_filename(filename: str) -> str:
    """从文件名提取歌手名

    支持格式：
    - "歌手名 - 歌曲名.ext"
    - "歌手名 - 歌曲名 (备注).ext"
    - "歌曲名 - 歌手名.ext"
    - "歌手名_歌曲名.ext"

    注意：会过滤掉纯哈希值、临时文件等无效名称

    Returns:
        提取的歌手名，如果无法提取则返回空字符串
    """
    if not filename:
        return ""
    name = os.path.splitext(os.path.basename(filename))[0]
    if len(name) > 30 and name.startswith("tmp"):
        return ""
    if _re.match(r'^[a-f0-9]{8,}$', name, _re.IGNORECASE):
        return ""
    if len(name) > 20 and _re.search(r'[a-f0-9]{8,}', name, _re.IGNORECASE):
        return ""
    hash_pattern = r'[a-fA-F0-9]{8,}[_~-]*$'
    name = _re.sub(hash_pattern, "", name)
    name = _re.sub(r'[_-~]+$', "", name).strip(" -_~")
    if not name or len(name) < 2:
        return ""
    patterns = [
        r'^(.+?)\s*[-–—_]\s*(.+?)(?:\s*[\(（].*[\)）])?$',
        r'^(.+?)\s*[-–—_]\s*(.+?)\s*$',
    ]
    for pattern in patterns:
        m = _re.match(pattern, name)
        if m:
            part1, part2 = m.group(1).strip(), m.group(2).strip()
            if len(part1) >= 2 and len(part1) <= 20 and not _re.match(r'^[a-f0-9]+$', part1, _re.IGNORECASE):
                return part1
            if len(part2) >= 2 and len(part2) <= 20 and not _re.match(r'^[a-f0-9]+$', part2, _re.IGNORECASE):
                return part2
    if len(name) >= 2 and len(name) <= 20 and not _re.match(r'^[a-f0-9]+$', name, _re.IGNORECASE):
        return name
    return ""


def _truncate_smart(base_name: str, ext: str, max_total: int = 255) -> str:
    """智能截断文件名，优先保留关键信息，总长度不超过max_total"""
    if not ext.startswith("."):
        ext = "." + ext
    max_base = max_total - len(ext)
    if len(base_name) <= max_base:
        return base_name + ext
    truncated = base_name[:max_base].rstrip("_ .-")
    return truncated + ext


def _resolve_duplicate_path(target_path: str) -> str:
    """处理重名文件：自动添加序号避免覆盖"""
    if not os.path.exists(target_path):
        return target_path
    base_dir = os.path.dirname(target_path)
    base_name_ext = os.path.basename(target_path)
    base_name, ext = os.path.splitext(base_name_ext)
    counter = 1
    while True:
        new_name = f"{base_name}({counter}){ext}"
        new_path = os.path.join(base_dir, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1
        if counter > 9999:
            import time as _t
            ts = int(_t.time() * 1000)
            return os.path.join(base_dir, f"{base_name}_{ts}{ext}")


def get_filename_rules():
    """获取所有可用的命名规则预设"""
    return dict(_FILENAME_RULES)


def get_active_rule_id() -> str:
    """获取当前激活的命名规则ID"""
    global _filename_prefs_cache
    if isinstance(_filename_prefs_cache, dict):
        return _filename_prefs_cache.get("rule_id", "model_song")
    return "model_song"


def set_active_rule_id(rule_id: str):
    """设置当前激活的命名规则并持久化"""
    global _filename_prefs_cache
    if rule_id not in _FILENAME_RULES:
        rule_id = "model_song"
    _filename_prefs_cache["rule_id"] = rule_id
    try:
        os.makedirs(os.path.dirname(_FILENAME_PREFS_PATH), exist_ok=True)
        with open(_FILENAME_PREFS_PATH, "w", encoding="utf-8") as f:
            _json_module.dump(_filename_prefs_cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_filename_prefs():
    """从磁盘加载用户命名偏好"""
    global _filename_prefs_cache
    try:
        if os.path.exists(_FILENAME_PREFS_PATH):
            with open(_FILENAME_PREFS_PATH, "r", encoding="utf-8") as f:
                data = _json_module.load(f)
                if isinstance(data, dict):
                    _filename_prefs_cache.update(data)
                    print_status(
                        f"📝 已加载文件命名偏好: {_filename_prefs_cache.get('rule_id', '默认')}",
                        "info",
                    )
    except Exception:
        pass


def generate_filename(
    model_name: str = "",
    song_name: str = "",
    file_type: str = "",
    ext: str = ".wav",
    artist_name: str = "",
    rule_id: str = None,
    target_dir: str = None,
) -> str:
    """基于用户选择的命名规则生成文件名（含特殊字符处理+长度控制+去重）

    Args:
        model_name: 模型名称
        song_name: 歌曲名称
        file_type: 文件类型标签（成品/干声/伴奏等）
        ext: 扩展名
        artist_name: 歌手名（可选）
        rule_id: 命名规则ID，None则使用用户偏好
        target_dir: 目标目录（用于去重检测），None则不做去重检测

    Returns:
        完整的安全文件名或完整路径（如果提供了target_dir）
    """
    if rule_id is None:
        rule_id = get_active_rule_id()
    if rule_id not in _FILENAME_RULES:
        rule_id = "model_song"

    model_label = safe_model_name(model_name) if model_name else ""
    model5_label = model_label[:5] if model_label else ""
    model6_label = model_label[:6] if model_label else ""
    safe_song = _sanitize_filename(song_name) if song_name else ""
    safe_artist = _sanitize_filename(artist_name) if artist_name else ""
    safe_type = _sanitize_filename(file_type) if file_type else ""

    template = _FILENAME_RULES[rule_id]["template"]
    base_name = template.format(
        model=model_label or "unknown",
        model5=model5_label or "",
        model6=model6_label or "",
        song=safe_song or "未知歌曲",
        artist=safe_artist or "",
    ).strip("_ ")
    if safe_type and safe_type not in base_name:
        if rule_id == "aic_cover" and file_type in ("成品",):
            pass
        else:
            base_name = f"{safe_type}_{base_name}"

    final_name = _truncate_smart(base_name, ext)

    if target_dir:
        full_path = os.path.join(target_dir, final_name)
        full_path = _resolve_duplicate_path(full_path)
        return full_path

    return final_name


load_filename_prefs()


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
        safe_song = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', "_", song_name)
        safe_song = safe_song.strip("_")
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
        base_name = base_name[:max_length].rstrip("_")

    if not ext.startswith("."):
        ext = "." + ext

    result = f"{base_name}{ext}"

    print_status(f"📝 生成下载文件名: {result}", "download")
    print_status(
        f"   └─ 模型: {model_label} | 歌曲: {safe_song or '(未指定)'} | 类型: {suffix}",
        "download",
    )

    return result


def generate_save_filename(
    model_name: str = "",
    song_name: str = "",
    file_type: str = "成品",
    ext: str = ".wav",
    artist_name: str = "",
) -> str:
    """生成统一规范的保存文件名，所有模块共用。

    命名规则: {类型}_{模型前5位}_{纯净歌曲名}.{扩展名}
    示例: 伴奏_h1h1h_是你没选我啊 烟嗓版.wav
          干声_0cp1z_声声慢.wav
          成品_xiaoj_夜曲 混响版.wav

    AI翻唱专用规则（当 rule_id=aic_cover）: {模型前5字}{歌曲}.{扩展名}
    示例: xiaoj夜曲.wav

    Args:
        model_name: 模型文件名（取前5位）
        song_name: 歌曲或音频原始名称（自动去除歌手名、hash后缀等噪音）
        file_type: 文件类型标识，如"成品"、"干声"、"伴奏"
        ext: 文件扩展名
        artist_name: 歌手名（用于AI翻唱专用命名规则）

    Returns:
        安全的保存文件名字符串
    """
    rule_id = get_active_rule_id()
    if rule_id == "aic_cover" and file_type in ("成品",):
        result = generate_filename(
            model_name=model_name,
            song_name=song_name,
            file_type=file_type,
            ext=ext,
            artist_name=artist_name,
            rule_id="aic_cover",
        )
        return result

    import re

    model_prefix = ""
    if model_name:
        _mname = os.path.basename(model_name)
        _raw_model = re.sub(r"\.pth$", "", _mname, flags=re.IGNORECASE).strip()
        if _raw_model:
            model_prefix = safe_model_name(_raw_model)[:5]

    safe_song = ""
    if song_name:
        _raw = os.path.splitext(os.path.basename(song_name))[0]
        _raw = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", _raw)
        _raw = re.sub(r"[a-fA-F0-9]{16,}$", "", _raw)
        _raw = re.sub(r"^[a-fA-F0-9]{8,}_", "", _raw)
        _raw = re.sub(
            r"[\s_(]*[-–—_\s(]*(?:伴奏|干声|去混响|变调|转换|成品|混响|Clean|Vocals|Instrumental)[\s)]*$",
            "",
            _raw,
            flags=re.IGNORECASE,
        )
        _raw = re.sub(r"\s+", " ", _raw).strip(" .-_")
        if _raw and len(_raw) > 1:
            safe_song = _raw

    safe_type = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", file_type).strip()

    parts = []
    if safe_type:
        parts.append(safe_type)
    if model_prefix:
        parts.append(model_prefix)
    if safe_song:
        parts.append(safe_song)

    base_name = "_".join(parts) if parts else "output"

    if not ext.startswith("."):
        ext = "." + ext

    result = f"{base_name}{ext}"
    _is_intermediate = file_type in ("干声", "去混响干声", "伴奏", "变调后", "混音后")
    if not _is_intermediate:
        print_status(f"📝 生成保存文件名: {result}", "save")
    return result


_SEP_CACHE_ROOT = os.path.join(now_dir, "分离缓存")
_SEP_CACHE_LOG = os.path.join(_SEP_CACHE_ROOT, "cache_log.json")


def _compute_audio_hash(audio_path: str) -> str:
    """计算音频文件的唯一哈希值（基于文件大小+前中后部分采样）"""
    import hashlib
    try:
        fsize = os.path.getsize(audio_path)
        hash_parts = [str(fsize)]
        with open(audio_path, "rb") as f:
            f.seek(0)
            header = f.read(8192)
            hash_parts.append(hashlib.md5(header).hexdigest()[:8])
            f.seek(max(0, fsize // 2 - 4096))
            middle = f.read(8192)
            hash_parts.append(hashlib.md5(middle).hexdigest()[:8])
            f.seek(max(0, fsize - 8192))
            tail = f.read(8192)
            hash_parts.append(hashlib.md5(tail).hexdigest()[:8])
        return hashlib.md5("_".join(hash_parts).encode()).hexdigest()[:16]
    except Exception:
        import time
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:16]


def _get_audio_duration(audio_path: str) -> float:
    """获取音频文件时长（秒）"""
    try:
        import soundfile as _sf
        info = _sf.info(audio_path)
        return float(info.frames) / float(info.samplerate)
    except Exception:
        try:
            import librosa as _librosa
            dur = _librosa.get_duration(path=audio_path)
            return dur
        except Exception:
            return 0.0


def _load_sep_cache_log() -> dict:
    """加载分离缓存日志"""
    try:
        if os.path.exists(_SEP_CACHE_LOG):
            with open(_SEP_CACHE_LOG, "r", encoding="utf-8") as f:
                return _json_module.load(f)
    except Exception:
        pass
    return {"entries": []}


def _save_sep_cache_log(log_data: dict):
    """保存分离缓存日志"""
    try:
        os.makedirs(_SEP_CACHE_ROOT, exist_ok=True)
        with open(_SEP_CACHE_LOG, "w", encoding="utf-8") as f:
            _json_module.dump(log_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _log_sep_cache(audio_hash: str, audio_path: str, duration: float, vocal_path: str, instr_path: str):
    """记录分离缓存到日志"""
    import time as _t
    log_data = _load_sep_cache_log()
    _artist, _song = extract_artist_song_from_filename(os.path.basename(audio_path))
    entry = {
        "hash": audio_hash,
        "original": audio_path,
        "original_name": os.path.basename(audio_path),
        "duration": round(duration, 2),
        "vocal": vocal_path,
        "instr": instr_path,
        "artist": _artist,
        "song": _song,
        "timestamp": _t.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "completed",
    }
    log_data["entries"].append(entry)
    _save_sep_cache_log(log_data)


def find_sep_cache(audio_path: str) -> dict:
    """根据音频路径查找分离缓存

    Returns:
        dict: {"found": bool, "vocal": str or None, "instr": str or None, "reason": str}
    """
    result = {"found": False, "vocal": None, "instr": None, "reason": ""}

    if not os.path.exists(audio_path):
        result["reason"] = "文件不存在"
        return result

    audio_hash = _compute_audio_hash(audio_path)
    duration = _get_audio_duration(audio_path)
    duration_rounded = round(duration, 2)

    log_data = _load_sep_cache_log()
    for entry in reversed(log_data.get("entries", [])):
        if entry.get("hash") == audio_hash:
            cached_duration = entry.get("duration", 0)
            if abs(cached_duration - duration_rounded) < 1.0:
                vocal_path = entry.get("vocal")
                instr_path = entry.get("instr")
                if vocal_path and os.path.exists(vocal_path):
                    result["found"] = True
                    result["vocal"] = vocal_path
                    result["instr"] = instr_path if instr_path and os.path.exists(instr_path) else None
                    result["reason"] = f"缓存命中 (hash={audio_hash}, duration={duration_rounded}s)"
                    return result
                else:
                    result["reason"] = "缓存记录存在但文件已删除"
            else:
                result["reason"] = f"时长不匹配 (期望:{duration_rounded}s, 缓存:{cached_duration}s)"
        else:
            continue

    result["reason"] = f"无缓存 (hash={audio_hash}, duration={duration_rounded}s)"
    return result


def save_sep_cache(audio_path: str, vocal_path: str, instr_path: str):
    """保存分离结果到缓存目录并记录日志"""
    if not os.path.exists(vocal_path):
        return

    os.makedirs(_SEP_CACHE_ROOT, exist_ok=True)

    audio_hash = _compute_audio_hash(audio_path)
    duration = _get_audio_duration(audio_path)

    _, ext = os.path.splitext(vocal_path)
    cached_vocal = os.path.join(_SEP_CACHE_ROOT, f"{audio_hash}_vocal{ext}")
    cached_instr = None

    import shutil as _shutil
    _shutil.copy2(vocal_path, cached_vocal)

    if instr_path and os.path.exists(instr_path):
        _, instr_ext = os.path.splitext(instr_path)
        cached_instr = os.path.join(_SEP_CACHE_ROOT, f"{audio_hash}_instr{instr_ext}")
        _shutil.copy2(instr_path, cached_instr)

    _log_sep_cache(audio_hash, audio_path, duration, cached_vocal, cached_instr)
    print_status(f"💾 分离缓存已保存: {audio_hash}", "save")


def _separate_with_vocal_separator(audio_path: str, output_dir: str) -> dict:
    """Fast Apple Silicon separation via the external demucs-mlx helper."""
    result = {"success": False, "vocal": None, "instr": None, "reason": ""}
    helper_dir = "/Users/liubin/Documents/github_pro/vocal-separator"
    helper_py = os.path.join(helper_dir, "separate.py")
    helper_python = os.path.join(helper_dir, ".venv", "bin", "python")

    if not os.path.exists(helper_py) or not os.path.exists(helper_python):
        result["reason"] = "vocal-separator 工具不存在"
        return result

    os.makedirs(output_dir, exist_ok=True)
    try:
        import subprocess

        env = os.environ.copy()
        for key in ("ALL_PROXY", "all_proxy"):
            env.pop(key, None)
        env["NO_PROXY"] = "127.0.0.1,localhost,::1"
        env["no_proxy"] = env["NO_PROXY"]

        mode = os.environ.get("RVC_DEMUCS_MLX_MODE", "precise").strip().lower()
        precise = mode not in {"fast", "quick", "0", "false"}
        cmd = [helper_python, helper_py, os.path.abspath(audio_path), "-o", os.path.abspath(output_dir)]
        if precise:
            cmd.append("--precise")
        print_status(
            "⚡ 使用 demucs-mlx {}分离（MLX + Metal GPU）".format("精细" if precise else "快速"),
            "sep",
        )
        proc = subprocess.run(
            cmd,
            cwd=helper_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
        )
        if proc.returncode != 0:
            result["reason"] = (proc.stderr or proc.stdout)[-500:]
            return result

        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        vocal_path = os.path.join(output_dir, f"{base_name}_人声.wav")
        instr_path = os.path.join(output_dir, f"{base_name}_伴奏.wav")
        if os.path.exists(vocal_path):
            result["vocal"] = vocal_path
        if os.path.exists(instr_path):
            result["instr"] = instr_path
        result["success"] = bool(result["vocal"])
        if not result["success"]:
            result["reason"] = "demucs-mlx 未生成 vocals 文件"
        return result
    except Exception as e:
        result["reason"] = str(e)
        return result


def separate_audio_for_cover(audio_path, do_deverb=True):
    """统一的音频分离接口，供AI翻唱模块调用。

    执行流程:
    1. 检查缓存 (hash + 歌名双重查找)
    2. 链式分离 (kim_vocal + deverb + karaoke)
    3. fallback: mel_band_roformer 单模型分离
    4. 独立去混响 (bs_roformer, 仅当链式未含deverb时)
    5. 保存缓存 (去混响干声 + 伴奏)

    Args:
        audio_path: 原始音频文件路径
        do_deverb: 是否执行去混响 (默认True)

    Returns:
        dict: {
            "success": bool,
            "vocal": str or None,   # 去混响干声路径
            "instr": str or None,   # 伴奏路径
            "raw_vocal": str or None,  # 原始干声路径(未去混响)
            "reason": str,
            "from_cache": bool,
        }
    """
    result = {
        "success": False,
        "vocal": None,
        "instr": None,
        "raw_vocal": None,
        "reason": "",
        "from_cache": False,
    }

    if not audio_path or not os.path.exists(audio_path):
        result["reason"] = "音频文件不存在"
        return result

    base_name = os.path.splitext(os.path.basename(audio_path))[0]

    # 缓存检查已禁用，允许重复分离
    # cache_result = find_sep_cache(audio_path)
    # if not cache_result["found"]:
    #     _artist_cache, _song_cache = extract_artist_song_from_filename(base_name)
    #     if _artist_cache and _song_cache:
    #         song_cache_result = find_sep_cache_by_song(_artist_cache, _song_cache)
    #         if song_cache_result["found"]:
    #             cache_result = song_cache_result
    #
    # if cache_result["found"]:
    #     result["vocal"] = cache_result["vocal"]
    #     result["instr"] = cache_result["instr"]
    #     result["raw_vocal"] = cache_result["vocal"]
    #     result["success"] = True
    #     result["reason"] = f"缓存命中 ({cache_result['reason']})"
    #     result["from_cache"] = True
    #     return result

    os.makedirs(_SEP_CACHE_ROOT, exist_ok=True)
    sep_out = os.path.join(_SEP_CACHE_ROOT, f"{base_name}_sep")
    clean_vocal_path = None
    instr_path = None
    raw_vocal_path = None

    fast_sep_out = os.path.join(_SEP_CACHE_ROOT, f"{base_name}_demucs_mlx")
    fast_sep = _separate_with_vocal_separator(audio_path, fast_sep_out)
    if fast_sep["success"]:
        raw_vocal_path = fast_sep["vocal"]
        clean_vocal_path = fast_sep["vocal"]
        instr_path = fast_sep["instr"]
        save_sep_cache(audio_path, clean_vocal_path, instr_path)
        result["vocal"] = clean_vocal_path
        result["instr"] = instr_path
        result["raw_vocal"] = raw_vocal_path
        result["success"] = True
        result["reason"] = "demucs-mlx 分离完成"
        result["from_cache"] = False
        return result
    else:
        print_status(f"⚠️ demucs-mlx 快速分离不可用，回退内置分离: {fast_sep['reason']}", "warning")

    chain_stages = ["kim_vocal", "karaoke"]
    deverb_model_path = os.path.join(
        os.getcwd(),
        "audio_tools",
        "models",
        "separator",
        "deverb_bs_roformer_8_256dim_8depth.ckpt",
    )
    if do_deverb and os.path.exists(deverb_model_path):
        chain_stages.insert(1, "deverb")
    chain_has_deverb = False

    try:
        chained = create_chained_separator(stages=chain_stages)
        if len(chained._loaded_stages) >= 1:
            sep_result = chained.separate(
                audio_path, sep_out,
                use_kim_vocal=True,
                use_deverb=do_deverb,
                use_karaoke=True,
            )
            chained.unload_all()
            del chained
            if sep_result and sep_result.vocals and os.path.exists(sep_result.vocals):
                raw_vocal_path = sep_result.vocals
                clean_vocal_path = sep_result.vocals
                if do_deverb and "deverb" in chain_stages:
                    chain_has_deverb = True
            if sep_result and sep_result.other and os.path.exists(sep_result.other):
                instr_path = sep_result.other
    except Exception as e:
        print_status(f"⚠️ 链式分离失败: {e}", "warning")

    if not clean_vocal_path or not os.path.exists(clean_vocal_path):
        try:
            from audio_tools.separator_model import SeparatorModel
            sep = SeparatorModel(model_type="mel_band_roformer")
            if sep.load():
                sep_result = sep.separate(audio_path, sep_out, instruments=["vocals", "other"])
                if sep_result and sep_result.vocals and os.path.exists(sep_result.vocals):
                    raw_vocal_path = sep_result.vocals
                    clean_vocal_path = sep_result.vocals
                if sep_result and sep_result.other and os.path.exists(sep_result.other):
                    instr_path = sep_result.other
                del sep
        except Exception as e:
            print_status(f"⚠️ 单模型分离失败: {e}", "warning")

    if not clean_vocal_path or not os.path.exists(clean_vocal_path):
        result["reason"] = "所有分离方法均失败"
        return result

    _artist, _song = extract_artist_song_from_filename(base_name)
    if not _artist or not _song:
        _artist = ""
        _song = base_name

    if instr_path and os.path.exists(instr_path):
        import shutil as _shutil
        instr_filename = generate_save_filename(_artist, _song, "伴奏")
        saved_instr = os.path.join(_SEP_CACHE_ROOT, instr_filename)
        try:
            _shutil.copy2(instr_path, saved_instr)
            instr_path = saved_instr
        except Exception as e:
            print_status(f"⚠️ 保存伴奏失败: {e}", "warning")

    if do_deverb and not chain_has_deverb and clean_vocal_path and os.path.exists(clean_vocal_path) and os.path.exists(deverb_model_path):
        try:
            from audio_tools.separator_model import SeparatorModel
            dereverb_sep = SeparatorModel(model_type="bs_roformer")
            if dereverb_sep.load():
                dereverb_out = os.path.join(_SEP_CACHE_ROOT, f"{base_name}_dereverb")
                d_result = dereverb_sep.separate(
                    clean_vocal_path, dereverb_out,
                    instruments=["vocals", "other"],
                )
                if d_result and d_result.vocals and os.path.exists(d_result.vocals):
                    dereverb_filename = generate_save_filename(_artist, _song, "去混响干声")
                    dereverb_vocal_path = os.path.join(_SEP_CACHE_ROOT, dereverb_filename)
                    _shutil.copy2(d_result.vocals, dereverb_vocal_path)
                    clean_vocal_path = dereverb_vocal_path
                del dereverb_sep
        except Exception as e:
            print_status(f"⚠️ 独立去混响失败: {e}", "warning")

    if clean_vocal_path and os.path.exists(clean_vocal_path):
        save_sep_cache(audio_path, clean_vocal_path, instr_path)

    result["vocal"] = clean_vocal_path
    result["instr"] = instr_path
    result["raw_vocal"] = raw_vocal_path
    result["success"] = True
    result["reason"] = "分离完成"
    return result


_AI_OUTPUT_ROOT = os.path.join(now_dir, "AI翻唱作品")

_OUTPUT_CATEGORIES = {
    "cover": "",
    "pipeline": "",
    "batch": "批量转换",
    "intermediate": "",
    "raw_source": "",
}

_SUBDIR_MAP = {
    "cover": {},
    "pipeline": {},
    "batch": {},
    "intermediate": {},
    "raw_source": {},
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


def get_sub_output_dir(
    category: str, sub_type: str, model_name: str = "", create: bool = True
) -> str:
    base_dir = get_output_dir(category, model_name, create=create)
    sub_map = _SUBDIR_MAP.get(category, {})
    sub_label = sub_map.get(sub_type, sub_type)
    sub_path = os.path.join(base_dir, sub_label)
    if create:
        os.makedirs(sub_path, exist_ok=True)
        return sub_path


def find_existing_processed_files(model_name: str, song_name: str) -> dict:
    """在AI翻唱作品目录中查找已处理过的文件，优先复用。

    查找顺序（优先级从高到低）：
      1. 去混响干声 (已去混响的干净人声) ← 仅保留此类型
      2. 伴奏 (分离出的伴奏)

    注意：不再回退到纯干声文件，确保只使用去混响后的干净人声。

    Args:
        model_name: 模型文件名
        song_name: 歌曲名或音频路径

    Returns:
        dict with keys: "deverb_vocal", "vocal", "instr" (values are file paths or None)
    """
    result = {"deverb_vocal": None, "vocal": None, "instr": None}
    out_dir = get_output_dir("cover", model_name, create=False)
    if not out_dir or not os.path.isdir(out_dir):
        return result

    deverb_path = os.path.join(
        out_dir, generate_save_filename(model_name, song_name, "去混响干声")
    )
    instr_path = os.path.join(
        out_dir, generate_save_filename(model_name, song_name, "伴奏")
    )

    if os.path.exists(deverb_path):
        result["deverb_vocal"] = deverb_path
        result["vocal"] = deverb_path
    if os.path.exists(instr_path):
        result["instr"] = instr_path

    if any(result.values()):
        found_types = [k for k, v in result.items() if v]
        print_status(
            f"📦 发现已有处理文件 [{song_name}]: {', '.join(found_types)}", "info"
        )
    return result


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
        "green": (
            "linear-gradient(135deg, #059669, #10b981, #34d399)",
            "rgba(16, 185, 129, 0.4)",
        ),
        "orange": (
            "linear-gradient(135deg, #ea580c, #f97316, #fb923c)",
            "rgba(249, 115, 22, 0.45)",
        ),
        "blue": (
            "linear-gradient(135deg, #1d4ed8, #2563eb, #3b82f6)",
            "rgba(37, 99, 235, 0.4)",
        ),
        "purple": (
            "linear-gradient(135deg, #6d28d9, #7c3aed, #8b5cf6)",
            "rgba(124, 58, 237, 0.45)",
        ),
        "red": (
            "linear-gradient(135deg, #dc2626, #ef4444, #f87171)",
            "rgba(239, 68, 68, 0.4)",
        ),
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
            print_status(
                f"⚠️  文件在工作目录外，自动复制到AI成品库: {raw_name}", "warning"
            )
            import shutil as _shutil_dl
            import re as _re

            _cache_dir = os.path.join(_AI_OUTPUT_ROOT, "下载缓存")
            os.makedirs(_cache_dir, exist_ok=True)
            _safe_base = _re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw_name)
            _ext = os.path.splitext(_safe_base)[1] or ".wav"
            _safe_base = _re.sub(r"[a-fA-F0-9]{16,}$", "", _safe_base)
            _safe_base = _re.sub(r"\.[^.]*$", "", _safe_base)
            _safe_dl_name = f"{_safe_base}{_ext}" if _safe_base else f"download{_ext}"
            _safe_path = os.path.join(_cache_dir, _safe_dl_name)
            _shutil_dl.copy2(abs_path, _safe_path)
            abs_path = _safe_path.replace("\\", "/")
            raw_name = _safe_dl_name
            print_status(
                f"✅ 已复制到安全目录: {raw_name} ({file_size_mb:.1f}MB)", "success"
            )

        file_url = f"/file={abs_path}"
        print_status(f"📥 准备下载: {raw_name} ({file_size_mb:.1f}MB)", "download")
    except Exception as e:
        print_status(f"❌ 下载路径解析异常: {str(e)}", "error")
        return f"""<div style="margin-top: 8px; padding: 8px 12px; border-radius: 8px; background: rgba(239,68,68,0.1); border-left: 3px solid #ef4444;">
            <span style="color: #fca5a5; font-size: 0.8rem;">⚠️ 下载路径解析失败: {str(e)}</span>
        </div>"""

    return f"""<div style="margin-top: 8px;" id="dl-area-{abs_path[-8:]}">
        <a href="{file_url}" download="{raw_name}" id="dl-link-{abs_path[-8:]}" style="
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


# ============================================
# 音频格式转换工具（全局输出格式选择）
# ============================================

def save_audio_with_format(
    audio_data,
    sample_rate,
    output_path,
    output_format="wav",
):
    """根据指定格式保存音频文件，支持 wav / mp3 / flac。

    Args:
        audio_data: numpy 数组音频数据 (float32)
        sample_rate: 采样率 (如 44100, 48000)
        output_path: 输出文件完整路径（扩展名会自动修正为 output_format）
        output_format: 输出格式，可选 "wav"(默认) | "mp3" | "flac"

    Returns:
        实际保存的文件路径（扩展名已修正）
    """
    import soundfile as sf
    import subprocess

    output_format = output_format.lower().strip()
    if output_format not in ("wav", "mp3", "flac"):
        output_format = "wav"

    base, _ = os.path.splitext(output_path)
    final_path = f"{base}.{output_format}"

    wav_tmp_path = f"{base}._format_temp_.wav"

    try:
        sf.write(wav_tmp_path, audio_data, sample_rate)

        ffmpeg_exe = os.path.join(os.getcwd(), "ffmpeg.exe")
        if not os.path.exists(ffmpeg_exe):
            ffmpeg_exe = "ffmpeg"

        if output_format == "wav":
            if os.path.abspath(wav_tmp_path) != os.path.abspath(final_path):
                os.replace(wav_tmp_path, final_path)
            else:
                pass
        elif output_format == "mp3":
            cmd = [
                ffmpeg_exe, "-y", "-i", wav_tmp_path,
                "-acodec", "libmp3lame", "-ab", "320k",
                final_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            try:
                os.remove(wav_tmp_path)
            except OSError:
                pass
        elif output_format == "flac":
            cmd = [
                ffmpeg_exe, "-y", "-i", wav_tmp_path,
                "-acodec", "flac", "-compression_level", "5",
                final_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            try:
                os.remove(wav_tmp_path)
            except OSError:
                pass

        return final_path
    except Exception:
        if os.path.exists(wav_tmp_path):
            try:
                os.remove(wav_tmp_path)
            except OSError:
                pass
        raise


def convert_audio_format(src_path, output_format="wav"):
    """将已有音频文件转换为指定格式。

    Args:
        src_path: 源音频文件路径
        output_format: 目标格式 "wav" | "mp3" | "flac"（默认 wav）

    Returns:
        转换后的文件路径（同目录，扩展名替换）
    """
    import subprocess

    if not src_path or not os.path.exists(src_path):
        return src_path

    output_format = output_format.lower().strip()
    if output_format not in ("wav", "mp3", "flac"):
        output_format = "wav"

    base, _ = os.path.splitext(src_path)
    dst_path = f"{base}.{output_format}"

    if src_path.lower().endswith(f".{output_format}"):
        if os.path.exists(dst_path) and os.path.samefile(src_path, dst_path):
            return dst_path
        if src_path == dst_path:
            return dst_path

    if os.path.exists(dst_path):
        try:
            os.remove(dst_path)
        except OSError:
            pass

    ffmpeg_exe = os.path.join(os.getcwd(), "ffmpeg.exe")
    if not os.path.exists(ffmpeg_exe):
        ffmpeg_exe = "ffmpeg"

    codec_map = {
        "wav": ["-acodec", "pcm_s16le"],
        "mp3": ["-acodec", "libmp3lame", "-ab", "320k"],
        "flac": ["-acodec", "flac", "-compression_level", "5"],
    }
    codec_args = codec_map.get(output_format, codec_map["wav"])

    cmd = [ffmpeg_exe, "-y", "-i", src_path] + codec_args + [dst_path]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        if os.path.exists(dst_path):
            try:
                os.remove(src_path)
            except OSError:
                pass
            return dst_path
    except subprocess.CalledProcessError as e:
        print(f"[convert_audio_format] ffmpeg error: {e.stderr.decode('utf-8', errors='ignore')[:200]}")
    except subprocess.TimeoutExpired:
        print("[convert_audio_format] ffmpeg timeout")
    except Exception as e:
        print(f"[convert_audio_format] error: {e}")

    if output_format != "wav":
        try:
            import soundfile as _sf
            data, sr = _sf.read(src_path)
            _sf.write(dst_path, data, sr, format=output_format.upper())
            if os.path.exists(dst_path):
                try:
                    os.remove(src_path)
                except OSError:
                    pass
                return dst_path
        except Exception as _sf_err:
            print(f"[convert_audio_format] soundfile fallback error: {_sf_err}")

    return src_path


_FORMAT_CHOICES = ["wav", "mp3", "flac"]


def resolve_format(fmt_value, default="wav"):
    """将 Dropdown 返回的值统一解析为格式字符串 (wav/mp3/flac)。"""
    if not fmt_value:
        return default
    fmt_value = str(fmt_value).strip()
    if fmt_value in _FORMAT_CHOICES:
        return fmt_value
    return default


def _friendly_err(e):
    """将技术异常转换为用户友好的错误描述"""
    msg = str(e)
    msg_lower = msg.lower()
    if (
        "cuda" in msg_lower
        or "gpu" in msg_lower
        or "oom" in msg_lower
        or "out of memory" in msg_lower
    ):
        return "显卡显存不足，试试减少同时处理的模型数量"
    if "file not found" in msg_lower or "no such file" in msg_lower:
        return "找不到文件，请确认文件路径正确"
    if "permission" in msg_lower or "denied" in msg_lower or "access" in msg_lower:
        return "文件权限不足或被其他程序占用"
    if "timeout" in msg_lower:
        return "处理超时，文件可能过大，建议缩短音频后重试"
    if "index" in msg_lower and ("not found" in msg_lower or "missing" in msg_lower):
        return "模型索引文件缺失，请刷新模型列表后重试"
    if "valueerror" in msg_lower or "shape" in msg_lower:
        return "数据格式不匹配，可能是音频采样率不支持"
    if len(msg) > 80:
        return msg[:77] + "..."
    return msg


def _get_audio_info(filepath):
    """获取音频文件元数据：返回(时长秒数, 大小字节, 采样率)"""
    duration = 0
    sr = 0
    try:
        import soundfile as sf

        info = sf.info(filepath)
        duration = info.duration
        sr = info.samplerate
    except Exception:
        try:
            import wave

            with wave.open(filepath, "rb") as wf:
                sr = wf.getframerate()
                frames = wf.getnframes()
                duration = frames / float(sr) if sr > 0 else 0
        except Exception:
            pass
    try:
        fsize = os.path.getsize(filepath)
    except OSError:
        fsize = 0
    return duration, fsize, sr


def _fmt_duration(seconds):
    """格式化时长为 mm:ss 或 hh:mm:ss"""
    if seconds <= 0:
        return "--:--"
    if seconds < 3600:
        m = int(seconds) // 60
        s = int(seconds) % 60
        return str(m).zfill(2) + ":" + str(s).zfill(2)
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return str(h) + ":" + str(m).zfill(2) + ":" + str(s).zfill(2)


def extract_artist_song_from_filename(filename: str) -> tuple:
    """从文件名中提取歌手名和歌曲名

    支持格式：
    - "歌手 - 歌曲名" (标准格式)
    - "歌手-歌曲名" (无空格)
    - "歌手_歌曲名" (下划线分隔)
    - "歌手 歌曲" (空格分隔)

    Args:
        filename: 文件名（不含路径）

    Returns:
        (artist_name, song_name): 歌手名和歌曲名的元组，如果无法识别则返回 ("", 原始文件名)
    """
    import re
    name = os.path.splitext(os.path.basename(filename))[0]
    name = name.strip()
    separators = [" - ", "-", "_", "  ", " "]
    for sep in separators:
        if sep in name and len(sep) > 1 or (sep in name and name.count(sep) == 1):
            parts = name.split(sep, 1)
            if len(parts) == 2:
                artist = parts[0].strip()
                song = parts[1].strip()
                if artist and song and len(artist) < 30 and len(song) > 1:
                    return artist, song
    return "", name


def find_sep_cache_by_song(artist: str, song: str) -> dict:
    """根据歌手和歌曲名查找分离缓存

    Returns:
        dict: {"found": bool, "vocal": str or None, "instr": str or None, "reason": str}
    """
    result = {"found": False, "vocal": None, "instr": None, "reason": ""}
    if not artist or not song:
        result["reason"] = "缺少歌手或歌曲信息"
        return result
    log_data = _load_sep_cache_log()
    for entry in reversed(log_data.get("entries", [])):
        entry_vocal = entry.get("vocal", "") or ""
        entry_instr = entry.get("instr", "") or ""
        vocal_basename = os.path.basename(entry_vocal)
        instr_basename = os.path.basename(entry_instr)
        target_vocal_pattern = f"{artist} - {song} dereverb vocals"
        target_instr_pattern = f"{artist} - {song} Instrumental"
        if target_vocal_pattern.lower() in vocal_basename.lower() or (
            target_instr_pattern.lower() in instr_basename.lower()
            and entry_vocal
            and os.path.exists(entry_vocal)
        ):
            result["found"] = True
            result["vocal"] = entry_vocal if entry_vocal and os.path.exists(entry_vocal) else None
            result["instr"] = entry_instr if entry_instr and os.path.exists(entry_instr) else None
            result["reason"] = f"缓存命中 (歌曲: {artist} - {song})"
            return result
    result["reason"] = f"无缓存 (歌曲: {artist} - {song})"
    return result


def _fmt_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return str(size_bytes) + "B"
    elif size_bytes < 1024 * 1024:
        return str(round(size_bytes / 1024, 1)) + "KB"
    else:
        return str(round(size_bytes / 1024 / 1024, 1)) + "MB"


def scan_folder_for_audio(folder_path: str, recursive: bool = True, keyword_filter: str = "") -> dict:
    """递归扫描文件夹中的所有音频文件

    Args:
        folder_path: 目标文件夹路径
        recursive: 是否递归扫描子目录
        keyword_filter: 关键词过滤（如"vo/干声/dry"），只返回包含关键词的文件

    Returns:
        dict: {
            "success": bool,
            "files": list[str],  # 文件路径列表
            "total_count": int,
            "total_size": int,
            "keyword_count": int,
            "message": str,
            "scan_time": float
        }
    """
    import time as _t
    _start = _t.time()
    result = {
        "success": False,
        "files": [],
        "total_count": 0,
        "total_size": 0,
        "keyword_count": 0,
        "message": "",
        "scan_time": 0,
    }

    if not folder_path or not os.path.isdir(folder_path):
        result["message"] = "❌ 目录不存在或无效"
        return result

    audio_files = []
    keyword_files = []

    _keywords = [k.strip().lower() for k in keyword_filter.split(",") if k.strip()] if keyword_filter else []

    try:
        if recursive:
            _walk_iter = os.walk(folder_path)
        else:
            _walk_iter = [(folder_path, [], os.listdir(folder_path))]

        for root, dirs, files in _walk_iter:
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SUPPORTED_AUDIO_EXTS:
                    continue
                fpath = os.path.join(root, fname)
                fname_lower = fname.lower()
                is_keyword_file = False
                if _keywords:
                    for kw in _keywords:
                        if kw in fname_lower:
                            is_keyword_file = True
                            break
                if is_keyword_file:
                    keyword_files.append(fpath)
                elif not _keywords:
                    audio_files.append(fpath)

        if keyword_files:
            result["files"] = keyword_files
            result["keyword_count"] = len(keyword_files)
        else:
            result["files"] = audio_files

        result["total_count"] = len(result["files"])
        for fp in result["files"]:
            try:
                result["total_size"] += os.path.getsize(fp)
            except OSError:
                pass

        result["success"] = True
        if result["total_count"] > 0:
            result["message"] = f"✅ 扫描完成：找到 {result['total_count']} 个音频文件"
            if keyword_files:
                result["message"] += f"（含 {len(keyword_files)} 个关键词匹配）"
            result["message"] += f"，总大小 {_fmt_file_size(result['total_size'])}"
        else:
            result["message"] = "⚠️ 未找到音频文件"

    except Exception as e:
        result["message"] = f"❌ 扫描失败: {str(e)}"

    result["scan_time"] = round(_t.time() - _start, 2)
    return result


def build_batch_progress_html(current_file: str, current_index: int, total: int, success_count: int, fail_count: int, elapsed: float = 0) -> str:
    """构建批量转换进度HTML

    Args:
        current_file: 当前处理的文件名
        current_index: 当前索引（从1开始）
        total: 总数
        success_count: 成功数量
        fail_count: 失败数量
        elapsed: 已用时间（秒）

    Returns:
        HTML字符串
    """
    pct = int((current_index / max(total, 1)) * 100)
    remaining = (elapsed / max(current_index, 1)) * (total - current_index) if current_index > 0 else 0
    remaining_str = f"{int(remaining // 60)}分{int(remaining % 60)}秒" if remaining > 60 else f"{int(remaining)}秒"

    html = f'''
    <div style="padding:12px;border-radius:10px;background:linear-gradient(135deg,rgba(59,130,246,0.08),rgba(96,165,250,0.04));border:1px solid rgba(59,130,246,0.2);">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="font-size:0.78rem;color:#3b82f6;font-weight:600;">📦 批量转换进度</span>
            <span style="font-size:0.74rem;color:#6b7280;">{current_index}/{total} ({pct}%)</span>
        </div>
        <div style="width:100%;height:8px;background:rgba(59,130,246,0.1);border-radius:4px;overflow:hidden;margin-bottom:8px;">
            <div style="width:{pct}%;height:100%;background:linear-gradient(90deg,#3b82f6,#60a5fa);border-radius:4px;transition:width 0.3s;"></div>
        </div>
        <div style="font-size:0.72rem;color:#374151;">
            🎵 当前：<b>{_html_escape(current_file)}</b><br>
            ✅ 成功: {success_count} | ❌ 失败: {fail_count}<br>
            ⏱ 已用时: {int(elapsed // 60)}分{int(elapsed % 60)}秒 | 预计剩余: {remaining_str}
        </div>
    </div>'''
    return html


def build_batch_result_html(total: int, success: int, failed: int, errors: list, output_dir: str = "") -> str:
    """构建批量转换结果报告HTML

    Args:
        total: 总数
        success: 成功数
        failed: 失败数
        errors: 错误列表 [{"file": str, "error": str}]
        output_dir: 输出目录

    Returns:
        HTML字符串
    """
    error_html = ""
    if errors:
        error_items = "".join([
            f'<li style="margin:3px 0;font-size:0.7rem;color:#dc2626;">{_html_escape(e.get("file", ""))}: {_html_escape(str(e.get("error", "")))[:80]}</li>'
            for e in errors[:20]
        ])
        more_text = f"<br><span style='color:#9ca3af;'>...还有 {len(errors)-20} 条错误</span>" if len(errors) > 20 else ""
        error_html = f'<details open><summary style="cursor:pointer;font-size:0.74rem;color:#ef4444;font-weight:600;margin:6px 0;">❌ 失败详情 ({len(errors)})</summary><ul style="padding-left:16px;margin:4px 0;">{error_items}{more_text}</ul></details>'

    status_color = "#10b981" if failed == 0 else ("#f59e0b" if success > 0 else "#ef4444")
    status_text = "全部成功" if failed == 0 else ("部分失败" if success > 0 else "全部失败")

    _output_dir_html = ""
    if output_dir:
        _output_dir_html = "<div style='font-size:0.7rem;color:#6b7280;margin-top:6px;'>📂 输出目录: " + _html_escape(output_dir) + "</div>"

    html = (
        '<div style="padding:14px;border-radius:10px;background:linear-gradient(135deg,'
        + status_color
        + '08,'
        + status_color
        + '04);border:1px solid '
        + status_color
        + '30;">'
        + '<div style="font-size:0.85rem;color:'
        + status_color
        + ';font-weight:700;margin-bottom:8px;">📊 批量转换完成 - '
        + status_text
        + '</div>'
        + '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px;">'
        + '<span style="font-size:0.76rem;padding:4px 10px;background:rgba(16,185,129,0.1);color:#059669;border-radius:6px;">✅ 成功: '
        + str(success)
        + '</span>'
        + '<span style="font-size:0.76rem;padding:4px 10px;background:rgba(239,68,68,0.1);color:#dc2626;border-radius:6px;">❌ 失败: '
        + str(failed)
        + '</span>'
        + '<span style="font-size:0.76rem;padding:4px 10px;background:rgba(107,114,128,0.1);color:#4b5563;border-radius:6px;">📁 总计: '
        + str(total)
        + '</span></div>'
        + error_html
        + _output_dir_html
        + "</div>"
    )
    return html


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
        return (
            False,
            f"⚠️ 不支持 {ext_upper:= ext_lower.upper()} 格式: {UNSUPPORTED_FORMATS[ext_lower]}",
            ext_lower,
        )

    # 检查文件大小
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, f"⚠️ 文件为空: {filename}", ext_lower
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / 1024 / 1024
            return (
                False,
                f"⚠️ 文件过大 ({size_mb:.1f}MB)，上限 {MAX_FILE_SIZE // 1024 // 1024}MB: {filename}",
                ext_lower,
            )
    except OSError as e:
        return False, f"⚠️ 无法读取文件: {filename} ({e})", ext_lower

    # 检查扩展名是否在支持列表
    if ext_lower not in SUPPORTED_AUDIO_EXTS:
        ext_hint = f"，建议转换为 WAV 格式" if ext_lower else "（无扩展名）"
        return (
            False,
            f"⚠️ 不确定的音频格式: {ext_upper if ext_lower else '未知'}{ext_hint}: {filename}",
            ext_lower,
        )

    return True, "", ext_lower


def _html_escape(text: str) -> str:
    """转义字符串中的HTML特殊字符，防止XSS注入和HTML结构破坏

    Args:
        text: 需要转义的原始文本
    Returns:
        转义后的安全文本
    """
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _js_escape(text: str) -> str:
    """转义字符串中的JavaScript特殊字符，用于嵌入JS字符串字面量

    Args:
        text: 需要转义的原始文本
    Returns:
        转义后的安全文本（可在单引号JS字符串中使用）
    """
    if not text:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("</", "<\\/")
    )


def _make_recursion_safe(defaults_tuple):
    """RecursionError安全包装器工厂

    FastAPI的jsonable_encoder在序列化错误响应时，如果traceback中捕获了
    含循环引用的对象（如PyTorch模型、Gradio文件对象等），会触发无限递归。
    此装饰器在异常发生时立即拦截RecursionError，返回安全的默认值。

    用法:
        @_make_recursion_safe((gr.update(value=0), 0.33, 0.33, gr.update(value=None), ""))
        def my_callback(x, y):
            ...
    """

    def _decorator(fn):
        import sys as _sys
        import traceback as _tb

        def _wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except RecursionError:
                _exc_info = _sys.exc_info()
                _detail = ""
                if _exc_info and _exc_info[1]:
                    _detail = str(_exc_info[1])[:120]
                print_status(
                    "⛔ RecursionError拦截: "
                    + fn.__name__
                    + " -> 返回安全默认值 ("
                    + _detail
                    + ")",
                    "error",
                )
                try:
                    _sys.exc_clear()
                except Exception:
                    pass
                if isinstance(defaults_tuple, (list, tuple)):
                    return tuple(defaults_tuple)
                return defaults_tuple
            except Exception:
                raise

        _wrapper.__name__ = fn.__name__ + "_recursion_safe"
        _wrapper.__qualname__ = fn.__qualname__
        return _wrapper

    return _decorator


def _cleanup_return_value(obj):
    """清理返回值中的危险对象，防止FastAPI jsonable_encoder崩溃

    当对象包含循环引用（PyTorch模型、Gradio组件、lamdba闭包等）时，
    FastAPI的error response序列化会触发RecursionError或ValueError。
    此函数在回调返回前对危险对象进行替换。
    """
    if obj is None:
        return None
    obj_type = type(obj)
    type_name = obj_type.__name__

    # 非危险类型直接返回
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return type(obj)(_cleanup_return_value(x) for x in obj)
    if isinstance(obj, dict):
        return {k: _cleanup_return_value(v) for k, v in obj.items()}

    # 危险类型替换为安全字符串
    dangerous_types = (
        "Tensor",
        "Module",
        "Parameter",
        "OptimizedModule",
        "Embedding",
        "LSTM",
        "GRU",
        "RNN",
        "Conv1d",
        "Conv2d",
        "Linear",
        "LayerNorm",
        "Dropout",
        "MultiheadAttention",
    )
    for dangerous in dangerous_types:
        if type_name == dangerous or type_name.endswith(dangerous):
            return f"<{type_name} object>"

    # Gradio/Streamlit组件
    if type_name in (
        "Update",
        "Component",
        "HTML",
        "Textbox",
        "Button",
        "Slider",
        "Dropdown",
        "Audio",
        "Video",
        "Image",
        "File",
        "State",
        "Row",
        "Column",
        "TabItem",
        "Block",
        "Button",
        "Markdown",
    ):
        return f"<gr.{type_name} object>"

    # lambda和函数对象
    if callable(obj) and not isinstance(obj, type):
        return f"<function {getattr(obj, '__name__', repr(obj)[:30])}>"

    # 类对象
    if isinstance(obj, type):
        return f"<class {obj.__name__}>"

    # 尝试转str
    try:
        return str(obj)[:200]
    except Exception:
        return f"<{type_name}>"


def _install_recursion_guard():
    """全局安装 RecursionError 防护（线程安全版本）

    核心原理：
    1. 用 threading.local() 线程标志位检测重入
    2. 包装函数内先检查标志位 → 若已设置则立即返回安全值（切断递归）
    3. 设置标志位 → 调用原始函数 → 清除标志位
    4. 即使原始函数内部通过模块名调用 jsonable_encoder，
       标志位也会阻止无限递归

    这解决了之前所有方案的问题：
    - getattr/__dict__ 取原始函数仍被模块替换拦截 → 标志位解决
    - except Exception 不捕获 RecursionError → 此补丁在 FastAPI 层面拦截
    - _cleanup_return_value 只清理返回值不处理异常序列化 → 此补丁兜底
    """
    import threading as _threading
    import fastapi.encoders as _fae

    _reentry = _threading.local()

    try:
        _orig_func = _fae.jsonable_encoder
    except (AttributeError, TypeError):
        print_status("[RecursionGuard] jsonable_encoder 不存在，跳过", "warning")
        return

    if getattr(_orig_func, "_rg_installed", False):
        print_status("[RecursionGuard] 已安装，跳过", "info")
        return

    def _guarded_jsonable_encoder(obj, *args, **kwargs):
        already_in = getattr(_reentry, "in_guard", False)
        if already_in:
            tn = type(obj).__name__ if obj is not None else "None"
            return f"<recursion_guard:{tn}>"

        _reentry.in_guard = True
        try:
            return _orig_func(obj, *args, **kwargs)
        except (RecursionError, ValueError):
            import sys as _sys

            try:
                _sys.exc_clear()
            except Exception:
                pass
            tn = type(obj).__name__ if obj is not None else "None"
            return f"<recursion_error:{tn}>"
        finally:
            _reentry.in_guard = False

    _guarded_jsonable_encoder._rg_installed = True
    _fae.jsonable_encoder = _guarded_jsonable_encoder
    print_status("[RecursionGuard] 全局防护已激活 (线程安全标志位模式)", "success")


def _get_model_shop_cache_path():
    """获取模型工坊本地缓存HTML路径"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(project_root, "tabs", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "model_shop.html")
    pycache_candidate = os.path.join(project_root, "__pycache__")
    if not os.path.exists(cache_file) and os.path.isdir(pycache_candidate):
        for f in os.listdir(pycache_candidate):
            if f.endswith(".html") and ("RVC" in f or "模型" in f or "model" in f.lower()):
                src = os.path.join(pycache_candidate, f)
                try:
                    import shutil
                    shutil.copy2(src, cache_file)
                except Exception:
                    pass
                break
    return cache_file


def _update_model_shop_cache(force=False):
    """更新模型工坊本地缓存，返回远程URL供iframe加载

    策略：
    - 默认：仅当缓存不存在或超过30天（一个月）才更新
    - force=True：强制刷新
    - 返回远程URL（iframe可直接加载），同时缓存HTML到本地作为备份
    """
    import time as _time
    import urllib.request as _urllib_req

    cache_path = _get_model_shop_cache_path()
    remote_url = "https://mxgf.cc"
    max_age_hours = 24 * 30  # 一个月更新一次

    needs_update = force
    if not needs_update:
        if not os.path.exists(cache_path):
            needs_update = True
        else:
            try:
                mtime = os.path.getmtime(cache_path)
                age_hours = (_time.time() - mtime) / 3600
                if age_hours > max_age_hours:
                    needs_update = True
            except Exception:
                needs_update = True

    if needs_update:
        try:
            print_status(f"[模型工坊] 正在更新缓存 (远程: {remote_url})...", "info")
            req = _urllib_req.Request(
                remote_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
            )
            with _urllib_req.urlopen(req, timeout=30) as resp:
                content = resp.read()
            try:
                html_text = content.decode("utf-8")
            except Exception:
                try:
                    html_text = content.decode("gbk", errors="replace")
                except Exception:
                    html_text = content.decode("latin-1", errors="replace")

            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(html_text)
            print_status(
                f"[模型工坊] 缓存已更新: {cache_path}", "success"
            )
        except Exception as e:
            print_status(f"[模型工坊] 缓存更新失败: {str(e)[:80]}", "warning")

    return remote_url


class OutputHistoryManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._records: list[dict] = []
        self._max_records = 50
        self._id_counter = 0

    def add_record(
        self,
        original_path: str,
        converted_paths: list[str],
        model_names: list[str],
        params: dict = None,
        category: str = "cover",
        status: str = "success",
    ) -> dict:
        with self._lock:
            self._id_counter += 1
            rec_id = f"H{self._id_counter:04d}"
            duration, fsize, sr = (
                _get_audio_info(original_path) if original_path else (0, 0, 0)
            )
            record = {
                "id": rec_id,
                "original_path": original_path,
                "original_name": os.path.basename(original_path)
                if original_path
                else "",
                "converted_paths": [
                    p for p in (converted_paths or []) if p and os.path.exists(p)
                ],
                "model_names": model_names or [],
                "params": params or {},
                "category": category,
                "status": status,
                "duration": duration,
                "file_size": fsize,
                "sample_rate": sr,
                "timestamp": _sched_time.time(),
                "time_str": _time_module.strftime(
                    "%m-%d %H:%M", _time_module.localtime()
                ),
                "favorite": False,
            }
            self._records.insert(0, record)
            if len(self._records) > self._max_records:
                self._records.pop()
            print_status(
                f"📜 历史记录 [{rec_id}]: {record['original_name']} → {len(record['converted_paths'])}个成品",
                "info",
            )
            return record

    def get_records(self, category: str = None, limit: int = 20) -> list[dict]:
        with self._lock:
            records = [
                r
                for r in self._records
                if category is None or r.get("category") == category
            ]
            return records[:limit]

    def toggle_favorite(self, rec_id: str) -> bool:
        with self._lock:
            for r in self._records:
                if r["id"] == rec_id:
                    r["favorite"] = not r["favorite"]
                    return r["favorite"]
            return False

    def delete_record(self, rec_id: str) -> bool:
        with self._lock:
            for i, r in enumerate(self._records):
                if r["id"] == rec_id:
                    self._records.pop(i)
                    return True
            return False

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._records)
            self._records.clear()
            return count

    def render_panel_html(self, category: str = None, selected_id: str = "") -> str:
        records = self.get_records(category, limit=30)
        if not records:
            return """<div style="padding:20px;text-align:center;color:#64748b;font-size:0.8rem;border-radius:10px;background:rgba(15,23,42,0.5);border:1px dashed #334155;">
                📭 暂无历史记录<br><span style="font-size:0.72rem;color:#475569;">完成AI翻唱后，成品将自动出现在此处</span>
            </div>"""

        fav_records = [r for r in records if r.get("favorite")]
        normal_records = [r for r in records if not r.get("favorite")]
        parts = []
        parts.append(
            """<div id="history-panel" style="font-family:-apple-system,sans-serif;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;padding:0 2px;">
                <span style="font-size:0.78rem;color:#a78bfa;font-weight:600;">📜 输出历史 (<span id="hist-count">"""
            + str(len(records))
            + """</span>)</span>
                <div style="display:flex;gap:6px;">
                    <button onclick="hist_filter('all')" id="hist-filter-all" style="padding:2px 8px;border-radius:4px;font-size:0.68rem;border:1px solid #7c3aed;background:#7c3aed;color:#fff;cursor:pointer;">全部</button>
                    <button onclick="hist_filter('fav')" id="hist-filter-fav" style="padding:2px 8px;border-radius:4px;font-size:0.68rem;border:1px solid #334155;background:transparent;color:#94a3b8;cursor:pointer;">⭐ 收藏</button>
                </div>
            </div>
            <div id="history-list" style="max-height:420px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;padding-right:4px;">
        """
        )

        display_records = fav_records + normal_records
        for idx, rec in enumerate(display_records):
            is_selected = rec["id"] == selected_id
            is_fav = rec.get("favorite", False)
            status_icon = (
                "✅"
                if rec["status"] == "success"
                else ("❌" if rec["status"] == "failed" else "⏳")
            )
            status_color = (
                "#22c55e"
                if rec["status"] == "success"
                else ("#ef4444" if rec["status"] == "failed" else "#f59e0b")
            )
            bg_style = (
                "background:rgba(124,58,237,0.12);border-color:#7c3aed;"
                if is_selected
                else (
                    "background:rgba(30,41,59,0.6);"
                    if idx % 2 == 0
                    else "background:rgba(15,23,42,0.5);"
                )
            )
            fav_star = "⭐" if is_fav else "☆"
            rid_safe = _js_escape(rec["id"])
            models_safe = [_html_escape(m) for m in (rec.get("model_names") or [])]
            models_tag = ", ".join(models_safe[:3]) if models_safe else "未知"
            if len(models_safe) > 3:
                models_tag += f" (+{len(models_safe) - 3})"
            orig_name_raw = rec.get("original_name") or ""
            orig_name_safe = _html_escape(orig_name_raw)
            orig_name = (
                orig_name_safe[:25] + "..."
                if len(orig_name_safe) > 28
                else (orig_name_safe or "未知音频")
            )

            converted_items_html = ""
            for ci, cp in enumerate(rec.get("converted_paths", [])[:4]):
                if not os.path.exists(cp):
                    continue
                cname = _html_escape(os.path.basename(cp))
                csize = (
                    _fmt_file_size(os.path.getsize(cp)) if os.path.exists(cp) else ""
                )
                c_url = f"/file={os.path.abspath(cp).replace(chr(92), '/')}"
                converted_items_html += f"""<div style="display:flex;align-items:center;gap:4px;padding:3px 6px;border-radius:4px;background:rgba(0,0,0,0.2);margin-top:2px;">
                    <audio src="{_html_escape(c_url)}" preload="none" controlslist="nodownload" style="height:22px;width:120px;" controls></audio>
                    <span style="font-size:0.65rem;color:#94a3b8;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{cname}</span>
                    <a href="{_html_escape(c_url)}" download="{cname}" style="color:#60a5fa;font-size:0.65rem;text-decoration:none;">⬇️{csize}</a>
                </div>"""
            if len(rec.get("converted_paths", [])) > 4:
                converted_items_html += f'<div style="font-size:0.62rem;color:#475569;text-align:center;padding:2px;">还有 {len(rec["converted_paths"]) - 4} 个文件...</div>'

            has_original = rec.get("original_path") and os.path.exists(
                rec["original_path"]
            )
            orig_audio_html = ""
            if has_original:
                _orig_path_val = rec["original_path"]
                orig_url = "/file=" + os.path.abspath(_orig_path_val).replace(
                    chr(92), "/"
                )
                orig_audio_html = f"""<div style="display:flex;align-items:center;gap:4px;margin-bottom:4px;">
                    <span style="font-size:0.65rem;color:#fbbf24;flex-shrink:0;">原曲:</span>
                    <audio src="{_html_escape(orig_url)}" preload="none" id="orig-audio-{rid_safe}" controlslist="nodownload" style="height:20px;width:140px;" controls></audio>
                </div>"""

            ab_compare_btn = ""
            if has_original and rec.get("converted_paths"):
                first_converted = rec["converted_paths"][0]
                if first_converted and os.path.exists(first_converted):
                    conv_url = "/file=" + os.path.abspath(first_converted).replace(
                        chr(92), "/"
                    )
                    ab_compare_btn = f"""<button onclick="event.preventDefault();hist_ab_toggle('{rid_safe}','{_js_escape(orig_url)}','{_js_escape(conv_url)}')" style="
                        padding:2px 8px;border-radius:4px;font-size:0.65rem;
                        border:1px solid #f59e0b;background:rgba(245,158,11,0.12);color:#fbbf24;
                        cursor:pointer;transition:all 0.2s;
                        " onmouseover="this.style.background='rgba(245,158,11,0.25)'" onmouseout="this.style.background='rgba(245,158,11,0.12)'">
                        🔀 AB对比
                    </button>"""

            dur_str = (
                _fmt_duration(rec.get("duration", 0)) if rec.get("duration") else ""
            )

            parts.append(f"""
            <div class="hist-item" data-id="{rid_safe}" data-fav="{str(is_fav).lower()}" style="
                padding:8px 10px;border-radius:8px;border:1px solid {"#7c3aed" if is_selected else "#1e293b"};
                {bg_style}transition:all 0.2s ease;cursor:pointer;
            " onclick="this.querySelector('.hist-detail').style.display=this.querySelector('.hist-detail').style.display==='block'?'none':'block'">
                <div style="display:flex;align-items:center;gap:6px;">
                    <span style="font-size:0.9rem;cursor:pointer;" onclick="event.stopPropagation();hist_toggle_fav('{rid_safe}')">{fav_star}</span>
                    <span style="color:{status_icon};">{status_icon}</span>
                    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:0.76rem;color:#e2e8f0;font-weight:500;">{orig_name}</span>
                    <span style="font-size:0.65rem;color:#64748b;flex-shrink:0;">{dur_str}</span>
                    <span style="font-size:0.62rem;color:#475569;flex-shrink:0;">{rec["time_str"]}</span>
                    {ab_compare_btn}
                    <button onclick="event.stopPropagation();hist_del('{rid_safe}')" style="
                        padding:1px 5px;border-radius:3px;font-size:0.6rem;
                        border:1px solid transparent;background:transparent;color:#475569;
                        cursor:pointer;" onmouseover="this.style.color='#ef4444';this.style.borderColor='#ef4444'"
                        onmouseout="this.style.color='#475569';this.style.borderColor='transparent'">🗑️</button>
                </div>
                <div style="display:flex;gap:6px;margin-top:4px;align-items:center;flex-wrap:wrap;">
                    <span style="font-size:0.65rem;color:#8b5cf6;background:rgba(139,92,246,0.1);padding:1px 6px;border-radius:3px;">🎤 {models_tag}</span>
                    <span style="font-size:0.62rem;color:#64748b;">{_html_escape(rec.get("category", ""))}</span>
                    <span style="font-size:0.62rem;color:#475569;margin-left:auto;">{len(rec.get("converted_paths", []))}个文件</span>
                </div>
                <div class="hist-detail" style="display:none;margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.05);">
                    {orig_audio_html}
                    <div style="font-size:0.65rem;color:#94a3b8;margin-bottom:3px;">🎧 成品文件:</div>
                    {converted_items_html}
                    <div id="ab-player-{rid_safe}" style="display:none;margin-top:4px;padding:6px;border-radius:6px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);">
                        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                            <span style="font-size:0.72rem;color:#fbbf24;font-weight:600;">🔀 AB对比播放器</span>
                            <button id="ab-btn-a-{rid_safe}" onclick="hist_ab_play('{rid_safe}', 'A')" style="padding:2px 8px;border-radius:4px;font-size:0.65rem;border:1px solid #f59e0b;background:#f59e0b;color:#000;cursor:pointer;font-weight:600;">▶ A 原曲</button>
                            <button id="ab-btn-b-{rid_safe}" onclick="hist_ab_play('{rid_safe}', 'B')" style="padding:2px 8px;border-radius:4px;font-size:0.65rem;border:1px solid #3b82f6;background:transparent;color:#3b82f6;cursor:pointer;">▶ B 翻唱</button>
                            <span id="ab-status-{rid_safe}" style="font-size:0.65rem;color:#94a3b8;"></span>
                        </div>
                        <audio id="ab-audio-{rid_safe}" preload="auto" style="width:100%;height:28px;" controls></audio>
                    </div>
                </div>
            </div>""")

        parts.append("""
            </div>
        </div>
        <script>
        function hist_toggle_fav(id) {
            var favInput = document.querySelector('input[data-testid="textbox"]') ||
                document.querySelectorAll('textarea')[0];
            if(favInput) {
                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(favInput, id);
                favInput.dispatchEvent(new Event('input', {bubbles: true}));
                favInput.dispatchEvent(new Event('change', {bubbles: true}));
            }
        }
        function hist_del(id) {
            if(confirm('确定删除这条历史记录？')) {
                var delInput = document.querySelectorAll('textarea')[1];
                if(delInput) {
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    nativeInputValueSetter.call(delInput, id);
                    delInput.dispatchEvent(new Event('input', {bubbles: true}));
                    delInput.dispatchEvent(new Event('change', {bubbles: true}));
                }
            }
        }
        function hist_filter(type) {
            document.getElementById('hist-filter-all').style.background = type==='all' ? '#7c3aed' : 'transparent';
            document.getElementById('hist-filter-all').style.color = type==='all' ? '#fff' : '#94a3b8';
            document.getElementById('hist-filter-fav').style.background = type==='fav' ? '#7c3aed' : 'transparent';
            document.getElementById('hist-filter-fav').style.color = type==='fav' ? '#fff' : '#94a3b8';
            var items = document.querySelectorAll('.hist-item');
            items.forEach(function(el) {
                var isFav = el.getAttribute('data-fav') === 'true';
                el.style.display = (type === 'fav' && !isFav) ? 'none' : '';
            });
        }
        function hist_ab_toggle(id, origUrl, convUrl) {
            var panel = document.getElementById('ab-player-' + id);
            if(panel) panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
            var aAudio = document.getElementById('ab-audio-' + id);
            if(aAudio) {
                aAudio.setAttribute('data-orig', origUrl);
                aAudio.setAttribute('data-conv', convUrl);
            }
        }
        function hist_ab_play(id, side) {
            var audio = document.getElementById('ab-audio-' + id);
            var btnA = document.getElementById('ab-btn-a-' + id);
            var btnB = document.getElementById('ab-btn-b-' + id);
            var status = document.getElementById('ab-status-' + id);
            if(!audio) return;
            var url = side === 'A' ? audio.getAttribute('data-orig') : audio.getAttribute('data-conv');
            audio.src = url;
            audio.play();
            btnA.style.background = side === 'A' ? '#f59e0b' : 'transparent';
            btnA.style.color = side === 'A' ? '#000' : '#3b82f6';
            btnB.style.background = side === 'B' ? '#3b82f6' : 'transparent';
            btnB.style.color = side === 'B' ? '#fff' : '#3b82f6';
            if(status) status.textContent = '正在播放: ' + (side === 'A' ? '原曲' : '翻唱');
            audio.onended = function() { if(status) status.textContent = ''; };
        }
        </script>""")
        return "\n".join(parts)


_output_history = OutputHistoryManager()


def safe_copy_file(
    src_path: str, dest_dir: str, orig_filename: str = "", max_retries: int = 3
) -> tuple:
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


# ============================================
# 🎯 任务调度系统 - Task Scheduler System
# ============================================

import threading
import time as _sched_time
import queue
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any, Optional


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Task:
    id: str
    name: str
    type: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    step_text: str = ""
    detail: str = ""
    created_at: float = field(default_factory=_sched_time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    result: Any = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    pause_event: threading.Event = field(default_factory=threading.Event)
    _target: Optional[Callable] = field(default=None, repr=False)
    _args: tuple = field(default_factory=tuple)
    _kwargs: dict = field(default_factory=dict)

    @property
    def elapsed(self) -> float:
        if self.started_at:
            end = self.completed_at or _sched_time.time()
            return end - self.started_at
        return 0

    @property
    def eta(self) -> str:
        if self.progress > 0 and self.elapsed > 0:
            total_est = self.elapsed / (self.progress / 100.0)
            remaining = max(0, total_est - self.elapsed)
            if remaining < 60:
                return f"{remaining:.0f}秒"
            elif remaining < 3600:
                return f"{remaining / 60:.1f}分钟"
            else:
                return f"{remaining / 3600:.1f}小时"
        return "--"

    def cancel(self):
        self.status = TaskStatus.CANCELLED
        self.cancel_event.set()

    def pause(self):
        if self.status == TaskStatus.RUNNING:
            self.status = TaskStatus.PAUSED
            self.pause_event.clear()

    def resume(self):
        if self.status == TaskStatus.PAUSED:
            self.status = TaskStatus.RUNNING
            self.pause_event.set()

    def check_cancelled(self):
        self.cancel_event.wait(timeout=0.001)
        return self.cancel_event.is_set()

    def wait_if_paused(self):
        while self.status == TaskStatus.PAUSED and not self.check_cancelled():
            self.pause_event.wait(timeout=0.5)


class ResourceMonitor:
    """系统资源监控模块（GPU显存 + 系统内存，通过nvidia-smi实时读取）"""

    _lock = threading.Lock()
    _last_result: dict = {}

    @classmethod
    def _read_nvidia_smi(cls) -> dict:
        try:
            import subprocess as _subprocess

            result = _subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    total = int(parts[0].strip())
                    used = int(parts[1].strip())
                    free = int(parts[2].strip())
                    return {
                        "total": total,
                        "used": used,
                        "free": free,
                        "available": True,
                    }
        except Exception:
            pass
        return {"total": 0, "used": 0, "free": 0, "available": False}

    @classmethod
    def _read_torch_cuda(cls) -> dict:
        try:
            import torch as _torch

            if _torch.cuda.is_available():
                total = _torch.cuda.get_device_properties(0).total_memory / (1024**2)
                used = _torch.cuda.memory_allocated(0) / (
                    1024**2
                ) + _torch.cuda.memory_reserved(0) / (1024**2)
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
                "gpu_percent": round(gpu.get("used", 0) / gpu.get("total", 1) * 100, 1)
                if gpu.get("total", 0) > 0
                else 0.0,
                "gpu_available": gpu.get("available", False),
                "sys_mem_percent": 0,
                "sys_mem_used_gb": 0.0,
                "sys_mem_total_gb": 0.0,
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
                "is_stressed": (gpu_percent > 90)
                if gpu_available
                else False or sys_mem.percent > 90,
            }
        return cls._last_result

    @classmethod
    def get_status_html(cls) -> str:
        info = cls.snapshot()
        gpu_color = (
            "#ef4444"
            if info["gpu_percent"] > 85
            else ("#f59e0b" if info["gpu_percent"] > 65 else "#22c55e")
        )
        mem_color = (
            "#ef4444"
            if info["sys_mem_percent"] > 85
            else ("#f59e0b" if info["sys_mem_percent"] > 70 else "#22c55e")
        )
        stress_tag = (
            ' <span style="color:#ef4444;font-size:0.7rem;">⚠️ 资源紧张</span>'
            if info.get("is_stressed")
            else ""
        )

        if info["gpu_available"]:
            gpu_bar = (
                f'<div style="width:60px;height:4px;background:#1e293b;border-radius:2px;margin-top:2px;">'
                f'<div style="width:{info["gpu_percent"]}%;height:100%;background:{gpu_color};border-radius:2px;"></div></div>'
            )
            gpu_detail = (
                f'<div style="font-size:0.62rem;color:#64748b;">'
                f"{info['gpu_used_mb'] // 1024:.1f}/{info['gpu_total_mb'] // 1024:.1f}GB</div>"
            )
        else:
            gpu_bar = '<div style="font-size:0.62rem;color:#f87171;margin-top:2px;">无GPU或驱动异常</div>'
            gpu_detail = ""

        return f"""<div id="gpu-status-panel" style="display:flex;gap:16px;align-items:flex-start;font-size:0.72rem;color:#94a3b8;flex-wrap:wrap;">
            <div>
                <div style="display:flex;align-items:center;gap:4px;">
                    <span>🎮 GPU</span>
                    <b style="color:{gpu_color}">{info["gpu_percent"]:.1f}%</b>
                </div>
                {gpu_detail}
                {gpu_bar}
            </div>
            {stress_tag}
        </div>"""


try:
    import psutil
except ImportError:
    psutil = None


class TaskQueue:
    """任务队列管理器（支持优先级排序）"""

    def __init__(self):
        self._queue: list[Task] = []
        self._lock = threading.RLock()
        self._task_counter = 0
        self._history: list[Task] = []

    def enqueue(self, task: Task) -> Task:
        with self._lock:
            self._task_counter += 1
            task.id = f"T{self._task_counter:04d}"
            self._queue.append(task)
            self._sort_queue()
            print_status(
                f"📋 任务入队 [{task.id}] {task.name} (优先级:{task.priority.name})",
                "info",
            )
            return task

    def dequeue(self) -> Optional[Task]:
        with self._lock:
            if self._queue:
                task = self._queue.pop(0)
                return task
            return None

    def peek(self) -> Optional[Task]:
        with self._lock:
            return self._queue[0] if self._queue else None

    def remove(self, task_id: str) -> bool:
        with self._lock:
            for i, t in enumerate(self._queue):
                if t.id == task_id:
                    t.cancel()
                    self._queue.pop(i)
                    print_status(f"❌ 任务已移除 [{task_id}] {t.name}", "warning")
                    return True
            return False

    def move_up(self, task_id: str) -> bool:
        with self._lock:
            for i, t in enumerate(self._queue):
                if t.id == task_id and i > 0:
                    self._queue[i], self._queue[i - 1] = (
                        self._queue[i - 1],
                        self._queue[i],
                    )
                    print_status(f"⬆️ 任务上移 [{task_id}]", "info")
                    return True
            return False

    def move_down(self, task_id: str) -> bool:
        with self._lock:
            for i, t in enumerate(self._queue):
                if t.id == task_id and i < len(self._queue) - 1:
                    self._queue[i], self._queue[i + 1] = (
                        self._queue[i + 1],
                        self._queue[i],
                    )
                    print_status(f"⬇️ 任务下移 [{task_id}]", "info")
                    return True
            return False

    def move_to_top(self, task_id: str) -> bool:
        with self._lock:
            for i, t in enumerate(self._queue):
                if t.id == task_id and i > 0:
                    task = self._queue.pop(i)
                    self._queue.insert(0, task)
                    print_status(f"⏫ 任务置顶 [{task_id}] {t.name}", "info")
                    return True
            return False

    def _sort_queue(self):
        self._queue.sort(key=lambda t: (t.priority.value, t.created_at))

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len([t for t in self._queue if t.status == TaskStatus.PENDING])

    @property
    def all_tasks(self) -> list[Task]:
        with self._lock:
            return list(self._queue)

    def add_to_history(self, task: Task):
        self._history.append(task)
        if len(self._history) > 20:
            self._history.pop(0)


class TaskScheduler:
    """全局任务调度器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.queue = TaskQueue()
        self._current_task: Optional[Task] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._state_lock = threading.RLock()
        self._update_callbacks: list[Callable] = []
        self._completion_callbacks: list[Callable] = []

    @property
    def is_busy(self) -> bool:
        with self._state_lock:
            return (
                self._current_task is not None
                and self._current_task.status == TaskStatus.RUNNING
            )

    @property
    def current_task(self) -> Optional[Task]:
        with self._state_lock:
            return self._current_task

    @property
    def queue_html(self) -> str:
        return self._render_queue_ui()

    def submit(
        self,
        name: str,
        task_type: str,
        target: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> Task:
        kwargs = kwargs or {}
        task = Task(
            id="",
            name=name,
            type=task_type,
            priority=priority,
            _target=target,
            _args=args,
            _kwargs=kwargs,
        )
        self.queue.enqueue(task)
        self._notify_update()
        if not self._running:
            self.start()
        return task

    def start(self):
        with self._state_lock:
            if self._running:
                return
            self._running = True
            self._scheduler_thread = threading.Thread(
                target=self._run_loop, daemon=True, name="TaskScheduler"
            )
            self._scheduler_thread.start()
            print_status("✅ 任务调度器已启动", "success")

    def stop(self):
        with self._state_lock:
            self._running = False
            if self._current_task:
                self._current_task.cancel()
        print_status("⏹️ 任务调度器已停止", "warning")

    def cancel_current(self):
        with self._state_lock:
            if self._current_task:
                self._current_task.cancel()
                print_status(f"❌ 取消当前任务: {self._current_task.name}", "warning")

    def pause_current(self):
        with self._state_lock:
            if self._current_task and self._current_task.status == TaskStatus.RUNNING:
                self._current_task.pause()
                print_status(f"⏸️ 暂停当前任务: {self._current_task.name}", "info")

    def resume_current(self):
        with self._state_lock:
            if self._current_task and self._current_task.status == TaskStatus.PAUSED:
                self._current_task.resume()
                print_status(f"▶️ 继续当前任务: {self._current_task.name}", "info")

    def cancel_queued(self, task_id: str) -> bool:
        return self.queue.remove(task_id)

    def clear_pending(self):
        with self.queue._lock:
            count = len(
                [t for t in self.queue._queue if t.status == TaskStatus.PENDING]
            )
            self.queue._queue = [
                t for t in self.queue._queue if t.status != TaskStatus.PENDING
            ]
            if count:
                print_status(f"🗑️ 已清除 {count} 个待处理任务", "warning")
            self._notify_update()
            return count

    def on_update(self, callback: Callable):
        self._update_callbacks.append(callback)

    def on_complete(self, callback: Callable):
        self._completion_callbacks.append(callback)

    def _notify_update(self):
        for cb in self._update_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _notify_complete(self, task: Task):
        for cb in self._completion_callbacks:
            try:
                cb(task)
            except Exception:
                pass

    def _run_loop(self):
        while self._running:
            task = self.queue.dequeue()
            if task is None:
                _sched_time.sleep(0.5)
                continue

            with self._state_lock:
                self._current_task = task
                task.status = TaskStatus.RUNNING
                task.started_at = _sched_time.time()
                task.pause_event.set()

            self._notify_update()
            print_status(f"▶️ 开始执行 [{task.id}] {task.name}", "convert")

            try:
                if task._target:
                    result = task._target(*task._args, **task._kwargs)
                    task.result = result
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.completed_at = _sched_time.time()
                print_status(
                    f"✅ 任务完成 [{task.id}] {task.name} ({task.elapsed:.1f}s)",
                    "success",
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                task.error = str(e)
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.FAILED
                    print_status(
                        f"⚠️ 任务失败 [{task.id}], 正在重试 ({task.retry_count}/{task.max_retries})...",
                        "error",
                    )
                    self.queue.enqueue(
                        Task(
                            id="",
                            name=f"[重试{task.retry_count}] {task.name}",
                            type=task.type,
                            priority=task.priority,
                            _target=task._target,
                            _args=task._args,
                            _kwargs=task._kwargs,
                            retry_count=task.retry_count,
                            max_retries=task.max_retries,
                        )
                    )
                else:
                    task.status = TaskStatus.FAILED
                    print_status(
                        f"❌ 任务最终失败 [{task.id}] {task.name}: {str(e)}", "error"
                    )

            self.queue.add_to_history(task)
            self._notify_complete(task)
            self._notify_update()

            with self._state_lock:
                self._current_task = None

    def _render_queue_ui(self) -> str:
        try:
            pending_tasks = [
                t for t in self.queue.all_tasks if t.status == TaskStatus.PENDING
            ]
            current = self.current_task
            res_info = ResourceMonitor.get_status_html()
        except Exception:
            res_info = '<span style="font-size:0.72rem;color:#64748b;">资源监控加载中...</span>'
            pending_tasks = []
            current = None

        parts = [
            f"""<div style="font-family:-apple-system,sans-serif;background:#0f172a;border-radius:12px;padding:14px;border:1px solid #1e293b;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <span style="font-weight:700;font-size:0.85rem;color:#e2e8f0;">🎯 任务调度中心</span>
                <span style="font-size:0.68rem;color:#64748b;">队列: {len(pending_tasks)} 个待处理</span>
            </div>
            {res_info}"""
        ]

        if current:
            pct = current.progress
            bar_color = (
                "#22c55e"
                if current.status == TaskStatus.COMPLETED
                else ("#f59e0b" if current.status == TaskStatus.PAUSED else "#3b82f6")
            )
            status_icon = {
                "running": "🔄",
                "paused": "⏸️",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "🚫",
            }.get(current.status.value, "📋")
            status_label = {
                "running": "执行中",
                "paused": "已暂停",
                "completed": "已完成",
                "failed": "失败",
                "cancelled": "已取消",
            }.get(current.status.value, "")

            parts.append(f"""
            <div style="background:#1e293b;border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #3b82f6;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <span><b>{status_icon}</b> <span style="color:#93c5fd;font-size:0.78rem;">{_html_escape(current.name)}</span></span>
                    <span style="font-size:0.68rem;color:{bar_color};">{status_label} {pct}%</span>
                </div>
                <div style="background:#0f172a;border-radius:4px;height:6px;overflow:hidden;margin-bottom:4px;">
                    <div style="background:{bar_color};width:{min(pct, 100)}%;height:100%;border-radius:4px;transition:width 0.3s;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.68rem;color:#64748b;">
                    <span>{_html_escape(current.step_text) or "--"}</span>
                    <span>⏱ {current.elapsed:.0f}s | ETA: {current.eta}</span>
                </div>
            </div>""")

        if pending_tasks:
            parts.append(f"""<div style="max-height:280px;overflow-y:auto;" id="queue-task-list">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;padding:0 2px;">
                    <span style="font-size:0.7rem;color:#94a3b8;">📋 待处理队列 ({len(pending_tasks)})</span>
                    <button onclick="queue_action('clear')" style="
                        padding:1px 8px;border-radius:4px;font-size:0.62rem;
                        border:1px solid #334155;background:transparent;color:#64748b;
                        cursor:pointer;" onmouseover="this.style.color='#ef4444';this.style.borderColor='#ef4444'"
                        onmouseout="this.style.color='#64748b';this.style.borderColor='#334155'">清空全部</button>
                </div>""")
            for i, t in enumerate(pending_tasks[:12]):
                pri_colors = {
                    "HIGH": ("#ef4444", "rgba(239,68,68,0.12)", "🔴 紧急"),
                    "NORMAL": ("#f59e0b", "rgba(245,158,11,0.12)", "🟡 普通"),
                    "LOW": ("#22c55e", "rgba(34,197,94,0.12)", "🟢 低优"),
                }
                pri_color, pri_bg, pri_label = pri_colors.get(
                    t.priority.name, ("#94a3b8", "rgba(148,163,184,0.12)", "⚪ 未知")
                )
                tname_safe = _html_escape(t.name)
                tname_display = (
                    tname_safe[:35] + "..." if len(tname_safe) > 35 else tname_safe
                )
                tid_safe = _js_escape(t.id)
                is_first = i == 0
                is_last = i == len(pending_tasks) - 1 or i >= 11

                parts.append(
                    '\
                <div class="queue-task-card" data-id="'
                    + tid_safe
                    + '" style="\
                    display:flex;align-items:center;gap:6px;padding:7px 10px;border-radius:8px;margin-bottom:4px;\
                    background:'
                    + (
                        "rgba(124,58,237,0.08)"
                        if i == 0
                        else (
                            "rgba(30,41,59,0.6)" if i % 2 == 0 else "rgba(15,23,42,0.5)"
                        )
                    )
                    + ";\
                    border:1px solid "
                    + ("#7c3aed" if i == 0 else "#1e293b")
                    + ';\
                    transition:all 0.2s ease;font-size:0.72rem;">\
                    <span style="cursor:grab;color:#475569;font-size:0.85rem;flex-shrink:0;" title="拖拽排序">☰</span>\
                    <span style="color:#475569;flex-shrink:0;width:16px;text-align:right;font-size:0.62rem;">'
                    + str(i + 1)
                    + '</span>\
                    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#e2e8f0;font-weight:500;">'
                    + tname_display
                    + '</span>\
                    <span style="padding:1px 6px;border-radius:3px;font-size:0.6rem;color:'
                    + pri_color
                    + ";background:"
                    + pri_bg
                    + ";border:1px solid "
                    + pri_color
                    + '33;flex-shrink:0;white-space:nowrap;">'
                    + pri_label
                    + '</span>\
                    <div style="display:flex;gap:2px;flex-shrink:0;">'
                    + (
                        ""
                        if is_first
                        else "<button onclick=\"queue_action('up','"
                        + tid_safe
                        + '\')" style="padding:1px 5px;border-radius:3px;font-size:0.6rem;border:1px solid #334155;background:transparent;color:#94a3b8;cursor:pointer;line-height:1.2;" title="上移优先">▲</button>'
                    )
                    + (
                        ""
                        if is_last
                        else "<button onclick=\"queue_action('down','"
                        + tid_safe
                        + '\')" style="padding:1px 5px;border-radius:3px;font-size:0.6rem;border:1px solid #334155;background:transparent;color:#94a3b8;cursor:pointer;line-height:1.2;" title="下移优先">▼</button>'
                    )
                    + (
                        ""
                        if is_first
                        else "<button onclick=\"queue_action('top','"
                        + tid_safe
                        + '\')" style="padding:1px 5px;border-radius:3px;font-size:0.6rem;border:1px solid #7c3aed;background:transparent;color:#a78bfa;cursor:pointer;line-height:1.2;" title="置顶">⏫</button>'
                    )
                    + "<button onclick=\"queue_action('cancel_queued','"
                    + tid_safe
                    + '\')" style="padding:1px 5px;border-radius:3px;font-size:0.6rem;border:1px solid transparent;background:transparent;color:#475569;cursor:pointer;line-height:1.2;" title="移除" onmouseover="this.style.color=\'#ef4444\'" onmouseout="this.style.color=\'#475569\'">✕</button>\
                    </div>\
                </div>'
                )
            if len(pending_tasks) > 12:
                parts.append(
                    f'<div style="text-align:center;font-size:0.66rem;color:#475569;padding:4px;">... 还有 {len(pending_tasks) - 12} 个任务在队列中</div>'
                )
            parts.append("</div>")

        history = self.queue._history[-5:]
        if history:
            parts.append(
                '<div style="margin-top:10px;border-top:1px solid #1e293b;padding-top:8px;">'
            )
            parts.append(
                '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:0.7rem;color:#475569;">📜 最近完成 ({len(history)})</span></div>'
            )
            for h in reversed(history):
                icon = (
                    "✅"
                    if h.status == TaskStatus.COMPLETED
                    else ("❌" if h.status == TaskStatus.FAILED else "🚫")
                )
                icon_color = (
                    "#22c55e"
                    if h.status == TaskStatus.COMPLETED
                    else ("#ef4444" if h.status == TaskStatus.FAILED else "#94a3b8")
                )
                hname_safe = _html_escape(h.name)
                hname = hname_safe[:30] + "..." if len(hname_safe) > 30 else hname_safe
                elapsed_str = (
                    f"{h.elapsed:.0f}s"
                    if h.elapsed < 60
                    else f"{h.elapsed / 60:.1f}min"
                )
                parts.append(
                    f'<div style="display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:4px;font-size:0.68rem;color:#64748b;{"background:rgba(34,197,94,0.04)" if h.status == TaskStatus.COMPLETED else ""}"><span style="color:{icon_color};">{icon}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{hname}</span><span style="color:#475569;flex-shrink:0;font-size:0.62rem;">{elapsed_str}</span></div>'
                )
            parts.append("</div>")

        parts.append("</div>")
        _gpu_refresh_js = """
        <script>
        (function(){
            if(window.__gpu_timer) return;
            window.__gpu_timer = setInterval(function(){
                var el = document.getElementById('gpu-status-panel');
                if(!el) return;
                fetch('/api/ping', {method:'GET', cache:'no-store'}).then(function(r){
                    if(r.ok){
                        var parent = el.parentElement;
                        if(parent) parent.innerHTML = '<div id="gpu-status-panel" style="opacity:0.6;">🎮 GPU 刷新中...</div>';
                    }
                }).catch(function(){});
            }, 5000);
        })();
        function queue_action(action, taskId) {
            if(action === 'clear' && !confirm('确定清空所有待处理任务？')) return;
            var actionStr = (taskId ? (action + '::' + taskId) : action);
            var textareas = document.querySelectorAll('textarea');
            for(var i = 0; i < textareas.length; i++) {
                var ta = textareas[i];
                if(ta.offsetParent === null || ta.offsetWidth === 0) {
                    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    nativeSetter.call(ta, actionStr);
                    ta.dispatchEvent(new Event('input', {bubbles: true}));
                    ta.dispatchEvent(new Event('change', {bubbles: true}));
                    break;
                }
            }
        }
        (function(){
            var listEl = document.getElementById('queue-task-list');
            if(listEl) {
                var draggedItem = null;
                listEl.addEventListener('dragstart', function(e) {
                    draggedItem = e.target.closest('.queue-task-card');
                    if(draggedItem) {
                        e.dataTransfer.effectAllowed = 'move';
                        draggedItem.style.opacity = '0.4';
                    }
                });
                listEl.addEventListener('dragend', function(e) {
                    if(draggedItem) draggedItem.style.opacity = '1';
                    draggedItem = null;
                });
                listEl.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    var target = e.target.closest('.queue-task-card');
                    if(target && target !== draggedItem) {
                        var rect = target.getBoundingClientRect();
                        var midY = rect.top + rect.height / 2;
                        if(e.clientY < midY) {
                            target.parentNode.insertBefore(draggedItem, target);
                        } else {
                            target.parentNode.insertBefore(draggedItem, target.nextSibling);
                        }
                    }
                });
            }
        })();
        </script>"""
        parts.append(_gpu_refresh_js)
        return "\n".join(parts)


scheduler = TaskScheduler()


def _acquire_exec(task_type: str, task_name: str = "") -> bool:
    from tabs.header import _acquire_exec as _header_acquire
    return _header_acquire(task_type, task_name)


def _release_exec(task_type: str):
    from tabs.header import _release_exec as _header_release
    _header_release(task_type)


def _is_executing(task_type: str) -> bool:
    from tabs.header import _is_executing as _header_is_exec
    return _header_is_exec(task_type)


def _update_task_name(task_type: str, task_name: str):
    """更新正在运行的任务的显示名称（实时状态）"""
    from tabs.header import _update_task_name as _header_update
    _header_update(task_type, task_name)


class _LiveTaskCtx:
    __slots__ = ("task",)

    def __init__(self, name: str, task_type: str):
        self.task = Task(
            id="",
            name=name,
            type=task_type,
            priority=TaskPriority.HIGH,
            status=TaskStatus.RUNNING,
            started_at=_sched_time.time(),
        )
        with scheduler._state_lock:
            scheduler._current_task = self.task
        scheduler._notify_update()

    def update(self, progress: int = 0, step_text: str = ""):
        if self.task:
            self.task.progress = min(progress, 99)
            if step_text:
                self.task.step_text = step_text[:80]

    def complete(self, success: bool = True, error: str = ""):
        if not self.task:
            return
        self.task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        self.task.progress = 100 if success else self.task.progress
        self.task.completed_at = _sched_time.time()
        self.task.error = error
        scheduler.queue.add_to_history(self.task)
        scheduler._notify_complete(self.task)
        with scheduler._state_lock:
            if scheduler._current_task is self.task:
                scheduler._current_task = None
        scheduler._notify_update()
        self.task = None


def render_scheduler_panel() -> str:
    """获取调度面板HTML，供Gradio组件刷新使用"""
    try:
        return scheduler._render_queue_ui()
    except Exception:
        return """<div style="font-family:-apple-system,sans-serif;background:#0f172a;border-radius:12px;padding:14px;border:1px solid #1e293b;text-align:center;color:#64748b;font-size:0.75rem;">
            ⚠️ 调度器加载中，请稍后...
        </div>"""


def scheduler_action(action: str, task_id: str = "") -> str:
    """执行调度操作（通过Gradio按钮调用）"""
    action = action.strip().lower() if action else ""
    if action == "pause":
        scheduler.pause_current()
    elif action == "resume":
        scheduler.resume_current()
    elif action == "cancel":
        scheduler.cancel_current()
    elif action == "cancel_queued" and task_id:
        scheduler.cancel_queued(task_id)
    elif action == "clear":
        scheduler.clear_pending()
    elif action == "up" and task_id:
        scheduler.queue.move_up(task_id)
    elif action == "down" and task_id:
        scheduler.queue.move_down(task_id)
    elif action == "top" and task_id:
        scheduler.queue.move_to_top(task_id)
    return scheduler.queue_html


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
                    print_status(
                        f"🎵 音频上传成功: {os.path.basename(dest_path)}", "success"
                    )
                else:
                    errors.append(f"⚠️ {os.path.basename(f.name)}: {copy_msg}")
                    print_status(errors[-1], "error")
            if errors:
                return (
                    f"上传完成 {len(results)} 个，{len(errors)} 个失败:\n"
                    + "\n".join(errors)
                )
            return (
                results
                if len(results) > 1
                else (results[0] if results else "未找到有效音频文件")
            )
        else:
            is_valid, msg, _ = validate_audio_file(file_obj.name)
            if not is_valid:
                print_status(msg, "error")
                return msg
            ok, dest_path, copy_msg = safe_copy_file(file_obj.name, tmp)
            if ok:
                print_status(
                    f"🎵 音频上传成功: {os.path.basename(dest_path)}", "success"
                )
                return dest_path
            print_status(f"❌ 音频上传失败: {copy_msg}", "error")
            return f"上传失败: {copy_msg}"
    except Exception as e:
        print_status(f"❌ 上传异常: {str(e)}", "error")
        return f"上传失败: {str(e)}"


def get_model_list():
    names = []
    blocked = []
    SVC_SIZE_LIMIT_MB = 300
    for name in os.listdir(weight_root):
        if name.endswith(".pth"):
            pth_path = os.path.join(weight_root, name)
            try:
                size_mb = os.path.getsize(pth_path) / (1024 * 1024)
                if size_mb > SVC_SIZE_LIMIT_MB:
                    blocked.append(f"{name} ({size_mb:.0f}MB)")
                    print_status(
                        f"⚠️ 模型 {name} ({size_mb:.0f}MB) 超过 {SVC_SIZE_LIMIT_MB}MB，可能是SVC模型，不兼容RVC",
                        "warning",
                    )
                    continue
            except Exception:
                pass
            names.append(name)
    if blocked:
        _SVC_BLOCKED_MODELS.clear()
        _SVC_BLOCKED_MODELS.extend(blocked)
    return sorted(names)


_SVC_BLOCKED_MODELS = []


def get_index_list():
    """获取索引文件列表"""
    index_paths = []
    for root, dirs, files in os.walk(index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append(os.path.join(root, name))
    for root, dirs, files in os.walk(outside_index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append(os.path.join(root, name))
    return sorted(index_paths)


def get_index_path_from_model(model_name):
    """根据 RVC 模型名自动匹配最可能的 FAISS 索引。"""
    if not model_name:
        return None
    if isinstance(model_name, list):
        model_name = model_name[0] if model_name else ""
    model_base = os.path.splitext(os.path.basename(str(model_name)))[0].lower()
    model_tokens = [t for t in re.split(r"[^a-z0-9]+", model_base) if t]
    if not model_tokens:
        return None

    best_score = 0
    best_path = None
    for index_path in get_index_list():
        index_base = os.path.splitext(os.path.basename(index_path))[0].lower()
        index_tokens = [t for t in re.split(r"[^a-z0-9]+", index_base) if t]
        if not index_tokens:
            continue

        score = 0
        if index_tokens[:len(model_tokens)] == model_tokens:
            score += 100
        if model_base in index_base:
            score += 50
        if os.path.basename(index_path).startswith("added_"):
            score += 10
        if os.path.dirname(index_path).lower().endswith(f"/{model_base}"):
            score += 25

        if score > best_score:
            best_score = score
            best_path = index_path

    return best_path if best_score >= 50 else None


if config is not None and get_config().dml == True:

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


weight_root = os.getenv("weight_root") or os.path.join(now_dir, "weights")
weight_uvr5_root = os.getenv("weight_uvr5_root") or os.path.join(now_dir, "assets", "uvr5_weights")
index_root = os.getenv("index_root") or os.path.join(now_dir, "logs")
outside_index_root = os.getenv("outside_index_root") or os.path.join(now_dir, "logs")

names = []
if weight_root and os.path.isdir(weight_root):
    for name in os.listdir(weight_root):
        if name.endswith(".pth"):
            names.append(name)
index_paths = []


def lookup_indices(index_root):
    global index_paths
    for root, dirs, files in os.walk(index_root, topdown=False):
        for name in files:
            if name.endswith(".index") and "trained" not in name:
                index_paths.append(os.path.join(root, name))


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
                index_paths.append(os.path.join(root, name))
    return {"choices": sorted(names), "__type__": "update", "value": None}, {
        "choices": sorted(index_paths),
        "__type__": "update",
        "value": None,
    }


def clean():
    return {"value": None, "__type__": "update"}


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
        get_config().python_cmd,
        trainset_dir,
        sr,
        n_p,
        now_dir,
        exp_dir,
        get_config().noparallel,
        get_config().preprocess_per,
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
                    get_config().python_cmd,
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
                            get_config().python_cmd,
                            leng,
                            idx,
                            n_g,
                            now_dir,
                            exp_dir,
                            get_config().is_half,
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
                    get_config().python_cmd
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
                get_config().python_cmd,
                get_config().device,
                leng,
                idx,
                n_g,
                now_dir,
                exp_dir,
                version19,
                get_config().is_half,
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
                get_config().json_config[config_path],
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
                get_config().python_cmd,
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
                get_config().python_cmd,
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
                    batch_size=256 * get_config().n_cpu,
                    compute_labels=False,
                    init="random",
                )
                .fit(big_npy)
                .cluster_centers_
            )
        except Exception:
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
    except Exception:
        infos.append("链接索引到外部-%s失败" % (outside_index_root))
    # faiss.write_index(index, '%s/added_IVF%s_Flat_FastScan_%s.index'%(exp_dir,n_ivf,version19))
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
    except Exception:
        return {"__type__": "update"}, {"__type__": "update"}, {"__type__": "update"}


F0GPUVisible = get_config().dml == False if config else True


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
        return (
            output_path,
            f"变调完成 | 步数: {n_steps:+d} 半音 | 方法: {method} | 输出: {output_path}",
        )
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
        return (
            output_path,
            f"混音完成 | 人声:{vocal_vol:.2f} 伴奏:{inst_vol:.2f} | 输出: {output_path}",
        )
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
            vocal_path,
            inst_path,
            output_path,
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
            audio_path,
            output_dir,
            min_duration=min_dur,
            max_duration=max_dur,
            top_db=top_db,
        )
        if not saved_files:
            return None, "未检测到有效片段，请调整参数后重试"
        summary = "\n".join(
            [f"  {i + 1}. {os.path.basename(f)}" for i, f in enumerate(saved_files)]
        )
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
        processed = mixer.apply_reverb(
            audio, room_size=room_size, damping=damping, wet_level=wet_level
        )
        sf.write(output_path, processed, sr)
        print_status(f"🔊 混响效果处理完成: {os.path.basename(output_path)}", "success")
        return (
            output_path,
            f"混响完成 | 空间:{room_size:.2f} 湿度:{wet_level:.2f} | 输出: {output_path}",
        )
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
        save_root_vocal = (
            save_root_vocal.strip().strip('"').strip("\n").strip() or "opt"
        )
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

                result = sep.separate(
                    file_path, out_dir, instruments=["vocals", "other"]
                )

                if result.vocals and os.path.exists(result.vocals):
                    dest_vocal = os.path.join(
                        save_root_vocal,
                        generate_save_filename("", base_name, "干声", f".{format0}"),
                    )
                    shutil.copy2(result.vocals, dest_vocal)
                else:
                    dest_vocal = None

                if result.other and os.path.exists(result.other):
                    dest_other = os.path.join(
                        save_root_ins,
                        generate_save_filename("", base_name, "伴奏", f".{format0}"),
                    )
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
        except Exception:
            pass
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    yield "\n".join(infos)


# ============================================
# 进度条 HTML 生成
# ============================================


def _progress_html(
    percent: float,
    step_text: str = "",
    detail: str = "",
    elapsed: float = None,
    remaining: float = None,
    tip: str = "",
) -> str:
    """生成可视化进度条 HTML，支持耗时预估和温馨提示"""
    bar_color = "#a78bfa"
    bg_color = "#2d1b4e"
    elapsed_str = ""
    if elapsed is not None:
        if elapsed < 60:
            elapsed_str = f"已用 {elapsed:.0f}s"
        else:
            elapsed_str = f"已用 {elapsed / 60:.1f}min"
        if remaining is not None and remaining > 0:
            if remaining < 60:
                elapsed_str += f" · 剩余约 {remaining:.0f}s"
            else:
                elapsed_str += f" · 剩余约 {remaining / 60:.1f}min"
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


def skeleton_loading_html(
    title: str = "加载中",
    subtitle: str = "",
    estimated_time: str = "",
    stage: str = "model",
) -> str:
    """生成骨架屏加载动画HTML，用于模型/分离模块加载等待期间展示

    Args:
        title: 主标题文字
        subtitle: 副标题描述
        estimated_time: 预计剩余时间文字
        stage: 加载阶段标识 ("model" | "separator" | "general")
    """
    stage_icons = {"model": "🎤", "separator": "✂️", "general": "⚙️"}
    icon = stage_icons.get(stage, "⏳")

    bar_colors = ["#7c3aed", "#8b5cf6", "#a78bfa", "#c4b5fd", "#7c3aed"]
    bars_html = ""
    for i, color in enumerate(bar_colors):
        delay = i * 0.15
        width = [60, 80, 100, 75, 50][i]
        bars_html += f"""<div style="
            width:{width}%;height:6px;border-radius:3px;
            background:linear-gradient(90deg, {color}, rgba(124,58,237,0.3));
            animation:skeleton-pulse 1.2s ease-in-out {delay}s infinite;
        "></div>"""

    circle_dots = ""
    for i in range(3):
        delay = i * 0.2
        circle_dots += f'<div style="width:10px;height:10px;border-radius:50%;background:#a78bfa;animation:dot-bounce 1s ease-in-out {delay}s infinite;"></div>'

    est_html = ""
    if estimated_time:
        est_html = f"""<div style="margin-top:10px;padding:6px 12px;border-radius:6px;background:rgba(251,191,36,0.08);border-left:3px solid #fbbf24;">
            <span style="font-size:0.72rem;color:#fde68a;">⏱️ 预计等待: </span>
            <span style="font-size:0.72rem;color:#fbbf24;font-weight:600;">{_html_escape(estimated_time)}</span>
        </div>"""

    sub_html = (
        f"""<div style="font-size:0.74rem;color:#94a3b8;margin-top:6px;">{_html_escape(subtitle)}</div>"""
        if subtitle
        else ""
    )

    return f"""<div style="margin:10px 0;padding:18px;border-radius:12px;background:linear-gradient(135deg,#1a0a2e 0%,#161032 50%,#1a0a2e 100%);border:1px solid rgba(124,58,237,0.15);text-align:center;">
        <div style="font-size:1.8rem;margin-bottom:8px;animation:icon-float 2s ease-in-out infinite;">{_html_escape(icon)}</div>
        <div style="font-size:0.88rem;color:#e2e8f0;font-weight:600;margin-bottom:4px;">{_html_escape(title)}</div>
        {sub_html}
        <div style="display:flex;gap:4px;justify-content:center;margin:14px 6px 8px;">
            {circle_dots}
        </div>
        <div style="display:flex;flex-direction:column;gap:5px;margin:10px 16px 0;">
            {bars_html}
        </div>
        {est_html}
        <style>
        @keyframes skeleton-pulse {{
            0%, 100% {{ opacity: 0.3; transform: scaleX(0.9); }}
            50% {{ opacity: 1; transform: scaleX(1); }}
        }}
        @keyframes dot-bounce {{
            0%, 80%, 100% {{ transform: scale(0.6); opacity: 0.4; }}
            40% {{ transform: scale(1); opacity: 1; }}
        }}
        @keyframes icon-float {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-6px); }}
        }}
        </style>
    </div>"""


def estimate_model_load_time(model_name: str = "", model_type: str = "vc") -> str:
    """根据模型大小和硬件信息预估加载时间

    Returns:
        预计时间字符串，如 "约 5-10 秒"
    """
    try:
        base_time = {"vc": 3, "separator": 8, "dereverb": 5, "automix": 2}.get(
            model_type, 5
        )

        if model_name:
            pth_path = (
                os.path.join(weight_root, model_name)
                if not os.path.isabs(model_name)
                else model_name
            )
            if os.path.exists(pth_path):
                size_mb = os.path.getsize(pth_path) / (1024 * 1024)
                if size_mb > 100:
                    base_time += int(size_mb / 50)
                elif size_mb > 50:
                    base_time += 3

        gpu_mem_mb = 0
        try:
            if torch.cuda.is_available():
                gpu_mem_mb = torch.cuda.get_device_properties(0).total_memory / (
                    1024 * 1024
                )
        except Exception:
            pass

        if gpu_mem_mb > 8000:
            base_time = max(2, base_time - 2)
        elif gpu_mem_mb < 4000:
            base_time = base_time + 5

        import platform as _plat

        if _plat.system() == "Windows":
            base_time += 1

        low = max(1, int(base_time * 0.6))
        high = base_time + 3
        if high < 60:
            return f"约 {low}-{high} 秒"
        elif high < 120:
            return f"约 {low // 60}-{high // 60} 分钟"
        else:
            return f"约 {low}-{high} 秒（首次加载较慢）"
    except Exception:
        return "约 5-15 秒"


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
        return _progress_html(
            pct, step, detail, tip=tip, elapsed=elapsed, remaining=remaining
        )

    def _elapsed():
        return _time.time() - _t0

    _do_deverb = do_dereverb  # 局部副本，链式管线已去混响时设为 False

    if not audio_paths_text:
        yield _p(0, "请检查", "请上传音频文件"), "", None, None
        return

    raw = audio_paths_text
    if isinstance(raw, list):
        items = []
        for item in raw:
            if item is None:
                continue
            if isinstance(item, str):
                items.append(item)
            elif hasattr(item, "name"):
                n = getattr(item, "name", "")
                if n:
                    items.append(str(n))
            else:
                items.append(str(item))
        all_paths = [p.strip() for p in items if p.strip()]
    elif isinstance(raw, str):
        all_paths = [p.strip() for p in raw.strip().split("\n") if p.strip()]
    else:
        n = getattr(raw, "name", "")
        all_paths = [str(n)] if n else []
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
    sep_base_dir = _SEP_CACHE_ROOT
    os.makedirs(sep_base_dir, exist_ok=True)

    total = len(all_paths)
    steps_per_song = int(do_separate) + int(do_dereverb)
    total_steps = total * steps_per_song

    def _check_cache(base_name, need_sep=False, need_deverb=False):
        cached = {"vocal": None, "instr": None}
        if need_sep:
            vocal_path = os.path.join(
                sep_base_dir, generate_save_filename("", base_name, "干声")
            )
            instr_path = os.path.join(
                sep_base_dir, generate_save_filename("", base_name, "伴奏")
            )
            if not os.path.exists(vocal_path):
                legacy_vocal = os.path.join(sep_base_dir, f"{base_name} (Vocals).wav")
                if os.path.exists(legacy_vocal):
                    vocal_path = legacy_vocal
            if not os.path.exists(instr_path):
                legacy_instr = os.path.join(
                    sep_base_dir, f"{base_name} (Instrumental).wav"
                )
                if os.path.exists(legacy_instr):
                    instr_path = legacy_instr
            if os.path.exists(vocal_path):
                cached["vocal"] = vocal_path
            if os.path.exists(instr_path):
                cached["instr"] = instr_path
        if need_deverb:
            clean_path = os.path.join(
                sep_base_dir, generate_save_filename("", base_name, "去混响干声")
            )
            if not os.path.exists(clean_path):
                legacy_clean = os.path.join(sep_base_dir, f"{base_name} (Clean).wav")
                if os.path.exists(legacy_clean):
                    clean_path = legacy_clean
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
                _sep_est = estimate_model_load_time(model_type="separator")
                _sep_skel = skeleton_loading_html(
                    "加载音频分离引擎",
                    "Kim Vocal → 去混响 → Karaoke 伴奏",
                    _sep_est,
                    "separator",
                )
                yield _sep_skel, "正在加载分离模型...", None, None
                # 根据用户选择动态构建 stages
                chain_stages = ["kim_vocal", "karaoke"]
                if _do_deverb:
                    chain_stages.insert(1, "deverb")
                try:
                    chained_sep = create_chained_separator(stages=chain_stages)
                    if len(chained_sep._loaded_stages) >= 1:
                        sep = chained_sep
                        chain_has_deverb = "deverb" in chained_sep._loaded_stages
                        print_status(
                            f"✂️  链式分离管线就绪，已加载: {chained_sep._loaded_stages} (去混响={'✓' if chain_has_deverb else '✗'})",
                            "sep",
                        )
                        if _do_deverb and not chain_has_deverb:
                            print_status(
                                f"⚠️  链式管线中 deverb stage 未加载成功，将使用独立去混响模块",
                                "warning",
                            )
                    else:
                        chained_sep = None
                        raise RuntimeError("链式管线加载失败")
                except Exception as _ce:
                    print_status(f"⚠️  链式分离管线不可用，切换到单模型模式", "warning")
                    chained_sep = None
                    sep = SeparatorModel(model_type="mel_band_roformer")
                    sep.load()
            # 去混响模块：当需要去混响 且 (链式未包含deverb 或 链式deverb失败) 时加载
            need_standalone_deverb = _do_deverb and (
                chained_sep is None or not chain_has_deverb
            )
            if need_standalone_deverb:
                _dv_est = estimate_model_load_time(model_type="dereverb")
                _dv_skel = skeleton_loading_html(
                    "加载去混响模块",
                    "BS-Roformer 去混响模型，消除录音环境回声",
                    _dv_est,
                    "separator",
                )
                yield _dv_skel, "正在加载去混响模型...", None, None
                dereverb_sep = SeparatorModel(model_type="bs_roformer")
                if not dereverb_sep.load():
                    print_status(
                        f"⚠️ 独立去混响模型加载失败，将依赖链式管线去混响", "warning"
                    )
                    dereverb_sep = None
                else:
                    print_status(f"🔇 独立去混响模块就绪", "sep")

        model_load_time = _elapsed()

        for idx, audio_path in enumerate(all_paths):
            _do_deverb = do_dereverb
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
            yield (
                _p(
                    song_pct,
                    f"[{idx + 1}/{total}] {base_name}",
                    f"开始{task_desc}...",
                    elapsed=_elapsed(),
                    remaining=est_remain,
                ),
                "",
                last_vocal,
                last_instr,
            )

            current_vocal = None
            current_instr = None

            # ---- 缓存检查：已处理文件直接复用 ----
            cache_hit = False
            sep_cache_hit = False
            cached = _check_cache(
                base_name, need_sep=do_separate, need_deverb=_do_deverb
            )
            if do_separate and (cached["vocal"] or cached["instr"]):
                if cached["vocal"]:
                    current_vocal = cached["vocal"]
                    msgs.append(
                        f"  📦 人声(缓存) -> {os.path.basename(cached['vocal'])}"
                    )
                if cached["instr"]:
                    current_instr = cached["instr"]
                    msgs.append(
                        f"  📦 伴奏(缓存) -> {os.path.basename(cached['instr'])}"
                    )
                sep_cache_hit = True
                print_status(
                    f"📦 [{idx + 1}/{total}] {base_name}: 命中分离缓存", "info"
                )
                step_count += int(do_separate)
            if _do_deverb:
                clean_path = os.path.join(
                    sep_base_dir, generate_save_filename("", base_name, "去混响干声")
                )
                if os.path.exists(clean_path):
                    current_vocal = clean_path
                    msgs.append(
                        f"  📦 去混响干声(缓存) -> {os.path.basename(clean_path)}"
                    )
                    print_status(
                        f"📦 [{idx + 1}/{total}] {base_name}: 命中去混响缓存，跳过",
                        "info",
                    )
                    _do_deverb = False
                    cache_hit = True
                elif not sep_cache_hit:
                    pass
                else:
                    print_status(
                        f"📦 [{idx + 1}/{total}] {base_name}: 分离缓存命中但无去混响缓存，将继续去混响",
                        "info",
                    )

            # ---- 只去混响时：设置原始音频为 current_vocal ----
            if _do_deverb and not do_separate and not cache_hit and not current_vocal:
                current_vocal = audio_path
                print_status(
                    f"🔧 [{idx + 1}/{total}] {base_name}: 直接对原始音频去混响", "info"
                )

            # ---- Step 1: 人声分离 ----
            if do_separate and not cache_hit:
                if sep is None:
                    msgs.append(f"  分离模块不可用，跳过")
                elif isinstance(sep, ChainedSeparator):
                    # 链式分离管线：kim_vocal → deverb → karaoke
                    sep_pct = (
                        int(((step_count + 0.5) / total_steps) * 100)
                        if total_steps
                        else 0
                    )
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    use_deverb_stage = _do_deverb  # 如果用户勾选了去混响，在管线中启用
                    yield (
                        _p(
                            sep_pct,
                            f"[{idx + 1}/{total}] {base_name}",
                            "正在链式分离 (Kim→去混响→Karaoke)...",
                            elapsed=_elapsed(),
                            remaining=est_remain,
                        ),
                        "",
                        last_vocal,
                        last_instr,
                    )
                    _step_t = _time.time()
                    sep_out = os.path.join(sep_base_dir, f"_{base_name}_sep_tmp")
                    result = sep.separate(
                        audio_path,
                        sep_out,
                        use_kim_vocal=True,
                        use_deverb=use_deverb_stage,
                        use_karaoke=True,
                    )

                    if result.vocals and os.path.exists(result.vocals):
                        saved_vocal = os.path.join(
                            sep_base_dir, generate_save_filename("", base_name, "干声")
                        )
                        shutil.copy2(result.vocals, saved_vocal)
                        current_vocal = saved_vocal
                        
                    if result.other and os.path.exists(result.other):
                        saved_instr = os.path.join(
                            sep_base_dir, generate_save_filename("", base_name, "伴奏")
                        )
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
                        _do_deverb = False
                        print_status(
                            f"✅ [{idx + 1}/{total}] {base_name}: 链式管线已完成去混响",
                            "success",
                        )
                        if saved_vocal and os.path.exists(saved_vocal):
                            saved_clean = os.path.join(
                                sep_base_dir,
                                generate_save_filename("", base_name, "去混响干声"),
                            )
                            shutil.copy2(saved_vocal, saved_clean)
                            msgs.append(
                                f"  去混响干声 -> {os.path.basename(saved_clean)}"
                            )
                    elif use_deverb_stage:
                        # 用户勾选了去混响但链式管线 deverb stage 没加载，需要后续独立处理
                        print_status(
                            f"⚠️ [{idx + 1}/{total}] {base_name}: 链式去混响未加载，将使用独立模块",
                            "warning",
                        )
                else:
                    sep_pct = (
                        int(((step_count + 0.5) / total_steps) * 100)
                        if total_steps
                        else 0
                    )
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    yield (
                        _p(
                            sep_pct,
                            f"[{idx + 1}/{total}] {base_name}",
                            "正在分离人声...",
                            elapsed=_elapsed(),
                            remaining=est_remain,
                        ),
                        "",
                        last_vocal,
                        last_instr,
                    )
                    _step_t = _time.time()
                    sep_out = os.path.join(sep_base_dir, f"_{base_name}_sep_tmp")
                    result = sep.separate(
                        audio_path, sep_out, instruments=["vocals", "other"]
                    )

                    if result.vocals and os.path.exists(result.vocals):
                        saved_vocal = os.path.join(
                            sep_base_dir, generate_save_filename("", base_name, "干声")
                        )
                        shutil.copy2(result.vocals, saved_vocal)
                        current_vocal = saved_vocal
                        
                    if result.other and os.path.exists(result.other):
                        saved_instr = os.path.join(
                            sep_base_dir, generate_save_filename("", base_name, "伴奏")
                        )
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
                    msgs.append(
                        f"  ⚠️ 去混响模块未加载，跳过（可能链式管线已包含去混响）"
                    )
                    print_status(
                        f"⚠️ [{idx + 1}/{total}] {base_name}: 去混响模块不可用",
                        "warning",
                    )
                elif not current_vocal:
                    msgs.append(f"  ⚠️ 无干声输入，跳过去混响")
                    print_status(
                        f"⚠️ [{idx + 1}/{total}] {base_name}: 无干声输入，无法去混响",
                        "warning",
                    )
                else:
                    dereverb_pct = (
                        int(((step_count + 0.5) / total_steps) * 100)
                        if total_steps
                        else 0
                    )
                    remain_steps = total_steps - step_count
                    est_remain = avg_step_time * remain_steps
                    yield (
                        _p(
                            dereverb_pct,
                            f"[{idx + 1}/{total}] {base_name}",
                            "正在去除混响...",
                            elapsed=_elapsed(),
                            remaining=est_remain,
                        ),
                        "",
                        last_vocal,
                        last_instr,
                    )
                    _step_t = _time.time()
                    input_for_dereverb = current_vocal if current_vocal else audio_path

                    dereverb_out = os.path.join(sep_base_dir, f"_{base_name}_deref_tmp")
                    d_result = dereverb_sep.separate(
                        input_for_dereverb,
                        dereverb_out,
                        instruments=["vocals", "other"],
                    )

                    if d_result.vocals and os.path.exists(d_result.vocals):
                        saved_clean = os.path.join(
                            sep_base_dir,
                            generate_save_filename("", base_name, "去混响干声"),
                        )
                        shutil.copy2(d_result.vocals, saved_clean)
                        current_vocal = saved_clean
                        msgs.append(f"  去混响干声 -> {saved_clean}")

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
            time_str = f"{total_time / 60:.1f} 分钟"

        msgs.insert(0, "")
        msgs.insert(1, "=" * 40)
        msgs.insert(2, f"批量处理完成 ({total} 首，耗时 {time_str})")
        msgs.insert(3, f"输出目录: {os.path.abspath(sep_base_dir)}")

        yield (
            _p(
                100,
                "处理完成",
                f"共 {total} 首 · 耗时 {time_str}",
                elapsed=total_time,
                remaining=0,
            ),
            "\n".join(msgs),
            last_vocal,
            last_instr,
        )

    except Exception as e:
        msgs.append(f"处理出错: {str(e)}")
        import traceback

        traceback.print_exc()
        yield (
            _p(0, "处理出错", str(e), elapsed=_elapsed()),
            "\n".join(msgs),
            last_vocal,
            last_instr,
        )


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
        if not _acquire_exec("full_pipeline", "全流程"):
            yield (
                _progress_html(0, "⚠️ 执行中", "当前有全流程任务正在运行"),
                None,
                None,
                None,
                "",
            )
            return
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        out_dir = get_output_dir("cover", model_name)
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

        _lt = _LiveTaskCtx(f"🚀 全流程 · {base_name}", "full_pipeline")
        total_weight = sum(w for _, w in steps)

        def _progress(idx, detail="", tip=""):
            done = sum(w for _, w in steps[:idx])
            pct = done / total_weight * 100 if total_weight > 0 else 0
            step_name = steps[idx][0] if idx < len(steps) else "完成"
            return _progress_html(
                pct,
                f"Step {idx + 1}/{len(steps)}: {step_name}",
                detail,
                tip=tip,
                elapsed=_elapsed(),
            )

        try:
            import shutil
            import librosa as _librosa
            import soundfile as _sf

            # ---- Step: 人声分离 ----
            if do_separate:
                existing = find_existing_processed_files(model_name, base_name)
                if existing["deverb_vocal"]:
                    current_vocal = existing["deverb_vocal"]
                    do_dereverb = False
                    print_status(
                        f"📦 {base_name}: 复用已去混响干声，跳过分离和去混响", "info"
                    )
                    steps = [
                        (n, w) for n, w in steps if n not in ("人声分离", "去混响")
                    ]
                    if steps:
                        total_weight = sum(w for _, w in steps)
                    if existing["instr"]:
                        current_instr = existing["instr"]
                elif existing["vocal"]:
                    current_vocal = existing["vocal"]
                    print_status(f"📦 {base_name}: 复用干声，跳过分离", "info")
                    steps = [(n, w) for n, w in steps if n != "人声分离"]
                    if steps:
                        total_weight = sum(w for _, w in steps)
                    if existing["instr"]:
                        current_instr = existing["instr"]

            if do_separate and not current_vocal:
                _lt.update(0, "人声分离中...")
                _update_task_name("full_pipeline", "分离: " + base_name)
                yield (
                    _progress(
                        0,
                        "正在分离人声...",
                        tip="使用链式分离管线: Kim人声→去混响→Karaoke伴奏",
                    ),
                    None,
                    None,
                    None,
                )
                if _has_separator:
                    sep_out = os.path.join(out_dir, f"{base_name}_sep")
                    use_deverb_in_chain = do_dereverb
                    try:
                        chained = create_chained_separator(
                            stages=["kim_vocal", "deverb", "karaoke"]
                        )
                        if len(chained._loaded_stages) >= 1:
                            result = chained.separate(
                                audio_path,
                                sep_out,
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
                        print_status(
                            f"⚠️  翻唱链式管线不可用，切换到单模型分离", "warning"
                        )
                        sep = SeparatorModel(model_type="mel_band_roformer")
                        sep.load()
                        result = sep.separate(
                            audio_path, sep_out, instruments=["vocals", "other"]
                        )
                        if result.vocals and os.path.exists(result.vocals):
                            current_vocal = result.vocals
                        if result.other and os.path.exists(result.other):
                            current_instr = result.other
                        del sep
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                else:
                    _lt.update(0, "分离模块不可用")
                    _update_task_name("full_pipeline", "分离不可用")
                    yield _progress(0, "分离模块不可用"), None, None, None

            step_idx = 1

            # ---- Step: 去混响 ----
            if do_dereverb:
                _lt.update(15, "去混响中...")
                _update_task_name("full_pipeline", "去混响: " + base_name)
                yield (
                    _progress(
                        step_idx, "正在去除混响...", tip="正在加载去混响模型，首次较慢"
                    ),
                    None,
                    None,
                    None,
                )
                if _has_separator and current_vocal:
                    dereverb_sep = SeparatorModel(model_type="bs_roformer")
                    dereverb_sep.load()
                    d_out = os.path.join(out_dir, f"{base_name}_dereverb")
                    d_result = dereverb_sep.separate(
                        current_vocal,
                        d_out,
                        instruments=["vocals", "other"],
                    )
                    if d_result.vocals and os.path.exists(d_result.vocals):
                        dv = os.path.join(
                            out_dir,
                            generate_save_filename(model_name, base_name, "去混响干声"),
                        )
                        shutil.copy2(d_result.vocals, dv)
                        current_vocal = dv
                    del dereverb_sep
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                step_idx += 1

            # ---- Step: 变调 ----
            if do_pitch_shift and pitch_steps != 0:
                _lt.update(25, f"变调 {pitch_steps:+d} 半音")
                _update_task_name("full_pipeline", f"变调{pitch_steps:+d}: " + base_name)
                yield (
                    _progress(step_idx, f"正在变调 {pitch_steps:+d} 半音..."),
                    None,
                    None,
                    None,
                )
                input_p = current_vocal or audio_path
                p_out = os.path.join(
                    out_dir,
                    generate_save_filename(
                        model_name, base_name, f"变调{pitch_steps:+d}半音"
                    ),
                )
                try:
                    from audio_tools.vocoder import pitch_shift_audio

                    pitch_shift_audio(input_p, p_out, pitch_steps, "librosa")
                    current_vocal = p_out
                except Exception as e:
                    _lt.update(25, f"变调失败: {e}")
                    _update_task_name("full_pipeline", "变调失败")
                    yield _progress(step_idx, f"变调失败: {e}"), None, None, None
                step_idx += 1

            # ---- Step: 音色转换 ----
            if do_vc:
                _lt.update(35, f"音色转换 ({model_name})")
                _update_task_name("full_pipeline", "转换: " + model_label)
                yield (
                    _progress(step_idx, f"正在音色转换 ({model_name})..."),
                    None,
                    None,
                    None,
                )
            vc_input = current_vocal or audio_path
            if model_name and vc_input:
                try:
                    _f0_up = int(float(vc_transform_single_value)) if vc_transform_single_value is not None else 0
                    vc_result = get_vc().vc_single(
                        0,
                        vc_input,
                        _f0_up,
                        None,
                        "rmvpe",
                        "",
                        None,
                        0.75,
                        3,
                        0,
                        1.0,
                        0.33,
                    )
                    if (
                        vc_result
                        and isinstance(vc_result, tuple)
                        and len(vc_result) == 2
                    ):
                        info_msg, audio_data = vc_result
                        if (
                            audio_data
                            and isinstance(audio_data, tuple)
                            and len(audio_data) == 2
                        ):
                            sr, audio_arr = audio_data
                            vc_out = os.path.join(
                                out_dir,
                                generate_save_filename(model_name, base_name, "干声"),
                            )
                            _sf.write(vc_out, audio_arr, sr)
                            current_vocal = vc_out
                except Exception as e:
                    _lt.update(35, f"转换失败: {e}")
                    _update_task_name("full_pipeline", "转换失败")
                    yield _progress(step_idx, f"音色转换失败: {e}"), None, None, None
            else:
                _lt.update(35, "请先选择模型")
                _update_task_name("full_pipeline", "无模型")
                yield _progress(step_idx, "请先选择模型"), None, None, None
            step_idx += 1

            # ---- Step: 混音 ----
            if do_mix and current_vocal and current_instr:
                _lt.update(65, "混音中...")
                _update_task_name("full_pipeline", "混音: " + base_name)
                yield _progress(step_idx, "正在混音..."), None, None, None
                try:
                    from audio_tools.mixer_model import MixerModel

                    mixer = MixerModel()
                    mixed, mix_sr = mixer.mix_files(
                        [current_vocal, current_instr],
                        volumes=[vocal_vol, inst_vol],
                    )
                    mix_out = os.path.join(
                        out_dir, generate_save_filename(model_name, base_name, "成品")
                    )
                    mixer.save(mix_out, mixed)
                    final_output = mix_out
                except Exception as e:
                    _lt.update(65, f"混音失败: {e}")
                    _update_task_name("full_pipeline", "混音失败")
                    yield _progress(step_idx, f"混音失败: {e}"), None, None, None
                step_idx += 1

            # ---- Step: 混响 ----
            if do_reverb:
                _lt.update(75, "添加混响中...")
                _update_task_name("full_pipeline", "混响: " + base_name)
                yield _progress(step_idx, "正在添加混响..."), None, None, None
                reverb_input = final_output or current_vocal
                if reverb_input:
                    try:
                        from audio_tools.mixer_model import MixerModel as MM

                        audio_r, sr_r = _librosa.load(reverb_input, sr=None)
                        mx = MM(sample_rate=sr_r)
                        reverbed = mx.apply_reverb(
                            audio_r, room_size=reverb_room, wet_level=reverb_wet
                        )
                        rev_out = os.path.join(
                            out_dir,
                            generate_save_filename(model_name, base_name, "成品_混响"),
                        )
                        _sf.write(rev_out, reverbed, sr_r)
                        final_output = rev_out
                    except Exception as e:
                        _lt.update(75, f"混响失败: {e}")
                        _update_task_name("full_pipeline", "混响失败")
                        yield _progress(step_idx, f"混响失败: {e}"), None, None, None
                step_idx += 1

            # ---- 完成 ----
            total_time = _elapsed()
            time_str = (
                f"{total_time:.1f}s" if total_time < 60 else f"{total_time / 60:.1f}min"
            )
            done_html = _progress_html(
                100,
                "全部完成",
                f"输出目录: {os.path.abspath(out_dir)} · 耗时 {time_str}",
                elapsed=total_time,
                remaining=0,
            )
            dl_html = build_download_html(
                final_output
                if (final_output and os.path.exists(final_output))
                else None,
                "⬇️ 下载全流程成品",
                "purple",
            )
            _lt.update(100, "✅ 全部完成")
            _update_task_name("full_pipeline", "完成: " + base_name)
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
    # 使用Soft主题作为基础，支持系统深色模式自动切换
    theme = gr.themes.Soft(
        font=['XiaChanYuanTi', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        font_mono=['SF Mono', 'Consolas', 'monospace'],
        primary_hue=gr.themes.colors.Violet,
        secondary_hue=gr.themes.colors.Purple,
        neutral_hue=gr.themes.colors.Slate,
        radius_size=gr.themes.radius_sizes.Large,
    ).set(
        # 通用设置 - 紫罗兰暮光主题
        body_background_fill="#f5f3ff",
        background_fill_primary="#ffffff",
        background_fill_secondary="#ede9fe",
        border_color_accent="#7c3aed",
        border_color_default="#ddd6fe",
        color_accent_soft="#ddd6fe",
        # 深色模式优化
        body_background_fill_dark="#1a0a2e",
        background_fill_primary_dark="#1e1538",
        background_fill_secondary_dark="#2d1b4e",
        border_color_accent_dark="#a78bfa",
        border_color_default_dark="#8b5cf6",
        color_accent_soft_dark="#c4b5fd",
    )
except AttributeError:
    # 旧版本Gradio不支持themes，使用默认主题
    theme = None




# ==================== >��� �S�RKmՋ��ShV ====================
_trigger_pressure_test = None

def set_pressure_test_trigger(trigger_fn):
    global _trigger_pressure_test
    _trigger_pressure_test = trigger_fn

def trigger_pressure_test():
    if _trigger_pressure_test is not None:
        try:
            _trigger_pressure_test()
        except Exception:
            pass
