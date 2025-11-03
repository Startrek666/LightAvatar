"""
Google Gemini API Handler for LLM responses
使用谷歌云原生 Gemini API，支持流式对话和历史记录
"""
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
            
            for chunk in response:
                if chunk.text:
                    chunk_count += 1
                    total_text += chunk.text
                    yield chunk.text
            
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
        logger.info(f"🔍 开始 Momo 高级搜索 (质量: {momo_search_quality})")
        
        if not momo_search_handler:
            logger.warning("⚠️ Momo 搜索处理器未提供，跳过搜索")
            async for chunk in self.stream_response(text, conversation_history):
                yield chunk
            return
        
        try:
            search_results = await momo_search_handler.search_with_progress(
                user_query,
                mode=momo_search_quality,
                progress_callback=progress_callback
            )
            
            if search_results and len(search_results) > 0:
                logger.info(f"✅ 搜索完成，获得 {len(search_results)} 个结果")
                
                # 构建搜索上下文
                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                
                search_context = f"# 以下内容是基于用户发送的消息的搜索结果（今天是{today}）:\n\n"
                
                for idx, doc in enumerate(search_results[:15], 1):  # 限制15个结果
                    search_context += f"[网页 {idx} 开始]\n\n"
                    search_context += f"标题: {doc.get('title', 'N/A')}\n\n"
                    search_context += f"链接: {doc.get('url', 'N/A')}\n\n"
                    
                    content = doc.get('content', '')
                    if content:
                        # 限制每个文档的内容长度
                        content = content[:1000] if len(content) > 1000 else content
                        search_context += f"内容摘要:\n{content}\n\n"
                    
                    search_context += f"[网页 {idx} 结束]\n\n"
                
                search_context += "# 请基于以上搜索结果回答用户的问题，确保信息准确且引用来源。\n\n"
                
                logger.info(f"📝 搜索上下文已构建 (长度: {len(search_context)})")
                
                # 将搜索上下文合并到用户消息中
                enhanced_text = f"{search_context}\n\n用户问题: {user_query}"
                
                logger.info(f"📤 准备发送增强消息 (总长度: {len(enhanced_text)})")
                
                # 使用增强后的消息进行生成
                async for chunk in self.stream_response(enhanced_text, conversation_history):
                    yield chunk
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

