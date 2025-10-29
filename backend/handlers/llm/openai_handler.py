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
        self.max_tokens = self.config.get("max_tokens", 20000)  # 提高默认值以支持长回复
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
            
            # Add current message (避免重复添加)
            if not conversation_history or conversation_history[-1].get("content") != text:
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
    
    async def stream_response_with_search(
        self, 
        text: str, 
        conversation_history: List[Dict] = None,
        search_handler = None,
        use_search: bool = False,
        progress_callback = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response with optional web search
        
        Args:
            text: User input text
            conversation_history: Previous conversation
            search_handler: WebSearchHandler instance
            use_search: Whether to perform web search
            progress_callback: Callback for search progress (step, total, message)
        """
        try:
            # Prepare messages
            messages = [{"role": "system", "content": self.system_prompt}]
            
            if conversation_history:
                max_history = self.config.get("max_history", 10)
                recent_history = conversation_history[-max_history:]
                
                # Gemma 模型特殊处理：每5轮对话重置一次上下文
                if 'gemma' in self.model.lower():
                    # 计算对话轮数（不包括 system 消息）
                    user_messages = [m for m in recent_history if m["role"] == "user"]
                    
                    # 判断是否需要重置（第6轮、第11轮、第16轮...）
                    if len(user_messages) >= 5 and len(user_messages) % 5 == 0:
                        logger.info(f"🔄 Gemma模型(搜索模式)检测到第 {len(user_messages)+1} 轮对话，执行上下文重置")
                        
                        # 只保留上一轮对话（最后2条消息）
                        if len(recent_history) >= 2:
                            last_user_msg = recent_history[-2]  # 上一轮的user消息
                            last_assistant_msg = recent_history[-1]  # 上一轮的assistant回复
                            
                            # 验证格式正确
                            if last_user_msg["role"] == "user" and last_assistant_msg["role"] == "assistant":
                                # 合并上一轮对话和新消息作为新的第一轮
                                merged_content = f"之前的对话：\n用户: {last_user_msg['content']}\n助手: {last_assistant_msg['content']}\n\n当前问题: {text}"
                                messages.append({"role": "user", "content": merged_content})
                                logger.info(f"✅ 重置上下文，只保留上一轮(user:{len(last_user_msg['content'])}字 + assistant:{len(last_assistant_msg['content'])}字) + 新消息({len(text)}字)")
                            else:
                                # 格式不对，按正常流程处理
                                for msg in recent_history:
                                    messages.append({
                                        "role": msg["role"],
                                        "content": msg["content"]
                                    })
                                messages.append({"role": "user", "content": text})
                        else:
                            # 历史记录不足，按正常流程处理
                            for msg in recent_history:
                                messages.append({
                                    "role": msg["role"],
                                    "content": msg["content"]
                                })
                            messages.append({"role": "user", "content": text})
                    else:
                        # 不到5轮，正常添加历史
                        for msg in recent_history:
                            messages.append({
                                "role": msg["role"],
                                "content": msg["content"]
                            })
                        # 避免重复添加最后一条用户消息
                        if not conversation_history or conversation_history[-1].get("content") != text:
                            messages.append({"role": "user", "content": text})
                else:
                    # 非 Gemma 模型或对话轮数不足，正常处理
                    for msg in recent_history:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
                    # 避免重复添加最后一条用户消息
                    if not conversation_history or conversation_history[-1].get("content") != text:
                        messages.append({"role": "user", "content": text})
            else:
                # 没有历史记录，直接添加新消息
                messages.append({"role": "user", "content": text})
            
            # 如果启用搜索且有搜索处理器
            if use_search and search_handler:
                logger.info(f"🔍 Performing web search for: {text}")
                
                # 执行搜索
                search_results = await search_handler.search_with_progress(
                    query=text,
                    max_results=3,
                    progress_callback=progress_callback
                )
                
                if search_results:
                    logger.info(f"\n{'*'*80}")
                    logger.info(f"📚 构建搜索上下文 (共 {len(search_results)} 个结果)")
                    logger.info(f"{'*'*80}\n")
                    
                    # 构建搜索上下文
                    context = "我为你搜索到了以下相关信息：\n\n"
                    for i, result in enumerate(search_results, 1):
                        context += f"{i}. **{result['title']}**\n"
                        context += f"   来源: {result['url']}\n"
                        if result.get('content'):
                            # 截取部分内容
                            content_preview = result['content'][:300]
                            context += f"   内容: {content_preview}...\n"
                        else:
                            context += f"   摘要: {result['snippet']}\n"
                        context += "\n"
                    
                    context += "请基于以上搜索结果回答用户的问题。"
                    
                    # 将搜索结果插入到用户消息之前
                    messages.insert(-1, {
                        'role': 'system',
                        'content': context
                    })
                    
                    # 详细记录发送给 LLM 的上下文
                    logger.info(f"📝 发送给 LLM 的完整搜索上下文:")
                    logger.info(f"{'─'*80}")
                    logger.info(context)
                    logger.info(f"{'─'*80}")
                    
                    # 统计信息
                    context_chars = len(context)
                    estimated_tokens = int(context_chars * 0.6)
                    logger.info(f"📊 上下文统计:")
                    logger.info(f"  字符数: {context_chars}")
                    logger.info(f"  估计token数: ~{estimated_tokens}")
                    logger.info(f"  搜索结果数: {len(search_results)}")
                    
                    # 记录每个结果的详细信息
                    for i, result in enumerate(search_results, 1):
                        content_len = len(result.get('content', ''))
                        snippet_len = len(result.get('snippet', ''))
                        logger.info(f"  结果{i}: 正文{content_len}字 | 摘要{snippet_len}字 | {result['title'][:40]}...")
                    
                    logger.info(f"\n{'*'*80}\n")
                else:
                    logger.warning(f"⚠️ 搜索未返回任何结果，将不使用搜索上下文")
            
            # 继续正常的流式响应
            async for chunk in self._stream_response_internal(messages):
                yield chunk
                
        except Exception as e:
            logger.error(f"Failed to stream response with search: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield "抱歉，我遇到了一些技术问题，请稍后再试。"
    
    async def _stream_response_internal(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """Internal method for streaming response"""
        
        # 计算输入的 token 数量（简单估算：中文按2字符/token，英文按4字符/token）
        total_chars = sum(len(msg.get('content', '')) for msg in messages)
        estimated_tokens = int(total_chars * 0.6)  # 平均估算
        
        logger.info(f"{'='*60}")
        logger.info(f"Starting LLM stream request")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  Base URL: {self.api_url}")
        logger.info(f"  Messages count: {len(messages)}")
        logger.info(f"  Total characters: {total_chars}")
        logger.info(f"  Estimated input tokens: ~{estimated_tokens}")
        logger.info(f"  Temperature: {self.temperature}")
        logger.info(f"  Max tokens: {self.max_tokens}")
        
        # 记录每条消息的详细信息
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            content_preview = content[:100] + ('...' if len(content) > 100 else '')
            logger.info(f"  Message {i+1} [{role}]: {len(content)} chars - {content_preview}")
        
        logger.info(f"{'='*60}")
        
        # 如果输入过长，记录完整的 messages（用于调试）
        if total_chars > 500:
            logger.warning(f"⚠️  Large input detected ({total_chars} chars), logging full messages for debugging:")
            import json
            for i, msg in enumerate(messages):
                logger.debug(f"Message {i+1} full content:\n{json.dumps(msg, ensure_ascii=False, indent=2)}")
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
                timeout=30.0  # 添加超时防止挂起
            )
            logger.info(f"✅ Stream object created successfully: {type(stream)}")
        except Exception as e:
            logger.error(f"❌ Failed to create stream: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

        chunk_count = 0
        content_chunks = 0
        total_content_length = 0
        logger.info("🔄 Entering async for loop to receive chunks...")
        
        try:
            async for chunk in stream:
                chunk_count += 1
                
                # 记录第一个 chunk 的完整内容以便调试
                if chunk_count == 1:
                    logger.info(f"📦 First chunk received")
                    logger.info(f"   Type: {type(chunk)}")
                    logger.info(f"   Has choices: {hasattr(chunk, 'choices')}")
                    if hasattr(chunk, 'choices'):
                        logger.info(f"   Choices count: {len(chunk.choices) if chunk.choices else 0}")
                    logger.info(f"   Raw chunk: {chunk}")
                
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    
                    # 检查是否有 finish_reason
                    if hasattr(choice, 'finish_reason') and choice.finish_reason:
                        logger.info(f"🏁 Stream finished with reason: {choice.finish_reason}")
                    
                    delta = choice.delta
                    if delta and delta.content:
                        content_chunks += 1
                        content_length = len(delta.content)
                        total_content_length += content_length
                        
                        if content_chunks == 1:
                            logger.info(f"✨ First content chunk received (chunk #{chunk_count})")
                            logger.info(f"   Content preview: {delta.content[:50]}")
                        elif content_chunks % 10 == 0:  # 每10个内容chunk记录一次
                            logger.info(f"📝 Received {content_chunks} content chunks, total {total_content_length} chars")
                        
                        yield delta.content
                else:
                    if chunk_count <= 3:  # 只记录前3个空 chunk
                        logger.warning(f"⚠️  Chunk #{chunk_count} has no choices or empty content")
                        logger.warning(f"   Chunk structure: {chunk}")
        except Exception as e:
            logger.error(f"Error during stream iteration: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
        
        logger.info(f"{'='*60}")
        logger.info(f"LLM stream completed")
        logger.info(f"  Total chunks received: {chunk_count}")
        logger.info(f"  Content chunks: {content_chunks}")
        logger.info(f"  Total content length: {total_content_length} chars")
        logger.info(f"  Estimated output tokens: ~{int(total_content_length * 0.6)}")

        if content_chunks == 0:
            logger.error(f"❌ Stream returned 0 content chunks!")
            logger.error(f"   Total chunks received: {chunk_count}")
            logger.error(f"   API endpoint: {self.client.base_url}")
            logger.error(f"   This suggests:")
            logger.error(f"   1. LLM API returned empty response")
            logger.error(f"   2. API may have rate limits or errors")
            logger.error(f"   3. Input may have triggered content filter")
            logger.error(f"   4. Model may not exist or is unavailable")
        else:
            logger.info(f"✅ Stream successful: {content_chunks} chunks, {total_content_length} chars")
        
        logger.info(f"{'='*60}")
    
    async def stream_response(self, text: str, conversation_history: List[Dict] = None) -> AsyncGenerator[str, None]:
        """Generate streaming response (without search)"""
        try:
            # Prepare messages
            messages = [{"role": "system", "content": self.system_prompt}]
            
            if conversation_history:
                max_history = self.config.get("max_history", 10)
                recent_history = conversation_history[-max_history:]
                
                # Gemma 模型特殊处理：每5轮对话重置一次上下文
                if 'gemma' in self.model.lower():
                    # 计算对话轮数（不包括 system 消息）
                    user_messages = [m for m in recent_history if m["role"] == "user"]
                    
                    # 判断是否需要重置（第6轮、第11轮、第16轮...）
                    if len(user_messages) >= 5 and len(user_messages) % 5 == 0:
                        logger.info(f"🔄 Gemma模型检测到第 {len(user_messages)+1} 轮对话，执行上下文重置")
                        
                        # 只保留上一轮对话（最后2条消息）
                        if len(recent_history) >= 2:
                            last_user_msg = recent_history[-2]  # 上一轮的user消息
                            last_assistant_msg = recent_history[-1]  # 上一轮的assistant回复
                            
                            # 验证格式正确
                            if last_user_msg["role"] == "user" and last_assistant_msg["role"] == "assistant":
                                # 合并上一轮对话和新消息作为新的第一轮
                                merged_content = f"之前的对话：\n用户: {last_user_msg['content']}\n助手: {last_assistant_msg['content']}\n\n当前问题: {text}"
                                messages.append({"role": "user", "content": merged_content})
                                logger.info(f"✅ 重置上下文，只保留上一轮(user:{len(last_user_msg['content'])}字 + assistant:{len(last_assistant_msg['content'])}字) + 新消息({len(text)}字)")
                            else:
                                # 格式不对，按正常流程处理
                                for msg in recent_history:
                                    messages.append({
                                        "role": msg["role"],
                                        "content": msg["content"]
                                    })
                                messages.append({"role": "user", "content": text})
                        else:
                            # 历史记录不足，按正常流程处理
                            for msg in recent_history:
                                messages.append({
                                    "role": msg["role"],
                                    "content": msg["content"]
                                })
                            messages.append({"role": "user", "content": text})
                    else:
                        # 不到5轮，正常添加历史
                        for msg in recent_history:
                            messages.append({
                                "role": msg["role"],
                                "content": msg["content"]
                            })
                        # 避免重复添加最后一条用户消息
                        if not conversation_history or conversation_history[-1].get("content") != text:
                            messages.append({"role": "user", "content": text})
                else:
                    # 非 Gemma 模型或对话轮数不足，正常处理
                    for msg in recent_history:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
                    # 避免重复添加最后一条用户消息
                    if not conversation_history or conversation_history[-1].get("content") != text:
                        messages.append({"role": "user", "content": text})
            else:
                # 没有历史记录，直接添加新消息
                messages.append({"role": "user", "content": text})
            
            # Stream response
            async for chunk in self._stream_response_internal(messages):
                yield chunk
                    
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
