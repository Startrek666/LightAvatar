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
            
            logger.info(f"[{self.name}] 开始提取关键词: {query}")
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
            logger.info(f"✅ [{self.name}] Agent已完成")
            return result
            
        except Exception as e:
            self.error = str(e)
            self.set_status(AgentStatus.FAILED)
            logger.error(f"❌ [{self.name}] Agent处理失败: {e}")
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
                
                # 使用查询项中指定的max_results，如果没有则使用默认值
                num_results = search_item.get("max_results", self.max_results)
                
                results = search_searxng(
                    query=search_item['query'],
                    num_results=num_results,
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
                
                # 根据max_results参数决定结果数量（英语40，中文20）
                max_results = ddg_item.get("max_results", 20)
                
                ddg_results = await search_duckduckgo(
                    query=ddg_item['query'],
                    max_results=max_results,
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
            logger.info(f"✅ [{self.name}] Agent已完成: 总计获得 {len(all_results)} 个搜索结果")
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
            queries = input_data.get("queries", [])  # 支持多查询
            documents = input_data.get("documents", [])
            
            # 兼容性：如果没有queries，使用query
            if not queries and query:
                queries = [query]
            
            if not queries or not documents:
                raise ValueError("查询或文档为空")
            
            logger.info(f"[{self.name}] 开始分析相关性: {len(documents)}个文档, {len(queries)}个查询")
            
            # 添加文档到检索器
            self.retriever.add_documents(documents)
            
            # 检索相关文档（支持多查询）
            if len(queries) > 1:
                # 多个查询：分开检索并合并结果
                relevant_docs = self.retriever.get_relevant_documents_multi_query(queries)
            else:
                # 单个查询：使用原有方法
                relevant_docs = self.retriever.get_relevant_documents(queries[0])
            
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
            logger.info(f"✅ [{self.name}] Agent已完成: 找到 {len(relevant_docs)} 个相关文档")
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
            logger.info(f"✅ [{self.name}] Agent已完成: 爬取了 {len(documents)} 个文档")
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


class ProblemUnderstandingAgent(BaseAgent):
    """问题理解Agent - 深度理解用户问题"""
    
    def __init__(self, zhipu_api_key: str, zhipu_model: str = "glm-4.5-flash"):
        super().__init__(
            name="problem_understanding",
            description="深度理解用户问题"
        )
        self.zhipu_api_key = zhipu_api_key
        self.zhipu_model = zhipu_model
    
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """理解问题"""
        self.set_status(AgentStatus.PROCESSING)
        
        try:
            query = input_data.get("query", "")
            if not query:
                raise ValueError("查询为空")
            
            from datetime import datetime
            from .momo_utils import call_zhipu_llm
            
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            prompt = f"""今天是{current_date}。请深入理解用户的问题，分析问题的核心需求、背景和上下文。

用户问题：{query}

请从以下角度进行分析：
1. 用户的核心需求是什么？
2. 问题的背景和上下文是什么？
3. 用户可能想要什么样的回答？（信息、分析、建议、对比等）
4. 这个问题涉及哪些关键概念和领域？

请用简洁清晰的语言输出你的理解，控制在200字以内。"""
            
            logger.info(f"[{self.name}] 开始理解问题: {query}")
            understanding = call_zhipu_llm(
                prompt=prompt,
                api_key=self.zhipu_api_key,
                model=self.zhipu_model,
                temperature=0.7,
                max_tokens=500
            )
            
            if understanding:
                result = {
                    "success": True,
                    "understanding": understanding
                }
                logger.info(f"✅ [{self.name}] 理解完成")
            else:
                result = {
                    "success": False,
                    "understanding": None,
                    "message": "问题理解失败"
                }
                logger.warning(f"⚠️ [{self.name}] 理解失败")
            
            self.result = result
            self.set_status(AgentStatus.COMPLETED)
            return result
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] 处理失败: {e}", exc_info=True)
            self.set_status(AgentStatus.FAILED)
            return {
                "success": False,
                "understanding": None,
                "message": str(e)
            }


class MaterialAnalysisAgent(BaseAgent):
    """资料分析Agent - 批判性分析搜索结果"""
    
    def __init__(self, zhipu_api_key: str, zhipu_model: str = "glm-4.5-flash", analysis_score_threshold: float = 0.5):
        super().__init__(
            name="material_analysis",
            description="批判性分析搜索结果"
        )
        self.zhipu_api_key = zhipu_api_key
        self.zhipu_model = zhipu_model
        self.analysis_score_threshold = analysis_score_threshold  # 资料分析的相似度阈值
    
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """分析资料"""
        self.set_status(AgentStatus.PROCESSING)
        
        try:
            query = input_data.get("query", "")
            documents = input_data.get("documents", [])
            understanding = input_data.get("understanding", "")  # 从前面的步骤获取
            
            if not query or not documents:
                raise ValueError("查询或文档为空")
            
            from .momo_utils import call_zhipu_llm
            
            # 根据相似度阈值进一步筛选文档（不限制数量，但提高质量）
            filtered_docs = []
            for doc in documents:
                score = getattr(doc, 'score', 0.0)
                if score >= self.analysis_score_threshold:
                    filtered_docs.append(doc)
            
            if not filtered_docs:
                logger.warning(f"⚠️ [{self.name}] 没有文档达到分析阈值 ({self.analysis_score_threshold})，使用所有文档")
                filtered_docs = documents
            
            # 按相似度分数排序（从高到低）
            filtered_docs.sort(key=lambda x: getattr(x, 'score', 0.0), reverse=True)
            
            # 构建资料摘要（不限制数量，使用所有通过阈值的文档）
            materials_summary = []
            for idx, doc in enumerate(filtered_docs, 1):
                title = doc.title if hasattr(doc, 'title') else 'N/A'
                content = doc.content if hasattr(doc, 'content') else ''
                if not content and hasattr(doc, 'snippet'):
                    content = doc.snippet
                # 限制内容长度
                content = content[:500] if len(content) > 500 else content
                score = getattr(doc, 'score', 0.0)
                materials_summary.append(f"[资料{idx}] 标题: {title}\n相似度: {score:.3f}\n内容: {content}\n")
            
            materials_text = "\n".join(materials_summary)
            
            understanding_context = f"\n之前对问题的理解：{understanding}\n" if understanding else ""
            
            prompt = f"""请对以下搜索结果进行批判性分析。

用户问题：{query}
{understanding_context}
搜索结果：
{materials_text}

请从以下角度进行分析：
1. 哪些资料最相关？为什么？
2. 不同资料之间有什么一致性和差异？
3. 资料的可靠性和权威性如何？
4. 哪些信息可能过时或不准确？
5. 是否存在观点冲突？如何理解这些冲突？

请用简洁清晰的语言输出你的分析，控制在300字以内。"""
            
            logger.info(f"[{self.name}] 开始分析资料: {len(documents)}个文档 -> {len(filtered_docs)}个文档（阈值>={self.analysis_score_threshold}）")
            analysis = call_zhipu_llm(
                prompt=prompt,
                api_key=self.zhipu_api_key,
                model=self.zhipu_model,
                temperature=0.7,
                max_tokens=800
            )
            
            if analysis:
                result = {
                    "success": True,
                    "analysis": analysis
                }
                logger.info(f"✅ [{self.name}] 分析完成")
            else:
                result = {
                    "success": False,
                    "analysis": None,
                    "message": "资料分析失败"
                }
                logger.warning(f"⚠️ [{self.name}] 分析失败")
            
            self.result = result
            self.set_status(AgentStatus.COMPLETED)
            return result
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] 处理失败: {e}", exc_info=True)
            self.set_status(AgentStatus.FAILED)
            return {
                "success": False,
                "analysis": None,
                "message": str(e)
            }


class DeepThinkingAgent(BaseAgent):
    """深度思考Agent - 进行深度推理和思考"""
    
    def __init__(self, zhipu_api_key: str, zhipu_model: str = "glm-4.5-flash"):
        super().__init__(
            name="deep_thinking",
            description="深度思考与推理"
        )
        self.zhipu_api_key = zhipu_api_key
        self.zhipu_model = zhipu_model
    
    async def process(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """深度思考"""
        self.set_status(AgentStatus.PROCESSING)
        
        try:
            query = input_data.get("query", "")
            understanding = input_data.get("understanding", "")
            analysis = input_data.get("analysis", "")
            
            if not query:
                raise ValueError("查询为空")
            
            from .momo_utils import call_zhipu_llm
            
            understanding_context = f"\n问题理解：{understanding}\n" if understanding else ""
            analysis_context = f"\n资料分析：{analysis}\n" if analysis else ""
            
            prompt = f"""基于以下信息进行深度思考与推理。

用户问题：{query}
{understanding_context}
{analysis_context}

请从以下角度进行深度思考：
1. 这些信息背后反映了什么趋势或规律？
2. 不同观点或方案的优势和劣势是什么？
3. 可以从哪些角度来分析这个问题？
4. 有什么被忽视的重要方面？
5. 如何将这些信息联系起来，形成更深入的见解？

请用简洁清晰的语言输出你的思考，控制在400字以内。"""
            
            logger.info(f"[{self.name}] 开始深度思考")
            thinking = call_zhipu_llm(
                prompt=prompt,
                api_key=self.zhipu_api_key,
                model=self.zhipu_model,
                temperature=0.8,  # 稍高温度以增加创造性
                max_tokens=1000
            )
            
            if thinking:
                result = {
                    "success": True,
                    "thinking": thinking
                }
                logger.info(f"✅ [{self.name}] 思考完成")
            else:
                result = {
                    "success": False,
                    "thinking": None,
                    "message": "深度思考失败"
                }
                logger.warning(f"⚠️ [{self.name}] 思考失败")
            
            self.result = result
            self.set_status(AgentStatus.COMPLETED)
            return result
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] 处理失败: {e}", exc_info=True)
            self.set_status(AgentStatus.FAILED)
            return {
                "success": False,
                "thinking": None,
                "message": str(e)
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
            
            # 二次检索（支持多查询，如果context中有）
            retrieval_queries = [query]  # 默认使用原始查询
            if context and context.get("retrieval_queries"):
                retrieval_queries = context.get("retrieval_queries")
            
            if len(retrieval_queries) > 1:
                relevant_docs_detailed = self.retriever.get_relevant_documents_multi_query(retrieval_queries)
            else:
                relevant_docs_detailed = self.retriever.get_relevant_documents(retrieval_queries[0])
            
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
            logger.info(f"✅ [{self.name}] Agent已完成: 处理了 {len(relevant_docs)} 个文档")
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
    
    async def execute(self, query: str, mode: str = "speed", detected_lang: str = "zh") -> tuple[List, str, dict]:
        """
        执行多Agent协作搜索
        
        Args:
            query: 搜索查询
            mode: 搜索模式 (speed/quality)
            detected_lang: 检测到的语言
            
        Returns:
            (相关文档列表, 引用信息, 思考结果字典)
        """
        try:
            # 计算总步骤数
            self._calculate_steps(mode)
            
            # 立即发送开始消息
            await self._report_progress(0, "多Agent搜索工作已启动")
            
            # 用于存储思考结果（深度模式）
            thinking_results = {}
            
            # 深度模式：Agent 0: 理解问题
            if mode == "quality":
                understanding_agent = self.agents.get("problem_understanding")
                if understanding_agent:
                    await self._report_progress(1, "理解问题")
                    understanding_result = await understanding_agent.process({"query": query})
                    if understanding_result.get("success"):
                        understanding_text = understanding_result.get("understanding", "")
                        thinking_results["understanding"] = understanding_text
                        logger.info(f"✅ 问题理解完成: {understanding_text[:50]}...")
                        # 发送理解结果（单独发送，让前端可以显示）
                        await self._report_progress(1, f"理解问题\n{understanding_text}")
            
            # Agent 1: 关键词提取
            keyword_agent = self.agents.get("keyword_extractor")
            step_offset = 2 if mode == "quality" else 1  # 深度模式：理解问题(1) + 关键词(2)，快速模式：开始(0) + 关键词(1)
            if keyword_agent:
                await self._report_progress(step_offset, "提取搜索关键词")
                keyword_result = await keyword_agent.process({"query": query})
                
                if not keyword_result.get("success"):
                    logger.warning("关键词提取失败，使用原始查询")
                    keyword_result = {"keywords": {"zh": query, "en": ""}}
            else:
                keyword_result = {"keywords": {"zh": query, "en": ""}}
            
            # 准备搜索查询列表（先英文，后中文）
            search_queries = []
            keywords = keyword_result.get("keywords", {})
            
            # 如果检测到是英语，只使用英文搜索，跳过中文搜索
            if detected_lang == "en":
                # 英语查询：优先使用英文关键词，否则使用原始查询
                if keywords.get("en"):
                    search_queries.append({
                        "query": keywords["en"],
                        "language": "en",
                        "source": "keywords_en",
                        "max_results": 60  # 英语SearXNG搜索增加到60条
                    })
                else:
                    search_queries.append({
                        "query": query,
                        "language": "en",
                        "source": "original",
                        "max_results": 60  # 英语SearXNG搜索增加到60条
                    })
            else:
                # 中文查询：先英文，后中文
                if keywords.get("en"):
                    search_queries.append({
                        "query": keywords["en"],
                        "language": "en",
                        "source": "keywords_en",
                        "max_results": 60  # 英语SearXNG搜索增加到60条
                    })
                
                if keywords.get("zh"):
                    search_queries.append({
                        "query": keywords["zh"],
                        "language": "zh",
                        "source": "keywords_zh",
                        "max_results": 50  # 中文SearXNG搜索保持50条
                    })
            
            # 准备DuckDuckGo查询（先英文，后中文）
            ddg_queries = []
            if detected_lang == "en":
                # 英语查询：只使用英文，且增加结果数量到60
                if keywords.get("en"):
                    ddg_queries.append({
                        "query": keywords["en"],
                        "language": "en",
                        "source": "ddg_en",
                        "max_results": 60  # 英语查询增加到60条
                    })
                else:
                    ddg_queries.append({
                        "query": query,
                        "language": "en",
                        "source": "ddg_en",
                        "max_results": 60  # 英语查询增加到60条
                    })
            else:
                # 中文查询：先英文，后中文
                if keywords.get("en"):
                    ddg_queries.append({
                        "query": keywords["en"],
                        "language": "en",
                        "source": "ddg_en",
                        "max_results": 40  # 中文搜索时的英语资料为40条
                    })
                elif detected_lang == "zh":
                    # 如果没有英文关键词，尝试翻译
                    from .momo_utils import translate_text
                    translated = translate_text(query, source="zh", target="en")
                    if translated:
                        ddg_queries.append({
                            "query": translated,
                            "language": "en",
                            "source": "ddg_en_translated",
                            "max_results": 40  # 中文搜索时的英语资料为40条
                        })
                
                if keywords.get("zh"):
                    ddg_queries.append({
                        "query": keywords["zh"],
                        "language": "zh",
                        "source": "ddg_zh",
                        "max_results": 20
                    })
            
            # Agent 2: 搜索
            search_agent = self.agents.get("searcher")
            # 初始化步骤计数器
            current_step = 1
            all_documents = []
            
            if search_agent:
                # 逐个执行搜索并报告进度
                
                # 执行SearXNG搜索（先英文，后中文）
                for sq in search_queries:
                    if sq['language'] == 'en':
                        message = f"正在搜索英语资料: {sq['query']}"
                    else:
                        message = f"正在搜索中文资料: {sq['query']}"
                    await self._report_progress(current_step, message)
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
                
                # 执行DuckDuckGo搜索（先英文，后中文）
                for dq in ddg_queries:
                    if dq['language'] == 'en':
                        message = "正在扩充搜索英语资料..."
                    else:
                        message = "正在进一步深度搜索中文资料..."
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
                    f"分析相关性 ({len(all_documents)}个结果)"
                )
                
                # 构建检索查询列表：分开查询中英文，提高匹配精度
                retrieval_queries = [query]  # 总是包含原始查询
                if keywords.get("en"):
                    # 如果有英文关键词，分别查询以提高英文文档匹配度
                    retrieval_queries.append(keywords["en"])
                    logger.info(f"[向量检索] 使用分开查询: 中文='{query[:50]}...', 英文='{keywords['en'][:50]}...'")
                else:
                    logger.info(f"[向量检索] 使用原始查询: {query[:100]}")
                
                retrieval_result = await retrieval_agent.process({
                    "queries": retrieval_queries,  # 传递查询列表
                    "documents": all_documents
                })
                relevant_docs = retrieval_result.get("results", [])
            else:
                relevant_docs = all_documents
            
            if not relevant_docs:
                logger.warning("⚠️ 未找到相关文档")
                return [], "", thinking_results
            
            # 深度模式：在爬取之前进行思考步骤
            if mode == "quality":
                # Agent 4: 分析资料
                analysis_agent = self.agents.get("material_analysis")
                if analysis_agent:
                    analysis_step = vector_step + 1
                    await self._report_progress(analysis_step, "分析资料")
                    analysis_result = await analysis_agent.process({
                        "query": query,
                        "documents": relevant_docs,
                        "understanding": thinking_results.get("understanding", "")
                    })
                    if analysis_result.get("success"):
                        thinking_results["analysis"] = analysis_result.get("analysis", "")
                        logger.info(f"✅ 资料分析完成: {thinking_results['analysis'][:50]}...")
                
                # Agent 5: 深度思考
                thinking_agent = self.agents.get("deep_thinking")
                if thinking_agent:
                    thinking_step = analysis_step + 1 if analysis_agent else vector_step + 1
                    await self._report_progress(thinking_step, "深度思考与推理")
                    thinking_result = await thinking_agent.process({
                        "query": query,
                        "understanding": thinking_results.get("understanding", ""),
                        "analysis": thinking_results.get("analysis", "")
                    })
                    if thinking_result.get("success"):
                        thinking_results["thinking"] = thinking_result.get("thinking", "")
                        logger.info(f"✅ 深度思考完成: {thinking_results['thinking'][:50]}...")
                
                # Agent 6: 深度爬取（仅quality模式）
                crawler_agent = self.agents.get("crawler")
                if crawler_agent:
                    # 计算爬取步骤位置
                    thinking_step = analysis_step + 1 if analysis_agent else vector_step + 1
                    crawl_step = thinking_step + 1 if thinking_agent else thinking_step
                    await self._report_progress(
                        crawl_step,
                        f"深度爬取内容 (前{len(relevant_docs)}个)"
                    )
                    
                    await crawler_agent.process({"documents": relevant_docs})
                    
                    # Agent 7: 文档处理
                    processor_agent = self.agents.get("document_processor")
                    if processor_agent:
                        split_step = crawl_step + 1
                        await self._report_progress(split_step, "✂️ 文档分块和二次检索")
                        
                        # 构建检索查询列表用于二次检索
                        retrieval_queries_for_processor = [query]
                        if keywords.get("en"):
                            retrieval_queries_for_processor.append(keywords["en"])
                        
                        processor_result = await processor_agent.process({
                            "query": query,
                            "documents": relevant_docs
                        }, context={
                            "retrieval_queries": retrieval_queries_for_processor
                        })
                        relevant_docs = processor_result.get("results", relevant_docs)
            
            # 完成搜索阶段
            final_step = self.total_steps - 1  # 搜索完成是倒数第二步
            await self._report_progress(final_step, f"✅ 搜索完成，找到{len(relevant_docs)}篇相关文档")
            
            # 综合信息，生成回答（最后一步）
            synthesizing_step = self.total_steps
            await self._report_progress(synthesizing_step, "综合信息，生成回答")
            
            # 生成引用信息（使用静态方法或直接实现）
            citations = self._format_citations(relevant_docs)
            
            logger.info(f"✅ 多Agent搜索完成: 返回{len(relevant_docs)}个文档")
            return relevant_docs, citations, thinking_results
            
        except Exception as e:
            logger.error(f"❌ 多Agent搜索失败: {e}", exc_info=True)
            return [], "", {}
    
    def _calculate_steps(self, mode: str):
        """计算总步骤数"""
        search_steps = 2  # 估算：中文+英文关键词搜索
        ddg_steps = 2  # DuckDuckGo中英文
        
        if mode == "quality":
            # 深度模式：理解问题(1) + 关键词(1) + 搜索(2) + 向量检索(1) + 分析资料(1) + 深度思考(1) + 爬取(1) + 分块(1) + 完成(1)
            base_steps = 9
            self.total_steps = base_steps + search_steps + ddg_steps
        else:
            # 快速模式：关键词(1) + 搜索(2) + 向量检索(1) + 完成(1)
            base_steps = 5
            self.total_steps = base_steps + search_steps + ddg_steps
        
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

