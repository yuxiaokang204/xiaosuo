"""
全局摘要链系统 v2.0 — 外置记忆 + 场景锚点 + 衔接追踪
参考: 用户提供的AI写作连贯性优化方案

核心功能:
  1. 章节摘要链 — 每章自动生成摘要，确保长篇小说记忆不丢失
  2. 场景感官锚点 — 每个重要地点绑定五感描述
  3. 章末衔接追踪 — 记录每章结尾，强制下一章开头衔接
  4. 前情提要注入 — 最近N章摘要自动注入 prompt 上下文
  5. 情节弧线追踪 — 追踪开端/发展/高潮/收束
"""
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChapterSummary:
    """章节摘要"""
    chapter: int = 0
    title: str = ""
    summary: str = ""  # 200字摘要
    key_events: List[str] = field(default_factory=list)
    character_changes: Dict[str, str] = field(default_factory=dict)  # {角色名: 变化描述}
    new_foreshadowings: List[str] = field(default_factory=list)
    resolved_foreshadowings: List[str] = field(default_factory=list)
    last_paragraph: str = ""  # 章末结尾场景（用于强制衔接）
    word_count: int = 0
    quality_score: float = 0.0
    timestamp: float = 0.0


@dataclass
class SceneAnchor:
    """场景感官锚点"""
    location_name: str = ""
    description: str = ""
    sensory_anchors: Dict[str, str] = field(default_factory=dict)  # {"嗅觉": "霉味", "听觉": "嗡嗡声"}
    first_appeared_chapter: int = 0
    last_appeared_chapter: int = 0


class GlobalSummary:
    """
    全局摘要管理器 v2.0
    维护从第1章到最新章的完整摘要链 + 场景锚点
    """

    def __init__(self):
        self._summaries: List[ChapterSummary] = []
        self._plot_arcs: List[Dict] = []
        self._scene_anchors: Dict[str, SceneAnchor] = {}  # 场景感官锚点
        self._updated_at: float = 0.0
        self._target_chapters: int = 0  # 目标总章节数（可由编排器设置，用于情节进度判断）

    def set_target_chapters(self, n: int):
        """设置目标总章节数，使情节进度按真实比例计算。"""
        self._target_chapters = max(0, int(n or 0))

    def add_chapter_summary(self, chapter: int, title: str, summary: str,
                            key_events: List[str] = None,
                            character_changes: Dict[str, str] = None,
                            foreshadowing_new: List[str] = None,
                            foreshadowing_resolved: List[str] = None,
                            last_paragraph: str = "",
                            word_count: int = 0,
                            quality_score: float = 0.0):
        """添加或更新章节摘要"""
        existing = None
        for s in self._summaries:
            if s.chapter == chapter:
                existing = s
                break

        if existing:
            existing.title = title
            existing.summary = summary
            existing.key_events = key_events or []
            existing.character_changes = character_changes or {}
            existing.new_foreshadowings = foreshadowing_new or []
            existing.resolved_foreshadowings = foreshadowing_resolved or []
            existing.last_paragraph = last_paragraph
            existing.word_count = word_count
            existing.quality_score = quality_score
            existing.timestamp = time.time()
        else:
            self._summaries.append(ChapterSummary(
                chapter=chapter, title=title, summary=summary,
                key_events=key_events or [],
                character_changes=character_changes or {},
                new_foreshadowings=foreshadowing_new or [],
                resolved_foreshadowings=foreshadowing_resolved or [],
                last_paragraph=last_paragraph,
                word_count=word_count, quality_score=quality_score,
                timestamp=time.time(),
            ))
            self._summaries.sort(key=lambda s: s.chapter)
        self._updated_at = time.time()

    # ── 场景感官锚点 ──

    def register_scene_anchor(self, location_name: str, description: str = "",
                              sensory_anchors: Dict[str, str] = None,
                              chapter: int = 0):
        """注册场景感官锚点"""
        if location_name in self._scene_anchors:
            anchor = self._scene_anchors[location_name]
            anchor.last_appeared_chapter = chapter
            if description:
                anchor.description = description
            if sensory_anchors:
                anchor.sensory_anchors.update(sensory_anchors)
        else:
            self._scene_anchors[location_name] = SceneAnchor(
                location_name=location_name,
                description=description,
                sensory_anchors=sensory_anchors or {},
                first_appeared_chapter=chapter,
                last_appeared_chapter=chapter,
            )
        self._updated_at = time.time()

    def get_scene_anchors_text(self) -> str:
        """获取所有场景感官锚点文本（用于注入 prompt）"""
        if not self._scene_anchors:
            return ""
        lines = ["【场景感官锚点 — 每个地点始终使用以下描述】"]
        for name, anchor in self._scene_anchors.items():
            anchors = "; ".join(f"{k}: {v}" for k, v in anchor.sensory_anchors.items())
            lines.append(f"- {name}: {anchor.description[:80]}")
            if anchors:
                lines.append(f"  感官: {anchors}")
        return "\n".join(lines)

    # ── 章节衔接追踪 ──

    def get_last_chapter_ending(self) -> str:
        """获取最后一章的结尾场景"""
        if not self._summaries:
            return ""
        return self._summaries[-1].last_paragraph

    def get_connection_instruction(self, chapter_idx: int) -> str:
        """
        生成强制衔接指令（方案2）
        让AI必须接续上一章结尾，并呼应前文细节
        """
        if chapter_idx <= 1 or not self._summaries:
            return ""

        prev = self._summaries[-1] if self._summaries else None
        if not prev or not prev.last_paragraph:
            return ""

        # 提取前2章的关键细节（作为"必须呼应"的细节）
        callbacks = []
        for s in self._summaries[-3:]:
            for event in (s.key_events or [])[:2]:
                if event and len(event) > 5:
                    callbacks.append(f"第{s.chapter}章: {event}")

        parts = ["【衔接指令 — 必须遵守】"]
        parts.append(f"1. 本章开头必须直接接续上一章结尾的场景/动作/对话。")
        parts.append(f"   上一章结尾是: \"{prev.last_paragraph[:200]}\"")
        if callbacks:
            parts.append(f"2. 本章必须呼应以下前文细节:")
            for cb in callbacks[:3]:
                parts.append(f"   ① {cb}")
        parts.append(f"3. 本章结尾留下下一章的钩子，格式为: \"就在这时，______\"")
        return "\n".join(parts)

    def get_connection_instruction_with_text(self, chapter_idx: int,
                                              prev_chapter_text: str = "") -> str:
        """
        生成强制衔接指令（增强版），优先使用上一章原文结尾
        回退到摘要中的 last_paragraph
        """
        if chapter_idx <= 1:
            return ""

        # 优先使用原文结尾
        ending = prev_chapter_text[-500:] if prev_chapter_text else ""
        if not ending:
            # 回退到摘要
            if not self._summaries:
                return ""
            prev = self._summaries[-1]
            ending = prev.last_paragraph if prev and prev.last_paragraph else ""

        if not ending:
            return ""

        parts = ["【衔接指令 — 必须遵守】"]
        parts.append("1. 本章开头必须直接接续上一章结尾的场景/动作/对话。")
        parts.append(f'   上一章结尾是: "{ending[:300]}"')
        parts.append("2. 本章必须呼应前文2-3个关键细节（如角色状态、未完成动作、对话中的暗示）")
        parts.append('3. 本章结尾留下下一章的钩子，格式为: "就在这时，______"')
        return "\n".join(parts)

    # ── 前情提要 ──

    def get_recent_context(self, count: int = 3) -> str:
        """获取最近N章摘要（注入 prompt 上下文）"""
        recent = self._summaries[-count:] if len(self._summaries) >= count else self._summaries
        if not recent:
            return ""
        lines = ["【前情提要】"]
        for s in recent:
            events = "；".join(s.key_events[:3]) if s.key_events else ""
            lines.append(f"第{s.chapter}章《{s.title}》: {s.summary[:100]}")
            if events:
                lines.append(f"  关键事件: {events}")
        return "\n".join(lines)

    def get_full_summary(self) -> str:
        """获取完整全局摘要"""
        lines = [f"# 全局摘要 - 共{len(self._summaries)}章\n"]
        for s in self._summaries:
            lines.append(f"## 第{s.chapter}章《{s.title}》")
            lines.append(f"  - 摘要: {s.summary}")
            lines.append(f"  - 字数: {s.word_count}, 质量分: {s.quality_score:.1f}")
            if s.key_events:
                lines.append(f"  - 关键事件: {'; '.join(s.key_events)}")
            if s.character_changes:
                changes = "; ".join(f"{k}: {v}" for k, v in s.character_changes.items())
                lines.append(f"  - 角色变化: {changes}")
            if s.new_foreshadowings:
                lines.append(f"  - 新伏笔: {'; '.join(s.new_foreshadowings)}")
            if s.resolved_foreshadowings:
                lines.append(f"  - 回收伏笔: {'; '.join(s.resolved_foreshadowings)}")
            if s.last_paragraph:
                lines.append(f"  - 章末结尾: {s.last_paragraph[:100]}")
            lines.append("")
        return "\n".join(lines)

    def get_plot_progress(self) -> Dict:
        """获取情节进度"""
        if not self._summaries:
            return {"phase": "未开始"}
        total = len(self._summaries)
        # 以"已写章节 / 目标章节"的进度百分比划分阶段；缺目标时退化为按已写章节估算。
        # 旧实现写成 `total <= total*0.3+2`（自比较恒不成立），导致"发展"阶段永不可达、
        # 7 章即误判"收束"。这里改为基于比例的正确分界。
        # 无目标章节数时退化为按 10 章（系统默认章节数）估算，保证四个阶段都可达。
        target = getattr(self, "_target_chapters", 0) or 0
        denom = max(total, target, 10)
        ratio = total / denom
        if total <= 2:
            phase = "开端"
        elif ratio <= 0.3:
            phase = "发展"
        elif ratio <= 0.7:
            phase = "高潮"
        else:
            phase = "收束"
        return {
            "total_chapters": total,
            "phase": phase,
            "total_words": sum(s.word_count for s in self._summaries),
            "avg_quality": sum(s.quality_score for s in self._summaries) / max(total, 1),
            "last_updated": self._updated_at,
        }

    def to_dict(self) -> Dict:
        return {
            "total_chapters": len(self._summaries),
            "summaries": [
                {
                    "chapter": s.chapter, "title": s.title, "summary": s.summary,
                    "key_events": s.key_events, "word_count": s.word_count,
                    "quality_score": s.quality_score, "last_paragraph": s.last_paragraph[:100],
                }
                for s in self._summaries
            ],
            "scene_anchors": {
                name: {
                    "description": a.description,
                    "sensory_anchors": a.sensory_anchors,
                    "first_chapter": a.first_appeared_chapter,
                    "last_chapter": a.last_appeared_chapter,
                }
                for name, a in self._scene_anchors.items()
            },
            "plot_progress": self.get_plot_progress(),
        }

    def reset(self):
        self._summaries.clear()
        self._plot_arcs.clear()
        self._scene_anchors.clear()
        self._updated_at = 0.0