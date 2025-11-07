"""
Lightweight Avatar Chat - Main Application Entry Point
"""
import asyncio
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from typing import Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import uvicorn
import tempfile
import subprocess

from backend.app.ws_manager import WebSocketManager
from backend.app.config import settings
from backend.app.integration_api import router as integration_router
from backend.core.session_manager import SessionManager
from backend.core.health_monitor import HealthMonitor
from backend.utils.logger import setup_logger
from backend.utils.process_monitor import start_process_monitor

# Setup logging
setup_logger()

# Log project root for debugging
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
logger.info(f"Project root directory: {PROJECT_ROOT}")

# Initialize managers
websocket_manager = WebSocketManager()
session_manager = SessionManager(
    max_memory_mb=settings.MAX_MEMORY_MB,
    websocket_manager=websocket_manager
)
health_monitor = HealthMonitor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting Lightweight Avatar Chat...")
    
    # Initialize database
    try:
        from backend.database.models import db_manager
        db_manager.create_tables()
        # Create default admin user
        admin = db_manager.init_admin_user()
        logger.info(f"Database initialized. Default admin: {admin.username}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    # Start health monitor
    health_monitor_task = asyncio.create_task(health_monitor.start())
    
    # Start process monitor (后台任务，监控FFmpeg进程)
    process_monitor_task = asyncio.create_task(start_process_monitor())
    logger.info("Process monitor started")
    
    # Start periodic cleanup
    cleanup_task = asyncio.create_task(session_manager.periodic_cleanup())
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    health_monitor_task.cancel()
    cleanup_task.cancel()
    
    # Cleanup all sessions
    await session_manager.cleanup_all()


# Create FastAPI app
app = FastAPI(
    title="Lightweight Avatar Chat",
    description="CPU-optimized 2D avatar chat system",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(integration_router)

# Import and register auth router
from backend.app.auth_api import router as auth_router
app.include_router(auth_router)

# Import and register docparser router
from backend.app.docparser_api import router as docparser_router
app.include_router(docparser_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Lightweight Avatar Chat",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await health_monitor.get_health_status()


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest
    return generate_latest()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str = None):
    """WebSocket endpoint for real-time communication"""
    
    # 先接受 WebSocket 连接
    await websocket_manager.connect(websocket, session_id)
    
    # 用户信息（用于会话管理）
    user_id = None
    username = None
    
    # 然后验证token和权限
    if token:
        try:
            from backend.database.auth import AuthService
            from backend.database.models import db_manager
            
            auth_service = AuthService()
            db_session = db_manager.get_session()
            
            try:
                user = auth_service.get_current_user(db_session, token)
                if not user:
                    logger.warning(f"WebSocket token无效: {session_id}")
                    await websocket.close(code=1008, reason="未授权: token无效")
                    return
                
                if not user.can_use_avatar:
                    logger.warning(f"用户无数字人权限: {user.username}")
                    await websocket.close(code=1008, reason="无数字人使用权限")
                    return
                
                # 保存用户信息
                user_id = user.id
                username = user.username
                
                logger.info(f"用户 {user.username} (ID: {user.id}) 已连接 WebSocket")
            finally:
                db_session.close()
        except Exception as e:
            logger.error(f"WebSocket认证失败: {e}", exc_info=True)
            await websocket.close(code=1008, reason="认证失败")
            return
    else:
        logger.warning(f"WebSocket连接未提供token: {session_id}")
    
    # Create or get session (with user ID to enforce single session per user)
    # 注意：必须在启动heartbeat之前创建session，这样如果创建失败可以直接返回
    try:
        session = await session_manager.create_session(session_id, user_id=user_id, username=username)
    except ValueError as e:
        # 用户已有活跃会话，拒绝连接
        logger.warning(f"❌ 拒绝创建会话: {e}")
        # 先关闭WebSocket，再清理连接管理器
        try:
            await websocket.close(code=1008, reason=str(e))
        except:
            pass
        websocket_manager.disconnect(session_id)  # 清理WebSocket连接
        return
    
    # Start heartbeat task to detect disconnections
    # 增加心跳间隔避免视频渲染时拥塞
    heartbeat_task = asyncio.create_task(
        websocket_manager.heartbeat(session_id, interval=60)
    )
    
    try:
        
        while True:
            # Receive data from client
            data = await websocket.receive_json()
            
            # Process based on message type
            message_type = data.get("type")
            logger.debug(f"[WebSocket] Session {session_id}: 收到消息类型: {message_type}")
            
            if message_type == "audio":
                # Handle audio stream
                audio_data = data.get("data")
                logger.debug(f"[WebSocket] Session {session_id}: 收到音频数据，长度: {len(audio_data) if audio_data else 0}")
                await session.process_audio(audio_data)
            
            elif message_type == "audio_end":
                # Handle recording end signal
                logger.info(f"[WebSocket] Session {session_id}: 收到录音结束信号")
                
                # ✅ 定义callback来发送ASR结果
                async def asr_callback(msg_type: str, msg_data: dict):
                    """Callback to send ASR results"""
                    if msg_type == "asr_result":
                        await websocket_manager.send_json(session_id, {
                            "type": "asr_result",
                            "data": msg_data
                        })
                        logger.info(f"[WebSocket] Session {session_id}: 已发送ASR结果: {msg_data}")
                
                await session.finish_audio_recording(callback=asr_callback)
                
            elif message_type == "text":
                # Check if streaming is enabled
                use_streaming = data.get("streaming", True)
                use_search = data.get("use_search", False)  # 是否启用联网搜索
                search_mode = data.get("search_mode", "simple")  # 搜索模式: simple/advanced
                search_quality = data.get("search_quality", "speed")  # 搜索质量: speed/quality
                ui_language = data.get("ui_language", "zh")  # 界面语言：zh 或 en
                text_content = data.get("text", "")
                logger.info(f"[WebSocket] Session {session_id}: 收到文本消息")
                logger.info(f"  - streaming: {use_streaming}")
                logger.info(f"  - use_search: {use_search}")
                logger.info(f"  - search_mode: {search_mode}")
                logger.info(f"  - search_quality: {search_quality}")
                logger.info(f"  - ui_language: {ui_language}")
                logger.info(f"  - text length: {len(text_content)}")
                logger.info(f"  - text preview: {text_content[:100]}")
                
                if use_streaming:
                    # Handle text input with streaming
                    async def stream_callback(chunk_type: str, chunk_data: dict):
                        """Callback to send streaming chunks to client"""
                        if chunk_type == "text_chunk":
                            # Send text chunk for real-time display
                            await websocket_manager.send_json(session_id, {
                                "type": "text_chunk",
                                "data": chunk_data
                            })
                        
                        elif chunk_type == "search_progress":
                            # Send search progress update
                            try:
                                await websocket_manager.send_json(session_id, {
                                    "type": "search_progress",
                                    "data": chunk_data
                                })
                            except Exception as e:
                                logger.warning(f"[WebSocket] 发送搜索进度失败（可能已断开）: {e}")
                                # 不抛出异常，避免中断搜索流程
                        
                        elif chunk_type == "search_results":
                            # Send search results (titles and URLs)
                            try:
                                await websocket_manager.send_json(session_id, {
                                    "type": "search_results",
                                    "data": chunk_data
                                })
                            except Exception as e:
                                logger.warning(f"[WebSocket] 发送搜索结果失败（可能已断开）: {e}")
                        
                        elif chunk_type == "video_chunk":
                            # Send video chunk as binary
                            video_bytes = chunk_data.get("video", b"")
                            if video_bytes:
                                # First send metadata
                                await websocket_manager.send_json(session_id, {
                                    "type": "video_chunk_meta",
                                    "data": {
                                        "seq": chunk_data.get("seq", -1),
                                        "text": chunk_data.get("text", ""),
                                        "size": len(video_bytes)
                                    }
                                })
                                # Then send binary video data
                                # 使用 websocket_manager 而不是直接使用 websocket，支持重连后继续发送
                                await websocket_manager.send_bytes(session_id, video_bytes)
                        
                        elif chunk_type == "user_message":
                            # Confirm user message received
                            await websocket_manager.send_json(session_id, {
                                "type": "user_message_ack",
                                "data": chunk_data
                            })
                        
                        elif chunk_type == "stream_complete":
                            # Stream finished
                            await websocket_manager.send_json(session_id, {
                                "type": "stream_complete",
                                "data": chunk_data
                            })
                        
                        elif chunk_type == "error":
                            # Error occurred
                            await websocket_manager.send_json(session_id, {
                                "type": "error",
                                "data": chunk_data
                            })
                    
                    # Process with streaming in background task to keep receiving messages (e.g., interrupt)
                    logger.info(f"[WebSocket] Session {session_id}: 开始流式处理文本（后台任务）")
                    
                    async def process_text_background():
                        """在后台处理文本，避免阻塞WebSocket接收循环"""
                        try:
                            await session.process_text_stream(
                                text_content, 
                                stream_callback,
                                use_search=use_search,
                                search_mode=search_mode,
                                search_quality=search_quality,
                                ui_language=ui_language
                            )
                            logger.info(f"[WebSocket] Session {session_id}: 流式处理完成")
                        except Exception as e:
                            logger.error(f"[WebSocket] Session {session_id}: 流式处理失败: {e}", exc_info=True)
                            try:
                                await websocket_manager.send_json(session_id, {
                                    "type": "error",
                                    "data": {"message": str(e)}
                                })
                            except:
                                pass
                    
                    # 启动后台任务，并添加到session的current_tasks中以便中断
                    background_task = asyncio.create_task(process_text_background())
                    session.current_tasks.append(background_task)
                    
                    # 任务完成后自动从列表中移除
                    def remove_task(task):
                        if task in session.current_tasks:
                            session.current_tasks.remove(task)
                    background_task.add_done_callback(lambda t: remove_task(t))
                
                else:
                    # Non-streaming mode (legacy support)
                    response = await session.process_text(data.get("text"))
                    
                    # Send text response
                    await websocket_manager.send_json(session_id, {
                        "type": "response",
                        "data": {
                            "text": response["text"]
                        }
                    })
                    
                    # Send video as binary
                    if response.get("video"):
                        await websocket.send_bytes(response["video"])
                
            elif message_type == "config":
                # Update session configuration
                try:
                    await session.update_config(data.get("config"))
                    # 发送确认响应（如果连接还存在）
                    try:
                        await websocket_manager.send_json(session_id, {
                            "type": "config_updated",
                            "status": "success"
                        })
                        logger.info(f"[WebSocket] Session {session_id}: 配置已更新")
                    except Exception as send_error:
                        logger.warning(f"[WebSocket] Session {session_id}: 配置确认消息发送失败: {send_error}")
                except Exception as e:
                    logger.error(f"[WebSocket] Session {session_id}: 配置更新失败: {e}", exc_info=True)
                    # 尝试发送错误响应（如果连接还存在）
                    try:
                        await websocket_manager.send_json(session_id, {
                            "type": "config_updated",
                            "status": "error",
                            "message": str(e)
                        })
                    except:
                        pass  # 如果发送失败，忽略
            
            elif message_type == "video_ack":
                # 客户端确认收到视频
                last_seq = data.get("last_seq", -1)
                logger.info(f"[WebSocket] Session {session_id}: 客户端确认已收到序号 {last_seq}")
                session.update_client_received_seq(last_seq)
            
            elif message_type == "reconnect_sync":
                # 重连同步：客户端告知最后收到的视频序号
                last_seq = data.get("last_seq", -1)
                logger.info(f"[WebSocket] Session {session_id}: 重连同步，客户端最后序号 {last_seq}")
                session.update_client_received_seq(last_seq)
                
                # 检查是否有未发送的视频需要重发
                missing_videos = session.get_missing_videos(last_seq)
                if missing_videos:
                    logger.info(f"[WebSocket] Session {session_id}: 重发 {len(missing_videos)} 个未收到的视频")
                    for video_data in missing_videos:
                        try:
                            # 发送视频块元数据
                            await websocket_manager.send_json(session_id, {
                                "type": "video_chunk_meta",
                                "data": {
                                    "seq": video_data['seq'],
                                    "size": len(video_data['video']),
                                    "text": video_data.get('text', '')
                                }
                            })
                            # 发送视频二进制数据
                            await websocket_manager.send_bytes(session_id, video_data['video'])
                            logger.info(f"[WebSocket] Session {session_id}: 已重发视频序号 {video_data['seq']}")
                        except Exception as e:
                            logger.error(f"[WebSocket] Session {session_id}: 重发视频序号 {video_data['seq']} 失败: {e}")
                            break
                else:
                    logger.info(f"[WebSocket] Session {session_id}: 无需重发视频")
                
                # 发送同步完成响应
                await websocket_manager.send_json(session_id, {
                    "type": "sync_complete",
                    "status": "success",
                    "resent_count": len(missing_videos)
                })
                
            elif message_type == "interrupt":
                # Handle interrupt request
                logger.info(f"[WebSocket] Session {session_id}: 收到中断请求")
                
                try:
                    # Call session manager to interrupt current tasks
                    success = await session_manager.interrupt_session(session_id)
                    
                    # Send interrupt acknowledgment (如果连接还存在)
                    try:
                        await websocket_manager.send_json(session_id, {
                            "type": "interrupt_ack",
                            "success": success
                        })
                        logger.info(f"[WebSocket] Session {session_id}: 中断{'成功' if success else '失败'}")
                    except Exception as send_error:
                        # 发送确认消息失败，但不影响中断操作
                        logger.warning(f"[WebSocket] Session {session_id}: 中断确认消息发送失败: {send_error}")
                except Exception as e:
                    logger.error(f"[WebSocket] Session {session_id}: 中断处理失败: {e}", exc_info=True)
                    # 尝试发送错误响应
                    try:
                        await websocket_manager.send_json(session_id, {
                            "type": "interrupt_ack",
                            "success": False,
                            "error": str(e)
                        })
                    except:
                        pass  # 如果发送失败，忽略
                
            elif message_type == "ping":
                # Heartbeat
                await websocket_manager.send_json(session_id, {"type": "pong"})
                
    except WebSocketDisconnect:
        logger.info(f"Client {session_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
    finally:
        # Cancel heartbeat task
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        
        # Clean up WebSocket connection first
        websocket_manager.disconnect(session_id)
        
        # 标记Session为断开状态（不删除，支持重连和继续发送未完成的视频）
        # 只对成功创建的session才调用disconnect_session
        if session_id in session_manager.sessions:
            await session_manager.disconnect_session(session_id)
            logger.info(f"⏸️ Session {session_id} 保留，等待重连（5分钟内重连可继续）")
        else:
            logger.debug(f"Session {session_id} 未创建或已删除，无需保留")


@app.get("/api/config")
async def get_config():
    """Get current system configuration"""
    return {
        "llm": {
            "api_url": settings.LLM_API_URL,
            "api_key": settings.LLM_API_KEY if settings.LLM_API_KEY else "",
            "model": settings.LLM_MODEL,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS
        },
        "tts": {
            "voice": settings.TTS_VOICE,
            "rate": settings.TTS_RATE,
            "pitch": settings.TTS_PITCH
        },
        "avatar": {
            "fps": settings.AVATAR_FPS,
            "resolution": list(settings.AVATAR_RESOLUTION),
            "template": settings.AVATAR_TEMPLATE,
            "use_onnx": settings.AVATAR_USE_ONNX,
            "static_mode": settings.AVATAR_STATIC_MODE,
            "enhance_mode": settings.AVATAR_ENHANCE_MODE,
            "face_padding_horizontal": settings.AVATAR_FACE_PADDING_HORIZONTAL,
            "face_padding_top": settings.AVATAR_FACE_PADDING_TOP,
            "face_padding_bottom": settings.AVATAR_FACE_PADDING_BOTTOM
        }
    }


@app.post("/api/config")
async def update_config(config: dict):
    """Update system configuration"""
    try:
        # Validate and update configuration
        from backend.app.config import update_settings
        update_settings(config)
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/sessions")
async def get_sessions():
    """Get active sessions information"""
    return {
        "active_sessions": session_manager.get_active_sessions(),
        "total_memory_mb": session_manager.get_total_memory_usage()
    }


@app.get("/api/session/current")
async def get_current_user_session(
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Get current user's session information"""
    try:
        from backend.database.auth import AuthService
        from backend.database.models import db_manager
        
        # 获取token
        if not authorization or not authorization.startswith("Bearer "):
            return {"has_session": False, "message": "未提供认证信息"}
        
        token = authorization[7:]
        
        auth_service = AuthService()
        db_session = db_manager.get_session()
        try:
            user = auth_service.get_current_user(db_session, token)
            if not user:
                return {"has_session": False, "message": "无效的认证信息"}
            
            # 获取用户会话
            session_info = session_manager.get_user_session(user.id)
            if session_info:
                return {
                    "has_session": True,
                    "session": session_info
                }
            else:
                return {
                    "has_session": False,
                    "message": "当前没有活跃会话"
                }
        finally:
            db_session.close()
    except Exception as e:
        logger.error(f"获取用户会话失败: {e}", exc_info=True)
        return {"has_session": False, "message": f"获取会话信息失败: {str(e)}"}


@app.post("/api/session/disconnect")
async def disconnect_current_user_session(
    authorization: Optional[str] = Header(default=None, alias="Authorization")
):
    """Disconnect current user's session"""
    try:
        from backend.database.auth import AuthService
        from backend.database.models import db_manager
        
        # 获取token
        if not authorization or not authorization.startswith("Bearer "):
            return {"success": False, "message": "未提供认证信息"}
        
        token = authorization[7:]
        
        auth_service = AuthService()
        db_session = db_manager.get_session()
        try:
            user = auth_service.get_current_user(db_session, token)
            if not user:
                return {"success": False, "message": "无效的认证信息"}
            
            # 断开用户会话
            success = await session_manager.disconnect_user_session(user.id)
            if success:
                return {
                    "success": True,
                    "message": "会话已断开"
                }
            else:
                return {
                    "success": False,
                    "message": "当前没有活跃会话"
                }
        finally:
            db_session.close()
    except Exception as e:
        logger.error(f"断开会话失败: {e}", exc_info=True)
        return {"success": False, "message": f"断开会话失败: {str(e)}"}


@app.get("/api/models")
async def get_available_models():
    """Get list of available models"""
    models_dir = Path("models")
    models = {
        "whisper": [],
        "wav2lip": [],
        "avatars": []
    }
    
    if models_dir.exists():
        # Check for Whisper models
        whisper_dir = models_dir / "whisper"
        if whisper_dir.exists():
            models["whisper"] = [f.name for f in whisper_dir.iterdir() if f.is_dir()]
        
        # Check for Wav2Lip models
        wav2lip_models = list(models_dir.glob("*.onnx"))
        models["wav2lip"] = [f.name for f in wav2lip_models]
        
        # Check for avatar templates
        avatar_dir = models_dir / "avatars"
        if avatar_dir.exists():
            models["avatars"] = [f.name for f in avatar_dir.iterdir() if f.suffix in [".mp4", ".png", ".jpg"]]
    
    return models


@app.get("/api/idle-video")
async def get_idle_video():
    """Get idle/background video for avatar"""
    from fastapi.responses import FileResponse
    
    # Try LiteAvatar background video first
    idle_video_path = PROJECT_ROOT / "models" / "lite_avatar" / "default" / "bg_video.mp4"
    
    logger.info(f"Looking for idle video at: {idle_video_path}")
    logger.info(f"File exists: {idle_video_path.exists()}")
    
    if not idle_video_path.exists():
        # Fallback to other locations
        fallback_paths = [
            PROJECT_ROOT / "models" / "avatars" / "default.mp4",
            PROJECT_ROOT / "static" / "default_avatar.mp4"
        ]
        for fallback in fallback_paths:
            logger.info(f"Trying fallback: {fallback}")
            if fallback.exists():
                idle_video_path = fallback
                break
    
    if idle_video_path.exists():
        logger.info(f"Serving idle video: {idle_video_path}")
        return FileResponse(
            str(idle_video_path),
            media_type="video/mp4",
            headers={"Content-Disposition": "inline"}
        )
    else:
        logger.error(f"Idle video not found. Searched paths: {idle_video_path}")
        raise HTTPException(status_code=404, detail=f"Idle video not found at: {idle_video_path}")


@app.post("/api/merge-videos")
async def merge_videos(videos: List[UploadFile] = File(...)):
    """
    合并多个MP4视频片段为一个完整的视频文件
    使用FFmpeg的concat协议来正确合并MP4文件
    """
    if not videos:
        raise HTTPException(status_code=400, detail="No videos provided")
    
    logger.info(f"📹 开始合并 {len(videos)} 个视频片段...")
    
    # 创建临时目录存储视频片段和输出文件
    temp_dir = Path(tempfile.mkdtemp(prefix="video_merge_"))
    input_files = []
    concat_list_path = temp_dir / "concat_list.txt"
    output_path = temp_dir / "merged_output.mp4"
    
    try:
        # 保存所有上传的视频片段
        for idx, video in enumerate(videos):
            video_path = temp_dir / f"segment_{idx:03d}.mp4"
            content = await video.read()
            video_path.write_bytes(content)
            input_files.append(video_path)
            logger.debug(f"  - 保存片段 {idx + 1}: {len(content)} bytes")
        
        # 创建FFmpeg concat列表文件
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for input_file in input_files:
                # 使用相对路径或绝对路径
                f.write(f"file '{input_file.absolute()}'\n")
        
        # 使用FFmpeg concat协议合并视频
        # 重新编码以确保兼容性（避免编码参数不一致导致播放失败）
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_list_path),
            # 重新编码视频，使用统一的编码参数
            '-c:v', 'libx264',  # H.264编码（兼容性最好）
            '-preset', 'fast',  # 快速编码
            '-crf', '23',  # 质量（18-28，23为默认，质量较好）
            '-pix_fmt', 'yuv420p',  # 像素格式（兼容性最好）
            '-c:a', 'aac',  # AAC音频编码
            '-b:a', '128k',  # 音频比特率
            '-movflags', '+faststart',  # 优化Web播放
            str(output_path)
        ]
        
        logger.info(f"🎬 执行FFmpeg合并: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # 60秒超时
        )
        
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg合并失败: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Video merge failed: {result.stderr}")
        
        # ✅ 优化：使用流式传输，避免一次性加载整个文件到内存
        file_size = output_path.stat().st_size
        logger.info(f"✅ 视频合并成功: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        # 保存临时目录路径，用于传输完成后清理
        temp_dir_to_clean = temp_dir
        
        def generate_video_chunks():
            """生成视频文件块，用于流式传输"""
            chunk_size = 1024 * 1024  # 1MB chunks
            try:
                with open(output_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
            finally:
                # 传输完成后清理临时文件
                try:
                    import shutil
                    if temp_dir_to_clean.exists():
                        shutil.rmtree(temp_dir_to_clean)
                        logger.debug(f"🧹 清理临时目录: {temp_dir_to_clean}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")
        
        # 使用流式响应，分块传输视频文件
        return StreamingResponse(
            generate_video_chunks(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": "attachment; filename=merged_video.mp4",
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes"
            }
        )
        
    except subprocess.TimeoutExpired:
        logger.error("❌ FFmpeg合并超时")
        raise HTTPException(status_code=500, detail="Video merge timeout")
    except Exception as e:
        logger.error(f"❌ 视频合并失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video merge error: {str(e)}")
    finally:
        # 注意：如果返回了 StreamingResponse，文件清理会在 generate_video_chunks 的 finally 块中进行
        # 这里只清理异常情况下的临时文件
        try:
            import shutil
            if 'temp_dir' in locals() and temp_dir.exists():
                # 检查是否已经返回了 StreamingResponse（通过检查 output_path 是否还存在）
                if not output_path.exists() or output_path.stat().st_size == 0:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"🧹 清理临时目录（异常情况）: {temp_dir}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")


# Mount static files
if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


def main():
    """Main entry point"""
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None  # Use loguru instead
    )


if __name__ == "__main__":
    main()