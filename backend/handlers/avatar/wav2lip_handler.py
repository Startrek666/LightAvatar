"""
Wav2Lip Handler for CPU-optimized avatar generation
"""
import cv2
import numpy as np
import onnxruntime as ort
import torch
from typing import List, Tuple, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from loguru import logger
import subprocess
import json
import sys

from backend.handlers.base import BaseHandler
from backend.core.health_monitor import timer, avatar_processing_time
from backend.utils.video_utils import VideoProcessor
from backend.utils.audio_utils import AudioProcessor


class Wav2LipHandler(BaseHandler):
    """Avatar generation using Wav2Lip with ONNX optimization for CPU"""
    
    def __init__(self,
                 fps: int = 25,
                 resolution: Tuple[int, int] = (512, 512),
                 config: Optional[dict] = None):
        super().__init__(config)
        self.fps = fps
        self.resolution = resolution
        
        # Models
        self.wav2lip_session = None  # ONNX session
        self.wav2lip_model = None     # PyTorch model
        self.face_detector = None
        self.use_onnx = self.config.get("use_onnx", False)
        
        # Processing
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.video_processor = VideoProcessor()
        self.audio_processor = AudioProcessor()
        
        # Parameters
        self.static_mode = self.config.get("static_mode", False)
        self.enhance_mode = self.config.get("enhance_mode", False)
        self.mel_step_size = 16
        self.img_size = 96
        
        # Cache for template face detection
        self.template_face_cache = {}
        
    async def _setup(self):
        """Setup Wav2Lip models"""
        try:
            if self.use_onnx:
                # Initialize ONNX Runtime session for Wav2Lip
                model_path = Path("models") / "wav2lip" / "wav2lip.onnx"
                if not model_path.exists():
                    # Fallback to old path
                    model_path = Path("models") / "wav2lip_cpu.onnx"
                
                if not model_path.exists():
                    raise FileNotFoundError(
                        f"Wav2Lip ONNX model not found. Please run: python scripts/convert_wav2lip_to_onnx.py"
                    )
                
                # Set ONNX Runtime options for CPU optimization
                sess_options = ort.SessionOptions()
                sess_options.intra_op_num_threads = self.config.get("cpu_threads", 4)
                sess_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                
                # Create inference session
                self.wav2lip_session = ort.InferenceSession(
                    str(model_path),
                    sess_options,
                    providers=['CPUExecutionProvider']
                )
                logger.info(f"Wav2Lip ONNX model loaded from {model_path}")
            else:
                # Load PyTorch model
                model_path = Path("models") / "wav2lip" / "wav2lip.pth"
                if not model_path.exists():
                    raise FileNotFoundError(
                        f"Wav2Lip PyTorch model not found at {model_path}. "
                        f"Please download it using scripts/download_models.sh"
                    )
                
                # Import Wav2Lip model definition
                try:
                    # Try to import from official repo if available
                    project_root = Path(__file__).resolve().parents[3]
                    tools_path = project_root / 'tools' / 'Wav2Lip'
                    if tools_path.exists():
                        sys.path.insert(0, str(tools_path))
                        from models import Wav2Lip
                        logger.info("Using official Wav2Lip model definition")
                    else:
                        raise ImportError("Official Wav2Lip not found")
                except ImportError:
                    # Fallback: use simplified model (may not match checkpoint)
                    logger.warning("Official Wav2Lip not found, avatar generation may fail")
                    logger.warning("Run: git clone https://github.com/Rudrabha/Wav2Lip.git tools/Wav2Lip")
                    raise FileNotFoundError(
                        "Please clone official Wav2Lip repo: git clone https://github.com/Rudrabha/Wav2Lip.git tools/Wav2Lip"
                    )
                
                # Load model
                self.wav2lip_model = Wav2Lip()
                checkpoint = torch.load(model_path, map_location='cpu')
                
                # Handle state_dict
                if 'state_dict' in checkpoint:
                    state_dict = checkpoint['state_dict']
                else:
                    state_dict = checkpoint
                
                # Remove 'module.' prefix if present (DataParallel)
                new_state_dict = {}
                for key, value in state_dict.items():
                    if key.startswith('module.'):
                        new_state_dict[key[7:]] = value
                    else:
                        new_state_dict[key] = value
                
                self.wav2lip_model.load_state_dict(new_state_dict)
                self.wav2lip_model.eval()
                logger.info(f"Wav2Lip PyTorch model loaded from {model_path}")
            
            # Initialize face detector (MediaPipe)
            import mediapipe as mp
            self.face_detector = mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.5
            )
            
            logger.info(f"Wav2Lip models loaded successfully (ONNX: {self.use_onnx})")
            
        except Exception as e:
            logger.error(f"Failed to load Wav2Lip models: {e}")
            raise
    
    async def process(self, audio_data: bytes, template_path: str) -> bytes:
        """
        Generate avatar video from audio
        
        Args:
            audio_data: Audio bytes (MP3 format from TTS)
            template_path: Path to avatar template video/image
            
        Returns:
            Video bytes in MP4 format with audio
        """
        with timer(avatar_processing_time):
            frames = await self._generate_avatar(audio_data, template_path)
            
            # Encode frames to MP4
            if frames:
                video_bytes = self.video_processor.frames_to_video_bytes(frames, self.fps)
                logger.info(f"Generated video: {len(video_bytes)} bytes")
                
                # Add audio track to video
                video_with_audio = await self._add_audio_to_video(video_bytes, audio_data)
                if video_with_audio:
                    logger.info(f"Added audio track: {len(video_with_audio)} bytes")
                    return video_with_audio
                else:
                    logger.warning("Failed to add audio, returning video without audio")
                    return video_bytes
            else:
                logger.warning("No frames generated")
                return b""
    
    async def _generate_avatar(self, audio_data: bytes, template_path: str) -> List[np.ndarray]:
        """Generate avatar video frames"""
        try:
            # Convert audio to WAV format
            wav_audio = await self.audio_processor.convert_to_wav(audio_data)
            
            # Extract mel spectrogram
            mel_chunks = await self._extract_mel_chunks(wav_audio)
            
            # Calculate required frames based on audio duration
            # Each mel chunk represents mel_step_size frames at mel hop_length
            # hop_length=512, sr=16000 → each mel frame = 32ms
            # mel_step_size=16 → each chunk = 512ms
            # At 25fps, 512ms = 12.8 frames ≈ 13 frames per chunk
            frames_per_chunk = int(self.fps * 0.512)  # ~13 frames for 512ms
            if frames_per_chunk < 1:
                frames_per_chunk = 1
            
            total_required_frames = len(mel_chunks) * frames_per_chunk
            logger.info(f"Audio has {len(mel_chunks)} mel chunks, will generate {total_required_frames} frames ({frames_per_chunk} frames per chunk)")
            
            # Load template video/image
            logger.info(f"Loading template: {template_path}")
            if template_path.endswith(('.mp4', '.avi', '.mov')):
                template_frames = await self._load_video_template(template_path)
            else:
                template_frames = await self._load_image_template(template_path)
            
            if not template_frames:
                raise ValueError(f"No frames loaded from template: {template_path}")
            
            logger.info(f"Loaded {len(template_frames)} template frames")
            
            # Pre-detect face in first template frame (cache for efficiency)
            template_key = f"{template_path}_{len(template_frames)}"
            if template_key not in self.template_face_cache:
                first_frame = template_frames[0]
                face_coords = self._detect_face(first_frame)
                if face_coords is None:
                    logger.warning(f"No face detected in template {template_path}, using full frame")
                    # Use center crop as fallback
                    h, w = first_frame.shape[:2]
                    face_size = min(h, w) * 3 // 4
                    x = (w - face_size) // 2
                    y = (h - face_size) // 2
                    face_coords = (x, y, face_size, face_size)
                self.template_face_cache[template_key] = face_coords
                logger.info(f"Cached face detection for template: {face_coords}")
            else:
                face_coords = self.template_face_cache[template_key]
                logger.info(f"Using cached face detection: {face_coords}")
            
            # Process frames: generate one processed frame per mel chunk, then repeat
            output_frames = []
            
            # Process in batches for efficiency
            batch_size = 5
            processed_frames = []  # Store one processed frame per mel chunk
            
            for i in range(0, len(mel_chunks), batch_size):
                batch_mel = mel_chunks[i:i+batch_size]
                # Use cycling template frames
                batch_frames = [template_frames[j % len(template_frames)] for j in range(i, i + len(batch_mel))]
                
                # Process batch with pre-detected face coords
                batch_output = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._process_batch,
                    batch_frames,
                    batch_mel,
                    face_coords  # Pass pre-detected face coords
                )
                
                processed_frames.extend(batch_output)
            
            # Repeat each processed frame to match audio duration
            for frame in processed_frames:
                for _ in range(frames_per_chunk):
                    output_frames.append(frame.copy())
            
            logger.info(f"Generated {len(output_frames)} frames from {len(processed_frames)} processed frames")
            
            return output_frames
            
        except Exception as e:
            logger.error(f"Avatar generation error: {e}")
            return []
    
    def _process_batch(self, frames: List[np.ndarray], mel_chunks: List[np.ndarray], face_coords: Optional[Tuple[int, int, int, int]] = None) -> List[np.ndarray]:
        """Process a batch of frames with mel chunks"""
        output_frames = []
        
        for frame, mel in zip(frames, mel_chunks):
            try:
                # Use pre-detected face coords or detect face in frame
                if face_coords is None:
                    frame_face_coords = self._detect_face(frame)
                    if frame_face_coords is None:
                        output_frames.append(frame)
                        continue
                else:
                    frame_face_coords = face_coords
                
                # Crop face region
                face_img = self._crop_face(frame, frame_face_coords)
                
                # Prepare inputs following official Wav2Lip format
                face_input = self._preprocess_face(face_img)
                mel_input = mel.reshape(1, 80, 16, 1)  # (batch, height, width, channels)
                
                # Run inference
                if self.use_onnx:
                    outputs = self.wav2lip_session.run(
                        None,
                        {
                            'audio': mel_input.astype(np.float32),
                            'face': face_input.astype(np.float32)
                        }
                    )
                else:
                    # PyTorch inference following official implementation
                    with torch.no_grad():
                        # Convert to tensor and transpose to NCHW format
                        # face_input shape: (batch, height, width, 6)
                        # mel_input shape: (batch, 80, 16, 1)
                        face_tensor = torch.FloatTensor(np.transpose(face_input, (0, 3, 1, 2)))  # (batch, 6, 96, 96)
                        mel_tensor = torch.FloatTensor(np.transpose(mel_input, (0, 3, 1, 2)))    # (batch, 1, 80, 16)
                        
                        # Move to device
                        if torch.cuda.is_available():
                            face_tensor = face_tensor.cuda()
                            mel_tensor = mel_tensor.cuda()
                        
                        outputs = self.wav2lip_model(mel_tensor, face_tensor)
                        outputs = [outputs.cpu().numpy()]
                
                # Post-process output
                lip_img = self._postprocess_output(outputs[0])
                
                # Merge back to frame
                output_frame = self._merge_face(frame, lip_img, frame_face_coords)
                
                output_frames.append(output_frame)
                
            except Exception as e:
                logger.error(f"Error processing frame: {e}")
                output_frames.append(frame)
        
        return output_frames
    
    def _detect_face(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detect face in image using MediaPipe"""
        try:
            # Validate input image
            if image is None or image.size == 0:
                logger.warning("Invalid image for face detection")
                return None
            
            # Ensure image is contiguous and correct dtype
            if not image.flags['C_CONTIGUOUS']:
                image = np.ascontiguousarray(image)
            
            # Ensure uint8 format
            if image.dtype != np.uint8:
                image = image.astype(np.uint8)
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Ensure contiguous for MediaPipe
            if not rgb_image.flags['C_CONTIGUOUS']:
                rgb_image = np.ascontiguousarray(rgb_image)
            
            # Detect faces
            results = self.face_detector.process(rgb_image)
            
            if results.detections:
                detection = results.detections[0]
                bbox = detection.location_data.relative_bounding_box
                
                # Convert to pixel coordinates
                h, w = image.shape[:2]
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                width = int(bbox.width * w)
                height = int(bbox.height * h)
                
                # Add padding
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                width = min(w - x, width + 2 * padding)
                height = min(h - y, height + 2 * padding)
                
                return (x, y, width, height)
            
            return None
            
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return None
    
    def _crop_face(self, image: np.ndarray, coords: Tuple[int, int, int, int]) -> np.ndarray:
        """Crop face region from image"""
        x, y, w, h = coords
        face = image[y:y+h, x:x+w]
        
        # Resize to model input size
        face = cv2.resize(face, (self.img_size, self.img_size))
        
        return face
    
    def _preprocess_face(self, face: np.ndarray) -> np.ndarray:
        """Preprocess face for model input following official Wav2Lip implementation"""
        # face shape: (96, 96, 3)
        
        # Create masked version (mask lower half)
        face_masked = face.copy()
        face_masked[self.img_size//2:] = 0
        
        # Concatenate masked and original face along channel dimension
        # Result: (96, 96, 6)
        face_input = np.concatenate((face_masked, face), axis=2)
        
        # Normalize to [0, 1]
        face_input = face_input.astype(np.float32) / 255.0
        
        # Add batch dimension: (1, 96, 96, 6)
        face_input = np.expand_dims(face_input, axis=0)
        
        return face_input
    
    def _postprocess_output(self, output: np.ndarray) -> np.ndarray:
        """Post-process model output"""
        # output shape: (batch, channels, height, width)
        # Transpose to (batch, height, width, channels)
        output = np.transpose(output, (0, 2, 3, 1))
        
        # Remove batch dimension
        output = output[0]
        
        # Denormalize from [0, 1] to [0, 255]
        output = (output * 255).astype(np.uint8)
        
        return output
    
    def _merge_face(self, frame: np.ndarray, lip_img: np.ndarray, coords: Tuple[int, int, int, int]) -> np.ndarray:
        """Merge lip-synced face back to frame"""
        x, y, w, h = coords
        
        # Resize lip image to match face region
        lip_img = cv2.resize(lip_img, (w, h))
        
        # Create output frame
        output = frame.copy()
        
        # Simple blending
        output[y:y+h, x:x+w] = lip_img
        
        # Apply gaussian blur to edges for smoother blending
        if self.enhance_mode:
            mask = np.ones((h, w), dtype=np.float32)
            mask = cv2.GaussianBlur(mask, (21, 21), 10)
            mask = np.expand_dims(mask, axis=2)
            
            output[y:y+h, x:x+w] = (
                output[y:y+h, x:x+w] * (1 - mask) +
                lip_img * mask
            ).astype(np.uint8)
        
        return output
    
    async def _extract_mel_chunks(self, audio_data: bytes) -> List[np.ndarray]:
        """Extract mel spectrogram chunks from audio"""
        try:
            import librosa
            import soundfile as sf
            import io
            
            # Convert bytes to audio array
            audio_io = io.BytesIO(audio_data)
            audio, sr = sf.read(audio_io)
            
            # Ensure mono
            if len(audio.shape) > 1:
                audio = librosa.to_mono(audio.T)
            
            # Resample to 16kHz if needed
            if sr != 16000:
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                sr = 16000
            
            # Extract mel spectrogram
            mel_spectrogram = librosa.feature.melspectrogram(
                y=audio,
                sr=sr,
                n_fft=800,          # FFT window size
                hop_length=200,      # Hop length (80ms @ 16kHz = ~12.5ms per frame)
                n_mels=80,          # Number of mel bands
                fmin=55,            # Minimum frequency
                fmax=7600           # Maximum frequency
            )
            
            # Convert to log scale (dB)
            mel_db = librosa.power_to_db(mel_spectrogram, ref=np.max)
            
            # Normalize to [0, 1]
            mel_normalized = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
            
            # Split into chunks of mel_step_size (16 frames)
            mel_chunks = []
            num_frames = mel_normalized.shape[1]
            
            for i in range(0, num_frames - self.mel_step_size + 1, self.mel_step_size):
                mel_chunk = mel_normalized[:, i:i + self.mel_step_size]
                
                # Ensure correct shape (80, 16)
                if mel_chunk.shape[1] == self.mel_step_size:
                    mel_chunks.append(mel_chunk.astype(np.float32))
            
            # If no chunks were created, return at least one
            if len(mel_chunks) == 0 and num_frames > 0:
                # Pad or trim to mel_step_size
                if num_frames < self.mel_step_size:
                    pad_width = self.mel_step_size - num_frames
                    mel_chunk = np.pad(mel_normalized, ((0, 0), (0, pad_width)), mode='edge')
                else:
                    mel_chunk = mel_normalized[:, :self.mel_step_size]
                mel_chunks.append(mel_chunk.astype(np.float32))
            
            logger.info(f"Extracted {len(mel_chunks)} mel chunks from audio")
            
            return mel_chunks
            
        except Exception as e:
            logger.error(f"Mel extraction error: {e}")
            # Fallback: create minimal mel chunks based on audio duration
            duration = len(audio_data) / (16000 * 2)
            num_chunks = max(1, int(duration * self.fps))
            return [np.zeros((80, 16), dtype=np.float32) for _ in range(num_chunks)]
    
    async def _load_video_template(self, video_path: str) -> List[np.ndarray]:
        """Load video template frames"""
        # Handle relative paths
        if not video_path.startswith('/') and not video_path.startswith('.'):
            video_path = f"models/avatars/{video_path}"
        
        frames = []
        
        cap = cv2.VideoCapture(video_path)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Resize to target resolution
            frame = cv2.resize(frame, self.resolution)
            frames.append(frame)
        
        cap.release()
        
        # If static mode, use only first frame
        if self.static_mode and frames:
            return [frames[0]] * 100  # Repeat first frame
        
        return frames
    
    async def _load_image_template(self, image_path: str) -> List[np.ndarray]:
        """Load image template"""
        # Handle relative paths
        if not image_path.startswith('/') and not image_path.startswith('.'):
            image_path = f"models/avatars/{image_path}"
        
        logger.info(f"Loading avatar template: {image_path}")
        image = cv2.imread(image_path)
        
        if image is None:
            raise ValueError(f"Failed to load image template: {image_path}")
        
        logger.info(f"Template loaded: shape={image.shape}")
        image = cv2.resize(image, self.resolution)
        
        # Return multiple copies for static avatar
        return [image] * 100
    
    async def _add_audio_to_video(self, video_bytes: bytes, audio_bytes: bytes) -> bytes:
        """
        Add audio track to video using FFmpeg
        
        Args:
            video_bytes: Silent video bytes
            audio_bytes: Audio bytes (MP3 from TTS)
            
        Returns:
            Video bytes with audio track
        """
        import subprocess
        import tempfile
        from pathlib import Path
        
        video_path = None
        audio_path = None
        output_path = None
        
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
                video_file.write(video_bytes)
                video_path = video_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as audio_file:
                audio_file.write(audio_bytes)
                audio_path = audio_file.name
            
            output_path = video_path.replace('.mp4', '_with_audio.mp4')
            
            # FFmpeg command to add audio to video
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', video_path,  # Video input
                '-i', audio_path,  # Audio input
                '-c:v', 'copy',    # Copy video stream (no re-encoding)
                '-c:a', 'aac',     # Encode audio to AAC
                '-b:a', '128k',    # Audio bitrate
                '-shortest',       # End when shortest stream ends
                output_path
            ]
            
            # Run FFmpeg
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode != 0:
                stderr_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"FFmpeg audio merge failed (returncode {process.returncode}): {stderr_msg}")
                return b""
            
            # Check output file
            if not Path(output_path).exists():
                logger.error(f"Output video with audio not created: {output_path}")
                return b""
            
            file_size = Path(output_path).stat().st_size
            if file_size == 0:
                logger.error("Output video with audio is empty")
                return b""
            
            # Read result
            with open(output_path, 'rb') as f:
                result = f.read()
            
            logger.debug(f"Audio merge successful: {len(result)} bytes")
            return result
            
        except asyncio.TimeoutError:
            logger.error("FFmpeg audio merge timeout")
            return b""
        except Exception as e:
            logger.error(f"Audio merge error: {e}")
            return b""
        finally:
            # Cleanup temporary files
            for path in [video_path, audio_path, output_path]:
                if path and Path(path).exists():
                    try:
                        Path(path).unlink()
                    except:
                        pass
    
    async def generate(self, audio_data: bytes, template_path: str) -> bytes:
        """
        Public method to generate avatar video
        
        Args:
            audio_data: Audio bytes from TTS
            template_path: Path to avatar template
            
        Returns:
            MP4 video bytes
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.process(audio_data, template_path)
    
    def update_config(self, config: dict):
        """Update avatar configuration"""
        super().update_config(config)
        
        if "fps" in config:
            self.fps = config["fps"]
        if "resolution" in config:
            self.resolution = tuple(config["resolution"])
        if "static_mode" in config:
            self.static_mode = config["static_mode"]
        if "enhance_mode" in config:
            self.enhance_mode = config["enhance_mode"]
        if "use_onnx" in config:
            if config["use_onnx"] != self.use_onnx:
                logger.warning("Changing ONNX mode requires reinitializing the handler")
                self.use_onnx = config["use_onnx"]
