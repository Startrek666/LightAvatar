# Avatar 配置参数说明

## 人脸检测 Padding 配置（新增）

用于调整人脸检测框的扩展范围，确保嘴部完整且效果更清晰。

### 配置参数

| 参数名 | 默认值 | 说明 | 调整建议 |
|--------|--------|------|----------|
| `AVATAR_FACE_PADDING_HORIZONTAL` | `0.15` | 左右两侧padding比例（占人脸宽度） | 0.10 ~ 0.20 |
| `AVATAR_FACE_PADDING_TOP` | `0.10` | 顶部padding比例（占人脸高度） | 0.05 ~ 0.15 |
| `AVATAR_FACE_PADDING_BOTTOM` | `0.35` | 底部padding比例（占人脸高度） | 0.25 ~ 0.45 |

### 为什么调整这些参数？

**问题**：嘴型模糊、开口不明显

**原因**：
1. 底部padding不足，嘴部区域被裁剪或不完整
2. 不同人脸比例、不同拍摄角度需要不同的扩展范围

**解决**：
- **底部padding最重要**：默认已从 `0.25` 提升到 `0.35`，确保嘴部完整
- 对于下巴较短的素材，可继续增大到 `0.40` 或 `0.45`
- 对于脸型较宽的素材，适当增加水平padding

---

## 配置方式

### 方式1：环境变量（推荐）

在服务器上设置环境变量：

```bash
# 编辑环境文件
sudo nano /opt/lightavatar/.env

# 添加或修改以下配置
AVATAR_FACE_PADDING_HORIZONTAL=0.15
AVATAR_FACE_PADDING_TOP=0.10
AVATAR_FACE_PADDING_BOTTOM=0.35  # 对于嘴部不清晰，增大到 0.40

# 重启服务
sudo systemctl restart lightavatar
```

### 方式2：通过WebSocket动态配置

前端可通过WebSocket发送配置消息：

```javascript
{
  "type": "config",
  "config": {
    "avatar": {
      "face_padding_horizontal": 0.15,
      "face_padding_top": 0.10,
      "face_padding_bottom": 0.40  // 增大底部padding
    }
  }
}
```

### 方式3：通过API配置

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "avatar": {
      "face_padding_bottom": 0.40
    }
  }'
```

---

## 调参建议

### 场景1：嘴型不清晰、开口小

**症状**：生成的视频嘴巴几乎不动或动作很小

**解决**：
```bash
AVATAR_FACE_PADDING_BOTTOM=0.40  # 增大底部padding
AVATAR_ENHANCE_MODE=true         # 开启融合增强
```

**配合使用**：
- 下载并使用 `wav2lip_gan.pth` 模型
- TTS语速降低：`TTS_RATE=-10%`

---

### 场景2：嘴部边缘有接缝、融合不自然

**症状**：嘴部与脸部连接处有明显分界线

**解决**：
```bash
AVATAR_ENHANCE_MODE=true                # 启用羽化融合
AVATAR_FACE_PADDING_HORIZONTAL=0.18     # 略增加水平padding
```

---

### 场景3：下巴被裁剪

**症状**：生成的视频中下巴部分缺失或变形

**解决**：
```bash
AVATAR_FACE_PADDING_BOTTOM=0.45  # 大幅增加底部padding
```

---

### 场景4：人脸检测失败

**症状**：日志中出现"Face detection error"

**解决**：
1. 检查模板图像质量（需正面、清晰）
2. 适当减小padding避免超出图像边界：
```bash
AVATAR_FACE_PADDING_HORIZONTAL=0.12
AVATAR_FACE_PADDING_TOP=0.08
AVATAR_FACE_PADDING_BOTTOM=0.30
```

---

## 最佳实践

### 推荐配置（针对中国人脸）

```bash
# 环境变量配置
AVATAR_FPS=25
AVATAR_RESOLUTION=512,512
AVATAR_TEMPLATE=default.mp4          # 使用视频模板
AVATAR_USE_ONNX=false                # 使用PyTorch GAN模型
AVATAR_ENHANCE_MODE=true             # 开启融合增强

# 人脸padding（已优化）
AVATAR_FACE_PADDING_HORIZONTAL=0.15
AVATAR_FACE_PADDING_TOP=0.10
AVATAR_FACE_PADDING_BOTTOM=0.35      # 默认值已提升

# TTS配置（配合更明显口型）
TTS_RATE=-10%                        # 略降语速
TTS_VOICE=zh-CN-XiaoxiaoNeural
```

### 测试流程

1. **使用默认配置测试**
   - 观察嘴型是否清晰、开口是否明显

2. **如果嘴型不清晰**
   - 增大 `AVATAR_FACE_PADDING_BOTTOM` 到 `0.40`
   - 重启服务测试

3. **如果还不理想**
   - 确认使用了 `wav2lip_gan.pth` 模型
   - 降低TTS语速：`TTS_RATE=-15%`
   - 尝试增大到 `0.45`

4. **优化融合效果**
   - 确保 `AVATAR_ENHANCE_MODE=true`
   - 微调水平padding：`0.15 ~ 0.18`

---

## 技术原理

### Padding作用

```
原始检测框：  [人脸区域]
添加padding后：
    ┌─────────────────┐  ← top padding (10%)
    │                 │
    │   [人脸区域]   │  ← horizontal padding (15%)
    │                 │
    │                 │
    └─────────────────┘  ← bottom padding (35%)
         ↑
       嘴部区域完整保留
```

### 为什么底部padding更大？

1. **嘴部位置**：嘴部位于人脸下半部分
2. **开口空间**：张嘴时需要额外的下方空间
3. **下巴包含**：确保完整的下颌轮廓
4. **Wav2Lip模型**：训练数据中嘴部区域较大

---

## 日志验证

修改配置后，查看日志确认生效：

```bash
sudo tail -f /var/log/lightavatar/backend.log
```

**关键日志**：
```
✓ Cached face detection for template: (x, y, width, height)
```

如果 `height` 值增大，说明底部padding生效。

---

## 故障排除

### Q: 修改配置后没有效果？

**A**: 
1. 确认已重启服务：`sudo systemctl restart lightavatar`
2. 检查配置是否生效：查看日志中的初始化信息
3. 清除缓存：修改padding后会自动清除人脸检测缓存

### Q: padding太大导致超出图像边界？

**A**: 代码已自动处理边界限制，不会超出图像范围。如果模板图像本身较小，适当减小padding。

### Q: 如何恢复默认配置？

**A**: 删除环境变量或设置为默认值：
```bash
AVATAR_FACE_PADDING_HORIZONTAL=0.15
AVATAR_FACE_PADDING_TOP=0.10
AVATAR_FACE_PADDING_BOTTOM=0.35
```

---

## 相关文档

- [唇形质量优化指南](LIP_SYNC_QUALITY.md)
- [Wav2Lip GAN模型下载](LIP_SYNC_QUALITY.md#下载步骤)
- [完整配置参数](../backend/app/config.py)
