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
        """Convert audio to WAV format with comprehensive timeout protection"""
        input_path = None
        output_path = None
        process = None
        
        try:
            logger.info(f"🎵 开始音频转换: {len(audio_data)} bytes ({input_format} -> wav)")
            
            # Use temporary files for conversion
            with tempfile.NamedTemporaryFile(suffix=f".{input_format}", delete=False) as input_file:
                input_file.write(audio_data)
                input_path = input_file.name
            
            output_path = input_path.replace(f".{input_format}", ".wav")
            
            logger.debug(f"📁 临时文件: {input_path} -> {output_path}")
            
            # Use ffmpeg for conversion (ensure it's installed)
            # Use absolute path to ensure it's found in systemd service
            ffmpeg_path = "/usr/bin/ffmpeg"
            cmd = [
                ffmpeg_path, "-i", input_path,
                "-ar", str(self.sample_rate),
                "-ac", "1",  # Mono
                "-f", "wav",
                output_path,
                "-y",  # Overwrite
                "-loglevel", "error"  # 减少FFmpeg输出
            ]
            
            logger.info(f"🔧 启动FFmpeg进程...")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            logger.info(f"✅ FFmpeg进程已启动 (PID: {process.pid})")
            
            # ⚡ 关键修复：加上30秒超时，防止FFmpeg卡死
            try:
                logger.info(f"⏳ 等待FFmpeg完成 (超时30秒)...")
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=30.0
                )
                logger.info(f"✅ FFmpeg进程已完成 (返回码: {process.returncode})")
            except asyncio.TimeoutError:
                logger.error(f"❌ FFmpeg超时（30秒），强制终止进程 PID={process.pid}")
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                    logger.error(f"✅ 进程已终止")
                except Exception as kill_error:
                    logger.error(f"❌ 终止进程失败: {kill_error}")
                return b""
            
            if process.returncode != 0:
                stderr_str = stderr.decode() if stderr else "No error output"
                logger.error(f"❌ FFmpeg错误 (返回码 {process.returncode}): {stderr_str}")
                return b""
            
            # Check if output file exists
            logger.debug(f"📂 检查输出文件: {output_path}")
            if not Path(output_path).exists():
                logger.error(f"❌ 输出文件未创建: {output_path}")
                return b""
            
            output_size = Path(output_path).stat().st_size
            logger.debug(f"✅ 输出文件存在: {output_size} bytes")
            
            # Read converted file
            logger.debug(f"📖 读取转换后的文件...")
            with open(output_path, 'rb') as f:
                wav_data = f.read()
            
            logger.info(f"✅ 音频转换成功: {len(wav_data)} bytes")
            
            # Cleanup
            try:
                if input_path and Path(input_path).exists():
                    Path(input_path).unlink()
                if output_path and Path(output_path).exists():
                    Path(output_path).unlink()
                logger.debug(f"🗑️ 已清理临时文件")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ 清理临时文件失败: {cleanup_error}")
            
            return wav_data
            
        except FileNotFoundError as e:
            logger.error(f"❌ FFmpeg未找到或文件错误: {e}. 请安装: sudo apt install ffmpeg")
            return b""
        except asyncio.CancelledError:
            logger.error(f"❌ 音频转换任务被取消")
            if process and process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
            raise
        except Exception as e:
            logger.error(f"❌ 音频转换异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return b""
        finally:
            # Final cleanup - ensure no orphaned processes or files
            try:
                if process and process.returncode is None:
                    logger.warning(f"⚠️ FFmpeg进程仍在运行，强制终止")
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=2.0)
            except:
                pass
            
            # Cleanup temp files
            try:
                if input_path and Path(input_path).exists():
                    Path(input_path).unlink()
                if output_path and Path(output_path).exists():
                    Path(output_path).unlink()
            except:
                pass
    
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
