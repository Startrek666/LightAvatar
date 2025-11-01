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
    FaissRetriever, 
    convert_to_markdown,
    detect_language,
    translate_text
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
            
            logger.info("🚀 初始化 Momo Search Handler...")
            logger.info(f"  SearXNG: {self.searxng_url}")
            logger.info(f"  语言: {self.searxng_language}")
            logger.info(f"  时间范围: {self.searxng_time_range}")
            logger.info(f"  嵌入模型: {embedding_model_name}")
            logger.info(f"  深度爬取: {'开启' if self.enable_deep_crawl else '关闭'}")
            
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
            # 步骤0: 检测语言并决定搜索策略
            detected_lang = detect_language(query)
            logger.info(f"🔍 检测到查询语言: {detected_lang} (查询: {query})")
            
            all_search_results = []
            total_steps = 6 if detected_lang == "zh" else 5  # 中文需要额外翻译步骤
            
            # 步骤1: 首次搜索（根据检测到的语言）
            if progress_callback:
                await progress_callback(1, total_steps, f"🔍 正在搜索: {query}")
            
            logger.info(f"🔍 开始Momo搜索: {query} (模式: {mode}, 语言: {detected_lang})")
            
            # 首次搜索：使用检测到的语言
            first_search_results = search_searxng(
                query=query,
                num_results=self.max_search_results,
                ip_address=self.searxng_url,
                language=detected_lang,
                time_range=self.searxng_time_range,
                deduplicate_by_url=True
            )
            
            all_search_results.extend(first_search_results)
            logger.info(f"✅ 首次搜索完成: 获得{len(first_search_results)}个结果")
            
            # 步骤2: 如果是中文，翻译并再次搜索
            if detected_lang == "zh":
                if progress_callback:
                    await progress_callback(2, total_steps, "🌐 翻译查询并搜索英文结果")
                
                # 翻译查询
                translated_query = translate_text(query, source="zh", target="en")
                
                if translated_query:
                    logger.info(f"🌐 翻译结果: {query} -> {translated_query}")
                    
                    # 使用英文查询再次搜索
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
                    
                    logger.info(f"✅ 英文搜索完成: 获得{len(english_search_results)}个新结果，总计{len(all_search_results)}个")
                else:
                    logger.warning("⚠️ 翻译失败，跳过英文搜索")
            else:
                logger.info("ℹ️ 查询为英文，跳过翻译步骤")
            
            if not all_search_results:
                logger.warning("⚠️ 所有搜索均未返回结果")
                return [], ""
            
            # 步骤3: 向量检索（合并后的结果）
            step_num = 3 if detected_lang == "zh" else 2
            if progress_callback:
                await progress_callback(step_num, total_steps, f"📊 分析相关性 ({len(all_search_results)}个结果)")
            
            self.retriever.add_documents(all_search_results)
            relevant_docs = self.retriever.get_relevant_documents(query)
            
            if not relevant_docs:
                logger.warning("⚠️ 未找到相关文档")
                return [], ""
            
            logger.info(f"✅ 找到{len(relevant_docs)}个相关文档")
            
            # 步骤4: 深度爬取 (仅quality模式)
            step_num = 4 if detected_lang == "zh" else 3
            if mode == "quality" and self.enable_deep_crawl:
                if progress_callback:
                    await progress_callback(step_num, total_steps, f"🕷️ 深度爬取内容 (前{self.max_crawl_docs}个)")
                
                await self.crawler.crawl_many(
                    relevant_docs,
                    score_threshold=self.crawl_score_threshold,
                    max_docs=self.max_crawl_docs
                )
                
                # 步骤5: 文档分块和二次检索
                step_num = 5 if detected_lang == "zh" else 4
                if progress_callback:
                    await progress_callback(step_num, total_steps, "✂️ 文档分块和二次检索")
                
                docs_with_details = expand_docs_by_text_split(relevant_docs)
                self.retriever.add_documents(docs_with_details)
                relevant_docs_detailed = self.retriever.get_relevant_documents(query)
                relevant_docs = merge_docs_by_url(relevant_docs_detailed)
                
                logger.info(f"📄 二次检索后: {len(relevant_docs)}个文档")
            
            # 最后一步: 完成
            final_step = total_steps
            if progress_callback:
                await progress_callback(final_step, total_steps, "✅ 搜索完成")
            
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



