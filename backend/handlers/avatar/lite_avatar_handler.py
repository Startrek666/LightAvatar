"""
LiteAvatar Handler - 高性能CPU实时数字人驱动
基于参数化2D渲染，30fps实时性能
"""
import cv2
import numpy as np
import torch
from typing import List, Tuple, Optional, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from loguru import logger
import queue
import threading
import time
from io import BytesIO
import soundfile as sf
import wave

from backend.handlers.base import BaseHandler
from backend.core.health_monitor import timer, avatar_processing_time
from backend.utils.audio_utils import AudioProcessor


_TORCH_THREADS_CONFIGURED = False
_TORCH_THREADS_LOCK = threading.Lock()


def _configure_torch_threads(intra_threads: int = None, inter_threads: int = None) -> None:
    """
    确保PyTorch线程数只配置一次，避免重复调用导致的RuntimeError
    
    Args:
        intra_threads: 内部操作并行线程数（单个操作内的并行），默认从settings读取
        inter_threads: 操作间并行线程数（多个操作间的并行），默认从settings读取
    """
    global _TORCH_THREADS_CONFIGURED
    if _TORCH_THREADS_CONFIGURED:
        return
    
    with _TORCH_THREADS_LOCK:
        if _TORCH_THREADS_CONFIGURED:
            return
        
        # 从settings读取配置
        from backend.app.config import settings
        if intra_threads is None:
            intra_threads = settings.PYTORCH_INTRA_THREADS
        if inter_threads is None:
            inter_threads = settings.PYTORCH_INTER_THREADS
        
        try:
            torch.set_num_threads(intra_threads)
            torch.set_num_interop_threads(inter_threads)
            logger.info(f"PyTorch线程配置: intra={intra_threads}, inter={inter_threads}")
        except RuntimeError as exc:
            logger.warning(f"PyTorch线程配置失败，使用默认线程设置: {exc}")
        finally:
            _TORCH_THREADS_CONFIGURED = True


class LiteAvatarHandler(BaseHandler):
    """
    LiteAvatar数字人驱动Handler
    
    特性：
    - 30fps实时渲染
    - CPU原生优化
    - 参数化驱动，无需人脸检测
    - 流畅的口型动画
    """
    
    def __init__(self,
                 fps: int = 20,
                 resolution: Tuple[int, int] = (512, 512),
                 config: Optional[dict] = None):
        super().__init__(config)
        self.fps = fps
        self.resolution = resolution
        
        # LiteAvatar核心组件
        self.audio2mouth = None
        self.encoder = None
        self.generator = None
        
        # Avatar数据
        self.data_dir = None
        self.bg_data_list = []
        self.ref_img_list = []
        self.neutral_pose = None
        self.merge_mask = None
        
        # 人脸区域
        self.y1 = self.y2 = self.x1 = self.x2 = 0
        self.bg_video_frame_count = 0
        
        # ⚡ 优化：移除全局队列，改为动态创建独立队列（避免任务间竞争）
        self.threads = []
        
        # 设备
        self.use_gpu = self.config.get("use_gpu", False)
        self.device = "cuda" if self.use_gpu else "cpu"
        
        # 图像预处理
        from torchvision import transforms
        self.image_transforms = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.5], [0.5]),
        ])
        
        # 参数列表（32个口型参数）
        self.p_list = [str(ii) for ii in range(32)]
        
        # 音频处理器
        self.audio_processor = AudioProcessor()
        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    async def _setup(self):
        """初始化LiteAvatar模型和数据"""
        try:
            # 1. 检查avatar数据目录
            avatar_name = self.config.get("avatar_name", "default")
            self.data_dir = Path("models") / "lite_avatar" / avatar_name
            
            if not self.data_dir.exists():
                raise FileNotFoundError(
                    f"Avatar数据目录不存在: {self.data_dir}\n"
                    f"请运行: python scripts/prepare_lite_avatar_data.py --avatar {avatar_name}"
                )
            
            # 配置PyTorch线程数（确保只执行一次）
            _configure_torch_threads()
            
            # 2. 加载Audio2Mouth模型
            logger.info("加载Audio2Mouth模型...")
            self._load_audio2mouth()
            
            # 3. 加载Avatar动态模型
            logger.info("加载Avatar动态模型...")
            await self._load_avatar_model()
            
            # 4. 创建渲染线程池（⚡ 优化：每个任务动态分配线程）
            num_threads = self.config.get("render_threads", 4)
            self.render_executor = ThreadPoolExecutor(
                max_workers=num_threads,
                thread_name_prefix="LiteAvatar-Render"
            )
            logger.info(f"LiteAvatar初始化完成 - Avatar: {avatar_name}, FPS: {self.fps}, 渲染线程池: {num_threads}")
            
        except Exception as e:
            logger.error(f"LiteAvatar初始化失败: {e}")
            raise
    
    def _load_audio2mouth(self):
        """加载Audio2Mouth模型"""
        try:
            import onnxruntime
            
            # 优先使用 INT8 量化模型（加速 2~3 倍）
            int8_path = Path("models") / "lite_avatar" / "model_int8.onnx"
            fp32_path = Path("models") / "lite_avatar" / "model_1.onnx"

            if int8_path.exists():
                model_path = int8_path
                logger.info(f"检测到 INT8 量化模型: {int8_path}")
            elif fp32_path.exists():
                model_path = fp32_path
                logger.warning("未找到 INT8 模型，退回 FP32：加载速度会慢 2~3 倍")
            else:
                raise FileNotFoundError(
                    f"Audio2Mouth 模型不存在: {fp32_path} 或 {int8_path}\n"
                    f"请运行: bash scripts/download_lite_avatar_models.sh"
                )
            
            # 配置ONNX推理选项（从settings读取线程配置）
            from backend.app.config import settings
            sess_options = onnxruntime.SessionOptions()
            sess_options.intra_op_num_threads = settings.PYTORCH_INTRA_THREADS  # 算子内部并行线程数
            sess_options.inter_op_num_threads = settings.PYTORCH_INTER_THREADS  # 算子之间并行线程数
            sess_options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # 创建ONNX推理会话
            provider = "CUDAExecutionProvider" if self.use_gpu else "CPUExecutionProvider"
            self.audio2mouth = onnxruntime.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=[provider]
            )
            
            logger.info(
                f"Audio2Mouth模型已加载: {model_path.name} | provider={provider} | "
                f"threads={sess_options.intra_op_num_threads}")
            
        except ImportError:
            logger.error("缺少依赖: onnxruntime，请运行: pip install onnxruntime")
            raise
    
    async def _load_avatar_model(self):
        """加载Avatar编码器和生成器"""
        # 加载编解码器模型
        encoder_path = self.data_dir / "net_encode.pt"
        decoder_path = self.data_dir / "net_decode.pt"
        
        if not encoder_path.exists() or not decoder_path.exists():
            raise FileNotFoundError(
                f"Avatar模型文件缺失:\n"
                f"  - {encoder_path}\n"
                f"  - {decoder_path}"
            )
        
        self.encoder = torch.jit.load(str(encoder_path)).to(self.device)
        self.generator = torch.jit.load(str(decoder_path)).to(self.device)
        
        # 加载中性表情参数
        neutral_pose_path = self.data_dir / "neutral_pose.npy"
        if neutral_pose_path.exists():
            self.neutral_pose = np.load(str(neutral_pose_path))
        else:
            self.neutral_pose = np.zeros(32)
        
        # 加载背景视频
        await self._load_background_video()
        
        # 加载并编码参考帧
        await self._load_reference_frames()
        
        # Warm-up推理：避免第一次推理输出NaN
        logger.info("执行模型warm-up推理...")
        await self._warmup_model()
        
        logger.info(f"Avatar模型已加载 - 背景帧数: {self.bg_video_frame_count}, 参考帧数: {len(self.ref_img_list)}")
    
    async def _load_background_video(self):
        """加载背景视频帧"""
        bg_video_path = self.data_dir / "bg_video.mp4"
        if not bg_video_path.exists():
            raise FileNotFoundError(f"背景视频不存在: {bg_video_path}")
        
        # 读取背景视频
        bg_video = cv2.VideoCapture(str(bg_video_path))
        self.bg_data_list = []
        
        while True:
            ret, frame = bg_video.read()
            if not ret:
                break
            self.bg_data_list.append(frame)
        
        bg_video.release()
        
        bg_frame_cnt = self.config.get("bg_frame_count", 150)
        self.bg_video_frame_count = min(bg_frame_cnt, len(self.bg_data_list))
        
        # 读取人脸区域
        face_box_path = self.data_dir / "face_box.txt"
        if face_box_path.exists():
            with open(face_box_path, 'r') as f:
                y1, y2, x1, x2 = f.readline().strip().split()
                self.y1, self.y2, self.x1, self.x2 = int(y1), int(y2), int(x1), int(x2)
        
        # 创建融合mask
        self.merge_mask = (np.ones((self.y2 - self.y1, self.x2 - self.x1, 3)) * 255).astype(np.uint8)
        self.merge_mask[10:-10, 10:-10, :] *= 0
        self.merge_mask = cv2.GaussianBlur(self.merge_mask, (21, 21), 15)
        self.merge_mask = self.merge_mask / 255
        logger.info(
            f"脸部ROI: y=({self.y1},{self.y2}), x=({self.x1},{self.x2}), mask形状={self.merge_mask.shape}"
        )
    
    async def _load_reference_frames(self):
        """加载并编码参考帧"""
        ref_frames_dir = self.data_dir / "ref_frames"
        if not ref_frames_dir.exists():
            raise FileNotFoundError(f"参考帧目录不存在: {ref_frames_dir}")
        
        self.ref_img_list = []
        
        for ii in range(self.bg_video_frame_count):
            ref_path = ref_frames_dir / f"ref_{ii:05d}.jpg"
            if not ref_path.exists():
                logger.warning(f"参考帧不存在: {ref_path}")
                continue
            
            # 读取并预处理
            image = cv2.cvtColor(cv2.imread(str(ref_path))[:, :, 0:3], cv2.COLOR_BGR2RGB)
            image = cv2.resize(image, (384, 384), interpolation=cv2.INTER_LINEAR)
            ref_img = self.image_transforms(np.uint8(image))
            
            # 编码
            encoder_input = ref_img.unsqueeze(0).float().to(self.device)
            with torch.no_grad():
                x = self.encoder(encoder_input)
            # ⚡ 保持encoder输出为list格式（generator期望List[Tensor]）
            if not isinstance(x, (list, tuple)):
                x = [x]  # 转换为list
            # 去掉每个tensor的batch维度
            x = [t.squeeze(0) for t in x]
            self.ref_img_list.append(x)
    
    async def _warmup_model(self):
        """执行warm-up推理避免NaN"""
        try:
            # 使用中性参数执行一次推理
            neutral_params = {key: 0.0 for key in self.p_list}
            
            # 使用第一个参考帧
            if self.ref_img_list:
                with torch.no_grad():
                    # ref_img_list[i]是List[Tensor]，需要添加batch维度
                    ref_img = [t.unsqueeze(0).to(self.device) for t in self.ref_img_list[0]]
                    test_output = self.generator(
                        ref_img,
                        torch.zeros(1, 32).float().to(self.device)
                    )
                    # 检查输出
                    if torch.isnan(test_output).any():
                        logger.warning("Warm-up推理仍包含NaN，将在运行时处理")
                    else:
                        logger.info("Warm-up推理成功")
        except Exception as e:
            logger.warning(f"Warm-up推理失败: {e}，继续启动")
    
    async def process(self, data: Dict[str, Any]) -> bytes:
        """
        处理音频生成数字人视频
        
        Args:
            data: 包含audio_data（音频字节）的字典
        
        Returns:
            视频字节流（MP4格式）
        """
        import time
        start_total = time.time()
        
        with timer(avatar_processing_time):
            try:
                # ⚡ 优化：移除全局锁，允许并发渲染多个视频
                audio_data = data.get("audio_data")
                if not audio_data:
                    raise ValueError("缺少audio_data参数")
                
                # 1. 音频转参数（带超时保护）
                logger.info("提取口型参数...")
                start = time.time()
                try:
                    param_res = await asyncio.wait_for(
                        self._audio_to_params(audio_data),
                        timeout=60.0  # 60秒超时
                    )
                    logger.debug(f"口型参数提取耗时: {time.time() - start:.2f}秒")
                except asyncio.TimeoutError:
                    logger.error("❌ 口型参数提取超时（60秒）")
                    raise ValueError("口型参数提取超时")
                
                # 2. 参数转视频帧（带超时保护）
                logger.info(f"渲染{len(param_res)}帧...")
                start = time.time()
                try:
                    frames = await asyncio.wait_for(
                        self._params_to_frames(param_res),
                        timeout=120.0  # 120秒超时（渲染可能较慢）
                    )
                    video_duration = len(frames) / self.fps if self.fps else 0
                    logger.info(f"视频帧数: {len(frames)}, 预期时长: {video_duration:.2f}秒")
                    logger.debug(f"帧渲染耗时: {time.time() - start:.2f}秒")
                except asyncio.TimeoutError:
                    logger.error("❌ 视频帧渲染超时（120秒）")
                    raise ValueError("视频帧渲染超时")
                
                # 3. 合成视频（带超时保护）
                logger.info("合成视频...")
                start = time.time()
                try:
                    video_data = await asyncio.wait_for(
                        self._frames_to_video(frames, audio_data),
                        timeout=60.0  # 60秒超时
                    )
                    logger.debug(f"视频合成耗时: {time.time() - start:.2f}秒")
                except asyncio.TimeoutError:
                    logger.error("❌ 视频合成超时（60秒）")
                    raise ValueError("视频合成超时")
                
                logger.info(f"总耗时: {time.time() - start_total:.2f}秒")
                
                return video_data
                
            except Exception as e:
                logger.error(f"LiteAvatar处理失败: {e}")
                raise
    
    async def generate(self, audio_data: bytes, template_path: str = None) -> bytes:
        """
        生成数字人视频（公共接口）
        
        Args:
            audio_data: 音频字节流（来自TTS）
            template_path: 模板路径（LiteAvatar不使用此参数）
        
        Returns:
            MP4视频字节流
        """
        if not self._initialized:
            await self.initialize()
        
        # 调用process方法
        return await self.process({"audio_data": audio_data})
    
    async def _audio_to_params(self, audio_data: bytes) -> List[Dict[str, float]]:
        """音频转口型参数"""
        try:
            # 将TTS音频（默认MP3）转换为16k单声道WAV
            wav_bytes = await self.audio_processor.convert_to_wav(audio_data, input_format="mp3")
            if not wav_bytes:
                raise ValueError("音频转换失败")

            audio_array, sr = sf.read(BytesIO(wav_bytes))
            if sr != 16000:
                # 双重保险：ffmpeg应已转换为16k，如果仍不一致则强制重采样
                audio_array = self.audio_processor.resample_audio(audio_array, sr, 16000)
                sr = 16000
            audio_duration = len(audio_array) / sr if sr else 0
            logger.info(f"音频时长: {audio_duration:.2f}秒, 采样率: {sr}")
            
            # 提取Paraformer特征（带超时保护）
            # 向上取整确保视频时长 >= 音频时长
            import math
            frame_cnt = math.ceil(len(audio_array) / 16000 * self.fps)
            logger.info(f"🎯 开始提取音频特征 (帧数: {frame_cnt})...")
            try:
                au_data = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        self._extract_paraformer_feature,
                        audio_array,
                        frame_cnt
                    ),
                    timeout=30.0  # 30秒超时
                )
                logger.info(f"✅ 音频特征提取完成: {au_data.shape}")
            except asyncio.TimeoutError:
                logger.error("❌ 音频特征提取超时（30秒）")
                raise ValueError("音频特征提取超时")
            
            # 清理特征中的NaN/Inf，避免后续推理异常
            au_data = np.nan_to_num(au_data, nan=0.0, posinf=0.0, neginf=0.0)
            
            # 预测口型参数（带超时保护）
            ph_data = np.zeros((au_data.shape[0], 2))
            logger.info(f"🎯 开始推理口型参数...")
            try:
                param_res = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        self._inference_mouth_params,
                        au_data,
                        ph_data
                    ),
                    timeout=30.0  # 30秒超时
                )
                logger.info(f"✅ 口型参数推理完成: {len(param_res)} 个参数")
            except asyncio.TimeoutError:
                logger.error("❌ 口型参数推理超时（30秒）")
                raise ValueError("口型参数推理超时")
            
            # FPS转换
            if self.fps != 30:
                param_res = self._interpolate_params(param_res, self.fps)
            
            return param_res
            
        except Exception as e:
            logger.error(f"音频转参数失败: {e}")
            raise
    
    def _extract_paraformer_feature(self, audio_array: np.ndarray, frame_cnt: int) -> np.ndarray:
        """提取Paraformer特征"""
        try:
            # 导入特征提取函数
            import sys
            # 尝试多个可能的路径
            possible_paths = [
                Path("/opt/lite-avatar"),
                Path("/opt/lightavatar/lite-avatar"),
                Path("d:/Aprojects/Light-avatar/lite-avatar-main")
            ]
            
            for lite_avatar_path in possible_paths:
                if lite_avatar_path.exists():
                    if str(lite_avatar_path) not in sys.path:
                        sys.path.insert(0, str(lite_avatar_path))
                    break
            
            from extract_paraformer_feature import extract_para_feature
            return extract_para_feature(audio_array, frame_cnt)
            
        except Exception as e:
            logger.warning(f"Paraformer特征提取失败，使用MFCC替代: {e}")
            # Fallback: 使用librosa提取MFCC特征
            return self._extract_mfcc_feature(audio_array, frame_cnt)
    
    def _extract_mfcc_feature(self, audio_array: np.ndarray, frame_cnt: int) -> np.ndarray:
        """使用MFCC作为音频特征的fallback，匹配Paraformer格式(frames, 50, 512)"""
        try:
            import librosa
            
            # 模型期望输入: (frames, 50, 512)
            # 总特征维度: 50 * 512 = 25600
            target_seq_len = 50
            target_feat_dim = 512
            
            # 提取梅尔频谱图作为特征
            n_mels = 80
            hop_length = len(audio_array) // frame_cnt if frame_cnt > 0 else 512
            
            # 提取Mel频谱
            mel = librosa.feature.melspectrogram(
                y=audio_array,
                sr=16000,
                n_mels=n_mels,
                hop_length=hop_length,
                n_fft=2048
            )
            
            # 转换为对数刻度
            mel_db = librosa.power_to_db(mel, ref=np.max)
            
            # 转置为 (frames, n_mels)
            mel_db = mel_db.T
            
            # 调整到目标帧数
            if mel_db.shape[0] != frame_cnt:
                from scipy import interpolate
                x = np.linspace(0, frame_cnt - 1, mel_db.shape[0])
                x_new = np.arange(frame_cnt)
                f = interpolate.interp1d(x, mel_db, axis=0, kind='linear', fill_value='extrapolate')
                mel_db = f(x_new)
            
            # 扩展特征：重复并padding到 (frames, 50*512)
            # 先扩展到25600维
            total_dim = target_seq_len * target_feat_dim  # 25600
            if mel_db.shape[1] < total_dim:
                # 重复并padding
                repeats = (total_dim // mel_db.shape[1]) + 1
                expanded = np.tile(mel_db, (1, repeats))
                expanded = expanded[:, :total_dim]
            else:
                expanded = mel_db[:, :total_dim]
            
            # Reshape为 (frames, 50, 512)
            features = expanded.reshape(frame_cnt, target_seq_len, target_feat_dim)
            
            logger.info(f"使用MFCC特征替代Paraformer: shape={features.shape}")
            return features.astype(np.float32)
            
        except Exception as e:
            logger.error(f"MFCC提取失败: {e}")
            # 最后的fallback：零特征，正确的4D形状
            return np.zeros((frame_cnt, 50, 512), dtype=np.float32)
    
    def _inference_mouth_params(self, au_data: np.ndarray, ph_data: np.ndarray) -> List[Dict[str, float]]:
        """推理口型参数（使用官方逻辑）"""
        param_res = []
        # 记录实际帧数（用于截断padding的帧）
        actual_frame_count = au_data.shape[0]
        audio_length = ph_data.shape[0] / 30
        interval = 1.0
        frag = int(interval * 30 / 5 + 0.5)
        
        w = np.array([1.0]).astype(np.float32)
        sp = np.array([2]).astype(np.int64)
        
        start_time = 0.0
        end_time = start_time + interval
        is_end = False
        
        while True:
            start_frame = int(start_time * 30)
            end_frame = start_frame + int(30 * interval)
            
            # 处理音频结束情况
            if end_time >= audio_length:
                is_end = True
                end_frame = au_data.shape[0]
                # 如果音频不足1秒，从末尾向前取30帧（padding）
                if end_frame < 30:
                    start_frame = 0
                    # Padding到30帧
                    pad_size = 30 - end_frame
                    # au_data是3D (frames, 50, 512)，需要3个维度的padding
                    input_au = np.pad(au_data, ((0, pad_size), (0, 0), (0, 0)), mode='edge')
                    # ph_data是2D (frames, 2)，需要2个维度的padding
                    input_ph = np.pad(ph_data, ((0, pad_size), (0, 0)), mode='edge')
                else:
                    start_frame = end_frame - int(30 * interval)
                    input_au = au_data[start_frame:end_frame]
                    input_ph = ph_data[start_frame:end_frame]
                start_time = max(0, audio_length - interval)
                end_time = audio_length
            else:
                input_au = au_data[start_frame:end_frame]
                input_ph = ph_data[start_frame:end_frame]
            
            input_au = input_au[np.newaxis, :].astype(np.float32)
            input_ph = input_ph[np.newaxis, :].astype(np.float32)

            # 运行前再次清理NaN/Inf
            input_au = np.nan_to_num(input_au, nan=0.0, posinf=0.0, neginf=0.0)
            input_ph = np.nan_to_num(input_ph, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Debug: 打印输入形状
            logger.debug(f"ONNX输入形状 - input_au: {input_au.shape}, input_ph: {input_ph.shape}")
            
            # 推理
            try:
                output, feat = self.audio2mouth.run(
                    ['output', 'feat'],
                    {'input_au': input_au, 'input_ph': input_ph, 'input_sp': sp, 'w': w}
                )
            except Exception as e:
                # 打印模型期望的输入形状
                logger.error(f"ONNX推理失败: {e}")
                logger.error(f"当前输入形状: input_au={input_au.shape}, input_ph={input_ph.shape}")
                # 尝试获取模型输入规格
                try:
                    for inp in self.audio2mouth.get_inputs():
                        logger.error(f"模型期望输入 '{inp.name}': shape={inp.shape}, type={inp.type}")
                except:
                    pass
                raise
            
            # 清理推理输出中的NaN/Inf，避免后续口型为中性
            output = np.nan_to_num(output, nan=0.0, posinf=0.0, neginf=0.0)

            # 提取参数
            if start_time == 0.0:
                end_idx = int(30 * interval) if not is_end else int(30 * interval)
                for tt in range(end_idx - (0 if is_end else frag)):
                    param_frame = {}
                    for ii, key in enumerate(self.p_list):
                        param_frame[key] = round(float(output[0, tt, ii]), 3)
                    param_res.append(param_frame)
            elif not is_end:
                for tt in range(frag, int(30 * interval) - frag):
                    frame_id = start_frame + tt
                    if frame_id < len(param_res):
                        scale = min((len(param_res) - frame_id) / frag, 1.0)
                        for ii, key in enumerate(self.p_list):
                            value = float(output[0, tt, ii])
                            value = (1 - scale) * value + scale * param_res[frame_id][key]
                            param_res[frame_id][key] = round(value, 3)
                    else:
                        param_frame = {}
                        for ii, key in enumerate(self.p_list):
                            param_frame[key] = round(float(output[0, tt, ii]), 3)
                        param_res.append(param_frame)
            else:
                for tt in range(frag, int(30 * interval)):
                    frame_id = start_frame + tt
                    if frame_id < len(param_res):
                        scale = min((len(param_res) - frame_id) / frag, 1.0)
                        for ii, key in enumerate(self.p_list):
                            value = float(output[0, tt, ii])
                            value = (1 - scale) * value + scale * param_res[frame_id][key]
                            param_res[frame_id][key] = round(value, 3)
                    else:
                        param_frame = {}
                        for ii, key in enumerate(self.p_list):
                            param_frame[key] = round(float(output[0, tt, ii]), 3)
                        param_res.append(param_frame)
            
            start_time = end_time - (frag / 10)
            end_time = start_time + interval
            if is_end:
                break
        
        # 推理逻辑已经根据audio_length正确生成了帧数，不需要额外截断
        logger.debug(f"推理生成 {len(param_res)} 帧参数（音频特征帧数: {actual_frame_count}）")
        
        # 平滑处理
        param_res = self._smooth_params(param_res)
        
        return param_res
    
    def _smooth_params(self, param_res: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """平滑口型参数"""
        from scipy import signal
        
        for key in param_res[0]:
            val_list = [p[key] for p in param_res]
            val_array = np.array(val_list)
            
            # Butterworth低通滤波
            wn = 2 * 10 / 30  # cutoff=10, fs=30
            b, a = signal.butter(4, wn, 'lowpass', analog=False)
            smoothed = signal.filtfilt(b, a, val_array, padtype=None, axis=0)
            
            for ii, p in enumerate(param_res):
                p[key] = float(smoothed[ii])
        
        return param_res
    
    def _interpolate_params(self, param_res: List[Dict[str, float]], target_fps: int) -> List[Dict[str, float]]:
        """参数插值以适配目标FPS"""
        from scipy.interpolate import interp1d
        
        old_len = len(param_res)
        new_len = int(old_len / 30 * target_fps + 0.5)
        
        interp_dict = {}
        for key in param_res[0]:
            val_list = [p[key] for p in param_res]
            val_array = np.array(val_list)
            
            x = np.linspace(0, old_len - 1, num=old_len, endpoint=True)
            newx = np.linspace(0, old_len - 1, num=new_len, endpoint=True)
            f = interp1d(x, val_array)
            interp_dict[key] = f(newx)
        
        new_param_res = []
        for ii in range(new_len):
            param_frame = {}
            for key in interp_dict:
                param_frame[key] = float(interp_dict[key][ii])
            new_param_res.append(param_frame)
        
        return new_param_res
    
    async def _params_to_frames(self, param_res: List[Dict[str, float]]) -> List[np.ndarray]:
        """⚡ 优化：批量推理（串行执行避免CPU过载）"""
        logger.debug(f"开始渲染 {len(param_res)} 个参数帧")
        
        # 准备背景帧ID
        bg_frame_ids = []
        for ii in range(len(param_res)):
            if int(ii / self.bg_video_frame_count) % 2 == 0:
                bg_frame_id = ii % self.bg_video_frame_count
            else:
                bg_frame_id = self.bg_video_frame_count - 1 - ii % self.bg_video_frame_count
            bg_frame_ids.append(bg_frame_id)
        
        # ⚡ 优化：适中的batch_size，平衡速度与资源
        # CPU环境：batch_size=16最优（避免内存带宽瓶颈）
        batch_size = 16
        
        # 串行处理batch（避免过度并发导致CPU过载）
        loop = asyncio.get_event_loop()
        frames = []
        
        for start_idx in range(0, len(param_res), batch_size):
            end_idx = min(start_idx + batch_size, len(param_res))
            batch_params = param_res[start_idx:end_idx]
            batch_bg_ids = bg_frame_ids[start_idx:end_idx]
            
            # 批量推理当前batch
            batch_frames = await loop.run_in_executor(
                self.render_executor,
                self._render_batch_frames,
                batch_params, batch_bg_ids, start_idx
            )
            frames.extend(batch_frames)
        
        num_batches = (len(param_res) + batch_size - 1) // batch_size
        logger.debug(f"所有 {len(frames)} 帧渲染完成（{num_batches}个batch，batch_size={batch_size}）")
        
        # 清理缓存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        import gc
        gc.collect()
        
        return frames
    
    def _render_batch_frames(self, batch_params: List[Dict[str, float]], 
                            batch_bg_ids: List[int], start_idx: int) -> List[np.ndarray]:
        """⚡ 批量渲染帧（加速关键）"""
        try:
            batch_size = len(batch_params)
            
            # 1. 批量准备参数
            param_arrays = np.array([[p[key] for key in self.p_list] for p in batch_params])
            param_arrays = np.nan_to_num(param_arrays, nan=0.0)
            
            # 2. 批量推理（关键优化：一次推理多帧）
            with torch.no_grad():
                param_tensor = torch.from_numpy(param_arrays).float().to(self.device)  # (batch, 32)
                
                # 准备批量ref_imgs（List[Tensor]格式）
                # ref_img_list[i]是List[Tensor]，需要将batch中的多个List合并
                # 例如：ref_img_list[0]=[t0,t1], ref_img_list[1]=[t0',t1']
                # 合并成：[stack([t0,t0']), stack([t1,t1'])]
                ref_imgs_list = [self.ref_img_list[bg_id] for bg_id in batch_bg_ids]
                num_tensors = len(ref_imgs_list[0])  # List中Tensor的数量
                ref_imgs_batch = [
                    torch.stack([ref_imgs_list[j][i] for j in range(len(ref_imgs_list))]).to(self.device)
                    for i in range(num_tensors)
                ]
                
                # 批量生成
                mouth_imgs = self.generator(ref_imgs_batch, param_tensor)  # (batch, 3, H, W)
                
                # 检测NaN
                if torch.isnan(mouth_imgs).any():
                    logger.warning(f"批量推理输出包含NaN，使用零张量替代")
                    mouth_imgs = torch.nan_to_num(mouth_imgs, nan=0.0)
            
            # 3. 批量后处理
            mouth_imgs = mouth_imgs.detach().cpu()
            mouth_imgs = (mouth_imgs / 2 + 0.5).clamp(0, 1)  # 反归一化
            
            frames = []
            for i, bg_id in enumerate(batch_bg_ids):
                # 提取单帧
                mouth_img = mouth_imgs[i].permute(1, 2, 0) * 255
                mouth_img = mouth_img.numpy().astype(np.uint8)
                
                # 调整大小
                mouth_img = cv2.resize(mouth_img, (self.x2 - self.x1, self.y2 - self.y1))
                mouth_img = mouth_img[:, :, ::-1]  # RGB to BGR
                
                # 融合到背景
                full_img = self.bg_data_list[bg_id].copy()
                full_img[self.y1:self.y2, self.x1:self.x2, :] = (
                    mouth_img * (1 - self.merge_mask) +
                    full_img[self.y1:self.y2, self.x1:self.x2, :] * self.merge_mask
                )
                
                frames.append(full_img.astype(np.uint8))
            
            return frames
            
        except Exception as e:
            logger.error(f"批量渲染失败 (起始帧{start_idx}): {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 返回空帧
            return [np.zeros((self.resolution[1], self.resolution[0], 3), dtype=np.uint8) 
                   for _ in range(len(batch_params))]
    
    def _param_to_image(self, params: Dict[str, float], bg_frame_id: int) -> torch.Tensor:
        """参数转嘴部图像"""
        # 边界检查
        if not self.ref_img_list or bg_frame_id >= len(self.ref_img_list):
            logger.error(
                f"ref_img_list访问越界: bg_frame_id={bg_frame_id}, "
                f"ref_img_list长度={len(self.ref_img_list) if self.ref_img_list else 0}"
            )
            # 返回零张量避免崩溃
            return torch.zeros((1, 3, 384, 384))
        
        param_val = np.array([params[key] for key in self.p_list])
        
        # 检测参数中的NaN
        if np.isnan(param_val).any():
            logger.warning(f"口型参数包含NaN，使用中性值替代")
            param_val = np.nan_to_num(param_val, nan=0.0)
        
        with torch.no_grad():
            # ref_img_list[i]是List[Tensor]，需要添加batch维度
            ref_img = [t.unsqueeze(0).to(self.device) for t in self.ref_img_list[bg_frame_id]]
            output = self.generator(
                ref_img,
                torch.from_numpy(param_val).unsqueeze(0).float().to(self.device)
            )
            
            # 检测输出中的NaN
            if torch.isnan(output).any():
                logger.error(f"生成器输出包含NaN (bg_frame_id={bg_frame_id})，使用零张量替代")
                output = torch.zeros_like(output)
        
        return output.detach().cpu()
    
    def _merge_mouth_to_bg(self, mouth_image: torch.Tensor, bg_frame_id: int) -> Tuple[np.ndarray, np.ndarray]:
        """融合嘴部到背景"""
        # 反归一化
        mouth_image = (mouth_image / 2 + 0.5).clamp(0, 1)
        mouth_image = mouth_image[0].permute(1, 2, 0) * 255
        mouth_image = mouth_image.numpy().astype(np.uint8)
        
        # 调整大小
        mouth_image = cv2.resize(mouth_image, (self.x2 - self.x1, self.y2 - self.y1))
        mouth_image = mouth_image[:, :, ::-1]  # RGB to BGR
        
        # 融合
        full_img = self.bg_data_list[bg_frame_id].copy()
        full_img[self.y1:self.y2, self.x1:self.x2, :] = (
            mouth_image * (1 - self.merge_mask) +
            full_img[self.y1:self.y2, self.x1:self.x2, :] * self.merge_mask
        )
        
        return full_img.astype(np.uint8), mouth_image.astype(np.uint8)
    
    async def _frames_to_video(self, frames: List[np.ndarray], audio_data: bytes) -> bytes:
        """帧序列合成视频（优化版：FFmpeg管道编码 + Fallback）"""
        import subprocess
        
        height, width = frames[0].shape[:2]
        
        # 准备音频临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
            headinfo = self._generate_wav_header(16000, 16, len(audio_data))
            tmp_audio.write(headinfo + audio_data)
            audio_path = tmp_audio.name
        
        # 输出视频临时文件
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_video:
            video_path = tmp_video.name
        
        try:
            # 方法1：FFmpeg管道编码（极速优化）
            logger.debug("尝试FFmpeg管道编码...")
            cmd = [
                'ffmpeg', '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{width}x{height}',
                '-r', str(self.fps),
                '-i', '-',
                '-i', audio_path,
                # ⚡ 极速编码优化
                '-c:v', 'libx264',
                '-preset', 'ultrafast',  # 最快预设
                '-tune', 'zerolatency',  # 零延迟调优
                '-crf', '30',  # 提高到30，降低质量换速度
                '-g', '999',  # 关键帧间隔，减少编码复杂度
                '-threads', '2',  # 限制编码线程，避免抢占渲染线程
                '-c:a', 'aac',
                '-b:a', '64k',  # 降低音频比特率
                '-movflags', '+faststart+frag_keyframe',
                '-loglevel', 'error',
                video_path
            ]
            
            # ⚡ 优化：预先连接帧数据
            try:
                # 使用numpy连续数组加速
                frames_array = np.ascontiguousarray(np.array(frames, dtype=np.uint8))
                frame_bytes = frames_array.tobytes()
            except Exception as e:
                logger.error(f"帧数据准备失败: {e}，使用fallback方法")
                raise
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, input=frame_bytes, capture_output=True, timeout=30)
            )
            
            if result.returncode != 0:
                stderr_msg = result.stderr.decode() if result.stderr else "Unknown error"
                logger.warning(f"FFmpeg管道编码失败: {stderr_msg}，使用fallback方法")
                raise RuntimeError("FFmpeg管道编码失败")
            
            # 读取视频数据
            with open(video_path, 'rb') as f:
                video_data = f.read()
            
            if len(video_data) == 0:
                logger.warning("FFmpeg生成空视频，使用fallback方法")
                raise RuntimeError("空视频")
            
            logger.debug(f"FFmpeg管道编码成功: {len(video_data)} bytes")
            
        except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError, Exception) as e:
            # Fallback：使用OpenCV编码 + FFmpeg合并音频（兼容性更好）
            logger.warning(f"FFmpeg管道失败 ({e})，使用OpenCV fallback")
            video_data = await self._frames_to_video_fallback(frames, audio_data, audio_path, video_path)
        
        finally:
            # 清理临时文件
            Path(video_path).unlink(missing_ok=True)
            Path(audio_path).unlink(missing_ok=True)
        
        return video_data
    
    async def _frames_to_video_fallback(self, frames: List[np.ndarray], audio_data: bytes, 
                                       audio_path: str, video_path: str) -> bytes:
        """Fallback方法：OpenCV编码 + FFmpeg合并音频"""
        import subprocess
        
        height, width = frames[0].shape[:2]
        
        try:
            # 使用OpenCV写入视频（无音频）
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_video_no_audio:
                video_no_audio_path = tmp_video_no_audio.name
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(video_no_audio_path, fourcc, self.fps, (width, height))
            
            if not out.isOpened():
                logger.error("OpenCV VideoWriter初始化失败")
                raise RuntimeError("OpenCV初始化失败")
            
            for frame in frames:
                out.write(frame)
            out.release()
            
            # 使用FFmpeg合并音视频
            cmd = [
                'ffmpeg', '-y',
                '-i', video_no_audio_path,
                '-i', audio_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', 'frag_keyframe+empty_moov',
                '-loglevel', 'error',
                video_path
            ]
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, timeout=30)
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg音视频合并失败: {result.stderr.decode()}")
                raise RuntimeError("音视频合并失败")
            
            # 读取视频数据
            with open(video_path, 'rb') as f:
                video_data = f.read()
            
            # 清理OpenCV临时文件
            Path(video_no_audio_path).unlink(missing_ok=True)
            
            logger.info(f"OpenCV fallback成功: {len(video_data)} bytes")
            return video_data
            
        except Exception as e:
            logger.error(f"Fallback方法也失败: {e}")
            raise RuntimeError(f"视频合成完全失败: {e}")
    
    def _generate_wav_header(self, sample_rate: int, bits: int, sample_num: int) -> bytes:
        """生成WAV文件头"""
        import struct
        header = b'\x52\x49\x46\x46'
        file_length = struct.pack('i', sample_num + 36)
        header += file_length
        header += b'\x57\x41\x56\x45\x66\x6D\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00'
        header += struct.pack('i', sample_rate)
        header += struct.pack('i', int(sample_rate * bits / 8))
        header += b'\x02\x00'
        header += struct.pack('H', bits)
        header += b'\x64\x61\x74\x61'
        header += struct.pack('i', sample_num)
        return header
    
    async def cleanup(self):
        """清理资源"""
        # 停止渲染线程
        self.input_queue.put(None)
        for t in self.threads:
            t.join(timeout=5)
        
        # 清理模型
        self.audio2mouth = None
        self.encoder = None
        self.generator = None
        
        self.executor.shutdown(wait=False)
        
        await super().cleanup()
