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
import psutil  # 添加psutil来监控和管理进程

# ✅ 全局信号量：限制并发FFmpeg进程数
# 16核心服务器，设置为14（峰值容量，留2个核心给系统）
_ffmpeg_semaphore = asyncio.Semaphore(14)

class AudioProcessor:
    """Audio processing utilities"""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
    
    async def convert_to_wav(self, audio_data: bytes, input_format: str = "mp3") -> bytes:
        """Convert audio to WAV format with comprehensive timeout protection"""
        # ✅ 使用信号量限制并发FFmpeg进程数
        async with _ffmpeg_semaphore:
            input_path = None
            output_path = None
            process = None
            
            try:
                logger.info(f"🎵 开始音频转换: {len(audio_data)} bytes ({input_format} -> wav)")
                
                # ✅ 检查系统资源
                cpu = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory().percent
                logger.info(f"📊 系统资源 - CPU: {cpu}%, 内存: {mem}%")
                
                if cpu > 95:
                    logger.error(f"⚠️ CPU使用率过高 ({cpu}%)，拒绝启动FFmpeg")
                    return b""
                if mem > 95:
                    logger.error(f"⚠️ 内存使用率过高 ({mem}%)，拒绝启动FFmpeg")
                    return b""
                
                # 检查FFmpeg进程数（正常≤14，超过16说明有问题）
                ffmpeg_count = sum(1 for proc in psutil.process_iter(['name']) 
                                 if proc.info.get('name') and 'ffmpeg' in proc.info['name'].lower())
                if ffmpeg_count > 15:
                    logger.error(f"⚠️ FFmpeg进程数过多 ({ffmpeg_count})，拒绝启动新进程")
                    return b""
                
                if ffmpeg_count > 0:
                    logger.debug(f"当前FFmpeg进程数: {ffmpeg_count}")
                
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
                # ✅ 关键修复：使用DEVNULL而不是PIPE，避免管道阻塞
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                logger.info(f"✅ FFmpeg进程已启动 (PID: {process.pid})")
                
                # ⚡ 关键修复：使用process.wait()而不是communicate()，并加上超时
                try:
                    logger.info(f"⏳ 等待FFmpeg完成 (超时20秒)...")
                    await asyncio.wait_for(
                        process.wait(), 
                        timeout=20.0
                    )
                    logger.info(f"✅ FFmpeg进程已完成 (返回码: {process.returncode})")
                except asyncio.TimeoutError:
                    logger.error(f"❌ FFmpeg超时（20秒），强制终止进程 PID={process.pid}")
                    try:
                        # ✅ 先用 kill() 杀死进程
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=3.0)
                        logger.info(f"✅ 进程已终止")
                    except asyncio.TimeoutError:
                        # ✅ 如果还不行，用psutil强制终止
                        logger.error(f"⚠️ 进程拒绝终止，使用psutil强制kill")
                        try:
                            proc = psutil.Process(process.pid)
                            proc.kill()
                            proc.wait(timeout=3)
                            logger.info(f"✅ 进程已被psutil终止")
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            logger.error(f"❌ 进程无法终止或已不存在")
                    except Exception as kill_error:
                        logger.error(f"❌ 终止进程失败: {kill_error}")
                    return b""
            
                if process.returncode != 0:
                    logger.error(f"❌ FFmpeg错误 (返回码 {process.returncode})")
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
                # ✅ 最终清理：确保进程被终止
                try:
                    if process and process.returncode is None:
                        logger.warning(f"⚠️ FFmpeg进程仍在运行，使用psutil强制终止")
                        try:
                            proc = psutil.Process(process.pid)
                            proc.kill()
                            proc.wait(timeout=2)
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            pass
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
