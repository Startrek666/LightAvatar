"""
Session management with memory control and lifecycle management
"""
import asyncio
import gc
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import psutil
from loguru import logger

from backend.handlers.vad.silero_vad_handler import SileroVADHandler
from backend.handlers.asr.whisper_handler import WhisperHandler
from backend.handlers.asr.skynet_whisper_handler import SkynetWhisperHandler
from backend.handlers.llm.openai_handler import OpenAIHandler
from backend.handlers.tts.edge_tts_handler import EdgeTTSHandler
from backend.handlers.avatar.wav2lip_handler import Wav2LipHandler
from backend.handlers.avatar.lite_avatar_handler import LiteAvatarHandler
from backend.handlers.search.web_search_handler import WebSearchHandler
from backend.app.config import settings
from backend.app.ws_manager import WebSocketManager
from backend.utils.text_utils import clean_markdown_for_tts


@dataclass
class Session:
    """Represents a user session"""
    session_id: str
    user_id: Optional[int] = None  # 用户ID，用于限制一个用户只能有一个会话
    username: Optional[str] = None  # 用户名，用于日志
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    
    # Handlers
    vad_handler: Optional[SileroVADHandler] = None
    asr_handler: Optional[WhisperHandler] = None
    llm_handler: Optional[OpenAIHandler] = None
    tts_handler: Optional[EdgeTTSHandler] = None
    avatar_handler: Optional[Wav2LipHandler] = None
    search_handler: Optional[WebSearchHandler] = None
    
    # Session state
    conversation_history: List[dict] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    is_processing: bool = False
    is_connected: bool = True  # WebSocket连接状态
    disconnected_at: Optional[datetime] = None  # 断开时间
    
    # Buffers
    audio_buffer: List[bytes] = field(default_factory=list)
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_active = datetime.now()
    
    async def initialize_handlers(self):
        """Initialize all handlers"""
        try:
            self.vad_handler = SileroVADHandler()
            await self.vad_handler.initialize()
            
            # 根据配置选择 ASR Handler
            asr_backend = settings.ASR_BACKEND.lower()
            if asr_backend == "skynet":
                logger.info(f"Using Skynet Whisper API for session {self.session_id}")
                self.asr_handler = SkynetWhisperHandler(
                    server_url=settings.SKYNET_WHISPER_URL,
                    participant_id=settings.SKYNET_WHISPER_PARTICIPANT_ID,
                    language=settings.ASR_LANGUAGE
                )
            else:
                logger.info(f"Using Faster-Whisper (local) for session {self.session_id}")
                self.asr_handler = WhisperHandler(
                    model_size=settings.WHISPER_MODEL,
                    device=settings.WHISPER_DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE
                )
            await self.asr_handler.initialize()
            
            self.llm_handler = OpenAIHandler(
                api_url=settings.LLM_API_URL,
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL_NAME
            )
            await self.llm_handler.initialize()
            
            self.tts_handler = EdgeTTSHandler(
                voice=settings.TTS_VOICE,
                rate=settings.TTS_RATE,
                pitch=settings.TTS_PITCH
            )
            await self.tts_handler.initialize()
            
            # 根据配置选择 Avatar Handler
            avatar_engine = settings.AVATAR_ENGINE.lower()
            if avatar_engine == "lite":
                logger.info(f"Using LiteAvatar engine for session {self.session_id}")
                self.avatar_handler = LiteAvatarHandler(
                    fps=settings.AVATAR_FPS,
                    resolution=settings.AVATAR_RESOLUTION,
                    config={
                        "avatar_name": settings.AVATAR_NAME,
                        "use_gpu": settings.AVATAR_USE_GPU,
                        "render_threads": settings.AVATAR_RENDER_THREADS,
                        "bg_frame_count": settings.AVATAR_BG_FRAME_COUNT,
                        "cpu_threads": settings.CPU_THREADS
                    }
                )
            else:
                logger.info(f"Using Wav2Lip engine for session {self.session_id}")
                self.avatar_handler = Wav2LipHandler(
                    fps=settings.AVATAR_FPS,
                    resolution=settings.AVATAR_RESOLUTION,
                    config={
                        "use_onnx": settings.AVATAR_USE_ONNX,
                        "static_mode": settings.AVATAR_STATIC_MODE,
                        "enhance_mode": settings.AVATAR_ENHANCE_MODE,
                        "cpu_threads": settings.CPU_THREADS
                    }
                )
            await self.avatar_handler.initialize()
            
            # 初始化搜索处理器（如果启用）
            if settings.SEARCH_ENABLED:
                logger.info(f"Initializing search handler for session {self.session_id}")
                self.search_handler = WebSearchHandler(
                    config={
                        "max_results": settings.SEARCH_MAX_RESULTS,
                        "fetch_content": settings.SEARCH_FETCH_CONTENT,
                        "content_max_length": settings.SEARCH_CONTENT_MAX_LENGTH
                    }
                )
                await self.search_handler.initialize()
            
            logger.info(f"Session {self.session_id} handlers initialized (ASR: {asr_backend}, Avatar: {avatar_engine})")
        except Exception as e:
            logger.error(f"Failed to initialize handlers for session {self.session_id}: {e}")
            raise
    
    async def process_audio(self, audio_data: bytes):
        """Process incoming audio data"""
        self.update_activity()
        
        # 转换列表为字节对象（前端发送的是数组）
        if isinstance(audio_data, list):
            audio_data = bytes(audio_data)
            logger.debug(f"[音频] Session {self.session_id}: 收到音频数组，已转换为字节，大小: {len(audio_data)} 字节")
        elif not isinstance(audio_data, bytes):
            logger.warning(f"[音频] Session {self.session_id}: 未知音频数据类型: {type(audio_data)}")
            return
        else:
            logger.debug(f"[音频] Session {self.session_id}: 收到音频字节，大小: {len(audio_data)} 字节")
        
        # Add to buffer
        self.audio_buffer.append(audio_data)
        buffer_size = sum(len(chunk) for chunk in self.audio_buffer)
        logger.debug(f"[音频] Session {self.session_id}: 缓冲区大小: {buffer_size} 字节 ({len(self.audio_buffer)} 块)")
        
        # ✅ 禁用VAD自动触发，只在用户点击停止录音时才处理
        # 避免录音还没结束就开始识别
        # Check VAD
        # if self.vad_handler:
        #     is_speech = await self.vad_handler.detect(audio_data)
        #     logger.debug(f"[VAD] Session {self.session_id}: 语音检测结果: {'检测到语音' if is_speech else '无语音'}")
        #     if is_speech and not self.is_processing:
        #         logger.info(f"[语音识别] Session {self.session_id}: 开始处理语音...")
        #         self.is_processing = True
        #         asyncio.create_task(self._process_speech())
    
    async def finish_audio_recording(self, callback=None):
        """Force process remaining audio when recording ends
        
        Args:
            callback: Optional callback function to send results
        """
        self.update_activity()
        
        buffer_size = sum(len(chunk) for chunk in self.audio_buffer)
        logger.info(f"[录音结束] Session {self.session_id}: 收到录音结束信号，缓冲区: {buffer_size} 字节")
        
        # 如果有缓冲的音频且不在处理中，强制处理
        if self.audio_buffer and not self.is_processing:
            logger.info(f"[语音识别] Session {self.session_id}: 强制处理缓冲的音频...")
            self.is_processing = True
            await self._process_speech(callback=callback)
        elif self.is_processing:
            logger.info(f"[语音识别] Session {self.session_id}: 已在处理中，跳过")
        else:
            logger.warning(f"[录音结束] Session {self.session_id}: 缓冲区为空，无音频可处理")
            # ✅ 即使缓冲区为空也要通知前端
            if callback:
                await callback("asr_result", {
                    "text": "",
                    "success": False,
                    "message": "未收到音频数据"
                })
        
        # 重置VAD状态
        if self.vad_handler:
            self.vad_handler.reset()
            logger.debug(f"[VAD] Session {self.session_id}: VAD状态已重置")
        
        logger.info(f"[录音结束] Session {self.session_id}: 录音处理完成")
    
    async def _process_speech(self, callback=None):
        """Process accumulated speech
        
        Args:
            callback: Optional callback function to send results
        """
        try:
            # Combine audio buffer
            audio = b''.join(self.audio_buffer)
            self.audio_buffer.clear()
            logger.info(f"[ASR] Session {self.session_id}: 开始语音识别，音频大小: {len(audio)} 字节")
            
            # ASR
            text = await self.asr_handler.transcribe(audio)
            
            if not text:
                logger.warning(f"[ASR] Session {self.session_id}: 识别结果为空")
                self.is_processing = False
                
                # ✅ 关键修复：即使识别为空也要通知前端
                if callback:
                    await callback("asr_result", {
                        "text": "",
                        "success": False,
                        "message": "未检测到语音内容，请重试"
                    })
                return
            
            logger.info(f"[ASR] Session {self.session_id}: 识别成功，文本: {text}")
            
            # ✅ 只发送识别结果给前端，不自动调用LLM
            # 让前端填充到输入框，由用户决定是否发送
            if callback:
                await callback("asr_result", {
                    "text": text,
                    "success": True
                })
                logger.info(f"[ASR] Session {self.session_id}: 已将识别结果发送给前端")
            
            # ✅ 不再自动调用LLM，由用户确认后通过文本消息发送
            # 以下代码已移除：
            # - Add to conversation history
            # - LLM generation
            # - TTS
            # - Avatar generation
            
        except Exception as e:
            logger.error(f"Error processing speech in session {self.session_id}: {e}")
        finally:
            self.is_processing = False
    
    async def process_text(self, text: str) -> dict:
        """Process text input directly (non-streaming mode)"""
        self.update_activity()
        
        try:
            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": text,
                "timestamp": datetime.now().isoformat()
            })
            
            # LLM
            response = await self.llm_handler.generate_response(
                text,
                self.conversation_history
            )
            
            # Add response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat()
            })
            
            # TTS
            audio_output = await self.tts_handler.synthesize(response)
            
            # Avatar generation
            video_output = await self.avatar_handler.generate(
                audio_output,
                self.config.get("avatar_template", settings.AVATAR_TEMPLATE)
            )
            
            return {
                "text": response,
                "audio": audio_output,
                "video": video_output
            }
            
        except Exception as e:
            logger.error(f"Error processing text in session {self.session_id}: {e}")
            raise
    
    async def process_text_stream(self, text: str, callback, use_search: bool = False):
        """
        Process text input with streaming response
        
        Args:
            text: User input text
            callback: Async callback function to send chunks to client
                     Signature: async def callback(chunk_type, data)
            use_search: Whether to perform web search before generating response
        """
        self.update_activity()
        logger.info(f"[Session {self.session_id}] process_text_stream 开始处理")
        logger.info(f"  - 输入文本长度: {len(text)}")
        logger.info(f"  - 输入文本预览: {text[:100]}")
        logger.info(f"  - 联网搜索: {use_search}")
        
        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": text,
                "timestamp": datetime.now().isoformat()
            })
            
            # Send user message confirmation
            await callback("user_message", {"text": text})
            
            # Stream LLM response with real-time sentence processing
            full_response = ""
            sentence_buffer = ""
            
            # 实时句子处理队列
            sentence_queue = asyncio.Queue()
            processing_task = None
            
            # 启动句子处理任务
            async def process_sentence_queue():
                """后台处理句子队列 - 真正的异步非阻塞"""
                sentence_index = 0
                pending_tasks = {}  # {index: task}
                next_to_send = 0
                next_to_start = 0
                MAX_CONCURRENT = settings.MAX_CONCURRENT_VIDEOS
                input_done = False
                logger.info(f"[实时] 句子处理队列启动，最大并发数: {MAX_CONCURRENT}")
                
                async def send_completed_tasks():
                    """异步发送已完成的任务，实现预缓冲策略"""
                    nonlocal next_to_send
                    
                    # 预缓冲策略：等待前N个视频完成后才开始发送
                    PREBUFFER_COUNT = settings.PREBUFFER_COUNT
                    
                    while next_to_send in pending_tasks:
                        task = pending_tasks[next_to_send]
                        
                        # 关键：只处理已完成的任务，未完成的直接跳过
                        if not task.done():
                            break  # 等待这个任务，不跳过后面的
                        
                        # 预缓冲检查：如果是前几个视频，检查是否已经有足够的缓冲
                        if next_to_send < PREBUFFER_COUNT:
                            # 检查后续视频的完成情况（只计算成功的）
                            buffered_count = 0
                            for i in range(next_to_send, min(next_to_send + PREBUFFER_COUNT, sentence_index)):
                                if i in pending_tasks and pending_tasks[i].done():
                                    # 检查任务是否成功（不是None）
                                    try:
                                        result_preview = pending_tasks[i].result()
                                        if result_preview is not None:
                                            buffered_count += 1
                                    except Exception:
                                        # 任务失败，不计入缓冲
                                        pass
                                elif i in pending_tasks:
                                    # 有未完成的任务，继续等待
                                    break
                            
                            # 如果缓冲不足，检查是否应该发送
                            if buffered_count < PREBUFFER_COUNT and next_to_send == 0:
                                # 特殊情况：如果LLM已完成且所有视频都已生成，直接发送
                                if input_done and next_to_start >= sentence_index:
                                    logger.info(f"[实时] LLM输出完成，立即发送已有的 {buffered_count} 个视频（无需等待预缓冲）")
                                else:
                                    logger.debug(f"[实时] 预缓冲中: {buffered_count}/{PREBUFFER_COUNT} 个成功视频（跳过失败任务）")
                                    break
                        
                        try:
                            result = await task  # 已完成，立即返回
                            del pending_tasks[next_to_send]
                            
                            if result:
                                # ⚡ 关键修复：检查连接状态，断开时等待重连
                                if not self.is_connected:
                                    logger.warning(f"⏸️ 连接断开，暂停发送句子 {next_to_send + 1}，等待重连...")
                                    wait_count = 0
                                    MAX_WAIT = 30  # 最多等待30秒（6次 × 10秒）
                                    
                                    while not self.is_connected and wait_count < MAX_WAIT:
                                        await asyncio.sleep(10)
                                        wait_count += 10
                                        if self.is_connected:
                                            logger.info(f"✅ 重连成功，继续发送句子 {next_to_send + 1}")
                                            break
                                    
                                    if not self.is_connected:
                                        logger.error(f"❌ 等待 {MAX_WAIT}秒 后仍未重连，丢弃句子 {next_to_send + 1}")
                                        next_to_send += 1
                                        continue
                                
                                # 发送视频
                                await callback("video_chunk", result)
                                self.update_activity()
                                if next_to_send == 0:
                                    # 计算实际预缓冲的视频数量
                                    actual_buffered = sum(1 for i in range(sentence_index) if i in pending_tasks and pending_tasks[i].done())
                                    logger.info(f"[实时] 句子 1 开始播放（已预缓冲 {actual_buffered} 个视频）: {len(result['video'])} bytes")
                                else:
                                    logger.info(f"[实时] 句子 {next_to_send + 1} 已发送: {len(result['video'])} bytes")
                            
                            next_to_send += 1
                        except Exception as e:
                            logger.error(f"[实时] 发送句子 {next_to_send + 1} 失败: {e}")
                            del pending_tasks[next_to_send]
                            next_to_send += 1
                
                pending_sentence = None  # 暂存等待处理的句子
                
                while True:
                    # 如果有等待的句子，优先处理它
                    if pending_sentence is None:
                        # 从队列获取句子（非阻塞）
                        try:
                            sentence = await asyncio.wait_for(sentence_queue.get(), timeout=0.1)
                        except asyncio.TimeoutError:
                            # 队列暂时为空，检查是否有已完成的任务可以发送
                            if pending_tasks:
                                await send_completed_tasks()
                            continue
                        
                        if sentence is None:  # 结束信号
                            input_done = True
                            break
                    else:
                        sentence = pending_sentence
                        pending_sentence = None
                    
                    # 启动生成任务（如果还有并发槽位）
                    slots_available = MAX_CONCURRENT - (next_to_start - next_to_send)
                    if slots_available > 0:
                        task = asyncio.create_task(self._generate_sentence_data(sentence))
                        pending_tasks[sentence_index] = task
                        logger.info(
                            f"[实时] 启动句子 {sentence_index + 1} 生成: {sentence[:30]}... "
                            f"(活跃任务: {len(pending_tasks)}, 已发送: {next_to_send}, 已启动: {next_to_start + 1})"
                        )
                        next_to_start = sentence_index + 1
                        sentence_index += 1
                    else:
                        # 并发已满，暂存这个句子，等待槽位释放
                        logger.debug(
                            f"[实时] 并发已满 (MAX={MAX_CONCURRENT})，句子 {sentence_index + 1} 等待槽位 "
                            f"(活跃: {len(pending_tasks)})"
                        )
                        pending_sentence = sentence
                        # 等待一小段时间，让已完成的任务有机会被发送
                        await asyncio.sleep(0.05)
                    
                    # 异步发送已完成的任务（不阻塞）
                    await send_completed_tasks()
                
                # 处理剩余任务
                logger.info(f"[实时] LLM输入完成，等待 {len(pending_tasks)} 个待处理任务...")
                while next_to_send < sentence_index:
                    await send_completed_tasks()
                    if next_to_send < sentence_index:
                        # 还有任务未完成，等待一下
                        await asyncio.sleep(0.1)
            
            processing_task = asyncio.create_task(process_sentence_queue())
            
            # 流式接收LLM输出
            chunk_received = 0
            logger.info(f"[Session {self.session_id}] 开始调用 LLM stream_response (use_search={use_search})")
            
            # 搜索进度回调
            async def search_progress_callback(step: int, total: int, message: str):
                await callback("search_progress", {
                    "step": step,
                    "total": total,
                    "message": message
                })
            
            # 根据是否启用搜索选择调用方式
            if use_search and self.search_handler:
                stream = self.llm_handler.stream_response_with_search(
                    text, 
                    self.conversation_history,
                    search_handler=self.search_handler,
                    use_search=True,
                    progress_callback=search_progress_callback
                )
            else:
                stream = self.llm_handler.stream_response(text, self.conversation_history)
            
            async for chunk in stream:
                chunk_received += 1
                full_response += chunk
                sentence_buffer += chunk
                
                # Send text chunk to client for real-time display
                await callback("text_chunk", {"chunk": chunk})
                self.update_activity()
                
                if chunk_received == 1:
                    logger.info(f"[Session {self.session_id}] 收到第一个LLM chunk: '{chunk}'")
                
                # Check if we have a complete sentence
                if self._is_sentence_end(sentence_buffer):
                    # 立即将句子加入处理队列（清理Markdown格式和emoji）
                    clean_sentence = sentence_buffer.strip()
                    if clean_sentence:
                        # 清理Markdown格式和emoji（去除**、*、😊等符号）
                        clean_sentence = clean_markdown_for_tts(clean_sentence)
                        # 清理后再次检查是否为空（例如纯emoji句子清理后会变成空字符串）
                        if clean_sentence.strip():
                            await sentence_queue.put(clean_sentence)
                            logger.info(f"[实时] 句子入队: {clean_sentence[:30]}...")
                        else:
                            logger.info(f"[实时] 跳过空句子（清理后为空）: 原文='{sentence_buffer[:30]}...'")
                    sentence_buffer = ""
            
            # Collect any remaining text
            logger.info(f"[实时] Stream结束，收到 {chunk_received} 个chunks，完整响应长度: {len(full_response)}")
            logger.info(f"[实时] 剩余buffer内容: '{sentence_buffer[:100]}...'")
            
            if sentence_buffer.strip():
                clean_sentence = clean_markdown_for_tts(sentence_buffer.strip())
                logger.info(f"[实时] 清理后的剩余文字: '{clean_sentence[:100]}...'")
                # 清理后再次检查是否为空
                if clean_sentence.strip():
                    await sentence_queue.put(clean_sentence)
                    logger.info(f"[实时] 剩余文字入队: {clean_sentence[:30]}...")
                else:
                    logger.info(f"[实时] 跳过空句子（清理后为空）: 原文='{sentence_buffer[:50]}...'")
            
            # 发送结束信号
            await sentence_queue.put(None)
            
            # 等待所有句子处理完成
            if processing_task:
                await processing_task
            
            # Add complete response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response,
                "timestamp": datetime.now().isoformat()
            })
            
            # Trim history if needed
            max_history = settings.LLM_MAX_HISTORY
            if len(self.conversation_history) > max_history * 2:
                # Keep system message + recent messages
                self.conversation_history = self.conversation_history[-max_history * 2:]
            
            # Send completion signal
            await callback("stream_complete", {"full_text": full_response})
            
        except Exception as e:
            logger.error(f"Error in streaming text processing: {e}")
            await callback("error", {"message": str(e)})
    
    async def _process_sentences_with_preload(self, sentences: list, callback):
        """
        并行预加载处理多个句子
        
        策略：在播放第N句时，后台并行生成第N+1句，实现流水线处理
        """
        if not sentences:
            return
        
        # 第一句立即处理
        if len(sentences) == 1:
            await self._process_sentence(sentences[0], callback)
            return
        
        # 多句处理：限制并发数（从配置读取）
        # 策略：使用滑动窗口，最多同时生成N个视频
        MAX_CONCURRENT = settings.MAX_CONCURRENT_VIDEOS
        pending_tasks = {}  # {index: task}
        next_to_send = 0  # 下一个要发送的句子索引
        next_to_start = 0  # 下一个要启动的句子索引
        
        # 初始启动前2个任务
        while next_to_start < len(sentences) and next_to_start < MAX_CONCURRENT:
            task = asyncio.create_task(self._generate_sentence_data(sentences[next_to_start]))
            pending_tasks[next_to_start] = task
            logger.debug(f"Started generating sentence {next_to_start + 1}: {sentences[next_to_start][:30]}...")
            next_to_start += 1
        
        # 循环：等待、发送、启动新任务
        while next_to_send < len(sentences):
            # 等待当前要发送的任务完成
            if next_to_send in pending_tasks:
                result = await pending_tasks[next_to_send]
                del pending_tasks[next_to_send]
                
                if result:
                    await callback("video_chunk", result)
                    logger.info(f"Sentence {next_to_send + 1}/{len(sentences)} processed: {len(result['video'])} bytes video - '{result['text'][:30]}...'")
                
                next_to_send += 1
                
                # 启动新任务（如果还有）
                if next_to_start < len(sentences):
                    task = asyncio.create_task(self._generate_sentence_data(sentences[next_to_start]))
                    pending_tasks[next_to_start] = task
                    logger.debug(f"Started generating sentence {next_to_start + 1}: {sentences[next_to_start][:30]}...")
                    next_to_start += 1
            else:
                # 任务不存在，跳过
                next_to_send += 1
    
    async def _generate_sentence_data(self, sentence: str) -> dict:
        """
        生成句子的视频数据（不发送），用于预加载
        
        Returns:
            dict with 'video', 'audio', 'text' or None if failed
        """
        try:
            logger.info(f"Preloading sentence: {sentence[:50]}...")
            
            # TTS synthesis
            audio_bytes = await self.tts_handler.synthesize(sentence)
            if not audio_bytes:
                logger.warning(f"TTS returned empty audio for: {sentence[:30]}...")
                return None
            
            # Avatar generation
            video_bytes = await self.avatar_handler.generate(
                audio_bytes,
                self.config.get("avatar_template", settings.AVATAR_TEMPLATE)
            )
            if not video_bytes:
                logger.warning(f"Avatar generation returned empty video for: {sentence[:30]}...")
                return None
            
            return {
                "video": video_bytes,
                "audio": audio_bytes,
                "text": sentence
            }
        except Exception as e:
            logger.error(f"Error preloading sentence '{sentence[:30]}...': {e}")
            return None
    
    def _is_sentence_end(self, text: str, min_length: int = 10, max_length: int = 20) -> bool:
        """
        智能判断是否应该分割句子
        
        策略：
        0. 长度 < 5字：绝对不分割（避免"你好！"这种极短句）
        1. 长度 5-10字：遇到强标点分割
        2. 长度 > max_length 且有逗号：在逗号处分割
        3. 中等长度：遇到句号等强标点分割
        
        Args:
            text: 当前累积的文本
            min_length: 最小分割长度（字符数）
            max_length: 最大分割长度（字符数）
        """
        if not text:
            return False
        
        text = text.rstrip()
        text_len = len(text)
        
        # 强制分割标点（句号、问号、感叹号）
        strong_delimiters = ['。', '！', '？', '.', '!', '?', '\n']
        
        # 检测标点（包括引号内的标点）
        # 例如："你好！" 或 「你好！」
        quote_pairs = ['"', '"', '」', "'", '"']
        has_strong_delimiter = any(text.endswith(d) for d in strong_delimiters)
        
        # 如果结尾是引号，检查引号前的字符
        if not has_strong_delimiter and len(text) >= 2:
            if text[-1] in quote_pairs:
                has_strong_delimiter = any(text[-2] == d for d in strong_delimiters)
        
        # 弱分割标点（逗号、分号）
        weak_delimiters = ['，', '；', ',', ';']
        has_weak_delimiter = any(text.endswith(d) for d in weak_delimiters)
        
        # 引号内的逗号
        if not has_weak_delimiter and len(text) >= 2:
            if text[-1] in quote_pairs:
                has_weak_delimiter = any(text[-2] == d for d in weak_delimiters)
        
        # 策略0：绝对最小长度（避免极短句如"你好！"被分割）
        ABSOLUTE_MIN = 5
        if text_len < ABSOLUTE_MIN:
            return False  # 无论有无标点，都不分割
        
        # 策略1：短句（5-10字）遇到强标点分割
        if text_len < min_length:
            return has_strong_delimiter
        
        # 策略2：超长强制分割（在逗号或任意标点处）
        if text_len > max_length:
            return has_weak_delimiter or has_strong_delimiter
        
        # 策略3：中等长度，遇到强标点就分割
        return has_strong_delimiter
    
    async def _process_sentence(self, sentence: str, callback):
        """
        Process a single sentence - TTS + Avatar generation
        
        Args:
            sentence: The sentence to process
            callback: Callback to send results
        """
        try:
            logger.info(f"Processing sentence: {sentence[:50]}...")
            
            # TTS synthesis
            audio_bytes = await self.tts_handler.synthesize(sentence)
            
            if not audio_bytes:
                logger.warning(f"TTS returned empty audio for: {sentence[:30]}...")
                return
            
            logger.debug(f"TTS完成，音频大小: {len(audio_bytes)} bytes")
            
            # Avatar generation
            video_bytes = await self.avatar_handler.generate(
                audio_bytes,
                self.config.get("avatar_template", settings.AVATAR_TEMPLATE)
            )
            
            if not video_bytes:
                logger.warning(f"Avatar generation returned empty video for: {sentence[:30]}...")
                return
            
            logger.debug(f"视频生成完成，大小: {len(video_bytes)} bytes")
            
            # Send video chunk to client
            await callback("video_chunk", {
                "video": video_bytes,
                "audio": audio_bytes,
                "text": sentence
            })
            
            logger.info(f"Sentence processed: {len(video_bytes)} bytes video - '{sentence[:30]}...'")
            
        except Exception as e:
            logger.error(f"Error processing sentence '{sentence[:30]}...': {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't fail the whole stream, just log the error
    
    async def update_config(self, config: dict):
        """Update session configuration"""
        self.config.update(config)
        
        # Update handler configurations
        if "llm" in config:
            # 如果模型选择改变，需要重新创建LLM handler
            if "model" in config["llm"]:
                settings.LLM_MODEL = config["llm"]["model"]
                logger.info(f"Switching LLM model to: {settings.LLM_MODEL}")
                
                # 重新创建LLM handler
                self.llm_handler = OpenAIHandler(
                    api_url=settings.LLM_API_URL,
                    api_key=settings.LLM_API_KEY,
                    model=settings.LLM_MODEL_NAME
                )
                await self.llm_handler.initialize()
            elif self.llm_handler:
                self.llm_handler.update_config(config["llm"])
        
        if "tts" in config and self.tts_handler:
            self.tts_handler.update_config(config["tts"])
        
        if "avatar" in config and self.avatar_handler:
            self.avatar_handler.update_config(config["avatar"])
    
    def release(self):
        """Release session resources"""
        # Clear handlers
        self.vad_handler = None
        self.asr_handler = None
        self.llm_handler = None
        self.tts_handler = None
        self.avatar_handler = None
        
        # Clear buffers
        self.audio_buffer.clear()
        self.conversation_history.clear()
        
        # Force garbage collection
        gc.collect()
        
        logger.info(f"Session {self.session_id} resources released")


class SessionManager:
    """Manages all active sessions with memory control"""
    
    def __init__(self, max_memory_mb: int = 4096, websocket_manager: Optional[WebSocketManager] = None):
        self.sessions: Dict[str, Session] = {}
        self.user_sessions: Dict[int, str] = {}  # 用户ID -> session_id的映射，用于限制一个用户只能有一个活跃会话
        self.max_memory_mb = max_memory_mb
        self._lock = asyncio.Lock()
        self.websocket_manager = websocket_manager
    
    async def create_session(self, session_id: str, user_id: Optional[int] = None, username: Optional[str] = None) -> Session:
        """Create or reconnect to a session
        
        Args:
            session_id: The session ID
            user_id: The user ID (for enforcing single session per user)
            username: The username (for logging)
            
        Returns:
            Session object
            
        Raises:
            ValueError: If user already has an active session
        """
        async with self._lock:
            # 检查是否有已存在的Session（支持重连）
            if session_id in self.sessions:
                existing_session = self.sessions[session_id]
                
                # 如果是断开状态，恢复连接
                if not existing_session.is_connected:
                    existing_session.is_connected = True
                    existing_session.disconnected_at = None
                    existing_session.update_activity()
                    logger.info(f"⚡ Session {session_id} 重连成功，继续使用原Session")
                else:
                    logger.info(f"Session {session_id} 已存在且在线")
                
                return existing_session
            
            # 检查该用户是否已有活跃会话
            if user_id is not None:
                existing_session_id = self.user_sessions.get(user_id)
                if existing_session_id and existing_session_id in self.sessions:
                    existing_session = self.sessions[existing_session_id]
                    # 只有在线的会话才算作冲突
                    if existing_session.is_connected:
                        logger.warning(
                            f"❌ 用户 {username or user_id} 已有活跃会话 {existing_session_id}，"
                            f"拒绝创建新会话 {session_id}"
                        )
                        raise ValueError(
                            f"您已有一个正在使用的会话，请先退出当前会话再重试。"
                            f"（会话ID: {existing_session_id[:8]}...）"
                        )
                    else:
                        # 旧会话已断开，可以清理
                        logger.info(f"清理用户 {username or user_id} 的旧断开会话 {existing_session_id}")
                        await self._remove_session_internal(existing_session_id)
            
            # Check memory before creating new session
            await self.check_memory()
            
            # Check max sessions limit
            if len(self.sessions) >= settings.MAX_SESSIONS:
                # Remove oldest inactive session
                await self._remove_oldest_inactive()
            
            # Create new session
            session = Session(
                session_id=session_id,
                user_id=user_id,
                username=username
            )
            await session.initialize_handlers()
            
            self.sessions[session_id] = session
            
            # 记录用户到会话的映射
            if user_id is not None:
                self.user_sessions[user_id] = session_id
            
            logger.info(
                f"✅ 创建会话 {session_id}"
                + (f" (用户: {username or user_id})" if user_id else "")
            )
            
            return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get an existing session"""
        return self.sessions.get(session_id)
    
    async def disconnect_session(self, session_id: str):
        """标记Session为断开状态（不删除，支持重连）"""
        async with self._lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.is_connected = False
                session.disconnected_at = datetime.now()
                logger.info(f"🔌 Session {session_id} 断开连接，保留Session数据等待重连")
    
    async def _remove_session_internal(self, session_id: str):
        """内部方法：删除Session（不加锁，由调用者负责加锁）"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            
            # 清理用户映射
            if session.user_id is not None and self.user_sessions.get(session.user_id) == session_id:
                del self.user_sessions[session.user_id]
                logger.debug(f"清理用户 {session.username or session.user_id} 的会话映射")
            
            session.release()
            del self.sessions[session_id]
            logger.info(f"🗑️ 已删除 Session {session_id}")
    
    async def remove_session(self, session_id: str):
        """彻底删除Session（用于清理长时间未重连的Session）"""
        async with self._lock:
            await self._remove_session_internal(session_id)
    
    async def check_memory(self):
        """Check memory usage and cleanup if needed"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        if memory_mb > self.max_memory_mb:
            logger.warning(f"Memory usage ({memory_mb:.2f}MB) exceeds limit ({self.max_memory_mb}MB)")
            await self.cleanup_old_sessions()
            gc.collect()
    
    async def cleanup_old_sessions(self):
        """Clean up sessions that have been inactive or disconnected for too long"""
        current_time = datetime.now()
        to_remove = []
        
        # 断开超时时间：5分钟（允许短时间重连）
        DISCONNECT_TIMEOUT = 300  # 秒
        
        for session_id, session in self.sessions.items():
            should_remove = False
            
            # 情况1：在线但长时间不活跃（超过配置的session_timeout）
            if session.is_connected:
                inactive_time = (current_time - session.last_active).total_seconds()
                if inactive_time > settings.SESSION_TIMEOUT:
                    logger.info(f"Session {session_id} 在线但不活跃 {inactive_time:.0f}秒，标记删除")
                    should_remove = True
            
            # 情况2：断开连接且超过重连等待时间
            elif session.disconnected_at:
                disconnect_time = (current_time - session.disconnected_at).total_seconds()
                if disconnect_time > DISCONNECT_TIMEOUT:
                    logger.info(f"Session {session_id} 断开 {disconnect_time:.0f}秒未重连，标记删除")
                    should_remove = True
            
            if should_remove:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            # 如果WebSocket还连着，通知前端
            if self.websocket_manager and self.websocket_manager.is_connected(session_id):
                try:
                    await self.websocket_manager.send_json(session_id, {
                        "type": "session_timeout",
                        "reason": "inactive",
                        "timeout_seconds": settings.SESSION_TIMEOUT
                    })
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Failed to notify session timeout for {session_id}: {e}")
                finally:
                    self.websocket_manager.disconnect(session_id)
            
            await self.remove_session(session_id)
        
        if to_remove:
            logger.info(f"🧹 清理了 {len(to_remove)} 个过期Session")
    
    async def _remove_oldest_inactive(self):
        """Remove the oldest inactive session"""
        if not self.sessions:
            return
        
        oldest_session = min(
            self.sessions.values(),
            key=lambda s: s.last_active
        )
        
        await self.remove_session(oldest_session.session_id)
    
    async def periodic_cleanup(self):
        """Periodic cleanup task"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.cleanup_old_sessions()
                await self.check_memory()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def cleanup_all(self):
        """Clean up all sessions"""
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.remove_session(session_id)
    
    def get_active_sessions(self) -> List[dict]:
        """Get information about active sessions"""
        return [
            {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "last_active": session.last_active.isoformat(),
                "is_processing": session.is_processing,
                "conversation_length": len(session.conversation_history)
            }
            for session in self.sessions.values()
        ]
    
    def get_total_memory_usage(self) -> float:
        """Get total memory usage in MB"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
