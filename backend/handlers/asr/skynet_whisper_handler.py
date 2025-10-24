"""
Skynet Whisper API Handler for speech recognition
"""
import asyncio
import json
import uuid
from typing import Optional

import numpy as np
from websocket import ABNF, create_connection
from loguru import logger

from backend.handlers.base import BaseHandler
from backend.core.health_monitor import timer, asr_processing_time


class SkynetWhisperHandler(BaseHandler):
    """Speech recognition using Skynet Whisper API (WebSocket)"""
    
    def __init__(self, 
                 server_url: str = "ws://localhost:6010",
                 participant_id: str = "avatar-user",
                 language: str = "zh",
                 config: Optional[dict] = None):
        super().__init__(config)
        self.server_url = server_url
        self.participant_id = participant_id
        self.language = language
        self.ws = None
        self.meeting_id = None
        
        # 音频参数
        self.sample_rate = 16000
        self.chunk_size = 32000  # 1秒音频
        
    async def _setup(self):
        """Setup Skynet Whisper connection"""
        try:
            # 生成会话 ID
            self.meeting_id = f"avatar-session-{uuid.uuid4().hex[:8]}"
            
            # 构建 WebSocket URL
            ws_url = f"{self.server_url}/streaming-whisper/ws/{self.meeting_id}"
            
            # 连接到 Whisper 服务（使用同步库，但在 executor 中运行）
            loop = asyncio.get_event_loop()
            self.ws = await loop.run_in_executor(
                None,
                lambda: create_connection(ws_url, timeout=10)
            )
            
            logger.info(f"Skynet Whisper connected: {ws_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Skynet Whisper: {e}")
            raise
    
    def _create_header(self) -> bytes:
        """创建 60 字节头部"""
        header_str = f"{self.participant_id}|{self.language}"
        return header_str.ljust(60, ' ').encode('utf-8')[:60]
    
    async def process(self, audio_data: bytes) -> str:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Transcribed text
        """
        with timer(asr_processing_time):
            return await self._transcribe(audio_data)
    
    async def _transcribe(self, audio_data) -> str:
        """Perform speech recognition"""
        try:
            # 兼容列表和字节对象两种格式
            if isinstance(audio_data, list):
                # 前端发送的是数组，转换为字节对象
                audio_data = bytes(audio_data)
            elif not isinstance(audio_data, bytes):
                logger.error(f"Unsupported audio data type: {type(audio_data)}")
                return ""
            
            # 转换音频为 PCM Int16
            pcm_data = await self._convert_to_pcm(audio_data)
            
            # 发送音频并接收结果
            text = await self._send_and_receive(pcm_data)
            
            if text:
                logger.info(f"Transcribed: {text}")
            
            return text
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    async def _convert_to_pcm(self, audio_data) -> bytes:
        """转换音频为 PCM 格式"""
        try:
            # 确保是字节对象
            if isinstance(audio_data, list):
                audio_data = bytes(audio_data)
            
            # 检查字节对齐：int16需要2字节对齐
            if len(audio_data) % 2 != 0:
                audio_data = audio_data[:-1]
            
            if len(audio_data) == 0:
                return b''
            
            # 将字节数据转换为 numpy 数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # 如果已经是 16kHz Int16，直接返回
            # 否则需要转换（这里假设输入已经是正确格式）
            return audio_array.tobytes()
            
        except Exception as e:
            logger.error(f"PCM conversion error: {e}")
            return audio_data
    
    async def _send_and_receive(self, pcm_data: bytes) -> str:
        """发送音频并接收识别结果"""
        try:
            loop = asyncio.get_event_loop()
            
            logger.info(f"[ASR] 开始发送音频数据，总大小: {len(pcm_data)} 字节")
            logger.info(f"[ASR] 分块大小: {self.chunk_size} 字节")
            
            # 分块发送音频
            results = []
            chunk_count = (len(pcm_data) + self.chunk_size - 1) // self.chunk_size
            logger.info(f"[ASR] 将分 {chunk_count} 个块发送")
            
            for i in range(0, len(pcm_data), self.chunk_size):
                chunk = pcm_data[i:i + self.chunk_size]
                chunk_index = i // self.chunk_size + 1
                
                if len(chunk) > 0:
                    # 创建头部
                    header = self._create_header()
                    payload = header + chunk
                    
                    logger.debug(f"[ASR] 发送第 {chunk_index}/{chunk_count} 块: {len(chunk)} 字节 (含头部: {len(payload)} 字节)")
                    
                    # 发送音频数据（二进制）
                    await loop.run_in_executor(
                        None,
                        lambda p=payload: self.ws.send(p, opcode=ABNF.OPCODE_BINARY)
                    )
                    
                    # 接收识别结果
                    try:
                        result_str = await asyncio.wait_for(
                            loop.run_in_executor(None, self.ws.recv),
                            timeout=5.0
                        )
                        
                        logger.debug(f"[ASR] 收到响应: {result_str[:200]}")
                        result = json.loads(result_str)
                        
                        # 记录所有类型的响应
                        result_type = result.get('type', 'unknown')
                        logger.debug(f"[ASR] 响应类型: {result_type}")
                        
                        # 只收集 final 结果
                        if result_type == 'final':
                            text = result.get('text', '').strip()
                            if text:
                                results.append(text)
                                logger.info(f"[ASR] 获得最终结果: {text}")
                            else:
                                logger.warning(f"[ASR] 收到 final 类型但文本为空")
                        elif result_type == 'partial':
                            logger.debug(f"[ASR] 部分结果: {result.get('text', '')}")
                        
                    except asyncio.TimeoutError:
                        logger.warning(f"[ASR] 第 {chunk_index}/{chunk_count} 块接收超时")
                    except json.JSONDecodeError as e:
                        logger.error(f"[ASR] JSON 解析失败: {e}, 原始数据: {result_str[:200]}")
                    except Exception as e:
                        logger.warning(f"[ASR] 接收错误: {e}")
            
            # 合并所有结果
            final_text = ' '.join(results)
            logger.info(f"[ASR] 识别完成，共 {len(results)} 个结果，总文本: '{final_text}'")
            return final_text
            
        except Exception as e:
            logger.error(f"[ASR] Send/receive error: {e}", exc_info=True)
            return ""
    
    async def transcribe(self, audio_data: bytes) -> str:
        """Public transcribe method"""
        if not self._initialized:
            await self.initialize()
        
        # 检查连接
        if not self.ws or not self.ws.connected:
            logger.warning("WebSocket disconnected, reconnecting...")
            await self._setup()
        
        return await self.process(audio_data)
    
    async def cleanup(self):
        """Clean up resources"""
        if self.ws:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.ws.close)
                logger.info("Skynet Whisper connection closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        self._initialized = False
    
    def __del__(self):
        """Destructor to ensure WebSocket is closed"""
        if self.ws and self.ws.connected:
            try:
                self.ws.close()
            except:
                pass

