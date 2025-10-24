#!/usr/bin/env python3
"""
测试语音识别功能
用法: python test_asr.py /path/to/audio.wav
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from backend.handlers.asr.skynet_whisper_handler import SkynetWhisperHandler
from backend.app.config import settings
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="DEBUG")


async def test_asr(audio_file_path: str):
    """测试ASR识别"""
    print(f"=" * 60)
    print(f"测试语音识别")
    print(f"=" * 60)
    print(f"音频文件: {audio_file_path}")
    
    # 检查文件是否存在
    if not os.path.exists(audio_file_path):
        print(f"❌ 错误: 文件不存在: {audio_file_path}")
        return
    
    # 获取文件大小
    file_size = os.path.getsize(audio_file_path)
    print(f"文件大小: {file_size} 字节 ({file_size / 1024:.2f} KB)")
    
    # 读取音频文件
    print(f"\n📂 读取音频文件...")
    with open(audio_file_path, 'rb') as f:
        audio_data = f.read()
    print(f"✅ 读取完成: {len(audio_data)} 字节")
    
    # 初始化ASR Handler
    print(f"\n🔧 初始化 Skynet Whisper Handler...")
    print(f"  - WebSocket URL: {settings.SKYNET_WHISPER_WS_URL}")
    
    asr_handler = SkynetWhisperHandler()
    
    try:
        # 初始化
        print(f"\n🚀 连接到 Skynet Whisper 服务...")
        await asr_handler.initialize()
        print(f"✅ 连接成功")
        
        # 执行识别
        print(f"\n🎤 开始语音识别...")
        print(f"  - 音频数据大小: {len(audio_data)} 字节")
        
        result = await asr_handler.transcribe(audio_data)
        
        print(f"\n" + "=" * 60)
        print(f"识别结果:")
        print(f"=" * 60)
        if result:
            print(f"✅ 识别成功: {result}")
            print(f"  - 文本长度: {len(result)} 字符")
        else:
            print(f"⚠️ 识别结果为空")
            print(f"\n可能的原因:")
            print(f"  1. 音频文件格式不正确（需要 WAV 格式）")
            print(f"  2. 音频文件没有语音内容")
            print(f"  3. Skynet Whisper 服务未正常运行")
            print(f"  4. 音频采样率不匹配（需要 16000 Hz）")
        print(f"=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理
        print(f"\n🧹 清理资源...")
        await asr_handler.cleanup()
        print(f"✅ 清理完成")


async def check_audio_format(audio_file_path: str):
    """检查音频格式"""
    try:
        import wave
        print(f"\n🔍 检查音频格式...")
        with wave.open(audio_file_path, 'rb') as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / framerate
            
            print(f"  - 声道数: {channels}")
            print(f"  - 采样宽度: {sample_width} 字节")
            print(f"  - 采样率: {framerate} Hz")
            print(f"  - 帧数: {n_frames}")
            print(f"  - 时长: {duration:.2f} 秒")
            
            # 检查是否符合要求
            issues = []
            if channels != 1:
                issues.append(f"声道数应为1（单声道），当前为{channels}")
            if framerate != 16000:
                issues.append(f"采样率应为16000 Hz，当前为{framerate} Hz")
            if sample_width != 2:
                issues.append(f"采样宽度应为2字节（16-bit），当前为{sample_width}字节")
            
            if issues:
                print(f"\n⚠️ 音频格式问题:")
                for issue in issues:
                    print(f"  - {issue}")
                print(f"\n建议使用 ffmpeg 转换:")
                print(f"  ffmpeg -i {audio_file_path} -ar 16000 -ac 1 -sample_fmt s16 output.wav")
            else:
                print(f"✅ 音频格式正确")
                
    except Exception as e:
        print(f"⚠️ 无法检查音频格式: {e}")


def main():
    if len(sys.argv) < 2:
        print("用法: python test_asr.py <音频文件路径>")
        print("示例: python test_asr.py /home/ftg/熊二_fixed.wav")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    # 检查音频格式
    asyncio.run(check_audio_format(audio_file))
    
    # 测试ASR
    asyncio.run(test_asr(audio_file))


if __name__ == "__main__":
    main()
