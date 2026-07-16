#!/bin/bash
# ============================================================
# 🎤 AI 翻唱系统 — 智能安装脚本
#    - 只安装缺失的依赖
#    - 所有包安装在项目内的 .venv/ 中
#    - 完全自包含，不污染系统 Python
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
VENV_DIR="$PROJECT_DIR/.venv"

# ── 颜色 ──────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}================================================${NC}"
echo -e "${BOLD}  🎤 AI 翻唱系统 — 智能安装${NC}"
echo -e "${BOLD}================================================${NC}"
echo ""

# ── 说明旧环境为何不能复用 ──────────────────────
echo -e "${YELLOW}💡 说明:${NC}"
echo "   RVC 原 runtime/ 目录是 Windows 版本 (python.exe + .dll)"
echo "   SVC 原 venv/   目录是 Windows 版本 (Scripts/ + Lib/)"
echo "   两者都无法在 macOS 上运行，需要新建 Mac 兼容环境。"
echo ""

# ── 查找系统 Python ──────────────────────────────
PYTHON_CMD=""
for py in python3.11 python3.10 python3.9 python3 python; do
    if command -v "$py" &> /dev/null; then
        PY_VER=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [[ "$PY_MAJOR" -ge 3 ]] && [[ "$PY_MINOR" -ge 9 ]]; then
            PYTHON_CMD="$py"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo "❌ 未找到 Python 3.9+，请先安装: brew install python@3.11"
    exit 1
fi

# ── 创建/复用虚拟环境 ────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
    echo -e "${CYAN}📦 创建虚拟环境 (.venv/)...${NC}"
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo -e "${GREEN}✅ 虚拟环境已创建${NC}"
else
    echo -e "${GREEN}✅ 虚拟环境已存在，复用${NC}"
fi

source "$VENV_DIR/bin/activate"

# ── 智能安装函数 ─────────────────────────────────
pip install --upgrade pip -q 2>&1 | tail -1

smart_install() {
    local pkg="$1"
    local import_name="${2:-$1}"
    # 去掉版本号，只取包名
    local pkg_name=$(echo "$pkg" | cut -d'>' -f1 | cut -d'<' -f1 | cut -d'=' -f1 | cut -d'!' -f1 | cut -d'~' -f1)
    local import_check=$(echo "$import_name" | cut -d'>' -f1 | cut -d'<' -f1 | cut -d'=' -f1 | cut -d'!' -f1 | cut -d'~' -f1)

    if python -c "import $import_check" 2>/dev/null; then
        echo -e "   ${GREEN}✅${NC} $pkg_name (已安装)"
        return 0
    else
        echo -e "   ${YELLOW}📦${NC} 安装 $pkg_name ..."
        pip install "$pkg" -q 2>&1 | tail -1
        return $?
    fi
}

echo ""
echo -e "${CYAN}🔍 检查并安装缺失的依赖...${NC}"
echo ""

# PyTorch — 最重要的
echo "── PyTorch ──"
if python -c "import torch; print(torch.__version__)" 2>/dev/null; then
    echo -e "   ${GREEN}✅ PyTorch $(python -c 'import torch; print(torch.__version__)') 已安装${NC}"
else
    echo -e "   ${YELLOW}📦 安装 PyTorch (Apple Silicon MPS 支持)...${NC}"
    pip install torch torchaudio -q
fi

# 验证 MPS
python -c "
import torch
mps = torch.backends.mps.is_available()
print(f'   {\"✅\" if mps else \"⚠️\"} MPS (Apple GPU): {\"可用\" if mps else \"不可用 — 使用 CPU\"}')"

echo ""
echo "── 音频处理 ──"
smart_install "numpy" "numpy"
smart_install "scipy" "scipy"
smart_install "librosa" "librosa"
smart_install "soundfile" "soundfile"
smart_install "resampy" "resampy"

echo ""
echo "── F0 音高提取 ──"
smart_install "pyworld" "pyworld"
smart_install "praat-parselmouth" "parselmouth"
smart_install "torchcrepe" "torchcrepe"

echo ""
echo "── 特征提取 ──"
smart_install "fairseq" "fairseq"
smart_install "faiss-cpu" "faiss"
smart_install "scikit-learn" "sklearn"

echo ""
echo "── ONNX Runtime ──"
smart_install "onnxruntime" "onnxruntime"

echo ""
echo "── Web UI ──"
smart_install "gradio" "gradio"

echo ""
echo "── 辅助依赖 ──"
smart_install "tqdm" "tqdm"
smart_install "pyyaml" "yaml"
smart_install "python-dotenv" "dotenv"
smart_install "matplotlib" "matplotlib"
smart_install "tensorboard" "tensorboard"
smart_install "transformers" "transformers"
smart_install "omegaconf" "omegaconf"

echo ""
echo "── 可选依赖 ──"
smart_install "pydub" "pydub" || true
smart_install "av" "av" || true
smart_install "ffmpeg-python" "ffmpeg" || true

# ── 创建目录 ──────────────────────────────────────
mkdir -p "$PROJECT_DIR/output" "$PROJECT_DIR/temp"

# ── 完成 ─────────────────────────────────────────
echo ""
echo -e "${BOLD}================================================${NC}"
echo -e "${GREEN}${BOLD}  ✅ 安装完成！${NC}"
echo -e "${BOLD}================================================${NC}"
echo ""
echo "  所有依赖在: .venv/ (项目内，完全自包含)"
echo "  输出目录:   output/"
echo ""
echo "  🚀 启动: ./start.sh"
echo ""
