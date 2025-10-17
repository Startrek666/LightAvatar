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

### 5.5 下载Wav2Lip模型

#### 方法一：自动下载（推荐）

```bash
# 创建下载脚本
cat > download_wav2lip.sh << 'EOF'
#!/bin/bash
cd /opt/lightavatar/models/wav2lip

# 下载原始Wav2Lip PyTorch模型
echo "下载Wav2Lip模型..."
wget -O wav2lip.pth https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip.pth

# 或使用备用链接（如果上面失败）
# wget -O wav2lip.pth https://huggingface.co/spaces/SayedNazim/Wav2Lip-GFPGAN/resolve/main/wav2lip.pth

echo "下载完成！"
ls -lh wav2lip.pth
EOF

chmod +x download_wav2lip.sh
./download_wav2lip.sh
```

#### 方法二：手动上传

如果自动下载失败，可以手动下载后上传：

1. 本地下载：https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip.pth
2. 上传到服务器：
```bash
# 在本地执行
scp wav2lip.pth user@your-server:/opt/lightavatar/models/wav2lip/
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
```

**保存**：按`Ctrl+X`，然后按`Y`，回车确认。

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
Environment="PATH=/opt/lightavatar/venv/bin"
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

### 问题4：内存不足

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

### 问题6：日志查看

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

**下一步**：
1. 配置SSL证书（使用Let's Encrypt）
2. 设置监控告警
3. 配置自动备份
4. 性能压测

---

**部署文档版本**: v1.0  
**最后更新**: 2024-10-17  
**适用系统**: Ubuntu 20.04 / 22.04 LTS
