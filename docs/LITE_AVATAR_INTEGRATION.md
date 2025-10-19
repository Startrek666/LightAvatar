# LiteAvatar 集成指南

## 📖 概述

本文档介绍如何将 **LiteAvatar** 数字人引擎集成到 lightweight-avatar-chat 系统中，作为 Wav2Lip 的替代方案。

## 🎯 为什么选择 LiteAvatar？

### 性能对比

| 特性 | Wav2Lip | LiteAvatar |
|------|---------|------------|
| **渲染性能** | 15-20 fps（需优化） | 30 fps（原生CPU） |
| **延迟** | 较高（检测+推理+融合） | 低（参数化驱动） |
| **质量风格** | 照片级真实感 | 2D卡通流畅动画 |
| **资源需求** | 需要模型权重 | 需要Avatar数据包 |
| **灵活性** | 支持任意真人视频 | 需要预制Avatar |

### 适用场景

✅ **适合使用 LiteAvatar：**
- 需要高帧率流畅动画
- CPU资源有限
- 2D风格可接受
- 实时性要求高

⚠️ **继续使用 Wav2Lip：**
- 需要照片级真实感
- 要支持任意真人视频
- 有GPU资源

## 📦 准备工作

### 1. 依赖安装

```bash
# 进入项目目录
cd d:/Aprojects/Light-avatar/lightweight-avatar-chat

# 安装额外依赖
pip install scipy soundfile pydub onnxruntime torchvision
```

### 2. 获取 Avatar 数据

LiteAvatar 需要特定的 Avatar 数据包，包含以下文件：

```
models/lite_avatar/default/
├── net_encode.pt          # 编码器模型（~50MB）
├── net_decode.pt          # 解码器模型（~50MB）
├── neutral_pose.npy       # 中性表情参数
├── bg_video.mp4          # 背景视频
├── face_box.txt          # 人脸区域坐标
└── ref_frames/           # 参考帧目录（150张图）
    ├── ref_00000.jpg
    ├── ref_00001.jpg
    └── ...
```

**获取方式：**

#### 方式1：使用仓库自带的示例数据（推荐）⭐

lite-avatar 官方仓库中已包含示例数据，这是最简单的方式：

```bash
# 1. 克隆 lite-avatar 仓库
cd /opt
git clone https://github.com/HumanAIGC/lite-avatar.git

# 2. 解压示例数据（仓库中已包含 sample_data.zip，约500MB）
cd lite-avatar/data
unzip sample_data.zip

# 3. 复制Avatar数据到lightweight-avatar-chat
cd /opt/lightavatar
mkdir -p models/lite_avatar/default

# 复制编码器和解码器
cp /opt/lite-avatar/data/preload/net_encode.pt models/lite_avatar/default/
cp /opt/lite-avatar/data/preload/net_decode.pt models/lite_avatar/default/

# 复制其他文件
cp /opt/lite-avatar/data/preload/neutral_pose.npy models/lite_avatar/default/
cp /opt/lite-avatar/data/preload/bg_video.mp4 models/lite_avatar/default/
cp /opt/lite-avatar/data/preload/face_box.txt models/lite_avatar/default/

# 复制参考帧目录
cp -r /opt/lite-avatar/data/preload/ref_frames models/lite_avatar/default/

# 验证数据
ls -lh models/lite_avatar/default/
```

**说明**：
- ✅ `sample_data.zip` 已包含在仓库中（~500MB）
- ✅ 包含完整的示例Avatar数据（编码器、背景视频、参考帧等）
- ✅ 无需额外下载，克隆仓库即可获得

#### 方式2：从 ModelScope 下载（备选）

如果不想克隆完整仓库：

```bash
# 访问 ModelScope 下载 Avatar 数据包
# https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery

# 下载后解压到 /opt/lightavatar/models/lite_avatar/default/
```

### 3. 下载 Audio2Mouth 模型

#### 方式1：使用官方下载脚本（推荐）⭐

```bash
# 1. 进入lite-avatar目录
cd /opt/lite-avatar

# 2. 安装modelscope CLI（如果未安装）
pip install modelscope

# 3. 运行官方下载脚本
bash download_model.sh
# 脚本会下载3个文件：
# - model_1.onnx (~140MB) - Audio2Mouth模型 ✅ 需要
# - lm.pb (~10MB) - Paraformer语言模型 ❌ 不需要
# - model.pb (~400MB) - Paraformer ASR模型 ❌ 不需要

# 4. 只复制model_1.onnx到lightweight-avatar-chat
cp weights/model_1.onnx /opt/lightavatar/models/lite_avatar/

# 验证
ls -lh /opt/lightavatar/models/lite_avatar/model_1.onnx
# 应该显示约140MB
```

**说明**：
- ✅ lightweight-avatar-chat 使用自己的ASR（Faster-Whisper/Skynet），不需要Paraformer
- ✅ 只需要 `model_1.onnx` 用于音频特征→口型参数转换
- ✅ 可选：删除不需要的Paraformer模型节省空间（~410MB）

#### 方式2：手动从ModelScope下载

```bash
# 访问 ModelScope 下载 model_1.onnx
# https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatar/files

# 下载后放置到
# /opt/lightavatar/models/lite_avatar/model_1.onnx
```

#### 方式3：使用modelscope命令行工具

```bash
cd /opt/lightavatar

# 使用modelscope CLI直接下载
pip install modelscope
modelscope download \
    --model HumanAIGC-Engineering/LiteAvatar \
    lite_avatar_weights/model_1.onnx \
    --local_dir ./models/lite_avatar
```

## ⚙️ 配置

### 修改配置文件

编辑 `config/config.yaml`：

```yaml
# Avatar settings
avatar:
  engine: "lite"  # 改为 "lite" 启用 LiteAvatar
  fps: 30  # LiteAvatar 原生30fps
  resolution: [512, 512]
  
  # LiteAvatar settings
  avatar_name: "default"  # Avatar数据名称
  use_gpu: false  # 是否使用GPU
  render_threads: 1  # 渲染线程数（CPU多核可增加）
  bg_frame_count: 150  # 使用的背景帧数
```

### 环境变量（可选）

```bash
# 设置环境变量覆盖配置
export AVATAR_ENGINE=lite
export AVATAR_FPS=30
export AVATAR_NAME=default
```

## 🚀 启动服务

```bash
# 启动后端
cd backend
python app/main.py

# 查看日志确认
# 应该看到：Using LiteAvatar engine for session xxx
```

## 🔄 引擎切换

系统支持在不同会话中动态使用不同引擎：

### 切换到 LiteAvatar

```yaml
# config/config.yaml
avatar:
  engine: "lite"
```

### 切换回 Wav2Lip

```yaml
# config/config.yaml
avatar:
  engine: "wav2lip"
```

**重启服务生效**

## 📁 目录结构

```
lightweight-avatar-chat/
├── backend/
│   └── handlers/
│       └── avatar/
│           ├── wav2lip_handler.py      # Wav2Lip引擎
│           └── lite_avatar_handler.py  # LiteAvatar引擎（新增）
├── models/
│   └── lite_avatar/                    # LiteAvatar模型目录（新增）
│       ├── model_1.onnx               # Audio2Mouth模型
│       └── default/                   # 默认Avatar数据
│           ├── net_encode.pt
│           ├── net_decode.pt
│           ├── neutral_pose.npy
│           ├── bg_video.mp4
│           ├── face_box.txt
│           └── ref_frames/
├── scripts/
│   └── prepare_lite_avatar_data.py    # 数据准备脚本（新增）
└── docs/
    └── LITE_AVATAR_INTEGRATION.md     # 本文档
```

## 🎨 制作自定义 Avatar

### 1. 准备素材

- **背景视频**：包含人物的视频（建议150帧）
- **人脸图像**：清晰的正面照

### 2. 使用 lite-avatar-main 工具

```bash
cd d:/Aprojects/Light-avatar/lite-avatar-main

# 运行数据生成工具（需要参考lite-avatar-main文档）
# 生成 net_encode.pt, net_decode.pt, ref_frames等文件
```

### 3. 复制到项目

```bash
python scripts/prepare_lite_avatar_data.py \
    --lite-avatar-path "d:/Aprojects/Light-avatar/lite-avatar-main" \
    --avatar my_custom_avatar
```

### 4. 配置使用

```yaml
# config/config.yaml
avatar:
  engine: "lite"
  avatar_name: "my_custom_avatar"
```

## 🐛 故障排查

### 问题1：找不到 Avatar 数据

**错误信息：**
```
Avatar数据目录不存在: models/lite_avatar/default
```

**解决方案：**
```bash
# 运行数据准备脚本
python scripts/prepare_lite_avatar_data.py
```

### 问题2：找不到 model_1.onnx

**错误信息：**
```
Audio2Mouth模型不存在: models/lite_avatar/model_1.onnx
```

**解决方案：**
- 从 ModelScope 手动下载 model_1.onnx
- 放置到 `models/lite_avatar/model_1.onnx`

### 问题3：无法导入 Paraformer 特征提取

**错误信息：**
```
无法导入Paraformer特征提取
```

**解决方案：**
```bash
# 确保 lite-avatar-main 路径正确
# 或在代码中修改路径：
# lite_avatar_handler.py 第469行
```

### 问题4：渲染性能不佳

**优化建议：**
1. 增加渲染线程（多核CPU）
   ```yaml
   avatar:
     render_threads: 2  # 或 4
   ```

2. 减少背景帧数
   ```yaml
   avatar:
     bg_frame_count: 50  # 降低到50
   ```

3. 降低分辨率
   ```yaml
   avatar:
     resolution: [384, 384]
   ```

## 📊 性能基准

### 测试环境

- CPU: Intel i7-10700 (8核16线程)
- 内存: 16GB
- OS: Windows 10

### 性能数据

| 引擎 | FPS | 首帧延迟 | CPU占用 | 内存占用 |
|------|-----|---------|---------|---------|
| Wav2Lip | 15-20 | 1.5s | 60-80% | 2.5GB |
| LiteAvatar | 28-30 | 0.8s | 40-50% | 2.0GB |

### 音频→视频延迟分解

**LiteAvatar 处理流程：**
1. 特征提取（Paraformer）: ~200ms
2. 口型参数预测：~100ms/秒音频
3. 帧渲染：~30ms/帧（30fps = 1秒30帧 = ~900ms）
4. 视频编码：~200ms

**总延迟：约 1.4秒（1秒音频）**

## 🔗 相关资源

- [lite-avatar-main 项目](d:/Aprojects/Light-avatar/lite-avatar-main)
- [LiteAvatar ModelScope](https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatar)
- [LiteAvatarGallery](https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery)

## ❓ 常见问题

### Q1: 可以同时使用两种引擎吗？

可以。系统支持配置级切换，重启服务后生效。未来可以实现会话级动态切换。

### Q2: LiteAvatar 需要 GPU 吗？

不需要。LiteAvatar 专为 CPU 设计，但也支持 GPU 加速（需设置 `use_gpu: true`）。

### Q3: 如何获得更多 Avatar？

访问 [LiteAvatarGallery](https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery) 下载预制 Avatar，或使用 lite-avatar-main 工具制作自定义 Avatar。

### Q4: 两种引擎可以共享配置吗？

部分共享：
- 共享：`fps`, `resolution`
- 独立：Wav2Lip 的 `template`，LiteAvatar 的 `avatar_name`

### Q5: 性能对比如何选择？

| 需求 | 推荐引擎 |
|------|---------|
| 照片级真实感 | Wav2Lip + GAN |
| 高帧率流畅动画 | LiteAvatar |
| 低CPU占用 | LiteAvatar |
| 任意视频源 | Wav2Lip |
| 固定角色 | LiteAvatar |

## 📝 后续计划

- [ ] 支持会话级动态引擎切换
- [ ] 提供 Avatar 数据转换工具
- [ ] 优化 Paraformer 特征提取性能
- [ ] 支持实时参数调整（表情、动作）
- [ ] 提供 WebUI 配置界面

## 📄 许可证

本集成遵循：
- lightweight-avatar-chat: MIT License
- lite-avatar-main: 参考其原始许可证

---

**集成完成日期：** 2025-10-19  
**维护者：** lightweight-avatar-chat team
