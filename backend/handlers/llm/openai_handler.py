"""
OpenAI-compatible API Handler for language models
"""
import json
from typing import List, Dict, Optional, AsyncGenerator
from openai import AsyncOpenAI
from loguru import logger

from backend.handlers.base import BaseHandler
from backend.core.health_monitor import timer, llm_processing_time


class OpenAIHandler(BaseHandler):
    """Handler for OpenAI-compatible API endpoints"""
    
    def __init__(self, 
                 api_url: str,
                 api_key: str,
                 model: str = "gpt-3.5-turbo",
                 config: Optional[dict] = None):
        super().__init__(config)
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.client = None
        
        # Generation parameters
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 500)
        self.top_p = self.config.get("top_p", 0.9)
        self.presence_penalty = self.config.get("presence_penalty", 0)
        self.frequency_penalty = self.config.get("frequency_penalty", 0)
        self.system_prompt = self.config.get(
            "system_prompt",
            "你是一个友好的AI助手，请用简洁清晰的语言回答问题。"
        )
        
    async def _setup(self):
        """Setup OpenAI client"""
        try:
            # Initialize async OpenAI client
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_url
            )
            
            # Test connection
            await self._test_connection()
            
            logger.info(f"OpenAI client initialized with model '{self.model}'")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
    
    async def _test_connection(self):
        """Test API connection"""
        try:
            # Try to list models or make a simple completion
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            logger.info("API connection test successful")
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            raise
    
    async def process(self, text: str, conversation_history: List[Dict] = None) -> str:
        """
        Generate response for given text
        
        Args:
            text: User input text
            conversation_history: Previous conversation messages
            
        Returns:
            Generated response text
        """
        with timer(llm_processing_time):
            return await self._generate_response(text, conversation_history)
    
    async def _generate_response(self, text: str, conversation_history: List[Dict] = None) -> str:
        """Generate response using the API"""
        try:
            # Prepare messages
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history
            if conversation_history:
                # Keep last N messages to avoid token limit
                max_history = self.config.get("max_history", 10)
                recent_history = conversation_history[-max_history:]
                
                for msg in recent_history:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Add current message
            # 如果历史中已包含当前用户消息，则不重复添加
            if not conversation_history:
                messages.append({"role": "user", "content": text})
            else:
                last_msg = conversation_history[-1]
                if last_msg.get("role") != "user" or last_msg.get("content") != text:
                    messages.append({"role": "user", "content": text})
            
            # Generate response
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                presence_penalty=self.presence_penalty,
                frequency_penalty=self.frequency_penalty
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            logger.info(f"Generated response: {response_text[:100]}...")
            
            return response_text
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return "抱歉，我遇到了一些技术问题，请稍后再试。"
    
    async def generate_response(self, text: str, conversation_history: List[Dict] = None) -> str:
        """Public method to generate response"""
        if not self._initialized:
            await self.initialize()
        
        return await self.process(text, conversation_history)
    
    async def stream_response(self, text: str, conversation_history: List[Dict] = None) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        try:
            # Prepare messages
            messages = [{"role": "system", "content": self.system_prompt}]
            
            if conversation_history:
                max_history = self.config.get("max_history", 10)
                recent_history = conversation_history[-max_history:]
                for msg in recent_history:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            messages.append({"role": "user", "content": text})
            
            # Stream response
            logger.info(f"Starting stream request to model: {self.model}, base_url: {self.api_url}")
            logger.info(f"Request messages: {messages}")
            logger.info(f"Stream parameters: temperature={self.temperature}, max_tokens={self.max_tokens}")
            
            # 先尝试非流式调用，测试API是否正常
            try:
                logger.info("Testing non-streaming call first...")
                test_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=50,
                    stream=False
                )
                logger.info(f"Non-streaming test successful: {test_response.choices[0].message.content[:100] if test_response.choices else 'No choices'}")
            except Exception as test_e:
                logger.error(f"Non-streaming test failed: {test_e}")
            
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                presence_penalty=self.presence_penalty,
                frequency_penalty=self.frequency_penalty,
                stream=True
            )
            logger.info(f"Stream object created: {type(stream)}")
            
            chunk_count = 0
            content_chunks = 0
            logger.info("Starting to iterate over stream chunks...")
            async for chunk in stream:
                chunk_count += 1
                if chunk_count <= 3 or chunk_count % 10 == 0:
                    logger.info(f"Received chunk {chunk_count}")
                
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        content_chunks += 1
                        if content_chunks == 1:
                            logger.info(f"First content received: {delta.content[:50]}...")
                        yield delta.content
                    else:
                        if chunk_count <= 5:
                            logger.info(f"Chunk {chunk_count} has no content - delta: {delta}")
                else:
                    logger.warning(f"Chunk {chunk_count} has no choices: {chunk}")
            
            logger.info(f"Stream completed, total chunks: {chunk_count}, content chunks: {content_chunks}")

            if content_chunks == 0:
                logger.warning("Stream returned no content, falling back to non-streaming request")
                fallback_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    presence_penalty=self.presence_penalty,
                    frequency_penalty=self.frequency_penalty,
                    stream=False
                )
                if fallback_response.choices and len(fallback_response.choices) > 0:
                    content = fallback_response.choices[0].message.content or ""
                    if content:
                        logger.info("Fallback response received content")
                        yield content
                    else:
                        logger.warning("Fallback response returned empty content")
                else:
                    logger.error("Fallback response returned no choices")
                    
        except Exception as e:
            logger.error(f"Failed to stream response: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield "抱歉，我遇到了一些技术问题，请稍后再试。"
    
    def update_config(self, config: Dict):
        """Update configuration"""
        super().update_config(config)
        
        # Update generation parameters
        self.temperature = self.config.get("temperature", self.temperature)
        self.max_tokens = self.config.get("max_tokens", self.max_tokens)
        self.top_p = self.config.get("top_p", self.top_p)
        self.system_prompt = self.config.get("system_prompt", self.system_prompt)
        
        # Update API settings if provided
        if "api_url" in config:
            self.api_url = config["api_url"]
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_url)
        
        if "api_key" in config:
            self.api_key = config["api_key"]
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_url)
        
        if "model" in config:
            self.model = config["model"]
