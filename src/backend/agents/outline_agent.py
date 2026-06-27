"""
大纲生成Agent v2.0 — 映射到故事架构师Skill

v2.0 改进：
- 继承新的 BaseAgent，使用 LLMGateway + Memory + EventBus
- 统一 execute() 接口
- 通过 EventBus 发布执行事件
- 保留所有原有功能和 mock fallback
"""
import re
from typing import Any, Dict

from .base import BaseAgent
from .prompts import STORY_ARCHITECT_SYSTEM_PROMPT, build_story_architect_user_prompt


class OutlineAgent(BaseAgent):
    """大纲生成Agent - 根据主题、风格、章节数生成分章大纲（映射到故事架构师）"""

    AGENT_ID = "outline"
    AGENT_NAME = "故事架构师"
    CAPABILITIES = ["outline", "planning"]
    EXPECTS_JSON = True
    DEFAULT_TEMPERATURE = 0.7

    # 章节标题词库（用于 mock fallback）
    _TITLE_POOL = [
        "初入江湖", "英雄初现", "风云际会", "暗流涌动", "生死考验",
        "绝处逢生", "峰回路转", "步步惊心", "龙争虎斗", "拨云见日",
        "血染长空", "破茧成蝶", "四面楚歌", "一鸣惊人", "柳暗花明",
        "玉石俱焚", "尘埃落定", "新的征程", "迷雾重重", "真相大白",
    ]

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成章节大纲

        Args:
            context: 包含 theme, tone, chapter_count, platform, world_info,
                     characters, start_chapter, existing_outline 等字段

        Returns:
            包含 success, chapters, narrative_arc, tension_curve, causality_chain 的结果
        """
        # 发布执行开始事件
        execution_id = await self._publish_execute_start(context)

        try:
            # 提取上下文参数
            theme = str(context.get("theme", ""))
            tone = str(context.get("tone", "史诗"))
            chapter_count = int(context.get("chapter_count", 10))
            platform = str(context.get("platform", "番茄"))
            world_info = str(context.get("world_info", ""))
            characters = str(context.get("characters", ""))
            start_chapter = int(context.get("start_chapter", 0))
            existing_outline = str(context.get("existing_outline", ""))
            depth_level = int(context.get("depth_level", 1))

            # 构建用户提示词
            user_prompt = build_story_architect_user_prompt(
                theme=theme,
                tone=tone,
                chapter_count=chapter_count,
                platform=platform,
                world_info=world_info,
                characters=characters,
                start_chapter=start_chapter,
                existing_outline=existing_outline,
                depth_level=depth_level,
            )

            # 调用LLM
            result = await self._call_llm(
                STORY_ARCHITECT_SYSTEM_PROMPT,
                user_prompt,
                expects_json=True,
                max_tokens=8000,
            )

            # 规范输出结构
            data = result.get("data") or {"chapters": []}
            chapters = data.get("chapters", [])

            # 确保每章标题都包含"第X章"前缀
            for i, ch in enumerate(chapters):
                if isinstance(ch, dict) and "第" not in str(ch.get("title", "")):
                    ch["title"] = f"第{i+1}章 {ch.get('title', '')}"

            # 写入长期记忆：大纲结构
            if chapters:
                self.memory.store_world_settings([
                    {
                        "id": "outline_structure",
                        "name": "故事大纲",
                        "description": f"{chapter_count}章大纲结构",
                        "rules": [ch.get("title", "") for ch in chapters[:10]],
                    }
                ])

            # 发布执行完成事件
            await self._publish_execute_done(execution_id, result)

            return {
                "success": True,
                "fallback": result.get("fallback", False),
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

        except Exception as e:
            import traceback
            print(f"[Agent {self.AGENT_ID}] ❌ 执行异常: {e}\n{traceback.format_exc()}")
            await self._publish_execute_done(execution_id, {
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "error": str(e),
                "chapters": [],
                "theme": theme if 'theme' in locals() else "",
                "chapter_count": chapter_count if 'chapter_count' in locals() else 0,
            }

    def _mock_fallback(self, user_prompt: str) -> Dict:
        """生成完整的 mock 大纲（不再硬编码5章）"""
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
            })
        return {"chapters": chapters}
