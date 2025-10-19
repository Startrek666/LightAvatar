# LiteAvatar 模型下载完整指南

## 🎯 需要下载的内容

### 1. Avatar数据包（~500MB）
- 包含：编解码器、背景视频、参考帧等
- 来源：ModelScope LiteAvatarGallery

### 2. Audio2Mouth模型（~140MB）
- 文件：model_1.onnx
- 来源：ModelScope LiteAvatar

---

## 📥 方式1：一键自动化（推荐）⭐

### 前提条件
```bash
# 克隆 lite-avatar 仓库（包含示例数据）
cd /opt
git clone https://github.com/HumanAIGC/lite-avatar.git
# 或国内镜像
git clone https://gitee.com/mirrors/lite-avatar.git

# 安装modelscope CLI
pip install modelscope
```

### 步骤1：下载Audio2Mouth模型

```bash
cd /opt/lite-avatar

# 运行下载脚本
bash download_model.sh
```

**这个脚本会自动下载：**
- ✅ `model_1.onnx` → `weights/model_1.onnx` (~140MB)
- ✅ `lm.pb` → `weights/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/lm/` (~10MB)
- ✅ `model.pb` → `weights/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/` (~400MB)

### 步骤2：准备Avatar数据（使用仓库自带示例数据）

**重要**：`sample_data.zip` 已包含在 lite-avatar 仓库中！

```bash
cd /opt/lite-avatar/data

# 验证文件存在
ls -lh sample_data.zip  # 应该显示 ~500MB

# 解压示例数据
unzip sample_data.zip
```

**说明**：
- ✅ `sample_data.zip` 已在仓库的 `data/` 目录中
- ✅ 无需额外下载，克隆仓库时已包含
- ✅ 包含完整的示例Avatar数据（编码器、背景视频、参考帧等）

### 步骤3：复制到lightweight-avatar-chat

```bash
cd /opt/lightavatar
mkdir -p models/lite_avatar/default

# 复制Avatar数据
cp /opt/lite-avatar/data/sample_data/net_encode.pt models/lite_avatar/default/
cp /opt/lite-avatar/data/sample_data/net_decode.pt models/lite_avatar/default/
cp /opt/lite-avatar/data/sample_data/neutral_pose.npy models/lite_avatar/default/
cp /opt/lite-avatar/data/sample_data/bg_video.mp4 models/lite_avatar/default/
cp /opt/lite-avatar/data/sample_data/face_box.txt models/lite_avatar/default/
cp -r /opt/lite-avatar/data/sample_data/ref_frames models/lite_avatar/default/

# 复制模型文件
cp /opt/lite-avatar/weights/model_1.onnx models/lite_avatar/

# 验证
ls -lh models/lite_avatar/
ls -lh models/lite_avatar/default/
```

---

## 📥 方式2：使用ModelScope SDK

### 安装SDK

```bash
pip install modelscope
```

### 下载Avatar数据

```python
# Python脚本
from modelscope import snapshot_download

# 下载LiteAvatarGallery
model_dir = snapshot_download(
    'HumanAIGC-Engineering/LiteAvatarGallery',
    cache_dir='./models'
)
print(f"Downloaded to: {model_dir}")
```

### 下载Audio2Mouth模型

```bash
# 命令行方式
modelscope download \
    --model HumanAIGC-Engineering/LiteAvatar \
    lite_avatar_weights/model_1.onnx \
    --local_dir ./models/lite_avatar
```

---

## 📥 方式3：手动下载

### Avatar数据

1. 访问 https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery
2. 点击 "Files" → 下载 `sample_data.zip`
3. 解压到临时目录
4. 将解压内容放置到：
   ```
   lightweight-avatar-chat/models/lite_avatar/default/
   ├── net_encode.pt
   ├── net_decode.pt
   ├── neutral_pose.npy
   ├── bg_video.mp4
   ├── face_box.txt
   └── ref_frames/
       └── ref_*.jpg (150个文件)
   ```

### Audio2Mouth模型

1. 访问 https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatar/files
2. 找到并下载 `lite_avatar_weights/model_1.onnx` (~140MB)
3. 放置到：
   ```
   lightweight-avatar-chat/models/lite_avatar/model_1.onnx
   ```

---

## ✅ 验证下载

### 检查文件结构

```bash
cd d:/Aprojects/Light-avatar/lightweight-avatar-chat

# 验证目录结构
tree models/lite_avatar
```

**期望结构：**
```
models/lite_avatar/
├── model_1.onnx                    # 140MB
└── default/
    ├── net_encode.pt              # ~50MB
    ├── net_decode.pt              # ~50MB
    ├── neutral_pose.npy           # <1MB
    ├── bg_video.mp4               # ~100MB
    ├── face_box.txt               # <1KB
    └── ref_frames/
        ├── ref_00000.jpg
        ├── ref_00001.jpg
        └── ... (150个文件)
```

### 运行验证脚本

```bash
python scripts/prepare_lite_avatar_data.py --skip-extract

# 应该看到：
# ✓ net_encode.pt (50.2 MB)
# ✓ net_decode.pt (48.5 MB)
# ✓ neutral_pose.npy (0.1 MB)
# ✓ bg_video.mp4 (98.3 MB)
# ✓ face_box.txt (0.0 MB)
# ✓ ref_frames/ (150 个文件)
# ✓ model_1.onnx (140.2 MB)
```

---

## 🌐 下载源对比

| 方式 | 速度 | 难度 | 推荐度 |
|------|------|------|--------|
| **官方脚本** | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| **ModelScope SDK** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **手动下载** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

### 国内用户建议

✅ **推荐**：
1. 使用 ModelScope（阿里巴巴提供，国内访问快）
2. 使用官方 `download_model.sh/bat` 脚本

⚠️ **避免**：
- 直接从 GitHub Release 下载（可能很慢）
- Hugging Face（国内访问不稳定）

---

## 🔧 常见问题

### Q1: ModelScope下载很慢？

```bash
# 使用国内镜像加速
export MODELSCOPE_CACHE=~/.cache/modelscope
export HF_ENDPOINT=https://hf-mirror.com
```

### Q2: 下载中断了怎么办？

ModelScope支持断点续传，重新运行下载命令即可继续。

### Q3: 没有Git怎么办？

可以直接从网页下载：
- https://github.com/HumanAIGC/lite-avatar/archive/refs/heads/main.zip
- 解压后运行 `download_model.bat`

### Q4: 网络不好，有离线包吗？

可以在已下载的机器上打包：
```bash
# 打包lite-avatar-main整个目录
cd d:/Aprojects/Light-avatar
tar -czf lite-avatar-with-models.tar.gz lite-avatar-main/

# 传输到目标机器后解压
tar -xzf lite-avatar-with-models.tar.gz
```

---

## 📊 文件大小参考

| 文件 | 大小 | 说明 |
|------|------|------|
| sample_data.zip | ~500MB | Avatar数据包 |
| model_1.onnx | ~140MB | Audio2Mouth模型 |
| lm.pb | ~10MB | Paraformer语言模型 |
| model.pb | ~400MB | Paraformer ASR模型 |
| **总计** | **~1.05GB** | 完整下载 |

**注意**：lightweight-avatar-chat 只需要 **~640MB**：
- sample_data.zip (~500MB)
- model_1.onnx (~140MB)

Paraformer的 lm.pb 和 model.pb 仅在使用lite-avatar-main独立运行时需要。

---

## 🎉 下载完成检查清单

在启动服务前确认：

- [ ] ✅ `models/lite_avatar/model_1.onnx` 存在 (~140MB)
- [ ] ✅ `models/lite_avatar/default/net_encode.pt` 存在 (~50MB)
- [ ] ✅ `models/lite_avatar/default/net_decode.pt` 存在 (~50MB)
- [ ] ✅ `models/lite_avatar/default/bg_video.mp4` 存在 (~100MB)
- [ ] ✅ `models/lite_avatar/default/ref_frames/` 包含150个jpg文件
- [ ] ✅ 配置文件 `config/config.yaml` 中 `engine: "lite"`

全部完成后，运行测试：
```bash
python scripts/test_lite_avatar.py
```

---

**更新日期**：2025-10-19  
**版本**：v1.0
