#!/bin/bash
# RVC AI翻唱 - Mac (Apple Silicon) 安装脚本
# 自动安装 Miniconda（如需要）并配置环境

set -e

echo "================================================"
echo "  RVC AI翻唱系统 - Mac Apple Silicon 安装"
echo "================================================"

# 检查是否在 Apple Silicon 上运行
if [[ "$(uname -m)" != "arm64" ]]; then
    echo "⚠️  警告: 当前不是 Apple Silicon Mac。MPS GPU 加速仅在 M1/M2/M3/M4 芯片上可用。"
    echo "   将继续使用 CPU 模式安装。"
fi

# 检查 Python 版本
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "✅ 找到 python3 $PY_VERSION"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PY_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "✅ 找到 python $PY_VERSION"
    PYTHON_CMD="python"
else
    echo "❌ 未找到 Python。请先安装 Python 3.9+ 或 Miniconda。"
    echo "   推荐: brew install python@3.11"
    exit 1
fi

# 创建虚拟环境（可选）
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 创建 Python 虚拟环境..."
    $PYTHON_CMD -m venv venv
    echo "✅ 虚拟环境创建完成"
fi

# 激活虚拟环境
echo ""
echo "🔄 激活虚拟环境..."
source venv/bin/activate

# 升级 pip
echo ""
echo "📦 升级 pip..."
pip install --upgrade pip -q

# 安装 PyTorch (带 MPS 支持)
echo ""
echo "📦 安装 PyTorch (Apple Silicon MPS 支持)..."
pip install torch torchaudio -q

# 验证 MPS 可用性
echo ""
echo "🔍 验证 MPS (Metal Performance Shaders) 可用性..."
python3 -c "
import torch
if torch.backends.mps.is_available():
    print('✅ MPS 可用！推理将使用 Apple GPU 加速。')
    device = torch.device('mps')
    x = torch.zeros(1).to(device)
    print('✅ MPS 设备测试通过。')
else:
    print('⚠️  MPS 不可用，将使用 CPU 模式。')
    print('   请确保:')
    print('   1. macOS 12.3 或更高版本')
    print('   2. PyTorch 2.0 或更高版本')
    print('   3. Apple Silicon (M1/M2/M3/M4) 芯片')
"

# 安装其他依赖
echo ""
echo "📦 安装其他 Python 依赖..."
pip install numpy scipy librosa soundfile -q
pip install pyworld praat-parselmouth torchcrepe -q
pip install fairseq faiss-cpu scikit-learn -q
pip install onnxruntime -q
pip install gradio -q
pip install resampy tqdm pyyaml python-dotenv matplotlib tensorboard -q

echo ""
echo "================================================"
echo "  ✅ 安装完成！"
echo "================================================"
echo ""
echo "🚀 启动 Web UI (推理):"
echo "   source venv/bin/activate"
echo "   python infer-web.py"
echo ""
echo "🚀 命令行推理:"
echo "   source venv/bin/activate"
echo "   python tools/infer_cli.py --input_path <音频文件> --model_name <模型名> --opt_path <输出文件>"
echo ""
echo "📁 模型文件放在: assets/weights/"
echo "📁 索引文件放在: assets/indices/ 或 logs/"
echo ""
