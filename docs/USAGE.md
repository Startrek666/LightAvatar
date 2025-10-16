# Lightweight Avatar Chat 使用指南

## 🚀 快速启动

### 1. 安装依赖

```bash
# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置API

编辑 `config/config.yaml` 文件，配置你的私有大模型API：

```yaml
llm:
  api_url: "http://localhost:8080/v1"  # 你的API地址
  api_key: "your-api-key"              # 你的API密钥
  model: "qwen-plus"                   # 模型名称
```

### 3. 下载模型

```bash
# 下载Whisper语音识别模型
python scripts/download_models.py --type whisper

# 下载Wav2Lip模型（需要手动转换为ONNX）
python scripts/download_models.py --type wav2lip
```

### 4. 启动服务

```bash
# 启动后端服务
python backend/app/main.py

# 新终端 - 启动前端（开发模式）
cd frontend
npm install
npm run dev

# 新终端 - 启动监控面板（开发模式）
cd monitor
npm install
npm run dev
```

### 5. 访问应用

- 主界面：http://localhost:3000
- 监控面板：http://localhost:3001
- API文档：http://localhost:8000/docs

## 📋 功能说明

### 语音对话

1. 点击"按住说话"按钮进行语音输入
2. 松开按钮后，系统会自动识别并处理
3. 数字人会以视频形式回复

### 文本对话

1. 在输入框输入文字
2. 按Enter或点击发送按钮
3. 系统会生成语音和数字人视频回复

### 设置配置

点击设置按钮可以配置：

- **LLM设置**：API地址、密钥、模型、温度等
- **语音识别**：Whisper模型大小、语言
- **语音合成**：Edge TTS语音、语速、音调
- **数字人**：帧率、分辨率、模板

## 🐳 Docker部署

### 构建镜像

```bash
cd docker
docker-compose build
```

### 启动服务

```bash
# 设置环境变量
export LLM_API_KEY=your-api-key

# 启动所有服务
docker-compose up -d
```

### 查看日志

```bash
docker-compose logs -f backend
```

## 🔧 高级配置

### Whisper模型选择

根据你的硬件配置选择合适的模型：

| 模型 | 大小 | 内存需求 | 速度 | 准确率 |
|------|------|----------|------|--------|
| tiny | 39MB | ~1GB | 最快 | 一般 |
| base | 74MB | ~1GB | 快 | 较好 |
| small | 244MB | ~2GB | 适中 | 好 |
| medium | 769MB | ~5GB | 慢 | 很好 |

### CPU优化

在 `.env` 文件中设置：

```bash
OMP_NUM_THREADS=4      # OpenMP线程数
MKL_NUM_THREADS=4      # MKL线程数
NUMEXPR_NUM_THREADS=4  # NumExpr线程数
```

### 内存管理

配置文件中可设置：

```yaml
system:
  max_memory_mb: 4096     # 最大内存使用
  max_sessions: 10        # 最大并发会话
  session_timeout: 300    # 会话超时（秒）
```

## 📊 监控指标

监控面板显示：

- **系统状态**：CPU、内存、磁盘使用率
- **活跃会话**：当前会话数、会话详情
- **性能指标**：各模块处理时间
- **请求统计**：总请求数、错误率

## 🐛 常见问题

### 1. 麦克风无法访问

- 确保浏览器已授权麦克风权限
- 使用HTTPS访问（localhost除外）

### 2. 数字人视频不流畅

- 降低分辨率：设置中改为256x256
- 降低帧率：设置中改为20fps
- 开启静态模式：仅使用单帧图片

### 3. 内存占用过高

- 减少最大会话数
- 使用更小的Whisper模型
- 及时清理过期会话

### 4. API连接失败

- 检查API地址是否正确
- 确认API密钥有效
- 测试API可用性：`curl http://your-api/v1/models`

## 🔐 安全建议

1. **生产环境必须使用HTTPS**
2. **限制API访问频率**
3. **定期更新依赖包**
4. **使用强密码保护API**
5. **限制CORS来源**

## 📝 开发调试

### 启用调试模式

```yaml
server:
  debug: true
logging:
  level: "DEBUG"
```

### 查看日志

```bash
# 实时查看日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log
```

### 性能分析

```bash
# 使用cProfile分析
python -m cProfile -o profile.stats backend/app/main.py

# 查看分析结果
python -m pstats profile.stats
```
