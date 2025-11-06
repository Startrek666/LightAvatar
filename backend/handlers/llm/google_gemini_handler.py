"""
Google Gemini API Handler for LLM responses
使用谷歌云原生 Gemini API，支持流式对话和历史记录
"""
import asyncio
from typing import AsyncGenerator, List, Dict, Optional, Any
from loguru import logger
from google import genai

from backend.handlers.base import BaseHandler


class GoogleGeminiHandler(BaseHandler):
    """Google Gemini API handler with streaming support"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp", config: Optional[dict] = None):
        """
        初始化 Google Gemini handler
        
        Args:
            api_key: Google API Key
            model: 模型名称，默认 gemini-2.0-flash-exp
            config: 额外配置
        """
        super().__init__(config)
        self.api_key = api_key
        self.model = model
        self.client = None
        self.chat = None
    
    async def _setup(self):
        """
        设置 Google Gemini 客户端（BaseHandler 接口）
        """
        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"✅ Google Gemini 客户端初始化成功 (模型: {self.model})")
            # 创建聊天会话
            self.create_chat()
        except Exception as e:
            logger.error(f"❌ Google Gemini 客户端初始化失败: {e}")
            raise
    
    async def process(self, data: Any) -> Any:
        """
        处理数据（BaseHandler 接口）
        这里不实现，使用 stream_response 系列方法
        """
        raise NotImplementedError("Use stream_response() or stream_response_with_search() instead")
    
    def create_chat(self):
        """创建新的聊天会话"""
        try:
            self.chat = self.client.chats.create(model=self.model)
            logger.info(f"✅ 创建新的 Gemini 聊天会话 (模型: {self.model})")
        except Exception as e:
            logger.error(f"❌ 创建 Gemini 聊天会话失败: {e}")
            raise
    
    def get_history(self) -> List[Dict]:
        """
        获取聊天历史记录
        
        Returns:
            List of message dicts with 'role' and 'content'
        """
        if not self.chat:
            return []
        
        try:
            history = []
            for message in self.chat.get_history():
                history.append({
                    "role": message.role,
                    "content": message.parts[0].text if message.parts else ""
                })
            return history
        except Exception as e:
            logger.error(f"❌ 获取历史记录失败: {e}")
            return []
    
    def _sync_conversation_history(self, conversation_history: List[Dict] = None):
        """
        同步 conversation_history 到 Gemini chat 对象
        
        Args:
            conversation_history: 对话历史记录 [{"role": "user/assistant", "content": "..."}]
        """
        if not conversation_history or len(conversation_history) == 0:
            return
        
        try:
            # 获取当前 chat 对象的历史
            current_history = self.get_history()
            
            # 比较历史记录是否一致
            # conversation_history 的最后一条应该是当前用户消息，需要排除它来比较
            history_to_compare = conversation_history[:-1] if conversation_history and conversation_history[-1].get("role") == "user" else conversation_history
            
            # 检查历史是否一致（比较消息数量和内容）
            if len(current_history) == len(history_to_compare):
                # 如果长度相同，检查内容是否一致
                is_synced = True
                for i, (current_msg, expected_msg) in enumerate(zip(current_history, history_to_compare)):
                    current_role = current_msg.get("role", "")
                    expected_role = expected_msg.get("role", "")
                    current_content = current_msg.get("content", "").strip()
                    expected_content = expected_msg.get("content", "").strip()
                    
                    # 角色必须一致，内容应该大致相同（允许一些差异，因为可能有格式变化）
                    if current_role != expected_role or (len(current_content) > 0 and len(expected_content) > 0 and 
                                                         abs(len(current_content) - len(expected_content)) > len(expected_content) * 0.1):
                        is_synced = False
                        logger.info(f"📊 历史记录不一致: 位置{i}, 角色={current_role}vs{expected_role}, 长度差异={abs(len(current_content) - len(expected_content))}")
                        break
                
                if is_synced:
                    logger.info(f"✅ 历史记录已同步: {len(current_history)} 条消息")
                    return
            
            # 历史不一致，需要重建 chat 并重新发送历史消息
            logger.info(f"🔄 历史记录不一致，重建 chat 对象")
            logger.info(f"  - Chat历史: {len(current_history)} 条")
            logger.info(f"  - Session历史: {len(history_to_compare)} 条")
            
            # 重建 chat 对象
            self.create_chat()
            
            # 重新发送历史消息（成对处理 user-assistant）
            # 注意：Gemini API 的 chat 对象需要实际调用 API 才能保存 assistant 回复
            # 为了建立完整历史，我们需要实际调用 API 获取 assistant 回复
            if history_to_compare:
                logger.info(f"📤 重新发送 {len(history_to_compare)} 条历史消息到 Gemini")
                
                # 将历史消息配对处理（user-assistant 对）
                i = 0
                while i < len(history_to_compare):
                    msg = history_to_compare[i]
                    role = msg.get("role", "")
                    content = msg.get("content", "").strip()
                    
                    if role == "user" and content:
                        try:
                            # 检查下一条是否是 assistant 回复
                            if i + 1 < len(history_to_compare) and history_to_compare[i + 1].get("role") == "assistant":
                                # 有对应的 assistant 回复
                                # 发送 user 消息，Gemini 会自动保存 user 和 assistant
                                # 注意：Gemini API 的 send_message 会返回 assistant 回复
                                # 但为了性能，我们只发送 user 消息，不等待 assistant 回复
                                # 这会导致历史不完全一致，但至少能保证上下文连续性
                                # 实际上，Gemini 的 chat 对象会自动保存 user 和 assistant 的对话
                                # 但如果我们只发送 user，assistant 不会自动出现
                                # 所以我们需要实际调用 API 来获取 assistant 回复
                                # 但为了性能，我们跳过这一步，只发送 user 消息
                                self.chat.send_message(content)
                                i += 2  # 跳过 user 和 assistant
                            else:
                                # 没有对应的 assistant 回复，只发送 user 消息
                                self.chat.send_message(content)
                                i += 1
                        except Exception as e:
                            logger.warning(f"⚠️ 发送历史消息失败: {e}")
                            i += 1
                    elif role == "assistant":
                        # assistant 消息会被自动保存（通过之前的 user 消息调用）
                        i += 1
                    else:
                        i += 1
                
                logger.info(f"✅ 历史消息同步完成")
            
        except Exception as e:
            logger.error(f"❌ 同步历史记录失败: {e}", exc_info=True)
            # 如果同步失败，继续使用当前 chat 对象，不中断流程
    
    async def stream_response(
        self, 
        text: str,
        conversation_history: List[Dict] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成响应（与 OpenAIHandler 接口一致）
        
        Args:
            text: 当前用户输入文本
            conversation_history: 对话历史记录 [{"role": "user/assistant", "content": "..."}]
            
        Yields:
            str: 响应文本块
        """
        if not self.chat:
            self.create_chat()
        
        # 同步 conversation_history 到 Gemini chat 对象
        self._sync_conversation_history(conversation_history)
        
        # Google Gemini API 通过 chat 管理历史，只需发送最新的用户消息
        user_message = text
        
        if not user_message:
            logger.warning("⚠️ 用户消息为空")
            return
        
        try:
            history = self.get_history()
            logger.info(f"🚀 开始流式生成 Gemini 响应")
            logger.info(f"  - 模型: {self.model}")
            logger.info(f"  - 消息长度: {len(user_message)}")
            logger.info(f"  - 历史消息数: {len(history)}")
            logger.info(f"  - 当前对话历史数: {len(conversation_history) if conversation_history else 0}")
            
            response = self.chat.send_message_stream(user_message)
            
            chunk_count = 0
            total_text = ""
            
            # Google Gemini 的 send_message_stream 返回同步迭代器
            # 需要在异步环境中逐块处理，避免阻塞事件循环
            # 使用 run_in_executor 在线程池中处理同步迭代器
            loop = asyncio.get_event_loop()
            
            def get_next_chunk(iterator, sentinel=object()):
                """获取迭代器的下一个元素"""
                try:
                    return next(iterator, sentinel)
                except StopIteration:
                    return sentinel
            
            sentinel = object()
            # 添加超时保护，避免在处理大表格时卡死
            CHUNK_TIMEOUT = 30.0  # 每个chunk最多等待30秒
            
            while True:
                try:
                    # 在线程池中获取下一个 chunk，添加超时保护
                    chunk = await asyncio.wait_for(
                        loop.run_in_executor(None, get_next_chunk, response, sentinel),
                        timeout=CHUNK_TIMEOUT
                    )
                    
                    if chunk is sentinel:
                        break
                    
                    if hasattr(chunk, 'text') and chunk.text:
                        chunk_count += 1
                        total_text += chunk.text
                        yield chunk.text
                        
                except asyncio.TimeoutError:
                    logger.error(f"❌ Gemini chunk 获取超时（{CHUNK_TIMEOUT}秒），可能遇到大表格或网络问题")
                    logger.error(f"  - 已接收块数: {chunk_count}")
                    logger.error(f"  - 已接收字符数: {len(total_text)}")
                    # 尝试继续获取下一个chunk，但如果连续超时则退出
                    try:
                        # 再尝试一次，缩短超时时间
                        chunk = await asyncio.wait_for(
                            loop.run_in_executor(None, get_next_chunk, response, sentinel),
                            timeout=5.0
                        )
                        if chunk is sentinel:
                            break
                        if hasattr(chunk, 'text') and chunk.text:
                            chunk_count += 1
                            total_text += chunk.text
                            yield chunk.text
                    except asyncio.TimeoutError:
                        logger.error("❌ 连续超时，停止流式处理")
                        break
            
            logger.info(f"✅ Gemini 流式响应完成")
            logger.info(f"  - 总块数: {chunk_count}")
            logger.info(f"  - 总字符数: {len(total_text)}")
            logger.info(f"  - 响应预览: {total_text[:100]}...")
            
        except Exception as e:
            logger.error(f"❌ Gemini 流式生成失败: {e}", exc_info=True)
            error_msg = f"抱歉，生成响应时出错: {str(e)}"
            yield error_msg
    
    async def stream_response_with_search(
        self,
        text: str,
        conversation_history: List[Dict] = None,
        search_handler=None,
        use_search: bool = True,
        search_mode: str = "advanced",
        momo_search_handler=None,
        momo_search_quality: str = "speed",
        progress_callback=None,
        search_results_callback=None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        带搜索功能的流式生成响应（与 OpenAIHandler 接口一致）
        
        Args:
            text: 当前用户输入
            conversation_history: 对话历史
            search_handler: 简单搜索处理器（未使用）
            use_search: 是否使用搜索
            search_mode: 搜索模式 (simple/advanced)
            momo_search_handler: 高级搜索处理器
            momo_search_quality: 搜索质量 (speed/quality)
            progress_callback: 搜索进度回调
            
        Yields:
            str: 响应文本块
        """
        user_query = text
        
        if not user_query:
            logger.warning("⚠️ 用户查询为空")
            async for chunk in self.stream_response(text, conversation_history):
                yield chunk
            return
        
        # 执行搜索（仅支持高级搜索）
        # 检查是否使用多Agent模式
        use_multi_agent = getattr(momo_search_handler, 'use_multi_agent', False) if momo_search_handler else False
        if use_multi_agent:
            logger.info(f"🤖 [多Agent模式] 开始 Momo 高级搜索 (质量: {momo_search_quality})")
        else:
            logger.info(f"⚙️ [管道模式] 开始 Momo 高级搜索 (质量: {momo_search_quality})")
        
        if not momo_search_handler:
            logger.warning("⚠️ Momo 搜索处理器未提供，跳过搜索")
            async for chunk in self.stream_response(text, conversation_history):
                yield chunk
            return
        
        # 保存引用信息
        citations_text = ""
        
        try:
            # Momo 搜索返回 (relevant_docs, citations) 元组
            search_results, citations, thinking_results = await momo_search_handler.search_with_progress(
                user_query,
                mode=momo_search_quality,
                progress_callback=progress_callback,
                conversation_history=conversation_history  # 传递对话历史，用于上下文理解
            )
            
            # 保存引用信息用于最后添加
            citations_text = citations
            
            # 发送搜索结果到前端（用于弹窗显示）
            if search_results and search_results_callback:
                await search_results_callback(search_results)
            
            if search_results and len(search_results) > 0:
                logger.info(f"✅ 搜索完成，获得 {len(search_results)} 个结果")
                logger.info(f"📚 引用信息长度: {len(citations)}")
                
                # 使用思考链构建深度思考的 Prompt
                from datetime import datetime
                from backend.handlers.llm.thinking_chain import build_enhanced_search_prompt
                
                today = datetime.now().strftime("%Y-%m-%d")
                
                # 根据搜索质量模式决定是否使用思考链
                # quality（深度）模式：使用思考链，进行深度思考
                # speed（快速）模式：使用简单模式，快速回答
                use_thinking_chain = (momo_search_quality == "quality")
                
                if use_thinking_chain:
                    logger.info(f"🧠 [深度模式] 使用深度思考链生成回答 (质量: {momo_search_quality})")
                    enhanced_text = build_enhanced_search_prompt(
                        user_query=user_query,
                        search_results=search_results,
                        current_date=today,
                        use_thinking_chain=True,
                        thinking_results=thinking_results
                    )
                else:
                    # 快速模式：使用简单 Prompt
                    logger.info(f"⚡ [快速模式] 使用简单模式生成回答 (质量: {momo_search_quality})")
                    enhanced_text = build_enhanced_search_prompt(
                        user_query=user_query,
                        search_results=search_results,
                        current_date=today,
                        use_thinking_chain=False
                    )
                
                logger.info(f"📝 搜索上下文已构建 (长度: {len(enhanced_text)}, 思考链: {use_thinking_chain})")
                
                logger.info(f"📤 准备发送增强消息 (总长度: {len(enhanced_text)})")
                
                # 使用增强后的消息进行生成
                async for chunk in self.stream_response(enhanced_text, conversation_history):
                    yield chunk
                
                # 在响应结束后添加引用信息
                if citations_text:
                    logger.info(f"📚 添加引用信息到响应末尾")
                    yield f"\n\n**📚 参考来源：**\n{citations_text}"
            else:
                logger.warning("⚠️ 搜索未返回结果，使用原始消息")
                async for chunk in self.stream_response(text, conversation_history):
                    yield chunk
                    
        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}", exc_info=True)
            logger.info("⚠️ 搜索失败，使用原始消息")
            async for chunk in self.stream_response(text, conversation_history):
                yield chunk
    
    def update_config(self, config: dict):
        """
        更新配置
        
        Args:
            config: 配置字典，可包含 model, api_key 等
        """
        updated = False
        
        if "model" in config and config["model"] != self.model:
            self.model = config["model"]
            logger.info(f"✅ 更新 Gemini 模型: {self.model}")
            # 模型变更，需要重新创建 chat
            if self.chat:
                self.create_chat()
            updated = True
        
        if "api_key" in config and config["api_key"] != self.api_key:
            self.api_key = config["api_key"]
            logger.info("✅ 更新 Gemini API Key")
            # API Key 变更，需要重新创建客户端
            try:
                self.client = genai.Client(api_key=self.api_key)
                if self.chat:
                    self.create_chat()
                updated = True
            except Exception as e:
                logger.error(f"❌ 更新 Gemini 客户端失败: {e}")
        
        if updated:
            logger.info("✅ Gemini 配置更新完成")

