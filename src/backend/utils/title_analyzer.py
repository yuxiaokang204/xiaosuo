"""
通用标题分析器 — 轻量级 LLM 调用，从任意小说标题中提取结构化核心要素

设计原则：
- 通用性：不硬编码任何具体关键词，适用于任何标题
- 轻量级：仅一次 LLM 调用，结果缓存供所有后续 Agent 使用
- 容错：分析失败时回退到空结果，不阻断主流程

示例：
  输入: "直播研发丧尸病毒，全网吓哭"
  输出: {
    "title": "直播研发丧尸病毒，全网吓哭",
    "keywords": ["直播", "研发", "丧尸", "病毒", "全网", "吓哭"],
    "themes": ["末日生存", "科幻", "社会讽刺"],
    "genre_hints": ["直播流", "灾难", "黑色幽默"],
    "tone": "紧张恐怖中带有黑色幽默",
    "unique_elements": ["直播叙事框架", "病毒研发者视角", "社会反响驱动"],
    "story_premise": "一名主角通过直播展示丧尸病毒的研发过程，引发全网震惊与恐慌",
    "prompt_inject": "【标题核心要素】本故事必须围绕'直播'（叙事框架）、'丧尸病毒研发'（核心事件）、'全网反响'（社会影响）三个维度展开。"
  }
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# LLM 系统提示词：指导 LLM 如何分析标题
_TITLE_ANALYZER_SYSTEM_PROMPT = """你是一位专业的小说标题分析师。你的任务是从小说标题中提取结构化核心要素，
以便后续的创作 Agent 能围绕这些要素展开内容生成。

分析规则：
1. keywords: 提取标题中所有有意义的词汇（2-4字为佳），去除无意义虚词
2. themes: 推断标题暗示的主题（2-4个），如"末日生存"、"科幻"、"成长"等
3. genre_hints: 推断标题暗示的题材类型（2-4个），如"升级流"、"御兽流"、"系统流"等
4. tone: 一句话描述标题传达的情绪基调
5. unique_elements: 提取标题中最独特、最具辨识度的元素（2-4个），这些是与其他标题区分开的关键
6. story_premise: 用一句话概括标题暗示的核心故事前提（30字以内）
7. prompt_inject: 生成一段可直接注入创作 Agent prompt 的强化指令，
   要求后续创作必须围绕提取的核心要素展开，用中文输出

输出格式：严格 JSON，无任何额外文字
{
  "title": "原始标题",
  "keywords": ["关键词1", "关键词2"],
  "themes": ["主题1", "主题2"],
  "genre_hints": ["题材1", "题材2"],
  "tone": "情绪基调描述",
  "unique_elements": ["独特元素1", "独特元素2"],
  "story_premise": "一句话故事前提",
  "prompt_inject": "【标题核心要素】本故事必须围绕...展开。后续创作需确保..."
}"""


async def analyze_title(title: str, llm_client=None) -> Dict:
    """分析小说标题，提取结构化核心要素

    Args:
        title: 小说标题字符串
        llm_client: LLM 客户端（可选，不传则使用默认客户端）

    Returns:
        结构化分析结果字典，失败时返回包含 title 的空结果
    """
    if not title or not title.strip():
        return {"title": "", "keywords": [], "themes": [], "genre_hints": [],
                "tone": "", "unique_elements": [], "story_premise": "", "prompt_inject": ""}

    result = {
        "title": title,
        "keywords": [],
        "themes": [],
        "genre_hints": [],
        "tone": "",
        "unique_elements": [],
        "story_premise": "",
        "prompt_inject": "",
    }

    try:
        from ..llm.client import LLMMessage, get_default_llm_client

        client = llm_client or get_default_llm_client()

        user_prompt = f"""请分析以下小说标题，提取结构化核心要素：

标题：《{title}》

请严格按照以下 JSON 格式输出，不要包含任何额外文字：
{{
  "title": "{title}",
  "keywords": [...],
  "themes": [...],
  "genre_hints": [...],
  "tone": "...",
  "unique_elements": [...],
  "story_premise": "...",
  "prompt_inject": "..."
}}"""

        response = await client.generate(
            [LLMMessage(role="user", content=user_prompt)],
            system_prompt=_TITLE_ANALYZER_SYSTEM_PROMPT,
            temperature=0.3,  # 低温度确保稳定输出
            max_tokens=600,
        )

        content = (response.content or "").strip()

        # 尝试解析 JSON
        import json
        import re
        try:
            # 提取 ```json ... ``` 代码块
            code_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', content)
            if code_match:
                content = code_match.group(1).strip()
            parsed = json.loads(content)
            result.update(parsed)
            logger.info(f"[TitleAnalyzer] ✅ 标题分析完成: {title[:20]}...")
        except (json.JSONDecodeError, AttributeError):
            logger.warning(f"[TitleAnalyzer] ⚠️ JSON 解析失败，使用回退结果")
            result["prompt_inject"] = f"【标题核心要素】本故事需围绕标题《{title}》中的核心意象展开。"

    except Exception as e:
        logger.warning(f"[TitleAnalyzer] ⚠️ 标题分析失败（非致命）: {e}")
        result["prompt_inject"] = f"【标题核心要素】本故事需围绕标题《{title}》中的核心意象展开。"

    return result
