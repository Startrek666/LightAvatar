#!/bin/bash
#
# 模型下载脚本
# 用法: bash download_models.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否在项目根目录
if [ ! -f "requirements.txt" ]; then
    echo_error "请在项目根目录运行此脚本"
    exit 1
fi

# 激活虚拟环境
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo_error "虚拟环境不存在，请先运行 python3.11 -m venv venv"
    exit 1
fi

echo_info "==================================="
echo_info "模型下载脚本"
echo_info "==================================="
echo ""

# 1. 下载Whisper模型
echo_info "1. 下载Whisper ASR模型"
echo ""
echo "可选模型大小："
echo "  1) tiny   - 最快，准确率较低 (~75MB)"
echo "  2) base   - 平衡 (~150MB)"
echo "  3) small  - 推荐 (~470MB) [默认]"
echo "  4) medium - 高准确率 (~1.5GB)"
echo "  5) large-v3 - 最高准确率 (~3GB)"
echo ""
read -p "请选择模型 [1-5] (默认3): " whisper_choice

case $whisper_choice in
    1) WHISPER_MODEL="tiny" ;;
    2) WHISPER_MODEL="base" ;;
    3|"") WHISPER_MODEL="small" ;;
    4) WHISPER_MODEL="medium" ;;
    5) WHISPER_MODEL="large-v3" ;;
    *) echo_error "无效选择"; exit 1 ;;
esac

echo_info "正在下载 Whisper $WHISPER_MODEL 模型..."

python << EOF
from faster_whisper import WhisperModel
import sys

try:
    print("下载中，请稍候...")
    model = WhisperModel("$WHISPER_MODEL", device="cpu", compute_type="int8", download_root="./models/whisper")
    print("✓ Whisper模型下载完成！")
except Exception as e:
    print(f"✗ 下载失败: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo_error "Whisper模型下载失败"
    exit 1
fi

# 2. 下载Wav2Lip模型
echo ""
echo_info "2. 下载Wav2Lip模型"
echo ""

mkdir -p models/wav2lip
cd models/wav2lip

if [ -f "wav2lip.pth" ]; then
    echo_warn "wav2lip.pth 已存在，跳过下载"
else
    echo_info "正在下载 Wav2Lip PyTorch模型..."
    
    # 尝试多个下载源（按优先级）
    DOWNLOADED=false
    
    # 源1: HuggingFace numz/wav2lip_studio (推荐)
    echo_info "尝试从 HuggingFace (numz/wav2lip_studio) 下载..."
    if wget -O wav2lip.pth "https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2lip/wav2lip.pth"; then
        echo_info "✓ Wav2Lip模型下载完成 (HuggingFace)"
        DOWNLOADED=true
    fi
    
    # 源2: HuggingFace camenduru/Wav2Lip (备用)
    if [ "$DOWNLOADED" = false ]; then
        echo_warn "源1失败，尝试备用源2..."
        if wget -O wav2lip.pth "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip.pth"; then
            echo_info "✓ Wav2Lip模型下载完成 (备用源2)"
            DOWNLOADED=true
        fi
    fi
    
    # 源3: 官方OneDrive (需要手动)
    if [ "$DOWNLOADED" = false ]; then
        echo_error "所有自动下载源均失败"
        echo ""
        echo "请手动下载 wav2lip.pth 并放置到 models/wav2lip/ 目录"
        echo ""
        echo "可用下载地址:"
        echo "  1. HuggingFace: https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2lip/wav2lip.pth"
        echo "  2. 官方OneDrive: https://iiitaphyd-my.sharepoint.com/:u:/g/personal/radrabha_m_research_iiit_ac_in/Eb3LEzbfuKlJiR600lQWRxgBIY27JZg80f7V9jtMfbNDaQ"
        echo ""
    fi
fi

cd ../..

# 3. 检查模型文件
echo ""
echo_info "==================================="
echo_info "模型文件检查"
echo_info "==================================="
echo ""

echo "Whisper模型目录:"
ls -lh models/whisper/ 2>/dev/null || echo "  (空)"

echo ""
echo "Wav2Lip模型:"
ls -lh models/wav2lip/*.pth 2>/dev/null || echo "  (未找到)"

echo ""
echo "Avatar模板:"
ls -lh models/avatars/ 2>/dev/null || echo "  (空)"

# 4. 提示后续步骤
echo ""
echo_info "==================================="
echo_info "下一步操作"
echo_info "==================================="
echo ""
echo "✓ Whisper模型已下载"
echo "✓ Wav2Lip模型已下载"
echo ""
echo "待完成:"
echo "  1. 准备Avatar模板视频/图片"
echo "     - 将数字人视频(MP4)或图片(JPG/PNG)放到 models/avatars/"
echo "     - 建议尺寸: 512x512像素"
echo "     - 命名为: default.mp4 或 default.jpg"
echo ""
echo "  2. 如需转换Wav2Lip为ONNX格式（可选，提升性能）："
echo "     - 运行: python scripts/convert_wav2lip_to_onnx.py"
echo ""
echo "  3. 配置文件："
echo "     - 编辑 config/config.yaml"
echo "     - 设置LLM API地址和Key"
echo ""

echo_info "模型下载完成！"
