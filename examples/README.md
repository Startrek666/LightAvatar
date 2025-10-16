# 集成示例

本目录包含将数字人系统集成到其他平台的示例代码。

## 📁 文件说明

| 文件 | 说明 | 使用场景 |
|------|------|---------|
| `jitsi_integration.py` | Jitsi Meet 集成 | 视频会议主持人/助手 |
| `virtual_camera_stream.py` | 虚拟摄像头推流 | Jitsi/Zoom/Teams 通用方案 |

---

## 🎯 快速开始

### 1. Jitsi Meet 集成

**场景：** 数字人作为 AI 主持人加入 Jitsi 视频会议

```bash
# 安装依赖
pip install aiohttp websockets

# 运行机器人
python jitsi_integration.py
```

**功能：**
- ✅ 自动加入指定会议室
- ✅ 监听会议对话
- ✅ 关键词触发回复
- ✅ 定时会议主持（议程提醒）
- ✅ 会议总结

---

### 2. 虚拟摄像头推流

**场景：** 将数字人视频作为虚拟摄像头，供任何视频会议软件使用

#### Linux 安装

```bash
# 1. 安装 v4l2loopback
sudo apt install v4l2loopback-dkms v4l2loopback-utils

# 2. 加载虚拟摄像头模块
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="AvatarCam"

# 3. 验证设备
v4l2-ctl --list-devices

# 4. 运行推流脚本
python virtual_camera_stream.py
```

#### Windows 安装

```bash
# 1. 安装 OBS Studio
# 下载：https://obsproject.com/

# 2. 启动 OBS 并开启 Virtual Camera
# 工具 -> 虚拟摄像头 -> 启动

# 3. 运行推流脚本
python virtual_camera_stream.py
```

#### macOS 安装

```bash
# 1. 安装 CamTwist 或 OBS Studio
brew install --cask obs

# 2. 启动虚拟摄像头
# OBS -> 工具 -> 虚拟摄像头

# 3. 运行推流脚本
python virtual_camera_stream.py
```

**使用方式：**
1. 运行脚本后，虚拟摄像头会显示待机画面
2. 在 Jitsi/Zoom/Teams 中选择 "AvatarCam" 摄像头
3. 在脚本命令行输入文字，数字人会说话并显示在会议中

---

## 🔌 集成 API 使用

### RESTful API 示例

```python
import requests

# 1. 创建会话
response = requests.post("http://localhost:8000/api/v1/sessions")
session_id = response.json()["session_id"]

# 2. 发送文本
response = requests.post(
    f"http://localhost:8000/api/v1/sessions/{session_id}/text",
    json={"text": "你好"}
)
print(response.json())

# 3. 清理会话
requests.delete(f"http://localhost:8000/api/v1/sessions/{session_id}")
```

### WebSocket 示例

```python
import asyncio
import websockets
import json

async def chat():
    uri = "ws://localhost:8000/ws/my-session"
    async with websockets.connect(uri) as ws:
        # 发送文本
        await ws.send(json.dumps({
            "type": "text",
            "text": "你好",
            "streaming": True
        }))
        
        # 接收响应
        async for message in ws:
            if isinstance(message, bytes):
                # 保存视频
                with open('response.mp4', 'wb') as f:
                    f.write(message)
            else:
                print(json.loads(message))

asyncio.run(chat())
```

---

## 📚 更多集成方案

详见 [集成指南](../docs/INTEGRATION_GUIDE.md)，包含：

- Discord 机器人
- 微信公众号/企业微信
- Microsoft Teams
- Zoom
- Slack
- Telegram

---

## ⚙️ 配置说明

所有示例都可以通过环境变量或配置文件自定义：

```bash
# 数字人服务地址
export AVATAR_API_URL="http://localhost:8000"

# Jitsi 服务器
export JITSI_DOMAIN="meet.jit.si"

# 虚拟摄像头设备号
export VIRTUAL_CAMERA_INDEX=10
```

---

## 🛠️ 开发指南

### 创建自定义集成

```python
from integration_base import AvatarIntegration

class MyPlatformIntegration(AvatarIntegration):
    async def on_message(self, message):
        """处理平台消息"""
        # 调用数字人 API
        response = await self.get_avatar_response(message.text)
        
        # 回复到平台
        await self.send_to_platform(response)

# 使用
integration = MyPlatformIntegration(
    avatar_api_url="http://localhost:8000"
)
await integration.run()
```

---

## 📊 性能参考

| 集成方式 | 延迟 | CPU 占用 | 适用场景 |
|---------|------|---------|---------|
| RESTful API | ~2s | 低 | 简单问答 |
| WebSocket | ~1s | 中 | 实时对话 |
| 虚拟摄像头 | ~500ms | 高 | 视频会议 |

---

## ❓ 常见问题

### Q: Jitsi 集成需要 TURN 服务器吗？

**A:** 不需要！我们使用的是虚拟摄像头方案，数字人视频作为本地摄像头输入，不涉及 P2P 连接。

### Q: 虚拟摄像头在 Jitsi 中看不到？

**A:** 
1. 确认虚拟摄像头已加载：`ls /dev/video*`（Linux）
2. 刷新浏览器权限
3. 在 Jitsi 设置中手动选择摄像头

### Q: 多人会议时数字人如何工作？

**A:** 数字人会监听所有人的发言：
- **全程监听**：ASR 识别所有对话
- **关键词触发**：检测到 "@AI" 等关键词时回复
- **定时主持**：按照议程定时发言

### Q: 可以同时集成多个平台吗？

**A:** 可以！每个平台使用独立的会话 ID，资源隔离。

---

## 📞 技术支持

- 详细文档：[docs/INTEGRATION_GUIDE.md](../docs/INTEGRATION_GUIDE.md)
- API 文档：http://localhost:8000/docs
- 问题反馈：GitHub Issues

