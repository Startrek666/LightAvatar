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
from backend.app.config import settings


@dataclass
class Session:
    """Represents a user session"""
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    
    # Handlers
    vad_handler: Optional[SileroVADHandler] = None
    asr_handler: Optional[WhisperHandler] = None
    llm_handler: Optional[OpenAIHandler] = None
    tts_handler: Optional[EdgeTTSHandler] = None
    avatar_handler: Optional[Wav2LipHandler] = None
    
    # Session state
    conversation_history: List[dict] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    is_processing: bool = False
    
    # Buffers
    audio_buffer: List[bytes] = field(default_factory=list)
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_active = datetime.now()
    
    async def initialize_handlers(self):
        """Initialize all handlers"""
        try:
            self.vad_handler = SileroVADHandler()
            
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
            
            self.llm_handler = OpenAIHandler(
                api_url=settings.LLM_API_URL,
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL
            )
            self.tts_handler = EdgeTTSHandler(
                voice=settings.TTS_VOICE,
                rate=settings.TTS_RATE,
                pitch=settings.TTS_PITCH
            )
            self.avatar_handler = Wav2LipHandler(
                fps=settings.AVATAR_FPS,
                resolution=settings.AVATAR_RESOLUTION
            )
            
            logger.info(f"Session {self.session_id} handlers initialized (ASR: {asr_backend})")
        except Exception as e:
            logger.error(f"Failed to initialize handlers for session {self.session_id}: {e}")
            raise
    
    async def process_audio(self, audio_data: bytes):
        """Process incoming audio data"""
        self.update_activity()
        
        # Add to buffer
        self.audio_buffer.append(audio_data)
        
        # Check VAD
        if self.vad_handler:
            is_speech = await self.vad_handler.detect(audio_data)
            if is_speech and not self.is_processing:
                self.is_processing = True
                asyncio.create_task(self._process_speech())
    
    async def _process_speech(self):
        """Process accumulated speech"""
        try:
            # Combine audio buffer
            audio = b''.join(self.audio_buffer)
            self.audio_buffer.clear()
            
            # ASR
            text = await self.asr_handler.transcribe(audio)
            if not text:
                return
            
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
            video_frames = await self.avatar_handler.generate(
                audio_output,
                self.config.get("avatar_template", settings.AVATAR_TEMPLATE)
            )
            
            # Send results back through WebSocket
            # This will be handled by the WebSocket manager
            
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
    
    async def process_text_stream(self, text: str, callback):
        """
        Process text input with streaming response
        
        Args:
            text: User input text
            callback: Async callback function to send chunks to client
                     Signature: async def callback(chunk_type, data)
        """
        self.update_activity()
        
        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": text,
                "timestamp": datetime.now().isoformat()
            })
            
            # Send user message confirmation
            await callback("user_message", {"text": text})
            
            # Stream LLM response
            full_response = ""
            sentence_buffer = ""
            
            async for chunk in self.llm_handler.stream_response(text, self.conversation_history):
                full_response += chunk
                sentence_buffer += chunk
                
                # Send text chunk to client for real-time display
                await callback("text_chunk", {"chunk": chunk})
                
                # Check if we have a complete sentence
                if self._is_sentence_end(sentence_buffer):
                    # Process this sentence immediately
                    asyncio.create_task(
                        self._process_sentence(sentence_buffer.strip(), callback)
                    )
                    sentence_buffer = ""
            
            # Process any remaining text
            if sentence_buffer.strip():
                asyncio.create_task(
                    self._process_sentence(sentence_buffer.strip(), callback)
                )
            
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
    
    def _is_sentence_end(self, text: str) -> bool:
        """Check if text ends with sentence delimiter"""
        if not text:
            return False
        
        # Chinese and English sentence delimiters
        delimiters = ['。', '！', '？', '.', '!', '?', '；', ';', '\n']
        
        # Check last character
        return any(text.rstrip().endswith(d) for d in delimiters)
    
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
                logger.warning("TTS returned empty audio")
                return
            
            # Avatar generation
            video_bytes = await self.avatar_handler.generate(
                audio_bytes,
                self.config.get("avatar_template", settings.AVATAR_TEMPLATE)
            )
            
            if not video_bytes:
                logger.warning("Avatar generation returned empty video")
                return
            
            # Send video chunk to client
            await callback("video_chunk", {
                "video": video_bytes,
                "audio": audio_bytes,
                "text": sentence
            })
            
            logger.info(f"Sentence processed: {len(video_bytes)} bytes video")
            
        except Exception as e:
            logger.error(f"Error processing sentence '{sentence[:30]}...': {e}")
            # Don't fail the whole stream, just log the error
    
    async def update_config(self, config: dict):
        """Update session configuration"""
        self.config.update(config)
        
        # Update handler configurations
        if "llm" in config and self.llm_handler:
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
    
    def __init__(self, max_memory_mb: int = 4096):
        self.sessions: Dict[str, Session] = {}
        self.max_memory_mb = max_memory_mb
        self._lock = asyncio.Lock()
    
    async def create_session(self, session_id: str) -> Session:
        """Create a new session"""
        async with self._lock:
            # Check memory before creating new session
            await self.check_memory()
            
            # Check max sessions limit
            if len(self.sessions) >= settings.MAX_SESSIONS:
                # Remove oldest inactive session
                await self._remove_oldest_inactive()
            
            # Create new session
            session = Session(session_id=session_id)
            await session.initialize_handlers()
            
            self.sessions[session_id] = session
            logger.info(f"Created session {session_id}")
            
            return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get an existing session"""
        return self.sessions.get(session_id)
    
    async def remove_session(self, session_id: str):
        """Remove a session"""
        async with self._lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.release()
                del self.sessions[session_id]
                logger.info(f"Removed session {session_id}")
    
    async def check_memory(self):
        """Check memory usage and cleanup if needed"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        if memory_mb > self.max_memory_mb:
            logger.warning(f"Memory usage ({memory_mb:.2f}MB) exceeds limit ({self.max_memory_mb}MB)")
            await self.cleanup_old_sessions()
            gc.collect()
    
    async def cleanup_old_sessions(self):
        """Clean up sessions that have been inactive"""
        current_time = time.time()
        to_remove = []
        
        for session_id, session in self.sessions.items():
            inactive_time = current_time - session.last_active.timestamp()
            if inactive_time > settings.SESSION_TIMEOUT:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            await self.remove_session(session_id)
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} inactive sessions")
    
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
