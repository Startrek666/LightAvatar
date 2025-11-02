"""
Momo Search Handler - 高级联网搜索处理器
集成 Momo-Search 的完整功能
"""
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime
import asyncio

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


class MomoSearchHandler(BaseHandler):
    """Momo 高级搜索处理器"""
    
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
            
            # 初始化嵌入模型
            # CPU不支持float16，使用float32
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            try:
                if device == "cuda":
                    # GPU可以使用float16加速
                    self.embedding_model = SentenceTransformer(
                        embedding_model_name,
                        device=device,
                        model_kwargs={"torch_dtype": torch.float16}
                    )
                else:
                    # CPU必须使用float32
                    self.embedding_model = SentenceTransformer(
                        embedding_model_name,
                        device=device,
                        model_kwargs={"torch_dtype": torch.float32}
                    )
                logger.info(f"✅ 嵌入模型加载成功: {embedding_model_name} (设备: {device})")
            except Exception as e:
                logger.error(f"❌ 嵌入模型加载失败: {e}")
                logger.info("ℹ️ 尝试使用默认设置...")
                self.embedding_model = SentenceTransformer(embedding_model_name, device=device)
            
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
        progress_callback: Optional[callable] = None
    ) -> tuple[List[SearchDocument], str]:
        """
        执行搜索并报告进度
        
        Args:
            query: 搜索查询
            mode: 搜索模式 (speed/quality)
            progress_callback: 进度回调函数
        
        Returns:
            (相关文档列表, 引用信息)
        """
        try:
            detected_lang = detect_language(query)
            all_search_results = []
            keywords_dict = None  # 初始化关键词字典
            
            # 预先计算总步骤数，用于一致的进度显示
            base_steps = 5  # 关键词提取(1) + 向量检索(1) + 深度爬取(1) + 文档分块(1) + 完成(1)
            ddg_steps = 2  # DuckDuckGo 中文 + 英文（最多2步）
            # 初始估算搜索查询数量（通常是2个：中文+英文关键词）
            estimated_search_queries = 2 if self.enable_keyword_extraction else 1
            total_steps = base_steps + estimated_search_queries + ddg_steps
            
            # 步骤0: 关键词提取（如果启用）
            if self.enable_keyword_extraction:
                if progress_callback:
                    await progress_callback(0, total_steps, "🔑 提取搜索关键词")
                
                logger.info(f"🔑 开始提取关键词: {query}")
                keywords_dict = extract_keywords(
                    query,
                    api_key=self.zhipu_api_key,
                    model=self.zhipu_model
                )
                
                # 准备搜索查询列表
                search_queries = []
                
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
                    await progress_callback(step_num, total_steps, f"🔍 正在搜索: {search_item['query']} ({search_item['source']})")
                
                logger.info(f"🔍 开始搜索: {search_item['query']} (语言: {search_item['language']}, 来源: {search_item['source']})")
                
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
            
            # 步骤2: 使用 DuckDuckGo 进行补充搜索（中英文各20条）
            # 准备 DuckDuckGo 搜索查询
            ddg_queries = []
            
            # 如果有中文关键词，使用中文关键词；否则使用原始查询
            if keywords_dict and keywords_dict.get("zh_keys"):
                ddg_queries.append({
                    "query": keywords_dict.get("zh_keys"),
                    "language": "zh",
                    "source": "ddg_zh"
                })
            elif detected_lang == "zh":
                ddg_queries.append({
                    "query": query,
                    "language": "zh",
                    "source": "ddg_zh"
                })
            
            # 如果有英文关键词，使用英文关键词；否则尝试翻译
            if keywords_dict and keywords_dict.get("en_keys"):
                ddg_queries.append({
                    "query": keywords_dict.get("en_keys"),
                    "language": "en",
                    "source": "ddg_en"
                })
            elif detected_lang == "en":
                ddg_queries.append({
                    "query": query,
                    "language": "en",
                    "source": "ddg_en"
                })
            elif detected_lang == "zh":
                # 中文查询尝试翻译为英文
                translated_query = translate_text(query, source="zh", target="en")
                if translated_query:
                    ddg_queries.append({
                        "query": translated_query,
                        "language": "en",
                        "source": "ddg_en_translated"
                    })
            
            # 执行 DuckDuckGo 搜索
            for idx, ddg_item in enumerate(ddg_queries):
                step_num = len(search_queries) + idx + 1
                if progress_callback:
                    await progress_callback(
                        step_num, 
                        total_steps, 
                        f"🦆 DuckDuckGo {ddg_item['language']}搜索"
                    )
                
                logger.info(f"🦆 开始DuckDuckGo搜索: {ddg_item['query']} (语言: {ddg_item['language']})")
                
                ddg_results = await search_duckduckgo(
                    query=ddg_item['query'],
                    max_results=20,
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
                await progress_callback(vector_step, total_steps, f"📊 分析相关性 ({len(all_search_results)}个结果)")
            
            self.retriever.add_documents(all_search_results)
            relevant_docs = self.retriever.get_relevant_documents(query)
            
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
                relevant_docs_detailed = self.retriever.get_relevant_documents(query)
                relevant_docs = merge_docs_by_url(relevant_docs_detailed)
                
                logger.info(f"📄 二次检索后: {len(relevant_docs)}个文档")
            
            # 最后一步: 完成
            if progress_callback:
                await progress_callback(total_steps, total_steps, "✅ 搜索完成，正在生成内容")
            
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
        if hasattr(self, 'crawler'):
            await self.crawler.close()
        logger.info("🧹 Momo Search Handler 资源已清理")
    
    def __del__(self):
        """析构函数"""
        # 注意：在异步环境中，析构函数中的异步调用可能不会执行
        pass



