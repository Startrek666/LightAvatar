"""
Edge TTS Handler for text-to-speech synthesis
"""
import io
import asyncio
from typing import Optional, List
import edge_tts
from loguru import logger

from backend.handlers.base import BaseHandler
from backend.core.health_monitor import timer, tts_processing_time


class EdgeTTSHandler(BaseHandler):
    """Text-to-Speech using Microsoft Edge TTS (free service)"""
    
    def __init__(self,
                 voice: str = "zh-CN-XiaoxiaoNeural",
                 rate: str = "+0%",
                 pitch: str = "+0Hz",
                 config: Optional[dict] = None):
        super().__init__(config)
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        
        # Additional parameters
        self.volume = self.config.get("volume", "+0%")
        
    async def _setup(self):
        """Setup Edge TTS"""
        try:
            # Edge TTS doesn't require initialization
            # Just verify we can list voices
            voices = await edge_tts.list_voices()
            available_voices = [v["ShortName"] for v in voices]
            
            if self.voice not in available_voices:
                logger.warning(f"Voice '{self.voice}' not found, using default")
                self.voice = "zh-CN-XiaoxiaoNeural"
            
            logger.info(f"Edge TTS initialized with voice: {self.voice}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Edge TTS: {e}")
            raise
    
    async def process(self, text: str) -> bytes:
        """
        Synthesize text to speech
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio data as bytes (MP3 format)
        """
        with timer(tts_processing_time):
            return await self._synthesize(text)
    
    async def _synthesize(self, text: str, max_retries: int = 3) -> bytes:
        """Perform text-to-speech synthesis with retry logic"""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                # Create TTS communication
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=self.voice,
                    rate=self.rate,
                    pitch=self.pitch,
                    volume=self.volume
                )
                
                # Synthesize to bytes
                audio_data = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]
                
                logger.info(f"Synthesized {len(text)} characters to {len(audio_data)} bytes")
                
                return audio_data
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2秒, 4秒, 6秒
                    logger.warning(f"TTS synthesis failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"TTS synthesis error after {max_retries} attempts: {e}")
                    return b""
    
    async def synthesize(self, text: str) -> bytes:
        """Public synthesize method"""
        if not self._initialized:
            await self.initialize()
        
        return await self.process(text)
    
    async def synthesize_to_file(self, text: str, output_path: str):
        """Synthesize text and save to file"""
        try:
            # Create TTS communication
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch,
                volume=self.volume
            )
            
            # Save to file
            await communicate.save(output_path)
            
            logger.info(f"Synthesized audio saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save TTS to file: {e}")
            raise
    
    async def get_available_voices(self, language: Optional[str] = None) -> List[dict]:
        """Get list of available voices"""
        try:
            voices = await edge_tts.list_voices()
            
            if language:
                # Filter by language
                voices = [v for v in voices if v["Locale"].startswith(language)]
            
            return [
                {
                    "name": v["ShortName"],
                    "display_name": v["FriendlyName"],
                    "language": v["Locale"],
                    "gender": v["Gender"]
                }
                for v in voices
            ]
            
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
            return []
    
    def update_config(self, config: dict):
        """Update TTS configuration"""
        super().update_config(config)
        
        # Update voice parameters
        if "voice" in config:
            self.voice = config["voice"]
        if "rate" in config:
            self.rate = config["rate"]
        if "pitch" in config:
            self.pitch = config["pitch"]
        if "volume" in config:
            self.volume = config["volume"]
    
    @staticmethod
    def format_rate(speed_percent: int) -> str:
        """Format speed percentage for Edge TTS"""
        if speed_percent >= 0:
            return f"+{speed_percent}%"
        else:
            return f"{speed_percent}%"
    
    @staticmethod
    def format_pitch(pitch_hz: int) -> str:
        """Format pitch in Hz for Edge TTS"""
        if pitch_hz >= 0:
            return f"+{pitch_hz}Hz"
        else:
            return f"{pitch_hz}Hz"
