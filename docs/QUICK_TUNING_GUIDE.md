# 快速调优指南

当你发现**嘴型模糊、开口不明显**时的快速解决方案。

---

## 🚀 3分钟快速优化

### Step 1: 下载GAN模型（必须）

**推荐使用Hugging Face镜像（国内可访问）**：

```bash
cd /opt/lightavatar
wget -O models/wav2lip/wav2lip_gan.pth \
  https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth
```

### Step 2: 调整配置

编辑 `/opt/lightavatar/.env` 文件：

```bash
sudo nano /opt/lightavatar/.env
```

添加或修改以下配置：

```bash
# 启用GAN模型和融合增强
AVATAR_USE_ONNX=false
AVATAR_ENHANCE_MODE=true

# 增大底部padding以确保嘴部完整（关键！）
AVATAR_FACE_PADDING_BOTTOM=0.40  # 从默认0.35增加到0.40

# 降低TTS语速，便于观察口型
TTS_RATE=-10%
```

### Step 3: 重启服务

```bash
sudo systemctl restart lightavatar
```

### Step 4: 验证效果

查看日志确认GAN模型已加载：

```bash
sudo tail -f /var/log/lightavatar/backend.log | grep "Using Wav2Lip"
```

应该看到：
```
Using Wav2Lip GAN model for enhanced quality
```

---

## 📊 效果对比

| 配置 | 嘴型清晰度 | 开口幅度 | 融合自然度 |
|------|-----------|---------|----------|
| **优化前** | ⭐⭐ | ⭐⭐ | ⭐⭐ |
| **使用GAN模型** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **+ 调整padding** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **+ 降低语速** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🎛️ 进阶调优

### 场景1：嘴型还是不够清晰

**进一步增大底部padding**：

```bash
AVATAR_FACE_PADDING_BOTTOM=0.45  # 最大可到0.50
```

### 场景2：嘴部与脸部接缝明显

**增加水平padding**：

```bash
AVATAR_FACE_PADDING_HORIZONTAL=0.18
AVATAR_ENHANCE_MODE=true  # 确保开启
```

### 场景3：使用视频模板

**替换静态图片为视频**：

```bash
# 将视频上传到 models/avatars/default.mp4
AVATAR_TEMPLATE=default.mp4
```

视频模板的优势：
- ✅ 自然的微表情
- ✅ 轻微的头部运动
- ✅ 更真实的效果

---

## 🔧 所有可调参数

### 人脸检测Padding

| 参数 | 默认值 | 建议范围 | 作用 |
|------|--------|---------|------|
| `AVATAR_FACE_PADDING_HORIZONTAL` | 0.15 | 0.10-0.20 | 左右扩展，影响脸颊包含 |
| `AVATAR_FACE_PADDING_TOP` | 0.10 | 0.05-0.15 | 顶部扩展，影响额头包含 |
| `AVATAR_FACE_PADDING_BOTTOM` | 0.35 | 0.25-0.50 | **底部扩展，影响嘴部和下巴** |

### TTS语速调整

| 设置 | 效果 | 建议场景 |
|------|------|---------|
| `TTS_RATE=+0%` | 正常语速 | 默认 |
| `TTS_RATE=-10%` | 略慢 | 观察口型 ✅ |
| `TTS_RATE=-20%` | 较慢 | 演示/教学 |
| `TTS_RATE=+10%` | 略快 | 快节奏对话 |

---

## 📋 完整推荐配置（复制即用）

```bash
# 编辑 /opt/lightavatar/.env
sudo nano /opt/lightavatar/.env
```

```bash
# Avatar优化配置
AVATAR_FPS=25
AVATAR_RESOLUTION=512,512
AVATAR_TEMPLATE=default.mp4
AVATAR_USE_ONNX=false
AVATAR_ENHANCE_MODE=true

# 人脸padding优化
AVATAR_FACE_PADDING_HORIZONTAL=0.15
AVATAR_FACE_PADDING_TOP=0.10
AVATAR_FACE_PADDING_BOTTOM=0.40

# TTS优化
TTS_RATE=-10%
TTS_VOICE=zh-CN-XiaoxiaoNeural
```

保存后重启：
```bash
sudo systemctl restart lightavatar
```

---

## ❓ 常见问题

### Q1: 修改配置后没效果？

**检查清单**：
- [ ] 确认已保存 `.env` 文件
- [ ] 确认已重启服务
- [ ] 查看日志确认配置加载

### Q2: 下载GAN模型失败？

**解决方案**：
1. 使用Hugging Face镜像（推荐）
2. 手动下载后上传到服务器
3. 参考 [LIP_SYNC_QUALITY.md](LIP_SYNC_QUALITY.md) 的详细说明

### Q3: 如何验证padding是否生效？

**查看日志**：
```bash
sudo tail -f /var/log/lightavatar/backend.log | grep "Cached face"
```

应该看到：
```
Cached face detection for template: (x, y, width, height)
```

修改padding后，`height` 值会变化。

### Q4: 可以实时调整参数吗？

**可以！通过WebSocket发送配置**：

```javascript
{
  "type": "config",
  "config": {
    "avatar": {
      "face_padding_bottom": 0.40
    }
  }
}
```

修改后会立即生效（清除缓存并重新检测人脸）。

---

## 📚 相关文档

- **[Avatar配置详解](AVATAR_CONFIG.md)** - 所有配置参数说明
- **[唇形质量优化](LIP_SYNC_QUALITY.md)** - 完整优化指南
- **[环境配置示例](../.env.example)** - 配置文件模板

---

## 🎯 推荐工作流

1. **基础优化**（所有人必做）
   - ✅ 下载GAN模型
   - ✅ 开启 `AVATAR_ENHANCE_MODE=true`
   - ✅ 设置 `AVATAR_FACE_PADDING_BOTTOM=0.35`

2. **针对素材调优**（根据实际效果）
   - 🔧 调整底部padding（0.35 → 0.40 → 0.45）
   - 🔧 调整TTS语速（-10% → -15%）

3. **进阶优化**（追求极致效果）
   - 🎬 使用视频模板
   - 🎨 优化模板素材质量
   - ⚙️ 微调所有padding参数

---

**预计优化时间**：3-10分钟  
**效果提升**：明显改善嘴型清晰度和开口幅度
