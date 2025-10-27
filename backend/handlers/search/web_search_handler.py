"""
Web Search Handler - 联网搜索处理器
使用 DuckDuckGo 搜索并提取网页正文内容
"""

import asyncio
from typing import List, Dict, Optional, AsyncGenerator, Callable, Tuple
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
            
            # 保存 DDGS 类引用，避免在多线程环境下共享同一实例
            self.ddgs_class = DDGS
            
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
    
    def _run_ddgs_search(self, params: Dict) -> List[Dict]:
        """在独立客户端中执行 DuckDuckGo 搜索，避免共享状态"""
        with self.ddgs_class() as ddgs:
            logger.debug(f"Executing DDGS.text with params: {params}")
            return list(ddgs.text(**params))

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

            # 搜索策略分两阶段：
            # 1. 纯中文搜索（优先）
            # 2. 失败时，添加英文关键词作为补充

            search_strategies: List[Tuple[str, Dict]] = []

            # 策略A：原始中文查询
            chinese_params = {
                'query': query,
                'max_results': max_results,
                'region': 'cn-zh',
                'safesearch': 'moderate',
                'timelimit': 'm'
            }
            search_strategies.append(('中文原始查询', chinese_params))

            # 策略B：英文增强查询（备选，用于没有中文有效结果时）
            optimized_query = self._optimize_search_query(query)
            if optimized_query != query:
                english_params = chinese_params.copy()
                english_params['query'] = optimized_query
                search_strategies.append(('中文+英文增强', english_params))

            results = []
            used_strategy = None

            for strategy_name, params in search_strategies:
                try:
                    logger.info(f"尝试搜索策略：{strategy_name} -> {params['query']}")
                    strategy_results = await asyncio.to_thread(self._run_ddgs_search, params)
                    logger.info(f" {strategy_name} 返回 {len(strategy_results)} 条结果")

                    if strategy_results:
                        results = strategy_results
                        used_strategy = strategy_name
                        break

                    # 无结果时回退：移除 timelimit 再试一次
                    logger.warning(f" {strategy_name} 无结果，尝试移除 timelimit")
                    fallback_params = params.copy()
                    fallback_params.pop('timelimit', None)
                    logger.debug(f" {strategy_name} fallback params: {fallback_params}")
                    strategy_results = await asyncio.to_thread(self._run_ddgs_search, fallback_params)
                    logger.info(f" {strategy_name}（无时间限制）返回 {len(strategy_results)} 条结果")

                    if strategy_results:
                        results = strategy_results
                        used_strategy = f"{strategy_name} (无 timelimit)"
                        break

                    # 仍无结果时，尝试移除 region 和 safesearch
                    logger.warning(f" {strategy_name}（无时间限制）仍无结果，移除 region/safesearch 再试")
                    fallback_params.pop('region', None)
                    fallback_params.pop('safesearch', None)
                    logger.debug(f" {strategy_name} fallback params (no region/safesearch): {fallback_params}")
                    strategy_results = await asyncio.to_thread(self._run_ddgs_search, fallback_params)
                    logger.info(f" {strategy_name}（无时间限制/无区域限制）返回 {len(strategy_results)} 条结果")

                    if strategy_results:
                        results = strategy_results
                        used_strategy = f"{strategy_name} (无 timelimit/region/safesearch)"
                        break

                except Exception as search_error:
                    logger.error(f"策略 {strategy_name} 搜索失败: {search_error}", exc_info=True)
                    continue

            if used_strategy:
                logger.info(f"使用搜索策略: {used_strategy}")
            else:
                logger.warning("所有策略均未获得有效结果")
            
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
                
                logger.info(f"\n{'='*80}")
                logger.info(f"搜索结果 #{i}:")
                logger.info(f"  标题: {result['title']}")
                logger.info(f"  链接: {result['url']}")
                logger.info(f"  摘要: {result['snippet'][:200]}...")
                
                # 如果需要获取正文内容
                if self.fetch_content:
                    if progress_callback:
                        await progress_callback(3, 4, f"正在提取第 {i}/{len(results)} 个网页内容")
                    
                    content = await self._fetch_page_content(result['url'])
                    result['content'] = content
                    
                    # 记录提取的内容
                    if content:
                        logger.info(f"  ✅ 成功提取正文内容 ({len(content)} 字符)")
                        logger.info(f"  内容预览: {content[:300]}...")
                        logger.debug(f"  完整内容:\n{content}")
                    else:
                        logger.warning(f"  ❌ 未能提取到有效内容")
                
                formatted_results.append(result)
                logger.info(f"{'='*80}\n")
            
            # 步骤4: 完成
            if progress_callback:
                await progress_callback(4, 4, "搜索完成")
            
            # 汇总日志
            logger.info(f"\n{'#'*80}")
            logger.info(f"📊 搜索汇总:")
            logger.info(f"  查询: {query}")
            logger.info(f"  优化查询: {optimized_query}")
            logger.info(f"  结果数量: {len(formatted_results)}")
            
            total_content_length = sum(len(r.get('content', '')) for r in formatted_results)
            logger.info(f"  总内容长度: {total_content_length} 字符")
            
            # 列出所有结果的标题
            logger.info(f"  结果列表:")
            for i, r in enumerate(formatted_results, 1):
                has_content = '✓' if r.get('content') else '✗'
                logger.info(f"    {i}. [{has_content}] {r['title'][:60]}...")
            
            logger.info(f"{'#'*80}\n")
            
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

