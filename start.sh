#!/bin/bash
# ============================================================
# 🎤 AI 翻唱系统 — 一键启动
#    自动检测环境 → 安装缺失依赖 → 启动 Web UI
#
# 用法:
#   ./start.sh              # 默认端口 7860
#   ./start.sh 8080         # 指定端口
#   ./start.sh --share      # 生成 Gradio 公网链接
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
VENV_DIR="$PROJECT_DIR/.venv"

# Gradio/httpx reads proxy variables during import. Local Web UI must not be
# started through SOCKS proxies unless httpx[socks] is installed.
if [[ "$ALL_PROXY" == socks* || "$all_proxy" == socks* ]]; then
    unset ALL_PROXY
    unset all_proxy
fi
export NO_PROXY="127.0.0.1,localhost,::1${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"

# ── 颜色 ──────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# ── 解析参数 ──────────────────────────────────────
PORT=7860
SHARE=""
FORCE_CPU=0
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --share) SHARE="--share"; shift ;;
        --cpu) FORCE_CPU=1; shift ;;
        --listen) EXTRA_ARGS+=("--listen"); shift ;;
        [0-9]*) PORT="$1"; shift ;;
        *) EXTRA_ARGS+=("$1"); shift ;;
    esac
done

# ── 横幅 ──────────────────────────────────────────
clear 2>/dev/null || true
echo ""
echo -e "${PURPLE}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${PURPLE}${BOLD}║        🎤  AI 翻唱系统 — RVC + SVC 双引擎               ║${NC}"
echo -e "${PURPLE}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 检查/创建虚拟环境 ────────────────────────────
NEED_INSTALL=0
if [[ ! -f "$VENV_DIR/bin/python" ]]; then
    echo -e "${YELLOW}⚠️  虚拟环境不存在，正在安装...${NC}"
    echo ""
    NEED_INSTALL=1
fi

if [[ $NEED_INSTALL -eq 1 ]]; then
    bash "$PROJECT_DIR/install.sh"
    echo ""
fi

# ── 激活虚拟环境 ──────────────────────────────────
source "$VENV_DIR/bin/python" 2>/dev/null || source "$VENV_DIR/bin/activate"

# 快速验证核心依赖
python -c "
import sys
missing = []
for mod in ['torch', 'gradio', 'numpy', 'scipy', 'librosa', 'soundfile', 'fairseq']:
    try:
        __import__(mod)
    except ImportError:
        missing.append(mod)
if missing:
    print('MISSING:' + ','.join(missing))
    sys.exit(1)
" 2>/dev/null

if [[ $? -ne 0 ]]; then
    echo -e "${YELLOW}⚠️  部分依赖缺失，正在补装...${NC}"
    bash "$PROJECT_DIR/install.sh"
    echo ""
fi

# ── 设备 & 模型概况 ──────────────────────────────
echo -e "${CYAN}📱 设备概况${NC}"
python -c "
import torch, platform
mps = torch.backends.mps.is_available()
cuda = torch.cuda.is_available()
if mps:
    gpu = '✅ Apple MPS (GPU 加速)'
elif cuda:
    gpu = '✅ NVIDIA CUDA (GPU 加速)'
else:
    gpu = '⚠️  CPU 模式 (较慢)'
print(f'   系统: {platform.system()} {platform.release()} ({platform.machine()})')
print(f'   PyTorch: {torch.__version__}  |  {gpu}')
"

RVC_N=$(find "$PROJECT_DIR/rvc/assets/weights" -name "*.pth" 2>/dev/null | wc -l | tr -d ' ')
SVC_N=$(find "$PROJECT_DIR/so-vits-svc" -name "G_*.pth" 2>/dev/null | wc -l | tr -d ' ')
echo -e "   模型: RVC ${RVC_N} 个 + SVC ${SVC_N} 个"

# ── 端口检查 ──────────────────────────────────────
if lsof -Pi ":$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  端口 $PORT 被占用，自动切换...${NC}"
    for p in $(seq 7861 7870); do
        if ! lsof -Pi ":$p" -sTCP:LISTEN -t >/dev/null 2>&1; then
            PORT=$p; break
        fi
    done
fi

# ── 启动 ──────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║  🚀 启动 Web UI                                         ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "   ${CYAN}🌐 本地访问:${NC}  ${BOLD}http://127.0.0.1:${PORT}${NC}"
echo -e "   ${CYAN}📋 标签页:${NC}   一键翻唱 | RVC推理 | SVC推理 | 系统信息"
echo -e "   ${CYAN}📁 输出目录:${NC}  output/"
echo ""
echo -e "   ${YELLOW}💡 按 Ctrl+C 停止${NC}"
echo ""

# macOS 27+ MPS: 禁用内存上限防止 OOM，启用主动 GC 减少碎片
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0
export PYTORCH_MPS_ALLOCATOR_POLICY=garbage_collection
# MPS fallback: 不支持的算子回退 CPU，避免 segfault
export PYTORCH_ENABLE_MPS_FALLBACK=1
# 限制 CPU 线程数，减少与 MPS 的竞争导致 segfault
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export VECLIB_MAXIMUM_THREADS=4
export NUMEXPR_NUM_THREADS=4

if [[ "$FORCE_CPU" -eq 1 ]]; then
    export AI_COVER_DEVICE=cpu
    echo -e "   ${YELLOW}🧯 稳定模式:${NC}  已强制使用 CPU，速度会慢一些但可避开 MPS 闪退"
    echo ""
fi

cd "$PROJECT_DIR"
python app.py --port "$PORT" $SHARE "${EXTRA_ARGS[@]}"

APP_EXIT_CODE=$?
if [[ "$APP_EXIT_CODE" -ne 0 && "$FORCE_CPU" -ne 1 ]]; then
    echo ""
    echo -e "${YELLOW}如果刚才看到 Segmentation fault: 11，请重新打开桌面启动器并选择「稳定 CPU 模式」。${NC}"
fi

echo ""
echo -e "${YELLOW}👋 AI 翻唱系统已停止${NC}"
echo ""
