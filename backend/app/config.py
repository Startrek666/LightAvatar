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
from loguru import logger

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
    LLM_MODEL: str = Field(default="qwen", description="LLM model selection (qwen or gemma)")
    LLM_TEMPERATURE: float = Field(default=0.7, description="LLM temperature")
    LLM_MAX_TOKENS: int = Field(default=500, description="Maximum tokens for LLM response")
    LLM_SYSTEM_PROMPT: str = Field(
        default="你是一个友好的AI助手，请用简洁清晰的语言回答问题。",
        description="System prompt for LLM"
    )
    LLM_MAX_HISTORY: int = Field(default=10, description="Maximum conversation history to keep")
    
    # 模型配置（从config.yaml读取）
    LLM_MODELS: dict = Field(
        default={
            "qwen": {
                "api_url": "https://api-llm.lemomate.com/v1/qwen",
                "api_key": "L5kGzmjwqXbk0ViD@",
                "model_name": "qwen-2.5b-instruct"
            },
            "gemma": {
                "api_url": "https://api-llm.lemomate.com/v1/gemma",
                "api_key": "L5kGzmjwqXbk0ViD@",
                "model_name": "gemma-3b-it"
            }
        },
        description="LLM model configurations"
    )
    
    # 动态获取当前选择模型的配置
    @property
    def LLM_API_URL(self) -> str:
        return self.LLM_MODELS.get(self.LLM_MODEL, {}).get("api_url", "")
    
    @property
    def LLM_API_KEY(self) -> str:
        return self.LLM_MODELS.get(self.LLM_MODEL, {}).get("api_key", "")
    
    @property
    def LLM_MODEL_NAME(self) -> str:
        return self.LLM_MODELS.get(self.LLM_MODEL, {}).get("model_name", "")
    
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
    AVATAR_RENDER_THREADS: int = Field(default=4, description="Number of render threads for LiteAvatar")
    AVATAR_BG_FRAME_COUNT: int = Field(default=100, description="Background frame count to use")
    
    # Concurrent video generation settings
    MAX_CONCURRENT_VIDEOS: int = Field(default=2, description="Maximum concurrent video generation tasks")
    PREBUFFER_COUNT: int = Field(default=1, description="Number of videos to prebuffer before starting playback")
    
    # PyTorch performance settings
    PYTORCH_INTRA_THREADS: int = Field(default=4, description="PyTorch intra-op parallelism threads")
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
    
    # Web Search settings (Simple Search)
    SEARCH_ENABLED: bool = Field(default=True, description="Enable web search functionality")
    SEARCH_MAX_RESULTS: int = Field(default=5, description="Maximum search results")
    SEARCH_FETCH_CONTENT: bool = Field(default=True, description="Fetch full page content")
    SEARCH_CONTENT_MAX_LENGTH: int = Field(default=2000, description="Maximum content length in characters")
    
    # Momo Advanced Search settings
    MOMO_SEARCH_ENABLED: bool = Field(default=False, description="Enable Momo advanced search (requires SearXNG)")
    MOMO_SEARCH_SEARXNG_URL: str = Field(default="http://localhost:9080", description="SearXNG instance URL")
    MOMO_SEARCH_LANGUAGE: str = Field(default="zh", description="Search language (zh/en)")
    MOMO_SEARCH_TIME_RANGE: str = Field(default="day", description="Search time range (day/week/month/year/'')")
    MOMO_SEARCH_MAX_RESULTS: int = Field(default=50, description="Maximum search results from SearXNG")
    MOMO_SEARCH_EMBEDDING_MODEL: str = Field(default="BAAI/bge-small-zh-v1.5", description="Embedding model for vector retrieval")
    MOMO_SEARCH_NUM_CANDIDATES: int = Field(default=40, description="Number of candidate documents")
    MOMO_SEARCH_SIM_THRESHOLD: float = Field(default=0.45, description="Similarity threshold (0-1)")
    MOMO_SEARCH_ENABLE_DEEP_CRAWL: bool = Field(default=True, description="Enable deep web crawling (quality mode)")
    MOMO_SEARCH_CRAWL_SCORE_THRESHOLD: float = Field(default=0.5, description="Minimum similarity score for crawling")
    MOMO_SEARCH_MAX_CRAWL_DOCS: int = Field(default=10, description="Maximum documents to crawl")
    MOMO_SEARCH_USE_MULTI_AGENT: bool = Field(default=True, description="Use multi-agent collaboration mode")
    
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
    # 只读属性列表（通过@property定义的）
    readonly_attrs = {'LLM_API_URL', 'LLM_API_KEY', 'LLM_MODEL_NAME'}
    
    def set_nested_value(key_path: str, value):
        """递归设置嵌套配置值"""
        # 特殊处理 llm.models（完整替换字典）
        if key_path == "llm.models":
            if hasattr(settings, "LLM_MODELS"):
                setattr(settings, "LLM_MODELS", value)
                logger.info(f"✅ 已加载 LLM 模型配置: {list(value.keys())}")
                return True
        # 尝试匹配 MOMO_SEARCH_ENABLED
        elif key_path == "search.advanced.enabled":
            if hasattr(settings, "MOMO_SEARCH_ENABLED"):
                setattr(settings, "MOMO_SEARCH_ENABLED", value)
                return True
        # 尝试匹配其他 search.advanced.* 配置
        elif key_path.startswith("search.advanced."):
            sub_key = key_path.replace("search.advanced.", "").upper()
            momo_key = f"MOMO_SEARCH_{sub_key}"
            if hasattr(settings, momo_key):
                setattr(settings, momo_key, value)
                return True
        return False
    
    for key, value in config_dict.items():
        # 直接匹配顶层键
        upper_key = key.upper()
        if upper_key not in readonly_attrs and hasattr(settings, upper_key):
            setattr(settings, upper_key, value)
        # 处理嵌套配置（如 avatar.fps -> AVATAR_FPS）
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                # 特殊处理：llm.models 直接作为字典整体处理
                nested_path = f"{key}.{sub_key}"
                if nested_path == "llm.models" and isinstance(sub_value, dict):
                    set_nested_value(nested_path, sub_value)
                    continue
                
                # 处理三层嵌套（如 search.advanced.enabled）
                if isinstance(sub_value, dict):
                    for sub_sub_key, sub_sub_value in sub_value.items():
                        nested_path = f"{key}.{sub_key}.{sub_sub_key}"
                        if not set_nested_value(nested_path, sub_sub_value):
                            # 尝试组合键（如 SEARCH_ADVANCED_ENABLED）
                            combined_key = f"{key}_{sub_key}_{sub_sub_key}".upper()
                            if combined_key not in readonly_attrs and hasattr(settings, combined_key):
                                setattr(settings, combined_key, sub_sub_value)
                else:
                    # 处理两层嵌套（如 avatar.fps）
                    combined_key = f"{key}_{sub_key}".upper()
                # 先尝试组合键（如 SERVER_PORT）
                if combined_key not in readonly_attrs and hasattr(settings, combined_key):
                    setattr(settings, combined_key, sub_value)
                # 如果组合键不存在，尝试只用sub_key（如 PORT）
                elif sub_key.upper() not in readonly_attrs and hasattr(settings, sub_key.upper()):
                    setattr(settings, sub_key.upper(), sub_value)


# Load configuration from file if exists
config_file = PROJECT_ROOT / "config" / "config.yaml"
if config_file.exists():
    file_config = load_config_file(config_file)
    update_settings(file_config)


# Export settings
__all__ = ["settings", "update_settings", "load_config_file"]
