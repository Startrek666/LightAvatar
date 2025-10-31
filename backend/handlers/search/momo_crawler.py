"""
Momo Search Crawler - 网页内容爬取
简化版，使用 trafilatura 替代 crawl4ai
"""
import asyncio
from typing import List
import httpx
from loguru import logger

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("⚠️ trafilatura 未安装，深度爬取功能将不可用")

from .momo_utils import SearchDocument


class SimpleCrawler:
    """简化版网页爬虫"""
    
    def __init__(self, timeout: float = 15.0, max_concurrent: int = 5):
        """
        初始化爬虫
        
        Args:
            timeout: 请求超时时间
            max_concurrent: 最大并发数
        """
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.http_client = None
        logger.info(f"🕷️ 简化爬虫初始化: timeout={timeout}s, 并发={max_concurrent}")
    
    async def _get_client(self):
        """获取或创建HTTP客户端"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            )
        return self.http_client
    
    async def crawl_one(self, doc: SearchDocument) -> bool:
        """
        爬取单个文档的内容
        
        Args:
            doc: 搜索文档对象（会直接修改其content字段）
        
        Returns:
            是否成功
        """
        if not TRAFILATURA_AVAILABLE:
            logger.warning(f"⚠️ trafilatura 未安装，跳过 {doc.url}")
            return False
        
        try:
            client = await self._get_client()
            
            # 获取网页内容
            response = await client.get(doc.url)
            response.raise_for_status()
            
            # 使用 trafilatura 提取正文
            content = trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=True,
                no_fallback=False
            )
            
            if content and len(content) > 100:
                doc.content = content
                logger.info(f"✅ 成功爬取: {doc.url[:60]}... ({len(content)}字)")
                return True
            else:
                logger.warning(f"⚠️ 提取内容为空: {doc.url[:60]}...")
                return False
        
        except httpx.HTTPStatusError as e:
            logger.warning(f"⚠️ HTTP错误 {e.response.status_code}: {doc.url[:60]}...")
            return False
        except Exception as e:
            logger.warning(f"⚠️ 爬取失败: {doc.url[:60]}... - {str(e)[:50]}")
            return False
    
    async def crawl_many(
        self, 
        docs: List[SearchDocument],
        score_threshold: float = 0.5,
        max_docs: int = 10
    ):
        """
        批量爬取多个文档
        
        Args:
            docs: 文档列表
            score_threshold: 只爬取相似度高于此阈值的文档
            max_docs: 最多爬取的文档数量
        """
        if not TRAFILATURA_AVAILABLE:
            logger.warning("⚠️ trafilatura 未安装，跳过深度爬取")
            return
        
        # 过滤文档：只爬取高分文档
        filtered_docs = [
            doc for doc in docs 
            if doc.score > score_threshold
        ][:max_docs]
        
        if not filtered_docs:
            logger.info("ℹ️ 没有文档需要深度爬取")
            return
        
        logger.info(f"🕷️ 开始深度爬取: {len(filtered_docs)}/{len(docs)} 个文档")
        
        # 创建信号量限制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def crawl_with_semaphore(doc):
            async with semaphore:
                return await self.crawl_one(doc)
        
        # 并发爬取
        tasks = [crawl_with_semaphore(doc) for doc in filtered_docs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if r is True)
        logger.info(f"✅ 深度爬取完成: {success_count}/{len(filtered_docs)} 成功")
    
    async def close(self):
        """关闭HTTP客户端"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None



