"""
Momo Search Multi-Agent Framework
多Agent协作搜索框架
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time
from loguru import logger


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """Agent之间的消息"""
    sender: str
    receiver: str
    message_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class BaseAgent(ABC):
    """基础Agent类"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.status = AgentStatus.IDLE
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        
    @abstractmethod
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理输入数据
        
        Args:
            input_data: 输入数据
            context: 上下文信息（可能包含其他Agent的结果）
            
        Returns:
            处理结果
        """
        pass
    
    async def send_message(self, receiver: 'BaseAgent', message_type: str, data: Dict[str, Any]):
        """向其他Agent发送消息"""
        message = AgentMessage(
            sender=self.name,
            receiver=receiver.name,
            message_type=message_type,
            data=data
        )
        await receiver.message_queue.put(message)
        logger.debug(f"📨 [{self.name}] -> [{receiver.name}]: {message_type}")
    
    async def receive_message(self, timeout: float = None) -> Optional[AgentMessage]:
        """接收消息"""
        try:
            return await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    def set_status(self, status: AgentStatus):
        """设置状态"""
        self.status = status
        logger.debug(f"🤖 [{self.name}] 状态: {status.value}")
    
    def reset(self):
        """重置Agent状态"""
        self.status = AgentStatus.IDLE
        self.result = None
        self.error = None
        # 清空消息队列
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except:
                pass


class KeywordExtractionAgent(BaseAgent):
    """关键词提取Agent"""
    
    def __init__(self, zhipu_api_key: str, zhipu_model: str = "glm-4.5-flash"):
        super().__init__(
            name="keyword_extractor",
            description="提取搜索关键词（中英文）"
        )
        self.zhipu_api_key = zhipu_api_key
        self.zhipu_model = zhipu_model
    
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """提取关键词"""
        self.set_status(AgentStatus.PROCESSING)
        
        try:
            query = input_data.get("query", "")
            if not query:
                raise ValueError("查询为空")
            
            from .momo_utils import extract_keywords
            
            logger.info(f"🔑 [{self.name}] 开始提取关键词: {query}")
            keywords_dict = extract_keywords(
                query,
                api_key=self.zhipu_api_key,
                model=self.zhipu_model
            )
            
            if keywords_dict:
                zh_keys = keywords_dict.get("zh_keys", "").strip()
                en_keys = keywords_dict.get("en_keys", "").strip()
                
                result = {
                    "success": True,
                    "keywords": {
                        "zh": zh_keys,
                        "en": en_keys
                    },
                    "raw": keywords_dict
                }
                
                logger.info(f"✅ [{self.name}] 提取成功: 中文={zh_keys}, 英文={en_keys}")
            else:
                result = {
                    "success": False,
                    "keywords": None,
                    "message": "关键词提取失败"
                }
                logger.warning(f"⚠️ [{self.name}] 提取失败")
            
            self.result = result
            self.set_status(AgentStatus.COMPLETED)
            return result
            
        except Exception as e:
            self.error = str(e)
            self.set_status(AgentStatus.FAILED)
            logger.error(f"❌ [{self.name}] 处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class SearchAgent(BaseAgent):
    """搜索Agent - 负责执行搜索引擎查询"""
    
    def __init__(self, searxng_url: str, searxng_language: str = "zh", 
                 searxng_time_range: str = "day", max_results: int = 50):
        super().__init__(
            name="searcher",
            description="执行搜索引擎查询（SearXNG + DuckDuckGo）"
        )
        self.searxng_url = searxng_url
        self.searxng_language = searxng_language
        self.searxng_time_range = searxng_time_range
        self.max_results = max_results
    
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行搜索"""
        self.set_status(AgentStatus.PROCESSING)
        
        try:
            queries = input_data.get("queries", [])  # [{query, language, source}, ...]
            all_results = []
            
            from .momo_utils import search_searxng, search_duckduckgo, SearchDocument
            
            # 执行SearXNG搜索
            for search_item in queries:
                if search_item.get("source", "").startswith("ddg"):
                    continue  # DuckDuckGo查询跳过
                
                logger.info(f"🔍 [{self.name}] SearXNG搜索: {search_item['query']} ({search_item['language']})")
                
                results = search_searxng(
                    query=search_item['query'],
                    num_results=self.max_results,
                    ip_address=self.searxng_url,
                    language=search_item['language'],
                    time_range=self.searxng_time_range,
                    deduplicate_by_url=True
                )
                
                # 去重合并
                seen_urls = {doc.url for doc in all_results}
                for doc in results:
                    if doc.url not in seen_urls:
                        all_results.append(doc)
                        seen_urls.add(doc.url)
                
                logger.info(f"✅ [{self.name}] SearXNG完成: +{len(results)}个结果, 总计{len(all_results)}个")
            
            # 执行DuckDuckGo搜索
            ddg_queries = [q for q in queries if q.get("source", "").startswith("ddg")]
            for ddg_item in ddg_queries:
                logger.info(f"🦆 [{self.name}] DuckDuckGo搜索: {ddg_item['query']} ({ddg_item['language']})")
                
                ddg_results = await search_duckduckgo(
                    query=ddg_item['query'],
                    max_results=20,
                    language=ddg_item['language'],
                    time_range=self.searxng_time_range if self.searxng_time_range else None
                )
                
                # 去重合并
                seen_urls = {doc.url for doc in all_results}
                for doc in ddg_results:
                    if doc.url not in seen_urls:
                        all_results.append(doc)
                        seen_urls.add(doc.url)
                
                logger.info(f"✅ [{self.name}] DuckDuckGo完成: +{len(ddg_results)}个结果, 总计{len(all_results)}个")
            
            result = {
                "success": True,
                "results": all_results,
                "count": len(all_results)
            }
            
            self.result = result
            self.set_status(AgentStatus.COMPLETED)
            return result
            
        except Exception as e:
            self.error = str(e)
            self.set_status(AgentStatus.FAILED)
            logger.error(f"❌ [{self.name}] 处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }


class RetrievalAgent(BaseAgent):
    """检索Agent - 负责向量检索和相关性分析"""
    
    def __init__(self, retriever, sim_threshold: float = 0.45):
        super().__init__(
            name="retriever",
            description="向量检索和相关性分析"
        )
        self.retriever = retriever
        self.sim_threshold = sim_threshold
    
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行向量检索"""
        self.set_status(AgentStatus.PROCESSING)
        
        try:
            query = input_data.get("query", "")
            documents = input_data.get("documents", [])
            
            if not query or not documents:
                raise ValueError("查询或文档为空")
            
            logger.info(f"📊 [{self.name}] 开始分析相关性: {len(documents)}个文档")
            
            # 添加文档到检索器
            self.retriever.add_documents(documents)
            
            # 检索相关文档
            relevant_docs = self.retriever.get_relevant_documents(query)
            
            if not relevant_docs:
                logger.warning(f"⚠️ [{self.name}] 未找到相关文档")
                result = {
                    "success": False,
                    "results": [],
                    "count": 0,
                    "message": "未找到相关文档"
                }
            else:
                logger.info(f"✅ [{self.name}] 找到{len(relevant_docs)}个相关文档")
                result = {
                    "success": True,
                    "results": relevant_docs,
                    "count": len(relevant_docs)
                }
            
            self.result = result
            self.set_status(AgentStatus.COMPLETED)
            return result
            
        except Exception as e:
            self.error = str(e)
            self.set_status(AgentStatus.FAILED)
            logger.error(f"❌ [{self.name}] 处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }


class CrawlerAgent(BaseAgent):
    """爬取Agent - 负责深度爬取网页内容"""
    
    def __init__(self, crawler, score_threshold: float = 0.5, max_docs: int = 10):
        super().__init__(
            name="crawler",
            description="深度爬取网页内容"
        )
        self.crawler = crawler
        self.score_threshold = score_threshold
        self.max_docs = max_docs
    
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行深度爬取"""
        self.set_status(AgentStatus.PROCESSING)
        
        try:
            documents = input_data.get("documents", [])
            
            if not documents:
                logger.warning(f"⚠️ [{self.name}] 无文档需要爬取")
                return {
                    "success": True,
                    "results": [],
                    "count": 0
                }
            
            logger.info(f"🕷️ [{self.name}] 开始深度爬取: {len(documents)}个文档")
            
            # 执行爬取
            await self.crawler.crawl_many(
                documents,
                score_threshold=self.score_threshold,
                max_docs=self.max_docs
            )
            
            # 爬取后的文档（crawler会更新文档的content字段）
            result = {
                "success": True,
                "results": documents,
                "count": len(documents)
            }
            
            logger.info(f"✅ [{self.name}] 爬取完成: {len(documents)}个文档")
            
            self.result = result
            self.set_status(AgentStatus.COMPLETED)
            return result
            
        except Exception as e:
            self.error = str(e)
            self.set_status(AgentStatus.FAILED)
            logger.error(f"❌ [{self.name}] 处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": documents if 'documents' in locals() else []
            }


class DocumentProcessorAgent(BaseAgent):
    """文档处理Agent - 负责文档分块和二次检索"""
    
    def __init__(self, retriever):
        super().__init__(
            name="document_processor",
            description="文档分块和二次检索"
        )
        self.retriever = retriever
    
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理文档"""
        self.set_status(AgentStatus.PROCESSING)
        
        try:
            query = input_data.get("query", "")
            documents = input_data.get("documents", [])
            
            if not query or not documents:
                raise ValueError("查询或文档为空")
            
            logger.info(f"✂️ [{self.name}] 开始文档分块和二次检索: {len(documents)}个文档")
            
            from .momo_retriever import expand_docs_by_text_split, merge_docs_by_url
            
            # 文档分块
            docs_with_details = expand_docs_by_text_split(documents)
            
            # 添加到检索器
            self.retriever.add_documents(docs_with_details)
            
            # 二次检索
            relevant_docs_detailed = self.retriever.get_relevant_documents(query)
            
            # 合并文档
            relevant_docs = merge_docs_by_url(relevant_docs_detailed)
            
            logger.info(f"✅ [{self.name}] 处理完成: {len(relevant_docs)}个文档")
            
            result = {
                "success": True,
                "results": relevant_docs,
                "count": len(relevant_docs)
            }
            
            self.result = result
            self.set_status(AgentStatus.COMPLETED)
            return result
            
        except Exception as e:
            self.error = str(e)
            self.set_status(AgentStatus.FAILED)
            logger.error(f"❌ [{self.name}] 处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": documents if 'documents' in locals() else []
            }


class SearchOrchestrator:
    """搜索协调器 - 管理多个Agent的协作"""
    
    def __init__(self, agents: Dict[str, BaseAgent], progress_callback: Optional[Callable] = None):
        self.agents = agents
        self.progress_callback = progress_callback
        self.total_steps = 0
        self.current_step = 0
    
    async def execute(self, query: str, mode: str = "speed", detected_lang: str = "zh") -> tuple[List, str]:
        """
        执行多Agent协作搜索
        
        Args:
            query: 搜索查询
            mode: 搜索模式 (speed/quality)
            detected_lang: 检测到的语言
            
        Returns:
            (相关文档列表, 引用信息)
        """
        try:
            # 计算总步骤数
            self._calculate_steps(mode)
            
            # Agent 1: 关键词提取
            keyword_agent = self.agents.get("keyword_extractor")
            if keyword_agent:
                await self._report_progress(0, "🔑 提取搜索关键词")
                keyword_result = await keyword_agent.process({"query": query})
                
                if not keyword_result.get("success"):
                    logger.warning("关键词提取失败，使用原始查询")
                    keyword_result = {"keywords": {"zh": query, "en": ""}}
            else:
                keyword_result = {"keywords": {"zh": query, "en": ""}}
            
            # 准备搜索查询列表
            search_queries = []
            keywords = keyword_result.get("keywords", {})
            
            if keywords.get("zh"):
                search_queries.append({
                    "query": keywords["zh"],
                    "language": "zh",
                    "source": "keywords_zh"
                })
            
            if keywords.get("en"):
                search_queries.append({
                    "query": keywords["en"],
                    "language": "en",
                    "source": "keywords_en"
                })
            
            if not search_queries:
                search_queries.append({
                    "query": query,
                    "language": detected_lang,
                    "source": "original"
                })
            
            # 准备DuckDuckGo查询
            ddg_queries = []
            if keywords.get("zh"):
                ddg_queries.append({
                    "query": keywords["zh"],
                    "language": "zh",
                    "source": "ddg_zh"
                })
            if keywords.get("en"):
                ddg_queries.append({
                    "query": keywords["en"],
                    "language": "en",
                    "source": "ddg_en"
                })
            elif detected_lang == "zh":
                # 尝试翻译
                from .momo_utils import translate_text
                translated = translate_text(query, source="zh", target="en")
                if translated:
                    ddg_queries.append({
                        "query": translated,
                        "language": "en",
                        "source": "ddg_en_translated"
                    })
            
            # Agent 2: 搜索
            search_agent = self.agents.get("searcher")
            # 初始化步骤计数器
            current_step = 1
            all_documents = []
            
            if search_agent:
                # 逐个执行搜索并报告进度
                
                # 执行SearXNG搜索
                for sq in search_queries:
                    await self._report_progress(
                        current_step,
                        f"🔍 正在搜索: {sq['query']} ({sq['source']})"
                    )
                    # 单个查询搜索
                    single_result = await search_agent.process({"queries": [sq]})
                    docs = single_result.get("results", [])
                    # 去重合并
                    seen_urls = {doc.url for doc in all_documents}
                    for doc in docs:
                        if doc.url not in seen_urls:
                            all_documents.append(doc)
                            seen_urls.add(doc.url)
                    current_step += 1
                
                # 执行DuckDuckGo搜索
                for dq in ddg_queries:
                    if dq['language'] == 'zh':
                        message = "正在进一步深度搜索..."
                    else:
                        message = "正在扩充搜索英语资料..."
                    await self._report_progress(current_step, message)
                    # 单个查询搜索
                    single_result = await search_agent.process({"queries": [dq]})
                    docs = single_result.get("results", [])
                    # 去重合并
                    seen_urls = {doc.url for doc in all_documents}
                    for doc in docs:
                        if doc.url not in seen_urls:
                            all_documents.append(doc)
                            seen_urls.add(doc.url)
                    current_step += 1
            else:
                all_documents = []
            
            if not all_documents:
                logger.warning("⚠️ 搜索未返回结果")
                return [], ""
            
            # Agent 3: 向量检索
            retrieval_agent = self.agents.get("retriever")
            if retrieval_agent:
                vector_step = current_step
                await self._report_progress(
                    vector_step,
                    f"📊 分析相关性 ({len(all_documents)}个结果)"
                )
                
                retrieval_result = await retrieval_agent.process({
                    "query": query,
                    "documents": all_documents
                })
                relevant_docs = retrieval_result.get("results", [])
            else:
                relevant_docs = all_documents
            
            if not relevant_docs:
                logger.warning("⚠️ 未找到相关文档")
                return [], ""
            
            # Agent 4: 深度爬取（仅quality模式）
            if mode == "quality":
                crawler_agent = self.agents.get("crawler")
                if crawler_agent:
                    crawl_step = vector_step + 1
                    await self._report_progress(
                        crawl_step,
                        f"🕷️ 深度爬取内容 (前{len(relevant_docs)}个)"
                    )
                    
                    await crawler_agent.process({"documents": relevant_docs})
                    
                    # Agent 5: 文档处理
                    processor_agent = self.agents.get("document_processor")
                    if processor_agent:
                        split_step = crawl_step + 1
                        await self._report_progress(split_step, "✂️ 文档分块和二次检索")
                        
                        processor_result = await processor_agent.process({
                            "query": query,
                            "documents": relevant_docs
                        })
                        relevant_docs = processor_result.get("results", relevant_docs)
            
            # 完成
            final_step = self.total_steps
            await self._report_progress(final_step, "✅ 搜索完成，正在生成内容")
            await self._report_progress(final_step + 1, f"找到{len(relevant_docs)}篇相关文档")
            
            # 生成引用信息（使用静态方法或直接实现）
            citations = self._format_citations(relevant_docs)
            
            logger.info(f"✅ 多Agent搜索完成: 返回{len(relevant_docs)}个文档")
            return relevant_docs, citations
            
        except Exception as e:
            logger.error(f"❌ 多Agent搜索失败: {e}", exc_info=True)
            return [], ""
    
    def _calculate_steps(self, mode: str):
        """计算总步骤数"""
        base_steps = 5  # 关键词(1) + 向量检索(1) + 深度爬取(1) + 文档分块(1) + 完成(1)
        search_steps = 2  # 估算：中文+英文关键词搜索
        ddg_steps = 2  # DuckDuckGo中英文
        
        if mode == "quality":
            self.total_steps = base_steps + search_steps + ddg_steps
        else:
            self.total_steps = base_steps + search_steps + ddg_steps - 2  # 无爬取和分块
        
        self.current_step = 0
    
    async def _report_progress(self, step: int, message: str):
        """报告进度"""
        self.current_step = step
        if self.progress_callback:
            await self.progress_callback(step, self.total_steps, message)
    
    def _format_citations(self, documents: List) -> str:
        """生成引用信息"""
        if not documents:
            return ""
        
        citations = []
        for idx, doc in enumerate(documents[:10], 1):  # 最多10个引用
            title = doc.title if hasattr(doc, 'title') else 'N/A'
            url = doc.url if hasattr(doc, 'url') else 'N/A'
            citations.append(f"{idx}. [{title}]({url})")
        
        return "\n".join(citations)

