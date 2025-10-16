"""
Base handler class for all handlers
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from loguru import logger


class BaseHandler(ABC):
    """Abstract base class for all handlers"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._initialized = False
        
    async def initialize(self):
        """Initialize the handler"""
        if not self._initialized:
            await self._setup()
            self._initialized = True
            logger.info(f"{self.__class__.__name__} initialized")
    
    @abstractmethod
    async def _setup(self):
        """Setup the handler - to be implemented by subclasses"""
        pass
    
    @abstractmethod
    async def process(self, data: Any) -> Any:
        """Process data - to be implemented by subclasses"""
        pass
    
    def update_config(self, config: Dict[str, Any]):
        """Update handler configuration"""
        self.config.update(config)
        logger.info(f"{self.__class__.__name__} configuration updated")
    
    async def cleanup(self):
        """Clean up resources"""
        self._initialized = False
        logger.info(f"{self.__class__.__name__} cleaned up")
