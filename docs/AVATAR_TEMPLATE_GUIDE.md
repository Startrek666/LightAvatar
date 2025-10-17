# Avatar模板制作指南

> 🎭 如何准备高质量的数字人模板

---

## 📋 目录

1. [模板要求](#模板要求)
2. [视频模板制作](#视频模板制作)
3. [图片模板制作](#图片模板制作)
4. [质量优化](#质量优化)
5. [常见问题](#常见问题)

---

## 模板要求

### 基本规格

| 类型 | 格式 | 分辨率 | 时长/大小 | 帧率 |
|------|------|--------|-----------|------|
| 视频 | MP4 | 512x512 | 5-10秒 | 25fps |
| 图片 | JPG/PNG | 512x512 | < 2MB | N/A |

### 拍摄要求

#### ✅ 推荐做法

- **人物位置**: 人脸居中，占画面60-70%
- **光线**: 柔和均匀，避免强烈阴影
- **背景**: 纯色或简单背景（推荐绿幕）
- **姿势**: 正面或微侧面（±15度内）
- **表情**: 自然、微笑、闭嘴状态
- **服装**: 简洁大方，颜色不要过于鲜艳

#### ❌ 避免

- ❌ 侧脸或转头过大
- ❌ 低头或仰头
- ❌ 遮挡面部（帽子、口罩、墨镜）
- ❌ 强烈的背光或侧光
- ❌ 杂乱的背景
- ❌ 大幅度动作

---

## 视频模板制作

### 方法一：手机录制（最简单）

#### 1. 录制设置

```
设备: iPhone/Android手机
分辨率: 1080x1080 或 更高
帧率: 25fps 或 30fps
时长: 5-10秒
格式: MP4
```

#### 2. 录制技巧

**环境布置**:
- 在明亮但光线柔和的室内
- 使用三脚架或稳定手机
- 背景选择纯色墙壁或绿幕

**拍摄指导**:
```
1. 人物站在画面中央
2. 脸部完全露出，头发不遮挡
3. 保持微笑，嘴巴闭合
4. 眼睛看向镜头
5. 可以有轻微的头部晃动（更自然）
6. 不要说话（保持嘴巴闭合）
```

#### 3. 后期处理

使用手机APP或电脑软件：

**推荐工具**:
- 手机: CapCut（剪映）
- 电脑: FFmpeg / Adobe Premiere

**处理步骤**:

```bash
# 使用FFmpeg裁剪和缩放
ffmpeg -i input.mp4 \
  -vf "crop=1080:1080:420:0,scale=512:512" \
  -c:v libx264 -preset medium -crf 23 \
  -r 25 -t 10 \
  output.mp4
```

**参数说明**:
- `crop=1080:1080:420:0` - 裁剪为正方形
- `scale=512:512` - 缩放到512x512
- `-r 25` - 设置帧率为25fps
- `-t 10` - 限制时长为10秒

### 方法二：AI生成（进阶）

使用AI工具生成数字人图片，然后制作视频：

**推荐AI工具**:
- Midjourney
- Stable Diffusion
- Leonardo.ai

**提示词示例**:
```
portrait photo of a young asian woman, 
professional headshot, 
neutral expression, closed mouth,
soft lighting, clean background,
centered composition, 
high quality, 8k
```

**转换为视频**:
```bash
# 使用图片生成静态视频
ffmpeg -loop 1 -i portrait.jpg \
  -c:v libx264 -t 10 -pix_fmt yuv420p \
  -vf "scale=512:512" \
  avatar_template.mp4
```

---

## 图片模板制作

### 适用场景

图片模板适合：
- 快速测试
- 资源受限环境
- 静态展示

**注意**: 图片模板效果不如视频模板自然

### 制作步骤

#### 1. 获取高质量肖像照

**拍摄要求**:
- 正面照片
- 五官清晰
- 光线均匀
- 背景简洁

#### 2. 图片处理

使用Photoshop或在线工具：

**处理清单**:
- [ ] 裁剪为正方形
- [ ] 调整亮度和对比度
- [ ] 移除背景或替换为纯色
- [ ] 缩放到512x512像素
- [ ] 压缩到合适大小（< 2MB）

**命令行处理**:
```bash
# 使用ImageMagick
convert input.jpg \
  -resize 512x512^ \
  -gravity center \
  -crop 512x512+0+0 \
  -quality 90 \
  avatar_template.jpg
```

#### 3. 去除背景（可选）

**在线工具**:
- remove.bg
- Photopea

**Python脚本**:
```python
from rembg import remove
from PIL import Image

# 去除背景
input_img = Image.open('input.jpg')
output_img = remove(input_img)

# 添加白色背景
background = Image.new('RGB', output_img.size, (255, 255, 255))
background.paste(output_img, mask=output_img)

# 保存
background.save('avatar_template.jpg')
```

---

## 质量优化

### 人脸检测测试

使用MediaPipe检测人脸是否合格：

```python
import cv2
import mediapipe as mp

# 初始化人脸检测
mp_face = mp.solutions.face_detection
face_detection = mp_face.FaceDetection(min_detection_confidence=0.5)

# 加载图片
image = cv2.imread('avatar_template.jpg')
rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 检测人脸
results = face_detection.process(rgb_image)

if results.detections:
    for detection in results.detections:
        score = detection.score[0]
        print(f"人脸检测置信度: {score:.2f}")
        
        if score > 0.8:
            print("✓ 人脸检测良好")
        elif score > 0.5:
            print("⚠ 人脸检测一般，建议优化")
        else:
            print("✗ 人脸检测较差，请重新制作")
else:
    print("✗ 未检测到人脸！")
```

### 模板质量评分

**优秀模板** (90-100分):
- ✅ 人脸清晰，五官端正
- ✅ 光线均匀，无阴影
- ✅ 背景干净，无杂物
- ✅ 分辨率512x512，帧率25fps
- ✅ 人脸占比60-70%

**良好模板** (70-89分):
- ✅ 人脸基本清晰
- ⚠ 有轻微阴影或光线不均
- ✅ 背景较简单
- ⚠ 分辨率或帧率略低

**需改进模板** (< 70分):
- ❌ 人脸模糊或遮挡
- ❌ 光线差，阴影严重
- ❌ 背景杂乱
- ❌ 分辨率过低

---

## 常见问题

### Q1: 为什么必须是正方形？

**答**: Wav2Lip模型训练时使用正方形输入，非正方形会导致画面变形。

### Q2: 可以使用真人照片吗？

**答**: 可以，但需注意：
- 获得本人授权
- 符合隐私和肖像权规定
- 遵守相关法律法规

**建议**: 使用AI生成的虚拟人脸更安全。

### Q3: 模板太大怎么办？

**压缩视频**:
```bash
ffmpeg -i input.mp4 -c:v libx264 -crf 28 -preset slow output.mp4
```

**压缩图片**:
```bash
convert input.jpg -quality 85 output.jpg
```

### Q4: 如何制作多个模板？

```bash
# 批量放入models/avatars/目录
models/avatars/
├── female_1.mp4
├── female_2.mp4
├── male_1.mp4
└── business_style.mp4

# 在config.yaml中切换
avatar:
  template: "female_1.mp4"  # 修改这里
```

### Q5: 视频和图片哪个效果好？

**视频模板**:
- ✅ 效果更自然
- ✅ 头部有微动，更真实
- ❌ 文件较大
- ❌ 处理稍慢

**图片模板**:
- ✅ 文件小，速度快
- ✅ 制作简单
- ❌ 效果略显僵硬
- ❌ 缺少自然感

**建议**: 生产环境使用视频模板，测试可用图片。

### Q6: 如何测试模板效果？

```bash
# 启动后端
python backend/app/main.py

# 访问测试页面
http://localhost:8000/docs

# 或直接测试
curl -X POST http://localhost:8000/api/test_avatar \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，我是数字人"}'
```

---

## 模板示例

### 示例1: 商务风格

**特点**:
- 正装
- 专业背景
- 标准证件照姿态

**适用**: 企业客服、虚拟助手

### 示例2: 亲和风格

**特点**:
- 休闲服装
- 微笑表情
- 温暖色调

**适用**: 教育培训、生活服务

### 示例3: 科技风格

**特点**:
- 简约背景
- 现代感服饰
- 冷色调

**适用**: AI助手、科技产品

---

## 推荐资源

### 免费素材网站

- **Pexels**: https://www.pexels.com/
- **Unsplash**: https://unsplash.com/
- **Pixabay**: https://pixabay.com/

**搜索关键词**: 
- "portrait"
- "headshot"
- "professional photo"

### AI生成工具

- **Midjourney**: https://www.midjourney.com/
- **Stable Diffusion**: https://stability.ai/
- **ThisPersonDoesNotExist**: https://thispersondoesnotexist.com/

### 处理工具

- **FFmpeg**: 视频处理
- **ImageMagick**: 图片处理
- **CapCut**: 手机视频编辑
- **Photopea**: 在线PS

---

## 最佳实践

### 制作流程

```
1. 确定数字人风格和定位
   ↓
2. 拍摄或生成原始素材
   ↓
3. 后期处理（裁剪、调色、去背景）
   ↓
4. 转换为标准格式（512x512, 25fps）
   ↓
5. 使用检测脚本验证质量
   ↓
6. 放入models/avatars/目录
   ↓
7. 在config.yaml中配置
   ↓
8. 测试效果并调整
```

### 质量检查清单

- [ ] 分辨率: 512x512
- [ ] 视频帧率: 25fps（如使用视频）
- [ ] 文件大小: < 50MB（视频）/ < 2MB（图片）
- [ ] 人脸检测置信度: > 0.8
- [ ] 人脸占比: 60-70%
- [ ] 光线均匀: 无强烈阴影
- [ ] 背景简洁: 无杂物
- [ ] 表情自然: 微笑、闭嘴

---

## 总结

好的Avatar模板是数字人效果的关键。投入时间制作高质量模板，将大大提升最终效果。

**记住**:
- 质量 > 数量
- 测试 > 假设
- 简洁 > 复杂

**Happy Creating!** 🎨
