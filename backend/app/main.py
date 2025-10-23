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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import uvicorn

from backend.app.websocket import WebSocketManager
from backend.app.config import settings
from backend.app.integration_api import router as integration_router
from backend.core.session_manager import SessionManager
from backend.core.health_monitor import HealthMonitor
from backend.utils.logger import setup_logger

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
    # 验证token和权限
    if token:
        try:
            from backend.database.auth import AuthService
            from backend.database.models import db_manager
            
            auth_service = AuthService()
            db_session = db_manager.get_session()
            
            try:
                user = auth_service.get_current_user(db_session, token)
                if not user:
                    await websocket.close(code=1008, reason="未授权: token无效")
                    return
                
                if not user.can_use_avatar:
                    await websocket.close(code=1008, reason="无数字人使用权限")
                    return
                
                logger.info(f"用户 {user.username} 已连接 WebSocket")
            finally:
                db_session.close()
        except Exception as e:
            logger.error(f"WebSocket认证失败: {e}")
            await websocket.close(code=1008, reason="认证失败")
            return
    else:
        logger.warning(f"WebSocket连接未提供token: {session_id}")
    
    await websocket_manager.connect(websocket, session_id)
    
    # Start heartbeat task to detect disconnections
    heartbeat_task = asyncio.create_task(
        websocket_manager.heartbeat(session_id, interval=30)
    )
    
    try:
        # Create or get session
        session = await session_manager.create_session(session_id)
        
        while True:
            # Receive data from client
            data = await websocket.receive_json()
            
            # Process based on message type
            message_type = data.get("type")
            
            if message_type == "audio":
                # Handle audio stream
                await session.process_audio(data.get("data"))
                
            elif message_type == "text":
                # Check if streaming is enabled
                use_streaming = data.get("streaming", True)
                
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
                        
                        elif chunk_type == "video_chunk":
                            # Send video chunk as binary
                            video_bytes = chunk_data.get("video", b"")
                            if video_bytes:
                                # First send metadata
                                await websocket_manager.send_json(session_id, {
                                    "type": "video_chunk_meta",
                                    "data": {
                                        "text": chunk_data.get("text", ""),
                                        "size": len(video_bytes)
                                    }
                                })
                                # Then send binary video data
                                await websocket.send_bytes(video_bytes)
                        
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
                    
                    # Process with streaming
                    await session.process_text_stream(data.get("text"), stream_callback)
                
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
                await session.update_config(data.get("config"))
                await websocket_manager.send_json(session_id, {
                    "type": "config_updated",
                    "status": "success"
                })
                
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
        
        # Clean up connection and session
        websocket_manager.disconnect(session_id)
        await session_manager.remove_session(session_id)


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
