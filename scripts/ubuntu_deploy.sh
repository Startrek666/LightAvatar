#!/bin/bash
#
# Lightweight Avatar Chat - Ubuntu自动部署脚本
# 用法: sudo bash ubuntu_deploy.sh
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo_error "请使用sudo运行此脚本"
    exit 1
fi

echo_info "开始部署 Lightweight Avatar Chat..."

# 1. 更新系统
echo_info "步骤 1/10: 更新系统..."
apt update && apt upgrade -y

# 2. 安装系统依赖
echo_info "步骤 2/10: 安装系统依赖..."
apt install -y wget curl git vim build-essential
apt install -y ffmpeg
apt install -y libsndfile1 libsndfile1-dev portaudio19-dev libasound2-dev
apt install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev

# 3. 安装Python 3.11
echo_info "步骤 3/10: 安装Python 3.11..."
if ! command -v python3.11 &> /dev/null; then
    add-apt-repository ppa:deadsnakes/ppa -y
    apt update
    apt install -y python3.11 python3.11-venv python3.11-dev
fi

python3.11 --version

# 4. 克隆项目
echo_info "步骤 4/10: 克隆项目..."
INSTALL_DIR="/opt/lightavatar"
if [ -d "$INSTALL_DIR" ]; then
    echo_warn "目录 $INSTALL_DIR 已存在，跳过克隆"
else
    mkdir -p $INSTALL_DIR
    cd /opt
    git clone https://github.com/Startrek666/LightAvatar.git lightavatar
fi

cd $INSTALL_DIR

# 5. 创建Python虚拟环境
echo_info "步骤 5/10: 创建虚拟环境..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi

source venv/bin/activate

# 6. 安装Python依赖
echo_info "步骤 6/10: 安装Python依赖（这可能需要10-15分钟）..."
pip install --upgrade pip
pip install -r requirements.txt

# 7. 创建模型目录
echo_info "步骤 7/10: 创建模型目录..."
mkdir -p models/whisper
mkdir -p models/wav2lip
mkdir -p models/avatars
mkdir -p logs

# 8. 下载Whisper模型
echo_info "步骤 8/10: 下载Whisper模型..."
cat > download_whisper.py << 'EOF'
from faster_whisper import WhisperModel
import sys

try:
    print("正在下载Whisper small模型...")
    model = WhisperModel("small", device="cpu", compute_type="int8", download_root="./models/whisper")
    print("下载完成！")
    sys.exit(0)
except Exception as e:
    print(f"下载失败: {e}")
    sys.exit(1)
EOF

python download_whisper.py
rm download_whisper.py

# 9. 安装Node.js
echo_info "步骤 9/10: 安装Node.js..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt install -y nodejs
fi

node --version
npm --version

# 10. 安装Nginx
echo_info "步骤 10/10: 安装Nginx..."
if ! command -v nginx &> /dev/null; then
    apt install -y nginx
fi

# 设置文件权限
echo_info "设置文件权限..."
chown -R www-data:www-data $INSTALL_DIR

# 创建日志目录
mkdir -p /var/log/lightavatar
chown www-data:www-data /var/log/lightavatar

echo_info ""
echo_info "============================================"
echo_info "基础环境安装完成！"
echo_info "============================================"
echo_info ""
echo_info "后续步骤："
echo_info "1. 下载Wav2Lip模型到 models/wav2lip/"
echo_info "2. 准备Avatar模板到 models/avatars/"
echo_info "3. 编辑配置文件: nano config/config.yaml"
echo_info "4. 构建前端: cd frontend && npm install && npm run build"
echo_info "5. 配置Nginx: nano /etc/nginx/sites-available/lightavatar"
echo_info "6. 创建systemd服务"
echo_info ""
echo_info "详细步骤请查看: docs/UBUNTU_DEPLOYMENT.md"
echo_info ""
