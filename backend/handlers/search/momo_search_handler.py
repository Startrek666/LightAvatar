"""
Momo Search Handler - 高级联网搜索处理器
集成 Momo-Search 的完整功能
"""
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime
import asyncio
import threading
from loguru import logger
from sentence_transformers import SentenceTransformer

from backend.handlers.base import BaseHandler
from .momo_utils import (
    SearchDocument, 
    search_searxng, 
    search_duckduckgo,
    FaissRetriever, 
    convert_to_markdown,
    detect_language,
    translate_text,
    extract_keywords
)
from .momo_crawler import SimpleCrawler
from .momo_retriever import expand_docs_by_text_split, merge_docs_by_url
from .momo_agents import (
    KeywordExtractionAgent,
    SearchAgent,
    RetrievalAgent,
    CrawlerAgent,
    DocumentProcessorAgent,
    SearchOrchestrator
)


class MomoSearchHandler(BaseHandler):
    """Momo 高级搜索处理器"""
    
    # 类级别的共享资源（所有实例共享）
    _shared_embedding_models: Dict[str, SentenceTransformer] = {}  # {model_name: model_instance}
    _model_lock = threading.Lock()  # 保护模型初始化的锁
    _model_ref_count: Dict[str, int] = {}  # 模型引用计数
    
    @classmethod
    def _get_shared_embedding_model(cls, model_name: str, device: str, torch_dtype) -> SentenceTransformer:
        """
        获取共享的embedding模型（线程安全）
        
        多个Session共享同一个模型实例，减少内存占用
        只有在模型不存在时才创建新实例
        
        Args:
            model_name: 模型名称
            device: 设备 (cuda/cpu)
            torch_dtype: torch数据类型
            
        Returns:
            SentenceTransformer实例
        """
        # 生成缓存键（包含设备信息，因为不同设备需要不同实例）
        cache_key = f"{model_name}_{device}_{str(torch_dtype)}"
        
        # 双重检查锁定模式
        if cache_key not in cls._shared_embedding_models:
            with cls._model_lock:
                # 再次检查（避免并发创建）
                if cache_key not in cls._shared_embedding_models:
                    logger.info(f"🔧 首次加载共享embedding模型: {cache_key}")
                    try:
                        if device == "cuda":
                            model = SentenceTransformer(
                                model_name,
                                device=device,
                                model_kwargs={"torch_dtype": torch_dtype}
                            )
                        else:
                            model = SentenceTransformer(
                                model_name,
                                device=device,
                                model_kwargs={"torch_dtype": torch_dtype}
                            )
                        cls._shared_embedding_models[cache_key] = model
                        cls._model_ref_count[cache_key] = 0
                        logger.info(f"✅ 共享embedding模型加载成功: {cache_key}")
                    except Exception as e:
                        logger.error(f"❌ 共享embedding模型加载失败: {e}")
                        logger.info("ℹ️ 尝试使用默认设置...")
                        model = SentenceTransformer(model_name, device=device)
                        cls._shared_embedding_models[cache_key] = model
                        cls._model_ref_count[cache_key] = 0
                else:
                    logger.debug(f"♻️ 使用已存在的共享embedding模型: {cache_key}")
        
        # 增加引用计数
        cls._model_ref_count[cache_key] = cls._model_ref_count.get(cache_key, 0) + 1
        logger.debug(f"📊 模型引用计数: {cache_key} = {cls._model_ref_count[cache_key]}")
        
        return cls._shared_embedding_models[cache_key]
    
    @classmethod
    def _release_embedding_model(cls, model_name: str, device: str, torch_dtype):
        """
        释放模型引用（当Session销毁时调用）
        
        注意：当前实现不会真正卸载模型，因为可能有其他Session在使用
        未来可以实现真正的卸载逻辑（当引用计数为0时）
        
        Args:
            model_name: 模型名称
            device: 设备
            torch_dtype: torch数据类型
        """
        cache_key = f"{model_name}_{device}_{str(torch_dtype)}"
        if cache_key in cls._model_ref_count:
            cls._model_ref_count[cache_key] = max(0, cls._model_ref_count[cache_key] - 1)
            logger.debug(f"📊 模型引用计数减少: {cache_key} = {cls._model_ref_count[cache_key]}")
            # TODO: 当引用计数为0时，可以考虑卸载模型释放内存
    
    async def _setup(self):
        """初始化搜索组件"""
        try:
            # SearXNG配置
            self.searxng_url = self.config.get('searxng_url', 'http://localhost:9080')
            self.searxng_language = self.config.get('searxng_language', 'zh')
            self.searxng_time_range = self.config.get('searxng_time_range', 'day')
            self.max_search_results = self.config.get('max_search_results', 50)
            
            # 向量检索配置
            embedding_model_name = self.config.get(
                'embedding_model', 
                'BAAI/bge-small-zh-v1.5'
            )
            self.num_candidates = self.config.get('num_candidates', 40)
            self.sim_threshold = self.config.get('sim_threshold', 0.45)
            
            # 爬虫配置
            self.enable_deep_crawl = self.config.get('enable_deep_crawl', True)
            self.crawl_score_threshold = self.config.get('crawl_score_threshold', 0.5)
            self.max_crawl_docs = self.config.get('max_crawl_docs', 10)
            
            # 关键词提取配置
            self.enable_keyword_extraction = self.config.get('enable_keyword_extraction', True)
            self.zhipu_api_key = self.config.get('zhipu_api_key', '6f29a799833a4a5daf5752973e9d0cc4.uoelH21xYFMkDknh')
            self.zhipu_model = self.config.get('zhipu_model', 'glm-4.5-flash')
            
            logger.info("🚀 初始化 Momo Search Handler...")
            logger.info(f"  SearXNG: {self.searxng_url}")
            logger.info(f"  语言: {self.searxng_language}")
            logger.info(f"  时间范围: {self.searxng_time_range}")
            logger.info(f"  嵌入模型: {embedding_model_name}")
            logger.info(f"  深度爬取: {'开启' if self.enable_deep_crawl else '关闭'}")
            logger.info(f"  关键词提取: {'开启' if self.enable_keyword_extraction else '关闭'}")
            
            # 初始化嵌入模型（使用共享模型优化内存）
            # CPU不支持float16，使用float32
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            torch_dtype = torch.float16 if device == "cuda" else torch.float32
            
            # 使用共享模型实例（多个Session共享同一个模型，减少内存占用）
            self.embedding_model = self._get_shared_embedding_model(
                embedding_model_name,
                device=device,
                torch_dtype=torch_dtype
            )
            # 保存模型信息用于清理时释放引用
            self._embedding_model_name = embedding_model_name
            self._embedding_device = device
            self._embedding_torch_dtype = torch_dtype
            logger.info(f"✅ 使用共享embedding模型: {embedding_model_name} (设备: {device})")
            
            # 初始化检索器
            self.retriever = FaissRetriever(
                self.embedding_model,
                num_candidates=self.num_candidates,
                sim_threshold=self.sim_threshold
            )
            
            # 初始化爬虫
            self.crawler = SimpleCrawler(
                timeout=15.0,
                max_concurrent=5
            )
            
            # 初始化多Agent系统
            self.use_multi_agent = self.config.get('use_multi_agent', True)  # 默认启用多Agent
            
            if self.use_multi_agent:
                logger.info("🤖 初始化多Agent系统...")
                self._initialize_agents()
                logger.info("✅ 多Agent系统初始化完成")
            else:
                logger.info("⚠️ 使用传统管道模式（未启用多Agent）")
            
            # 上下文压缩配置
            compression_config = self.config.get('context_compression', {})
            self.compression_method = compression_config.get('method', 'rule_based')
            self.compression_max_messages = compression_config.get('max_messages', 4)
            self.compression_min_total_length = compression_config.get('min_total_length', 1200)
            self.compression_max_length = compression_config.get('max_compressed_length', 600)
            logger.info(f"📦 上下文压缩配置: 方法={self.compression_method}, 消息阈值={self.compression_max_messages}条, 字符阈值={self.compression_min_total_length}字符, 最大长度={self.compression_max_length}字符")
            
            logger.info("✅ Momo Search Handler 初始化完成")
            
        except Exception as e:
            logger.error(f"❌ Momo Search Handler 初始化失败: {e}")
            raise
    
    def get_today_date(self) -> str:
        """获取今天的日期"""
        return datetime.today().strftime('%Y-%m-%d')
    
    def format_sources_for_llm(self, sources: List[SearchDocument]) -> str:
        """
        格式化搜索结果为LLM可用的上下文
        
        Args:
            sources: 搜索文档列表
        
        Returns:
            格式化的字符串
        """
        sources_str = "\n\n".join([
            f"[网页 {i+1} 开始]\n"
            f"标题: {doc.title}\n"
            f"链接: {doc.url}\n"
            f"内容: {doc.content if doc.content else doc.snippet}\n"
            f"[网页 {i+1} 结束]"
            for i, doc in enumerate(sources)
        ])
        return sources_str
    
    def _initialize_agents(self):
        """初始化所有Agent"""
        self.agents = {}
        
        # 深度思考相关Agent（使用智谱清言）
        from .momo_agents import ProblemUnderstandingAgent, MaterialAnalysisAgent, DeepThinkingAgent
        
        # 问题理解Agent（仅深度模式）
        self.agents["problem_understanding"] = ProblemUnderstandingAgent(
            zhipu_api_key=self.zhipu_api_key,
            zhipu_model=self.zhipu_model
        )
        
        # 资料分析Agent（仅深度模式）
        # 使用更高的相似度阈值（0.5）来筛选更相关的文档进行分析
        analysis_score_threshold = self.config.get('analysis_score_threshold', 0.5)
        self.agents["material_analysis"] = MaterialAnalysisAgent(
            zhipu_api_key=self.zhipu_api_key,
            zhipu_model=self.zhipu_model,
            analysis_score_threshold=analysis_score_threshold
        )
        
        # 深度思考Agent（仅深度模式）
        self.agents["deep_thinking"] = DeepThinkingAgent(
            zhipu_api_key=self.zhipu_api_key,
            zhipu_model=self.zhipu_model
        )
        
        # 关键词提取Agent
        if self.enable_keyword_extraction:
            self.agents["keyword_extractor"] = KeywordExtractionAgent(
                zhipu_api_key=self.zhipu_api_key,
                zhipu_model=self.zhipu_model
            )
        
        # 搜索Agent
        self.agents["searcher"] = SearchAgent(
            searxng_url=self.searxng_url,
            searxng_language=self.searxng_language,
            searxng_time_range=self.searxng_time_range,
            max_results=self.max_search_results
        )
        
        # 检索Agent
        self.agents["retriever"] = RetrievalAgent(
            retriever=self.retriever,
            sim_threshold=self.sim_threshold
        )
        
        # 爬取Agent（仅quality模式需要）
        if self.enable_deep_crawl:
            self.agents["crawler"] = CrawlerAgent(
                crawler=self.crawler,
                score_threshold=self.crawl_score_threshold,
                max_docs=self.max_crawl_docs
            )
            
            # 文档处理Agent
            self.agents["document_processor"] = DocumentProcessorAgent(
                retriever=self.retriever
            )
        
        logger.info(f"✅ 已初始化 {len(self.agents)} 个Agent: {list(self.agents.keys())}")
    
    def format_citations(self, docs: List[SearchDocument]) -> str:
        """
        格式化引用信息
        
        Args:
            docs: 文档列表
        
        Returns:
            Markdown格式的引用列表
        """
        citations = []
        for i, doc in enumerate(docs):
            # 截断过长的标题
            title = doc.title[:50] + "..." if len(doc.title) > 50 else doc.title
            citations.append(f"{i+1}. [{title}]({doc.url})")
        
        return "\n".join(citations)
    
    async def search_with_progress(
        self,
        query: str,
        mode: str = "speed",
        progress_callback: Optional[callable] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> tuple[List[SearchDocument], str, dict]:
        """
        执行搜索并报告进度
        
        Args:
            query: 搜索查询
            mode: 搜索模式 (speed/quality)
            progress_callback: 进度回调函数
            conversation_history: 对话历史记录，用于上下文理解
        
        Returns:
            (相关文档列表, 引用信息, 思考结果字典)
        """
        # 如果启用多Agent模式，使用Agent协作
        if self.use_multi_agent and hasattr(self, 'agents'):
            return await self._search_with_agents(query, mode, progress_callback, conversation_history)
        
        # 否则使用传统管道模式（返回空的思考结果）
        docs, citations = await self._search_with_pipeline(query, mode, progress_callback, conversation_history)
        return docs, citations, {}
    
    async def _search_with_agents(
        self,
        query: str,
        mode: str = "speed",
        progress_callback: Optional[callable] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> tuple[List[SearchDocument], str, dict]:
        """使用多Agent协作执行搜索"""
        try:
            logger.info(f"🤖 [多Agent模式] 开始执行搜索: 查询='{query}', 模式={mode}")
            logger.info(f"🤖 [多Agent模式] 已启用 {len(self.agents)} 个Agent: {list(self.agents.keys())}")
            if conversation_history:
                logger.info(f"📚 [多Agent模式] 对话历史: {len(conversation_history)} 条消息")
            
            detected_lang = detect_language(query)
            
            # 创建协调器
            orchestrator = SearchOrchestrator(
                agents=self.agents,
                progress_callback=progress_callback
            )
            
            # 传递压缩配置给orchestrator（以便传递给各个Agent）
            orchestrator._compression_config = {
                "compression_method": self.compression_method,
                "compression_max_messages": self.compression_max_messages,
                "compression_max_length": self.compression_max_length,
                "compression_min_total_length": self.compression_min_total_length
            }
            
            # 执行多Agent协作搜索
            relevant_docs, citations, thinking_results = await orchestrator.execute(
                query=query,
                mode=mode,
                detected_lang=detected_lang,
                conversation_history=conversation_history
            )
            
            logger.info(f"✅ [多Agent模式] 搜索完成: 返回 {len(relevant_docs)} 个文档")
            if thinking_results:
                logger.info(f"🧠 思考结果: {list(thinking_results.keys())}")
            return relevant_docs, citations, thinking_results
            
        except Exception as e:
            logger.error(f"❌ 多Agent搜索失败: {e}", exc_info=True)
            return [], "", {}
    
    async def _search_with_pipeline(
        self,
        query: str,
        mode: str = "speed",
        progress_callback: Optional[callable] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> tuple[List[SearchDocument], str]:
        """使用传统管道模式执行搜索（原有实现）"""
        try:
            detected_lang = detect_language(query)
            all_search_results = []
            keywords_dict = None  # 初始化关键词字典
            
            # 如果有对话历史，构建上下文增强的查询（使用压缩技术）
            enhanced_query = query
            if conversation_history:
                from .momo_utils import compress_conversation_history
                
                # 尝试压缩对话历史（只在历史较长时压缩）
                # 使用配置中的压缩方法
                compressed_context = compress_conversation_history(
                    conversation_history=conversation_history,
                    current_query=query,
                    max_messages=self.compression_max_messages,
                    max_compressed_length=self.compression_max_length,
                    min_total_length=self.compression_min_total_length,
                    compression_method=self.compression_method,
                    api_key=self.zhipu_api_key,
                    model=self.zhipu_model
                )
                
                # 如果配置的方法失败，尝试降级策略
                if not compressed_context and self.compression_method != "rule_based":
                    compressed_context = compress_conversation_history(
                        conversation_history=conversation_history,
                        current_query=query,
                        max_messages=self.compression_max_messages,
                        max_compressed_length=self.compression_max_length,
                        min_total_length=self.compression_min_total_length,
                        compression_method="rule_based"
                    )
                elif not compressed_context and self.compression_method != "smart_truncate":
                    compressed_context = compress_conversation_history(
                        conversation_history=conversation_history,
                        current_query=query,
                        max_messages=self.compression_max_messages,
                        max_compressed_length=self.compression_max_length,
                        min_total_length=self.compression_min_total_length,
                        compression_method="smart_truncate"
                    )
                
                if compressed_context:
                    # 使用压缩后的上下文
                    enhanced_query = f"{query}\n\n上下文信息:\n{compressed_context}"
                    logger.info(f"📚 [管道模式] 已添加压缩后的对话上下文到查询（压缩版本）")
                else:
                    # 如果压缩失败或不需要压缩，使用简单的截断方式
                    recent_history = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
                    context_parts = []
                    for msg in recent_history:
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                        if role == "user" and content and content != query:
                            context_parts.append(f"用户之前提到: {content}")
                        elif role == "assistant" and content:
                            # 只取前200字符的摘要，避免太长
                            content_preview = content[:200] + "..." if len(content) > 200 else content
                            context_parts.append(f"AI之前回答: {content_preview}")
                    
                    if context_parts:
                        context_text = "\n".join(context_parts)
                        enhanced_query = f"{query}\n\n上下文信息:\n{context_text}"
                        logger.info(f"📚 [管道模式] 已添加对话上下文到查询（未压缩版本）")
            
            # 预先计算总步骤数，用于一致的进度显示
            base_steps = 5  # 关键词提取(1) + 向量检索(1) + 深度爬取(1) + 文档分块(1) + 完成(1)
            ddg_steps = 2  # DuckDuckGo 中文 + 英文（最多2步）
            # 初始估算搜索查询数量（通常是2个：中文+英文关键词）
            estimated_search_queries = 2 if self.enable_keyword_extraction else 1
            total_steps = base_steps + estimated_search_queries + ddg_steps
            
            # 步骤0: 关键词提取（如果启用）
            if self.enable_keyword_extraction:
                if progress_callback:
                    await progress_callback(0, total_steps, "提取搜索关键词")
                
                logger.info(f"开始提取关键词: {enhanced_query if enhanced_query != query else query}")
                keywords_dict = extract_keywords(
                    enhanced_query,  # 使用增强的查询（包含上下文）
                    api_key=self.zhipu_api_key,
                    model=self.zhipu_model,
                    conversation_history=conversation_history  # 传递对话历史
                )
                
                # 准备搜索查询列表
                search_queries = []
                
                # 如果检测到是英语，只使用英文搜索，跳过中文搜索
                if detected_lang == "en":
                    if keywords_dict:
                        en_keys = keywords_dict.get("en_keys", "").strip()
                        if en_keys:
                            search_queries.append({
                                "query": en_keys,
                                "language": "en",
                                "source": "keywords_en"
                            })
                            logger.info(f"✅ 提取到英文关键词: {en_keys}")
                    
                    # 如果没有提取到英文关键词，使用原始查询
                    if not search_queries:
                        search_queries.append({
                            "query": query,
                            "language": "en",
                            "source": "original"
                        })
                else:
                    # 中文查询：使用中英文关键词
                    if keywords_dict:
                        zh_keys = keywords_dict.get("zh_keys", "").strip()
                        en_keys = keywords_dict.get("en_keys", "").strip()
                        
                        # 如果提取到中文关键词，添加到搜索列表
                        if zh_keys:
                            search_queries.append({
                                "query": zh_keys,
                                "language": "zh",
                                "source": "keywords_zh"
                            })
                            logger.info(f"✅ 提取到中文关键词: {zh_keys}")
                        
                        # 如果提取到英文关键词，添加到搜索列表
                        if en_keys:
                            search_queries.append({
                                "query": en_keys,
                                "language": "en",
                                "source": "keywords_en"
                            })
                            logger.info(f"✅ 提取到英文关键词: {en_keys}")
                    
                    # 如果关键词提取失败或没有提取到关键词，使用原始查询
                    if not search_queries:
                        logger.warning("⚠️ 关键词提取失败或为空，使用原始查询")
                        search_queries.append({
                            "query": query,
                            "language": detected_lang,
                            "source": "original"
                        })
            else:
                # 未启用关键词提取，使用原始查询
                search_queries = [{
                    "query": query,
                    "language": detected_lang,
                    "source": "original"
                }]
            
            all_search_results = []
            # 重新计算精确的总步骤数（基于实际search_queries数量）
            actual_total_steps = base_steps + len(search_queries) + ddg_steps
            if actual_total_steps != total_steps:
                # 如果实际步数与估算不同，更新total_steps
                total_steps = actual_total_steps
            
            # 步骤1: 使用提取的关键词进行搜索
            for idx, search_item in enumerate(search_queries):
                step_num = idx + 1
                if progress_callback:
                    await progress_callback(step_num, total_steps, f"正在搜索: {search_item['query']} ({search_item['source']})")
                
                logger.info(f"开始搜索: {search_item['query']} (语言: {search_item['language']}, 来源: {search_item['source']})")
                
                search_results = search_searxng(
                    query=search_item['query'],
                    num_results=self.max_search_results,
                    ip_address=self.searxng_url,
                    language=search_item['language'],
                    time_range=self.searxng_time_range,
                    deduplicate_by_url=True
                )
                
                # 合并结果（自动去重）
                seen_urls = {doc.url for doc in all_search_results}
                for doc in search_results:
                    if doc.url not in seen_urls:
                        all_search_results.append(doc)
                        seen_urls.add(doc.url)
                
                logger.info(f"✅ {search_item['source']}搜索完成: 获得{len(search_results)}个结果，总计{len(all_search_results)}个")
            
            # 如果只提取到中文关键词但没有英文关键词，且原始查询是中文，尝试翻译并搜索
            if detected_lang == "zh" and keywords_dict and keywords_dict.get("en_keys") and not any(item['source'] == 'keywords_en' for item in search_queries):
                if progress_callback:
                    await progress_callback(2, total_steps, "🌐 翻译查询并搜索英文结果")
                
                # 翻译原始查询作为补充
                translated_query = translate_text(query, source="zh", target="en")
                
                if translated_query:
                    logger.info(f"🌐 翻译结果: {query} -> {translated_query}")
                    
                    english_search_results = search_searxng(
                        query=translated_query,
                        num_results=self.max_search_results,
                        ip_address=self.searxng_url,
                        language="en",
                        time_range=self.searxng_time_range,
                        deduplicate_by_url=True
                    )
                    
                    # 合并结果（自动去重）
                    seen_urls = {doc.url for doc in all_search_results}
                    for doc in english_search_results:
                        if doc.url not in seen_urls:
                            all_search_results.append(doc)
                            seen_urls.add(doc.url)
                    
                    logger.info(f"✅ 翻译搜索完成: 获得{len(english_search_results)}个新结果，总计{len(all_search_results)}个")
            
            # 步骤2: 使用 DuckDuckGo 进行补充搜索
            # 准备 DuckDuckGo 搜索查询
            ddg_queries = []
            
            if detected_lang == "en":
                # 英语查询：只使用英文，且增加结果数量到40
                if keywords_dict and keywords_dict.get("en_keys"):
                    ddg_queries.append({
                        "query": keywords_dict.get("en_keys"),
                        "language": "en",
                        "source": "ddg_en",
                        "max_results": 40  # 英语查询增加到40条
                    })
                else:
                    ddg_queries.append({
                        "query": query,
                        "language": "en",
                        "source": "ddg_en",
                        "max_results": 40  # 英语查询增加到40条
                    })
            else:
                # 中文查询：使用中英文
                # 如果有中文关键词，使用中文关键词；否则使用原始查询
                if keywords_dict and keywords_dict.get("zh_keys"):
                    ddg_queries.append({
                        "query": keywords_dict.get("zh_keys"),
                        "language": "zh",
                        "source": "ddg_zh",
                        "max_results": 20
                    })
                elif detected_lang == "zh":
                    ddg_queries.append({
                        "query": query,
                        "language": "zh",
                        "source": "ddg_zh",
                        "max_results": 20
                    })
                
                # 如果有英文关键词，使用英文关键词；否则尝试翻译
                if keywords_dict and keywords_dict.get("en_keys"):
                    ddg_queries.append({
                        "query": keywords_dict.get("en_keys"),
                        "language": "en",
                        "source": "ddg_en",
                        "max_results": 40  # 英语查询增加到40条
                    })
                elif detected_lang == "zh":
                    # 中文查询尝试翻译为英文
                    translated_query = translate_text(query, source="zh", target="en")
                    if translated_query:
                        ddg_queries.append({
                            "query": translated_query,
                            "language": "en",
                            "source": "ddg_en_translated",
                            "max_results": 40  # 英语查询增加到40条
                        })
            
            # 执行 DuckDuckGo 搜索
            for idx, ddg_item in enumerate(ddg_queries):
                step_num = len(search_queries) + idx + 1
                if progress_callback:
                    if ddg_item['language'] == 'zh':
                        message = "正在进一步深度搜索..."
                    else:  # en
                        message = "正在扩充搜索英语资料..."
                    await progress_callback(
                        step_num, 
                        total_steps, 
                        message
                    )
                
                logger.info(f"🦆 开始DuckDuckGo搜索: {ddg_item['query']} (语言: {ddg_item['language']})")
                
                # 根据max_results参数决定结果数量（英语40，中文20）
                max_results = ddg_item.get("max_results", 20)
                
                ddg_results = await search_duckduckgo(
                    query=ddg_item['query'],
                    max_results=max_results,
                    language=ddg_item['language'],
                    time_range=self.searxng_time_range if self.searxng_time_range else None
                )
                
                # 合并结果（自动去重）
                seen_urls = {doc.url for doc in all_search_results}
                for doc in ddg_results:
                    if doc.url not in seen_urls:
                        all_search_results.append(doc)
                        seen_urls.add(doc.url)
                
                logger.info(f"✅ DuckDuckGo {ddg_item['source']}搜索完成: 获得{len(ddg_results)}个结果，总计{len(all_search_results)}个")
            
            if not all_search_results:
                logger.warning("⚠️ 所有搜索均未返回结果")
                return [], ""
            
            # 步骤3: 向量检索（合并后的结果）
            vector_step = len(search_queries) + len(ddg_queries) + 1
            if progress_callback:
                await progress_callback(vector_step, total_steps, f"分析相关性 ({len(all_search_results)}个结果)")
            
            # 构建检索查询列表：分开查询中英文，提高匹配精度
            retrieval_queries = [query]  # 总是包含原始查询
            if self.enable_keyword_extraction and keywords_dict:
                en_keys = keywords_dict.get("en_keys", "").strip()
                if en_keys:
                    # 如果有英文关键词，分别查询以提高英文文档匹配度
                    retrieval_queries.append(en_keys)
                    logger.info(f"[向量检索-Pipeline] 使用分开查询: 中文='{query[:50]}...', 英文='{en_keys[:50]}...'")
                else:
                    logger.info(f"[向量检索-Pipeline] 使用原始查询: {query[:100]}")
            else:
                logger.info(f"[向量检索-Pipeline] 使用原始查询: {query[:100]}")
            
            self.retriever.add_documents(all_search_results)
            # 使用多查询检索
            if len(retrieval_queries) > 1:
                relevant_docs = self.retriever.get_relevant_documents_multi_query(retrieval_queries)
            else:
                relevant_docs = self.retriever.get_relevant_documents(retrieval_queries[0])
            
            if not relevant_docs:
                logger.warning("⚠️ 未找到相关文档")
                return [], ""
            
            logger.info(f"✅ 找到{len(relevant_docs)}个相关文档")
            
            # 步骤4: 深度爬取 (仅quality模式)
            if mode == "quality" and self.enable_deep_crawl:
                crawl_step = vector_step + 1
                if progress_callback:
                    await progress_callback(crawl_step, total_steps, f"🕷️ 深度爬取内容 (前{self.max_crawl_docs}个)")
                
                await self.crawler.crawl_many(
                    relevant_docs,
                    score_threshold=self.crawl_score_threshold,
                    max_docs=self.max_crawl_docs
                )
                
                # 步骤5: 文档分块和二次检索
                split_step = crawl_step + 1
                if progress_callback:
                    await progress_callback(split_step, total_steps, "✂️ 文档分块和二次检索")
                
                docs_with_details = expand_docs_by_text_split(relevant_docs)
                self.retriever.add_documents(docs_with_details)
                # 二次检索也使用多查询（retrieval_queries已在上方定义）
                if len(retrieval_queries) > 1:
                    relevant_docs_detailed = self.retriever.get_relevant_documents_multi_query(retrieval_queries)
                else:
                    relevant_docs_detailed = self.retriever.get_relevant_documents(retrieval_queries[0])
                relevant_docs = merge_docs_by_url(relevant_docs_detailed)
                
                logger.info(f"📄 二次检索后: {len(relevant_docs)}个文档")
            
            # 最后一步: 完成
            if progress_callback:
                await progress_callback(total_steps, total_steps, "✅ 搜索完成，正在生成内容")
                # 额外发送文档数量信息
                await progress_callback(total_steps + 1, total_steps + 1, f"找到{len(relevant_docs)}篇相关文档")
            
            # 生成引用信息
            citations = self.format_citations(relevant_docs)
            
            logger.info(f"✅ Momo搜索完成: 返回{len(relevant_docs)}个文档 (语言: {detected_lang})")
            return relevant_docs, citations
            
        except Exception as e:
            logger.error(f"❌ Momo搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], ""
    
    async def process(self, query: str, mode: str = "speed") -> Dict:
        """
        处理搜索请求（同步接口）
        
        Args:
            query: 搜索查询
            mode: 搜索模式
        
        Returns:
            包含搜索结果的字典
        """
        relevant_docs, citations = await self.search_with_progress(query, mode)
        
        if not relevant_docs:
            return {
                "success": False,
                "message": "未找到相关结果"
            }
        
        # 格式化为LLM上下文
        context = self.format_sources_for_llm(relevant_docs)
        
        return {
            "success": True,
            "context": context,
            "citations": citations,
            "num_results": len(relevant_docs),
            "documents": relevant_docs
        }
    
    async def cleanup(self):
        """清理资源"""
        # 释放embedding模型引用
        if hasattr(self, '_embedding_model_name'):
            self._release_embedding_model(
                self._embedding_model_name,
                self._embedding_device,
                self._embedding_torch_dtype
            )
        
        if hasattr(self, 'crawler'):
            await self.crawler.close()
        logger.info("🧹 Momo Search Handler 资源已清理")
    
    def __del__(self):
        """析构函数"""
        # 注意：在异步环境中，析构函数中的异步调用可能不会执行
        # 但在Python退出时仍可能被调用，用于释放资源
        pass
