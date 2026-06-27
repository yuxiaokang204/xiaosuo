"""
开篇钩子师Agent - 新增，专攻黄金三章+首章300字
职责：设计黄金三章的开篇方案，确保首章300字抛钩子
"""
from typing import Dict
from .base import BaseAgent
from .prompts import OPENING_HOOK_SYSTEM_PROMPT, build_opening_hook_user_prompt


class OpeningHookAgent(BaseAgent):
    """开篇钩子师 - 专精黄金三章和首章300字定生死法则"""

    AGENT_ID = "opening_hook"
    AGENT_NAME = "开篇钩子师"
    CAPABILITIES = ["opening", "hook", "golden_three_chapters"]
    EXPECTS_JSON = True

    async def execute(self, context: Dict) -> Dict[str, object]:
        theme = str(context.get("theme", ""))
        platform = str(context.get("platform", "番茄"))
        world_info = str(context.get("world_info", ""))
        character_info = str(context.get("character_info", ""))
        outline_info = str(context.get("outline_info", ""))

        user_prompt = build_opening_hook_user_prompt(
            theme=theme,
            platform=platform,
            world_info=world_info,
            character_info=character_info,
            outline_info=outline_info,
        )
        result = await self._call_llm(OPENING_HOOK_SYSTEM_PROMPT, user_prompt, expects_json=True)

        data = result.get("data") or {}

        return {
            "success": True,
            "theme": theme,
            "platform": platform,
            "chapter_1": data.get("chapter_1", {}),
            "chapter_2": data.get("chapter_2", {}),
            "chapter_3": data.get("chapter_3", {}),
            "platform_notes": data.get("platform_notes", ""),
            "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"),
            "raw": result.get("raw"),
        }

    def _mock_fallback(self, user_prompt: str) -> Dict:
        """生成 mock 黄金三章开篇方案"""
        return {
            "chapter_1": {
                "title": "第一章 风云际会",
                "opening_300_words_plan": "冲突设计：主角在危机中醒来，周围是陌生的环境，必须立即做出选择",
                "first_conflict": "主角发现自己被困在未知空间，必须在300秒内找到出口",
                "protagonist_first_impression": "冷静、果断、有危机意识",
                "ending_hook": "主角发现了一个关键线索，指向更大的谜团",
            },
            "chapter_2": {
                "title": "第二章 暗流涌动",
                "twist_design": "主角发现线索指向一个意想不到的人",
                "expectation_build": "读者期待主角如何应对这个发现",
                "key_character_intro": "关键配角出现，提供关键信息",
                "ending_hook": "主角面临一个艰难的选择",
            },
            "chapter_3": {
                "title": "第三章 绝处逢生",
                "small_win": "主角解决了第一个小困境",
                "satisfaction_point": "读者感受到主角的成长和能力",
                "bigger_suspense": "更大的谜团浮出水面",
                "ending_hook": "主角决定踏上更大的征程",
            },
            "platform_notes": "番茄平台：快节奏，300字内必须有冲突",
        }