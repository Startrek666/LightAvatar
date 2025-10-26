"""
Web Search Handler - 联网搜索处理器
使用 DuckDuckGo 搜索并提取网页正文内容
"""

import asyncio
from typing import List, Dict, Optional, AsyncGenerator
import httpx
from loguru import logger
from backend.handlers.base import BaseHandler


class WebSearchHandler(BaseHandler):
    """联网搜索处理器"""
    
    async def _setup(self):
        """初始化搜索客户端"""
        try:
            # 优先尝试新包名
            try:
                from ddgs import DDGS
                logger.info("Using ddgs package (recommended)")
            except ImportError:
                # 备用方案：旧包名
                from duckduckgo_search import DDGS
                logger.warning("Using deprecated duckduckgo_search package. Consider upgrading: pip install ddgs")
            
            # 初始化搜索客户端
            self.ddgs = DDGS()
            
        except ImportError as e:
            logger.error(f"Search package not installed: {e}")
            logger.error("Run: pip install ddgs")
            raise
        
        # HTTP 客户端用于获取网页内容
        self.http_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        
        self.max_results = self.config.get('max_results', 5)
        self.fetch_content = self.config.get('fetch_content', True)
        self.content_max_length = self.config.get('content_max_length', 2000)
        
        logger.info(f"WebSearchHandler initialized: max_results={self.max_results}, fetch_content={self.fetch_content}")
    
    async def search_with_progress(
        self, 
        query: str, 
        max_results: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """
        执行搜索并报告进度
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数量
            progress_callback: 进度回调函数 (step, total, message)
            
        Returns:
            搜索结果列表
        """
        max_results = max_results or self.max_results
        
        try:
            # 步骤1: 开始搜索
            if progress_callback:
                await progress_callback(1, 4, f"正在搜索: {query}")
            
            logger.info(f"Searching for: {query} (max_results={max_results})")
            
            # 优化搜索关键词（为技术术语添加英文）
            optimized_query = self._optimize_search_query(query)
            if optimized_query != query:
                logger.info(f"Optimized query: {optimized_query}")
            
            # 执行 DuckDuckGo 搜索（新版本 API 使用同步方法）
            # 使用 asyncio.to_thread 将同步调用转为异步
            try:
                # 优化搜索参数以获得更相关的结果
                # timelimit: 'd' (day), 'w' (week), 'm' (month), 'y' (year)
                search_params = {
                    'query': optimized_query,  # 注意：参数名是 query 不是 keywords
                    'max_results': max_results,
                    'region': 'cn-zh',  # 中文地区
                    'safesearch': 'moderate',  # 过滤不当内容
                    'timelimit': 'm'  # 最近一个月的结果（获取更新鲜的内容）
                }
                
                results = await asyncio.to_thread(
                    lambda: list(self.ddgs.text(**search_params))
                )
                logger.info(f"DuckDuckGo returned {len(results)} raw results")
                
                # 打印前3个结果用于调试
                if results:
                    logger.info(f"Search results preview:")
                    for i, r in enumerate(results[:3], 1):
                        logger.info(f"  {i}. {r.get('title', 'N/A')[:60]}... | {r.get('href', 'N/A')}")
                else:
                    logger.warning("DuckDuckGo returned empty results, trying without time limit...")
                    # 回退：不限制时间再试一次
                    search_params.pop('timelimit')
                    results = await asyncio.to_thread(
                        lambda: list(self.ddgs.text(**search_params))
                    )
                    logger.info(f"Retry without time limit: {len(results)} results")
                    
            except Exception as search_error:
                logger.error(f"DuckDuckGo search error: {search_error}", exc_info=True)
                results = []
            
            # 步骤2: 获取到搜索结果
            if progress_callback:
                await progress_callback(2, 4, f"找到 {len(results)} 个结果")
            
            logger.info(f"Found {len(results)} search results")
            
            # 步骤3: 提取网页内容
            formatted_results = []
            for i, r in enumerate(results, 1):
                result = {
                    'title': r.get('title', ''),
                    'url': r.get('href', ''),
                    'snippet': r.get('body', ''),
                }
                
                # 如果需要获取正文内容
                if self.fetch_content:
                    if progress_callback:
                        await progress_callback(3, 4, f"正在提取第 {i}/{len(results)} 个网页内容")
                    
                    content = await self._fetch_page_content(result['url'])
                    result['content'] = content
                
                formatted_results.append(result)
            
            # 步骤4: 完成
            if progress_callback:
                await progress_callback(4, 4, "搜索完成")
            
            logger.info(f"Search completed: {len(formatted_results)} results with content")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            if progress_callback:
                await progress_callback(0, 4, f"搜索失败: {str(e)}")
            return []
    
    async def process(self, query: str) -> List[Dict]:
        """
        处理搜索请求（实现 BaseHandler 的抽象方法）
        
        Args:
            query: 搜索关键词
            
        Returns:
            搜索结果列表
        """
        return await self.search(query)
    
    def _optimize_search_query(self, query: str) -> str:
        """
        优化搜索关键词，为技术术语添加英文关键词以改善搜索结果
        
        Args:
            query: 原始查询
            
        Returns:
            优化后的查询
        """
        # 技术术语映射（中文 -> 英文）
        tech_terms = {
            '开源大模型': 'open source LLM',
            '大模型': 'large language model LLM',
            'AI': 'artificial intelligence',
            '人工智能': 'AI',
            '深度学习': 'deep learning',
            '机器学习': 'machine learning',
            '神经网络': 'neural network',
            'ChatGPT': 'ChatGPT OpenAI',
            'Python': 'Python programming',
            'JavaScript': 'JavaScript',
            '区块链': 'blockchain',
            '加密货币': 'cryptocurrency'
        }
        
        optimized = query
        for cn_term, en_term in tech_terms.items():
            if cn_term in query and en_term not in query:
                # 添加英文术语，但保持原查询
                optimized = f"{query} {en_term}"
                break  # 只添加第一个匹配的术语
        
        return optimized
    
    async def search(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """
        执行搜索（不带进度回调）
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数量
            
        Returns:
            搜索结果列表
        """
        return await self.search_with_progress(query, max_results, None)
    
    async def _fetch_page_content(self, url: str) -> str:
        """
        获取网页正文内容
        
        Args:
            url: 网页URL
            
        Returns:
            提取的正文内容
        """
        try:
            # 下载网页
            logger.debug(f"Fetching content from: {url}")
            response = await self.http_client.get(url)
            html = response.text
            
            # 尝试使用 trafilatura 提取正文
            try:
                import trafilatura
                content = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=True,
                    no_fallback=False
                )
                
                if content:
                    # 限制长度
                    if len(content) > self.content_max_length:
                        content = content[:self.content_max_length] + "..."
                    return content
            except ImportError:
                logger.warning("trafilatura not installed, using simple text extraction")
            
            # 备用方案：简单文本提取
            from html.parser import HTMLParser
            
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                
                def handle_data(self, data):
                    if data.strip():
                        self.text.append(data.strip())
            
            extractor = TextExtractor()
            extractor.feed(html)
            content = ' '.join(extractor.text)
            
            if len(content) > self.content_max_length:
                content = content[:self.content_max_length] + "..."
            
            return content if content else ""
                
        except Exception as e:
            logger.warning(f"Failed to fetch content from {url}: {e}")
            return ""
    
    async def cleanup(self):
        """清理资源"""
        if hasattr(self, 'http_client'):
            await self.http_client.aclose()

