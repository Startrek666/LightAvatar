"""
深度思考链（Thinking Chain）- 使用 LangChain 实现多步骤推理和深度分析
解决"回答缺乏深度思考，只是搜索结果拼接"的问题
"""
from typing import List, Dict, Optional, Any
from loguru import logger

from backend.handlers.search.momo_utils import SearchDocument


class ThinkingChain:
    """
    思考链：通过多步骤推理生成深度思考的回答
    
    流程：
    1. 理解问题：分析用户意图和需求
    2. 分析资料：批判性分析搜索结果的可靠性和相关性
    3. 深度思考：进行推理、对比、总结
    4. 生成回答：综合思考结果生成高质量回答
    5. 自我审查：检查回答的逻辑性和完整性
    """
    
    def __init__(self):
        self.enabled = True
    
    def build_thinking_prompt(
        self,
        user_query: str,
        search_results: List[SearchDocument],
        current_date: str
    ) -> str:
        """
        构建要求深度思考的 Prompt
        
        Args:
            user_query: 用户查询
            search_results: 搜索结果
            current_date: 当前日期
            
        Returns:
            完整的思考链 Prompt
        """
        # 检测用户查询的语言
        def detect_language(text: str) -> str:
            chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
            english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
            return "en" if english_chars > chinese_chars and english_chars > 0 else "zh"
        
        detected_lang = detect_language(user_query)
        
        # 根据检测到的语言添加强制指令
        if detected_lang == "en":
            lang_instruction = """
🔴🔴🔴 CRITICAL MANDATORY INSTRUCTION 🔴🔴🔴
The user's question is in ENGLISH. You MUST write your ENTIRE response in ENGLISH.
- All thinking steps: ENGLISH
- Final answer: ENGLISH
- Do NOT use any Chinese characters in your response.
This is a MANDATORY requirement that overrides all other instructions.
"""
        else:
            lang_instruction = """
🔴🔴🔴 重要强制指令 🔴🔴🔴
用户的问题是中文。你必须用中文撰写整个回答。
- 所有思考步骤：中文
- 最终答案：中文
- 不要在回答中使用任何英文字符。
这是强制要求，优先级高于所有其他指令。
"""
        
        # 构建搜索结果上下文
        search_context = self._build_search_context(search_results)
        
        # 构建思考链 Prompt
        thinking_prompt = f"""{lang_instruction}

# 角色定位
你是一位具有深度思考能力的AI助手。你的任务不是简单地总结搜索结果，而是要进行深度的分析、推理和思考，为用户提供有价值的见解。

# 当前日期
今天是 {current_date}

# 搜索结果
{search_context}

# 思考流程（请严格按照以下步骤进行思考）

## 第一步：理解问题（Problem Understanding）
请先深入理解用户的问题：
- 用户的核心需求是什么？
- 问题的背景和上下文是什么？
- 用户可能想要什么样的回答？（信息、分析、建议、对比等）
- 这个问题涉及哪些关键概念和领域？

**请写出你的理解：**

## 第二步：批判性分析资料（Critical Analysis）
对搜索结果进行批判性分析：
- 哪些资料最相关？为什么？
- 不同资料之间有什么一致性和差异？
- 资料的可靠性和权威性如何？
- 哪些信息可能过时或不准确？
- 是否存在观点冲突？如何理解这些冲突？

**请写出你的分析：**

## 第三步：深度思考与推理（Deep Thinking）
基于资料进行深度思考：
- 这些信息背后反映了什么趋势或规律？
- 不同观点或方案的优势和劣势是什么？
- 可以从哪些角度来分析这个问题？
- 有什么被忽视的重要方面？
- 如何将这些信息联系起来，形成更深入的见解？

**请写出你的思考：**

## 第四步：综合推理与结论（Synthesis）
综合前面的分析，形成自己的见解：
- 如何整合不同来源的信息？
- 可以得出什么有价值的结论？
- 有哪些重要的洞察或建议？
- 是否需要对多个角度进行对比分析？

**请写出你的综合结论：**

## 第五步：生成高质量回答（Response Generation）
基于以上思考，生成回答。要求：
- **不要简单罗列搜索结果**，而是要基于思考形成自己的观点
- **进行多角度分析**，不只是单一视角
- **提供有价值的洞察**，而不仅仅是事实陈述
- **逻辑清晰**，结构合理
- **引用资料**：在适当位置使用 [citation:X] 格式引用来源
- **语言自然**：回答应该流畅、专业，像专家在分享见解
- **语言匹配**：**必须使用与用户问题相同的语言回答**。如果用户用英语提问，必须用英语回答；如果用户用中文提问，必须用中文回答。这一点至关重要！

**回答格式要求：**
- 如果问题需要对比分析，请提供清晰的对比框架
- 如果问题需要建议，请提供有依据的建议
- 如果问题需要解释，请提供深入的解释和背景
- 始终记住：你是在分享**经过思考的见解**，而不是在**转述搜索结果**
- **重要：回答语言必须与用户问题语言完全一致**

# 用户问题
{user_query}

---

**现在，请按照上述五个步骤进行思考，然后生成高质量的回答。**"""
        
        return thinking_prompt
    
    def _build_search_context(self, search_results: List[SearchDocument]) -> str:
        """构建搜索结果上下文"""
        if not search_results:
            return "未找到相关搜索结果。"
        
        context_parts = []
        context_parts.append(f"共找到 {len(search_results)} 个相关搜索结果：\n")
        
        for idx, doc in enumerate(search_results[:20], 1):  # 限制前20个结果
            context_parts.append(f"[参考资料 {idx}]")
            context_parts.append(f"标题: {doc.title if hasattr(doc, 'title') else 'N/A'}")
            
            # 添加来源域名
            if hasattr(doc, 'url') and doc.url:
                from urllib.parse import urlparse
                try:
                    domain = urlparse(doc.url).netloc
                    context_parts.append(f"来源: {domain}")
                except:
                    context_parts.append(f"来源: 网络资料")
            
            # 添加内容
            content = doc.content if hasattr(doc, 'content') and doc.content else ''
            if not content and hasattr(doc, 'snippet'):
                content = doc.snippet
            
            if content:
                # 限制每个文档的内容长度
                content = content[:1500] if len(content) > 1500 else content
                context_parts.append(f"内容:\n{content}")
            
            context_parts.append("---\n")
        
        return "\n".join(context_parts)
    
    def build_synthesis_prompt(
        self,
        user_query: str,
        search_results: List[SearchDocument],
        current_date: str,
        thinking_results: dict
    ) -> str:
        """
        构建综合信息 Prompt（使用前面的思考结果）
        
        Args:
            user_query: 用户查询
            search_results: 搜索结果
            current_date: 当前日期
            thinking_results: 思考结果字典（包含 understanding, analysis, thinking）
            
        Returns:
            综合信息 Prompt
        """
        # 检测用户查询的语言
        def detect_language(text: str) -> str:
            chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
            english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
            return "en" if english_chars > chinese_chars and english_chars > 0 else "zh"
        
        detected_lang = detect_language(user_query)
        
        # 根据检测到的语言添加强制指令
        if detected_lang == "en":
            lang_instruction = """
🔴🔴🔴 CRITICAL MANDATORY INSTRUCTION 🔴🔴🔴
The user's question is in ENGLISH. You MUST write your ENTIRE response in ENGLISH.
Do NOT use any Chinese characters in your response.
This is a MANDATORY requirement that overrides all other instructions.
"""
        else:
            lang_instruction = """
🔴🔴🔴 重要强制指令 🔴🔴🔴
用户的问题是中文。你必须用中文撰写整个回答。
不要在回答中使用任何英文字符。
这是强制要求，优先级高于所有其他指令。
"""
        
        search_context = self._build_search_context(search_results)
        
        understanding = thinking_results.get("understanding", "")
        analysis = thinking_results.get("analysis", "")
        thinking = thinking_results.get("thinking", "")
        
        synthesis_prompt = f"""{lang_instruction}

# 角色定位
你是一位具有深度思考能力的AI助手。你的任务是基于前面的思考和分析，综合信息并生成高质量的回答。

# 当前日期
今天是 {current_date}

# 前面的思考过程

## 问题理解
{understanding if understanding else "（未提供）"}

## 资料分析
{analysis if analysis else "（未提供）"}

## 深度思考
{thinking if thinking else "（未提供）"}

# 搜索结果
{search_context}

# 任务：综合信息，生成高质量回答

请基于以上信息，生成回答。要求：

1. **综合前面的思考**：整合问题理解、资料分析和深度思考的结果
2. **提供有价值的洞察**：不仅仅是事实陈述，要提供经过思考的见解
3. **逻辑清晰**：结构合理，条理分明
4. **引用资料**：在适当位置使用 [citation:X] 格式引用来源
5. **语言自然**：回答应该流畅、专业，像专家在分享见解

**回答格式要求：**
- 如果问题需要对比分析，请提供清晰的对比框架
- 如果问题需要建议，请提供有依据的建议
- 如果问题需要解释，请提供深入的解释和背景
- 始终记住：你是在分享**经过深度思考的见解**，而不是在**转述搜索结果**

# 用户问题
{user_query}

---

**现在，请基于以上所有信息，生成高质量的回答。**"""
        
        return synthesis_prompt
    
    def build_reflection_prompt(
        self,
        original_query: str,
        generated_response: str,
        search_results: List[SearchDocument]
    ) -> str:
        """
        构建自我审查 Prompt（可选，用于进一步优化回答）
        
        Args:
            original_query: 原始查询
            generated_response: 生成的回答
            search_results: 搜索结果
            
        Returns:
            反思 Prompt
        """
        reflection_prompt = f"""# 自我审查任务
请对以下回答进行自我审查，确保质量：

## 原始问题
{original_query}

## 生成的回答
{generated_response}

## 审查要点
1. **逻辑性**：回答的逻辑是否清晰？推理是否合理？
2. **完整性**：是否充分回答了用户的问题？
3. **深度**：是否有足够的深度思考，还是只是表面信息的拼接？
4. **准确性**：引用是否正确？信息是否准确？
5. **价值**：是否提供了有价值的见解，而不仅仅是事实陈述？

## 改进建议
如果发现任何问题，请提供改进后的回答。如果回答已经很好，请说明为什么。"""
        
        return reflection_prompt
    
    def extract_thinking_steps(self, response: str) -> Dict[str, str]:
        """
        从 LLM 回答中提取思考步骤（用于调试和优化）
        
        Args:
            response: LLM 的完整回答
            
        Returns:
            包含各步骤的字典
        """
        steps = {
            "understanding": "",
            "analysis": "",
            "thinking": "",
            "synthesis": "",
            "final_response": ""
        }
        
        # 尝试提取各个步骤（如果 LLM 按照格式回答）
        # 这里可以根据实际 LLM 输出格式进行调整
        sections = response.split("## ")
        for section in sections:
            if "第一步" in section or "理解问题" in section:
                steps["understanding"] = section
            elif "第二步" in section or "批判性分析" in section:
                steps["analysis"] = section
            elif "第三步" in section or "深度思考" in section:
                steps["thinking"] = section
            elif "第四步" in section or "综合推理" in section:
                steps["synthesis"] = section
            elif "第五步" in section or "生成高质量回答" in section:
                steps["final_response"] = section
        
        return steps


def build_enhanced_search_prompt(
    user_query: str,
    search_results: List[SearchDocument],
    current_date: str,
    use_thinking_chain: bool = True,
    thinking_results: Optional[dict] = None
) -> str:
    """
    构建增强的搜索 Prompt（便捷函数）
    
    Args:
        user_query: 用户查询
        search_results: 搜索结果
        current_date: 当前日期
        use_thinking_chain: 是否使用思考链
        thinking_results: 思考结果字典（包含 understanding, analysis, thinking）
        
    Returns:
        完整的 Prompt
    """
    if use_thinking_chain:
        chain = ThinkingChain()
        # 如果有思考结果，使用综合信息模式
        if thinking_results and (thinking_results.get("understanding") or thinking_results.get("analysis") or thinking_results.get("thinking")):
            return chain.build_synthesis_prompt(user_query, search_results, current_date, thinking_results)
        else:
            # 否则使用原来的思考链模式
            return chain.build_thinking_prompt(user_query, search_results, current_date)
    else:
        # 回退到简单模式（向后兼容）
        return _build_simple_prompt(user_query, search_results, current_date)


def _build_simple_prompt(
    user_query: str,
    search_results: List[SearchDocument],
    current_date: str
) -> str:
    """构建简单的 Prompt（向后兼容）"""
    from urllib.parse import urlparse
    
    # 检测用户查询的语言
    def detect_language(text: str) -> str:
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        return "en" if english_chars > chinese_chars and english_chars > 0 else "zh"
    
    detected_lang = detect_language(user_query)
    
    # 根据检测到的语言添加强制指令
    if detected_lang == "en":
        lang_instruction = "🔴 CRITICAL: User's question is in ENGLISH. Answer in ENGLISH ONLY.\n\n"
    else:
        lang_instruction = "🔴 重要：用户问题是中文。只用中文回答。\n\n"
    
    context_parts = [lang_instruction + f"# 以下内容是基于用户发送的消息的搜索结果（今天是{current_date}）:\n"]
    
    for idx, doc in enumerate(search_results[:15], 1):
        context_parts.append(f"[参考资料 {idx}]")
        context_parts.append(f"标题: {doc.title if hasattr(doc, 'title') else 'N/A'}")
        
        if hasattr(doc, 'url') and doc.url:
            try:
                domain = urlparse(doc.url).netloc
                context_parts.append(f"来源: {domain}")
            except:
                pass
        
        content = doc.content if hasattr(doc, 'content') and doc.content else ''
        if not content and hasattr(doc, 'snippet'):
            content = doc.snippet
        
        if content:
            content = content[:1000] if len(content) > 1000 else content
            context_parts.append(f"内容:\n{content}")
        
        context_parts.append("---\n")
    
    context_parts.append("\n# 请基于以上参考资料，用自然严谨的方式回答用户的问题。")
    context_parts.append(f"\n# 用户问题: {user_query}")
    
    return "\n".join(context_parts)

