"""
角色塑造Agent v2.0 — 映射到角色塑造师Skill

v2.0 改进：
- 继承新的 BaseAgent，使用 LLMGateway + Memory + EventBus
- 统一 execute() 接口
- 通过 EventBus 发布执行事件
- 保留所有原有功能和 mock fallback
"""
import re
from typing import Any, Dict

from .base import BaseAgent
from .prompts import CHARACTER_SYSTEM_PROMPT, build_character_user_prompt


class CharacterAgent(BaseAgent):
    """角色Agent - 设计角色性格、背景、目标、成长弧线"""

    AGENT_ID = "character"
    AGENT_NAME = "角色塑造师"
    CAPABILITIES = ["character_design", "development"]
    EXPECTS_JSON = True
    DEFAULT_TEMPERATURE = 0.7

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成角色设计

        Args:
            context: 包含 role, world_info, theme, title, depth_level 等字段

        Returns:
            包含 success, name, aliases, role, personality, background, goals,
            conflicts, arc_start, arc_mid, arc_end, speech_pattern, appearance 的结果
        """
        # 发布执行开始事件
        execution_id = await self._publish_execute_start(context)

        try:
            # 提取上下文参数
            role_hint = str(context.get("role", "主角"))
            world_info = str(context.get("world_info", ""))
            theme = str(context.get("theme", ""))
            title = str(context.get("title", ""))
            depth_level = int(context.get("depth_level", 1))
            title_analysis = context.get("title_analysis") or {}

            # 构建用户提示词
            user_prompt = build_character_user_prompt(
                role_hint, world_info, depth_level, title,
                title_analysis=title_analysis if title_analysis else None,
            )
            if theme:
                user_prompt += f"\n\n【小说主题】{theme}"

            # 调用LLM
            result = await self._call_llm(
                CHARACTER_SYSTEM_PROMPT,
                user_prompt,
                expects_json=True,
                max_tokens=8000,
            )

            # 规范输出结构
            data = result.get("data") or {}
            arc = data.get("arc", {})

            # 写入长期记忆：角色信息
            if data and data.get("name"):
                self.memory.store_characters([
                    {
                        "id": f"char_{data['name']}",
                        "name": data["name"],
                        "personality": data.get("personality", ""),
                        "background": data.get("background", ""),
                        "role": data.get("role", "主角"),
                        "keywords": [data["name"]],
                    }
                ])

            # 发布执行完成事件
            await self._publish_execute_done(execution_id, result)

            return {
                "success": True,
                "fallback": result.get("fallback", False),
                "name": data.get("name", ""),
                "aliases": data.get("aliases", []),
                "role": data.get("role", "supporting"),
                "psychological_profile": data.get("psychological_profile", {}),
                "personality": data.get("personality", ""),
                "background": data.get("background", ""),
                "goals": data.get("goals", []),
                "conflicts": data.get("conflicts", []),
                "arc_start": arc.get("start", "") if isinstance(arc, dict) else "",
                "arc_mid": arc.get("midpoint", "") if isinstance(arc, dict) else "",
                "arc_end": arc.get("end", "") if isinstance(arc, dict) else "",
                "speech_fingerprint": data.get("speech_fingerprint", {}),
                "appearance": data.get("appearance", ""),
                "behavior_tags": data.get("behavior_tags", []),
                "relationship_webs": data.get("relationship_webs", []),
                "provider": result.get("provider"),
                "latency_ms": result.get("latency_ms"),
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
                "name": "",
                "aliases": [],
                "role": "supporting",
                "personality": "",
                "background": "",
                "goals": [],
                "conflicts": [],
                "arc_start": "",
                "arc_mid": "",
                "arc_end": "",
                "speech_fingerprint": {},
                "appearance": "",
                "behavior_tags": [],
                "relationship_webs": [],
            }

    def _mock_fallback(self, user_prompt: str) -> Dict:
        """生成切题的 mock 角色数据"""
        prompt_lower = user_prompt.lower()
        if "修真" in prompt_lower or "修仙" in prompt_lower or "仙侠" in prompt_lower:
            return {
                "name": "林逸",
                "aliases": ["小林", "逸公子"],
                "role": "protagonist",
                "psychological_profile": {
                    "core_drive": "追求长生之道，守护师门",
                    "inner_conflict": "既依赖传承力量，又怕被力量反噬",
                    "decision_pattern": "沉稳决策，关键时刻敢于冒险",
                    "breaking_point": "当师门或亲友面临生死危机时",
                },
                "personality": "沉稳内敛，重情重义，外柔内刚，偶尔幽默自嘲。面对困难不轻言放弃，善于在逆境中寻找机会。",
                "background": "出身小宗门的外门弟子，意外获得上古传承，踏上逆天修行之路。在修炼中不断突破自我，逐渐揭开上古传承的秘密。",
                "goals": ["突破境界", "守护师门", "探寻上古真相"],
                "conflicts": [
                    {"type": "internal", "desc": "既依赖传承力量，又怕被力量反噬"},
                    {"type": "external", "desc": "对师门忠诚与对仇敌宽容之间的矛盾"},
                ],
                "arc": {
                    "start": "底层的默默修行者",
                    "trigger": "获得上古传承",
                    "midpoint": "崭露头角但代价沉重",
                    "end": "接受命运，成为守护者",
                },
                "speech_fingerprint": {
                    "pattern": "话不多但句句中肯",
                    "catchphrase": "随缘",
                    "pace": "沉稳缓慢",
                    "taboo_words": ["浮夸", "虚浮"],
                },
                "appearance": "中等身材，眼神清澈，着素色道袍，腰间系着一只破旧的玉佩。",
                "behavior_tags": ["紧张时无意识转动玉佩", "思考时眉头微皱"],
                "relationship_webs": [
                    {"target": "师尊", "type": "导师", "dynamic": "敬重且依赖"},
                    {"target": "同门师兄", "type": "盟友", "dynamic": "互相扶持"},
                ],
            }
        elif "科幻" in prompt_lower or "赛博" in prompt_lower or "未来" in prompt_lower:
            return {
                "name": "陈凯",
                "aliases": ["凯哥", "K"],
                "role": "protagonist",
                "psychological_profile": {
                    "core_drive": "揭露真相，保护家人",
                    "inner_conflict": "使用非法手段对抗邪恶是否合理",
                    "decision_pattern": "理性分析优先，关键时刻敢于冒险",
                    "breaking_point": "当家人或无辜者受到威胁时",
                },
                "personality": "理性冷静，善于分析，但在关键时刻敢于冒险。对技术有近乎偏执的热爱。",
                "background": "前企业程序员，因揭露公司黑幕被追捕，现为地下黑客。在黑暗中寻找光明，试图摧毁腐败的系统。",
                "goals": ["揭露真相", "保护家人", "摧毁腐败系统"],
                "conflicts": [
                    {"type": "internal", "desc": "使用非法手段对抗邪恶是否合理"},
                    {"type": "external", "desc": "个人复仇与大局利益之间的抉择"},
                ],
                "arc": {
                    "start": "被追捕的逃亡者",
                    "trigger": "发现企业更大阴谋",
                    "midpoint": "成长为反抗领袖",
                    "end": "建立新秩序",
                },
                "speech_fingerprint": {
                    "pattern": "简洁高效，多用技术术语",
                    "catchphrase": "数据不会说谎",
                    "pace": "快速干脆",
                    "taboo_words": ["模糊", "大概"],
                },
                "appearance": "瘦高个，戴着数据眼镜，右手有义体改造痕迹。",
                "behavior_tags": ["思考时手指在空中虚拟敲击", "紧张时会调整数据眼镜"],
                "relationship_webs": [
                    {"target": "队友J", "type": "盟友", "dynamic": "技术互补，互相信任"},
                    {"target": "企业CEO", "type": "对手", "dynamic": "猫鼠游戏"},
                ],
            }
        elif "悬疑" in prompt_lower or "推理" in prompt_lower or "侦探" in prompt_lower:
            return {
                "name": "陈默",
                "aliases": ["老陈", "陈探长"],
                "role": "protagonist",
                "psychological_profile": {
                    "core_drive": "破解未解悬案，为受害者伸张正义",
                    "inner_conflict": "对真相的执着与现实的妥协之间",
                    "decision_pattern": "观察入微，沉默决策",
                    "breaking_point": "当证据指向信任的人时",
                },
                "personality": "观察入微，沉默寡言，执着于真相，有轻微强迫症。",
                "background": "前刑警，因一起未破悬案辞职，现为私家侦探。在调查中不断接近真相，却发现真相往往比表象更复杂。",
                "goals": ["破解未解悬案", "为受害者伸张正义"],
                "conflicts": [
                    {"type": "internal", "desc": "对真相的执着与现实的妥协之间"},
                    {"type": "external", "desc": "信任他人与保持警惕的矛盾"},
                ],
                "arc": {
                    "start": "孤身追查悬案",
                    "trigger": "发现惊人真相",
                    "midpoint": "发现真相但代价沉重",
                    "end": "真相大白但付出代价",
                },
                "speech_fingerprint": {
                    "pattern": "提问简洁，回答更简洁，喜欢用反问",
                    "catchphrase": "有意思",
                    "pace": "缓慢沉稳",
                    "taboo_words": ["猜测", "也许"],
                },
                "appearance": "中年，略显沧桑，总是穿着深色风衣，口袋里永远有笔记本。",
                "behavior_tags": ["思考时翻阅笔记本", "审讯时目光直视对方"],
                "relationship_webs": [
                    {"target": "搭档小李", "type": "盟友", "dynamic": "亦师亦友"},
                    {"target": "神秘人", "type": "镜像", "dynamic": "亦敌亦友"},
                ],
            }
        elif "都市" in prompt_lower or "现代" in prompt_lower or "校园" in prompt_lower:
            return {
                "name": "苏小冉",
                "aliases": ["小冉", "冉冉"],
                "role": "protagonist",
                "psychological_profile": {
                    "core_drive": "揭开身世之谜，保护身边的人",
                    "inner_conflict": "平凡生活的渴望与不凡命运的拉扯",
                    "decision_pattern": "乐观应对，内心敏感但表面坚强",
                    "breaking_point": "当身边人受到威胁时",
                },
                "personality": "乐观开朗，善良坚韧，内心敏感但表面坚强。善于用笑容掩饰内心的不安。",
                "background": "普通大学生，在一次意外中发现自己的身世秘密，生活从此改变。在平凡与不凡之间寻找平衡。",
                "goals": ["揭开身世之谜", "保护身边的人", "找到属于自己的路"],
                "conflicts": [
                    {"type": "internal", "desc": "平凡生活的渴望与不凡命运的拉扯"},
                    {"type": "external", "desc": "对他人的信任与自我保护"},
                ],
                "arc": {
                    "start": "普通大学生",
                    "trigger": "发现身世秘密",
                    "midpoint": "逐步发现真相",
                    "end": "接受命运并主动选择",
                },
                "speech_fingerprint": {
                    "pattern": "轻松自然，偶尔语出惊人，喜欢用比喻",
                    "catchphrase": "没关系啦",
                    "pace": "轻快活泼",
                    "taboo_words": ["绝望", "放弃"],
                },
                "appearance": "清秀，扎马尾，穿着简单干净，眼神明亮。",
                "behavior_tags": ["紧张时会不自觉地扎马尾", "开心时会哼歌"],
                "relationship_webs": [
                    {"target": "闺蜜小雅", "type": "盟友", "dynamic": "无话不谈"},
                    {"target": "神秘学长", "type": "导师", "dynamic": "指引与启发"},
                ],
            }
        else:
            return {
                "name": "主角",
                "aliases": [],
                "role": "protagonist",
                "psychological_profile": {
                    "core_drive": "寻找真相，保护重要的人",
                    "inner_conflict": "理想与现实的冲突",
                    "decision_pattern": "坚定勇敢，有自己独特的信念",
                    "breaking_point": "当重要之人受到伤害时",
                },
                "personality": "坚定勇敢，有自己独特的信念，在逆境中成长。不轻易放弃，也不盲目冲动。",
                "background": "身世成谜，被命运选中，踏上未知的旅程。在旅途中不断发现自我。",
                "goals": ["寻找真相", "保护重要的人"],
                "conflicts": [
                    {"type": "internal", "desc": "理想与现实的冲突"},
                    {"type": "external", "desc": "内心挣扎与外部压力的矛盾"},
                ],
                "arc": {
                    "start": "迷茫的普通人",
                    "trigger": "命运之选",
                    "midpoint": "找到方向但遭遇挫折",
                    "end": "成长并主动承担责任",
                },
                "speech_fingerprint": {
                    "pattern": "有自己的独特表达方式",
                    "catchphrase": "我会找到答案",
                    "pace": "平稳坚定",
                    "taboo_words": [],
                },
                "appearance": "有辨识度的外貌特征，让人一眼记住。",
                "behavior_tags": ["思考时望向远方", "下定决心时会握拳"],
                "relationship_webs": [
                    {"target": "同伴", "type": "盟友", "dynamic": "互相扶持"},
                    {"target": "对手", "type": "对手", "dynamic": "既对抗又尊重"},
                ],
            }
