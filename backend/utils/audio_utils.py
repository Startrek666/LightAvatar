"""
Audio processing utilities
"""
import asyncio
import numpy as np
import soundfile as sf
import librosa
import io
from typing import Tuple, Optional
from loguru import logger
import subprocess
import tempfile
from pathlib import Path


class AudioProcessor:
    """Audio processing utilities"""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
    
    async def convert_to_wav(self, audio_data: bytes, input_format: str = "mp3") -> bytes:
        """Convert audio to WAV format"""
        try:
            # Use temporary files for conversion
            with tempfile.NamedTemporaryFile(suffix=f".{input_format}", delete=False) as input_file:
                input_file.write(audio_data)
                input_path = input_file.name
            
            output_path = input_path.replace(f".{input_format}", ".wav")
            
            # Use ffmpeg for conversion (ensure it's installed)
            cmd = [
                "ffmpeg", "-i", input_path,
                "-ar", str(self.sample_rate),
                "-ac", "1",  # Mono
                "-f", "wav",
                output_path,
                "-y"  # Overwrite
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            # Read converted file
            with open(output_path, 'rb') as f:
                wav_data = f.read()
            
            # Cleanup
            Path(input_path).unlink()
            Path(output_path).unlink()
            
            return wav_data
            
        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return b""
    
    def load_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """Load audio file"""
        try:
            audio, sr = librosa.load(audio_path, sr=self.sample_rate)
            return audio, sr
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            return np.array([]), 0
    
    def save_audio(self, audio: np.ndarray, output_path: str, sample_rate: Optional[int] = None):
        """Save audio to file"""
        try:
            sr = sample_rate or self.sample_rate
            sf.write(output_path, audio, sr)
            logger.info(f"Audio saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
    
    def normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1]"""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            return audio / max_val
        return audio
    
    def resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate"""
        if orig_sr == target_sr:
            return audio
        
        return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
    
    def extract_mel_spectrogram(self, audio: np.ndarray, 
                               n_fft: int = 2048,
                               hop_length: int = 512,
                               n_mels: int = 80) -> np.ndarray:
        """Extract mel spectrogram from audio"""
        try:
            # Compute mel spectrogram
            mel = librosa.feature.melspectrogram(
                y=audio,
                sr=self.sample_rate,
                n_fft=n_fft,
                hop_length=hop_length,
                n_mels=n_mels
            )
            
            # Convert to log scale
            mel_db = librosa.power_to_db(mel, ref=np.max)
            
            return mel_db
            
        except Exception as e:
            logger.error(f"Mel extraction error: {e}")
            return np.array([])
    
    def chunk_audio(self, audio: np.ndarray, chunk_size: int) -> list:
        """Split audio into chunks"""
        chunks = []
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i + chunk_size]
            
            # Pad last chunk if needed
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            
            chunks.append(chunk)
        
        return chunks
