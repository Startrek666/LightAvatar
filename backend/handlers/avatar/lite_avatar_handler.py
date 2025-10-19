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
                 fps: int = 30,
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
        
        # 处理队列
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
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
            
            # 2. 加载Audio2Mouth模型
            logger.info("加载Audio2Mouth模型...")
            self._load_audio2mouth()
            
            # 3. 加载Avatar动态模型
            logger.info("加载Avatar动态模型...")
            await self._load_avatar_model()
            
            # 4. 启动渲染线程
            num_threads = self.config.get("render_threads", 1)
            logger.info(f"启动{num_threads}个渲染线程...")
            barrier = threading.Barrier(num_threads)
            for i in range(num_threads):
                t = threading.Thread(
                    target=self._render_loop,
                    args=(i, barrier, self.input_queue, self.output_queue)
                )
                t.daemon = True
                t.start()
                self.threads.append(t)
            
            logger.info(f"LiteAvatar初始化完成 - Avatar: {avatar_name}, FPS: {self.fps}")
            
        except Exception as e:
            logger.error(f"LiteAvatar初始化失败: {e}")
            raise
    
    def _load_audio2mouth(self):
        """加载Audio2Mouth模型"""
        try:
            import onnxruntime
            
            model_path = Path("models") / "lite_avatar" / "model_1.onnx"
            if not model_path.exists():
                raise FileNotFoundError(
                    f"Audio2Mouth模型不存在: {model_path}\n"
                    f"请运行: bash scripts/download_lite_avatar_models.sh"
                )
            
            # 创建ONNX推理会话
            provider = "CUDAExecutionProvider" if self.use_gpu else "CPUExecutionProvider"
            self.audio2mouth = onnxruntime.InferenceSession(
                str(model_path),
                providers=[provider]
            )
            
            logger.info(f"Audio2Mouth模型已加载: {provider}")
            
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
        
        # 加载参考帧
        await self._load_reference_frames()
        
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
            self.ref_img_list.append(x)
    
    async def process(self, data: Dict[str, Any]) -> bytes:
        """
        处理音频生成数字人视频
        
        Args:
            data: 包含audio_data（音频字节）的字典
        
        Returns:
            视频字节流（MP4格式）
        """
        with timer(avatar_processing_time):
            try:
                audio_data = data.get("audio_data")
                if not audio_data:
                    raise ValueError("缺少audio_data参数")
                
                # 1. 音频转参数
                logger.info("提取口型参数...")
                param_res = await self._audio_to_params(audio_data)
                
                # 2. 参数转视频帧
                logger.info(f"渲染{len(param_res)}帧...")
                frames = await self._params_to_frames(param_res)
                
                # 3. 合成视频
                logger.info("合成视频...")
                video_data = await self._frames_to_video(frames, audio_data)
                
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
            # 添加WAV头
            headinfo = self._generate_wav_header(16000, 16, len(audio_data))
            audio_with_header = headinfo + audio_data
            
            # 读取音频
            audio_array, sr = sf.read(BytesIO(audio_with_header))
            
            # 提取Paraformer特征
            frame_cnt = int(len(audio_array) / 16000 * 30)
            au_data = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._extract_paraformer_feature,
                audio_array,
                frame_cnt
            )
            
            # 预测口型参数
            ph_data = np.zeros((au_data.shape[0], 2))
            param_res = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._inference_mouth_params,
                au_data,
                ph_data
            )
            
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
        """参数转视频帧"""
        logger.debug(f"开始渲染 {len(param_res)} 个参数帧")
        
        # 清空队列
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                break
        
        # 提交渲染任务
        for ii, params in enumerate(param_res):
            # 计算背景帧ID（循环播放）
            if int(ii / self.bg_video_frame_count) % 2 == 0:
                bg_frame_id = ii % self.bg_video_frame_count
            else:
                bg_frame_id = self.bg_video_frame_count - 1 - ii % self.bg_video_frame_count
            
            self.input_queue.put((params, bg_frame_id, ii))
        
        logger.debug(f"已提交 {len(param_res)} 个渲染任务到队列")
        
        # 等待渲染完成
        frames = []
        for i in range(len(param_res)):
            try:
                frame_data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.output_queue.get
                )
                frames.append(frame_data)
                if (i + 1) % 10 == 0:
                    logger.debug(f"已接收 {i + 1}/{len(param_res)} 帧")
            except Exception as e:
                logger.error(f"等待渲染帧 {i} 失败: {e}")
                raise
        
        logger.debug(f"所有 {len(frames)} 帧渲染完成，开始排序")
        
        # 按帧ID排序
        frames.sort(key=lambda x: x[0])
        return [f[1] for f in frames]
    
    def _render_loop(self, thread_id: int, barrier: threading.Barrier,
                    in_queue: queue.Queue, out_queue: queue.Queue):
        """渲染循环（在独立线程中运行）"""
        logger.debug(f"渲染线程 {thread_id} 已启动")
        
        while True:
            try:
                data = in_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            if data is None:
                logger.debug(f"渲染线程 {thread_id} 收到终止信号")
                break
            
            try:
                params, bg_frame_id, global_frame_id = data
                
                # 参数转图像
                mouth_img = self._param_to_image(params, bg_frame_id)
                
                # 融合到背景
                full_img, _ = self._merge_mouth_to_bg(mouth_img, bg_frame_id)
                
                out_queue.put((global_frame_id, full_img))
                
            except Exception as e:
                logger.error(f"渲染线程 {thread_id} 渲染帧 {global_frame_id} 失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 放入一个空帧，避免卡住
                out_queue.put((global_frame_id, np.zeros((512, 512, 3), dtype=np.uint8)))
    
    def _param_to_image(self, params: Dict[str, float], bg_frame_id: int) -> torch.Tensor:
        """参数转嘴部图像"""
        param_val = np.array([params[key] for key in self.p_list])
        
        with torch.no_grad():
            output = self.generator(
                self.ref_img_list[bg_frame_id],
                torch.from_numpy(param_val).unsqueeze(0).float().to(self.device)
            )
        
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
        """帧序列合成视频"""
        try:
            import subprocess
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_video:
                video_path = tmp_video.name
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
                # 写入音频
                headinfo = self._generate_wav_header(16000, 16, len(audio_data))
                tmp_audio.write(headinfo + audio_data)
                audio_path = tmp_audio.name
            
            # 使用OpenCV写入视频
            height, width = frames[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_video_no_audio:
                video_no_audio_path = tmp_video_no_audio.name
            
            out = cv2.VideoWriter(video_no_audio_path, fourcc, self.fps, (width, height))
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
                '-shortest',
                '-movflags', 'frag_keyframe+empty_moov',
                '-loglevel', 'error',
                video_path
            ]
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True)
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg错误: {result.stderr.decode()}")
                raise RuntimeError("视频合成失败")
            
            # 读取视频数据
            with open(video_path, 'rb') as f:
                video_data = f.read()
            
            # 清理临时文件
            Path(video_path).unlink(missing_ok=True)
            Path(audio_path).unlink(missing_ok=True)
            Path(video_no_audio_path).unlink(missing_ok=True)
            
            return video_data
            
        except Exception as e:
            logger.error(f"视频合成失败: {e}")
            raise
    
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
