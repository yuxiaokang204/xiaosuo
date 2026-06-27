"""
记忆协调引擎 v1.0 — 统一管理 5 个记忆/状态组件

统一数据流：
  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
  │  StateTracker    │ ──▶ │                  │ ──▶ │              │
  │  (角色/地点/伏笔) │     │                  │     │  ChapterPipeline
  └──────────────────┘     │  MemoryCoord-    │     │  (_agent_draft)
                           │  inationEngine    │     │              │
  ┌──────────────────┐     │                  │ ──▶ │  (输出prompt)
  │  GlobalSummary   │ ──▶ │  (统一上下文 +    │     │              │
  │  (摘要/场景锚点)  │     │   token预算)       │     │              │
  └──────────────────┘     │                  │     └──────────────┘
                           │                  │
  ┌──────────────────┐     │                  │
  │  NovelMemory     │ ──▶ │                  │  (写入更新)
  │  (三层记忆 + 评分)│     │                  │
  └──────────────────┘     │                  │
                           │                  │
  ┌──────────────────┐     │                  │
  │ ContinuityEngine │ ──▶ │                  │
  │ (章末钩子提取)    │     │                  │
  └──────────────────┘     └──────────────────┘

两个核心入口：
  1. generate_context_for_next_chapter()  → 生成下一章的上下文
  2. update_after_chapter()               → 生成完成后更新所有记忆
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .memory import NovelMemory, estimate_tokens
from .state_tracker import StateTracker
from .global_summary import GlobalSummary
from .continuity_engine import extract_continuity_hooks, generate_continuity_instruction
from .vector_memory import VectorMemoryStore, get_vector_memory_store

logger = logging.getLogger(__name__)


class MemoryCoordinationEngine:
    """
    协调 5 个记忆/状态组件，提供统一的上下文生成接口。

    - 自动去重：避免 state_tracker.story_bible 与 NovelMemory.characters 重复
    - token 预算管理：确保所有提示加起来不超过预算
    - 统一写入：章节生成完成后一次性更新各组件
    """

    def __init__(
        self,
        state_tracker: Optional[StateTracker] = None,
        global_summary: Optional[GlobalSummary] = None,
        novel_memory: Optional[NovelMemory] = None,
        total_token_budget: int = 4000,
        learning_engine: Optional[Any] = None,
        vector_store: Optional[VectorMemoryStore] = None,  # v5.4: 向量记忆集成
    ):
        self.state_tracker = state_tracker or StateTracker()
        self.global_summary = global_summary or GlobalSummary()
        self.novel_memory = novel_memory or NovelMemory()
        self.total_token_budget = total_token_budget
        self.learning_engine = learning_engine
        # v5.4: 向量记忆存储（持久化 + 语义搜索）
        self.vector_store = vector_store or get_vector_memory_store()

    # ────────────────────────────────────────────────────
    # 核心入口 1: 为下一章生成上下文
    # ────────────────────────────────────────────────────

    async def generate_context_for_next_chapter(
        self,
        chapter_idx: int,
        chapter_title: str = "",
        prev_chapter_text: str = "",
        theme: str = "",
        continuity_hooks: Optional[Dict[str, Any]] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成统一的上下文包。

        Returns:
            {
                "story_bible": "...",          # 故事圣经（世界观+核心角色）
                "state_card": "...",           # 当前角色状态快照
                "continuity_instruction": "...",  # 强制衔接指令（核心增强点）
                "scene_anchors": "...",        # 场景感官锚点
                "foreshadowing_summary": "...",   # 伏笔线索
                "recent_summaries": "...",     # 最近章节摘要
                "context_token_stats": {...},  # token 统计
            }
        """
        start = time.time()

        # ── Step 1: 从各组件抓取原始数据 ──
        raw = self._collect_raw_context(chapter_idx, chapter_title, theme)

        # ── Step 2: 获取衔接强度（从 LearningEngine 或 默认）──
        intensity = self._get_intensity(novel_id)

        # ── Step 3: 构建衔接指令（最高优先级，最有价值的上下文）──
        continuity_instruction = ""
        if chapter_idx > 1:
            hooks = continuity_hooks or self._load_hooks_from_memory(chapter_idx - 1)
            if hooks:
                continuity_instruction = generate_continuity_instruction(
                    prev_hooks=hooks,
                    next_chapter_idx=chapter_idx,
                    intensity=intensity,
                )
            elif prev_chapter_text and self.global_summary:
                # 回退到 global_summary 的旧接口
                continuity_instruction = self.global_summary.get_connection_instruction_with_text(
                    chapter_idx,
                    prev_chapter_text,
                )

        # ── Step 4: 应用 token 预算，按优先级填充 ──
        # 优先级: 衔接指令 > 故事圣经 > 状态卡 > 场景锚点 > 伏笔摘要 > 最近章节摘要
        result = self._allocate_with_budget(raw, continuity_instruction, chapter_idx)

        result["context_token_stats"]["generation_time_ms"] = int((time.time() - start) * 1000)
        return result

    # ────────────────────────────────────────────────────
    # 核心入口 2: 章节生成完成后更新所有记忆
    # ────────────────────────────────────────────────────

    async def update_after_chapter(
        self,
        chapter_idx: int,
        chapter_title: str,
        chapter_content: str,
        key_events: Optional[List[str]] = None,
        character_changes: Optional[Dict[str, str]] = None,
        new_foreshadowing: Optional[List[str]] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        章节生成完成后，统一更新各记忆组件。

        步骤:
          1. state_tracker.set_last_ending(章末结尾)
          2. global_summary.add_chapter_summary(摘要+关键事件)
          3. novel_memory.update_with_chapter(章节内容, 更新引用计数)
          4. continuity_engine.extract_continuity_hooks(提取并保存结构化钩子)
        """
        if not chapter_content:
            return {"status": "empty_content", "updated": 0}

        word_count = len(chapter_content)

        # 1) 记录章末结尾
        if hasattr(self.state_tracker, "set_last_ending"):
            self.state_tracker.set_last_ending(chapter_idx, chapter_content[-300:])

        # 2) 更新摘要链
        if hasattr(self.global_summary, "add_chapter_summary"):
            summary_text = chapter_content[:200]
            self.global_summary.add_chapter_summary(
                chapter=chapter_idx,
                title=chapter_title,
                summary=summary_text,
                key_events=key_events or [],
                character_changes=character_changes or {},
                foreshadowing_new=new_foreshadowing or [],
                last_paragraph=chapter_content[-200:],
                word_count=word_count,
            )

        # 3) 更新 NovelMemory（三层记忆 + 引用计数）
        if self.novel_memory is not None:
            try:
                self.novel_memory.update_with_chapter(chapter_title, chapter_content)
            except Exception as e:
                logger.warning("NovelMemory 更新失败: %s", e)

        # 4) 提取衔接钩子并保存（自动调用 continuity_engine）
        hooks_saved = 0
        try:
            hooks = await extract_continuity_hooks(
                chapter_content=chapter_content,
                chapter_idx=chapter_idx,
                chapter_title=chapter_title,
                state_tracker=self.state_tracker,
            )
            # 从 continuity_engine 导入 DB 保存函数
            from .continuity_engine import save_continuity_to_db
            if novel_id:
                ok = await save_continuity_to_db(
                    novel_id=novel_id,
                    chapter_idx=chapter_idx,
                    chapter_title=chapter_title,
                    hooks=hooks,
                )
                if ok:
                    hooks_saved = 1
            # 同时存入内存缓存，供下一章读取
            self._cached_hooks = (chapter_idx, hooks)
        except Exception as e:
            logger.warning("衔接钩子提取失败: %s", e)

        # 5) v5.4: 同步到向量存储（持久化 + 语义搜索）
        vectors_synced = 0
        try:
            if novel_id:
                # 章节摘要
                self.vector_store.add_memory(
                    f"第{chapter_idx}章 {chapter_title}: {chapter_content[:500]}",
                    metadata={"type": "chapter_summary", "chapter_idx": chapter_idx},
                    novel_id=novel_id,
                )
                vectors_synced += 1
                # 关键事件
                for event in (key_events or [])[:3]:
                    self.vector_store.add_memory(
                        event,
                        metadata={"type": "key_event", "chapter_idx": chapter_idx},
                        novel_id=novel_id,
                    )
                    vectors_synced += 1
                logger.info(f"[MemoryCoordination] 向量存储同步完成: {vectors_synced} 条")
        except Exception as e:
            logger.warning(f"[MemoryCoordination] 向量存储同步失败: {e}")

        return {
            "status": "ok",
            "chapter_idx": chapter_idx,
            "word_count": word_count,
            "hooks_saved": hooks_saved,
            "updated_components": 4,
        }

    # ────────────────────────────────────────────────────
    # v5.4: 语义搜索接口
    # ────────────────────────────────────────────────────

    async def semantic_search(self, query: str, top_k: int = 5,
                              novel_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """语义搜索记忆 — 支持自然语言查询，如"主角第一次遇到反派" """
        return self.vector_store.search(query, top_k=top_k, novel_id=novel_id)

    async def sync_to_vector(self, novel_id: str, text: str, metadata: Optional[Dict] = None) -> str:
        """同步一条记忆到向量存储"""
        metadata = metadata or {}
        return self.vector_store.add_memory(text, metadata=metadata, novel_id=novel_id)

    # ────────────────────────────────────────────────────
    # 内部辅助
    # ────────────────────────────────────────────────────

    def _collect_raw_context(self, chapter_idx: int, title: str, theme: str) -> Dict[str, str]:
        """从各组件抓取原始文本（还没做去重和预算分配）"""
        raw = {}

        # 故事圣经（世界观 + 核心设定）
        if hasattr(self.state_tracker, "build_story_bible"):
            try:
                raw["story_bible"] = self.state_tracker.build_story_bible(
                    title=title,
                    theme=theme,
                ) or ""
            except Exception as e:
                logger.warning("build_story_bible 失败: %s", e)
                raw["story_bible"] = ""
        else:
            raw["story_bible"] = ""

        # 当前状态卡（角色最新状态/地点/时间线）
        if hasattr(self.state_tracker, "build_state_card"):
            try:
                raw["state_card"] = self.state_tracker.build_state_card() or ""
            except Exception as e:
                logger.warning("build_state_card 失败: %s", e)
                raw["state_card"] = ""
        else:
            raw["state_card"] = ""

        # 场景感官锚点
        if hasattr(self.global_summary, "get_scene_anchors_text"):
            raw["scene_anchors"] = self.global_summary.get_scene_anchors_text() or ""
        else:
            raw["scene_anchors"] = ""

        # 伏笔线索
        if hasattr(self.state_tracker, "get_foreshadowing_summary"):
            raw["foreshadowing_summary"] = self.state_tracker.get_foreshadowing_summary() or ""
        else:
            raw["foreshadowing_summary"] = ""

        # 最近章节摘要（提供故事弧线上下文）
        raw["recent_summaries"] = ""
        if hasattr(self.global_summary, "_summaries"):
            try:
                recent = getattr(self.global_summary, "_summaries", [])[-3:]
                if recent:
                    lines = ["【最近章节摘要】"]
                    for s in recent:
                        lines.append(f"  第{s.chapter}章({s.title}): {s.summary}")
                    raw["recent_summaries"] = "\n".join(lines)
            except Exception:
                pass

        # 从 NovelMemory 获取（如果有）长期记忆要点
        raw["long_term_highlights"] = ""
        if self.novel_memory is not None and hasattr(self.novel_memory, "top_items"):
            try:
                top = self.novel_memory.top_items(limit=5)
                if top:
                    lines = ["【长期记忆亮点】"]
                    for item in top:
                        score = item.get("score", 0) if isinstance(item, dict) else 0
                        text = item.get("text", str(item)) if isinstance(item, dict) else str(item)
                        lines.append(f"  [{score:.1f}] {text[:80]}")
                    raw["long_term_highlights"] = "\n".join(lines)
            except Exception as e:
                logger.debug("NovelMemory top_items 失败: %s", e)

        return raw

    def _allocate_with_budget(self, raw: Dict[str, str], continuity_instruction: str,
                              chapter_idx: int) -> Dict[str, Any]:
        """按优先级 + token 预算分配上下文空间"""
        budget = self.total_token_budget
        used = 0
        result = {
            "story_bible": "",
            "state_card": "",
            "continuity_instruction": continuity_instruction,
            "scene_anchors": "",
            "foreshadowing_summary": "",
            "recent_summaries": "",
            "long_term_highlights": "",
            "context_token_stats": {
                "budget": budget,
                "used": 0,
                "chapter_idx": chapter_idx,
            },
        }

        # 1. 衔接指令（最高优先级，直接放入，不做预算裁剪）
        if continuity_instruction:
            result["continuity_instruction"] = continuity_instruction
            used += estimate_tokens(continuity_instruction)

        # 2. 故事圣经
        for key in ["story_bible", "state_card", "scene_anchors",
                    "foreshadowing_summary", "recent_summaries", "long_term_highlights"]:
            content = raw.get(key, "")
            if not content:
                continue
            tokens = estimate_tokens(content)
            remaining = budget - used
            if tokens <= remaining or remaining > 500:
                # 如果剩余预算足够，或还剩很多，直接放入
                result[key] = content
                used += tokens
            elif remaining > 100:
                # 预算紧张但还有剩余，只截取部分
                chars_to_keep = int(remaining * 2)  # 粗略估计: 2 字 = 1 token
                result[key] = content[:chars_to_keep] + "\n...(截断)"
                used += estimate_tokens(result[key])
            else:
                # 预算耗尽，跳过
                result[key] = ""

        stats = result["context_token_stats"]
        stats["used"] = used
        stats["remaining"] = budget - used
        stats["items_included"] = sum(1 for k in result if k != "context_token_stats" and result[k])
        return result

    def _get_intensity(self, novel_id: Optional[str]) -> Dict[str, Any]:
        """从 LearningEngine 获取衔接强度，或返回默认值"""
        if self.learning_engine is not None and hasattr(self.learning_engine, "get_continuity_intensity"):
            try:
                return self.learning_engine.get_continuity_intensity(novel_id)
            except Exception as e:
                logger.debug("LearningEngine intensity 失败: %s", e)
        return {
            "instruction_count": 3,
            "strictness": "medium",
            "require_exact_scene": True,
            "require_state_continuity": True,
        }

    def _load_hooks_from_memory(self, prev_chapter_idx: int) -> Optional[Dict[str, Any]]:
        """从内存缓存加载上一章的钩子"""
        cached = getattr(self, "_cached_hooks", None)
        if cached and cached[0] == prev_chapter_idx:
            return cached[1]
        return None

    # ── 便捷接口（供前端 API 或调试使用）──

    def get_stats(self) -> Dict[str, Any]:
        """获取所有记忆组件的统计信息"""
        stats = {
            "total_token_budget": self.total_token_budget,
        }
        if hasattr(self.state_tracker, "_characters"):
            stats["character_count"] = len(getattr(self.state_tracker, "_characters", {}))
        if hasattr(self.state_tracker, "_foreshadowings"):
            stats["foreshadowing_count"] = len(getattr(self.state_tracker, "_foreshadowings", {}))
        if hasattr(self.global_summary, "_summaries"):
            stats["chapter_summary_count"] = len(getattr(self.global_summary, "_summaries", []))
        if self.novel_memory is not None:
            try:
                ms = self.novel_memory.get_context_stats()
                stats["novel_memory"] = ms
            except Exception:
                pass
        return stats

    def reset(self):
        """重置所有记忆组件"""
        for obj in [self.state_tracker, self.global_summary, self.novel_memory]:
            if obj is None:
                continue
            if hasattr(obj, "reset"):
                try:
                    obj.reset()
                except Exception:
                    pass
        self._cached_hooks = None
        logger.info("MemoryCoordinationEngine 已重置")