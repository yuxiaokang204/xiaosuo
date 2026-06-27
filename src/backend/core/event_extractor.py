"""
自动事件提取器 — 从生成的章节内容中提取关键信息

功能：
1. extract_key_events: 从章节正文提取 3-5 个关键事件
2. extract_character_changes: 识别出场角色及其状态变化
3. extract_new_foreshadowings: 检测新伏笔和已回收伏笔
4. 全部提供无 LLM 时的启发式回退方案
"""
import json
import re
from typing import Dict, List, Optional, Tuple

from ..llm.client import LLMClient, LLMMessage, get_default_llm_client


def _is_verbed_sentence(sent: str) -> bool:
    """判断句子是否包含动作（简单启发式）"""
    action_words = [
        "走", "来", "去", "说", "做", "想", "看", "听", "拿", "放",
        "站", "坐", "跑", "跳", "打", "问", "答", "开", "关", "进",
        "出", "上", "下", "回", "到", "过", "见", "找", "追", "逃",
        "杀", "救", "帮", "害", "爱", "恨", "哭", "笑", "喊", "叫",
        "写", "读", "想", "记", "忘", "做", "变", "成", "得", "失",
        "生", "死", "伤", "病", "好", "坏", "对", "错", "赢", "输",
    ]
    return any(w in sent for w in action_words)


def _extract_sentences(text: str) -> List[str]:
    """提取中文句子（按句号、感叹号、问号、换行分割）"""
    # 先按换行分
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # 再按句子结束符分
    sentences = []
    for line in lines:
        parts = re.split(r'[。！？!?；;]', line)
        for p in parts:
            p = p.strip()
            if len(p) >= 5:  # 过滤太短的
                sentences.append(p)
    return sentences


def extract_key_events_fallback(content: str) -> List[str]:
    """
    无 LLM 时的回退方案：从正文中提取关键事件。
    策略：找出包含动作词的段落首句。
    """
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    events: List[str] = []

    for para in paragraphs[:15]:  # 只看前 15 个段落
        sentences = _extract_sentences(para)
        for sent in sentences[:2]:
            if _is_verbed_sentence(sent) and len(sent) >= 8 and sent not in events:
                events.append(sent)
                if len(events) >= 5:
                    break
        if len(events) >= 5:
            break

    # 至少返回 1 个
    if not events and content:
        events.append(content[:100] + "...")

    return events[:5]


async def extract_key_events(content: str) -> List[str]:
    """
    从章节内容中提取 3-5 个关键事件。
    优先使用 LLM，失败时回退到启发式提取。
    """
    if not content or len(content) < 100:
        return []

    # 截取前 2000 字用于提取（足够识别关键事件）
    preview = content[:2000]

    prompt = f"""从以下小说章节内容中提取 3-5 个关键事件。只提取推动情节发展的事件，不要提取纯描写或对话。

章节内容（前2000字）：
{preview}

请输出 JSON 数组格式，例如：
["事件1：主角在酒馆遇见神秘陌生人", "事件2：陌生人透露关键情报", "事件3：主角决定前往目的地"]

注意：每个事件一句话概括，不超过30个字。只输出 JSON 数组，不要其他内容。"""

    client = get_default_llm_client()

    try:
        result = await client.generate(
            [LLMMessage(role="user", content=prompt)],
            system_prompt="你是专业的小说编辑，擅长从章节内容中提炼关键事件。请输出纯 JSON 数组格式。",
            temperature=0.3,
            max_tokens=500,
        )
        content_str = result.content.strip() if hasattr(result, "content") else str(result)

        # 尝试解析 JSON
        content_str = re.sub(r'^```(?:json)?\s*', '', content_str)
        content_str = re.sub(r'\s*```$', '', content_str)
        data = json.loads(content_str)
        if isinstance(data, list) and len(data) > 0:
            return data[:5]
    except Exception as e:
        print(f"[EventExtractor] LLM 关键事件提取失败: {e}")

    # 回退到启发式
    return extract_key_events_fallback(content)


def extract_character_changes_fallback(
    content: str,
    known_chars: List[str],
) -> Dict[str, Dict]:
    """
    无 LLM 时的角色变化提取。
    策略：在内容中搜索已知角色名，提取附近的句子。
    """
    changes: Dict[str, Dict] = {}
    char_sentences: Dict[str, List[str]] = {name: [] for name in known_chars}

    # 按段落分析
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]

    for para in paragraphs[:20]:
        for char_name in known_chars:
            if char_name in para:
                char_sentences[char_name].append(para[:100])

    # 提取位置变化（出现地点关键词）
    location_keywords = ["走进", "来到", "到了", "来到", "进入", "离开", "到达", "在"]
    location_pattern = r"[一-鿿]{2,6}(?:室|馆|厅|房|院|楼|场|店|城|镇|村|谷|林|园|殿|塔|堡|山|海|河|湖|岛|街|巷|门)"

    for char_name, sentences in char_sentences.items():
        char_changes: Dict[str, Any] = {"appearance_sentences": []}
        for sent in sentences[:5]:
            char_changes["appearance_sentences"].append(sent)
            # 尝试提取地点
            locations = re.findall(location_pattern, sent)
            if locations:
                char_changes["locations"] = list(set(locations))[:3]
            # 尝试提取情绪
            emotion_words = ["愤怒", "悲伤", "喜悦", "恐惧", "焦虑", "平静", "紧张", "害怕", "高兴"]
            found_emotions = [w for w in emotion_words if w in sent]
            if found_emotions:
                char_changes["emotions"] = found_emotions[:2]
        if char_changes["appearance_sentences"]:
            changes[char_name] = char_changes

    return changes


async def extract_character_changes(
    content: str,
    known_chars: List[str],
) -> Dict[str, Dict]:
    """
    从章节内容中提取角色状态变化。
    优先使用 LLM，失败时回退到启发式提取。
    """
    if not known_chars or not content:
        return {}

    preview = content[:2000]
    char_list = "、".join(known_chars)

    prompt = f"""从以下章节内容中提取已知角色的状态变化。

已知角色：{char_list}

章节内容（前2000字）：
{preview}

请输出 JSON：
{{
  "角色名1": {{
    "locations": ["到达地点1"],
    "emotions": ["当前情绪"],
    "items": ["获得/失去的物品"],
    "key_action": "本章主要动作"
  }}
}}

只输出 JSON 对象，不要其他内容。"""

    client = get_default_llm_client()

    try:
        result = await client.generate(
            [LLMMessage(role="user", content=prompt)],
            system_prompt="你是专业的小说编辑，擅长分析角色状态变化。请输出纯 JSON 格式。",
            temperature=0.3,
            max_tokens=800,
        )
        content_str = result.content.strip() if hasattr(result, "content") else str(result)
        content_str = re.sub(r'^```(?:json)?\s*', '', content_str)
        content_str = re.sub(r'\s*```$', '', content_str)
        data = json.loads(content_str)
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"[EventExtractor] LLM 角色变化提取失败: {e}")

    return extract_character_changes_fallback(content, known_chars)


def extract_new_foreshadowings_fallback(
    content: str,
    existing: List[Dict],
) -> Dict[str, List[str]]:
    """
    无 LLM 时的伏笔检测。
    策略：查找暗示性表达（也许、可能、隐约、似乎、暗藏等）。
    """
    hint_words = ["也许", "可能", "隐约", "似乎", "暗藏", "埋下", "暗示", "预示着",
                   "没想到", "不可能", "绝不可能", "秘密", "隐藏", "真相", "未知"]
    potential_foreshadowing: List[str] = []

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    for para in paragraphs[:15]:
        for hw in hint_words:
            if hw in para and len(para) > 20:
                if para not in potential_foreshadowing:
                    potential_foreshadowing.append(para[:120])
                break

    return {"new": potential_foreshadowing[:5], "resolved": []}


async def extract_new_foreshadowings(
    content: str,
    existing: List[Dict],
) -> Dict[str, List[str]]:
    """
    检测新伏笔埋设和旧伏笔回收。
    优先使用 LLM，失败时回退到启发式检测。
    """
    if not content:
        return {"new": [], "resolved": []}

    preview = content[:2000]

    # 构建已存在伏笔列表供 LLM 参考
    existing_str = ""
    if existing:
        lines = []
        for fw in existing[:10]:
            desc = fw.get("description", fw.get("text", str(fw)))[:50]
            status = fw.get("status", "planted")
            chapter = fw.get("chapter_planted", "?")
            if status != "resolved":
                lines.append(f"- 第{chapter}章: {desc}")
        if lines:
            existing_str = f"\n当前未回收伏笔（请检查是否已回收）：\n{''.join(lines)}\n"

    prompt = f"""分析以下章节内容，识别新伏笔埋设和旧伏笔回收。{existing_str}
章节内容（前2000字）：
{preview}

请输出 JSON：
{{
  "new_foreshadowing": ["新埋设的伏笔1", "新埋设的伏笔2"],
  "resolved_foreshadowing": ["已回收的伏笔描述"]
}}

只输出 JSON 数组，不要其他内容。"""

    client = get_default_llm_client()

    try:
        result = await client.generate(
            [LLMMessage(role="user", content=prompt)],
            system_prompt="你是专业的小说编辑，擅长分析伏笔。请输出纯 JSON 格式。",
            temperature=0.3,
            max_tokens=600,
        )
        content_str = result.content.strip() if hasattr(result, "content") else str(result)
        content_str = re.sub(r'^```(?:json)?\s*', '', content_str)
        content_str = re.sub(r'\s*```$', '', content_str)
        data = json.loads(content_str)
        if isinstance(data, dict):
            return {
                "new": data.get("new_foreshadowing", []),
                "resolved": data.get("resolved_foreshadowing", []),
            }
    except Exception as e:
        print(f"[EventExtractor] LLM 伏笔检测失败: {e}")

    return extract_new_foreshadowings_fallback(content, existing)


def batch_extract(events: List[Tuple[str, List[str]]]) -> Dict[str, List[str]]:
    """
    批量提取关键事件（用于编排器一次性传入多个章节）。

    Args:
        events: [(章节内容, 章节标题), ...]

    Returns:
        {章节标题: [关键事件列表], ...}
    """
    results = {}
    for content, title in events:
        results[title] = extract_key_events_fallback(content)
    return results
