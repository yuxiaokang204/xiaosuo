"""
故事架构师Agent - 合并原OutlineAgent + PlotAgent
职责：大纲设计 + 爽点地图 + 情绪曲线 + 因果链验证
"""
from typing import Dict
from .base import BaseAgent
from .prompts import STORY_ARCHITECT_SYSTEM_PROMPT, build_story_architect_user_prompt


class StoryArchitectAgent(BaseAgent):
    """故事架构师 - 设计完整章节架构、爽点地图、情绪曲线"""

    AGENT_ID = "story_architect"
    AGENT_NAME = "故事架构师"
    CAPABILITIES = ["outline", "planning", "plot", "structure"]
    EXPECTS_JSON = True

    # 章节标题词库（用于 mock fallback）
    _TITLE_POOL = [
        "风云际会", "暗流涌动", "绝处逢生", "峰回路转", "步步惊心",
        "龙争虎斗", "拨云见日", "尘埃落定", "初露锋芒", "惊心动魄",
        "血染长空", "破茧成蝶", "四面楚歌", "一鸣惊人", "柳暗花明",
        "玉石俱焚", "新的征程", "迷雾重重", "真相大白", "背水一战",
    ]

    async def execute(self, context: Dict) -> Dict[str, object]:
        title = str(context.get("title", ""))
        theme = str(context.get("theme", ""))
        tone = str(context.get("tone", "史诗"))
        chapter_count = int(context.get("chapter_count", 10))
        platform = str(context.get("platform", "番茄"))
        world_info = str(context.get("world_info", ""))
        characters = str(context.get("characters", ""))
        start_chapter = int(context.get("start_chapter", 0))
        existing_outline = str(context.get("existing_outline", ""))
        story_direction = str(context.get("story_direction", ""))
        title_analysis = context.get("title_analysis") or {}

        user_prompt = build_story_architect_user_prompt(
            title=title,
            theme=theme,
            tone=tone,
            chapter_count=chapter_count,
            platform=platform,
            world_info=world_info,
            characters=characters,
            start_chapter=start_chapter,
            existing_outline=existing_outline,
            story_direction=story_direction,
            title_analysis=title_analysis if title_analysis else None,
        )
        # 大纲生成需要大量token（每章约400-600字摘要+元数据）
        max_tokens = max(4000, chapter_count * 800)
        result = await self._call_llm(STORY_ARCHITECT_SYSTEM_PROMPT, user_prompt, expects_json=True, max_tokens=max_tokens)

        # 规范输出结构
        data = result.get("data") or {"chapters": []}
        chapters = data.get("chapters", [])

        # 确保每章标题都包含"第X章"前缀
        for i, ch in enumerate(chapters):
            if isinstance(ch, dict) and "第" not in str(ch.get("title", "")):
                ch["title"] = f"第{i+1}章 {ch.get('title', '')}"

        return {
            "success": True,
            "theme": theme,
            "tone": tone,
            "chapter_count": chapter_count,
            "platform": platform,
            "chapters": chapters,
            "narrative_arc": data.get("narrative_arc", {}),
            "tension_curve": data.get("tension_curve", {}),
            "causality_chain": data.get("causality_chain", []),
            "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"),
            "raw": result.get("raw"),
        }

    def _mock_fallback(self, user_prompt: str) -> Dict:
        """生成完整的 mock 大纲"""
        import re
        # 从 prompt 中提取章节数
        match = re.search(r'章节数[：:]?\s*(\d+)', user_prompt)
        chapter_count = int(match.group(1)) if match else 10

        chapters = []
        for i in range(chapter_count):
            title_part = self._TITLE_POOL[i % len(self._TITLE_POOL)]
            if i >= len(self._TITLE_POOL):
                title_part = f"第{i+1}幕"
            chapters.append({
                "title": f"第{i+1}章 {title_part}",
                "summary": f"主角在异世中面临新的挑战，情节逐步推进，展现第{i+1}章的核心冲突与转折。",
                "key_events": [f"事件{i+1}A", f"事件{i+1}B"],
                "opening_state": "主角起始状态",
                "trigger_event": "触发事件",
                "core_conflict": "核心冲突",
                "turning_point": "转折点",
                "closing_state": "收束状态",
                "ending_hook": "结尾期待点",
                "excitement_points": [f"爽点{i+1}A（位置：第3段）", f"爽点{i+1}B（位置：第8段）"],
            })
        return {
            "chapters": chapters,
            "narrative_arc": {"act1": "第1-3章（黄金三章）", "act2": "第4-7章", "act3": "第8-10章"},
            "tension_curve": {"overall": "张力逐步升级", "peaks": ["高潮点1（第3章）", "高潮点2（第7章）"]},
            "causality_chain": ["事件A导致事件B", "事件B引发事件C"],
        }