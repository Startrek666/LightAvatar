"""
Momo Search Utils - 搜索工具函数
"""
from dataclasses import dataclass
import urllib.parse
from json import JSONDecodeError
from typing import List, Optional
import re

import faiss
import numpy as np
import requests
from loguru import logger

# 翻译API配置
TRANSLATE_API_URL = "https://api-utils.lemomate.com/translate"
TRANSLATE_API_KEY = "L5kGzmjwqXbk0ViD@"


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
