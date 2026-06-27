"""
8-Agent 协同写作管道 — 每个Agent都是内容创作者，不是检查员

8个Agent的职责：
  1. Outline Agent    → 规划本章大纲结构和情节要点
  2. World Agent      → 补充本章需要的世界观细节（地点、规则、势力）
  3. Character Agent  → 设计本章角色对白、动作、心理变化
  4. Plot Agent       → 设计情节转折、冲突、线索埋设
  5. Style Agent      → 提供风格模板和语言润色点
  6. Draft Agent      → 注入所有Agent的建议，流式生成正文
  7. Edit Agent       → 润色修改，使语言更精炼
  8. Review Agent     → 每5章检查整体一致性（世界观/角色/情节）

流程：
  - 普通章节（不是5的倍数）：步骤1-7协同写作，流式输出
  - 每5章（第5、10、15...章）：完整8步 + 审查问题修正
"""
import asyncio
import json
import logging
import re
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

from ..agents.prompts import (
    DRAFT_SYSTEM_PROMPT,
    sanitize_chapter_content,
    build_story_architect_system_prompt,
    build_world_system_prompt,
    build_character_system_prompt,
    build_opening_hook_system_prompt,
    build_draft_system_prompt,
    build_style_editor_system_prompt,
)
from ..agents.character_roleplay_agent import CharacterRoleplayAgent


def sanitize_content(content: str) -> str:
    """清理LLM输出中的乱码英文和异常字符"""
    # 移除纯英文单词（保留中文、中文标点、数字、常见英文标点）
    # 但要保留已经在中文语境中合理的英文缩略词

    # 1. 移除独立的英文单词（3个及以上连续ASCII字母）
    content = re.sub(r'\b[a-zA-Z]{3,}\b', '', content)

    # 2. 移除孤立的ASCII标点/特殊字符（如 `#`, `@`, `$`, `%`, `^`, `&`, `*`, `|`, `~`）
    content = re.sub(r'(?<![a-zA-Z0-9])[#@$%^&*|~`]+(?![a-zA-Z0-9])', '', content)

    # 3. 移除JSON残留（花括号、方括号、引号包围的键值对）
    content = re.sub(r'\{[^}]*\}', '', content)
    content = re.sub(r'\[[^\]]*\]', '', content)
    content = re.sub(r'"[a-zA-Z_]+"\s*:', '', content)
    content = re.sub(r'"[a-zA-Z_]+"', '', content)

    # 4. 清理多余空白（连续多个空格/换行）
    content = re.sub(r' {3,}', '  ', content)
    content = re.sub(r'\n{4,}', '\n\n\n', content)

    # 5. 移除行首的英语标签和残留（如 "status:", "type:", "role:" 等）
    content = re.sub(r'^[a-zA-Z_\s]+:\s*$', '', content, flags=re.MULTILINE)

    return content.strip()


@dataclass
class AgentContribution:
    """单个Agent的创作贡献"""
    agent_name: str = ""
    content: str = ""  # 产出的建议/提示/段落
    score: float = 0.0  # 可选评分
    details: Dict = field(default_factory=dict)


@dataclass
class ChapterPipelineResult:
    """一个章节完成管道的最终结果"""
    chapter_index: int = 0
    title: str = ""
    content: str = ""
    word_count: int = 0
    is_review_chapter: bool = False  # 是否是5的倍数（审查章节）
    passed_review: bool = True
    contributions: List[AgentContribution] = field(default_factory=list)
    overall_score: float = 0.0
    revision_rounds: int = 0


class ChapterPipeline:
    """
    6-Skill 协同写作管道 v4.0 — LOOP 循环架构
    - v3.0: 合并8个Agent为6个Skill
    - v4.0: 支持depth_level / loop_metadata 深度感知调用

    深度说明:
        depth 0 (SKELETON): 粗略产出，快速建立骨架
        depth 1 (DETAIL):   完整细化，详细产出
        depth 2 (POLISH):   精修润色，质量审查
        depth 3+ (REFINE):  按需继续精修
    """

    REVIEW_EVERY = 5  # 每5章做一次完整审查
    MAX_REVISIONS = 1  # 审查后最多1轮修订

    # v3.0: 6个Skill的展示名称（方案A）
    AGENT_ROLES = [
        ("story_architect", "故事架构师"),  # 合并Outline+Plot
        ("world", "世界观构建师"),          # 保留
        ("character", "角色塑造师"),        # 保留
        ("opening_hook", "开篇钩子师"),     # 新增（前三章使用）
        ("draft", "专业写手"),              # 增强
        ("style_editor", "文风精修师"),     # 合并Style+Edit+Review
    ]

    def __init__(self, agents: Dict[str, Any], emit: Callable, state_tracker=None,
                 global_summary=None, pause_event=None, paused_ref=None,
                 memory_engine=None):
        self.agents = agents
        self.emit = emit
        self.state_tracker = state_tracker
        self.global_summary = global_summary
        self._pause_event = pause_event
        self._paused_ref = paused_ref
        # v5.0: 追踪本次运行中使用的 prompt（供 orchestrator 自动保存）
        self._used_prompts: Dict[str, Dict] = {}
        # v5.1: 记忆协调引擎（可选，优先级高于 state_tracker + global_summary）
        self._memory_engine = memory_engine
        # v6.0 角色代入式创作：角色代入Agent
        self._roleplay_agent = CharacterRoleplayAgent()

    async def _check_pause(self):
        """暂停检查 — yield到事件循环以允许其他协程（如pause/resume API）运行"""
        if self._pause_event:
            await asyncio.sleep(0)  # 确保event loop有机会处理其他任务
            await self._pause_event.wait()

    # ────────────────────────────────────────────────────
    # 8个Agent的创作方法（所有Agent都产出内容建议）
    # ────────────────────────────────────────────────────

    async def _agent_outline(self, chapter_idx: int, title: str, summary: str,
                               context: Dict, loop_metadata: Optional[Dict] = None) -> AgentContribution:
        """Agent 1: 大纲规划师（深度感知）
        depth 0: 粗略骨架(3-5结构要点)
        depth 1: 完整细节大纲(结构+关键事件+线索+转折点)
        depth 2: 审查大纲质量+因果链验证
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        from ..llm.client import LLMMessage, get_default_llm_client

        world_info = context.get("world", "")[:600]
        recent_summaries = context.get("summaries", "")[:600]
        prev_chapter_text = context.get("previous_chapter_text", "")

        # 上一章结尾衔接信息
        prev_ending_info = ""
        if prev_chapter_text and chapter_idx > 1:
            prev_ending_info = f"\n\n【上一章结尾场景（本章开头必须接续）】\n{prev_chapter_text[-300:]}"

        # depth 0: 简化 JSON 结构
        if depth_level <= 0:
            json_template = """{
  "structure": ["结构要点1", "结构要点2", "结构要点3"]
}"""
        elif depth_level >= 2:
            json_template = """{
  "review_summary": "整体评价（50字）",
  "issues": [{"problem": "问题描述", "suggestion": "建议"}],
  "adjusted_structure": ["调整后的结构要点"]
}"""
        else:
            json_template = """{
  "structure": [
    "开场：冲突或悬念（约300字）",
    "发展：情节推进和人物互动（约800字）",
    "高潮：关键冲突（约600字）",
    "收束：解决与新悬念（约300字）"
  ],
  "key_events": ["关键事件1", "关键事件2", "关键事件3"],
  "foreshadowing": ["可埋设的线索1", "可埋设的线索2"],
  "turning_points": ["转折点1", "转折点2"]
}"""

        user_prompt = f"""作为本章大纲规划师，请为以下章节设计详细大纲。

章节序号：第{chapter_idx}章
章节标题：{title}
已有大纲：{summary if summary else "无"}
世界观背景：{world_info if world_info else "按需设定"}
前情摘要：{recent_summaries if recent_summaries else "第一章"}{prev_ending_info}

请输出JSON：
{json_template}"""

        # 深度感知 system_prompt（使用 PromptResolver 两级 fallback）
        from .prompt_resolver import resolve_system_prompt
        system_prompt = await resolve_system_prompt("story_architect", depth_level)
        if not system_prompt:
            system_prompt = build_story_architect_system_prompt(depth_level)
        # 记录实际使用的 prompt（供 orchestrator 自动保存）
        self._used_prompts["story_architect"] = {
            "agent_type": "story_architect",
            "depth_level": depth_level,
            "prompt_type": "system",
            "content": system_prompt,
            "quality_score": 8,  # 初始评分，后续由质量审查更新
        }

        # 深度感知 max_tokens
        if depth_level <= 0:
            max_tokens = 500
        elif depth_level >= 2:
            max_tokens = 1500
        else:
            max_tokens = 1000

        client = get_default_llm_client()
        try:
            result = await client.generate(
                [LLMMessage(role="user", content=user_prompt)],
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=max_tokens,
            )
            content = (result.content or "").strip()
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                data = {"structure": ["开场", "发展", "高潮", "收束"],
                         "key_events": ["事件1", "事件2"],
                         "foreshadowing": ["线索1"],
                         "turning_points": ["转折1"]}

            # 格式化输出作为创作建议
            output_parts = []
            if "structure" in data:
                output_parts.append("【结构规划】\n" + "\n".join("  - " + str(s) for s in data["structure"][:6]))
            if "key_events" in data:
                output_parts.append("【关键事件】\n" + "\n".join("  • " + str(e) for e in data["key_events"][:5]))
            if "foreshadowing" in data:
                output_parts.append("【可埋设线索】\n" + "\n".join("  ◇ " + str(f) for f in data["foreshadowing"][:3]))
            if "turning_points" in data:
                output_parts.append("【转折设计】\n" + "\n".join("  △ " + str(t) for t in data["turning_points"][:3]))

            # 如果有 state_tracker，自动注册大纲规划师建议的线索
            if self.state_tracker and data.get("foreshadowing"):
                for fs_text in data["foreshadowing"][:3]:
                    try:
                        self.state_tracker.plant_foreshadowing(
                            chapter=chapter_idx,
                            description=str(fs_text),
                            f_type="plot",
                            importance=3,
                        )
                    except Exception:
                        pass  # 线索注册失败不影响主流程

            return AgentContribution(
                agent_name="故事架构师",
                content="\n\n".join(output_parts),
                score=8.0,
                details=data,
            )
        except Exception:
            # 简化的fallback：基于章节序号生成简单大纲
            events = [f"主角进入第{chapter_idx}章的新情境", f"遇到意想不到的阻力或发现", f"与敌人或环境的冲突升级", f"在困境中做出关键抉择"]
            fores = [f"暗示第{chapter_idx+2}章的潜在威胁", f"提及第{chapter_idx+1}章会出现的线索"]
            data = {
                "structure": [f"开场：新情境/悬念（约300字）", f"发展：推进主线与人物（约800字）",
                             f"高潮：核心冲突（约600字）", f"收束：解决与新悬念（约300字）"],
                "key_events": events,
                "foreshadowing": fores,
                "turning_points": [f"第{chapter_idx}章中段的意外发现", f"章末的关键性选择"],
            }
            output_parts = [
                "【结构规划】\n" + "\n".join("  - " + str(s) for s in data["structure"]),
                "【关键事件】\n" + "\n".join("  • " + str(e) for e in data["key_events"]),
                "【可埋设线索】\n" + "\n".join("  ◇ " + str(f) for f in data["foreshadowing"]),
                "【转折设计】\n" + "\n".join("  △ " + str(t) for t in data["turning_points"]),
            ]
            return AgentContribution(
                agent_name="大纲规划师",
                content="\n\n".join(output_parts),
                score=7.5,
                details=data,
            )

    async def _agent_world(self, chapter_idx: int, context: Dict,
                            loop_metadata: Optional[Dict] = None) -> AgentContribution:
        """Agent 2: 世界观构建师（深度感知）— v5.2: 调用 LLM + PromptResolver
        depth 0: 仅场景地点提示
        depth 1: 详细世界观细节+规则锚点
        depth 2: 一致性审查
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        world_info = context.get("world", "")[:1500]
        outline = context.get("outline", "")[:500]

        try:
            from .prompt_resolver import resolve_system_prompt
            from ..llm.client import LLMMessage, get_default_llm_client

            system_prompt = await resolve_system_prompt("world", depth_level)
            if not system_prompt:
                system_prompt = build_world_system_prompt(depth_level)

            user_prompt = f"""为第{chapter_idx}章提供世界观场景细节。

【已有世界观设定】
{world_info if world_info else "（暂无详细设定）"}

【本章大纲】
{outline if outline else "（暂无大纲）"}

【深度级别】{depth_level}（0=骨架/1=细节/2=精修）

请根据深度级别输出：
- depth 0: 仅提供场景地点和氛围关键词（2-3条）
- depth 1: 详细场景描述、世界规则锚点、感官细节（4-6条）
- depth 2: 一致性审查清单，检查术语/规则/感官锚点是否正确（3-5条）

请直接输出创作建议，不要输出JSON格式，不要包含元写作术语。"""

            client = get_default_llm_client()
            result = await client.generate(
                [LLMMessage(role="user", content=user_prompt)],
                temperature=0.7,
                max_tokens=600,
                system_prompt=system_prompt,
            )
            output_text = (result.content or "").strip()
            if not output_text:
                raise ValueError("LLM 返回空内容")

            logger.info(f"[World Agent] 第{chapter_idx}章 LLM 生成完成 ({len(output_text)}字)")
            return AgentContribution(
                agent_name="世界观构建师",
                content=output_text,
                score=7.5,
                details={"world_context": world_info[:200], "depth_level": depth_level, "llm": True},
            )
        except Exception as e:
            logger.warning(f"[World Agent] LLM 调用失败，回退硬编码: {e}")
            # 回退：硬编码文本
            details = []
            if world_info and len(world_info) > 50:
                details.append("已知世界观规则已注入")
            if not details:
                locations = ["城镇", "山谷", "森林", "废墟", "要塞", "遗迹", "沙漠", "岛屿"]
                time_settings = ["清晨", "黄昏", "深夜", "正午", "雨夜", "暴风雪"]
                chosen_loc = random.choice(locations)
                chosen_time = random.choice(time_settings)
                details = [
                    f"场景地点：{chosen_loc}",
                    f"时间氛围：{chosen_time}",
                ]
            output_text = "【本章世界观细节】\n" + "\n".join("  · " + d for d in details)
            if depth_level <= 0:
                output_text += "\n\n【SKELETON模式】仅提供基础场景锚点，不需要展开规则细节。"
            elif depth_level >= 2:
                output_text += "\n\n【POLISH模式】请检查以下规则一致性：\n  · 正文术语与世界观词汇场一致\n  · 无规则矛盾\n  · 感官锚点正确使用"
            else:
                output_text += "\n\n【需要注意的规则】\n  · 保持与已有设定一致\n  · 不要引入新的超自然系统"
            return AgentContribution(
                agent_name="世界观构建师",
                content=output_text,
                score=7.5,
                details={"world_context": world_info[:200], "depth_level": depth_level, "llm": False, "fallback": True},
            )

    async def _agent_character(self, chapter_idx: int, title: str, context: Dict,
                                  loop_metadata: Optional[Dict] = None) -> AgentContribution:
        """Agent 3: 角色塑造师（深度感知）— v5.2: 调用 LLM + PromptResolver
        depth 0: 主角基本行为提示
        depth 1: 角色对白/动机/关系的详细建议
        depth 2: 角色行为一致性审查
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        character_info = context.get("characters", "")[:1500]
        outline = context.get("outline", "")[:500]

        try:
            from .prompt_resolver import resolve_system_prompt
            from ..llm.client import LLMMessage, get_default_llm_client

            system_prompt = await resolve_system_prompt("character", depth_level)
            if not system_prompt:
                system_prompt = build_character_system_prompt(depth_level)

            user_prompt = f"""为第{chapter_idx}章「{title}」设计角色行为方案。

【已有角色设定】
{character_info if character_info else "（暂无详细设定）"}

【本章大纲】
{outline if outline else "（暂无大纲）"}

【深度级别】{depth_level}（0=骨架/1=细节/2=精修）

请根据深度级别输出：
- depth 0: 主角本章核心行为（1-2条）
- depth 1: 主角行为+关键对话+角色关系变化（4-6条）
- depth 2: 角色行为一致性审查（3-5条检查项）

请直接输出创作建议，不要输出JSON格式，不要包含元写作术语。"""

            client = get_default_llm_client()
            result = await client.generate(
                [LLMMessage(role="user", content=user_prompt)],
                temperature=0.75,
                max_tokens=600,
                system_prompt=system_prompt,
            )
            output_text = (result.content or "").strip()
            if not output_text:
                raise ValueError("LLM 返回空内容")

            logger.info(f"[Character Agent] 第{chapter_idx}章 LLM 生成完成 ({len(output_text)}字)")
            return AgentContribution(
                agent_name="角色塑造师",
                content=output_text,
                score=7.5,
                details={"depth_level": depth_level, "llm": True},
            )
        except Exception as e:
            logger.warning(f"[Character Agent] LLM 调用失败，回退硬编码: {e}")
            # 回退：硬编码文本
            protagonist_names = re.findall(r"[\u4e00-\u9fff]{2,4}", character_info[:200])
            main_char = protagonist_names[0] if protagonist_names else "主角"
            if depth_level <= 0:
                actions = [f"{main_char}做出一个关键决策", f"{main_char}展现核心性格特征"]
                dialogues, dynamics = [], []
            elif depth_level >= 2:
                actions = [f"检查{main_char}的行为是否与性格设定一致", f"验证{main_char}的决策是否符合心理画像", f"评估{main_char}的成长弧线进度"]
                dialogues = [f"检查{main_char}的语言指纹是否保持一致性", f"验证对话中的行为标签是否使用"]
                dynamics = [f"角色关系变化是否符合预期", f"检查是否有角色行为矛盾"]
            else:
                actions = [f"{main_char}在压力下做出一个出人意料的决定", f"{main_char}与同伴的对话揭示了隐藏的动机", f"{main_char}展现出之前未曾显露的技能或弱点", f"{main_char}的情绪在本章经历明显变化"]
                dialogues = [f"{main_char}：简短有力的台词（3-5句），展现决心或困惑", f"配角：与{main_char}形成观点碰撞"]
                dynamics = [f"本章{main_char}展现性格的新侧面", f"角色关系发生微妙转变"]
            output_parts = [f"【主角本章行为】\n" + "\n".join("  · " + a for a in actions[:3])]
            if dialogues:
                output_parts.append("【关键对话】\n" + "\n".join("  » " + d for d in dialogues[:2]))
            if dynamics:
                output_parts.append("【角色动态】\n" + "\n".join("  ~ " + d for d in dynamics))
            return AgentContribution(
                agent_name="角色塑造师",
                content="\n\n".join(output_parts),
                score=7.5,
                details={"main_character": main_char, "depth_level": depth_level, "llm": False, "fallback": True},
            )

    # ────────────────────────────────────────────────────
    # v6.0 角色代入式创作：多线程并行角色代入（保证行为一致性）
    # ────────────────────────────────────────────────────

    def _get_active_characters_for_chapter(self, chapter_idx: int) -> List[Dict]:
        """获取本章活跃角色（已出场且未退场）

        基于角色生命周期过滤，已退场角色不再代入。
        """
        active = []
        # 从 context 获取角色列表（可能是字符串或列表）
        characters_raw = self._current_context.get("characters_list", []) if hasattr(self, '_current_context') else []
        if not characters_raw:
            # 回退：尝试从 agents 或 state 获取
            return []

        for char in characters_raw:
            if not isinstance(char, dict):
                continue
            first = char.get("first_appear_chapter", 1) or 1
            last = char.get("last_appear_chapter", None)
            status = char.get("character_status", "active")
            # 角色已退场或已死亡，不再代入
            if status in ("exited", "dead"):
                continue
            # 角色尚未出场
            if chapter_idx < first:
                continue
            # 角色已退场（超过最后出场章节）
            if last is not None and chapter_idx > last:
                continue
            active.append(char)
        return active

    async def _agent_character_roleplay_parallel(
        self, chapter_idx: int, title: str, context: Dict, loop_metadata: Optional[Dict] = None
    ) -> Optional[AgentContribution]:
        """v6.0 角色代入：多线程并行代入所有出场角色

        为每个出场角色生成"角色代入卡"，注入DraftAgent，
        保证角色行为基于其设定和经历记忆，避免"失忆"和"全知"。
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)

        # depth 0 (SKELETON) 阶段跳过角色代入，简化流程
        if depth_level <= 0:
            return None

        # 保存当前 context 供 _get_active_characters_for_chapter 使用
        self._current_context = context

        # 获取本章活跃角色
        active_characters = self._get_active_characters_for_chapter(chapter_idx)
        if not active_characters:
            logger.info(f"[Roleplay] 第{chapter_idx}章无活跃角色，跳过代入")
            return None

        # 识别场景类型
        outline = context.get("outline", "") or title
        scene_type = self._roleplay_agent.detect_scene_type(outline, chapter_idx)

        # 获取世界观和故事走向
        world_info = context.get("world", "")
        story_direction = context.get("story_direction", "")
        chapter_outline = context.get("outline", "") or title

        # 记忆链获取回调
        def memory_chain_getter(name: str, ch_idx: int) -> str:
            if self.state_tracker:
                return self.state_tracker.get_character_behavior_context(name, ch_idx)
            return ""

        try:
            # 多线程并行代入所有出场角色
            cards = await self._roleplay_agent.generate_roleplay_cards_parallel(
                characters=active_characters,
                world_info=world_info,
                story_direction=story_direction,
                chapter_outline=chapter_outline,
                chapter_idx=chapter_idx,
                memory_chain_getter=memory_chain_getter,
                scene_type=scene_type,
            )

            # 格式化代入卡
            cards_text = self._roleplay_agent.format_roleplay_cards(cards)

            logger.info(f"[Roleplay] 第{chapter_idx}章角色代入完成：{len(cards)}个角色，场景类型={scene_type}")

            return AgentContribution(
                agent_name="角色代入师",
                content=cards_text,
                score=8.0,
                details={
                    "character_count": len(cards),
                    "scene_type": scene_type,
                    "characters": [c.get("name", "") for c in active_characters],
                },
            )
        except Exception as e:
            logger.warning(f"[Roleplay] 第{chapter_idx}章角色代入失败: {e}")
            return None

    async def _update_character_memories_after_chapter(
        self, chapter_idx: int, content: str, context: Dict
    ):
        """v6.0 章节生成后更新角色经历记忆

        为每个出场角色生成经历记忆条目，追加到StateTracker的记忆链，
        保证角色下次代入时携带完整经历记忆。
        """
        # 保存当前 context
        self._current_context = context

        # 获取本章活跃角色
        active_characters = self._get_active_characters_for_chapter(chapter_idx)
        if not active_characters or not self.state_tracker:
            return

        try:
            # 多线程并行提取所有角色的经历记忆
            memories = await self._roleplay_agent.extract_memories_parallel(
                characters=active_characters,
                chapter_content=content,
                chapter_idx=chapter_idx,
            )

            # 追加到 StateTracker 的角色经历记忆链
            from .state_tracker import CharacterExperienceMemory
            for name, memory_data in memories.items():
                entry = CharacterExperienceMemory(
                    chapter=chapter_idx,
                    experienced_events=memory_data.get("experienced_events", ""),
                    emotional_trajectory=memory_data.get("emotional_trajectory", ""),
                    cognition_updates=memory_data.get("cognition_updates", []),
                    personality_shifts=memory_data.get("personality_shifts", ""),
                    decisions_made=memory_data.get("decisions_made", []),
                    information_gained=memory_data.get("information_gained", []),
                    relationships_change=memory_data.get("relationships_change", {}),
                )
                self.state_tracker.append_character_memory(name, entry)

            logger.info(f"[Roleplay] 第{chapter_idx}章角色经历记忆更新完成：{len(memories)}个角色")
        except Exception as e:
            logger.warning(f"[Roleplay] 第{chapter_idx}章角色经历记忆更新失败: {e}")

    async def _agent_opening_hook(self, chapter_idx: int, title: str, context: Dict,
                                    loop_metadata: Optional[Dict] = None) -> AgentContribution:
        """Skill 4: 开篇钩子师（深度感知）— v5.2: 调用 LLM + PromptResolver
        depth 0: 基础钩子类型提示
        depth 1: 黄金三章详细钩子设计(场景/悬念/反转)
        depth 2: 重审钩子有效性+匹配度检查
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        world_info = context.get("world", "")[:800]
        character_info = context.get("characters", "")[:800]
        outline = context.get("outline", "")[:500]

        try:
            from .prompt_resolver import resolve_system_prompt
            from ..llm.client import LLMMessage, get_default_llm_client

            system_prompt = await resolve_system_prompt("opening_hook", depth_level)
            if not system_prompt:
                system_prompt = build_opening_hook_system_prompt(depth_level)

            chapter_label = {1: "第一章（黄金开头）", 2: "第二章（反转设计）", 3: "第三章（小回报）"}.get(chapter_idx, f"第{chapter_idx}章")
            user_prompt = f"""为{chapter_label}「{title}」设计开篇钩子方案。

【世界观】
{world_info if world_info else "（暂无详细设定）"}

【角色信息】
{character_info if character_info else "（暂无详细设定）"}

【本章大纲】
{outline if outline else "（暂无大纲）"}

【深度级别】{depth_level}（0=骨架/1=细节/2=精修）

请根据深度级别和章节序号输出：
- depth 0: 钩子类型推荐（1-2条）
- depth 1: 详细钩子设计（前300字策略+结尾期待点，3-5条）
- depth 2: 钩子有效性重审（3-4条检查项）

请直接输出创作建议，不要输出JSON格式，不要包含元写作术语。"""

            client = get_default_llm_client()
            result = await client.generate(
                [LLMMessage(role="user", content=user_prompt)],
                temperature=0.8,
                max_tokens=600,
                system_prompt=system_prompt,
            )
            output_text = (result.content or "").strip()
            if not output_text:
                raise ValueError("LLM 返回空内容")

            logger.info(f"[OpeningHook Agent] 第{chapter_idx}章 LLM 生成完成 ({len(output_text)}字)")
            return AgentContribution(
                agent_name="开篇钩子师",
                content=output_text,
                score=8.5,
                details={"chapter": chapter_idx, "depth_level": depth_level, "llm": True},
            )
        except Exception as e:
            logger.warning(f"[OpeningHook Agent] LLM 调用失败，回退硬编码: {e}")
            # 回退：硬编码文本
            if depth_level <= 0:
                hook_design = ["【钩子类型提示】", "  · 推荐类型：冲突/悬念/反差/危机", "  · 前300字：直接入戏，抛出困境", "  · 结尾：留下期待点"]
                score = 7.0
            elif depth_level >= 2:
                hook_design = ["【钩子有效性重审】", "  · 检查第一章前300字是否成功抛出钩子", "  · 评估第二章转折是否出人意料但合理", "  · 验证第三章回报是否给读者满足感", "  · 检查钩子与细化大纲的匹配度"]
                score = 8.0
            elif chapter_idx == 1:
                hook_design = ["【第一章前300字钩子】", "  · 开场即入戏，不要环境描写", "  · 在前300字内抛出冲突/悬念/反差/危机", "  · 主角必须遇到第一个困境", "  · 让读者记住主角的一个核心特征", "", "【第一章结尾期待点】", "  · 新信息出现，指向更大的谜团"]
                score = 8.5
            elif chapter_idx == 2:
                hook_design = ["【第二章反转设计】", "  · 延续第一章困境，给出意想不到的转折", "  · 建立读者期待：主角如何应对", "  · 引入关键配角或势力", "", "【第二章结尾期待点】", "  · 主角面临艰难选择"]
                score = 8.5
            else:
                hook_design = ["【第三章小回报】", "  · 主角解决第一个小困境（不是大困境）", "  · 给读者满足感，证明'这书值得追'", "  · 埋下更大的悬念", "", "【第三章结尾期待点】", "  · 主角决定踏上更大的征程"]
                score = 8.5
            return AgentContribution(
                agent_name="开篇钩子师",
                content="\n".join(hook_design),
                score=score,
                details={"chapter": chapter_idx, "depth_level": depth_level, "llm": False, "fallback": True},
            )

    async def _agent_style_editor_full(self, chapter_idx: int, title: str, content: str,
                                        context: Dict, existing_chapters: str,
                                        loop_metadata: Optional[Dict] = None) -> AgentContribution:
        """Skill 6: 文风精修师完整审查（深度感知）— v5.2: 调用 LLM + PromptResolver
        depth 0: 轻量审查+修复
        depth 1: 完整精修编辑+多维度审查评分
        depth 2: 严格标准+前章一致性检查
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        style_info = context.get("style", "")[:500]
        world_info = context.get("world", "")[:500]

        try:
            from .prompt_resolver import resolve_system_prompt
            from ..llm.client import LLMMessage, get_default_llm_client

            system_prompt = await resolve_system_prompt("style_editor", depth_level)
            if not system_prompt:
                system_prompt = build_style_editor_system_prompt(depth_level)

            content_sample = content[:1500] if len(content) > 1500 else content
            existing_sample = existing_chapters[:800] if existing_chapters else "（无前章）"

            user_prompt = f"""审查第{chapter_idx}章「{title}」的写作质量。

【本章正文（节选）】
{content_sample}

【前章内容（节选）】
{existing_sample}

【风格指南】
{style_info if style_info else "（无特定风格指南）"}

【世界观规则】
{world_info if world_info else "（无特定世界观规则）"}

【深度级别】{depth_level}（0=骨架/1=细节/2=精修）

请根据深度级别输出：
- depth 0: 仅检查AI味表达（如"眼中闪过""心中涌起""只见""突然"等），给出评分+问题列表
- depth 1: 完整精修审查（AI味表达+段落结构+语言流畅度），给出评分+问题列表+改进建议
- depth 2: 严格标准审查（以上全部+前章一致性+世界观一致性），给出评分+问题列表+改进建议

请直接输出审查结果，不要输出JSON格式，不要包含元写作术语。"""

            client = get_default_llm_client()
            result = await client.generate(
                [LLMMessage(role="user", content=user_prompt)],
                temperature=0.5,
                max_tokens=800,
                system_prompt=system_prompt,
            )
            output_text = (result.content or "").strip()
            if not output_text:
                raise ValueError("LLM 返回空内容")

            logger.info(f"[StyleEditor Agent] 第{chapter_idx}章 LLM 审查完成 ({len(output_text)}字)")
            return AgentContribution(
                agent_name="文风精修师",
                content=output_text,
                score=7.0,
                details={
                    "passed": True,
                    "issues": [],
                    "edited_content": content,
                    "depth_level": depth_level,
                    "llm": True,
                },
            )
        except Exception as e:
            logger.warning(f"[StyleEditor Agent] LLM 调用失败，回退硬编码: {e}")
            # 回退：硬编码文本
            edit_issues = []
            if depth_level <= 0:
                ai_patterns = ["眼中闪过", "心中涌起", "只见", "只听", "只觉"]
                for pattern in ai_patterns:
                    if pattern in content:
                        edit_issues.append(f"发现AI味表达：{pattern}")
                score = 8.0
                if len(edit_issues) > 2: score -= 1.0
                elif len(edit_issues) > 0: score -= 0.3
                passed = score >= 7.0
                consistency_issues = []
            else:
                if depth_level >= 2:
                    ai_patterns = ["眼中闪过", "心中涌起", "只见", "只听", "只觉", "与此同时", "就在这时", "突然", "仿佛", "好像", "似乎", "不禁", "不由得"]
                else:
                    ai_patterns = ["眼中闪过", "心中涌起", "只见", "只听", "只觉", "与此同时", "就在这时", "突然"]
                for pattern in ai_patterns:
                    if pattern in content:
                        edit_issues.append(f"发现AI味表达：{pattern}")
                paragraph_limit = 100 if depth_level >= 2 else 300
                paragraphs = content.split("\n\n")
                long_paragraphs = [p for p in paragraphs if len(p) > paragraph_limit]
                if long_paragraphs:
                    edit_issues.append(f"发现{len(long_paragraphs)}个过长段落（>{paragraph_limit}字）")
                if depth_level >= 2:
                    score = 8.5
                    if len(edit_issues) > 2: score -= 2.0
                    elif len(edit_issues) > 0: score -= 1.0
                else:
                    score = 8.0
                    if len(edit_issues) > 3: score -= 1.5
                    elif len(edit_issues) > 0: score -= 0.5
                consistency_issues = []
                if existing_chapters and depth_level >= 2:
                    if world_info and "灵力" in world_info and "魔法" in content:
                        consistency_issues.append("世界观不一致：设定为灵力体系但出现魔法术语")
                passed = score >= 7.0 and len(consistency_issues) == 0
            output_parts = [
                "【文风精修结果】",
                f"  · 编辑问题：{len(edit_issues)}个",
                f"  · 一致性问题：{len(consistency_issues)}个",
                f"  · 综合评分：{score}",
                f"  · 是否通过：{'✅' if passed else '❌'}",
            ]
            if edit_issues:
                output_parts.append("\n【需要修正的问题】")
                output_parts.extend(f"  - {issue}" for issue in edit_issues[:5])
            if consistency_issues:
                output_parts.append("\n【一致性警告】")
                output_parts.extend(f"  - {issue}" for issue in consistency_issues)
            return AgentContribution(
                agent_name="文风精修师",
                content="\n".join(output_parts),
                score=score,
                details={
                    "passed": passed,
                    "issues": edit_issues + consistency_issues,
                    "edited_content": content,
                    "llm": False,
                    "fallback": True,
                },
            )

    async def _agent_style(self, chapter_idx: int, context: Dict,
                          loop_metadata: Optional[Dict] = None) -> AgentContribution:
        """Agent 5: 风格润色师 — 提供风格模板和语言润色点（深度感知）
        depth 0: 仅关键词汇场和禁用词
        depth 1: 完整风格模板 + 语言润色 + 场景模板
        depth 2: 严格审查标准
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        style_info = context.get("style", "")[:400]

        # 深度感知：不同深度不同风格规则
        if depth_level <= 0:
            style_rules = [
                "核心规则：用动作和细节代替形容词（冰山原则）",
                "避免表达：眼中闪过、心中涌起、似乎、仿佛、好像等模糊词",
            ]
            language_tips = [
                "保持叙述视角稳定（第三人称有限视角）",
            ]
        elif depth_level >= 2:
            style_rules = [
                "段落规则：每段不超过100字，动作描写可更短（1-2句）",
                "对话规则：换人必换行，对话推动剧情，用动作标签区分说话者",
                "描写原则：用动作和细节代替形容词（冰山原则），严格审查禁用词",
                "动作细节：如果要表达紧张，可以写反复折叠纸张、指节发白",
                "避免表达：眼中闪过、心中涌起、似乎、仿佛、好像、突然、与此同时、不禁、不由得",
            ]
            language_tips = [
                "保持叙述视角稳定（第三人称有限视角）",
                "用具体动作代替情绪形容词（严格审查）",
                "对话中加入细微动作：攥拳、转笔、看向窗外、指尖敲击桌面",
                "重要信息、反转、笑点单独成段，形成视觉冲击",
                "检查前章文风一致性，确保词汇场和句式风格统一",
            ]
        else:
            style_rules = [
                "段落规则：每段不超过150字（约5行），动作描写可更短（1-2句）",
                "对话规则：换人必换行，对话推动剧情，不用引号可用冒号",
                "描写原则：用动作和细节代替形容词（冰山原则）",
                "动作细节：如果要表达紧张，可以写反复折叠纸张、指节发白",
                "避免表达：眼中闪过、心中涌起、似乎、仿佛、好像等模糊词",
            ]
            language_tips = [
                "保持叙述视角稳定（一般是第三人称有限视角）",
                "用具体动作代替情绪形容词（不说'他很紧张'，说'他的手指反复折叠那张纸'）",
                "对话中加入细微动作：攥拳、转笔、看向窗外、指尖敲击桌面",
                "重要信息、反转、笑点单独成段，形成视觉冲击",
            ]

        # 场景氛围模板
        if chapter_idx % 5 == 0:
            scene_template = "本章为审查章节：建议用更紧凑的节奏，强化紧张感和信息量"
        elif chapter_idx % 5 == 1:
            scene_template = "新篇章开始：重新建立地点感、时间感、当前处境"
        elif chapter_idx % 5 == 4:
            scene_template = "接近小高潮：加快节奏，缩短段落，增加紧迫感"
        else:
            scene_template = "节奏推进章节：保持稳定的情节前进，适度融入关键细节"

        output_parts = [
            "【写作格式规则】\n" + "\n".join("  · " + r for r in style_rules),
            "【语言润色要点】\n" + "\n".join("  ✎ " + t for t in language_tips),
            "【本章节奏】\n  ◇ " + scene_template,
        ]

        return AgentContribution(
            agent_name="风格润色师",
            content="\n\n".join(output_parts),
            score=8.0,
            details={"style_guide": style_info[:100]},
        )

    async def _agent_draft(self, chapter_idx: int, title: str, summary: str,
                            contributions: List[AgentContribution], context: Dict,
                            loop_metadata: Optional[Dict] = None) -> str:
        """Agent 6: 正文作者（深度感知）
        depth 0: 精简快速生成（~300-500字，骨架草稿）
        depth 1: 标准完整生成（~2000字，含钩子）
        depth 2+: 高质量精修级生成（更严格的表达规范）
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        from ..llm.client import LLMMessage, get_default_llm_client

        client = get_default_llm_client()

        # 汇总所有前序Agent的建议作为上下文
        suggestions_text = "\n\n".join(
            f"【{c.agent_name}的建议】\n{c.content}"
            for c in contributions if c.content
        )

        # ── v5.1: 优先使用记忆协调引擎（统一上下文 + token预算管理）──
        unified_ctx = None
        if self._memory_engine is not None and chapter_idx > 0:
            try:
                unified_ctx = await self._memory_engine.generate_context_for_next_chapter(
                    chapter_idx=chapter_idx,
                    chapter_title=context.get("title", ""),
                    prev_chapter_text=context.get("previous_chapter_text", ""),
                    theme=context.get("theme", ""),
                    novel_id=getattr(self, "_novel_id", None),
                )
            except Exception as e:
                logger.warning("记忆协调引擎上下文生成失败: %s（回退到分散调用）", e)
                unified_ctx = None

        # 故事圣经（方案1）
        story_bible = ""
        if unified_ctx and unified_ctx.get("story_bible"):
            story_bible = unified_ctx["story_bible"]
        elif self.state_tracker:
            story_bible = self.state_tracker.build_story_bible(
                title=context.get("title", ""),
                theme=context.get("theme", ""),
            )

        # 动态状态卡（方案4）
        state_card = ""
        if unified_ctx and unified_ctx.get("state_card"):
            state_card = unified_ctx["state_card"]
        elif self.state_tracker:
            state_card = self.state_tracker.build_state_card()

        # 强制衔接指令（增强版，使用原文 + 结构化钩子）
        connection_instruction = ""
        if unified_ctx and unified_ctx.get("continuity_instruction"):
            # 优先使用统一引擎生成的衔接指令（包含 state_tracker 真实状态 + 学习引擎强度）
            connection_instruction = unified_ctx["continuity_instruction"]
        elif chapter_idx > 1:
            # 回退到旧逻辑
            if self.global_summary:
                prev_chapter_text = context.get("previous_chapter_text", "")
                connection_instruction = self.global_summary.get_connection_instruction_with_text(
                    chapter_idx, prev_chapter_text
                )
            if getattr(self, "_novel_id", None):
                try:
                    from .continuity_engine import load_continuity_from_db, generate_continuity_instruction
                    prev_hooks = await load_continuity_from_db(
                        novel_id=self._novel_id,
                        chapter_idx=chapter_idx - 1,
                    )
                    if prev_hooks:
                        continuity_inst = generate_continuity_instruction(
                            prev_hooks=prev_hooks,
                            next_chapter_idx=chapter_idx,
                        )
                        if connection_instruction:
                            connection_instruction = continuity_inst + "\n\n" + connection_instruction
                        else:
                            connection_instruction = continuity_inst
                except Exception as e:
                    logger.warning("加载 continuity engine 指令失败（非致命）: %s", e)

        # 场景感官锚点（进阶技巧C）
        scene_anchors = ""
        if unified_ctx and unified_ctx.get("scene_anchors"):
            scene_anchors = unified_ctx["scene_anchors"]
        elif self.global_summary:
            scene_anchors = self.global_summary.get_scene_anchors_text()

        # 伏笔线索 & 最近章节摘要
        foreshadowing_summary = unified_ctx.get("foreshadowing_summary", "") if unified_ctx else ""
        recent_summaries = unified_ctx.get("recent_summaries", "") if unified_ctx else ""
        long_term_highlights = unified_ctx.get("long_term_highlights", "") if unified_ctx else ""

        characters = context.get("characters", "")[:2000]
        world_info = context.get("world", "")[:2000]
        style_guide = context.get("style", "")[:300]
        summaries = context.get("summaries", "")[:400]
        foreshadowings = context.get("context_clues", "")[:300]
        # v6.0 角色代入式创作：注入角色代入卡和故事走向
        roleplay_cards = context.get("roleplay_cards", "")
        story_direction = context.get("story_direction", "")[:500]

        # 构建 prompt — 故事圣经在最前面
        prompt_parts = []

        if story_bible:
            prompt_parts.append(story_bible)
            prompt_parts.append("")

        if connection_instruction:
            prompt_parts.append(connection_instruction)
            prompt_parts.append("")

        # ── 上一章原文结尾（直接衔接，修改2）──
        prev_chapter_text = context.get("previous_chapter_text", "")
        if prev_chapter_text and chapter_idx > 1:
            prompt_parts.append(f"""═══════════════════════════════════════════
          上一章结尾（请直接从此处接续）
═══════════════════════════════════════════

{prev_chapter_text[-500:]}

↑ 本章开头必须直接接续以上场景，不得跳跃或重新开始。""")
            prompt_parts.append("")

        if state_card:
            prompt_parts.append(state_card)
            prompt_parts.append("")

        # ── 伏笔线索（v5.1 来自记忆协调引擎）──
        if foreshadowing_summary:
            prompt_parts.append(foreshadowing_summary)
            prompt_parts.append("")

        # ── 最近章节摘要（v5.1 来自记忆协调引擎）──
        if recent_summaries:
            prompt_parts.append(recent_summaries)
            prompt_parts.append("")

        # ── 长期记忆亮点（v5.1 来自 NovelMemory 评分）──
        if long_term_highlights:
            prompt_parts.append(long_term_highlights)
            prompt_parts.append("")

        # ── 角色状态快照（修改7）──
        character_snapshot = ""
        if self.state_tracker:
            character_snapshot = self.state_tracker.get_character_snapshot()
        if character_snapshot:
            prompt_parts.append(character_snapshot)
            prompt_parts.append("")

        if scene_anchors:
            prompt_parts.append(scene_anchors)
            prompt_parts.append("")

        prompt_parts.append(f"""═══════════════════════════════════════════
                 本章创作任务
═══════════════════════════════════════════

章节：第{chapter_idx}章 {title}
本章大纲：{summary if summary else "请根据上下文合理创作"}
小说标题：{context.get("title", "")}
主题：{context.get("theme", "")}
类型：{context.get("genre", "")}
文风基调：{context.get("tone", "")} — 请在行文中贯彻此基调

【角色设定】
{characters if characters else "主角一个，现代青年。"}

【世界观背景】
{world_info if world_info else "请根据主题合理设定世界"}

{f"【故事走向】{chr(10)}{story_direction}" + chr(10) if story_direction else ""}

{roleplay_cards + chr(10) if roleplay_cards else ""}

【风格指南】
{style_guide if style_guide else "现代网络小说风格，节奏紧凑，语言精炼"}

【前情摘要】
{summaries if summaries else "这是第一章，建立世界与人物"}

【前文线索（请自然融入，不要用"伏笔"这个词）】
{foreshadowings if foreshadowings else "无"}

═══════════════════════════════════════════
           8个Agent的协同创作建议
═══════════════════════════════════════════

{suggestions_text}

═══════════════════════════════════════════
                 创作要求
═══════════════════════════════════════════

写作要求：
1. 字数：{800 if depth_level == 0 else 2000 if depth_level == 1 else 2500}-{1500 if depth_level == 0 else 3000 if depth_level == 1 else 3500}字，波动不超过30%（深度{depth_level}）
2. 开头：前三句话必须制造冲突或悬念，不要开篇就交代背景
3. 第一页（约300字）必须出现主角或核心冲突
4. 段落：每段不超过150字；动作描写1-2句一段；对话换人必换行
5. 对话：70%推动剧情或塑造人物，30%交代信息；用细微动作代替表情描写
6. 描写：用动作和细节展示，不用形容词告知；调动五感（视觉/听觉/触觉）
7. 避免：眼中闪过、心中涌起、只见、只听、似乎、好像、仿佛等模糊表达
8. 结尾：留下悬念或线索，作为下一章钩子
9. 严格遵循上述所有Agent的建议，尤其是结构、情节、角色设计
10. 保持视角稳定（第三人称有限视角为主）
11. 如果提供了场景感官锚点，严格使用对应的感官描述
12. 如果提供了衔接指令，严格遵循衔接要求
13. 🚨 禁止输出任何英文单词、英文缩写、JSON、代码或非中文内容。全文必须是纯中文。

现在，请直接输出正文内容。""")

        user_prompt = "\n".join(prompt_parts)

        # 深度感知：system_prompt
        # 使用 PromptResolver 两级 fallback
        from .prompt_resolver import resolve_system_prompt
        system_prompt = await resolve_system_prompt("draft", depth_level)
        if not system_prompt:
            system_prompt = build_draft_system_prompt(depth_level)
        # 记录实际使用的 prompt（供 orchestrator 自动保存）
        self._used_prompts["draft"] = {
            "agent_type": "draft",
            "depth_level": depth_level,
            "prompt_type": "system",
            "content": system_prompt,
            "quality_score": 8,
        }

        # 深度感知：temperature 和 target_words
        if depth_level <= 0:
            temperature = 0.85
            target_words = 600
        elif depth_level >= 2:
            temperature = 0.55
            target_words = 3000
        else:
            temperature = 0.70
            target_words = 2500

        # ── 使用分块生成器（解决大上下文导致截断的问题）──
        from .chunked_generator import chunked_generate_stream

        # 估算总 prompt 长度（用于计算最优 max_tokens）
        total_prompt_len = len(user_prompt) + len(system_prompt)

        full_text = ""
        try:
            full_text = await chunked_generate_stream(
                client=client,
                messages=[LLMMessage(role="user", content=user_prompt)],
                system_prompt=system_prompt,
                temperature=temperature,
                target_words=target_words,
                chunk_size=2000,
                emit=self.emit,
                chapter_idx=chapter_idx,
            )
        except Exception as e:
            print(f"[ChapterPipeline] 分块生成失败: {e}，回退到标准生成")
            try:
                result = await client.generate(
                    [LLMMessage(role="user", content=user_prompt)],
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max(8000, total_prompt_len),
                )
                full_text = result.content if hasattr(result, "content") else str(result)
                await self.emit("chapter_token", {
                    "index": chapter_idx,
                    "token": "",
                    "partial": full_text,
                    "final": True,
                })
            except Exception as e2:
                print(f"[ChapterPipeline] 标准生成也失败: {e2}")
                full_text = f"[第{chapter_idx}章 - 生成失败: {str(e2)[:100]}]"

        return sanitize_chapter_content(sanitize_content(full_text))

    async def _agent_edit(self, chapter_idx: int, content: str,
                            contributions: List[AgentContribution],
                            loop_metadata: Optional[Dict] = None) -> AgentContribution:
        """Agent 7: 编辑润色 — 使语言更精炼，保持段落简短（深度感知）
        depth 0: 跳过编辑
        depth 1: 需编辑时调用 LLM 编辑
        depth 2: 强制编辑 + 更严格的 temperature
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        from ..llm.client import LLMMessage, get_default_llm_client

        # depth 0: 跳过编辑
        if depth_level <= 0:
            return AgentContribution(
                agent_name="编辑润色",
                content="SKELETON模式：跳过编辑润色",
                score=7.0,
                details={"edited_content": content, "skipped": True},
            )

        client = get_default_llm_client()

        # 简单的本地编辑：修正明显问题
        # 1. 检查段落长度
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
        long_count = sum(1 for p in paragraphs if len(p) > 200)

        # 2. 检查禁用词
        banned_phrases = ["眼中闪过", "心中涌起", "只见", "只听", "似乎", "好像", "仿佛"]
        found_banned = sum(1 for b in banned_phrases if b in content)

        edit_notes = []
        if long_count > len(paragraphs) * 0.3:
            edit_notes.append(f"{long_count}段过长，需要拆分")
        if found_banned > 5:
            edit_notes.append(f"发现{found_banned}处禁用表达，需要替换")

        # 如果有明显问题，调用LLM编辑
        # depth 2: 强制编辑
        if depth_level >= 2:
            needs_edit = True
        else:
            needs_edit = len(edit_notes) > 0 or len(content) < 1500
        edited_content = content

        if needs_edit:
            try:
                instructions = "\n".join(edit_notes) if edit_notes else "润色语言，使更精炼"
                user_prompt = f"""请编辑润色以下小说章节。

需要修正：{instructions}

编辑规则：
1. 保持原意不变，只优化语言
2. 长段落拆分为短段落（每段不超过{100 if depth_level >= 2 else 150}字）
3. 用动作细节代替情绪形容词
4. 删除冗余修饰词
5. 保持字数在{2500 if depth_level >= 2 else 2000}-{3500 if depth_level >= 2 else 3000}字

原文：
{content[:4000]}"""

                result = await client.generate(
                    [LLMMessage(role="user", content=user_prompt)],
                    system_prompt="你是专业的小说编辑，擅长精炼语言、优化段落结构、使表达更生动。保持情节和意思不变，只优化写法。",
                    temperature=0.2 if depth_level >= 2 else 0.3,
                    max_tokens=5000,
                )
                if len(result.content.strip()) > 500:
                    edited_content = sanitize_chapter_content(sanitize_content(result.content.strip()))
            except Exception:
                # 编辑失败，使用原文
                pass

        return AgentContribution(
            agent_name="编辑润色",
            content=f"完成编辑润色，修正了 {len(edit_notes)} 个问题",
            score=8.0 if edited_content != content else 7.0,
            details={
                "edited_content": edited_content,
                "issues_found": edit_notes,
                "original_length": len(content),
                "edited_length": len(edited_content),
            },
        )

    async def _agent_review(self, chapter_idx: int, title: str, content: str,
                              context: Dict, all_chapters_text: str = "",
                              loop_metadata: Optional[Dict] = None) -> AgentContribution:
        """Agent 8: 质量审查 — 每5章检查整体一致性（深度感知）
        depth 0: 跳过审查
        depth 1: 本地7维度评分（当前行为）
        depth 2: 更严格的评分阈值
        """
        loop_metadata = loop_metadata or {"depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        from ..llm.client import LLMMessage, get_default_llm_client

        # depth 0: 跳过审查
        if depth_level <= 0:
            return AgentContribution(
                agent_name="质量审查",
                content="SKELETON模式：跳过质量审查",
                score=7.0,
                details={"skipped": True},
            )

        # 本地快速评分（6维度）
        issues = []
        scores = {}

        # 1. 开场
        first_500 = content[:500]
        opening_hooks = ["突然", "？", "谁知", "不料", "竟然", "居然", "猛地", "砰"]
        scores["opening"] = 8.0 if any(h in first_500 for h in opening_hooks) else 6.0

        # 2. 情节冲突
        conflict_markers = ["！", "？", "冲", "追", "挡", "说", "道", "突", "忽然"]
        found_count = sum(content.count(m) for m in conflict_markers)
        scores["plot"] = min(9.0, 6.5 + found_count * 0.01)

        # 3. 角色（本地无法精确判断，给中高分）
        character_info = context.get("characters", "")[:200]
        protagonist_names = re.findall(r"[\u4e00-\u9fff]{2,3}", character_info)
        if protagonist_names:
            main = protagonist_names[0]
            scores["character"] = 7.5 if main in content else 6.0
        else:
            scores["character"] = 7.0

        # 4. 文笔（禁用词检查）
        banned_phrases = ["眼中闪过", "心中涌起", "只见", "只听", "似乎", "好像", "仿佛"]
        banned_count = sum(1 for b in banned_phrases if b in content)
        scores["writing"] = 9.0 if banned_count == 0 else max(6.0, 8.5 - banned_count * 0.2)
        if banned_count > 3:
            issues.append(f"禁用词{int(banned_count)}处")

        # 5. 节奏（段落长度）
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
        if paragraphs:
            avg_len = sum(len(p) for p in paragraphs) / len(paragraphs)
            long_ratio = sum(1 for p in paragraphs if len(p) > 200) / len(paragraphs)
            if avg_len <= 100 and long_ratio < 0.1:
                scores["pacing"] = 9.0
            elif avg_len <= 180 and long_ratio < 0.25:
                scores["pacing"] = 7.5
            else:
                scores["pacing"] = 6.0
            if long_ratio > 0.3:
                issues.append(f"长段落比例{int(long_ratio*100)}%")
        else:
            scores["pacing"] = 6.0

        # 6. 字数
        wc = len(content)
        if 2000 <= wc <= 3000:
            scores["word_count"] = 9.0
        elif 1500 <= wc <= 4000:
            scores["word_count"] = 7.5
        else:
            scores["word_count"] = 6.0
            issues.append(f"字数{wc}，偏离2000-3000")

        # 7. 整体一致性（每5章的特别检查）
        if all_chapters_text:
            # 简化的一致性检查：角色名是否在前文出现过
            if protagonist_names and protagonist_names[0] in all_chapters_text:
                scores["consistency"] = 8.0
            else:
                scores["consistency"] = 6.5
        else:
            scores["consistency"] = 7.0

        # 加权总分
        weights = {"opening": 1, "plot": 2, "character": 1, "writing": 2, "pacing": 2, "word_count": 1, "consistency": 1}
        total_weight = sum(weights.values())
        overall_score = round(sum(scores[k] * weights[k] for k in scores) / total_weight, 1)

        passed = overall_score >= (7.0 if depth_level >= 2 else 6.5)

        # 总结
        summary_text = f"综合评分：{overall_score}/10\n"
        summary_text += "\n".join(f"  · {k}: {v}" for k, v in scores.items())
        if issues:
            summary_text += "\n\n【需要改进】\n" + "\n".join(f"  ⚠ {i}" for i in issues[:3])

        return AgentContribution(
            agent_name="质量审查",
            content=summary_text,
            score=overall_score,
            issues=issues,
            details={"scores": scores, "passed": passed, "word_count": wc, "issues": issues},
        )

    # ────────────────────────────────────────────────────
    # 工具方法
    # ────────────────────────────────────────────────────

    def _register_scene_anchors_from_content(self, chapter_idx: int, content: str):
        """从章节内容中提取地点并注册感官锚点（进阶技巧C）"""
        # 常见场景关键词
        scene_patterns = [
            (r"走进[了]?([\u4e00-\u9fff]{2,6}(?:室|馆|厅|房|院|楼|场|店|城|镇|村|谷|林|园|殿|塔|堡|山|海|河|湖|岛))", "进入"),
            (r"来到[了]?([\u4e00-\u9fff]{2,6}(?:室|馆|厅|房|院|楼|场|店|城|镇|村|谷|林|园|殿|塔|堡|山|海|河|湖|岛))", "来到"),
        ]
        default_anchors = {
            "室": {"嗅觉": "陈旧纸张和灰尘的味道", "听觉": "墙壁内管道的水流声"},
            "馆": {"嗅觉": "淡淡的消毒水味", "听觉": "远处的脚步声回荡"},
            "厅": {"视觉": "昏暗的灯光", "听觉": "低沉的交谈声"},
            "房": {"嗅觉": "木头的味道", "听觉": "窗外的风声"},
            "楼": {"视觉": "灰暗的水泥墙面", "听觉": "电梯运行的嗡嗡声"},
            "院": {"嗅觉": "草药的苦味", "听觉": "风吹树叶的沙沙声"},
            "店": {"嗅觉": "食物的香气", "听觉": "嘈杂的人声"},
            "城": {"视觉": "高耸的城墙", "听觉": "市集的喧嚣"},
            "林": {"嗅觉": "潮湿的泥土味", "听觉": "鸟鸣和虫叫"},
            "谷": {"视觉": "陡峭的岩壁", "听觉": "回声阵阵"},
            "殿": {"视觉": "高耸的穹顶", "嗅觉": "檀香的气味"},
            "塔": {"视觉": "螺旋上升的楼梯", "听觉": "风穿过窗洞的呼啸声"},
        }

        for pattern, _ in scene_patterns:
            matches = re.findall(pattern, content)
            for loc_name in matches:
                if len(loc_name) >= 2:
                    # 查找匹配的默认锚点
                    anchors = {}
                    for suffix, default in default_anchors.items():
                        if loc_name.endswith(suffix):
                            anchors = default
                            break
                    self.global_summary.register_scene_anchor(
                        location_name=loc_name,
                        description=f"第{chapter_idx}章首次出现",
                        sensory_anchors=anchors,
                        chapter=chapter_idx,
                    )

    # ────────────────────────────────────────────────────
    # 主入口：运行管道
    # ────────────────────────────────────────────────────

    async def run(self, chapter_idx: int, title: str, summary: str,
                  chapter_outline_ch: dict = None, context: Dict = None,
                  existing_chapters_text: str = "",
                  previous_chapter_text: str = "",
                  loop_metadata: Optional[Dict] = None,
                  novel_id: Optional[str] = None) -> ChapterPipelineResult:
        """
        v4.0: 6-Skill LOOP 深度感知管道

        Args:
            chapter_idx: 章节序号
            title: 章节标题
            summary: 章节大纲
            context: 共享上下文（世界观、角色、风格等）
            existing_chapters_text: 已生成章节的内容（用于每5章的一致性检查）
            previous_chapter_text: 上一章结尾原文（用于强制衔接，最后800字）
            loop_metadata: v4.0 LOOP 元数据: {"loop": int, "depth": str, "depth_level": int}
        """
        context = context or {}
        context["previous_chapter_text"] = previous_chapter_text
        self._novel_id = novel_id  # v5.0: 供 _agent_draft 使用 continuity engine
        loop_metadata = loop_metadata or {"loop": 0, "depth": "DETAIL", "depth_level": 1}
        depth_level = loop_metadata.get("depth_level", 1)
        contributions: List[AgentContribution] = []
        content = ""
        final_score = 7.0
        passed = True

        # 判断是否是审查章节（5的倍数）
        is_review_chapter = chapter_idx % self.REVIEW_EVERY == 0 and chapter_idx > 0

        await self.emit("pipeline_start", {
            "index": chapter_idx,
            "title": title,
            "is_review_chapter": is_review_chapter,
            "total_agents": 6,  # 方案A：6个Skill
            "depth_level": depth_level,
            "loop": loop_metadata.get("loop", 0),
        })

        # ── Phase 1: 4个Skill协同规划（方案A）──
        await self.emit("pipeline_phase", {
            "phase": "planning",
            "phase_name": "协同规划（故事架构师/世界观/角色/开篇钩子）",
            "index": chapter_idx,
            "depth": depth_level,
        })

        # Skill 1: 故事架构师
        await self._check_pause()
        c1 = await self._agent_outline(chapter_idx, title, summary, context, loop_metadata)
        contributions.append(c1)
        await self.emit("pipeline_step", {
            "step": 1, "name": c1.agent_name, "passed": True,
            "score": c1.score, "index": chapter_idx,
        })

        # Skill 2: 世界观构建师
        await self._check_pause()
        c2 = await self._agent_world(chapter_idx, context, loop_metadata)
        contributions.append(c2)
        await self.emit("pipeline_step", {
            "step": 2, "name": c2.agent_name, "passed": True,
            "score": c2.score, "index": chapter_idx,
        })

        # Skill 3: 角色塑造师
        await self._check_pause()
        c3 = await self._agent_character(chapter_idx, title, context, loop_metadata)
        contributions.append(c3)
        await self.emit("pipeline_step", {
            "step": 3, "name": c3.agent_name, "passed": True,
            "score": c3.score, "index": chapter_idx,
        })

        # v6.0 角色代入：多线程并行代入所有出场角色（保证行为一致性）
        await self._check_pause()
        c_roleplay = await self._agent_character_roleplay_parallel(chapter_idx, title, context, loop_metadata)
        if c_roleplay and c_roleplay.content:
            contributions.append(c_roleplay)
            context["roleplay_cards"] = c_roleplay.content
            await self.emit("pipeline_step", {
                "step": 3.5, "name": c_roleplay.agent_name, "passed": True,
                "score": c_roleplay.score, "index": chapter_idx,
            })

        # Skill 4: 开篇钩子师（仅前三章，且深度>0时）
        if chapter_idx <= 3:
            await self._check_pause()
            c4 = await self._agent_opening_hook(chapter_idx, title, context, loop_metadata)
            contributions.append(c4)
            await self.emit("pipeline_step", {
                "step": 4, "name": c4.agent_name, "passed": True,
                "score": c4.score, "index": chapter_idx,
            })

        # ── Phase 2: Skill 5 核心生成 ──
        await self.emit("pipeline_phase", {
            "phase": "generation",
            "phase_name": "专业写手流式创作",
            "index": chapter_idx,
            "depth": depth_level,
        })

        # Skill 5: 专业写手（流式生成，深度感知）
        await self._check_pause()
        content = await self._agent_draft(chapter_idx, title, summary, contributions, context, loop_metadata)
        await self.emit("pipeline_step", {
            "step": 5, "name": "专业写手", "passed": True,
            "word_count": len(content), "index": chapter_idx,
            "depth": depth_level,
        })

        # ── Phase 3: Skill 6 文风精修（每5章完整审查）──
        review_contribution = None
        if is_review_chapter or depth_level >= 2:
            await self.emit("pipeline_phase", {
                "phase": "review",
                "phase_name": "文风精修师完整审查",
                "index": chapter_idx,
                "depth": depth_level,
            })

            await self._check_pause()
            review_contribution = await self._agent_style_editor_full(
                chapter_idx, title, content, context, existing_chapters_text, loop_metadata
            )
            contributions.append(review_contribution)
            final_score = review_contribution.score
            passed = review_contribution.details.get("passed", True)

            await self.emit("pipeline_step", {
                "step": 8, "name": review_contribution.agent_name, "passed": passed,
                "score": final_score, "index": chapter_idx,
                "issues": review_contribution.details.get("issues", []),
            })

            # 如果审查不通过，最多做1轮修订（仅在深度>=1时）
            revision_rounds = 0
            if not passed and revision_rounds < self.MAX_REVISIONS and depth_level >= 1:
                await self.emit("pipeline_revision", {
                    "index": chapter_idx, "round": revision_rounds + 1,
                    "issues": review_contribution.details.get("issues", []),
                    "score": final_score,
                })

                # 根据审查建议重新生成
                fix_suggestions = "\n".join(
                    f"- [{i.agent_name}] {content}" for i in contributions if i
                )[:500]
                revision_contributions = contributions[:5]  # 重新规划
                content = await self._agent_draft(
                    chapter_idx, title, summary, revision_contributions, context, loop_metadata
                )
                revision_rounds += 1
                await self.emit("pipeline_step", {
                    "step": "r1_draft", "name": "修订正文",
                    "passed": True, "index": chapter_idx,
                    "word_count": len(content),
                })

                # 重新审查
                review2 = await self._agent_style_editor_full(chapter_idx, title, content, context, existing_chapters_text, loop_metadata)
                final_score = review2.score
                passed = review2.details.get("passed", True)
        else:
            # 非审查章节，使用简单的本地评分（深度越高标准越高）
            if depth_level == 0:
                final_score = 7.0 if len(content) >= 1000 else 5.5
            elif depth_level == 1:
                final_score = 7.5 if len(content) >= 1500 else 6.0
            else:
                final_score = 8.0 if len(content) >= 1800 else 6.5
            passed = True

        # ── v5.1: 统一更新各记忆组件（state_tracker + global_summary + novel_memory + continuity）──
        if content and chapter_idx > 0:
            if self._memory_engine is not None:
                try:
                    await self._memory_engine.update_after_chapter(
                        chapter_idx=chapter_idx,
                        chapter_title=title,
                        chapter_content=content,
                        novel_id=novel_id,
                    )
                    logger.info("第%d章: 记忆协调引擎已更新所有组件", chapter_idx)
                except Exception as e:
                    logger.warning("记忆协调引擎更新失败: %s（回退到分散更新）", e)
                    # 回退到分散更新
                    if self.state_tracker:
                        last_ending = content[-300:] if len(content) > 300 else content
                        self.state_tracker.set_last_ending(chapter_idx, last_ending)
            else:
                # 没有记忆协调引擎，保持旧的分散更新逻辑
                if self.state_tracker:
                    last_ending = content[-300:] if len(content) > 300 else content
                    self.state_tracker.set_last_ending(chapter_idx, last_ending)

                # v5.0: 提取并保存结构化衔接钩子
                if novel_id and chapter_idx > 0:
                    try:
                        from .continuity_engine import extract_continuity_hooks, save_continuity_to_db
                        hooks = await extract_continuity_hooks(
                            chapter_content=content,
                            chapter_idx=chapter_idx,
                            chapter_title=title,
                            context=context,
                            state_tracker=self.state_tracker,
                        )
                        await save_continuity_to_db(
                            novel_id=novel_id,
                            chapter_idx=chapter_idx,
                            chapter_title=title,
                            hooks=hooks,
                        )
                        logger.info("第%d章衔接钩子已提取并保存", chapter_idx)
                    except Exception as e:
                        logger.warning("提取衔接钩子失败（非致命）: %s", e)

        # ── v6.0 章节生成后更新角色经历记忆（保证下次代入行为一致性）──
        if content and depth_level >= 1:
            try:
                await self._update_character_memories_after_chapter(chapter_idx, content, context)
            except Exception as e:
                logger.warning("第%d章角色经历记忆更新失败（非致命）: %s", chapter_idx, e)

        # ── 提取并注册场景感官锚点（方案4 + 进阶技巧C）──
        if content and self.global_summary:
            self._register_scene_anchors_from_content(chapter_idx, content)

        # 推送完成事件
        await self.emit("pipeline_done", {
            "index": chapter_idx,
            "title": title,
            "is_review_chapter": is_review_chapter,
            "passed": passed,
            "score": final_score,
            "word_count": len(content),
        })

        return ChapterPipelineResult(
            chapter_index=chapter_idx,
            title=title,
            content=content,
            word_count=len(content),
            is_review_chapter=is_review_chapter,
            passed_review=passed,
            contributions=contributions,
            overall_score=final_score,
            revision_rounds=0 if not review_contribution else (1 if not passed else 0),
        )