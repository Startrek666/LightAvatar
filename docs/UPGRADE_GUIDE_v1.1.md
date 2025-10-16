# v1.1 升级指南

## 🚀 快速开始

### 1. 更新代码
```bash
# 拉取最新代码（如果使用git）
git pull origin main

# 或者直接使用新代码覆盖
```

### 2. 安装FFmpeg（推荐）
FFmpeg用于高效的视频编码，可以将传输体积降低96%。

#### Windows
```bash
# 使用Chocolatey
choco install ffmpeg

# 或下载并添加到PATH
# https://ffmpeg.org/download.html
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

#### 验证安装
```bash
ffmpeg -version
```

> **注意**：如果不安装FFmpeg，系统会自动使用OpenCV编码（体积略大但仍可用）

### 3. 无需修改配置
所有新功能默认启用，配置文件保持不变。

### 4. 重启服务
```bash
# 后端
cd backend
python app/main.py

# 前端（如果需要重新构建）
cd frontend
npm run build  # 生产环境
npm run dev    # 开发环境
```

---

## ✨ 新功能使用

### 1. 流式对话（默认启用）

#### 用户体验
- 发送消息后**立即**看到数字人开始说话
- 文字**实时**显示在聊天框
- **边生成边播放**，无需等待

#### 技术细节
流式模式下，系统会：
1. 接收到LLM的每个文字片段立即显示
2. 检测到句子结束（。！？等）立即生成视频
3. 视频分片传输并排队播放

#### 前端控制
```typescript
// 启用流式（默认）
send({
  type: 'text',
  text: '你好',
  streaming: true
})

// 禁用流式（兼容模式）
send({
  type: 'text',
  text: '你好',
  streaming: false
})
```

---

### 2. 语音输入开关

#### 界面位置
在页面右上角，找到 **"语音输入"** 开关

#### 使用场景
- **开启**：显示"按住说话"按钮，支持语音输入
- **关闭**：隐藏语音按钮，仅使用文字聊天

#### 适用人群
- 办公室等需要安静环境的场景
- 没有麦克风的设备
- 更喜欢打字的用户

---

### 3. 对话记录控制

#### 界面位置
在页面右上角，找到 **"对话记录"** 开关

#### 使用场景
- **显示**：查看完整对话历史
- **隐藏**：专注观看数字人，数字人区域自动扩展

#### 效果
隐藏对话记录后：
- 数字人显示区域从40%扩展到100%
- 提供更沉浸的观看体验
- 适合演示、展示场景

---

## 🎯 性能提升

### 延迟对比
| 场景 | v1.0 | v1.1 | 说明 |
|------|------|------|------|
| 用户发送消息 | 0s | 0s | - |
| 看到第一个字 | 1.0-1.5s | **0.3-0.5s** | ⚡ 提升60-70% |
| 数字人开始说话 | 1.5-2.0s | **0.5-0.8s** | ⚡ 实时响应 |
| 完整回复结束 | 5-8s | 5-8s | 总时长相同，但体验更流畅 |

### 流量对比
| 场景 | v1.0 | v1.1 | 说明 |
|------|------|------|------|
| 10秒视频 | ~50MB | **~2MB** | 📉 减少96% |
| 30秒视频 | ~150MB | **~6MB** | 📉 减少96% |
| 1分钟视频 | ~300MB | **~12MB** | 📉 减少96% |

---

## 🔍 常见问题

### Q1: 为什么还是有延迟？
**A**: 
- **LLM延迟**：大模型生成第一个字需要时间（无法避免）
- **TTS延迟**：语音合成需要时间（~100-200ms）
- **Avatar延迟**：视频生成需要时间（~200-300ms）
- **网络延迟**：传输需要时间（取决于带宽）

v1.1通过**流式处理**，让这些延迟**并行**而不是**串行**，大幅提升体验。

### Q2: 没有FFmpeg会怎样？
**A**: 
- 系统会自动检测FFmpeg是否可用
- 如果没有，自动使用OpenCV编码
- 功能完全正常，只是视频体积稍大（~5-10MB/10秒）
- **建议安装FFmpeg以获得最佳性能**

### Q3: 如何确认流式模式工作？
**A**: 
查看浏览器控制台（F12），应该看到：
```
WebSocket connected
Extracted X mel chunks from audio
Generated video: XXXX bytes
Video chunk incoming: XXXX bytes
```

同时，聊天框中的文字会**逐字出现**而不是一次性显示。

### Q4: 视频播放卡顿？
**A**: 可能原因：
1. **CPU性能不足**：降低分辨率（设置中改为256x256）
2. **网络延迟**：检查网络连接
3. **并发过高**：减少同时对话的用户数

优化方法：
```yaml
# config/config.yaml
avatar:
  fps: 20           # 降低帧率
  resolution: [256, 256]  # 降低分辨率
  static_mode: true # 启用静态模式（仅使用单帧）
```

### Q5: Wav2Lip嘴型还是不同步？
**A**: 检查：
1. **模型文件**：确保`models/wav2lip_cpu.onnx`存在
2. **音频质量**：确保TTS输出正常
3. **日志信息**：查看`logs/app.log`中是否有mel提取错误

如果仍有问题，可能需要：
- 重新转换Wav2Lip模型为ONNX格式
- 检查MediaPipe人脸检测是否正常

---

## 🛠️ 高级配置

### 自定义句子检测
```python
# backend/core/session_manager.py

def _is_sentence_end(self, text: str) -> bool:
    """自定义句子结束检测"""
    delimiters = ['。', '！', '？', '.', '!', '?', '；', ';', '\n']
    
    # 添加自定义分隔符
    delimiters.append('：')  # 冒号
    delimiters.append(',')   # 逗号（更短的句子）
    
    return any(text.rstrip().endswith(d) for d in delimiters)
```

### 调整视频编码质量
```python
# backend/utils/video_utils.py

ffmpeg_cmd = [
    # ...
    '-crf', '18',  # 改为18（更高质量）或28（更小体积）
    # 默认23是平衡点
    # ...
]
```

### 禁用流式模式（全局）
```python
# backend/app/main.py

# 将默认值改为False
use_streaming = data.get("streaming", False)  # 改为False
```

---

## 📊 监控和调试

### 查看实时日志
```bash
# Linux/Mac
tail -f logs/app.log

# Windows
Get-Content logs/app.log -Wait
```

### 关键日志信息
```
INFO: Extracted 45 mel chunks from audio  # mel提取成功
INFO: Generated video: 245678 bytes       # 视频生成成功
INFO: Sentence processed: 245678 bytes    # 句子处理完成
INFO: Processing sentence: 你好...       # 正在处理句子
```

### 性能监控
访问监控面板查看实时性能：
```
http://localhost:3001
```

关注指标：
- **Avatar处理时间**：应该在200-500ms
- **TTS处理时间**：应该在100-300ms
- **内存使用**：应该在2-3GB

---

## 🎓 最佳实践

### 1. 生产环境建议
- ✅ 安装FFmpeg
- ✅ 使用HTTPS
- ✅ 配置CDN加速视频传输
- ✅ 启用Redis缓存（未来版本）

### 2. 低配置服务器优化
```yaml
# config/config.yaml
avatar:
  fps: 20
  resolution: [256, 256]
  static_mode: true  # 仅使用静态图片
  
whisper:
  model: "tiny"  # 使用最小模型
```

### 3. 高并发优化
```yaml
# config/config.yaml
system:
  max_sessions: 5   # 限制并发数
  session_timeout: 180  # 缩短超时时间
```

---

## 🆘 需要帮助？

### 提交Issue
https://github.com/yourusername/lightweight-avatar-chat/issues

### 查看文档
- [使用指南](USAGE.md)
- [API文档](api.md)
- [配置说明](configuration.md)

### 社区支持
- 讨论区：（待添加）
- 邮件：（待添加）

---

**祝您使用愉快！** 🎉

