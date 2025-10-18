"""
Video processing utilities
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional
from pathlib import Path
import tempfile
from loguru import logger


class VideoProcessor:
    """Video processing utilities"""
    
    def __init__(self):
        # Try H.264 compatible codecs for browser playback
        # Priority: avc1 (H.264) > X264 > mp4v
        self.fourcc = None
        for codec in ['avc1', 'H264', 'X264', 'mp4v']:
            try:
                self.fourcc = cv2.VideoWriter_fourcc(*codec)
                break
            except:
                continue
        
        if self.fourcc is None:
            # Last resort
            self.fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        # Check if FFmpeg is available and supports H.264
        self.ffmpeg_available = self._check_ffmpeg_h264()
    
    def read_video(self, video_path: str) -> Tuple[List[np.ndarray], float]:
        """Read video and return frames and FPS"""
        frames = []
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        
        cap.release()
        
        logger.info(f"Read {len(frames)} frames from {video_path}")
        
        return frames, fps
    
    def write_video(self, frames: List[np.ndarray], output_path: str, fps: float = 25.0):
        """Write frames to video file"""
        if not frames:
            logger.warning("No frames to write")
            return
        
        height, width = frames[0].shape[:2]
        
        writer = cv2.VideoWriter(
            output_path,
            self.fourcc,
            fps,
            (width, height)
        )
        
        # Check if writer is opened successfully
        if not writer.isOpened():
            logger.error(f"Failed to open VideoWriter for {output_path}")
            logger.error(f"Trying alternative codec...")
            # Try with MJPEG codec as fallback
            writer = cv2.VideoWriter(
                output_path,
                cv2.VideoWriter_fourcc(*'MJPG'),
                fps,
                (width, height)
            )
            if not writer.isOpened():
                raise RuntimeError(f"Failed to initialize VideoWriter")
        
        for frame in frames:
            writer.write(frame)
        
        writer.release()
        
        logger.info(f"Wrote {len(frames)} frames to {output_path}")
    
    def resize_frame(self, frame: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
        """Resize frame to target size"""
        return cv2.resize(frame, size)
    
    def crop_center(self, frame: np.ndarray, crop_size: Tuple[int, int]) -> np.ndarray:
        """Crop center of frame"""
        h, w = frame.shape[:2]
        crop_h, crop_w = crop_size
        
        start_x = (w - crop_w) // 2
        start_y = (h - crop_h) // 2
        
        return frame[start_y:start_y + crop_h, start_x:start_x + crop_w]
    
    def pad_frame(self, frame: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
        """Pad frame to target size"""
        h, w = frame.shape[:2]
        target_h, target_w = target_size
        
        if h >= target_h and w >= target_w:
            return frame
        
        pad_h = max(0, target_h - h)
        pad_w = max(0, target_w - w)
        
        pad_top = pad_h // 2
        pad_bottom = pad_h - pad_top
        pad_left = pad_w // 2
        pad_right = pad_w - pad_left
        
        return cv2.copyMakeBorder(
            frame,
            pad_top, pad_bottom, pad_left, pad_right,
            cv2.BORDER_CONSTANT,
            value=(0, 0, 0)
        )
    
    def _check_ffmpeg_h264(self) -> bool:
        """Check if FFmpeg is available and supports H.264"""
        import subprocess
        try:
            # Check if ffmpeg is available
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.warning("FFmpeg not available")
                return False
            
            # Check if libx264 is available
            result = subprocess.run(
                ['ffmpeg', '-codecs'],
                capture_output=True,
                timeout=5
            )
            output = result.stdout.decode()
            has_h264 = 'libx264' in output or 'h264' in output.lower()
            
            if has_h264:
                logger.info("FFmpeg with H.264 support detected")
            else:
                logger.warning("FFmpeg found but H.264 (libx264) not available")
            
            return has_h264
            
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("FFmpeg not found in PATH")
            return False
        except Exception as e:
            logger.warning(f"FFmpeg check failed: {e}")
            return False
    
    def frames_to_video_bytes(self, frames: List[np.ndarray], fps: float = 25.0, use_ffmpeg: bool = True) -> bytes:
        """
        Convert frames to video bytes
        
        Args:
            frames: List of video frames
            fps: Frames per second
            use_ffmpeg: Use FFmpeg for better compression (recommended)
            
        Returns:
            Video bytes in MP4 format
        """
        if not frames:
            return b""
        
        # Automatically choose encoding method based on availability
        if use_ffmpeg and self.ffmpeg_available:
            return self._frames_to_mp4_ffmpeg(frames, fps)
        else:
            if use_ffmpeg and not self.ffmpeg_available:
                logger.warning("FFmpeg not available, using OpenCV encoding. Install FFmpeg with libx264 for better browser compatibility.")
            return self._frames_to_mp4_opencv(frames, fps)
    
    def _frames_to_mp4_opencv(self, frames: List[np.ndarray], fps: float) -> bytes:
        """Convert frames to MP4 using OpenCV"""
        import os
        
        # Use temporary file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            self.write_video(frames, tmp_path, fps)
            
            # Check if file exists and has content
            if not os.path.exists(tmp_path):
                logger.error(f"Temp video file not created: {tmp_path}")
                return b""
            
            file_size = os.path.getsize(tmp_path)
            logger.info(f"Temp video file size: {file_size} bytes")
            
            if file_size == 0:
                logger.error(f"Temp video file is empty: {tmp_path}")
                return b""
            
            # Read video bytes
            with open(tmp_path, 'rb') as f:
                video_bytes = f.read()
            
            logger.info(f"Read {len(video_bytes)} bytes from OpenCV video")
            return video_bytes
        finally:
            # Cleanup
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()
    
    def _frames_to_mp4_ffmpeg(self, frames: List[np.ndarray], fps: float) -> bytes:
        """Convert frames to MP4 using FFmpeg for better compression"""
        import subprocess
        
        if not frames:
            return b""
        
        height, width = frames[0].shape[:2]
        
        # FFmpeg command for H.264 encoding with optimized settings
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{width}x{height}',
            '-pix_fmt', 'bgr24',
            '-r', str(fps),
            '-i', '-',  # Input from stdin
            '-c:v', 'libx264',  # H.264 codec
            '-preset', 'ultrafast',  # Fast encoding for real-time
            '-tune', 'zerolatency',  # Low latency
            '-crf', '23',  # Quality (lower = better, 23 is good)
            '-pix_fmt', 'yuv420p',  # Compatible pixel format
            '-movflags', '+faststart',  # Enable streaming
            '-f', 'mp4',
            'pipe:1'  # Output to stdout
        ]
        
        try:
            # Start FFmpeg process
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            try:
                # Write frames to FFmpeg
                for frame in frames:
                    process.stdin.write(frame.tobytes())
                
                # Close stdin to signal end of input
                process.stdin.close()
            except BrokenPipeError:
                # FFmpeg crashed while writing
                logger.error("FFmpeg broken pipe during write, falling back to OpenCV")
                process.kill()
                return self._frames_to_mp4_opencv(frames, fps)
            
            # Get output
            video_bytes, stderr = process.communicate(timeout=30)
            
            if process.returncode != 0:
                stderr_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"FFmpeg encoding failed (returncode {process.returncode}): {stderr_msg}")
                # Fallback to OpenCV
                return self._frames_to_mp4_opencv(frames, fps)
            
            if len(video_bytes) == 0:
                logger.error("FFmpeg returned empty video, falling back to OpenCV")
                return self._frames_to_mp4_opencv(frames, fps)
            
            logger.info(f"Encoded {len(frames)} frames to {len(video_bytes)} bytes using FFmpeg")
            
            return video_bytes
            
        except FileNotFoundError:
            logger.warning("FFmpeg not found, falling back to OpenCV encoding")
            return self._frames_to_mp4_opencv(frames, fps)
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg encoding timeout, falling back to OpenCV")
            process.kill()
            return self._frames_to_mp4_opencv(frames, fps)
        except Exception as e:
            logger.error(f"FFmpeg encoding error: {e}, falling back to OpenCV")
            return self._frames_to_mp4_opencv(frames, fps)
    
    def extract_face_region(self, frame: np.ndarray, 
                          face_coords: Tuple[int, int, int, int],
                          padding: float = 0.2) -> np.ndarray:
        """Extract face region with padding"""
        x, y, w, h = face_coords
        
        # Add padding
        pad_w = int(w * padding)
        pad_h = int(h * padding)
        
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(frame.shape[1], x + w + pad_w)
        y2 = min(frame.shape[0], y + h + pad_h)
        
        return frame[y1:y2, x1:x2]
    
    def blend_frames(self, frame1: np.ndarray, frame2: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        """Blend two frames"""
        return cv2.addWeighted(frame1, alpha, frame2, 1 - alpha, 0)
    
    def apply_gaussian_blur(self, frame: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """Apply Gaussian blur to frame"""
        return cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)
    
    def detect_faces_dlib(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces using dlib (if available)"""
        # This is a placeholder - in production you'd use dlib or other face detectors
        # For now, return empty list
        return []
