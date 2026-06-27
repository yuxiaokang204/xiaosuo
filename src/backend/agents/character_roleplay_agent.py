"""
角色代入Agent v6.0 — 保证人物行为一致性的核心组件

核心能力：
  1. 为单个角色生成"角色代入卡"（基于角色设定+经历记忆）
  2. 支持多线程并行代入所有出场角色
  3. 章节生成后提取角色经历记忆，更新记忆链

设计理念：
  - 角色不是被描述的对象，而是被代入的身份
  - 角色行为基于"原始性格 + 经历记忆塑造的新认知"综合决策
  - 角色不能"失忆"——必须基于过往经历行动
  - 角色不能"全知"——只能基于自己应该知道的信息行动
"""
import json
import logging
import asyncio
from typing import Any, Dict, List, Optional

from .prompts import (
    CHARACTER_ROLEPLAY_SYSTEM_PROMPT,
    CHARACTER_MEMORY_EXTRACTION_SYSTEM_PROMPT,
    build_roleplay_user_prompt,
    build_memory_extraction_user_prompt,
)

logger = logging.getLogger(__name__)


class CharacterRoleplayAgent:
    """角色代入Agent — 为单个角色生成代入卡，保证行为一致性"""

    async def generate_roleplay_card(
        self,
        character: Dict,
        world_info: str,
        story_direction: str,
        chapter_outline: str,
        chapter_idx: int,
        character_memory_chain: str,
        scene_type: str = "narrative",
        other_characters: str = "",
    ) -> Dict[str, Any]:
        """为单个角色生成角色代入卡

        Args:
            character: 完整角色档案（含psychological_profile/behavior_tags/speech_fingerprint等）
            world_info: 世界观信息
            story_direction: 故事走向
            chapter_outline: 本章大纲
            chapter_idx: 章节序号
            character_memory_chain: 角色经历记忆链文本
            scene_type: 场景类型（narrative/perspective/dialogue）
            other_characters: 同场景其他角色

        Returns:
            角色代入卡字典，包含inner_monologue/behavior_tendency/dialogue_style等
        """
        from ..llm.client import LLMMessage, get_default_llm_client

        name = character.get("name", "未知角色")
        user_prompt = build_roleplay_user_prompt(
            character=character,
            world_info=world_info,
            story_direction=story_direction,
            chapter_outline=chapter_outline,
            chapter_idx=chapter_idx,
            character_memory_chain=character_memory_chain,
            scene_type=scene_type,
            other_characters=other_characters,
        )

        try:
            client = get_default_llm_client()
            result = await client.generate(
                [LLMMessage(role="user", content=user_prompt)],
                temperature=0.8,
                max_tokens=800,
                system_prompt=CHARACTER_ROLEPLAY_SYSTEM_PROMPT,
            )
            output_text = (result.content or "").strip()
            if not output_text:
                raise ValueError("LLM 返回空内容")

            # 解析JSON
            card = self._safe_parse_json(output_text)
            if card is None:
                # JSON解析失败，使用文本作为代入卡
                logger.warning(f"[Roleplay Agent] {name} JSON解析失败，使用文本格式")
                card = {
                    "character_name": name,
                    "inner_monologue": output_text[:200],
                    "behavior_tendency": "按角色设定行动",
                    "dialogue_style": "按语言指纹说话",
                    "memory_influence": "无特殊记忆影响",
                    "decision_preview": "按决策模式行动",
                    "emotional_state": "平静",
                    "consistency_check": "已校验",
                }

            card["character_name"] = name
            logger.info(f"[Roleplay Agent] 角色「{name}」代入卡生成完成")
            return card

        except Exception as e:
            logger.warning(f"[Roleplay Agent] 角色「{name}」代入卡生成失败: {e}")
            return self._fallback_card(character, scene_type)

    async def generate_roleplay_cards_parallel(
        self,
        characters: List[Dict],
        world_info: str,
        story_direction: str,
        chapter_outline: str,
        chapter_idx: int,
        memory_chain_getter: callable,
        scene_type: str = "narrative",
    ) -> List[Dict[str, Any]]:
        """多线程并行代入所有出场角色

        Args:
            characters: 出场角色列表
            world_info: 世界观信息
            story_direction: 故事走向
            chapter_outline: 本章大纲
            chapter_idx: 章节序号
            memory_chain_getter: 回调函数，(name, chapter_idx) -> 记忆链文本
            scene_type: 场景类型

        Returns:
            角色代入卡列表
        """
        if not characters:
            return []

        # 构建其他角色名称列表
        all_names = [c.get("name", "") for c in characters]

        async def _roleplay_single(char: Dict) -> Dict[str, Any]:
            name = char.get("name", "未知角色")
            other_names = [n for n in all_names if n != name]
            other_chars_str = "、".join(other_names) if other_names else ""

            # 获取该角色的经历记忆链
            memory_chain = memory_chain_getter(name, chapter_idx) if memory_chain_getter else ""

            return await self.generate_roleplay_card(
                character=char,
                world_info=world_info,
                story_direction=story_direction,
                chapter_outline=chapter_outline,
                chapter_idx=chapter_idx,
                character_memory_chain=memory_chain,
                scene_type=scene_type,
                other_characters=other_chars_str,
            )

        # 并行代入所有角色
        tasks = [_roleplay_single(c) for c in characters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_cards = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                name = characters[i].get("name", "未知角色") if i < len(characters) else "未知角色"
                logger.warning(f"[Roleplay Agent] 角色「{name}」并行代入失败: {result}")
                valid_cards.append(self._fallback_card(characters[i], scene_type))
            else:
                valid_cards.append(result)

        logger.info(f"[Roleplay Agent] 并行代入完成：{len(valid_cards)}/{len(characters)}个角色")
        return valid_cards

    async def extract_character_memory(
        self,
        character: Dict,
        chapter_content: str,
        chapter_idx: int,
    ) -> Dict[str, Any]:
        """从章节正文中提取角色经历记忆

        章节生成后调用，为角色生成经历记忆条目，追加到记忆链。

        Args:
            character: 角色档案
            chapter_content: 本章正文内容
            chapter_idx: 章节序号

        Returns:
            经历记忆条目字典，包含experienced_events/emotional_trajectory等
        """
        from ..llm.client import LLMMessage, get_default_llm_client

        name = character.get("name", "未知角色")
        user_prompt = build_memory_extraction_user_prompt(
            character=character,
            chapter_content=chapter_content,
            chapter_idx=chapter_idx,
        )

        try:
            client = get_default_llm_client()
            result = await client.generate(
                [LLMMessage(role="user", content=user_prompt)],
                temperature=0.6,
                max_tokens=600,
                system_prompt=CHARACTER_MEMORY_EXTRACTION_SYSTEM_PROMPT,
            )
            output_text = (result.content or "").strip()
            if not output_text:
                raise ValueError("LLM 返回空内容")

            memory = self._safe_parse_json(output_text)
            if memory is None:
                logger.warning(f"[Roleplay Agent] {name} 经历记忆提取JSON解析失败")
                memory = {
                    "experienced_events": output_text[:200],
                    "emotional_trajectory": "平静",
                    "cognition_updates": [],
                    "personality_shifts": "无显著变化",
                    "decisions_made": [],
                    "information_gained": [],
                    "relationships_change": {},
                }

            logger.info(f"[Roleplay Agent] 角色「{name}」第{chapter_idx}章经历记忆提取完成")
            return memory

        except Exception as e:
            logger.warning(f"[Roleplay Agent] 角色「{name}」经历记忆提取失败: {e}")
            return {
                "experienced_events": f"第{chapter_idx}章经历（提取失败，使用默认）",
                "emotional_trajectory": "平静",
                "cognition_updates": [],
                "personality_shifts": "无显著变化",
                "decisions_made": [],
                "information_gained": [],
                "relationships_change": {},
            }

    async def extract_memories_parallel(
        self,
        characters: List[Dict],
        chapter_content: str,
        chapter_idx: int,
    ) -> Dict[str, Dict[str, Any]]:
        """多线程并行提取所有出场角色的经历记忆

        Args:
            characters: 出场角色列表
            chapter_content: 本章正文内容
            chapter_idx: 章节序号

        Returns:
            {角色名: 经历记忆条目}
        """
        if not characters:
            return {}

        tasks = [self.extract_character_memory(c, chapter_content, chapter_idx) for c in characters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        memories = {}
        for i, result in enumerate(results):
            name = characters[i].get("name", f"角色{i}") if i < len(characters) else f"角色{i}"
            if isinstance(result, Exception):
                logger.warning(f"[Roleplay Agent] 角色「{name}」经历记忆并行提取失败: {result}")
            else:
                memories[name] = result

        logger.info(f"[Roleplay Agent] 并行经历记忆提取完成：{len(memories)}/{len(characters)}个角色")
        return memories

    def format_roleplay_cards(self, cards: List[Dict[str, Any]]) -> str:
        """格式化角色代入卡列表为注入DraftAgent的文本"""
        if not cards:
            return "（无角色代入卡）"

        lines = ["【角色代入卡 — 指导角色言行，保证行为一致性】"]
        for card in cards:
            name = card.get("character_name", "未知角色")
            lines.append(f"\n◆ {name}的代入卡：")
            lines.append(f"  内心独白：{card.get('inner_monologue', '无')}")
            lines.append(f"  行为倾向：{card.get('behavior_tendency', '按设定行动')}")
            lines.append(f"  对话风格：{card.get('dialogue_style', '按语言指纹说话')}")
            lines.append(f"  记忆影响：{card.get('memory_influence', '无特殊影响')}")
            lines.append(f"  关键决策：{card.get('decision_preview', '按决策模式行动')}")
            lines.append(f"  情绪状态：{card.get('emotional_state', '平静')}")
            lines.append(f"  一致性校验：{card.get('consistency_check', '已校验')}")

        lines.append("\n⚠️ 写作时必须严格遵循每个角色的代入卡，保证角色行为与其性格、经历、认知一致。")
        return "\n".join(lines)

    def detect_scene_type(self, outline: str, chapter_idx: int) -> str:
        """识别场景类型，决定代入策略

        - perspective: 角色视角章节（前3章后的特定转折章节）
        - dialogue: 对话密集场景（大纲含对话/谈判/冲突/质问等关键词）
        - narrative: 叙事主导（默认）
        """
        if not outline:
            return "narrative"

        outline_lower = outline.lower()

        # 对话密集场景关键词
        dialogue_keywords = ["对话", "谈判", "冲突", "质问", "争论", "辩论", "对峙", "交谈", "质询", "审问"]
        if any(kw in outline_lower for kw in dialogue_keywords):
            return "dialogue"

        # 角色视角章节：第4章后的转折章节（简化判断）
        if chapter_idx > 3 and any(kw in outline_lower for kw in ["转折", "回忆", "内心", "独白", "反思"]):
            return "perspective"

        return "narrative"

    def _fallback_card(self, character: Dict, scene_type: str) -> Dict[str, Any]:
        """生成兜底代入卡（LLM调用失败时使用）"""
        name = character.get("name", "未知角色")
        personality = character.get("personality", "")
        return {
            "character_name": name,
            "inner_monologue": f"我是{name}，{personality[:50]}，按我的性格行动。",
            "behavior_tendency": "按角色性格设定行动",
            "dialogue_style": "按角色语言指纹说话",
            "memory_influence": "基于过往经历决策",
            "decision_preview": "按角色决策模式行动",
            "emotional_state": "平静",
            "consistency_check": "兜底代入卡，需关注一致性",
        }

    def _safe_parse_json(self, text: str) -> Optional[Dict]:
        """健壮的JSON解析"""
        if not text:
            return None
        import re
        cleaned = text.strip()

        # 1. 直接解析
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 2. 去掉```json代码块
        code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', cleaned, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1).strip())
            except Exception:
                pass

        # 3. 截取第一个{到最后一个}
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start:end + 1]
            candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
            try:
                return json.loads(candidate)
            except Exception:
                pass

        return None
