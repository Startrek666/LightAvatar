"""
Momo Search Utils - 搜索和检索工具
基于 Momo-Search 项目改造
"""
from dataclasses import dataclass
import urllib.parse
from json import JSONDecodeError
import requests
from typing import List, Optional
import re

import faiss
import numpy as np
from loguru import logger


@dataclass
class SearchDocument:
    """搜索文档数据结构"""
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


def escape_special_chars(text: str) -> str:
    """转义Markdown特殊字符"""
    # 用于Telegram Markdown V2格式
    special_chars = r'_\*\[\]\(\)~`>#\+\-=\|\{\}\.\!'
    return re.sub(f'([{special_chars}])', r'\\\1', text)


def escape_special_chars_for_link(text: str) -> str:
    """转义链接中的特殊字符"""
    # 在链接的()部分，所有 ) 和 \ 必须转义
    return re.sub(r'([\\)])', r'\\\1', text)


def process_bold_text(text: str) -> str:
    """处理粗体文本"""
    # 将 **text** 替换为 *escaped_text*
    processed_text = re.sub(r'\*\*(.*?)\*\*', lambda m: f"*{escape_special_chars(m.group(1))}*", text)
    parts = []
    in_bold = False
    for part in processed_text.split('*'):
        if in_bold:
            parts.append(f"*{part}*")
        else:
            parts.append(escape_special_chars(part))
        in_bold = not in_bold
    return ''.join(parts)


def convert_to_markdown(text: str) -> str:
    """
    将LLM输出转换为适合显示的Markdown格式
    (简化版，不使用Telegram特殊转义)
    """
    lines = text.split('\n')
    result = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # 处理引用标记 [citation:X] -> [X]
        if '[citation:' in line_stripped:
            line_stripped = re.sub(r'\[citation:(\d+)\]', r'[\1]', line_stripped)
        
        # 处理标题
        if line_stripped.startswith('#'):
            header_text = line_stripped.strip('#').strip()
            result.append(f"**{header_text}**\n")
        # 处理列表项
        elif line_stripped.startswith('- '):
            bullet_text = line_stripped[2:]
            result.append(f"• {bullet_text}\n")
        # 处理分隔线
        elif line_stripped == '---':
            result.append("━━━━━━━━━━━━━━━━━━━━\n")
        else:
            result.append(f"{line_stripped}\n")
    
    return ''.join(result)


def search_searxng(
    query: str, 
    num_results: int,
    ip_address: str = "http://localhost:8080",
    language: str = "zh",
    time_range: str = "day"
) -> List[SearchDocument]:
    """
    使用SearXNG搜索引擎进行搜索
    
    Args:
        query: 搜索查询
        num_results: 期望的结果数量
        ip_address: SearXNG实例地址
        language: 搜索语言
        time_range: 时间范围 (day/week/month/year/'')
    
    Returns:
        搜索文档列表
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }
    
    request_str = f"/search?q={encode_url(query)}&time_range={time_range}&format=json&language={language}&pageno="
    pageno = 1
    base_url = ip_address
    results = []
    
    logger.info(f"🔍 SearXNG搜索: {query} (期望{num_results}个结果)")
    
    while len(results) < num_results:
        url = base_url + request_str + str(pageno)
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response_dict = response.json()
        except JSONDecodeError:
            logger.error("❌ SearXNG返回的不是有效JSON，请检查SearXNG配置")
            break
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ SearXNG请求失败: {e}")
            break
        
        result_dicts = response_dict.get("results", [])
        if not result_dicts:
            logger.warning(f"⚠️ 第{pageno}页没有更多结果")
            break
        
        for result in result_dicts:
            if "content" in result:
                doc = SearchDocument(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=result.get("content", "")
                )
                results.append(doc)
                
                if len(results) >= num_results:
                    break
        
        pageno += 1
    
    logger.info(f"✅ SearXNG搜索完成: 获得{len(results)}个结果")
    return results


class FaissRetriever:
    """基于FAISS的向量检索器"""
    
    def __init__(
        self, 
        embedding_model, 
        num_candidates: int = 40, 
        sim_threshold: float = 0.45
    ):
        """
        初始化FAISS检索器
        
        Args:
            embedding_model: SentenceTransformer嵌入模型
            num_candidates: 候选文档数量
            sim_threshold: 相似度阈值
        """
        self.embedding_model = embedding_model
        self.num_candidates = num_candidates
        self.sim_threshold = sim_threshold
        self.embeddings_dim = embedding_model.get_sentence_embedding_dimension()
        self.reset_state()
        logger.info(f"📦 FAISS检索器初始化: dim={self.embeddings_dim}, candidates={num_candidates}, threshold={sim_threshold}")
    
    def reset_state(self):
        """重置检索器状态"""
        self.index = faiss.IndexFlatIP(self.embeddings_dim)  # 内积索引
        self.documents = []
    
    def encode_doc(self, doc: str | List[str]) -> np.ndarray:
        """编码文档为向量"""
        return self.embedding_model.encode(doc, normalize_embeddings=True)
    
    def add_documents(self, documents: List[SearchDocument]):
        """添加文档到检索器"""
        if not documents:
            logger.warning("⚠️ 没有文档添加到检索器")
            return
        
        self.reset_state()
        self.documents = documents
        
        # 编码文档
        doc_texts = [doc.content if doc.content else doc.snippet for doc in documents]
        doc_embeddings = self.encode_doc(doc_texts)
        
        # 添加到FAISS索引
        self.index.add(doc_embeddings)
        logger.info(f"✅ 已添加{len(documents)}个文档到FAISS索引")
    
    def filter_by_sim(self, distances: np.ndarray, indices: np.ndarray) -> np.ndarray:
        """根据相似度阈值过滤"""
        cutoff_idx = -1
        for idx, sim in enumerate(distances):
            if sim > self.sim_threshold:
                cutoff_idx = idx
            else:
                break
        top_sim_indices = indices[:cutoff_idx + 1]
        return top_sim_indices
    
    def get_relevant_documents(self, query: str) -> List[SearchDocument]:
        """获取与查询相关的文档"""
        if not self.documents:
            raise ValueError("❌ 检索器中没有文档")
        
        # 编码查询
        query_embedding = self.encode_doc(query)
        
        # FAISS搜索
        distances, indices = self.index.search(
            query_embedding.reshape(1, -1), 
            self.num_candidates
        )
        
        # 添加相似度信息
        for idx, sim in enumerate(distances[0]):
            if indices[0][idx] < len(self.documents):
                self.documents[indices[0][idx]].score = float(sim)
        
        # 根据阈值过滤
        top_indices = self.filter_by_sim(distances[0], indices[0])
        logger.info(f"🎯 找到{len(top_indices)}个相关文档（阈值>{self.sim_threshold}）")
        
        relevant_docs = [self.documents[idx] for idx in top_indices]
        
        # 打印相关文档信息
        for idx, doc in enumerate(relevant_docs):
            logger.debug(f"  {idx+1}. {doc.title[:50]}... (相似度: {doc.score:.3f})")
        
        return relevant_docs



