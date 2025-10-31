"""
Momo Search Retriever - 文档检索和处理
"""
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from .momo_utils import SearchDocument


def expand_docs_by_text_split(docs: List[SearchDocument]) -> List[SearchDocument]:
    """
    将文档展开为多个小块
    
    Args:
        docs: 原始文档列表
    
    Returns:
        展开后的文档列表
    """
    res_docs = []
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,  # 块大小（字符）
        chunk_overlap=50,  # 块重叠（字符）
        add_start_index=True,  # 跟踪原始文档中的索引
    )
    
    for doc in docs:
        if doc.content and len(doc.content) > 100:
            all_splits = text_splitter.split_text(doc.content)
            logger.debug(f"📄 文档 '{doc.title[:30]}...' 分块: {len(all_splits)}块")
            
            for split in all_splits:
                res_docs.append(SearchDocument(
                    title=doc.title,
                    url=doc.url,
                    snippet=doc.snippet,
                    content=split,
                ))
        else:
            res_docs.append(doc)
    
    logger.info(f"✂️ 文档分块完成: {len(docs)} -> {len(res_docs)} 块")
    return res_docs


def merge_docs_by_url(docs: List[SearchDocument]) -> List[SearchDocument]:
    """
    按URL合并文档，将同一URL的多个块合并
    
    Args:
        docs: 文档列表
    
    Returns:
        合并后的文档列表
    """
    url_to_docs = {}
    
    # 按URL分组
    for doc in docs:
        if doc.url not in url_to_docs:
            url_to_docs[doc.url] = []
        url_to_docs[doc.url].append(doc)
    
    merged_docs = []
    
    # 合并同一URL的文档
    for url, doc_list in url_to_docs.items():
        if len(doc_list) == 1:
            # 只有一个文档，无需合并
            merged_docs.append(doc_list[0])
        else:
            # 合并多个文档
            base_doc = doc_list[0]
            
            # 合并内容
            combined_content = "\n".join([d.content for d in doc_list if d.content])
            
            merged_doc = SearchDocument(
                title=base_doc.title,
                url=base_doc.url,
                snippet=base_doc.snippet,
                content=combined_content,
                score=max(d.score for d in doc_list)  # 取最高分
            )
            
            merged_docs.append(merged_doc)
            logger.debug(f"🔗 合并URL '{url[:50]}...': {len(doc_list)}块 -> 1块")
    
    logger.info(f"🔗 文档合并完成: {len(docs)} -> {len(merged_docs)} 个URL")
    return merged_docs



