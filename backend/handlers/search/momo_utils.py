"""
Momo Search Utils - 搜索工具函数
"""
from dataclasses import dataclass
import urllib.parse
from json import JSONDecodeError
from typing import List, Optional, Dict
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


def extract_key_entities(text: str) -> List[str]:
    """
    使用规则提取文本中的关键实体和概念（通用版本）
    
    提取规则：
    - 中文：提取常见的实体模式（名词短语、人名、地名、作品名等）
    - 英文：提取专有名词和大写词汇
    - 技术术语：提取特定模式的术语
    - 通用：提取引号内容、关键词
    """
    entities = []
    import re
    
    # 1. 英文专有名词（人名、地名、公司名等）
    tech_patterns = [
        r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',  # 英文专有名词 (如 Python, Machine Learning)
        r'[a-z]+-[a-z]+',  # 连字符术语 (如 deep-learning, state-of-the-art)
        r'\d+[GBKM]',  # 大小单位 (如 16GB, 500MB)
        r'[a-z]{2,}\d+',  # 产品型号 (如 gpt4, llama3, iPhone15)
        r'[A-Z]{2,}',  # 全大写缩写 (如 API, NLP, AI)
    ]
    
    for pattern in tech_patterns:
        matches = re.findall(pattern, text)
        entities.extend(matches)
    
    # 2. 中文实体提取（更全面的模式）
    # 人名：2-4个中文字符，可能包含·号（如 李·明）
    chinese_name_pattern = r'[\u4e00-\u9fa5]{2,4}(?:·[\u4e00-\u9fa5]{1,3})?'
    chinese_names = re.findall(chinese_name_pattern, text)
    entities.extend(chinese_names)
    
    # 3. 常见的中文名词短语（2-6个字符的技术术语、概念、产品名等）
    # 匹配：数字+单位、形容词+名词、名词+名词等常见组合
    chinese_concept_patterns = [
        r'[\u4e00-\u9fa5]{2,6}',  # 2-6个汉字的名词短语（会匹配很多，需要后续过滤）
    ]
    for pattern in chinese_concept_patterns:
        matches = re.findall(pattern, text)
        # 过滤掉常见的停用词和虚词
        stop_words = {'这个', '那个', '什么', '如何', '怎么', '为什么', '因为', '所以', '但是', '然而', 
                     '可以', '应该', '需要', '如果', '那么', '或者', '而且', '以及', '等等', '例如',
                     '还有', '另外', '首先', '其次', '最后', '然后', '接下来', '同时', '因此'}
        filtered_matches = [m for m in matches if len(m) >= 2 and m not in stop_words]
        entities.extend(filtered_matches)
    
    # 4. 提取引号内的内容（通常是重要概念、引用）
    quoted = re.findall(r'["""](.*?)["""]', text)
    entities.extend(quoted)
    
    # 5. 提取【】内的内容（中文常用强调格式）
    bracketed = re.findall(r'【(.*?)】', text)
    entities.extend(bracketed)
    
    # 6. 提取《》内的内容（书名、作品名）
    book_titles = re.findall(r'《(.*?)》', text)
    entities.extend(book_titles)
    
    # 7. 提取常见的关键词模式（如果文本中有明确的主题词）
    # 匹配"关于XXX"、"XXX的"等模式
    topic_patterns = [
        r'关于([\u4e00-\u9fa5]{2,10})',
        r'([\u4e00-\u9fa5]{2,10})的',
        r'(?:介绍|讲解|说明|分析)([^，。：;]{2,10})',
    ]
    for pattern in topic_patterns:
        matches = re.findall(pattern, text)
        entities.extend(matches)
    
    # 去重并过滤
    entities = list(set([e.strip() for e in entities if 2 <= len(e) <= 30]))
    
    # 按长度和重要性排序（短的可能更重要，如"AI"、"Python"）
    entities.sort(key=lambda x: (len(x), x))
    
    return entities[:25]  # 返回最多25个实体（增加数量以覆盖更多领域）


def compress_conversation_history_rule_based(
    conversation_history: List[Dict],
    current_query: str,
    max_messages: int = 4,
    max_compressed_length: int = 800,
    min_total_length: int = 1600
) -> Optional[str]:
    """
    基于规则的上下文压缩（通用版本，适配不同问题领域）
    
    策略：
    1. 提取最近几轮对话的关键实体和概念（支持技术、文学、艺术、历史等）
    2. 提取用户提到的主要主题（保留完整的问题表述）
    3. 提取AI回答中的核心要点（不仅仅是第一句，包含关键信息句）
    4. 保留对话逻辑和关联性（通过实体关联）
    5. 过滤掉无关的细节，但保留领域相关的关键信息
    
    适用领域：
    - ✅ 技术/产品：实体提取效果好
    - ✅ 学术研究：保留关键概念和术语
    - ✅ 历史/文化：提取人名、地名、作品名
    - ⚠️ 文学/艺术：保留引号和作品名，但可能丢失情感细节
    - ⚠️ 抽象讨论：依赖实体提取，可能不够深入
    """
    if not conversation_history or len(conversation_history) <= max_messages:
        return None
    
    try:
        total_length = sum(len(msg.get("content", "")) for msg in conversation_history)
        if total_length <= min_total_length:
            return None
        
        # 提取最近的对话（用于分析）
        recent_history = conversation_history[-max_messages*2:]
        
        # 收集关键信息
        user_queries = []
        ai_summaries = []
        key_entities = set()
        
        for msg in recent_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if not content:
                continue
            
            if role == "user" and content != current_query:
                user_queries.append(content)
                # 提取实体
                entities = extract_key_entities(content)
                key_entities.update(entities)
            
            elif role == "assistant":
                # 提取AI回答的关键句子（不仅限前3句）
                # 分句处理（考虑中英文标点）
                sentences = re.split(r'[。！？\n]|\.\s+|! |\? ', content)
                sentences = [s.strip() for s in sentences if s.strip()]
                
                # 提取关键句子策略：
                # 1. 第一句（通常是总结或开头）
                # 2. 包含最多实体的句子（核心内容）
                # 3. 包含引号或特殊标记的句子（重要引用或强调）
                
                key_sentences = []
                
                # 添加第一句（如果存在）
                if sentences:
                    first_sentence = sentences[0]
                    if len(first_sentence) > 0:
                        key_sentences.append(first_sentence)
                
                # 找出包含最多实体的句子（更可能是核心内容）
                if len(sentences) > 1:
                    sentence_entity_counts = []
                    for i, sent in enumerate(sentences[:10]):  # 只检查前10句（避免太长）
                        entities_in_sent = extract_key_entities(sent)
                        # 给包含引号、书名号等的句子加分
                        score = len(entities_in_sent)
                        if '""' in sent or '"' in sent or '《' in sent or '【' in sent:
                            score += 3
                        if i > 0:  # 第一句已经添加，其他句子加分少一点
                            score += 1
                        sentence_entity_counts.append((score, i, sent))
                    
                    # 按分数排序，取前2个（排除已经添加的第一句）
                    sentence_entity_counts.sort(reverse=True)
                    for score, idx, sent in sentence_entity_counts[:2]:
                        if idx != 0:  # 避免重复添加第一句
                            key_sentences.append(sent)
                
                # 构建摘要（最多3个关键句子）
                for sent in key_sentences[:3]:
                    if len(sent) > 200:
                        sent = sent[:200] + "..."
                    ai_summaries.append(sent)
                
                # 提取关键实体（从整个内容中提取，不仅仅是前500字符）
                # 但为了避免过长，分段落提取
                content_sample = content[:1000] if len(content) > 1000 else content  # 取前1000字符
                entities = extract_key_entities(content_sample)
                key_entities.update(entities)
        
        # 构建压缩后的上下文
        compressed_parts = []
        
        # 1. 用户之前的问题
        if user_queries:
            # 如果用户问题很长，只保留核心部分
            for q in user_queries[-2:]:  # 最多保留最近2个问题
                if len(q) > 100:
                    # 尝试提取问题关键词部分
                    q_short = q[:100] + "..."
                else:
                    q_short = q
                compressed_parts.append(f"用户提到: {q_short}")
        
        # 2. 核心实体和概念（按重要性排序）
        if key_entities:
            # 更全面的停用词过滤
            stop_words = {
                '这个', '那个', '什么', '如何', '怎么', '为什么', '因为', '所以', '但是', '然而',
                '可以', '应该', '需要', '如果', '那么', '或者', '而且', '以及', '等等', '例如',
                '还有', '另外', '首先', '其次', '最后', '然后', '接下来', '同时', '因此',
                '一下', '一点', '一些', '一种', '一个', '一般', '一直', '一定', '一样',
                '很好', '非常', '比较', '相当', '可能', '也许', '大概', '应该',
            }
            
            # 过滤并去重
            filtered_entities = [
                e for e in key_entities 
                if len(e) >= 2 and e not in stop_words 
                and not e.isdigit()  # 排除纯数字
            ]
            
            # 按长度和类型排序（短词可能在前面，但也要考虑多样性）
            # 优先保留：有特殊格式的（引号、书名号）、英文专有名词、技术术语
            def entity_score(entity):
                score = 0
                # 包含大写字母的加分（可能是专有名词）
                if re.search(r'[A-Z]', entity):
                    score += 10
                # 包含数字的加分（可能是版本号、型号）
                if re.search(r'\d', entity):
                    score += 5
                # 包含连字符的加分（可能是复合术语）
                if '-' in entity:
                    score += 5
                # 长度适中的加分（2-8字符最佳）
                if 2 <= len(entity) <= 8:
                    score += 3
                return score
            
            filtered_entities.sort(key=lambda x: (entity_score(x), -len(x)), reverse=True)
            
            if filtered_entities:
                entities_str = "、".join(filtered_entities[:20])  # 增加到20个实体以提高覆盖率
                compressed_parts.append(f"涉及的关键概念: {entities_str}")
        
        # 3. AI之前回答的要点（保留更多关键句子）
        if ai_summaries:
            # 去重（避免重复的句子）
            unique_summaries = []
            seen = set()
            for summary in ai_summaries:
                summary_normalized = summary[:50].strip()  # 用前50字符作为唯一标识
                if summary_normalized not in seen:
                    unique_summaries.append(summary)
                    seen.add(summary_normalized)
            
            for summary in unique_summaries[:3]:  # 增加到最多3个摘要，提高信息保留率
                compressed_parts.append(f"AI之前回答要点: {summary}")
        
        if compressed_parts:
            compressed = "\n".join(compressed_parts)
            # 确保不超过最大长度
            if len(compressed) > max_compressed_length:
                compressed = compressed[:max_compressed_length] + "..."
            
            logger.info(f"📦 [规则压缩] 对话历史已压缩: {total_length} 字符 → {len(compressed)} 字符")
            return compressed
        
        return None
        
    except Exception as e:
        logger.error(f"❌ 规则压缩失败: {e}", exc_info=True)
        return None


def compress_conversation_history_smart_truncate(
    conversation_history: List[Dict],
    current_query: str,
    max_messages: int = 4,
    max_compressed_length: int = 800,
    min_total_length: int = 1600
) -> Optional[str]:
    """
    智能截断压缩：保留最重要的开头和结尾部分
    
    策略：
    - 保留用户第一次提到的核心问题（开头）
    - 保留最近几轮对话的关键信息（结尾）
    - 中间部分用摘要代替
    """
    if not conversation_history or len(conversation_history) <= max_messages:
        return None
    
    try:
        total_length = sum(len(msg.get("content", "")) for msg in conversation_history)
        if total_length <= min_total_length:
            return None
        
        # 提取开头和结尾
        start_messages = conversation_history[:max_messages]
        end_messages = conversation_history[-max_messages:]
        
        compressed_parts = []
        
        # 开头：用户最初的问题
        for msg in start_messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if content and content != current_query:
                    compressed_parts.append(f"最初问题: {content[:150]}")
                    break
        
        # 结尾：最近的对话
        recent_user_query = None
        for msg in reversed(end_messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if role == "user" and content and content != current_query:
                recent_user_query = content[:100] if len(content) > 100 else content
                break
        
        if recent_user_query:
            compressed_parts.append(f"最近提到: {recent_user_query}")
        
        # 如果有中间部分被省略，添加说明
        if len(conversation_history) > max_messages * 2:
            compressed_parts.append(f"（省略中间 {len(conversation_history) - max_messages * 2} 轮对话）")
        
        if compressed_parts:
            compressed = "\n".join(compressed_parts)
            if len(compressed) > max_compressed_length:
                compressed = compressed[:max_compressed_length] + "..."
            
            logger.info(f"📦 [智能截断] 对话历史已压缩: {total_length} 字符 → {len(compressed)} 字符")
            return compressed
        
        return None
        
    except Exception as e:
        logger.error(f"❌ 智能截断失败: {e}", exc_info=True)
        return None


def compress_conversation_history(
    conversation_history: List[Dict],
    current_query: str,
    max_messages: int = 4,
    max_compressed_length: int = 800,
    min_total_length: int = 1600,
    compression_method: str = "rule_based",  # "rule_based", "smart_truncate", "llm"
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> Optional[str]:
    """
    压缩对话历史，提取与当前查询最相关的关键信息
    
    支持多种压缩方法：
    - "rule_based": 基于规则的压缩（快速，无需API调用）
    - "smart_truncate": 智能截断（快速，保留开头和结尾）
    - "llm": 使用LLM压缩（最准确，但需要API调用）
    
    Args:
        conversation_history: 完整对话历史
        current_query: 当前用户查询
        max_messages: 最多保留的消息数量（如果历史较短，不压缩）
        max_compressed_length: 压缩后文本的最大长度（字符）
        min_total_length: 历史对话总字符数阈值，超过此值才开始压缩
        compression_method: 压缩方法 ("rule_based", "smart_truncate", "llm")
        api_key: 智谱清言API密钥（仅llm方法需要）
        model: 智谱清言模型名称（仅llm方法需要）
    
    Returns:
        压缩后的上下文文本（字符串），如果没有历史或不需要压缩则返回None
    """
    if not conversation_history or len(conversation_history) <= max_messages:
        # 如果历史很短，不需要压缩
        return None
    
    # 根据压缩方法选择策略
    if compression_method == "rule_based":
        return compress_conversation_history_rule_based(
            conversation_history=conversation_history,
            current_query=current_query,
            max_messages=max_messages,
            max_compressed_length=max_compressed_length,
            min_total_length=min_total_length
        )
    
    elif compression_method == "smart_truncate":
        return compress_conversation_history_smart_truncate(
            conversation_history=conversation_history,
            current_query=current_query,
            max_messages=max_messages,
            max_compressed_length=max_compressed_length,
            min_total_length=min_total_length
        )
    
    elif compression_method == "llm":
        # LLM压缩（原有的实现）
        try:
            # 计算原始文本长度
            total_length = sum(len(msg.get("content", "")) for msg in conversation_history)
            
            # 如果总长度已经很小，不需要压缩
            if total_length <= min_total_length:
                return None
            
            # 提取对话历史的关键信息
            history_text_parts = []
            for i, msg in enumerate(conversation_history[-max_messages*2:]):  # 取最近的消息用于摘要
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "user":
                    history_text_parts.append(f"用户: {content}")
                elif role == "assistant":
                    # 对AI回答进行截断，只保留前500字符用于摘要
                    content_preview = content[:500] + "..." if len(content) > 500 else content
                    history_text_parts.append(f"AI: {content_preview}")
            
            history_text = "\n".join(history_text_parts)
            
            # 使用LLM压缩历史对话
            prompt = f"""请对以下对话历史进行压缩摘要，提取与当前查询最相关的关键信息。

当前查询：{current_query}

对话历史：
{history_text}

**压缩要求**：
1. 只保留与当前查询相关的核心概念、实体、主题
2. 如果当前查询是不完整的（如"用表格对比"、"详细说明"），必须保留历史中提到的核心概念（如"开源大模型"）
3. 删除无关的细节、冗余信息、重复内容、冗长的思考过程
4. 重点提取：实体名称、关键概念、讨论主题、用户意图
5. 忽略：详细的推理过程、长篇解释、重复的总结
6. 保持关键信息完整，但要尽量简洁
7. 输出格式：用简洁的文本描述历史对话中的关键信息，控制在{max_compressed_length}字以内

**重要**：如果当前查询看起来是对之前讨论的延续或补充，必须保留历史中提到的核心主题和关键概念。

压缩摘要："""
            
            try:
                compressed = call_zhipu_llm(
                    prompt=prompt,
                    api_key=api_key,
                    model=model,
                    temperature=0.3,  # 较低温度保证摘要准确性
                    max_tokens=600   # 控制输出长度
                )
            except Exception as e:
                logger.warning(f"⚠️ 调用LLM压缩失败: {e}，跳过压缩")
                compressed = None
            
            if compressed and len(compressed.strip()) > 0:
                # 确保不超过最大长度
                if len(compressed) > max_compressed_length:
                    compressed = compressed[:max_compressed_length] + "..."
                logger.info(f"📦 [LLM压缩] 对话历史已压缩: {total_length} 字符 → {len(compressed)} 字符")
                return compressed
            else:
                logger.warning("⚠️ LLM对话历史压缩失败，返回None")
                return None
                
        except Exception as e:
            logger.error(f"❌ LLM压缩失败: {e}", exc_info=True)
            return None
    
    else:
        logger.warning(f"⚠️ 未知的压缩方法: {compression_method}，使用规则压缩")
        return compress_conversation_history_rule_based(
            conversation_history=conversation_history,
            current_query=current_query,
            max_messages=max_messages,
            max_compressed_length=max_compressed_length,
            min_total_length=min_total_length
        )


def extract_keywords(
    query: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    understanding: Optional[str] = None,
    conversation_history: Optional[List[Dict]] = None
) -> Optional[dict]:
    """
    使用智谱清言模型提取搜索关键词
    
    Args:
        query: 用户查询文本
        api_key: 智谱清言API密钥，如果为None则使用默认值
        model: 智谱清言模型名称，如果为None则使用默认值
        understanding: 问题理解结果（可选），如果提供，将基于理解结果生成更全面的关键词
    
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
        
        # 构建上下文信息（使用压缩技术）
        context_info = ""
        if conversation_history:
            # 尝试压缩对话历史（使用默认配置，因为extract_keywords可能被独立调用）
            # 优先使用规则压缩（快速，无需API调用）
            compressed_context = compress_conversation_history(
                conversation_history=conversation_history,
                current_query=query,
                max_messages=4,  # 如果历史≤4条消息，不压缩（默认值，可在调用时覆盖）
                max_compressed_length=500,  # 压缩后最多500字符
                min_total_length=1000,  # 默认字符阈值（可在调用时覆盖）
                compression_method="rule_based",  # 使用规则压缩（快速，无需API）
                api_key=api_key,
                model=model
            )
            
            # 如果规则压缩失败，尝试智能截断
            if not compressed_context:
                compressed_context = compress_conversation_history(
                    conversation_history=conversation_history,
                    current_query=query,
                    max_messages=4,
                    max_compressed_length=500,
                    min_total_length=1000,
                    compression_method="smart_truncate"
                )
            
            if compressed_context:
                # 使用压缩后的上下文
                context_info = f"""

**对话上下文摘要**（重要！请结合上下文提取关键词）：
{compressed_context}

**注意**：如果当前问题是简短的不完整表述（如"用表格对比"、"详细说明"、"还有哪些"等），请结合上下文中的核心概念提取关键词。
例如：用户说"用表格对比"，但上下文中提到过"开源大模型"，应该提取"开源大模型 表格 对比 比较"等关键词。
"""
            else:
                # 如果压缩失败或不需要压缩，使用简单的截断方式
                recent_history = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
                context_parts = []
                for msg in recent_history:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if role == "user" and content and content != query:
                        context_parts.append(f"- 用户之前提到: {content}")
                    elif role == "assistant" and content:
                        content_preview = content[:100] + "..." if len(content) > 100 else content
                        context_parts.append(f"- AI之前回答: {content_preview}")
                
                if context_parts:
                    context_info = f"""

**对话上下文**（重要！请结合上下文提取关键词）：
{chr(10).join(context_parts)}

**注意**：如果当前问题是简短的不完整表述（如"用表格对比"、"详细说明"、"还有哪些"等），请结合上下文中的核心概念提取关键词。
例如：用户说"用表格对比"，但上下文中提到过"开源大模型"，应该提取"开源大模型 表格 对比 比较"等关键词。
"""
        
        # 构建Prompt（根据是否有理解结果选择不同的prompt）
        if understanding:
            # 深度模式：基于问题理解生成更全面的关键词
            prompt = f"""今天是{current_date}。你是一个专业的搜索关键词提取专家。基于对用户问题的深度理解，提取全面的搜索关键词。

用户当前问题：{query}{context_info}

问题理解：
{understanding}

**任务要求：**
1. 基于问题理解，提取涵盖用户所有潜在需求的搜索关键词
2. 关键词应该覆盖问题的多个维度：
   - **核心概念**：问题的主体、相关术语、同义词
   - **关键属性**：特征、参数、规格、品牌、版本等
   - **评估维度**：评测、对比、优缺点、排名、评价等
   - **实用信息**：应用、使用、购买、获取、教程等
   - **时间限定**：如果涉及"最新"、"最近"，必须加上{now.year}年或{now.month}月

3. **输出格式（JSON）**：
   - zh_keys: 中文关键词，用空格分隔，15-20个
   - en_keys: 英文关键词，用空格分隔，15-20个
   - 英文关键词要包含完整术语和常用缩写

**示例**（仅供参考，需根据实际问题灵活调整）：
1. 技术问题："Python和Java哪个好？"
{{
  "zh_keys": "Python Java 编程语言对比 优缺点 学习难度 应用领域 性能对比 就业前景 开发效率 生态系统 适用场景 {now.year}年",
  "en_keys": "Python Java programming language comparison pros cons learning curve application domain performance job market development efficiency ecosystem use case {now.year}"
}}

2. 消费问题："iPhone 15值得买吗？"
{{
  "zh_keys": "iPhone 15 苹果手机 值得购买 性能评测 价格 优缺点 用户评价 对比iPhone14 参数配置 购买建议 {now.year}年",
  "en_keys": "iPhone 15 Apple smartphone worth buying performance review price pros cons user review comparison iPhone14 specs buying guide {now.year}"
}}

现在，请为用户问题提取关键词："""
        else:
            # 快速模式：原有的简单关键词提取（如果有上下文，也加上）
            prompt_base = f"""今天是{current_date}。为了给用户的回答保持准确，你需要使用搜索引擎。使用json格式返回关键词，属性为zh_keys,en_keys。每个属性只需要一行，关键词用空格分隔。仅需返回重要关键词，每行不超过10个。对于英语关键词，除了完整翻译，还可以加上相关缩写。如果语句中包含"最近"，"最新"等词语，根据需要加上年份或者月份，年份和月份不能连在一起。"""
            
            if context_info:
                prompt = f"""{prompt_base}

**对话上下文**（重要！请结合上下文提取关键词）：
{context_info}

**注意**：如果当前问题是简短的不完整表述，请结合上下文中的核心概念提取关键词。

现在从下面这句话中提取用于搜索引擎的关键词：{query}"""
            else:
                prompt = f"""{prompt_base}从下面这句话中提取用于搜索引擎的关键词：{query}"""
        
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
        
        # 添加重试机制（最多3次）
        max_retries = 3
        retry_delay = 2  # 重试间隔（秒）
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    ZHIPU_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=30  # 增加超时时间到30秒，与call_zhipu_llm一致
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
                    
            except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)  # 指数退避
                    logger.warning(f"⚠️ 关键词提取超时（尝试 {attempt + 1}/{max_retries}），{wait_time}秒后重试...")
                    import time
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ 关键词提取失败（已重试{max_retries}次）: {e}")
                    raise
            except Exception as e:
                # 其他错误直接抛出，不重试
                logger.error(f"❌ 关键词提取失败: {e}")
                raise
            
    except Exception as e:
        logger.error(f"❌ 关键词提取失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def call_zhipu_llm(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    response_format: Optional[dict] = None
) -> Optional[str]:
    """
    通用的智谱清言 LLM 调用函数
    
    Args:
        prompt: 提示词
        api_key: 智谱清言API密钥，如果为None则使用默认值
        model: 智谱清言模型名称，如果为None则使用默认值
        temperature: 温度参数
        max_tokens: 最大token数
        response_format: 响应格式（如 {"type": "json_object"}）
    
    Returns:
        LLM返回的文本内容，失败返回None
    """
    try:
        zhipu_api_key = api_key if api_key is not None else ZHIPU_API_KEY
        zhipu_model = model if model is not None else ZHIPU_MODEL
        
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
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
            "do_sample": True,
            "top_p": 0.95,
            "tool_stream": False
        }
        
        # 如果指定了响应格式，添加到payload
        if response_format:
            payload["response_format"] = response_format
        
        # 添加重试机制（最多3次）
        max_retries = 3
        retry_delay = 2  # 重试间隔（秒）
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    ZHIPU_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                
                response.raise_for_status()
                result = response.json()
                
                # 解析返回的JSON
                choices = result.get("choices", [])
                if not choices:
                    logger.warning("⚠️ 智谱清言API返回空choices")
                    return None
                
                message = choices[0].get("message", {})
                content = message.get("content", "").strip()
                
                if not content:
                    logger.warning("⚠️ 智谱清言API返回空内容")
                    return None
                
                return content
                
            except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)  # 指数退避
                    logger.warning(f"⚠️ 智谱清言API超时（尝试 {attempt + 1}/{max_retries}），{wait_time}秒后重试...")
                    import time
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ 智谱清言调用失败（已重试{max_retries}次）: {e}")
                    raise
            except Exception as e:
                # 其他错误直接抛出，不重试
                logger.error(f"❌ 智谱清言调用失败: {e}")
                raise
            
    except Exception as e:
        logger.error(f"❌ 智谱清言调用失败: {e}")
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