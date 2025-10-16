# 🔌 集成指南

本指南介绍如何将数字人系统集成到其他应用中。

---

## 📋 目录

1. [集成方式概览](#集成方式概览)
2. [RESTful API 集成](#restful-api-集成)
3. [WebSocket 集成](#websocket-集成)
4. [Jitsi Meet 集成](#jitsi-meet-集成)
5. [其他平台集成](#其他平台集成)

---

## 集成方式概览

我们的数字人系统提供**三种集成方式**：

| 方式 | 适用场景 | 复杂度 | 实时性 |
|------|---------|-------|-------|
| **RESTful API** | 简单问答、异步处理 | 低 | 中 |
| **WebSocket** | 实时对话、流式响应 | 中 | 高 |
| **WebRTC（规划中）** | 视频会议集成 | 高 | 极高 |

---

## RESTful API 集成

### 快速开始

```python
import requests

# 1. 创建会话
response = requests.post("http://localhost:8000/api/v1/sessions", json={
    "config": {
        "avatar_template": "templates/female_01.jpg",
        "tts_voice": "zh-CN-XiaoxiaoNeural"
    }
})
session_id = response.json()["session_id"]

# 2. 发送文本，获取数字人回复
response = requests.post(
    f"http://localhost:8000/api/v1/sessions/{session_id}/text",
    json={"text": "你好，请介绍一下自己", "streaming": False}
)
result = response.json()

print(f"数字人回复: {result['text']}")
print(f"视频链接: {result['video_url']}")

# 3. 清理会话
requests.delete(f"http://localhost:8000/api/v1/sessions/{session_id}")
```

### API 端点

#### 创建会话
```http
POST /api/v1/sessions
Content-Type: application/json

{
    "config": {
        "avatar_template": "templates/female_01.jpg",
        "llm_model": "gpt-3.5-turbo",
        "tts_voice": "zh-CN-XiaoxiaoNeural"
    }
}
```

**响应：**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "active",
    "created_at": "2025-01-15T10:30:00"
}
```

#### 文本对话
```http
POST /api/v1/sessions/{session_id}/text
Content-Type: application/json

{
    "text": "你好",
    "streaming": false
}
```

**响应：**
```json
{
    "session_id": "...",
    "text": "你好！我是你的数字助手，很高兴认识你。",
    "audio_url": "/api/v1/sessions/{session_id}/audio/latest",
    "video_url": "/api/v1/sessions/{session_id}/video/latest"
}
```

#### 音频对话
```http
POST /api/v1/sessions/{session_id}/audio
Content-Type: application/json

{
    "audio_data": "base64_encoded_audio",
    "format": "wav"
}
```

---

## WebSocket 集成

### 实时对话

**JavaScript 示例：**

```javascript
// 连接 WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/my-session-123');
ws.binaryType = 'blob';

// 监听消息
ws.onmessage = async (event) => {
    if (event.data instanceof Blob) {
        // 接收视频数据
        const videoUrl = URL.createObjectURL(event.data);
        document.querySelector('#avatar-video').src = videoUrl;
    } else {
        // 接收 JSON 消息
        const data = JSON.parse(event.data);
        
        if (data.type === 'text_chunk') {
            // 流式文本响应
            console.log('数字人说:', data.data.chunk);
        } else if (data.type === 'stream_complete') {
            console.log('完整回复:', data.data.full_text);
        }
    }
};

// 发送文本消息
function sendText(text) {
    ws.send(JSON.stringify({
        type: 'text',
        text: text,
        streaming: true
    }));
}

// 发送音频
function sendAudio(audioBlob) {
    const reader = new FileReader();
    reader.onload = () => {
        ws.send(JSON.stringify({
            type: 'audio',
            data: reader.result.split(',')[1]  // Base64
        }));
    };
    reader.readAsDataURL(audioBlob);
}
```

**Python 示例：**

```python
import websockets
import asyncio
import json

async def chat_with_avatar():
    uri = "ws://localhost:8000/ws/my-session"
    
    async with websockets.connect(uri) as ws:
        # 发送文本
        await ws.send(json.dumps({
            "type": "text",
            "text": "你好，请介绍一下自己",
            "streaming": True
        }))
        
        # 接收响应
        async for message in ws:
            if isinstance(message, bytes):
                # 视频数据
                with open('avatar_response.mp4', 'wb') as f:
                    f.write(message)
            else:
                # JSON 数据
                data = json.loads(message)
                if data['type'] == 'text_chunk':
                    print(data['data']['chunk'], end='', flush=True)

asyncio.run(chat_with_avatar())
```

---

## Jitsi Meet 集成

### 方案 1: 作为虚拟参与者（推荐）

**架构：**
```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│ Jitsi Meet  │ ◄─────► │ 数字人机器人  │ ◄─────► │ 数字人服务   │
│  (WebRTC)   │  音频   │  (适配层)    │   API   │  (后端)     │
└─────────────┘         └──────────────┘         └─────────────┘
     ↑                          │
     │                      推送视频
     └──────────────────────────┘
```

**实现步骤：**

1. **创建 Jitsi 机器人**

```python
# 见 examples/jitsi_integration.py
from jitsi_integration import JitsiAvatarBot

bot = JitsiAvatarBot(
    avatar_api_url="http://localhost:8000",
    jitsi_domain="meet.jit.si"
)

await bot.initialize()
await bot.join_meeting("TechTeamMeeting", "AI主持人")
```

2. **音频处理流程**

```
Jitsi 音频流 → ASR (Skynet Whisper) → 检测关键词
                                          ↓
                                    触发数字人回复
                                          ↓
                         LLM → TTS → Wav2Lip → 推送视频到 Jitsi
```

3. **视频推送方式**

**方式 A：虚拟摄像头（最简单）**
```bash
# 使用 OBS Virtual Camera 或 v4l2loopback
# 将数字人视频作为虚拟摄像头输入

# Linux
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="Avatar"
ffmpeg -re -i avatar.mp4 -f v4l2 /dev/video10

# Jitsi 选择 "Avatar" 摄像头
```

**方式 B：WebRTC 直接推流**
```python
from aiortc import RTCPeerConnection, VideoStreamTrack

class AvatarVideoTrack(VideoStreamTrack):
    def __init__(self, avatar_video_url):
        super().__init__()
        self.video_url = avatar_video_url
    
    async def recv(self):
        # 读取数字人视频帧并推送
        frame = await self.get_next_frame()
        return frame

# 建立 WebRTC 连接并推流到 Jitsi
```

### 方案 2: Jitsi 前端插件

**在 Jitsi 网页中嵌入数字人：**

```javascript
// jitsi-avatar-plugin.js
export class AvatarPlugin {
    constructor(api) {
        this.api = api;  // JitsiMeetExternalAPI
        this.avatarWs = null;
    }
    
    init() {
        // 创建数字人窗口
        const avatarDiv = document.createElement('div');
        avatarDiv.id = 'avatar-container';
        avatarDiv.innerHTML = '<video id="avatar-video" autoplay></video>';
        document.body.appendChild(avatarDiv);
        
        // 连接数字人服务
        this.avatarWs = new WebSocket('ws://localhost:8000/ws/jitsi-session');
        
        // 监听会议音频
        this.api.addEventListener('audioAvailabilityChanged', (event) => {
            if (event.available) {
                this.startListening();
            }
        });
        
        // 接收数字人视频
        this.avatarWs.onmessage = (event) => {
            if (event.data instanceof Blob) {
                const videoUrl = URL.createObjectURL(event.data);
                document.querySelector('#avatar-video').src = videoUrl;
            }
        };
    }
    
    startListening() {
        // 获取会议音频流并发送给数字人服务
        const audioTracks = this.api.getAudioTracks();
        // ... 音频处理逻辑
    }
}

// 在 Jitsi 会议中加载插件
const api = new JitsiMeetExternalAPI('meet.jit.si', {
    roomName: 'MyMeeting'
});
const avatarPlugin = new AvatarPlugin(api);
avatarPlugin.init();
```

### 使用场景

**1. 会议主持人**
```python
# 定时提醒
await bot.speak("还有 10 分钟会议就要结束了")

# 议程引导
await bot.speak("接下来请张三分享技术方案")
```

**2. 会议助手**
```python
# 监听关键词
if "@助手" in meeting_transcription:
    await bot.speak("我在，请问有什么可以帮助的？")

# 会议记录
await bot.speak("本次会议讨论了以下三个议题...")
```

**3. 同声传译**
```python
# 检测发言语言
if detected_language == "en":
    translated = await translate_to_chinese(text)
    await bot.speak(translated)
```

---

## 其他平台集成

### Zoom

**使用 Zoom SDK：**
```python
from zoomus import ZoomClient

client = ZoomClient('CLIENT_ID', 'CLIENT_SECRET')

# 创建会议
meeting = client.meeting.create(user_id='me', meeting_dict={
    "topic": "AI主持的会议"
})

# 加入会议（使用 Zoom Meeting SDK）
# 推送数字人视频流
```

### Microsoft Teams

**使用 Teams Bot Framework：**
```python
from botbuilder.core import BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity

class AvatarTeamsBot:
    async def on_message_activity(self, turn_context: TurnContext):
        # 接收 Teams 消息
        user_message = turn_context.activity.text
        
        # 调用数字人服务
        response = await self.get_avatar_response(user_message)
        
        # 回复视频卡片
        await turn_context.send_activity(Activity(
            type="message",
            attachments=[{
                "contentType": "video/mp4",
                "contentUrl": response['video_url']
            }]
        ))
```

### Discord

**使用 Discord.py：**
```python
import discord

class AvatarDiscordBot(discord.Client):
    async def on_message(self, message):
        if message.author == self.user:
            return
        
        # 调用数字人服务
        response = await self.get_avatar_response(message.content)
        
        # 发送视频
        await message.channel.send(
            content=response['text'],
            file=discord.File(response['video_path'])
        )

bot = AvatarDiscordBot()
bot.run('YOUR_DISCORD_TOKEN')
```

### 微信公众号/企业微信

**使用 itchat 或企业微信 API：**
```python
import itchat

@itchat.msg_register(itchat.content.TEXT)
def text_reply(msg):
    # 调用数字人服务
    response = requests.post(
        "http://localhost:8000/api/v1/sessions/wechat-session/text",
        json={"text": msg['Text']}
    ).json()
    
    # 回复文本
    return response['text']
    
    # 可以发送视频（需要先上传到微信服务器）
    # itchat.send_video(response['video_path'], msg['FromUserName'])

itchat.auto_login(hotReload=True)
itchat.run()
```

---

## 集成最佳实践

### 1. 会话管理

```python
# 每个用户/房间使用独立会话
session_map = {
    "user_123": "session_abc",
    "room_456": "session_def"
}

# 定期清理不活跃会话
async def cleanup_inactive_sessions():
    for session_id in inactive_sessions:
        await requests.delete(f"/api/v1/sessions/{session_id}")
```

### 2. 错误处理

```python
async def safe_avatar_call(session_id, text):
    try:
        response = await call_avatar_api(session_id, text)
        return response
    except TimeoutError:
        return {"text": "抱歉，我现在有点忙，请稍后再试"}
    except Exception as e:
        logger.error(f"Avatar error: {e}")
        return {"text": "抱歉，出了点问题"}
```

### 3. 性能优化

```python
# 使用连接池
session = aiohttp.ClientSession(
    connector=aiohttp.TCPConnector(limit=100)
)

# 并发处理
tasks = [
    avatar_speak(session_id, text1),
    avatar_speak(session_id, text2)
]
await asyncio.gather(*tasks)
```

### 4. 缓存策略

```python
# 常用回复缓存
cache = {
    "你好": {
        "text": "你好！很高兴见到你。",
        "video_path": "cache/hello.mp4"
    }
}

if user_input in cache:
    return cache[user_input]
else:
    response = await call_avatar_api(session_id, user_input)
    cache[user_input] = response
```

---

## 常见问题

### Q: 可以同时集成到多个平台吗？

**A:** 可以！每个平台使用独立的会话 ID，互不干扰。

```python
sessions = {
    "jitsi_room_1": "session_001",
    "discord_channel_2": "session_002",
    "wechat_user_3": "session_003"
}
```

### Q: 性能瓶颈在哪里？

**A:** 主要瓶颈：
1. **Wav2Lip 生成**（300ms/句）：建议使用 GPU 或优化参数
2. **并发会话数**：CPU 建议 ≤10 个会话
3. **网络传输**：大视频文件传输慢，建议使用 CDN

### Q: 支持多语言吗？

**A:** 支持！在配置中设置：

```yaml
asr:
  language: "en"  # zh, en, ja, ko, es, fr, de

tts:
  voice: "en-US-JennyNeural"  # 英文女声
```

---

## 技术支持

- **GitHub Issues**: [提交问题](https://github.com/yourrepo/issues)
- **示例代码**: `examples/` 目录
- **API 文档**: http://localhost:8000/docs

