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
    - 链接：[text](url) -> text
    - Emoji表情符号
    
    Args:
        text: 原始文本（可能包含Markdown）
        
    Returns:
        清理后的纯文本
    """
    if not text:
        return text
    
    # 0. 去除emoji表情符号（在其他处理之前）
    # 匹配常见的emoji Unicode范围
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符号
        "\U0001F300-\U0001F5FF"  # 符号和象形文字
        "\U0001F680-\U0001F6FF"  # 交通和地图符号
        "\U0001F1E0-\U0001F1FF"  # 旗帜
        "\U00002600-\U000027BF"  # 杂项符号
        "\U0001F900-\U0001F9FF"  # 补充符号和象形文字
        "\U0001FA00-\U0001FA6F"  # 扩展A
        "\U0001FA70-\U0001FAFF"  # 扩展B
        "\U00002702-\U000027B0"  # 装饰符号
        "\U000024C2-\U0001F251"  # 封闭字符
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    # 1. 代码块（多行）
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    # 2. 行内代码
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # 3. 加粗和斜体（**text** 或 __text__）
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    
    # 4. 斜体（*text* 或 _text_）
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    # 5. 删除线（~~text~~）
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    
    # 6. 标题（# 、## 等）
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # 7. 列表标记（- 、* 、+ 、1. 等）
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # 8. 链接（[text](url)）
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
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
