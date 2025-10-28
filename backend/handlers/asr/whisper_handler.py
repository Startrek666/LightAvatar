"""
Faster-Whisper Handler for speech recognition
"""
import io
import numpy as np
from typing import Optional, List
from faster_whisper import WhisperModel
import soundfile as sf
from loguru import logger

from backend.handlers.base import BaseHandler
from backend.core.health_monitor import timer, asr_processing_time


class WhisperHandler(BaseHandler):
    """Speech recognition using Faster-Whisper (CPU optimized)"""
    
    def __init__(self, 
                 model_size: str = "small",
                 device: str = "cpu",
                 compute_type: str = "int8",
                 config: Optional[dict] = None):
        super().__init__(config)
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        
        # Recognition parameters
        self.language = self.config.get("language", "zh")
        self.beam_size = self.config.get("beam_size", 5)
        self.best_of = self.config.get("best_of", 5)
        self.temperature = self.config.get("temperature", 0)
        
    async def _setup(self):
        """Setup Whisper model"""
        try:
            # Initialize Faster-Whisper model
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.config.get("cpu_threads", 4),
                num_workers=self.config.get("num_workers", 1)
            )
            
            logger.info(f"Whisper model '{self.model_size}' loaded on {self.device} with {self.compute_type}")
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
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
            
            # 检查字节对齐：int16需要2字节对齐
            if len(audio_data) % 2 != 0:
                audio_data = audio_data[:-1]
            
            if len(audio_data) == 0:
                logger.warning(f"[ASR] 音频数据为空")
                return ""
            
            logger.info(f"[ASR] 开始识别，音频字节数: {len(audio_data)}")
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            audio_array = audio_array / 32768.0  # Normalize to [-1, 1]
            
            logger.info(f"[ASR] 音频数组长度: {len(audio_array)}, 时长: {len(audio_array) / 16000:.2f}秒")
            
            # 计算音频音量（RMS）
            rms = np.sqrt(np.mean(audio_array ** 2))
            logger.info(f"[ASR] 音频RMS音量: {rms:.4f}")
            
            # 降低VAD阈值，提高语音检测灵敏度
            segments, info = self.model.transcribe(
                audio_array,
                language=self.language,
                beam_size=self.beam_size,
                best_of=self.best_of,
                temperature=self.temperature,
                vad_filter=True,
                vad_parameters={
                    "threshold": 0.3,  # 降低阈值从0.5到0.3
                    "min_speech_duration_ms": 200,  # 降低最小语音时长
                    "min_silence_duration_ms": 500
                }
            )
            
            logger.info(f"[ASR] Whisper检测到的语言: {info.language}, 概率: {info.language_probability:.2f}")
            
            # Combine segments
            segment_list = list(segments)
            logger.info(f"[ASR] 检测到 {len(segment_list)} 个语音段")
            
            for i, segment in enumerate(segment_list):
                logger.info(f"[ASR] 段 {i+1}: [{segment.start:.2f}s - {segment.end:.2f}s] {segment.text}")
            
            text = " ".join([segment.text.strip() for segment in segment_list])
            
            if text:
                logger.info(f"[ASR] ✅ 识别成功: {text}")
            else:
                logger.warning(f"[ASR] ❌ 识别结果为空（音频有效但未检测到语音）")
            
            return text
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    async def transcribe(self, audio_data: bytes) -> str:
        """Public transcribe method"""
        if not self._initialized:
            await self.initialize()
        
        return await self.process(audio_data)
    
    async def transcribe_file(self, file_path: str) -> str:
        """Transcribe audio file"""
        try:
            # Read audio file
            audio_data, sample_rate = sf.read(file_path, dtype='int16')
            
            # Convert to bytes
            audio_bytes = audio_data.tobytes()
            
            return await self.transcribe(audio_bytes)
            
        except Exception as e:
            logger.error(f"Failed to transcribe file {file_path}: {e}")
            return ""
    
    def get_available_models(self) -> List[str]:
        """Get list of available Whisper models"""
        return ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return [
            "zh", "en", "ja", "ko", "es", "fr", "de", "it", "pt", "ru",
            "ar", "hi", "vi", "th", "id", "ms", "tr", "he", "pl", "nl"
        ]
