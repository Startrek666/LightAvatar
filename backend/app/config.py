"""
Configuration management for the application
"""
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Application settings"""
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    DEBUG: bool = Field(default=False, description="Debug mode")
    
    # CORS settings
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        description="Allowed CORS origins"
    )
    
    # WebSocket settings
    WS_HEARTBEAT_INTERVAL: int = Field(default=30, description="WebSocket heartbeat interval in seconds")
    WS_MESSAGE_QUEUE_SIZE: int = Field(default=100, description="WebSocket message queue size")
    
    # System resources
    MAX_MEMORY_MB: int = Field(default=10240, description="Maximum memory usage in MB")
    MAX_SESSIONS: int = Field(default=10, description="Maximum concurrent sessions")
    SESSION_TIMEOUT: int = Field(default=300, description="Session timeout in seconds")
    
    # ASR settings
    ASR_BACKEND: str = Field(default="faster-whisper", description="ASR backend: faster-whisper or skynet")
    ASR_LANGUAGE: str = Field(default="zh", description="Default language for ASR")
    
    # Faster-Whisper settings (本地)
    WHISPER_MODEL: str = Field(default="small", description="Whisper model size")
    WHISPER_DEVICE: str = Field(default="cpu", description="Device for Whisper")
    WHISPER_COMPUTE_TYPE: str = Field(default="int8", description="Compute type for Whisper")
    
    # Skynet Whisper settings (远程 API)
    SKYNET_WHISPER_URL: str = Field(default="ws://localhost:6010", description="Skynet Whisper server URL")
    SKYNET_WHISPER_PARTICIPANT_ID: str = Field(default="avatar-user", description="Participant ID for Skynet")
    
    # LLM settings
    LLM_API_URL: str = Field(
        default="http://localhost:8080/v1",
        description="LLM API URL (OpenAI compatible)"
    )
    LLM_API_KEY: str = Field(
        default=os.getenv("LLM_API_KEY", ""),
        description="LLM API key"
    )
    LLM_MODEL: str = Field(default="qwen-plus", description="LLM model name")
    LLM_TEMPERATURE: float = Field(default=0.7, description="LLM temperature")
    LLM_MAX_TOKENS: int = Field(default=500, description="Maximum tokens for LLM response")
    LLM_SYSTEM_PROMPT: str = Field(
        default="你是一个友好的AI助手，请用简洁清晰的语言回答问题。",
        description="System prompt for LLM"
    )
    LLM_MAX_HISTORY: int = Field(default=10, description="Maximum conversation history to keep")
    
    # TTS settings
    TTS_VOICE: str = Field(default="zh-CN-XiaoxiaoNeural", description="Edge TTS voice")
    TTS_RATE: str = Field(default="+0%", description="Speech rate")
    TTS_PITCH: str = Field(default="+0Hz", description="Speech pitch")
    
    # Avatar settings
    AVATAR_ENGINE: str = Field(default="wav2lip", description="Avatar engine: wav2lip or lite")
    AVATAR_FPS: int = Field(default=25, description="Avatar video FPS")
    AVATAR_RESOLUTION: tuple = Field(default=(512, 512), description="Avatar video resolution")
    
    # Wav2Lip settings
    AVATAR_TEMPLATE: str = Field(default="default.mp4", description="Default avatar template")
    AVATAR_USE_ONNX: bool = Field(default=False, description="Use ONNX model for avatar generation")
    AVATAR_STATIC_MODE: bool = Field(default=False, description="Use static image mode")
    AVATAR_ENHANCE_MODE: bool = Field(default=True, description="Enable edge blending enhancement")
    
    # Face detection padding ratios for better mouth capture
    AVATAR_FACE_PADDING_HORIZONTAL: float = Field(default=0.15, description="Horizontal padding ratio (left/right)")
    AVATAR_FACE_PADDING_TOP: float = Field(default=0.10, description="Top padding ratio")
    AVATAR_FACE_PADDING_BOTTOM: float = Field(default=0.35, description="Bottom padding ratio (for mouth)")
    
    # LiteAvatar settings
    AVATAR_NAME: str = Field(default="default", description="LiteAvatar data name")
    AVATAR_USE_GPU: bool = Field(default=False, description="Use GPU for LiteAvatar")
    AVATAR_RENDER_THREADS: int = Field(default=1, description="Number of render threads for LiteAvatar")
    AVATAR_BG_FRAME_COUNT: int = Field(default=150, description="Background frame count to use")
    
    # Concurrent video generation settings
    MAX_CONCURRENT_VIDEOS: int = Field(default=2, description="Maximum concurrent video generation tasks")
    PREBUFFER_COUNT: int = Field(default=2, description="Number of videos to prebuffer before starting playback")
    
    # PyTorch performance settings
    PYTORCH_INTRA_THREADS: int = Field(default=6, description="PyTorch intra-op parallelism threads")
    PYTORCH_INTER_THREADS: int = Field(default=2, description="PyTorch inter-op parallelism threads")
    
    # Buffer settings
    AUDIO_BUFFER_SIZE: int = Field(default=50, description="Audio buffer size (frames)")
    VIDEO_BUFFER_SIZE: int = Field(default=75, description="Video buffer size (frames)")
    
    # Performance settings
    CPU_THREADS: int = Field(
        default=os.cpu_count() or 4,
        description="Number of CPU threads to use"
    )
    
    # Monitoring settings
    ENABLE_MONITORING: bool = Field(default=True, description="Enable monitoring")
    METRICS_PORT: int = Field(default=9090, description="Prometheus metrics port")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略未定义的环境变量


# Global settings instance
settings = Settings()


def load_config_file(config_path: Path) -> dict:
    """Load configuration from YAML file"""
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def update_settings(config_dict: dict):
    """Update settings from dictionary"""
    for key, value in config_dict.items():
        # 直接匹配顶层键
        if hasattr(settings, key.upper()):
            setattr(settings, key.upper(), value)
        # 处理嵌套配置（如 avatar.fps -> AVATAR_FPS）
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                combined_key = f"{key}_{sub_key}".upper()
                # 先尝试组合键（如 SERVER_PORT）
                if hasattr(settings, combined_key):
                    setattr(settings, combined_key, sub_value)
                # 如果组合键不存在，尝试只用sub_key（如 PORT）
                elif hasattr(settings, sub_key.upper()):
                    setattr(settings, sub_key.upper(), sub_value)


# Load configuration from file if exists
config_file = PROJECT_ROOT / "config" / "config.yaml"
if config_file.exists():
    file_config = load_config_file(config_file)
    update_settings(file_config)


# Export settings
__all__ = ["settings", "update_settings", "load_config_file"]
