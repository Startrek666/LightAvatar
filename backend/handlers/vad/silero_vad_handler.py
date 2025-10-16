"""
Silero VAD Handler for voice activity detection
"""
import torch
import numpy as np
from typing import Tuple, Optional
from loguru import logger

from backend.handlers.base import BaseHandler
from backend.core.health_monitor import timer, vad_processing_time


class SileroVADHandler(BaseHandler):
    """Voice Activity Detection using Silero VAD"""
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.model = None
        self.utils = None
        
        # VAD parameters
        self.threshold = self.config.get("threshold", 0.5)
        self.sampling_rate = self.config.get("sampling_rate", 16000)
        self.min_speech_duration = self.config.get("min_speech_duration", 0.25)
        self.min_silence_duration = self.config.get("min_silence_duration", 0.5)
        
        # State
        self.speech_buffer = []
        self.is_speaking = False
        self.silence_frames = 0
        
    async def _setup(self):
        """Setup Silero VAD model"""
        try:
            # Load Silero VAD
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            
            # Get utility functions
            self.get_speech_timestamps = self.utils[0]
            
            logger.info("Silero VAD model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            raise
    
    async def process(self, audio_data: bytes) -> Tuple[bool, Optional[bytes]]:
        """
        Process audio data for voice activity detection
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Tuple of (is_speech_detected, speech_audio_bytes)
        """
        with timer(vad_processing_time):
            return await self._detect_speech(audio_data)
    
    async def _detect_speech(self, audio_data: bytes) -> Tuple[bool, Optional[bytes]]:
        """Detect speech in audio data"""
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            audio_array = audio_array / 32768.0  # Normalize to [-1, 1]
            
            # Convert to tensor
            audio_tensor = torch.from_numpy(audio_array)
            
            # Get speech probability
            speech_prob = self.model(audio_tensor, self.sampling_rate).item()
            
            # Detect speech
            is_speech = speech_prob > self.threshold
            
            # State machine for speech detection
            if is_speech:
                self.speech_buffer.append(audio_data)
                self.silence_frames = 0
                
                if not self.is_speaking:
                    # Check if we have enough speech to start
                    speech_duration = len(self.speech_buffer) * len(audio_data) / (self.sampling_rate * 2)
                    if speech_duration >= self.min_speech_duration:
                        self.is_speaking = True
                        logger.debug("Speech started")
                        
            else:
                if self.is_speaking:
                    self.silence_frames += 1
                    silence_duration = self.silence_frames * len(audio_data) / (self.sampling_rate * 2)
                    
                    if silence_duration >= self.min_silence_duration:
                        # Speech ended, return the complete utterance
                        self.is_speaking = False
                        complete_speech = b''.join(self.speech_buffer)
                        self.speech_buffer.clear()
                        self.silence_frames = 0
                        logger.debug("Speech ended")
                        return False, complete_speech
                    else:
                        # Still in speech, add silence to buffer
                        self.speech_buffer.append(audio_data)
                        
            return is_speech, None
            
        except Exception as e:
            logger.error(f"VAD processing error: {e}")
            return False, None
    
    async def detect(self, audio_data: bytes) -> bool:
        """Simple detection without returning audio"""
        is_speech, _ = await self.process(audio_data)
        return is_speech
    
    def reset(self):
        """Reset VAD state"""
        self.speech_buffer.clear()
        self.is_speaking = False
        self.silence_frames = 0
        logger.debug("VAD state reset")
