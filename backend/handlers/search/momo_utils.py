"""
Momo Search Utils - 搜索工具函数
"""
from dataclasses import dataclass
import urllib.parse
from json import JSONDecodeError
from typing import List, Optional
import re
import asyncio

import faiss
import numpy as np
import requests
from loguru import logger

# 翻译API配置
TRANSLATE_API_URL = "https://api-utils.lemomate.com/translate"
TRANSLATE_API_KEY = "L5kGzmjwqXbk0ViD@"

# 智谱清言关键词提取API配置
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_API_KEY = "6f29a799833a4a5daf5752973e9d0cc4.uoelH21xYFMkDknh"
ZHIPU_MODEL = "glm-4.5-flash"


@dataclass
class SearchDocument:
    """搜索结果文档"""
    title: str = ""
    url: str = ""
    snippet: str = ""
    content: str = ""
    score: float = 0.0


def encode_url(url: str) -> str:
    """URL编码"""
    return urllib.parse.quote(url)


def decode_url(url: str) -> str:
    """URL解码"""
    return urllib.parse.unquote(url)


def escape_markdown(text: str) -> str:
    """转义Markdown特殊字符"""
    special_chars = r'_\*\[\]\(\)~`>#\+\-=\|\{\}\.\!'
    return re.sub(f'([{special_chars}])', r'\\\1', text)


def detect_language(text: str) -> str:
    """
    检测文本语言（简单版本）
    
    Args:
        text: 输入文本
    
    Returns:
        "zh" 如果主要是中文，"en" 如果主要是英文
    """
    if not text:
        return "en"
    
    # 统计中文字符数量
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(re.sub(r'\s+', '', text))  # 去除空格后的总字符数
    
    if total_chars == 0:
        return "en"
    
    # 如果中文字符占比超过30%，认为是中文
    chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
    
    if chinese_ratio > 0.3:
        return "zh"
    else:
        return "en"


def extract_keywords(
    query: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> Optional[dict]:
    """
    使用智谱清言模型提取搜索关键词
    
    Args:
        query: 用户查询文本
        api_key: 智谱清言API密钥，如果为None则使用默认值
        model: 智谱清言模型名称，如果为None则使用默认值
    
    Returns:
        包含zh_keys和en_keys的字典，失败返回None
    """
    try:
        from datetime import datetime
        
        # 使用传入的参数或默认值
        zhipu_api_key = api_key if api_key is not None else ZHIPU_API_KEY
        zhipu_model = model if model is not None else ZHIPU_MODEL
        
        # 获取当前日期，去掉月份和日期的前导零
        now = datetime.now()
        current_date = f"{now.year}年{now.month}月{now.day}日"
        
        # 构建Prompt
        prompt = f"""今天是{current_date}。为了给用户的回答保持准确，你需要使用搜索引擎。使用json格式返回关键词，属性为zh_keys,en_keys。每个属性只需要一行，关键词用空格分隔。仅需返回重要关键词，每行不超过10个。对于英语关键词，除了完整翻译，还可以加上相关缩写。如果语句中包含"最近"，"最新"等词语，根据需要加上年份或者月份，年份和月份不能连在一起。从下面这句话中提取用于搜索引擎的关键词：{query}"""
        
        headers = {
            "Authorization": f"Bearer {zhipu_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": zhipu_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 1,
            "max_tokens": 65536,
            "stream": False,
            "thinking": {"type": "disabled"},
            "do_sample": True,
            "top_p": 0.95,
            "tool_stream": False,
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(
            ZHIPU_API_URL,
            json=payload,
            headers=headers,
            timeout=15
        )
        
        response.raise_for_status()
        result = response.json()
        
        # 解析返回的JSON
        choices = result.get("choices", [])
        if not choices:
            logger.warning("⚠️ 关键词提取API返回空choices")
            return None
        
        message = choices[0].get("message", {})
        content = message.get("content", "").strip()
        
        if not content:
            logger.warning("⚠️ 关键词提取API返回空内容")
            return None
        
        # 解析JSON字符串（content中包含JSON格式的字符串）
        import json
        try:
            keywords_dict = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON解析失败: {e}")
            logger.error(f"原始内容: {content[:200]}")  # 记录前200个字符用于调试
            return None
        
        zh_keys = keywords_dict.get("zh_keys", "").strip()
        en_keys = keywords_dict.get("en_keys", "").strip()
        
        if zh_keys or en_keys:
            logger.info(f"✅ 关键词提取成功: zh_keys={zh_keys}, en_keys={en_keys}")
            return {
                "zh_keys": zh_keys,
                "en_keys": en_keys
            }
        else:
            logger.warning("⚠️ 关键词提取API返回空关键词")
            return None
            
    except Exception as e:
        logger.error(f"❌ 关键词提取失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def translate_text(query: str, source: str = "zh", target: str = "en") -> Optional[str]:
    """
    调用翻译API翻译文本
    
    Args:
        query: 要翻译的文本
        source: 源语言 (zh/en)
        target: 目标语言 (zh/en)
    
    Returns:
        翻译后的文本，失败返回None
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": TRANSLATE_API_KEY
        }
        
        data = {
            "q": query,
            "source": source,
            "target": target
        }
        
        response = requests.post(
            TRANSLATE_API_URL,
            headers=headers,
            json=data,
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        
        translated_text = result.get("translatedText", "")
        if translated_text:
            logger.info(f"✅ 翻译成功: {query} -> {translated_text}")
            return translated_text
        else:
            logger.warning(f"⚠️ 翻译API返回空结果")
            return None
            
    except Exception as e:
        logger.error(f"❌ 翻译失败: {e}")
        return None


def convert_to_markdown(text: str) -> str:
    """将文本转换为Markdown格式"""
    lines = text.split('\n')
    result = []
    
    for line in lines:
        line = line.strip()
        
        if not line:
            result.append('\n')
            continue
        
        # 处理引用标记 [citation:X]
        if '[citation:' in line:
            line = re.sub(r'\[citation:(\d+)\]', r'[\1]', line)
        
        # 处理标题
        if line.startswith('#'):
            header_text = line.strip('#').strip()
            # 处理加粗文本
            if '**' in header_text:
                header_text = re.sub(r'\*\*(.*?)\*\*', r'**\1**', header_text)
            result.append(f"{line}\n")
        
        # 处理列表项
        elif line.strip().startswith('- '):
            bullet_text = line.strip()[2:]
            result.append(f"- {bullet_text}\n")
        
        # 处理分隔线
        elif line.strip() == '---':
            result.append("---\n")
        
        # 处理普通文本
        else:
            result.append(f"{line}\n")
    
    return ''.join(result)


def search_searxng(
    query: str,
    num_results: int,
    ip_address: str = "http://localhost:9080",
    language: str = "zh",
    time_range: str = "",
    deduplicate_by_url: bool = True
) -> List[SearchDocument]:
    """
    使用SearXNG搜索
    
    Args:
        query: 搜索查询
        num_results: 需要的结果数量
        ip_address: SearXNG服务地址
        language: 搜索语言 (zh/en)
        time_range: 时间范围 (day/week/month/year/"")
    
    Returns:
        搜索结果文档列表
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    # 构建请求URL
    params = {
        "q": query,
        "format": "json",
        "language": language,
    }
    
    # 添加时间范围参数（如果提供）
    if time_range:
        params["time_range"] = time_range
    
    # 构建基础URL
    base_url = ip_address.rstrip('/')
    if not base_url.startswith('http'):
        base_url = f"http://{base_url}"
    
    res = []
    seen_urls = set() if deduplicate_by_url else None
    pageno = 1
    
    while len(res) < num_results:
        params["pageno"] = pageno
        query_string = urllib.parse.urlencode(params)
        url = f"{base_url}/search?{query_string}"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            response_dict = response.json()
            
        except JSONDecodeError as e:
            logger.error(f"❌ SearXNG JSON解析失败: {e}")
            logger.error(f"响应内容: {response.text[:500]}")
            raise ValueError("JSONDecodeError: 请确保SearXNG实例可以返回JSON格式数据")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ SearXNG请求失败: {e}")
            raise
        
        result_dicts = response_dict.get("results", [])
        if not result_dicts:
            logger.debug(f"第{pageno}页无更多结果")
            break
        
        for result in result_dicts:
            # 提取内容（优先使用content，否则使用snippet）
            content = result.get("content", "") or result.get("snippet", "")
            result_url = result.get("url", "")
            
            # 去重：如果启用了去重且URL已存在，跳过
            if deduplicate_by_url and seen_urls is not None:
                if result_url in seen_urls:
                    continue
                seen_urls.add(result_url)
            
            if content:
                doc = SearchDocument(
                    title=result.get("title", ""),
                    url=result_url,
                    snippet=result.get("snippet", ""),
                    content=content,
                    score=result.get("score", 0.0)
                )
                res.append(doc)
                
                if len(res) >= num_results:
                    break
        
        # 如果没有更多结果，停止分页
        if len(result_dicts) < 20:  # 通常每页20个结果
            break
        
        pageno += 1
    
    logger.info(f"✅ SearXNG搜索完成: 获得{len(res)}个结果")
    return res


async def search_duckduckgo(
    query: str,
    max_results: int = 20,
    language: str = "zh",
    time_range: Optional[str] = None
) -> List[SearchDocument]:
    """
    使用 DuckDuckGo API 直接搜索
    
    Args:
        query: 搜索查询
        max_results: 最大结果数量
        language: 搜索语言 (zh/en)
        time_range: 时间范围 ('d'=天, 'w'=周, 'm'=月, 'y'=年, None=不限)
    
    Returns:
        搜索结果文档列表
    """
    try:
        # 尝试导入 ddgs
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        
        # 准备搜索参数
        search_params = {
            "query": query,
            "max_results": max_results,
            "safesearch": "moderate"
        }
        
        # 根据语言设置地区参数
        if language == "zh":
            search_params["region"] = "cn-zh"
        else:
            search_params["region"] = "us-en"
        
        # 设置时间范围
        if time_range:
            # 将 searxng 的时间范围格式转换为 duckduckgo 格式
            time_map = {
                "day": "d",
                "week": "w",
                "month": "m",
                "year": "y"
            }
            ddg_time = time_map.get(time_range.lower())
            if ddg_time:
                search_params["timelimit"] = ddg_time
        
        # 在独立线程中执行搜索（避免阻塞）
        def _run_search():
            with DDGS() as ddgs:
                return list(ddgs.text(**search_params))
        
        results = await asyncio.to_thread(_run_search)
        
        # 转换为 SearchDocument 格式
        documents = []
        for result in results:
            doc = SearchDocument(
                title=result.get("title", ""),
                url=result.get("href", ""),
                snippet=result.get("body", ""),
                content=result.get("body", ""),  # DuckDuckGo 返回的是 body
                score=0.0  # DuckDuckGo 不提供分数
            )
            if doc.url and (doc.title or doc.snippet):
                documents.append(doc)
        
        logger.info(f"✅ DuckDuckGo搜索完成: 查询='{query}', 语言={language}, 获得{len(documents)}个结果")
        return documents
        
    except ImportError:
        logger.warning("⚠️ DuckDuckGo搜索包未安装，跳过DuckDuckGo搜索。请运行: pip install ddgs")
        return []
    except Exception as e:
        logger.error(f"❌ DuckDuckGo搜索失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


class FaissRetriever:
    """FAISS向量检索器"""
    
    def __init__(self, embedding_model, num_candidates: int = 40, sim_threshold: float = 0.45) -> None:
        """
        初始化检索器
        
        Args:
            embedding_model: 嵌入模型（SentenceTransformer实例）
            num_candidates: 候选文档数量
            sim_threshold: 相似度阈值
        """
        self.embedding_model = embedding_model
        self.num_candidates = num_candidates
        self.sim_threshold = sim_threshold
        self.embeddings_dim = embedding_model.get_sentence_embedding_dimension()
        self.reset_state()
        logger.info(f"📦 FAISS检索器初始化: dim={self.embeddings_dim}, candidates={num_candidates}, threshold={sim_threshold}")
    
    def reset_state(self) -> None:
        """重置状态"""
        self.index = faiss.IndexFlatIP(self.embeddings_dim)  # 使用内积（cosine相似度）
        self.documents = []
    
    def encode_doc(self, doc: str | List[str]) -> np.ndarray:
        """编码文档为向量"""
        return self.embedding_model.encode(doc, normalize_embeddings=True)
    
    def add_documents(self, documents: List[SearchDocument]) -> None:
        """
        添加文档到索引
        
        Args:
            documents: 文档列表
        """
        if not documents:
            logger.warning("⚠️ 没有文档添加到检索器")
            return
        
        self.reset_state()
        self.documents = documents
        
        # 提取文档内容（优先使用content，否则使用snippet）
        doc_texts = [doc.content if doc.content else doc.snippet for doc in documents]
        
        # 编码文档
        doc_embeddings = self.encode_doc(doc_texts)
        
        # 添加到索引
        self.index.add(doc_embeddings)
        logger.debug(f"📚 添加{len(documents)}个文档到FAISS索引")
    
    def filter_by_sim(self, distances: np.ndarray, indices: np.ndarray) -> np.ndarray:
        """
        根据相似度阈值过滤结果
        
        Args:
            distances: 相似度分数数组
            indices: 索引数组
        
        Returns:
            过滤后的索引数组
        """
        cutoff_idx = -1
        for idx, sim in enumerate(distances):
            if sim >= self.sim_threshold:
                cutoff_idx = idx
            else:
                break
        
        if cutoff_idx == -1:
            return np.array([])
        
        return indices[:cutoff_idx + 1]
    
    def get_relevant_documents(self, query: str) -> List[SearchDocument]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
        
        Returns:
            相关文档列表
        """
        if not self.documents:
            logger.warning("⚠️ 检索器中没有任何文档")
            return []
        
        # 编码查询
        query_embedding = self.encode_doc(query)
        
        # 搜索最相似的文档
        distances, indices = self.index.search(
            query_embedding.reshape(1, -1),
            min(self.num_candidates, len(self.documents))
        )
        
        # 添加相似度分数到文档
        for idx, sim in enumerate(distances[0]):
            doc_idx = indices[0][idx]
            if doc_idx < len(self.documents):
                self.documents[doc_idx].score = float(sim)
        
        # 过滤相似度阈值
        top_indices = self.filter_by_sim(distances[0], indices[0])
        
        if len(top_indices) == 0:
            logger.warning(f"⚠️ 未找到相关文档（阈值>{self.sim_threshold}）")
            return []
        
        relevant_docs = [self.documents[int(idx)] for idx in top_indices]
        
        logger.info(f"🎯 找到{len(relevant_docs)}个相关文档（阈值>={self.sim_threshold}）")
        
        # 记录前几个结果
        for idx, doc in enumerate(relevant_docs[:5]):
            logger.debug(f"  {idx+1}. {doc.title[:50]}... (sim: {doc.score:.3f})")
        
        return relevant_docs
    
    def get_relevant_documents_multi_query(self, queries: List[str]) -> List[SearchDocument]:
        """
        使用多个查询分别检索，然后合并结果（保留最高相似度分数）
        
        Args:
            queries: 查询文本列表（例如：["中文查询", "English keywords"]）
        
        Returns:
            合并后的相关文档列表（按相似度降序）
        """
        if not self.documents:
            logger.warning("⚠️ 检索器中没有任何文档")
            return []
        
        if not queries:
            return []
        
        # 存储文档URL到最高相似度分数的映射
        doc_scores = {}  # {url: max_score}
        doc_map = {}  # {url: SearchDocument}
        
        # 对每个查询分别检索
        for query_idx, query in enumerate(queries):
            if not query or not query.strip():
                continue
                
            logger.debug(f"[多查询检索] 查询 {query_idx + 1}/{len(queries)}: {query[:50]}...")
            
            # 编码查询
            query_embedding = self.encode_doc(query)
            
            # 搜索最相似的文档
            distances, indices = self.index.search(
                query_embedding.reshape(1, -1),
                min(self.num_candidates, len(self.documents))
            )
            
            # 处理每个结果，保留最高分数
            for idx, sim in enumerate(distances[0]):
                doc_idx = int(indices[0][idx])
                if doc_idx >= len(self.documents):
                    continue
                
                doc = self.documents[doc_idx]
                sim_score = float(sim)
                
                # 只考虑超过阈值的文档
                if sim_score >= self.sim_threshold:
                    # 保留更高的相似度分数
                    if doc.url not in doc_scores or sim_score > doc_scores[doc.url]:
                        doc_scores[doc.url] = sim_score
                        # 创建文档副本并更新分数
                        doc_copy = SearchDocument(
                            title=doc.title,
                            url=doc.url,
                            snippet=doc.snippet,
                            content=doc.content,
                            score=sim_score
                        )
                        doc_map[doc.url] = doc_copy
        
        if not doc_map:
            logger.warning(f"⚠️ 多查询检索未找到相关文档（阈值>={self.sim_threshold}）")
            return []
        
        # 按相似度分数排序
        relevant_docs = list(doc_map.values())
        relevant_docs.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"🎯 多查询检索完成: {len(queries)}个查询, 找到{len(relevant_docs)}个相关文档（阈值>={self.sim_threshold}）")
        
        # 记录前几个结果
        for idx, doc in enumerate(relevant_docs[:5]):
            logger.debug(f"  {idx+1}. {doc.title[:50]}... (sim: {doc.score:.3f})")
        
        return relevant_docs