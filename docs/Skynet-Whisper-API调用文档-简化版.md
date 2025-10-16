# Skynet Whisper API 调用文档（简化版）

**版本**: 1.0  
**适用场景**: 同服务器内网调用（无需认证）  
**更新日期**: 2025-10-03

---

## 目录

1. [服务概述](#1-服务概述)
2. [快速开始](#2-快速开始)
3. [API 规范](#3-api-规范)
4. [Python 调用示例](#4-python-调用示例)
5. [音频格式要求](#5-音频格式要求)
6. [常见问题](#6-常见问题)

---

## 1. 服务概述

### 1.1 服务端点

```
WebSocket URL: ws://localhost:6010/streaming-whisper/ws/{meeting_id}
```

**参数说明**：
- `meeting_id`: 会话唯一标识符（可以是 UUID 或自定义字符串）

**示例**：
```
ws://localhost:6010/streaming-whisper/ws/my-session-001
ws://localhost:6010/streaming-whisper/ws/550e8400-e29b-41d4-a716-446655440000
```

### 1.2 支持的语言

| 语言码 | 语言 | 语言码 | 语言 |
|-------|------|-------|------|
| zh | 中文 | en | English |
| ja | 日语 | ko | 韩语 |
| es | 西班牙语 | fr | 法语 |
| de | 德语 | ru | 俄语 |
| pt | 葡萄牙语 | it | 意大利语 |

---

## 2. 快速开始

### 2.1 安装依赖

```bash
pip install websocket-client
```

### 2.2 最小示例

```python
import websocket
import json

# 连接服务
ws = websocket.create_connection("ws://localhost:6010/streaming-whisper/ws/test-session")

# 准备 60 字节头部（参与者ID|语言码）
header = "user123|zh".ljust(60, ' ').encode('utf-8')[:60]

# 读取 PCM 音频（16kHz 单声道 Int16）
with open('audio.pcm', 'rb') as f:
    audio_data = f.read(32000)  # 1秒音频

# 发送：头部 + 音频数据
payload = header + audio_data
ws.send(payload, opcode=websocket.ABNF.OPCODE_BINARY)

# 接收转录结果
result = json.loads(ws.recv())
print(f"[{result['type']}] {result['text']}")

ws.close()
```

---

## 3. API 规范

### 3.1 数据发送格式

每条消息结构：
```
[60 字节头部] + [音频数据]
```

#### 60 字节头部格式

```python
header_string = "{participant_id}|{language_code}"
# 用空格填充至 60 字节
header = header_string.ljust(60, ' ').encode('utf-8')[:60]
```

**示例**：
```python
# 中文
header = "user-001|zh".ljust(60, ' ').encode('utf-8')[:60]

# 英文
header = "speaker-a|en".ljust(60, ' ').encode('utf-8')[:60]
```

#### 音频数据要求

| 参数 | 要求 |
|------|------|
| 采样率 | 16000 Hz |
| 声道 | 单声道（Mono） |
| 位深度 | 16 bit (Int16) |
| 编码 | PCM |
| 文件头 | 无（纯音频数据） |
| 推荐块大小 | 32000 字节（1秒） |

### 3.2 数据接收格式

服务器返回 JSON 格式：

```json
{
  "type": "interim",           // "interim" 临时结果 或 "final" 最终结果
  "text": "识别的文字内容",
  "ts": 1696319551000,        // 时间戳（毫秒）
  "variance": 0.85,           // 置信度 (0.0-1.0)
  "audio": ""                 // 通常为空
}
```

**消息类型说明**：
- **interim（临时）**: 实时返回，频繁更新，用于实时显示
- **final（最终）**: 语音段结束后返回，准确度高，用于记录

---

## 4. Python 调用示例

### 4.1 基础客户端类

```python
import websocket
import json

class WhisperClient:
    """Skynet Whisper 客户端"""
    
    def __init__(self, server_url="ws://localhost:6010", meeting_id="default", 
                 participant_id="user", language="zh"):
        """
        初始化客户端
        
        Args:
            server_url: 服务器地址
            meeting_id: 会话ID
            participant_id: 参与者ID
            language: 语言码（zh, en, ja 等）
        """
        self.ws_url = f"{server_url}/streaming-whisper/ws/{meeting_id}"
        self.participant_id = participant_id
        self.language = language
        self.ws = None
    
    def create_header(self):
        """创建 60 字节头部"""
        header_str = f"{self.participant_id}|{self.language}"
        return header_str.ljust(60, ' ').encode('utf-8')[:60]
    
    def connect(self):
        """连接到服务"""
        self.ws = websocket.create_connection(self.ws_url)
        print(f"✓ 已连接到 {self.ws_url}")
    
    def send_audio(self, audio_data):
        """
        发送音频数据
        
        Args:
            audio_data: PCM 音频字节数据（16kHz 单声道 Int16）
        """
        header = self.create_header()
        payload = header + audio_data
        self.ws.send(payload, opcode=websocket.ABNF.OPCODE_BINARY)
    
    def receive_result(self):
        """
        接收转录结果
        
        Returns:
            dict: 包含 type, text, ts, variance 的字典
        """
        result_str = self.ws.recv()
        return json.loads(result_str)
    
    def send_audio_stream(self, audio_data, chunk_size=32000):
        """
        分块发送音频流
        
        Args:
            audio_data: 完整音频数据
            chunk_size: 每块大小（默认 32000 = 1秒）
        """
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            if len(chunk) > 0:
                self.send_audio(chunk)
                # 尝试接收结果
                try:
                    result = self.receive_result()
                    print(f"[{result['type']}] {result['text']}")
                except:
                    pass
    
    def close(self):
        """关闭连接"""
        if self.ws:
            self.ws.close()
            print("✓ 连接已关闭")
```

### 4.2 基本使用示例

```python
# 创建客户端
client = WhisperClient(
    server_url="ws://localhost:6010",
    meeting_id="session-001",
    participant_id="user123",
    language="zh"
)

try:
    # 连接服务
    client.connect()
    
    # 读取 PCM 音频文件
    with open('audio_16khz_mono.pcm', 'rb') as f:
        audio_data = f.read()
    
    # 发送并接收结果
    client.send_audio_stream(audio_data)
    
finally:
    client.close()
```

### 4.3 实时麦克风转录示例

```python
import pyaudio
import threading
import time

# 需要安装: pip install pyaudio

class RealtimeMicTranscriber:
    """实时麦克风转录"""
    
    def __init__(self, server_url="ws://localhost:6010", language="zh"):
        self.client = WhisperClient(
            server_url=server_url,
            meeting_id=f"mic-{int(time.time())}",
            participant_id="microphone",
            language=language
        )
        self.running = False
        
        # 音频参数
        self.RATE = 16000
        self.CHUNK = 16000  # 1秒
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
    
    def start(self):
        """开始录音并转录"""
        self.client.connect()
        self.running = True
        
        # 启动结果接收线程
        receiver_thread = threading.Thread(target=self._receive_results)
        receiver_thread.daemon = True
        receiver_thread.start()
        
        # 开始录音
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        print("🎤 开始录音转录... (Ctrl+C 停止)")
        
        try:
            while self.running:
                audio_data = stream.read(self.CHUNK, exception_on_overflow=False)
                self.client.send_audio(audio_data)
        except KeyboardInterrupt:
            print("\n停止录音")
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
            self.running = False
            self.client.close()
    
    def _receive_results(self):
        """接收转录结果（后台线程）"""
        while self.running:
            try:
                result = self.client.receive_result()
                print(f"\r[{result['type']}] {result['text']}", end='', flush=True)
                if result['type'] == 'final':
                    print()  # 换行
            except:
                break

# 使用
transcriber = RealtimeMicTranscriber(language="zh")
transcriber.start()
```

### 4.4 批量文件转录示例

```python
import os
import subprocess

def convert_wav_to_pcm(wav_path):
    """WAV 转 PCM（使用 ffmpeg）"""
    pcm_path = wav_path.replace('.wav', '.pcm')
    cmd = [
        'ffmpeg', '-i', wav_path,
        '-ar', '16000',      # 16kHz
        '-ac', '1',          # 单声道
        '-f', 's16le',       # Int16 PCM
        pcm_path,
        '-y'                 # 覆盖已存在文件
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return pcm_path

def transcribe_file(audio_file, language="zh"):
    """转录单个文件"""
    # 如果是 WAV，先转换
    if audio_file.endswith('.wav'):
        pcm_file = convert_wav_to_pcm(audio_file)
    else:
        pcm_file = audio_file
    
    # 创建客户端
    client = WhisperClient(
        meeting_id=f"file-{os.path.basename(pcm_file)}",
        language=language
    )
    
    try:
        client.connect()
        
        # 读取音频
        with open(pcm_file, 'rb') as f:
            audio_data = f.read()
        
        # 转录
        results = []
        for i in range(0, len(audio_data), 32000):
            chunk = audio_data[i:i+32000]
            if len(chunk) > 0:
                client.send_audio(chunk)
                try:
                    result = client.receive_result()
                    if result['type'] == 'final':
                        results.append(result['text'])
                except:
                    pass
        
        return ' '.join(results)
        
    finally:
        client.close()

# 使用示例
text = transcribe_file('audio.wav', language='zh')
print(f"转录结果: {text}")
```

### 4.5 带重连的健壮客户端

```python
import time

class RobustWhisperClient(WhisperClient):
    """带自动重连的客户端"""
    
    def __init__(self, *args, max_retries=3, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_retries = max_retries
    
    def connect_with_retry(self):
        """带重试的连接"""
        for attempt in range(self.max_retries):
            try:
                self.connect()
                return True
            except Exception as e:
                print(f"连接失败 ({attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
        return False
    
    def send_audio_safe(self, audio_data):
        """带错误处理的发送"""
        try:
            self.send_audio(audio_data)
            return True
        except Exception as e:
            print(f"发送失败: {e}")
            # 尝试重连
            if self.connect_with_retry():
                try:
                    self.send_audio(audio_data)
                    return True
                except:
                    pass
            return False
    
    def receive_result_safe(self, timeout=5):
        """带超时的接收"""
        try:
            self.ws.settimeout(timeout)
            return self.receive_result()
        except Exception as e:
            print(f"接收失败: {e}")
            return None

# 使用
client = RobustWhisperClient(language="zh")
if client.connect_with_retry():
    # 业务逻辑
    pass
```

---

## 5. 音频格式要求

### 5.1 必须遵守的规格

| 参数 | 要求值 | 说明 |
|------|--------|------|
| 采样率 | 16000 Hz | 必须严格遵守 |
| 声道数 | 1（单声道） | 不支持立体声 |
| 位深度 | 16 bit | Int16，范围：-32768 到 32767 |
| 编码 | PCM | 无压缩 |
| 字节序 | Little Endian | x86/x64 默认 |
| 文件头 | 无 | 纯音频数据，不含 WAV 头 |

### 5.2 使用 FFmpeg 转换音频

```bash
# WAV 转 PCM
ffmpeg -i input.wav -ar 16000 -ac 1 -f s16le output.pcm

# MP3 转 PCM
ffmpeg -i input.mp3 -ar 16000 -ac 1 -f s16le output.pcm

# 批量转换目录下所有 WAV 文件
for file in *.wav; do
    ffmpeg -i "$file" -ar 16000 -ac 1 -f s16le "${file%.wav}.pcm" -y
done
```

### 5.3 Python 转换示例

```python
import subprocess

def convert_to_pcm(input_file, output_file):
    """转换任意音频为 PCM 格式"""
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-ar', '16000',
        '-ac', '1',
        '-f', 's16le',
        output_file,
        '-y'
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"✓ 已转换: {input_file} -> {output_file}")

# 使用
convert_to_pcm('audio.wav', 'audio.pcm')
convert_to_pcm('audio.mp3', 'audio.pcm')
```

### 5.4 音频质量验证

```python
import numpy as np

def validate_pcm_audio(pcm_file):
    """验证 PCM 音频格式"""
    # 读取文件
    with open(pcm_file, 'rb') as f:
        pcm_data = f.read()
    
    # 检查字节数（必须为偶数）
    if len(pcm_data) % 2 != 0:
        print("✗ 错误: 数据长度必须为偶数（Int16）")
        return False
    
    # 转换为 numpy 数组
    audio = np.frombuffer(pcm_data, dtype=np.int16)
    
    # 计算时长
    duration = len(audio) / 16000
    print(f"✓ 音频时长: {duration:.2f} 秒")
    
    # 检查音量
    max_amp = np.abs(audio).max()
    print(f"✓ 最大振幅: {max_amp}")
    
    if max_amp < 100:
        print("⚠️  警告: 音量过低")
    elif max_amp > 30000:
        print("⚠️  警告: 可能削波（失真）")
    
    # 检查静音
    if max_amp < 10:
        print("✗ 错误: 音频为静音")
        return False
    
    return True

# 使用
validate_pcm_audio('audio.pcm')
```

### 5.5 音频块大小建议

| 块大小 | 字节数 | 适用场景 |
|--------|--------|---------|
| 0.5 秒 | 16000 | 低延迟（准确度略降） |
| 1.0 秒 | 32000 | **推荐**（最佳平衡） |
| 2.0 秒 | 64000 | 高准确度 |
| 3.0 秒 | 96000 | 长句识别 |

---

## 6. 常见问题

### 6.1 如何测试服务是否正常？

```python
import websocket

def test_service(server_url="ws://localhost:6010"):
    """测试 Whisper 服务是否可用"""
    try:
        ws = websocket.create_connection(
            f"{server_url}/streaming-whisper/ws/test",
            timeout=5
        )
        print("✓ 服务正常")
        ws.close()
        return True
    except Exception as e:
        print(f"✗ 服务异常: {e}")
        return False

test_service()
```

### 6.2 为什么识别结果是英文？

**可能原因**：
1. 语言码设置错误（发送了 `en` 而不是 `zh`）
2. 使用了仅英文模型（如 `tiny.en`）
3. 音频质量差

**解决方案**：
```python
# 确保语言码正确
header = "user123|zh".ljust(60, ' ').encode('utf-8')[:60]

# 第一句话用目标语言（如中文说"你好"）
```

### 6.3 如何提高识别准确度？

1. **音频质量**：
   - 清晰录音，降低背景噪音
   - 适当音量（不要过高或过低）
   - 使用 16kHz 采样率

2. **发送策略**：
   - 每次发送 1-2 秒音频
   - 避免过短的片段

3. **服务器配置**（如需要）：
   - 使用更大的模型（tiny → base → small）
   - 启用 GPU 加速

### 6.4 支持多参与者吗？

**支持！** 每个参与者使用不同的 `participant_id`：

```python
# 同一个 WebSocket 连接，不同参与者
ws = websocket.create_connection("ws://localhost:6010/streaming-whisper/ws/meeting-001")

# 参与者 A（说中文）
header_a = "user-A|zh".ljust(60, ' ').encode('utf-8')[:60]
ws.send(header_a + audio_a, opcode=websocket.ABNF.OPCODE_BINARY)

# 参与者 B（说英文）
header_b = "user-B|en".ljust(60, ' ').encode('utf-8')[:60]
ws.send(header_b + audio_b, opcode=websocket.ABNF.OPCODE_BINARY)

# 结果会分别返回
```

### 6.5 如何降低延迟？

1. **减少音频块大小**：从 1 秒减少到 0.5 秒
2. **优化网络**：本地调用（已是最优）
3. **服务器端优化**（需修改配置）：
   - 使用更小的模型（base → tiny）
   - 启用 GPU 加速
   - 减少 `BEAM_SIZE`

### 6.6 遇到错误怎么办？

```python
# 常见错误处理
try:
    client = WhisperClient()
    client.connect()
    # ... 业务逻辑
except ConnectionRefusedError:
    print("服务未启动，请检查: sudo systemctl status skynet")
except websocket.WebSocketTimeoutException:
    print("连接超时，请检查网络或服务器负载")
except Exception as e:
    print(f"未知错误: {e}")
    print("查看服务器日志: sudo journalctl -u skynet -f")
```

### 6.7 如何查看服务器日志？

```bash
# 实时查看 Skynet 日志
sudo journalctl -u skynet -f

# 查看最近 50 行
sudo journalctl -u skynet -n 50

# 只看错误
sudo journalctl -u skynet --priority=err -n 50
```

---

## 附录：完整示例脚本

```python
#!/usr/bin/env python3
"""
Skynet Whisper 转录完整示例
功能：读取音频文件并转录为文本
"""

import websocket
import json
import sys
import os

class WhisperClient:
    """Whisper 客户端"""
    
    def __init__(self, server_url="ws://localhost:6010", meeting_id="default", 
                 participant_id="user", language="zh"):
        self.ws_url = f"{server_url}/streaming-whisper/ws/{meeting_id}"
        self.participant_id = participant_id
        self.language = language
        self.ws = None
    
    def create_header(self):
        header_str = f"{self.participant_id}|{self.language}"
        return header_str.ljust(60, ' ').encode('utf-8')[:60]
    
    def connect(self):
        self.ws = websocket.create_connection(self.ws_url)
        print(f"✓ 已连接到服务")
    
    def send_audio(self, audio_data):
        header = self.create_header()
        payload = header + audio_data
        self.ws.send(payload, opcode=websocket.ABNF.OPCODE_BINARY)
    
    def receive_result(self):
        return json.loads(self.ws.recv())
    
    def transcribe_file(self, pcm_file):
        """转录 PCM 文件"""
        with open(pcm_file, 'rb') as f:
            audio_data = f.read()
        
        results = []
        chunk_size = 32000  # 1秒
        
        print(f"开始转录 {pcm_file}...")
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            if len(chunk) > 0:
                self.send_audio(chunk)
                try:
                    result = self.receive_result()
                    if result['type'] == 'final':
                        print(f"  {result['text']}")
                        results.append(result['text'])
                except:
                    pass
        
        return ' '.join(results)
    
    def close(self):
        if self.ws:
            self.ws.close()

def main():
    if len(sys.argv) < 2:
        print("用法: python script.py <audio.pcm> [语言码]")
        print("示例: python script.py audio.pcm zh")
        sys.exit(1)
    
    pcm_file = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "zh"
    
    if not os.path.exists(pcm_file):
        print(f"✗ 文件不存在: {pcm_file}")
        sys.exit(1)
    
    # 创建客户端
    client = WhisperClient(
        meeting_id=os.path.basename(pcm_file),
        language=language
    )
    
    try:
        client.connect()
        full_text = client.transcribe_file(pcm_file)
        print(f"\n完整转录结果:\n{full_text}")
    except Exception as e:
        print(f"✗ 错误: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    main()
```

**使用方法**：
```bash
# 安装依赖
pip install websocket-client

# 转录中文音频
python transcribe.py audio.pcm zh

# 转录英文音频
python transcribe.py audio.pcm en
```

---

