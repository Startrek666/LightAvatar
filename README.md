# Lightweight Avatar Chat - 轻量级CPU数字人对话系统

> 🚀 一个原生为CPU设计的轻量级2D数字人对话系统，具有高稳定性和低资源占用特性。

## 🔥 核心特性

- **CPU原生设计**：无需GPU，专为CPU优化
- **模块化架构**：灵活的Handler系统，易于扩展
- **内存友好**：智能内存管理，防止泄漏
- **高稳定性**：进程隔离，自动恢复
- **实时监控**：内置监控面板，实时查看系统状态
- **灵活配置**：支持自定义API配置

## 🛠️ 技术栈

- **后端**：FastAPI + WebSocket
- **前端**：Vue3 + TypeScript + Ant Design Vue
- **语音识别**：Faster-Whisper (CPU优化版)
- **语音合成**：Edge TTS (微软免费服务)
- **数字人驱动**：Wav2Lip (ONNX优化)
- **大语言模型**：支持OpenAI兼容API

## 📊 性能指标

| 指标 | 4核8G | 8核16G |
|-----|-------|--------|
| 首帧延迟 | 1.0-1.5s | 0.8-1.2s |
| 视频帧率 | 20-25fps | 25-30fps |
| 内存占用 | <2.5GB | <3GB |
| 并发支持 | 1路 | 2-3路 |

## 🚀 快速开始

### 1. 环境要求

- Python 3.11+
- Node.js 18+
- CPU: 4核心以上
- 内存: 8GB以上

### 2. 安装依赖

```bash
# 后端依赖
cd backend
pip install -r requirements.txt

# 前端依赖
cd ../frontend
npm install

# 监控面板依赖
cd ../monitor
npm install
```

### 3. 配置

编辑 `config/config.yaml` 配置文件：

```yaml
llm:
  api_url: "http://localhost:8000/v1"  # 你的私有大模型API地址
  api_key: "your-api-key"
  model: "qwen-plus"
```

### 4. 启动服务

```bash
# 启动后端
cd backend
python app/main.py

# 启动前端（新终端）
cd frontend
npm run dev

# 启动监控面板（新终端）
cd monitor
npm run dev
```

### 5. 访问

- 主界面：http://localhost:3000
- 监控面板：http://localhost:3001
- API文档：http://localhost:8000/docs

## 📁 项目结构

```
lightweight-avatar-chat/
├── backend/              # 后端服务
│   ├── app/             # 应用主入口
│   ├── handlers/        # 功能模块Handler
│   ├── core/           # 核心功能（会话、缓冲、监控）
│   └── utils/          # 工具函数
├── frontend/            # 前端界面
├── monitor/            # 监控面板
├── config/             # 配置文件
├── models/             # 模型文件
├── scripts/            # 工具脚本
└── docker/             # Docker部署
```

## 🐳 Docker部署

```bash
# 构建镜像
docker build -f docker/Dockerfile.cpu -t lightweight-avatar .

# 运行容器
docker run -d \
  --name avatar-chat \
  -p 8000:8000 \
  -v ./config:/app/config \
  -v ./models:/app/models \
  lightweight-avatar
```

## 📖 文档

- [API文档](docs/api.md)
- [配置说明](docs/configuration.md)
- [部署指南](docs/deployment.md)
- [开发指南](docs/development.md)

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系

- 项目地址：https://github.com/yourusername/lightweight-avatar-chat
- 问题反馈：[Issues](https://github.com/yourusername/lightweight-avatar-chat/issues)
