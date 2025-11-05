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
                
                # 注意：recent_history 已经包含当前用户输入（在 session_manager 中添加），直接全部添加即可
                for msg in recent_history:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            else:
                # 没有历史记录，直接添加新消息
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
        search_mode: str = "simple",  # "simple" 或 "advanced"
        momo_search_handler = None,
        momo_search_quality: str = "speed",  # "speed" 或 "quality"
        progress_callback = None,
        search_results_callback = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response with optional web search
        
        Args:
            text: User input text
            conversation_history: Previous conversation
            search_handler: WebSearchHandler instance (简单搜索)
            use_search: Whether to perform web search
            search_mode: 搜索模式 ("simple" 或 "advanced")
            momo_search_handler: MomoSearchHandler instance (高级搜索)
            momo_search_quality: Momo搜索质量 ("speed" 或 "quality")
            progress_callback: Callback for search progress (step, total, message)
        """
        try:
            # Prepare messages
            messages = [{"role": "system", "content": self.system_prompt}]
            
            if conversation_history:
                # Gemma 模型特殊处理：每5轮对话重置一次上下文
                # 注意：必须先判断是否需要重置（基于完整历史），再应用 max_history 截断
                if 'gemma' in self.model.lower():
                    # conversation_history 中最后一条是当前用户输入（已经在 session_manager 中添加）
                    # 所以要排除它来计算之前的对话轮数
                    history_without_current = conversation_history[:-1] if conversation_history and conversation_history[-1].get("role") == "user" else conversation_history
                    user_messages = [m for m in history_without_current if m["role"] == "user"] if history_without_current else []
                    
                    logger.info(f"📊 Gemma模型(搜索模式)对话统计: 完整历史={len(conversation_history) if conversation_history else 0}条, 用户消息={len(user_messages)}条")
                    
                    # 判断是否需要重置（第5轮之后，即第6、11、16轮...）
                    if len(user_messages) >= 5 and len(user_messages) % 5 == 0:
                        logger.info(f"🔄 Gemma模型(搜索模式)检测到第 {len(user_messages)+1} 轮对话，执行上下文重置")
                        
                        # 从 history_without_current 中取最后2条消息（上一轮对话）
                        if history_without_current and len(history_without_current) >= 2:
                            last_user_msg = history_without_current[-2]  # 上一轮的user消息
                            last_assistant_msg = history_without_current[-1]  # 上一轮的assistant回复
                            
                            # 验证格式正确
                            if last_user_msg["role"] == "user" and last_assistant_msg["role"] == "assistant":
                                # 合并上一轮对话和新消息作为新的第一轮
                                merged_content = f"之前的对话：\n用户: {last_user_msg['content']}\n助手: {last_assistant_msg['content']}\n\n当前问题: {text}"
                                messages.append({"role": "user", "content": merged_content})
                                logger.info(f"✅ 重置上下文，只保留上一轮(user:{len(last_user_msg['content'])}字 + assistant:{len(last_assistant_msg['content'])}字) + 新消息({len(text) if text else 0}字)")
                            else:
                                # 格式不对，说明历史记录异常，按正常流程处理（但排除当前输入，因为后面会统一添加）
                                logger.warning(f"⚠️ 上下文重置失败：历史记录格式不正确 (last_user_msg role={last_user_msg.get('role')}, last_assistant_msg role={last_assistant_msg.get('role')})")
                                for msg in history_without_current:
                                    messages.append({
                                        "role": msg["role"],
                                        "content": msg["content"]
                                    })
                                # 添加当前用户输入
                                messages.append({"role": "user", "content": text})
                        else:
                            # 历史记录不足，按正常流程处理
                            logger.warning(f"⚠️ 上下文重置失败：历史记录不足 (len={len(history_without_current) if history_without_current else 0})")
                            if history_without_current:
                                for msg in history_without_current:
                                    messages.append({
                                        "role": msg["role"],
                                        "content": msg["content"]
                                    })
                            messages.append({"role": "user", "content": text})
                    else:
                        # 不到5轮，正常添加历史（Gemma 模型限制为最多8条，即4轮对话）
                        max_history = 8  # Gemma 模型最多保留 4 轮对话（8条消息）
                        recent_history = conversation_history[-max_history:]
                        
                        # ✅ 确保第一条消息是 user（保持对话配对完整性）
                        while recent_history and recent_history[0].get("role") != "user":
                            recent_history = recent_history[1:]
                            logger.warning(f"⚠️ Gemma模型(搜索模式)：跳过开头的非user消息，确保对话配对完整")
                        
                        for msg in recent_history:
                            messages.append({
                                "role": msg["role"],
                                "content": msg["content"]
                            })
                        logger.info(f"📝 Gemma模型(搜索模式)正常对话: 使用最近 {len(recent_history)} 条历史记录（最多4轮）")
                else:
                    # 非 Gemma 模型，正常处理（应用 max_history 限制）
                    max_history = self.config.get("max_history", 10)
                    recent_history = conversation_history[-max_history:]
                    for msg in recent_history:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
            else:
                # 没有历史记录，直接添加新消息
                messages.append({"role": "user", "content": text})
            
            # 调试日志：记录最终发送给 LLM 的消息列表（搜索前）
            logger.info(f"📤 准备发送给 LLM 的消息数量（搜索前）: {len(messages)}")
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content_preview = msg.get('content', '')[:50]
                logger.debug(f"  消息 {i+1}: role={role}, content={content_preview}...")
            
            # 如果启用搜索
            citations_text = ""  # 用于存储引用信息
            
            if use_search:
                # 高级搜索模式 (Momo Search)
                if search_mode == "advanced" and momo_search_handler:
                    # 检查是否使用多Agent模式
                    use_multi_agent = getattr(momo_search_handler, 'use_multi_agent', False) if momo_search_handler else False
                    if use_multi_agent:
                        logger.info(f"🤖 [多Agent模式] 执行Momo高级搜索: {text} (质量: {momo_search_quality})")
                    else:
                        logger.info(f"⚙️ [管道模式] 执行Momo高级搜索: {text} (质量: {momo_search_quality})")
                    
                    # 执行Momo搜索
                    from datetime import datetime
                    cur_date = datetime.today().strftime('%Y-%m-%d')
                    
                    relevant_docs, citations, thinking_results = await momo_search_handler.search_with_progress(
                        query=text,
                        mode=momo_search_quality,
                        progress_callback=progress_callback
                    )
                    
                    # 发送搜索结果到前端（用于弹窗显示）
                    if relevant_docs and search_results_callback:
                        await search_results_callback(relevant_docs)
                    
                    if relevant_docs:
                        logger.info(f"\n{'*'*80}")
                        logger.info(f"📚 构建Momo搜索上下文 (共 {len(relevant_docs)} 个结果)")
                        logger.info(f"{'*'*80}\n")
                        
                        # 使用思考链构建深度思考的 Prompt
                        from backend.handlers.llm.thinking_chain import build_enhanced_search_prompt
                        
                        # 根据搜索质量模式决定是否使用思考链
                        # quality（深度）模式：使用思考链，进行深度思考
                        # speed（快速）模式：使用简单模式，快速回答
                        use_thinking_chain = (momo_search_quality == "quality")
                        
                        if use_thinking_chain:
                            logger.info(f"🧠 [深度模式] 使用深度思考链生成回答 (质量: {momo_search_quality})")
                            thinking_prompt = build_enhanced_search_prompt(
                                user_query=text,
                                search_results=relevant_docs,
                                current_date=cur_date,
                                use_thinking_chain=True,
                                thinking_results=thinking_results
                            )
                            context = thinking_prompt
                        else:
                            # 快速模式：使用简单 Prompt
                            logger.info(f"⚡ [快速模式] 使用简单模式生成回答 (质量: {momo_search_quality})")
                            context = f"# 以下内容是基于用户发送的消息的搜索结果（今天是{cur_date}）:\n\n"
                        
                        for i, doc in enumerate(relevant_docs, 1):
                            context += f"[网页 {i} 开始]\n"
                            context += f"标题: {doc.title}\n"
                            context += f"链接: {doc.url}\n"
                            content_text = doc.content if doc.content else doc.snippet
                            context += f"内容: {content_text}\n"
                            context += f"[网页 {i} 结束]\n\n"
                        
                        context += """在回答时，请注意以下几点：
- 在适当的情况下在句子末尾引用上下文，按照引用编号[citation:X]的格式在答案中对应部分引用上下文
- 如果一句话源自多个上下文，请列出所有相关的引用编号，例如[citation:3][citation:5]
- 并非搜索结果的所有内容都与用户的问题密切相关，你需要结合问题，对搜索结果进行甄别、筛选
- 对于列举类的问题，尽量将答案控制在10个要点以内
- 如果回答很长，请尽量结构化、分段落总结，控制在5个点以内
- 你的回答应该综合多个相关网页来回答，不能重复引用一个网页
- 除非用户要求，否则你回答的语言需要和用户提问的语言保持一致

# 用户消息为：
{text}"""
                        
                        # 保存引用信息，稍后添加到响应中
                        citations_text = citations
                        
                        # 将搜索结果插入到用户消息之前
                        messages.insert(-1, {
                            'role': 'system',
                            'content': context
                        })
                        
                        logger.info(f"📝 搜索上下文已构建 (长度: {len(context)}, 思考链: {use_thinking_chain})")
                        
                        # 详细记录
                        logger.info(f"📝 Momo搜索上下文已注入 (长度: {len(context)}字符)")
                        logger.info(f"📊 相关文档数: {len(relevant_docs)}")
                    else:
                        logger.warning(f"⚠️ Momo搜索未返回结果")
                
                # 简单搜索模式 (WebSearchHandler)
                elif search_mode == "simple" and search_handler:
                    logger.info(f"🔍 执行简单搜索: {text}")
                    
                    # 执行简单搜索
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
                        
                        # 详细记录
                        logger.info(f"📝 简单搜索上下文已注入")
                        logger.info(f"📊 搜索结果数: {len(search_results)}")
                    else:
                        logger.warning(f"⚠️ 搜索未返回任何结果，将不使用搜索上下文")
            
            # 继续正常的流式响应
            async for chunk in self._stream_response_internal(messages):
                yield chunk
            
            # 如果有引用信息，在响应结束后添加
            if citations_text:
                yield f"\n\n**📚 参考来源：**\n{citations_text}"
                
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
                # Gemma 模型特殊处理：每5轮对话重置一次上下文
                # 注意：必须先判断是否需要重置（基于完整历史），再应用 max_history 截断
                if 'gemma' in self.model.lower():
                    # conversation_history 中最后一条是当前用户输入（已经在 session_manager 中添加）
                    # 所以要排除它来计算之前的对话轮数
                    history_without_current = conversation_history[:-1] if conversation_history and conversation_history[-1].get("role") == "user" else conversation_history
                    user_messages = [m for m in history_without_current if m["role"] == "user"] if history_without_current else []
                    
                    logger.info(f"📊 Gemma模型对话统计: 完整历史={len(conversation_history) if conversation_history else 0}条, 用户消息={len(user_messages)}条")
                    
                    # 判断是否需要重置（第5轮之后，即第6、11、16轮...）
                    if len(user_messages) >= 5 and len(user_messages) % 5 == 0:
                        logger.info(f"🔄 Gemma模型检测到第 {len(user_messages)+1} 轮对话，执行上下文重置")
                        
                        # 从 history_without_current 中取最后2条消息（上一轮对话）
                        if history_without_current and len(history_without_current) >= 2:
                            last_user_msg = history_without_current[-2]  # 上一轮的user消息
                            last_assistant_msg = history_without_current[-1]  # 上一轮的assistant回复
                            
                            # 验证格式正确
                            if last_user_msg["role"] == "user" and last_assistant_msg["role"] == "assistant":
                                # 合并上一轮对话和新消息作为新的第一轮
                                merged_content = f"之前的对话：\n用户: {last_user_msg['content']}\n助手: {last_assistant_msg['content']}\n\n当前问题: {text}"
                                messages.append({"role": "user", "content": merged_content})
                                logger.info(f"✅ 重置上下文，只保留上一轮(user:{len(last_user_msg['content'])}字 + assistant:{len(last_assistant_msg['content'])}字) + 新消息({len(text) if text else 0}字)")
                            else:
                                # 格式不对，说明历史记录异常，按正常流程处理（但排除当前输入，因为后面会统一添加）
                                logger.warning(f"⚠️ 上下文重置失败：历史记录格式不正确 (last_user_msg role={last_user_msg.get('role')}, last_assistant_msg role={last_assistant_msg.get('role')})")
                                for msg in history_without_current:
                                    messages.append({
                                        "role": msg["role"],
                                        "content": msg["content"]
                                    })
                                # 添加当前用户输入
                                messages.append({"role": "user", "content": text})
                        else:
                            # 历史记录不足，按正常流程处理
                            logger.warning(f"⚠️ 上下文重置失败：历史记录不足 (len={len(history_without_current) if history_without_current else 0})")
                            if history_without_current:
                                for msg in history_without_current:
                                    messages.append({
                                        "role": msg["role"],
                                        "content": msg["content"]
                                    })
                            messages.append({"role": "user", "content": text})
                    else:
                        # 不到5轮，正常添加历史（Gemma 模型限制为最多8条，即4轮对话）
                        max_history = 8  # Gemma 模型最多保留 4 轮对话（8条消息）
                        recent_history = conversation_history[-max_history:]
                        
                        # ✅ 确保第一条消息是 user（保持对话配对完整性）
                        while recent_history and recent_history[0].get("role") != "user":
                            recent_history = recent_history[1:]
                            logger.warning(f"⚠️ Gemma模型：跳过开头的非user消息，确保对话配对完整")
                        
                        for msg in recent_history:
                            messages.append({
                                "role": msg["role"],
                                "content": msg["content"]
                            })
                        logger.info(f"📝 Gemma模型正常对话: 使用最近 {len(recent_history)} 条历史记录（最多4轮）")
                else:
                    # 非 Gemma 模型，正常处理（应用 max_history 限制）
                    max_history = self.config.get("max_history", 10)
                    recent_history = conversation_history[-max_history:]
                    for msg in recent_history:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
            else:
                # 没有历史记录，直接添加新消息
                messages.append({"role": "user", "content": text})
            
            # 调试日志：记录最终发送给 LLM 的消息列表
            logger.info(f"📤 准备发送给 LLM 的消息数量: {len(messages)}")
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content_preview = msg.get('content', '')[:50]
                logger.debug(f"  消息 {i+1}: role={role}, content={content_preview}...")
            
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
