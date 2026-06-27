"""
状态跟踪器 v2.0 — 外置记忆系统
核心理念: "故事圣经" + 动态状态卡 + 感官锚点
参考: 用户提供的AI写作连贯性优化方案

核心功能:
  1. 角色状态卡 — 动态追踪每个角色的位置/情绪/物品/目标
  2. 地点状态卡 — 每个场景的感官锚点（霉味、日光灯嗡嗡声）
  3. 时间线 — 故事内时间戳追踪
  4. 伏笔追踪 — 埋设/发展/回收完整链路
  5. 故事圣经生成 — 注入 prompt 的完整上下文
"""
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CharacterState:
    """角色状态"""
    name: str = ""
    role: str = ""  # 主角 / 反派 / 导师 / 配角
    current_location: str = ""
    physical_state: str = "健康"  # 健康 / 受伤 / 重伤 / 死亡
    emotional_state: str = "平静"  # 平静 / 愤怒 / 悲伤 / 喜悦 / 恐惧 / 焦虑
    power_level: str = ""
    relationships: Dict[str, str] = field(default_factory=dict)  # {角色名: 关系}
    key_items: List[str] = field(default_factory=list)  # 持有物品
    goals: List[str] = field(default_factory=list)  # 当前目标
    distinctive_traits: List[str] = field(default_factory=list)  # 独特标签(左撇子、口头禅)
    history: List[Dict] = field(default_factory=list)  # 状态变更历史


@dataclass
class LocationState:
    """地点状态 — 场景感官锚点"""
    name: str = ""
    description: str = ""
    sensory_anchors: Dict[str, str] = field(default_factory=dict)  # {"嗅觉": "霉味", "听觉": "日光灯嗡嗡声"}
    current_state: str = ""  # 当前状态（如"一片漆黑，备用电源还有10分钟"）
    occupants: List[str] = field(default_factory=list)  # 当前在场角色
    last_seen_chapter: int = 0


@dataclass
class Foreshadowing:
    """伏笔"""
    id: str = ""
    chapter_planted: int = 0
    description: str = ""
    type: str = "plot"  # plot / character / world / item
    status: str = "planted"  # planted / developing / resolved
    chapter_resolved: Optional[int] = None
    resolution: str = ""
    importance: int = 3  # 1-5
    characters: List[str] = field(default_factory=list)


@dataclass
class TimelineEvent:
    """时间线事件"""
    chapter: int = 0
    story_time: str = ""  # 故事内时间，如"2030年11月7日，晚上10:17"
    event: str = ""
    real_time: float = 0.0


@dataclass
class CharacterExperienceMemory:
    """角色经历记忆 — 保证人物行为一致性的核心数据结构

    记录角色在每章经历的所有重要事件，使角色后续行为基于其过往经历
    形成的认知和性格变化，而非"失忆"状态。
    """
    chapter: int = 0
    experienced_events: str = ""        # 该角色在此章经历的所有重要事件（第一人称视角）
    emotional_trajectory: str = ""      # 情绪变化轨迹（如"平静→震惊→愤怒→释然"）
    cognition_updates: List[str] = field(default_factory=list)   # 认知更新：新获得的认知/信念改变
    personality_shifts: str = ""        # 性格微调：因此章经历产生的性格变化
    decisions_made: List[str] = field(default_factory=list)      # 该角色在此章做出的关键决策
    information_gained: List[str] = field(default_factory=list)  # 该角色在此章获得的关键信息
    relationships_change: Dict[str, str] = field(default_factory=dict)  # 该角色对他人看法的改变


class StateTracker:
    """
    状态跟踪器 v2.0
    实现"故事圣经" + "动态状态卡" + "感官锚点"
    """

    def __init__(self):
        self._characters: Dict[str, CharacterState] = {}
        self._locations: Dict[str, LocationState] = {}
        self._foreshadowings: Dict[str, Foreshadowing] = {}
        self._timeline: List[TimelineEvent] = []
        self._chapters: List[Dict] = []
        self._last_chapter_ending: str = ""  # 上一章结尾场景
        self._story_time: str = ""  # 当前故事时间
        self._updated_at: float = 0.0
        # v6.0 角色经历记忆链 — 保证人物行为一致性
        self._character_memories: Dict[str, List[CharacterExperienceMemory]] = {}

    # ── 角色状态管理 ──

    def track_character(self, name: str, personality: str = ""):
        """便捷方法: 从编排器追踪角色（v3.0 兼容接口）"""
        if not name or name in self._characters:
            return
        state = CharacterState(name=name, role="主要角色")
        if personality:
            state.distinctive_traits = [p.strip() for p in personality.split(",") if p.strip()][:5]
        self._characters[name] = state
        self._updated_at = time.time()

    def register_character(self, name: str, role: str, initial_state: Dict = None):
        """注册角色"""
        state = CharacterState(name=name, role=role)
        if initial_state:
            state.current_location = initial_state.get("location", "")
            state.physical_state = initial_state.get("physical", "健康")
            state.emotional_state = initial_state.get("emotional", "平静")
            state.power_level = initial_state.get("power", "")
            state.relationships = initial_state.get("relationships", {})
            state.key_items = initial_state.get("items", [])
            state.goals = initial_state.get("goals", [])
            state.distinctive_traits = initial_state.get("traits", [])
        self._characters[name] = state
        self._updated_at = time.time()

    def update_character(self, name: str, chapter: int, changes: Dict):
        """更新角色状态"""
        if name not in self._characters:
            return
        char = self._characters[name]
        history_entry = {"chapter": chapter, "changes": {}}

        for field, key in [("location", "current_location"), ("physical", "physical_state"),
                           ("emotional", "emotional_state"), ("power", "power_level")]:
            if field in changes:
                setattr(char, key, changes[field])
                history_entry["changes"][field] = changes[field]

        if "relationships" in changes:
            char.relationships.update(changes["relationships"])
            history_entry["changes"]["relationships"] = changes["relationships"]
        if "items_add" in changes:
            char.key_items.extend(changes["items_add"])
            history_entry["changes"]["items_add"] = changes["items_add"]
        if "items_remove" in changes:
            for item in changes["items_remove"]:
                if item in char.key_items:
                    char.key_items.remove(item)
            history_entry["changes"]["items_remove"] = changes["items_remove"]
        if "goals" in changes:
            char.goals = changes["goals"]
            history_entry["changes"]["goals"] = changes["goals"]

        char.history.append(history_entry)
        # 限制单角色历史长度，避免长篇小说下内存随章节线性膨胀
        if len(char.history) > 100:
            char.history = char.history[-100:]
        self._updated_at = time.time()

    def get_character(self, name: str) -> Optional[Dict]:
        """获取角色状态"""
        if name not in self._characters:
            return None
        char = self._characters[name]
        return {
            "name": char.name, "role": char.role,
            "location": char.current_location, "physical": char.physical_state,
            "emotional": char.emotional_state, "power": char.power_level,
            "relationships": char.relationships, "items": char.key_items,
            "goals": char.goals, "traits": char.distinctive_traits,
        }

    def get_all_characters_summary(self) -> str:
        """获取所有角色状态摘要（注入prompt上下文）"""
        if not self._characters:
            return ""
        lines = ["【角色当前状态】"]
        for name, char in self._characters.items():
            lines.append(f"- {name}({char.role}): 位于{char.current_location or '未知'}, "
                        f"状态:{char.physical_state}, 情绪:{char.emotional_state}")
            if char.distinctive_traits:
                lines.append(f"  标签: {', '.join(char.distinctive_traits[:3])}")
            if char.key_items:
                lines.append(f"  持有: {', '.join(char.key_items[:5])}")
            if char.goals:
                lines.append(f"  目标: {char.goals[0] if char.goals else '无'}")
        return "\n".join(lines)

    # ── 角色经历记忆链管理（v6.0 保证人物行为一致性）──

    def append_character_memory(self, name: str, entry: CharacterExperienceMemory):
        """章节生成后追加角色经历记忆

        保证角色下次代入时携带完整经历记忆，行为基于过往经历决策。
        """
        if not name:
            return
        self._character_memories.setdefault(name, []).append(entry)
        self._updated_at = time.time()

    def get_character_memory_chain(self, name: str, up_to_chapter: int) -> List[CharacterExperienceMemory]:
        """获取角色截至某章的完整经历记忆链

        用于角色代入时注入，保证角色行为基于其过往经历形成的认知，
        而非"失忆"状态。这是保证人物行为一致性的核心。
        """
        chain = self._character_memories.get(name, [])
        return [m for m in chain if m.chapter < up_to_chapter]

    def get_character_behavior_context(self, name: str, up_to_chapter: int) -> str:
        """生成角色行为上下文摘要（用于代入卡生成）

        将角色经历记忆链整理为行为指导：
        - 过往经历如何塑造了角色当前认知
        - 角色当前的情绪状态和性格倾向
        - 角色已知和未知的信息
        - 角色对其他人物的当前看法
        """
        chain = self.get_character_memory_chain(name, up_to_chapter)
        if not chain:
            return "（该角色尚无过往经历，按原始设定行动）"

        lines = [f"【{name}的经历记忆链（共{len(chain)}章经历）】"]
        for m in chain:
            lines.append(f"\n第{m.chapter}章经历：")
            if m.experienced_events:
                lines.append(f"  经历事件：{m.experienced_events}")
            if m.emotional_trajectory:
                lines.append(f"  情绪轨迹：{m.emotional_trajectory}")
            if m.cognition_updates:
                lines.append(f"  认知更新：{'；'.join(m.cognition_updates)}")
            if m.personality_shifts:
                lines.append(f"  性格微调：{m.personality_shifts}")
            if m.decisions_made:
                lines.append(f"  关键决策：{'；'.join(m.decisions_made)}")
            if m.information_gained:
                lines.append(f"  获得信息：{'；'.join(m.information_gained)}")
            if m.relationships_change:
                rel_str = "；".join(f"对{k}的看法：{v}" for k, v in m.relationships_change.items())
                lines.append(f"  关系变化：{rel_str}")

        # 汇总当前状态
        latest = chain[-1] if chain else None
        if latest:
            lines.append(f"\n【当前行为指导】")
            lines.append(f"  当前情绪状态：{latest.emotional_trajectory.split('→')[-1] if latest.emotional_trajectory else '平静'}")
            if latest.personality_shifts:
                lines.append(f"  性格已演变：{latest.personality_shifts}")
            lines.append(f"  已知信息：{'; '.join(latest.information_gained) if latest.information_gained else '无特殊信息'}")
            lines.append("  ⚠️ 角色只能基于上述已知信息行动，不能泄露角色不应该知道的信息")

        return "\n".join(lines)

    # ── 地点状态管理（感官锚点）──

    def register_location(self, name: str, description: str = "",
                          sensory_anchors: Dict[str, str] = None):
        """注册地点及其感官锚点"""
        loc = LocationState(
            name=name,
            description=description,
            sensory_anchors=sensory_anchors or {},
        )
        self._locations[name] = loc
        self._updated_at = time.time()

    def update_location(self, name: str, chapter: int, current_state: str = "",
                        occupants: List[str] = None):
        """更新地点状态"""
        if name not in self._locations:
            self.register_location(name)
        loc = self._locations[name]
        loc.current_state = current_state
        if occupants is not None:
            loc.occupants = occupants
        loc.last_seen_chapter = chapter
        self._updated_at = time.time()

    def get_location_anchors(self, name: str) -> str:
        """获取地点的感官锚点描述"""
        if name not in self._locations:
            return ""
        loc = self._locations[name]
        anchors = "; ".join(f"{k}: {v}" for k, v in loc.sensory_anchors.items())
        result = f"【地点: {name}】{loc.description}"
        if anchors:
            result += f"\n  感官锚点: {anchors}"
        if loc.current_state:
            result += f"\n  当前状态: {loc.current_state}"
        if loc.occupants:
            result += f"\n  在场角色: {', '.join(loc.occupants)}"
        return result

    def get_all_location_anchors(self) -> str:
        """获取所有地点锚点摘要"""
        if not self._locations:
            return ""
        lines = ["【场景感官锚点】"]
        for name, loc in self._locations.items():
            anchors = "; ".join(f"{k}: {v}" for k, v in loc.sensory_anchors.items())
            lines.append(f"- {name}: {anchors if anchors else loc.description[:50]}")
        return "\n".join(lines)

    # ── 时间线管理 ──

    def set_story_time(self, time_str: str):
        """设置当前故事时间"""
        self._story_time = time_str

    def add_timeline_event(self, chapter: int, event: str, story_time: str = ""):
        """添加时间线事件"""
        self._timeline.append(TimelineEvent(
            chapter=chapter,
            story_time=story_time or self._story_time,
            event=event,
            real_time=time.time(),
        ))
        if story_time:
            self._story_time = story_time
        self._updated_at = time.time()

    def get_timeline_summary(self) -> str:
        """获取时间线摘要"""
        if not self._timeline:
            return ""
        lines = [f"【故事时间线】当前时间: {self._story_time or '未设定'}"]
        for t in self._timeline[-5:]:  # 最近5个事件
            lines.append(f"  第{t.chapter}章 ({t.story_time}): {t.event[:60]}")
        return "\n".join(lines)

    # ── 章末衔接 ──

    def set_last_ending(self, chapter: int, ending_text: str):
        """记录上一章结尾场景（用于强制衔接）"""
        self._last_chapter_ending = ending_text

    def get_last_ending(self) -> str:
        """获取上一章结尾"""
        return self._last_chapter_ending

    # ── 伏笔管理 ──

    def plant_foreshadowing(self, chapter: int, description: str,
                           f_type: str = "plot", characters: List[str] = None,
                           importance: int = 3) -> str:
        """埋下伏笔"""
        fid = f"fw_{len(self._foreshadowings) + 1}_{int(time.time())}"
        fw = Foreshadowing(
            id=fid, chapter_planted=chapter, description=description,
            type=f_type, status="planted", importance=importance,
            characters=characters or [],
        )
        self._foreshadowings[fid] = fw
        self._updated_at = time.time()
        return fid

    def develop_foreshadowing(self, fid: str, chapter: int, development: str):
        """发展伏笔"""
        if fid not in self._foreshadowings:
            return
        self._foreshadowings[fid].status = "developing"
        self._updated_at = time.time()

    def resolve_foreshadowing(self, fid: str, chapter: int, resolution: str):
        """回收伏笔"""
        if fid not in self._foreshadowings:
            return
        fw = self._foreshadowings[fid]
        fw.status = "resolved"
        fw.chapter_resolved = chapter
        fw.resolution = resolution
        self._updated_at = time.time()

    def get_unresolved_foreshadowings(self) -> List[Dict]:
        """获取未回收的伏笔"""
        result = []
        for fid, fw in self._foreshadowings.items():
            if fw.status != "resolved":
                result.append({
                    "id": fid, "chapter_planted": fw.chapter_planted,
                    "description": fw.description, "type": fw.type,
                    "status": fw.status, "importance": fw.importance,
                    "chapters_pending": 0,
                })
        return result

    def get_foreshadowing_summary(self) -> str:
        """获取伏笔摘要（注入prompt上下文）"""
        if not self._foreshadowings:
            return ""
        unresolved = self.get_unresolved_foreshadowings()
        if not unresolved:
            return "【伏笔状态】所有伏笔已回收"
        lines = [f"【伏笔状态】{len(unresolved)}个未回收"]
        for fw in unresolved[:5]:
            lines.append(f"- 第{fw['chapter_planted']}章埋下: {fw['description'][:50]}")
        return "\n".join(lines)

    # ── 章节上下文记录 ──

    def record_chapter(self, chapter: int, title: str, key_events: List[str], word_count: int = 0):
        """记录章节上下文"""
        entry = {
            "chapter": chapter, "title": title,
            "key_events": key_events, "word_count": word_count,
            "timestamp": time.time(),
        }
        existing_idx = None
        for i, c in enumerate(self._chapters):
            if c["chapter"] == chapter:
                existing_idx = i
                break
        if existing_idx is not None:
            self._chapters[existing_idx] = entry
        else:
            self._chapters.append(entry)
            self._chapters.sort(key=lambda x: x["chapter"])
        self._updated_at = time.time()

    def get_chapter_context(self, current_chapter: int, context_window: int = 3) -> str:
        """获取章节上下文（前N章摘要）"""
        if not self._chapters:
            return ""
        recent = [c for c in self._chapters if c["chapter"] < current_chapter]
        recent = recent[-context_window:] if len(recent) >= context_window else recent
        if not recent:
            return ""
        lines = ["【前章提要】"]
        for c in recent:
            events = "；".join(c["key_events"][:2]) if c["key_events"] else ""
            lines.append(f"第{c['chapter']}章《{c['title']}》: {events}")
        return "\n".join(lines)

    # ── 故事圣经生成（核心：注入 prompt 的完整上下文）──

    def build_story_bible(self, title: str = "", theme: str = "",
                          character_names: List[str] = None) -> str:
        """
        构建"故事圣经" — 在每次生成新章节前注入 prompt 开头
        包含: 核心设定 + 已发生事件 + 当前状态 + 伏笔清单 + 章末衔接 + 感官锚点
        """
        parts = []
        parts.append(f"【故事圣经 v1.0】")
        if title:
            parts.append(f"- 小说: {title}")
        if theme:
            parts.append(f"- 主题: {theme}")

        # 核心角色
        if self._characters:
            parts.append("")
            parts.append("【核心角色】")
            for name, char in self._characters.items():
                traits = "、".join(char.distinctive_traits) if char.distinctive_traits else ""
                parts.append(f"- {name}({char.role}): {traits}, "
                            f"状态:{char.physical_state}, 情绪:{char.emotional_state}")
                if char.key_items:
                    parts.append(f"  持有物品: {', '.join(char.key_items)}")
                if char.goals:
                    parts.append(f"  当前目标: {char.goals[0]}")

        # 已发生事件
        if self._chapters:
            parts.append("")
            parts.append("【已发生事件摘要】")
            for c in self._chapters[-5:]:
                events_str = "；".join(c["key_events"][:2]) if c["key_events"] else ""
                parts.append(f"  • 第{c['chapter']}章《{c['title']}》: {events_str}")

        # 当前状态
        parts.append("")
        parts.append(f"【当前状态】")
        parts.append(f"- 故事时间: {self._story_time or '未设定'}")
        if self._last_chapter_ending:
            parts.append(f"- 上一章结尾: {self._last_chapter_ending[:200]}")

        # 伏笔清单
        unresolved = self.get_unresolved_foreshadowings()
        if unresolved:
            parts.append("")
            parts.append(f"【伏笔清单】({len(unresolved)}个未回收)")
            for fw in unresolved[:5]:
                parts.append(f"  • 第{fw['chapter_planted']}章: {fw['description']}")

        # 感官锚点
        if self._locations:
            parts.append("")
            parts.append("【场景感官锚点】")
            for name, loc in self._locations.items():
                anchors = "; ".join(f"{k}: {v}" for k, v in loc.sensory_anchors.items())
                if anchors:
                    parts.append(f"  • {name}: {anchors}")

        return "\n".join(parts)

    # ── 动态状态卡生成 ──

    def build_state_card(self) -> str:
        """
        构建"动态状态卡" — 简化的实时状态，适合快速注入 prompt
        格式对标用户提供的方案4
        """
        parts = ["【当前状态卡】"]
        for name, char in self._characters.items():
            parts.append(f"- {name}: {char.physical_state}, 情绪: {char.emotional_state}")
            if char.distinctive_traits:
                parts.append(f"  标签: {', '.join(char.distinctive_traits[:3])}")
            if char.key_items:
                parts.append(f"  持有: {', '.join(char.key_items[:5])}")
        if self._locations:
            parts.append(f"- 关键地点: {', '.join(self._locations.keys())}")
        parts.append(f"- 故事时间: {self._story_time or '未设定'}")
        if self._last_chapter_ending:
            parts.append(f"- 上章结尾: {self._last_chapter_ending[:150]}")
        return "\n".join(parts)

    def get_character_snapshot(self) -> str:
        """
        获取角色状态快照（用于注入下一章 prompt）
        包含位置、动作、情绪、目标、持有物品等动态信息
        """
        if not self._characters:
            return ""
        parts = ["【角色状态快照 — 上一章结束时】"]
        for name, char in self._characters.items():
            loc = getattr(char, 'location', '') or '未知'
            parts.append(f"- {name}({char.role}): 位置={loc}, "
                         f"状态={char.physical_state}, 情绪={char.emotional_state}")
            if char.goals:
                parts.append(f"  当前目标: {char.goals[0]}")
            if char.key_items:
                parts.append(f"  持有: {', '.join(char.key_items[:3])}")
        if self._last_chapter_ending:
            parts.append(f"\n上一章结尾场景: {self._last_chapter_ending[:200]}")
        return "\n".join(parts)

    # ── 导出与重置 ──

    def to_dict(self) -> Dict:
        return {
            "characters": {
                name: {
                    "name": char.name, "role": char.role,
                    "location": char.current_location, "physical": char.physical_state,
                    "emotional": char.emotional_state, "power": char.power_level,
                    "relationships": char.relationships, "items": char.key_items,
                    "goals": char.goals, "traits": char.distinctive_traits,
                }
                for name, char in self._characters.items()
            },
            "locations": {
                name: {
                    "name": loc.name, "description": loc.description,
                    "sensory_anchors": loc.sensory_anchors,
                    "current_state": loc.current_state, "occupants": loc.occupants,
                }
                for name, loc in self._locations.items()
            },
            "foreshadowings": {
                fid: {
                    "id": fw.id, "chapter_planted": fw.chapter_planted,
                    "description": fw.description, "type": fw.type,
                    "status": fw.status, "chapter_resolved": fw.chapter_resolved,
                    "resolution": fw.resolution, "importance": fw.importance,
                }
                for fid, fw in self._foreshadowings.items()
            },
            "timeline": [
                {"chapter": t.chapter, "story_time": t.story_time, "event": t.event}
                for t in self._timeline
            ],
            "chapters": self._chapters,
            "story_time": self._story_time,
            "last_ending": self._last_chapter_ending,
            "updated_at": self._updated_at,
        }

    def reset(self):
        self._characters.clear()
        self._locations.clear()
        self._foreshadowings.clear()
        self._timeline.clear()
        self._chapters.clear()
        self._story_time = ""
        self._last_chapter_ending = ""
        self._updated_at = 0.0
        # v6.0 清空角色经历记忆链，避免新小说残留旧角色记忆
        self._character_memories.clear()