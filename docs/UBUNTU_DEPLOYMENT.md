# Ubuntu服务器部署指南 - Lightweight Avatar Chat

> 🐧 详细的Ubuntu 20.04/22.04服务器部署步骤

---

## 🚀 快速开始（3分钟）

**如果你想快速部署，按以下步骤操作**：

```bash
# 1. 克隆项目
cd /opt && sudo mkdir lightavatar && sudo chown $USER:$USER lightavatar
git clone https://github.com/Startrek666/LightAvatar.git lightavatar && cd lightavatar

# 2. 一键安装环境
sudo bash scripts/ubuntu_deploy.sh

# 3. 下载AI模型
bash scripts/download_models.sh

# 4. 检查环境
python scripts/check_environment.py

# 5. 配置并启动（参考下方详细步骤）
nano config/config.yaml  # 配置LLM API
```

**详细步骤请继续阅读下方内容** ↓

---

## 📋 目录

1. [环境准备](#环境准备)
2. [系统依赖安装](#系统依赖安装)
3. [Python环境配置](#python环境配置)
4. [源码下载](#源码下载)
5. [模型准备](#模型准备)
6. [配置文件设置](#配置文件设置)
7. [后端部署](#后端部署)
8. [前端部署](#前端部署)
9. [Nginx配置](#nginx配置)
10. [系统服务配置](#系统服务配置)
11. [验证测试](#验证测试)
12. [常见问题](#常见问题)
13. [脚本使用说明](#脚本使用说明)

---

## 环境准备

### 1.1 服务器要求

**最低配置**：
- CPU: 4核心
- 内存: 8GB
- 硬盘: 50GB
- 系统: Ubuntu 20.04 / 22.04 LTS

**推荐配置**：
- CPU: 8核心
- 内存: 16GB
- 硬盘: 100GB
- 系统: Ubuntu 22.04 LTS

### 1.2 更新系统

```bash
# 更新软件包列表
sudo apt update

# 升级已安装的软件包
sudo apt upgrade -y

# 安装基础工具
sudo apt install -y wget curl git vim build-essential
```

---

## 系统依赖安装

### 2.1 安装FFmpeg

```bash
# FFmpeg用于视频编码
sudo apt install -y ffmpeg

# 验证安装
ffmpeg -version
```

### 2.2 安装音频处理库

```bash
# 安装音频处理相关库
sudo apt install -y libsndfile1 libsndfile1-dev
sudo apt install -y portaudio19-dev
sudo apt install -y libasound2-dev
```

### 2.3 安装OpenCV依赖

```bash
# OpenCV所需的系统库
sudo apt install -y libgl1-mesa-glx
sudo apt install -y libglib2.0-0
sudo apt install -y libsm6
sudo apt install -y libxext6
sudo apt install -y libxrender-dev
```

---

## Python环境配置

### 3.1 安装Python 3.11

```bash
# 添加deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# 安装Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 验证安装
python3.11 --version
```

### 3.2 安装pip

```bash
# 下载get-pip.py
curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py

# 使用Python 3.11安装pip
python3.11 get-pip.py

# 验证
python3.11 -m pip --version

# 清理
rm get-pip.py
```

---

## 源码下载

### 4.1 克隆项目

```bash
# 创建项目目录
cd /opt
sudo mkdir -p lightavatar
sudo chown $USER:$USER lightavatar
cd lightavatar

# 克隆源码
git clone https://github.com/Startrek666/LightAvatar.git .

# 查看项目结构
ls -la
```

### 4.2 创建Python虚拟环境

```bash
# 在项目目录创建虚拟环境
python3.11 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 验证Python版本
python --version  # 应显示Python 3.11.x
```

### 4.3 安装Python依赖

```bash
# 确保在虚拟环境中
source venv/bin/activate

# 升级pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 这个过程可能需要10-15分钟，请耐心等待
```

**常见安装问题**：
```bash
# 如果遇到编译错误，安装以下包
sudo apt install -y python3.11-dev gcc g++

# 如果numpy安装失败
pip install numpy==1.26.4 --no-cache-dir

# 如果onnxruntime安装失败
pip install onnxruntime==1.19.2 --no-cache-dir

# 如果需要使用联网搜索功能，确保安装正确的包
pip uninstall -y duckduckgo-search  # 卸载旧版本
pip install ddgs>=1.0.0              # 安装新版本
pip install trafilatura>=1.6.0       # 网页内容提取
```

---

## 模型准备

### 5.1 ASR (语音识别) 配置说明

**项目支持两种ASR方式，可根据实际情况选择**：

#### 方式一：Faster-Whisper 本地模型（推荐新手）
- ✅ 完全独立，不依赖外部服务
- ✅ 隐私性好，所有数据本地处理
- ✅ 配置简单
- ❌ 需要下载模型文件（470MB-3GB）
- ❌ 消耗本机CPU资源

#### 方式二：Skynet Whisper API（推荐已有服务）
- ✅ 无需下载模型，节省磁盘空间
- ✅ 不占用本机资源
- ✅ 可复用已部署的Whisper服务
- ✅ 支持多个应用共享一个服务
- ❌ 需要额外部署Skynet Whisper服务
- ❌ 依赖网络连接（建议内网）

**配置对比**：

| 特性 | Faster-Whisper | Skynet Whisper API |
|------|----------------|-------------------|
| 部署难度 | 简单 | 需单独部署服务 |
| 磁盘占用 | 470MB-3GB | 几乎为0 |
| CPU占用 | 中等 | 很低 |
| 网络依赖 | 无 | 需要（内网） |
| 适用场景 | 单机部署 | 多服务共享 |

**如何选择**：
- 如果你是**首次部署**，选择 `Faster-Whisper`（方式一）
- 如果你**已有Skynet Whisper服务**，选择 `Skynet API`（方式二）

### 5.2 创建模型目录

```bash
cd /opt/lightavatar

# 创建模型目录
mkdir -p models/whisper  # 仅Faster-Whisper需要
mkdir -p models/wav2lip
mkdir -p models/avatars
```

### 5.3 方式一：配置Faster-Whisper本地模型

**步骤1：下载模型**

```bash
# 激活虚拟环境
source venv/bin/activate

# 创建下载脚本
cat > download_whisper.py << 'EOF'
from faster_whisper import WhisperModel

# 下载small模型（推荐）
print("正在下载Whisper small模型...")
model = WhisperModel("small", device="cpu", compute_type="int8", download_root="./models/whisper")
print("下载完成！")
EOF

# 运行下载脚本
python download_whisper.py

# 验证模型文件
ls -lh models/whisper/
```

**可选模型大小**：
- `tiny` - 最快，准确率较低 (~75MB)
- `base` - 平衡 (~150MB)
- `small` - 推荐 (~470MB)
- `medium` - 高准确率 (~1.5GB)
- `large-v3` - 最高准确率 (~3GB)

**步骤2：配置使用**

在 `config/config.yaml` 中设置：

```yaml
# ASR设置
asr:
  backend: "faster-whisper"  # 使用本地模型
  language: "zh"

# Faster-Whisper配置
whisper:
  model: "small"  # 选择下载的模型大小
  device: "cpu"
  compute_type: "int8"
```

---

### 5.4 方式二：配置Skynet Whisper API

**如果你已经部署了Skynet Whisper服务，可以直接使用API方式**。

**步骤1：确认Skynet服务可用**

```bash
# 检查Skynet Whisper服务状态
sudo systemctl status skynet

# 或测试WebSocket连接
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     http://localhost:6010/streaming-whisper/ws/test
```

**步骤2：配置使用**

在 `config/config.yaml` 中设置：

```yaml
# ASR设置
asr:
  backend: "skynet"  # 使用Skynet API
  language: "zh"

# Skynet Whisper API配置
skynet_whisper:
  server_url: "ws://localhost:6010"  # Skynet服务地址
  participant_id: "avatar-user"       # 参与者ID
```

**步骤3：跳过Whisper模型下载**

使用Skynet API时，无需下载本地Whisper模型，可直接跳到第5.5节。

**API调用说明**：
- 项目已实现完整的Skynet Whisper API集成
- 自动处理WebSocket连接和数据格式
- 详细API文档见：`docs/Skynet-Whisper-API调用文档-简化版.md`

---

### 5.5 准备 Wav2Lip 环境

**重要**：Wav2Lip 需要两个部分：
1. **官方代码仓库**（包含模型架构定义）- 必需
2. **模型权重文件** - 必需

#### 步骤1：克隆官方 Wav2Lip 仓库（必需）

```bash
cd /opt/lightavatar

# 创建 tools 目录
mkdir -p tools
cd tools

# 克隆官方 Wav2Lip 仓库
git clone https://github.com/Rudrabha/Wav2Lip.git

# 验证文件结构
ls -la Wav2Lip/
# 应该看到：models/、face_detection/、wav2lip_train.py 等文件
```

**为什么需要克隆仓库？**
- Wav2Lip 模型架构定义在官方仓库中
- 包含人脸检测等依赖模块
- 我们的代码会从 `tools/Wav2Lip/models/` 导入模型定义

#### 步骤2：下载 Wav2Lip 模型权重

**方法一：使用HuggingFace（推荐）**

```bash
cd /opt/lightavatar/models/wav2lip

# 方案1: 从numz/wav2lip_studio下载（推荐）
wget -O wav2lip.pth "https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2lip/wav2lip.pth"

# 或方案2: 从camenduru/Wav2Lip下载
# wget -O wav2lip.pth "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip.pth"

# 验证下载
ls -lh wav2lip.pth
# 应该显示约 400MB
```

**方法二：使用官方OneDrive链接**

如果HuggingFace速度慢，可以使用官方OneDrive：

```bash
cd /opt/lightavatar/models/wav2lip

# 使用wget下载（可能需要手动访问链接获取直接下载URL）
# 官方链接: https://iiitaphyd-my.sharepoint.com/:u:/g/personal/radrabha_m_research_iiit_ac_in/Eb3LEzbfuKlJiR600lQWRxgBIY27JZg80f7V9jtMfbNDaQ

echo "如果自动下载失败，请在浏览器中访问上述链接手动下载"
```

**方法三：手动上传

如果自动下载失败，可以手动下载后上传：

**可用下载源**：
1. HuggingFace (推荐): https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2lip/wav2lip.pth
2. 官方OneDrive: https://iiitaphyd-my.sharepoint.com/:u:/g/personal/radrabha_m_research_iiit_ac_in/Eb3LEzbfuKlJiR600lQWRxgBIY27JZg80f7V9jtMfbNDaQ

**上传到服务器**：
```bash
# 在本地执行
scp wav2lip.pth user@your-server:/opt/lightavatar/models/wav2lip/
```

**使用脚本自动下载**：

项目中的 `scripts/download_models.sh` 已包含多个下载源，可以直接使用：

```bash
cd /opt/lightavatar
bash scripts/download_models.sh
# 选择 Wav2Lip 模型下载
```

#### 步骤3：设置文件权限

```bash
# 设置正确的所有者
sudo chown -R www-data:www-data /opt/lightavatar/tools/
sudo chown -R www-data:www-data /opt/lightavatar/models/

# 验证安装完整性
ls -lh /opt/lightavatar/tools/Wav2Lip/
ls -lh /opt/lightavatar/models/wav2lip/wav2lip.pth
```

**验证 Wav2Lip 安装**：

```bash
cd /opt/lightavatar
source venv/bin/activate

# 测试导入模型
python3 << 'EOF'
import sys
sys.path.append('tools/Wav2Lip')
from models import Wav2Lip
print("✓ Wav2Lip 模型架构导入成功")
EOF
```

### 5.6 转换Wav2Lip模型为ONNX格式（可选，提升性能）

项目已包含完整的转换脚本，直接使用即可：

```bash
cd /opt/lightavatar

# 激活虚拟环境
source venv/bin/activate

# 运行转换脚本（确保wav2lip.pth已下载）
python scripts/convert_wav2lip_to_onnx.py
```

**转换过程说明**：
- 脚本会自动加载 `models/wav2lip/wav2lip.pth`
- 转换为ONNX格式并保存到 `models/wav2lip/wav2lip.onnx`
- 自动验证输出一致性
- 显示性能对比信息

**输出示例**：
```
===========================================================
Wav2Lip PyTorch -> ONNX 转换工具
===========================================================

1. 创建模型架构...
2. 加载模型权重...
   模型参数数量: 14,123,456
3. 准备示例输入...
4. 测试模型前向传播...
   输入形状: audio=(1, 1, 80, 16), face=(1, 6, 96, 96)
   输出形状: (1, 3, 96, 96)
5. 导出为ONNX格式...
   ✓ ONNX模型已保存: models/wav2lip/wav2lip.onnx
   文件大小: 54.32 MB
6. 验证ONNX模型...
   ✓ ONNX模型验证通过
7. 测试ONNX Runtime推理...
   ✓ ONNX推理输出形状: (1, 3, 96, 96)
8. 比较PyTorch和ONNX输出...
   最大差异: 0.000023
   平均差异: 0.000004
   ✓ 输出一致性验证通过

转换完成！
```

**配置使用ONNX模型**：

转换完成后，在 `config/config.yaml` 中启用ONNX：

```yaml
avatar:
  use_onnx: true  # 设置为true使用ONNX模型
```

### 5.7 准备Avatar模板视频

```bash
# 创建示例模板
cd /opt/lightavatar/models/avatars

# 方法1：使用静态图片
# 将你的数字人图片上传到这里，命名为default.jpg

# 方法2：使用短视频模板
# 上传5-10秒的数字人视频，命名为default.mp4

# 验证文件
ls -lh
```

**模板要求**：
- 图片：512x512像素，JPG/PNG格式
- 视频：512x512像素，25fps，MP4格式
- 人脸清晰可见，正面或微侧面

---

## 配置文件设置

### 6.1 复制配置模板

```bash
cd /opt/lightavatar

# 如果有.env.template
cp .env.template .env
```

### 6.2 编辑主配置文件

```bash
sudo nano config/config.yaml
```

**修改以下关键配置**：

```yaml
# Server settings
server:
  host: "0.0.0.0"  # 监听所有网络接口
  port: 8000
  debug: false      # 生产环境设为false

# CORS settings - 添加你的域名
cors:
  origins:
    - "http://localhost:3000"
    - "http://your-domain.com"      # 替换为你的域名
    - "https://your-domain.com"     # 替换为你的域名

# System resources
system:
  max_memory_mb: 8192   # 根据服务器内存调整
  max_sessions: 5       # 根据CPU核心数调整
  session_timeout: 300
  cpu_threads: 4        # 根据CPU核心数调整

# ASR settings
asr:
  backend: "faster-whisper"  # 使用本地模型
  language: "zh"

# Whisper settings
whisper:
  model: "small"        # 或 base/medium
  device: "cpu"
  compute_type: "int8"
  beam_size: 5

# LLM settings - 配置你的大模型API
llm:
  api_url: "http://localhost:8080/v1"  # 修改为你的LLM API地址
  api_key: "your-api-key-here"         # 设置API Key
  model: "qwen-plus"                    # 修改为你的模型名
  temperature: 0.7
  max_tokens: 500

# TTS settings
tts:
  voice: "zh-CN-XiaoxiaoNeural"  # 微软语音
  rate: "+0%"
  pitch: "+0Hz"

# Avatar settings
avatar:
  fps: 25
  resolution: [512, 512]
  template: "default.mp4"  # 或 default.jpg

# 联网搜索配置（可选）
search:
  enabled: true           # 启用联网搜索功能
  max_results: 5          # 每次搜索返回的最大结果数
  fetch_content: true     # 是否获取网页正文内容
  content_max_length: 2000  # 正文内容最大长度
```

**保存**：按`Ctrl+X`，然后按`Y`，回车确认。

**配置说明**：

**联网搜索配置** (可选)：
- `enabled`: 是否启用联网搜索功能，需要安装 `ddgs` 和 `trafilatura` 包
- `max_results`: 搜索结果数量，建议 3-5 个
- `fetch_content`: 是否提取网页正文（提供更详细的上下文给 LLM）
- `content_max_length`: 每个网页正文的最大字符数，避免 token 超限

如果不需要联网搜索功能，可以设置 `enabled: false` 或删除该配置段。

### 6.3 设置环境变量

```bash
sudo nano .env
```

**添加以下内容**：

```bash
# LLM API配置
LLM_API_KEY=your-actual-api-key-here
LLM_API_URL=http://your-llm-server:8080/v1

# 日志级别
LOG_LEVEL=INFO

# 其他配置
PYTHONUNBUFFERED=1
```

**保存并退出**。

---

## 后端部署

### 7.1 测试后端启动

```bash
cd /opt/lightavatar

# 激活虚拟环境
source venv/bin/activate

# 测试运行后端
python backend/app/main.py
```

**预期输出**：
```
INFO: Starting Lightweight Avatar Chat...
INFO: Starting server on 0.0.0.0:8000
INFO: Uvicorn running on http://0.0.0.0:8000
```

按`Ctrl+C`停止测试。

### 7.2 使用systemd创建后端服务

```bash
sudo nano /etc/systemd/system/lightavatar-backend.service
```

**粘贴以下内容**：

```ini
[Unit]
Description=Lightweight Avatar Chat Backend
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/lightavatar
# 重要：PATH 必须包含系统路径以找到 ffmpeg 等工具
Environment="PATH=/opt/lightavatar/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/lightavatar/.env
ExecStart=/opt/lightavatar/venv/bin/python backend/app/main.py
Restart=always
RestartSec=10

# 资源限制
MemoryLimit=4G
CPUQuota=400%

# 日志
StandardOutput=append:/var/log/lightavatar/backend.log
StandardError=append:/var/log/lightavatar/backend-error.log

[Install]
WantedBy=multi-user.target
```

**保存并退出**。

### 7.3 创建日志目录

```bash
sudo mkdir -p /var/log/lightavatar
sudo chown www-data:www-data /var/log/lightavatar
```

### 7.4 调整文件权限

```bash
# 修改项目所有者
sudo chown -R www-data:www-data /opt/lightavatar

# 确保虚拟环境可执行
sudo chmod -R 755 /opt/lightavatar/venv
```

### 7.5 启动后端服务

```bash
# 重载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start lightavatar-backend

# 查看状态
sudo systemctl status lightavatar-backend

# 设置开机自启
sudo systemctl enable lightavatar-backend

# 查看日志
sudo tail -f /var/log/lightavatar/backend.log
```

---

## 前端部署

### 8.1 安装Node.js

```bash
# 安装NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -

# 安装Node.js 18.x
sudo apt install -y nodejs

# 验证安装
node --version  # 应该是v18.x.x
npm --version
```

### 8.2 构建前端

```bash
cd /opt/lightavatar/frontend

# 安装依赖
npm install

# 如果npm install很慢，使用国内镜像
# npm config set registry https://registry.npmmirror.com
# npm install

# 构建生产版本
npm run build

# 构建完成后，会生成dist目录
ls -la dist/
```

### 8.3 构建监控面板

```bash
cd /opt/lightavatar/monitor

# 安装依赖
npm install

# 构建
npm run build

# 验证
ls -la dist/
```

---

## Nginx配置

### 9.1 安装Nginx

```bash
sudo apt install -y nginx

# 验证安装
nginx -v
```

### 9.2 配置Nginx

```bash
sudo nano /etc/nginx/sites-available/lightavatar
```

**粘贴以下配置**：

```nginx
# 前端主界面
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或IP

    # 前端静态文件
    location / {
        root /opt/lightavatar/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端API代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # WebSocket超时设置
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # 静态资源缓存
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|woff|woff2|ttf)$ {
        root /opt/lightavatar/frontend/dist;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}

# 监控面板
server {
    listen 3001;
    server_name your-domain.com;  # 替换为你的域名或IP

    location / {
        root /opt/lightavatar/monitor/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 监控API代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /metrics {
        proxy_pass http://127.0.0.1:8000/metrics;
        proxy_http_version 1.1;
    }
}
```

**保存并退出**。

### 9.3 启用站点配置

```bash
# 创建符号链接
sudo ln -s /etc/nginx/sites-available/lightavatar /etc/nginx/sites-enabled/

# 删除默认配置
sudo rm /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx

# 设置开机自启
sudo systemctl enable nginx
```

### 9.4 配置防火墙

```bash
# 允许HTTP和HTTPS
sudo ufw allow 'Nginx Full'

# 允许监控端口
sudo ufw allow 3001/tcp

# 如果防火墙未启用，启用它
sudo ufw enable

# 查看状态
sudo ufw status
```

---

## 系统服务配置

### 10.1 创建启动脚本

```bash
sudo nano /opt/lightavatar/start.sh
```

**内容**：

```bash
#!/bin/bash
set -e

echo "启动Lightweight Avatar Chat..."

# 启动后端
sudo systemctl start lightavatar-backend

# 等待后端启动
sleep 3

# 检查后端状态
if systemctl is-active --quiet lightavatar-backend; then
    echo "✓ 后端服务启动成功"
else
    echo "✗ 后端服务启动失败"
    exit 1
fi

# 启动Nginx
sudo systemctl start nginx

echo "✓ 所有服务启动完成"
echo "访问地址: http://$(hostname -I | awk '{print $1}')"
```

```bash
sudo chmod +x /opt/lightavatar/start.sh
```

### 10.2 创建停止脚本

```bash
sudo nano /opt/lightavatar/stop.sh
```

**内容**：

```bash
#!/bin/bash

echo "停止Lightweight Avatar Chat..."

# 停止后端
sudo systemctl stop lightavatar-backend

echo "✓ 所有服务已停止"
```

```bash
sudo chmod +x /opt/lightavatar/stop.sh
```

---

## 验证测试

### 11.1 检查服务状态

```bash
# 检查后端服务
sudo systemctl status lightavatar-backend

# 检查Nginx
sudo systemctl status nginx

# 检查端口监听
sudo netstat -tlnp | grep -E '(8000|80|3001)'
```

### 11.2 测试后端API

```bash
# 健康检查
curl http://localhost:8000/health

# 预期返回JSON，包含status等信息

# 查看API文档
curl http://localhost:8000/docs
```

### 11.3 浏览器访问

1. **主界面**: http://your-server-ip
2. **监控面板**: http://your-server-ip:3001
3. **API文档**: http://your-server-ip/docs

### 11.4 WebSocket测试

在浏览器控制台执行：

```javascript
const ws = new WebSocket('ws://your-server-ip/ws/test-session');
ws.onopen = () => {
    console.log('WebSocket连接成功');
    ws.send(JSON.stringify({type: 'ping'}));
};
ws.onmessage = (e) => {
    console.log('收到消息:', e.data);
};
```

---

## 常见问题

### 问题1：后端服务启动失败

**排查步骤**：

```bash
# 查看详细日志
sudo journalctl -u lightavatar-backend -n 50

# 查看错误日志
sudo tail -f /var/log/lightavatar/backend-error.log

# 检查Python依赖
source /opt/lightavatar/venv/bin/activate
pip list

# 手动运行测试
cd /opt/lightavatar
source venv/bin/activate
python backend/app/main.py
```

**常见错误**：
- 模型文件未找到 → 检查`models/`目录
- 端口占用 → `sudo lsof -i :8000`
- 权限问题 → `sudo chown -R www-data:www-data /opt/lightavatar`

### 问题2：前端白屏

**排查步骤**：

```bash
# 检查Nginx配置
sudo nginx -t

# 查看Nginx错误日志
sudo tail -f /var/log/nginx/error.log

# 检查前端文件
ls -la /opt/lightavatar/frontend/dist/

# 检查文件权限
sudo chmod -R 755 /opt/lightavatar/frontend/dist/
```

### 问题3：WebSocket连接失败

**排查步骤**：

```bash
# 检查Nginx WebSocket配置
sudo nano /etc/nginx/sites-available/lightavatar

# 确保包含以下行：
# proxy_set_header Upgrade $http_upgrade;
# proxy_set_header Connection "upgrade";

# 重启Nginx
sudo systemctl restart nginx

# 测试后端WebSocket
python -c "
import asyncio
import websockets

async def test():
    uri = 'ws://localhost:8000/ws/test'
    async with websockets.connect(uri) as ws:
        print('连接成功')

asyncio.run(test())
"
```

### 问题4：数字人生成失败（黑屏无视频）

这是最常见的部署问题，需要逐步排查：

#### 4.1 检查 Wav2Lip 仓库是否克隆

```bash
# 检查官方仓库
ls -la /opt/lightavatar/tools/Wav2Lip/

# 如果不存在，执行克隆
cd /opt/lightavatar
mkdir -p tools && cd tools
git clone https://github.com/Rudrabha/Wav2Lip.git
```

**错误日志特征**：
```
ERROR | Failed to load Wav2Lip models: Please clone official Wav2Lip repo
```

#### 4.2 检查 FFmpeg 是否安装且可用

```bash
# 检查 FFmpeg
ffmpeg -version

# 如果未安装
sudo apt update && sudo apt install -y ffmpeg

# 测试 www-data 用户能否执行
sudo -u www-data ffmpeg -version
```

**错误日志特征**：
```
ERROR | Audio conversion error: [Errno 2] No such file or directory
ERROR | FFmpeg encoding error: [Errno 32] Broken pipe
```

#### 4.3 检查模型文件和模板文件

```bash
# 检查模型权重
ls -lh /opt/lightavatar/models/wav2lip/wav2lip.pth
# 应该约 400MB

# 检查 avatar 模板
ls -lh /opt/lightavatar/models/avatars/
# 应该至少有一个 default.jpg 或 default.png

# 如果缺少模板，创建一个
cd /opt/lightavatar/models/avatars/
wget -O default.jpg "https://via.placeholder.com/512x512.jpg?text=Avatar"
```

**错误日志特征**：
```
ERROR | Failed to load image template: models/avatars/default.png
ERROR | list index out of range
ERROR | No frames loaded from template
```

#### 4.4 检查代码维度问题

查看日志是否有以下错误：

```
ERROR | Error processing frame: expected 4D input (got 3D input)
```

**解决方法**：确保 `backend/handlers/avatar/wav2lip_handler.py` 第 246-260 行包含维度转换代码：

```python
# Model expects (batch, channels, height, width) for face
# Remove time dimension
face_tensor = face_tensor.squeeze(1)  # (1, 3, 96, 96)
mel_tensor = mel_tensor.squeeze(1)    # (1, 80, 16)
```

#### 4.5 完整诊断脚本

```bash
#!/bin/bash
echo "=== 数字人生成故障诊断 ==="

echo -e "\n1. 检查 Wav2Lip 仓库"
[ -d /opt/lightavatar/tools/Wav2Lip ] && echo "✓ 已克隆" || echo "✗ 未克隆"

echo -e "\n2. 检查 FFmpeg"
command -v ffmpeg &>/dev/null && echo "✓ 已安装" || echo "✗ 未安装"

echo -e "\n3. 检查模型文件"
[ -f /opt/lightavatar/models/wav2lip/wav2lip.pth ] && echo "✓ wav2lip.pth 存在" || echo "✗ 缺失"

echo -e "\n4. 检查模板文件"
ls /opt/lightavatar/models/avatars/*.{jpg,png,mp4} 2>/dev/null && echo "✓ 模板存在" || echo "✗ 缺失"

echo -e "\n5. 检查后端服务"
systemctl is-active lightavatar-backend &>/dev/null && echo "✓ 运行中" || echo "✗ 未运行"

echo -e "\n6. 查看最近错误"
sudo tail -20 /var/log/lightavatar/backend.log | grep ERROR || echo "无明显错误"
```

保存为 `diagnose_avatar.sh` 并运行：

```bash
chmod +x diagnose_avatar.sh
./diagnose_avatar.sh
```

### 问题5：内存不足

**优化配置**：

```bash
sudo nano config/config.yaml
```

修改：
```yaml
system:
  max_memory_mb: 4096  # 降低内存限制
  max_sessions: 2      # 减少并发会话
  
whisper:
  model: "base"        # 使用更小的模型

avatar:
  resolution: [256, 256]  # 降低分辨率
```

### 问题5：模型下载速度慢

**使用国内镜像**：

```bash
# 设置HuggingFace镜像
export HF_ENDPOINT=https://hf-mirror.com

# 重新下载模型
python download_whisper.py
```

### 问题6：联网搜索功能报错

**症状**：
```
ERROR | DuckDuckGo search error: DDGS.text() got an unexpected keyword argument 'query'
```

**原因**：DuckDuckGo 搜索包版本不匹配。

#### 6.1 检查当前安装的包

```bash
# 进入虚拟环境
source /opt/lightavatar/venv/bin/activate

# 检查安装的包
pip show duckduckgo-search ddgs
```

#### 6.2 解决方案：更换为新版本包

```bash
# 卸载旧版本的包
pip uninstall -y duckduckgo-search

# 安装新版本
pip install ddgs>=1.0.0
pip install trafilatura>=1.6.0

# 验证安装
pip show ddgs trafilatura
```

#### 6.3 重启后端服务

```bash
sudo systemctl restart lightavatar-backend

# 查看日志确认正常
sudo tail -f /var/log/lightavatar/backend.log
```

#### 6.4 测试搜索功能

```bash
cd /opt/lightavatar
source venv/bin/activate

# 运行测试脚本
python test_search.py

# 如果看到搜索结果，说明已修复
```

**预期输出**：
```
✅ 使用新包: ddgs
=== 测试 DuckDuckGo 搜索 ===
搜索关键词: 今天有什么新闻
最大结果数: 3
方法1: 直接同步调用
结果数量: 3
第一个结果:
  标题: ...
  URL: ...
```

**包版本说明**：
- ❌ **旧包**：`duckduckgo-search` - 使用 `keywords` 参数，已过时
- ✅ **新包**：`ddgs>=1.0.0` - 使用 `query` 参数，推荐使用

**如果仍然报错**：
```bash
# 完全重新安装所有依赖
pip uninstall -y duckduckgo-search ddgs
pip cache purge
pip install ddgs==1.0.0 trafilatura==1.6.0

# 如果 httpx 版本冲突
pip install --upgrade openai
pip install httpx>=0.24.0
```

### 问题7：日志查看

```bash
# 实时查看后端日志
sudo tail -f /var/log/lightavatar/backend.log

# 查看Nginx访问日志
sudo tail -f /var/log/nginx/access.log

# 查看系统日志
sudo journalctl -f -u lightavatar-backend
```

---

## 维护命令

### 日常维护

```bash
# 重启服务
sudo systemctl restart lightavatar-backend
sudo systemctl restart nginx

# 查看资源使用
htop

# 查看磁盘使用
df -h

# 清理日志
sudo journalctl --vacuum-time=7d

# 更新代码
cd /opt/lightavatar
git pull
sudo systemctl restart lightavatar-backend
```

### 备份

```bash
# 备份配置
sudo tar -czf /backup/lightavatar-config-$(date +%Y%m%d).tar.gz \
    /opt/lightavatar/config \
    /opt/lightavatar/.env

# 备份模型
sudo tar -czf /backup/lightavatar-models-$(date +%Y%m%d).tar.gz \
    /opt/lightavatar/models
```

---

## 性能优化建议

### 1. 系统层面

```bash
# 增加文件描述符限制
sudo nano /etc/security/limits.conf

# 添加：
* soft nofile 65536
* hard nofile 65536
```

### 2. Nginx优化

```bash
sudo nano /etc/nginx/nginx.conf
```

```nginx
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # 启用gzip压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss;
}
```

### 3. Python优化

在`.env`中添加：
```bash
# 优化Python性能
PYTHONOPTIMIZE=1
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
```

---

## 脚本使用说明

### 添加脚本执行权限

在使用shell脚本前，需要添加执行权限：

```bash
# 进入scripts目录
cd /opt/lightavatar/scripts

# 为所有shell脚本添加执行权限
chmod +x *.sh

# 或者单独添加
chmod +x ubuntu_deploy.sh
chmod +x download_models.sh
chmod +x setup_ssl.sh
```

### 运行脚本的方法

**Shell脚本**：
```bash
# 方法1：直接执行（需要执行权限）
./ubuntu_deploy.sh

# 方法2：使用bash（推荐，不需要执行权限）
bash ubuntu_deploy.sh

# 方法3：使用sudo（需要root权限的脚本）
sudo bash ubuntu_deploy.sh
```

**Python脚本**：
```bash
# 使用python解释器（推荐）
python check_environment.py
python3.11 check_environment.py

# 如果在虚拟环境中
source /opt/lightavatar/venv/bin/activate
python check_environment.py
```

### 脚本执行顺序

建议按以下顺序执行：

```bash
# 1. 基础部署（首次部署）
sudo bash scripts/ubuntu_deploy.sh

# 2. 下载模型
bash scripts/download_models.sh

# 3. 检查环境
python scripts/check_environment.py

# 4. 转换模型为ONNX（可选，提升性能）
python scripts/convert_wav2lip_to_onnx.py

# 5. 配置SSL（如有域名）
sudo bash scripts/setup_ssl.sh your-domain.com
```

### 常见脚本问题

**权限被拒绝**：
```bash
# 错误：Permission denied
# 解决：
chmod +x ubuntu_deploy.sh
# 或使用：
bash ubuntu_deploy.sh
```

**找不到命令**：
```bash
# 错误：command not found
# 解决：使用相对路径或bash
./ubuntu_deploy.sh
# 或
bash ubuntu_deploy.sh
```

**Python模块未找到**：
```bash
# 错误：ModuleNotFoundError
# 解决：激活虚拟环境
source /opt/lightavatar/venv/bin/activate
python check_environment.py
```

**换行符问题**（从Windows上传脚本时）：
```bash
# 如果脚本报错，转换换行符
sed -i 's/\r$//' ubuntu_deploy.sh
# 或安装并使用dos2unix
sudo apt install dos2unix
dos2unix ubuntu_deploy.sh
```

---

## 总结

部署完成后，你应该有：

✅ 后端服务运行在 `http://localhost:8000`
✅ 前端界面运行在 `http://your-server-ip`
✅ 监控面板运行在 `http://your-server-ip:3001`
✅ 所有服务设置为开机自启
✅ 日志记录完善
✅ WebSocket正常工作

---

## 前端静态服务配置（可选）

如果你希望前端也作为独立服务运行（而非仅通过Nginx），可以使用以下配置：

### 12.1 使用serve托管前端

```bash
# 全局安装serve
sudo npm install -g serve

# 创建前端服务文件
sudo nano /etc/systemd/system/lightavatar-frontend.service
```

**服务配置**：

```ini
[Unit]
Description=Lightweight Avatar Chat Frontend
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/lightavatar/frontend
ExecStart=/usr/bin/serve -s dist -l 3000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 启动前端服务
sudo systemctl daemon-reload
sudo systemctl start lightavatar-frontend
sudo systemctl enable lightavatar-frontend

# 查看状态
sudo systemctl status lightavatar-frontend
```

### 12.2 前端开发模式（本地调试）

```bash
cd /opt/lightavatar/frontend

# 开发模式运行（自动热重载）
npm run dev

# 访问 http://localhost:3000
```

---

## SSL/HTTPS 配置（Let's Encrypt）

### 13.1 安装Certbot

```bash
# 安装Certbot和Nginx插件
sudo apt install -y certbot python3-certbot-nginx

# 验证安装
certbot --version
```

### 13.2 申请SSL证书

**前提条件**：
- 拥有一个域名（如 `example.com`）
- 域名DNS已解析到服务器IP
- 防火墙已开放80和443端口

```bash
# 停止Nginx（Let's Encrypt需要使用80端口）
sudo systemctl stop nginx

# 申请证书（独立模式）
sudo certbot certonly --standalone \
  -d your-domain.com \
  -d www.your-domain.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# 或者使用Nginx插件（自动配置）
sudo certbot --nginx \
  -d your-domain.com \
  -d www.your-domain.com \
  --email your-email@example.com \
  --agree-tos \
  --redirect
```

**证书位置**：
- 证书：`/etc/letsencrypt/live/your-domain.com/fullchain.pem`
- 私钥：`/etc/letsencrypt/live/your-domain.com/privkey.pem`

### 13.3 配置Nginx使用SSL

```bash
sudo nano /etc/nginx/sites-available/lightavatar
```

**完整的HTTPS配置**：

```nginx
# HTTP重定向到HTTPS
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # Let's Encrypt验证
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # 重定向到HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS主服务
server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL证书配置
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL优化配置
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    
    # 现代SSL配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    
    # HSTS（HTTP严格传输安全）
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 前端静态文件
    location / {
        root /opt/lightavatar/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端API代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket代理（WSS）
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket超时设置
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    # 静态资源缓存
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|woff|woff2|ttf|svg)$ {
        root /opt/lightavatar/frontend/dist;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}

# HTTPS监控面板
server {
    listen 3001 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        root /opt/lightavatar/monitor/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /metrics {
        proxy_pass http://127.0.0.1:8000/metrics;
    }
}
```

**保存并重启Nginx**：

```bash
# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx
```

### 13.4 配置自动续期

Let's Encrypt证书有效期90天，需要定期续期：

```bash
# 测试续期（不实际执行）
sudo certbot renew --dry-run

# Certbot已自动配置定时任务，查看：
sudo systemctl list-timers | grep certbot

# 手动续期
sudo certbot renew

# 续期后重启Nginx
sudo certbot renew --post-hook "systemctl reload nginx"
```

### 13.5 更新前端WebSocket配置

修改前端代码使用WSS（加密WebSocket）：

```bash
nano /opt/lightavatar/frontend/src/composables/useWebSocket.ts
```

确保WebSocket URL使用协议自适应：

```typescript
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`
```

然后重新构建前端：

```bash
cd /opt/lightavatar/frontend
npm run build
```

### 13.6 使用脚本自动配置SSL

项目提供了自动配置脚本：

```bash
cd /opt/lightavatar/scripts

# 添加执行权限
chmod +x setup_ssl.sh

# 运行脚本（替换为你的域名和邮箱）
sudo bash setup_ssl.sh your-domain.com your-email@example.com
```

### 13.7 验证HTTPS配置

```bash
# 1. 检查证书有效性
sudo certbot certificates

# 2. 测试SSL配置
curl -I https://your-domain.com

# 3. 在线检测SSL安全性
# 访问：https://www.ssllabs.com/ssltest/
```

### 13.8 防火墙配置

```bash
# 允许HTTPS流量
sudo ufw allow 443/tcp

# 查看防火墙状态
sudo ufw status

# 预期输出应包含：
# 80/tcp                     ALLOW       Anywhere
# 443/tcp                    ALLOW       Anywhere
# 3001/tcp                   ALLOW       Anywhere
```

---

**下一步**：
1. ✅ SSL证书已配置
2. 设置监控告警
3. 配置自动备份
4. 性能压测

---

**部署文档版本**: v1.1  
**最后更新**: 2024-10-18  
**适用系统**: Ubuntu 20.04 / 22.04 LTS
