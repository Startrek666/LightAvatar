"""
文本处理工具
"""
import re


def clean_markdown_for_tts(text: str) -> str:
    """
    清理Markdown格式符号，准备用于TTS
    
    保留文字内容，去除格式符号：
    - 加粗：**text** -> text
    - 斜体：*text* -> text
    - 代码块：```code``` -> code
    - 行内代码：`code` -> code
    - 标题：# Title -> Title
    - 列表：- item -> item
    - Markdown链接：[text](url) -> text
    - 纯URL链接：https://example.com -> 移除（不读出）
    - Emoji表情符号
    - 引用标记：[citation:X] -> 移除（不读出）
    - 参考来源部分：完整移除（不读出）
    
    Args:
        text: 原始文本（可能包含Markdown）
        
    Returns:
        清理后的纯文本
    """
    if not text:
        return text
    
    original_text = text  # 保存原文用于调试
    
    # 0. 移除"参考来源"部分（包括标题和所有引用列表）
    # 匹配格式：**📚 参考来源：**\n1. [标题](URL)\n2. [标题](URL)...
    # 使用更精确的正则表达式，匹配整个参考来源块
    text = re.sub(
        r'\*\*📚\s*参考来源[：:]\*\*\s*\n(?:\d+\.\s*\[.*?\]\(.*?\)\s*)+',
        '',
        text,
        flags=re.DOTALL
    )
    
    # 如果文本被修改，说明成功移除了参考来源部分
    if len(text) != len(original_text):
        from loguru import logger
        logger.debug(f"✂️ 已移除参考来源部分 (从 {len(original_text)} 字符减少到 {len(text)} 字符)")
    
    # 移除引用标记 [citation:X] 或 [citation:X, Y] 或 [citation: X]（不读出）
    # 匹配格式：[citation:1], [citation:1, 9], [citation: 12], [citation:1, 12, 40] 等
    before_citation_remove = text
    # 更全面的正则表达式，匹配所有可能的citation格式（包括空格、多个数字等）
    text = re.sub(r'\[citation\s*:\s*[\d\s,]+\]', '', text, flags=re.IGNORECASE)
    
    if len(text) != len(before_citation_remove):
        from loguru import logger
        logger.debug(f"✂️ 已移除引用标记 (从 {len(before_citation_remove)} 字符减少到 {len(text)} 字符)")
    
    # 0. 去除emoji表情符号（在其他处理之前）
    # 使用更精确的emoji Unicode范围（避免误删中文字符）
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符号
        "\U0001F300-\U0001F5FF"  # 符号和象形文字
        "\U0001F680-\U0001F6FF"  # 交通和地图符号
        "\U0001F1E0-\U0001F1FF"  # 旗帜
        "\U0001F900-\U0001F9FF"  # 补充符号和象形文字
        "\U0001FA00-\U0001FA6F"  # 扩展A
        "\U0001FA70-\U0001FAFF"  # 扩展B
        "\u2600-\u27BF"          # 杂项符号（修正范围）
        "\u2702-\u27B0"          # 装饰符号（修正范围）
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    # 1. 代码块（多行）
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    # 2. 行内代码
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # 3. 加粗和斜体（**text** 或 __text__）
    # 先移除成对的加粗标记（保留文本内容）
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    
    # 移除所有剩余的 ** 和 __（防止有未匹配或单独的标记）
    text = re.sub(r'\*\*+', '', text)  # 移除连续的星号（**、***等）
    text = re.sub(r'__+', '', text)    # 移除连续的下划线（__、___等）
    
    # 4. 斜体（*text* 或 _text_）
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    # 移除所有剩余的单独的 * 和 _（防止有未匹配的标记）
    # 注意：这里要小心，不要移除中文书名号中的下划线
    text = re.sub(r'(?<!\*)\*(?!\*)', '', text)  # 移除单独的星号
    text = re.sub(r'(?<!_)_(?!_)', '', text)    # 移除单独的下划线
    
    # 5. 删除线（~~text~~）
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    
    # 6. 标题（# 、## 等）
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # 7. 列表标记（- 、* 、+ 、1. 等）
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # 8. 链接（[text](url)）
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # 8.5. 纯URL链接（http://、https://、www. 开头的链接）
    # 匹配各种URL格式：http://、https://、www.、ftp:// 等
    # 匹配到句末或空格，或者被括号包围的URL
    url_pattern = r'(?:https?://|www\.|ftp://)[^\s\)\]\}\"\'<>]+'
    removed_urls = re.findall(url_pattern, text)
    text = re.sub(url_pattern, '', text)
    
    # 记录移除的URL数量（用于调试）
    if removed_urls:
        from loguru import logger
        logger.debug(f"✂️ 已移除 {len(removed_urls)} 个纯URL链接: {removed_urls[:3]}...")
    
    # 9. 图片（![alt](url)）
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
    
    # 10. 引用（> text）
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    
    # 11. 水平线（--- 、*** 等）
    text = re.sub(r'^[\s]*[-*_]{3,}[\s]*$', '', text, flags=re.MULTILINE)
    
    # 12. HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 13. 清理多余的空行和空格
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()


def has_speakable_content(text: str) -> bool:
    """
    检查文本是否包含可发音的内容
    
    过滤掉只包含标点符号、空白字符的文本，这些无法被TTS处理。
    
    Args:
        text: 待检查的文本
        
    Returns:
        True: 包含可发音内容
        False: 只包含标点符号/空白字符
    """
    if not text:
        return False
    
    # 移除所有空白字符和常见标点符号
    # 保留中文、英文、数字等可发音字符
    speakable = re.sub(r'[\s\.,;:!?。，、；：！？…\.]+', '', text)
    
    # 如果清理后还有内容，说明包含可发音字符
    return len(speakable) > 0


def split_long_text(text: str, max_length: int = 200) -> list:
    """
    将长文本分割成多个片段，便于TTS处理
    
    Args:
        text: 原始文本
        max_length: 每个片段的最大长度
        
    Returns:
        文本片段列表
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # 按句子分割
    sentences = re.split(r'([。！？.!?\n])', text)
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        delimiter = sentences[i + 1] if i + 1 < len(sentences) else ""
        full_sentence = sentence + delimiter
        
        if len(current_chunk) + len(full_sentence) <= max_length:
            current_chunk += full_sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = full_sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks
