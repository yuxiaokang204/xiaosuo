"""
章节衔接引擎 v2.0 — 结合记忆系统

增强：
  1. StateTracker 驱动的钩子提取（利用真实角色/地点状态，不依赖简单关键词）
  2. LearningEngine 强度感知的衔接指令（高分少指令，低分多要求）
  3. GlobalSummary 摘要链联动（利用最近章节摘要做上下文校验）
  4. NovelMemory 的伏笔回收提示
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def extract_continuity_hooks(
    chapter_content: str,
    chapter_idx: int,
    chapter_title: str = "",
    context: Optional[Dict[str, Any]] = None,
    state_tracker: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Stage A: 从章节正文中提取结构化钩子（增强版 v2.0）

    优先从 state_tracker 读取真实角色/地点状态，辅以基于规则的章末文本分析。
    """
    context = context or {}
    full_text = chapter_content.strip()
    if not full_text:
        return _empty_hooks()

    # 取章末 800 字
    ending_text = full_text[-800:] if len(full_text) > 800 else full_text

    # ── 提取场景信息 ──
    scene = _extract_scene(ending_text)

    # ── 提取角色状态（增强 v2.0：优先使用 state_tracker 真实状态） ──
    character_info = context.get("characters", "")
    character_states = _extract_character_states(ending_text, character_info, state_tracker)

    # ── 提取未解决的情节节点 ──
    plot_nodes = _extract_plot_nodes(ending_text)

    # ── 提取章末张力点 ──
    # 取最后 200 字判断是否有悬念/冲突/转折
    tension_points = _extract_tension_points(ending_text[-200:])

    # ── v2.0: 从 state_tracker 补充伏笔线索（不依赖关键词匹配）──
    if state_tracker is not None and hasattr(state_tracker, "get_unresolved_foreshadowings"):
        try:
            unresolved = state_tracker.get_unresolved_foreshadowings()
            if unresolved:
                # 将 state_tracker 中记录但尚未回收的伏笔追加到 plot_nodes
                existing_texts = {pn.get("text", "") for pn in plot_nodes}
                for fw in unresolved[:5]:
                    desc = fw.get("description", "")
                    if desc and desc not in existing_texts:
                        ch_planted = fw.get("chapter_planted", 0)
                        plot_nodes.append({
                            "text": f"第{ch_planted}章伏笔: {desc}",
                            "resolved": False,
                            "from_state_tracker": True,
                        })
                        existing_texts.add(desc)
        except Exception as e:
            logger.warning("从state_tracker获取伏笔失败: %s", e)

    return {
        "ending_text": ending_text,
        "scene": scene,
        "character_states": character_states,
        "plot_nodes": plot_nodes,
        "tension_points": tension_points,
    }


def _extract_scene(text: str) -> Dict[str, str]:
    """从文本中提取场景信息"""
    scene = {"location": "", "time": "", "atmosphere": ""}

    # 地点关键词
    location_keywords = [
        "房间", "大厅", "广场", "街道", "山顶", "废墟", "宫殿", "客栈",
        "办公室", "教室", "医院", "基地", "飞船", "密室", "门口", "窗边",
        "树林", "河边", "海边", "沙漠", "城市", "小镇", "村庄",
    ]
    for loc in location_keywords:
        if loc in text:
            scene["location"] = loc
            break

    # 时间关键词
    time_keywords = ["清晨", "黄昏", "深夜", "正午", "午后", "傍晚", "凌晨", "子夜", "黎明"]
    for t in time_keywords:
        if t in text:
            scene["time"] = t
            break

    # 氛围词
    atmosphere_keywords = [
        "紧张", "压抑", "欢快", "肃杀", "宁静", "诡异", "温暖", "寒冷",
        "阴森", "热烈", "悲痛", "恐惧", "期待", "愤怒", "绝望", "希望",
    ]
    for a in atmosphere_keywords:
        if a in text:
            scene["atmosphere"] = a
            break

    return scene


def _extract_character_states(text: str, character_info: str,
                               state_tracker: Optional[Any] = None) -> List[Dict[str, str]]:
    """
    从文本中提取角色状态（增强版 v2.0）

    优先级:
      1. state_tracker 中记录的真实角色状态（位置/情绪/物品/目标）
      2. 基于关键词的文本分析作为补充
    """
    states = []

    # ── 策略 1: 从 state_tracker 获取真实状态 ──
    st_names = set()
    if state_tracker is not None and hasattr(state_tracker, "_characters"):
        try:
            chars = getattr(state_tracker, "_characters", {})
            if chars:
                for name, ch in chars.items():
                    if not name or len(name) < 2:
                        continue
                    st_names.add(name)
                    state = {
                        "name": name,
                        "status": getattr(ch, "physical_state", "") or "",
                        "emotion": getattr(ch, "emotional_state", "") or "",
                        "intent": "",
                        "location": getattr(ch, "current_location", "") or "",
                        "role": getattr(ch, "role", "") or "",
                        "from_state_tracker": True,
                    }
                    if state["status"] or state["emotion"] or state["location"]:
                        states.append(state)
        except Exception as e:
            logger.warning("从 state_tracker 提取角色状态失败: %s", e)

    # ── 策略 2: 基于关键词分析补充 state_tracker 未覆盖的角色 ──
    protagonist_names = re.findall(r"[\u4e00-\u9fff]{2,4}", character_info[:200])

    emotion_patterns = [
        (r"(紧张|害怕|恐惧|恐慌)", "紧张"),
        (r"(愤怒|暴怒|怒火|愤恨)", "愤怒"),
        (r"(悲伤|难过|痛苦|绝望)", "悲伤"),
        (r"(喜悦|高兴|兴奋|激动)", "喜悦"),
        (r"(冷静|沉着|镇定)", "冷静"),
        (r"(困惑|迷茫|不解|疑惑)", "困惑"),
        (r"(坚定|决然|毅然)", "坚定"),
        (r"(疲惫|疲惫不堪|筋疲力尽)", "疲惫"),
    ]

    status_patterns = [
        (r"(受伤|流血|倒下|昏迷)", "受伤"),
        (r"(逃走|逃离|逃跑|撤退)", "逃离"),
        (r"(战斗|对峙|交锋|交手)", "战斗"),
        (r"(对话|交谈|质问|回答)", "对话"),
        (r"(等待|观望|潜伏|隐藏)", "等待"),
        (r"(决定|决心|做出|选择)", "决定"),
        (r"(发现|察觉|意识|明白)", "发现"),
        (r"(离开|出发|启程|前往)", "离开"),
    ]

    for name in protagonist_names[:3]:
        if name in st_names:
            continue  # state_tracker 已经覆盖
        if name not in text:
            continue
        state = {"name": name, "status": "", "emotion": "", "intent": ""}

        idx = text.find(name)
        context_text = text[max(0, idx - 50):idx + 50 + len(name)]

        for pattern, emotion in emotion_patterns:
            if re.search(pattern, context_text):
                state["emotion"] = emotion
                break

        for pattern, status in status_patterns:
            if re.search(pattern, context_text):
                state["status"] = status
                break

        states.append(state)

    return states[:5]  # 最多 5 个角色，避免上下文过长


def _extract_plot_nodes(text: str) -> List[Dict[str, Any]]:
    """提取未解决的情节节点"""
    nodes = []

    # 未解决标识词
    unresolved_patterns = [
        r"(还未|尚未|还没|仍未|未解|未了|未完成).{0,20}",
        r"(还在|仍在|依旧).{0,20}",
        r"(不会|不能|无法|难以).{0,20}",
        r"(如果|要是|一旦).{0,20}",
        r"(不知|不明|未明|未料).{0,20}",
    ]

    for pattern in unresolved_patterns:
        matches = re.findall(pattern, text)
        for m in matches[:2]:
            if len(m) > 5:
                nodes.append({"text": m.strip(), "resolved": False})

    return nodes[:3]


def _extract_tension_points(text: str) -> List[Dict[str, str]]:
    """提取章末张力点"""
    points = []

    # 冲突类张力
    if re.search(r"(突然|忽然|猛|砰|轰|咔嚓|唰)", text):
        points.append({"text": "章末存在突发事件/动作转折", "type": "event"})

    # 悬念类张力
    if re.search(r"(\?|……|…|未完|待续|到底|究竟|怎么|为什么)", text):
        points.append({"text": "章末留有悬念或疑问", "type": "suspense"})

    # 对话张力
    if re.search(r"(说|道|问|答|喊|叫|吼|喝|斥|怒|冷|笑)['\"'""]?$", text[-100:]):
        points.append({"text": "章末以对话结束，形成对话张力", "type": "dialogue"})

    # 场景切换张力
    if re.search(r"(与此同时|另一边|画面一转|镜头切换|而在)", text):
        points.append({"text": "章末出现场景切换，形成交叉张力", "type": "crosscut"})

    # 情绪张力
    if re.search(r"(震惊|震撼|不敢相信|目瞪口呆|难以置信|毛骨悚然|不寒而栗)", text):
        points.append({"text": "章末情绪强度高，形成情绪张力", "type": "emotion"})

    if not points:
        points.append({"text": "章末节奏平稳，建议添加衔接提示", "type": "smooth"})

    return points


def generate_continuity_instruction(
    prev_hooks: Dict[str, Any],
    next_chapter_idx: int,
    intensity: Optional[Dict[str, Any]] = None,
    style_preference: str = "",
) -> str:
    """
    Stage B: 生成强制衔接指令

    Args:
        prev_hooks: 上一章的结构化钩子（来自 extract_continuity_hooks 或 DB）
        next_chapter_idx: 下一章序号
        intensity: 学习引擎返回的衔接强度参数
        style_preference: 学习引擎返回的表达偏好
    """
    intensity = intensity or {
        "instruction_count": 3,
        "strictness": "medium",
        "require_exact_scene": True,
        "require_state_continuity": True,
    }

    prev_idx = next_chapter_idx - 1
    parts = []

    parts.append("【强制衔接要求 — 必须严格遵守】")
    parts.append("")

    # 规则 1: 场景接续
    scene = prev_hooks.get("scene", {})
    ending_text = prev_hooks.get("ending_text", "")[-300:]
    if intensity.get("require_exact_scene", True):
        parts.append(f"1. 必须从第{prev_idx}章结尾的同一时刻继续，不得跳跃时间线或切换场景。")
        if ending_text:
            parts.append(f'   上一章结尾原文："{ending_text}"')
        if scene.get("location"):
            parts.append(f'   当前场景：{scene["location"]}，时间：{scene.get("time", "未指定")}，氛围：{scene.get("atmosphere", "未指定")}')

    # 规则 2: 角色状态承接
    if intensity.get("require_state_continuity", True):
        character_states = prev_hooks.get("character_states", [])
        if character_states:
            parts.append(f"2. 必须承接以下角色在第{prev_idx}章结尾的状态：")
            for cs in character_states[:3]:
                status = cs.get("status", "")
                emotion = cs.get("emotion", "")
                name = cs.get("name", "角色")
                desc_parts = []
                if status:
                    desc_parts.append(f"状态：{status}")
                if emotion:
                    desc_parts.append(f"情绪：{emotion}")
                if desc_parts:
                    parts.append(f"   - {name}：{'，'.join(desc_parts)}")
        else:
            parts.append(f"2. 角色状态必须与第{prev_idx}章结尾保持一致，不得突然改变情绪或立场。")

    # 规则 3: 张力点回应
    tension_points = prev_hooks.get("tension_points", [])
    if tension_points:
        parts.append(f"3. 必须回应第{prev_idx}章结尾留下的悬念/张力：")
        for tp in tension_points[:intensity.get("instruction_count", 3)]:
            text = tp.get("text", str(tp)) if isinstance(tp, dict) else str(tp)
            parts.append(f"   - {text}")

    # 规则 4: 未解决情节推进
    plot_nodes = prev_hooks.get("plot_nodes", [])
    if plot_nodes:
        parts.append(f"4. 以下未解决的情节必须在本章推进或提及：")
        for pn in plot_nodes[:2]:
            text = pn.get("text", str(pn)) if isinstance(pn, dict) else str(pn)
            parts.append(f"   - {text}")

    # 规则 5: 新章结尾要求
    parts.append(f"5. 本章结尾必须再次留下新的张力点，为第{next_chapter_idx + 1}章留出悬念。")

    # 严格度补充
    strictness = intensity.get("strictness", "medium")
    if strictness == "hard":
        parts.append("")
        parts.append("⚠️ 以上要求为硬约束，违反任何一条都将导致章节质量不合格。")
    elif strictness == "soft":
        parts.append("")
        parts.append("提示：以上为衔接建议，可在保持连续性的前提下适当灵活处理。")

    if style_preference:
        parts.append(f"\n【表达偏好】{style_preference}")

    return "\n".join(parts)


def _empty_hooks() -> Dict[str, Any]:
    """返回空的钩子数据结构"""
    return {
        "ending_text": "",
        "scene": {"location": "", "time": "", "atmosphere": ""},
        "character_states": [],
        "plot_nodes": [],
        "tension_points": [],
    }


async def save_continuity_to_db(
    novel_id: str,
    chapter_idx: int,
    chapter_title: str,
    hooks: Dict[str, Any],
) -> bool:
    """将提取的钩子数据保存到 ChapterContinuityDB"""
    from ..db.database import AsyncSessionLocal
    from ..db.models import ChapterContinuityDB
    from sqlalchemy import select, and_
    from datetime import datetime
    import uuid

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ChapterContinuityDB).where(and_(
                    ChapterContinuityDB.novel_id == novel_id,
                    ChapterContinuityDB.chapter_idx == chapter_idx,
                )).limit(1)
            )
            existing = result.scalar_one_or_none()
            now = datetime.now()

            if existing:
                existing.ending_text = hooks.get("ending_text", "")
                existing.scene = hooks.get("scene", {})
                existing.character_states = hooks.get("character_states", [])
                existing.unresolved = hooks.get("plot_nodes", [])
                existing.tension_points = hooks.get("tension_points", [])
                existing.updated_at = now
            else:
                c = ChapterContinuityDB(
                    id=str(uuid.uuid4()),
                    novel_id=novel_id,
                    chapter_idx=chapter_idx,
                    chapter_title=chapter_title,
                    ending_text=hooks.get("ending_text", ""),
                    scene=hooks.get("scene", {}),
                    character_states=hooks.get("character_states", []),
                    unresolved=hooks.get("plot_nodes", []),
                    tension_points=hooks.get("tension_points", []),
                    continuity_score=7,
                    created_at=now,
                    updated_at=now,
                )
                session.add(c)
            await session.commit()
            logger.info("已保存第%d章衔接钩子到DB", chapter_idx)
            return True
    except Exception as e:
        logger.error("保存衔接钩子失败: %s", e)
        return False


async def load_continuity_from_db(
    novel_id: str,
    chapter_idx: int,
) -> Optional[Dict[str, Any]]:
    """从 DB 加载指定章节的衔接钩子"""
    from ..db.database import AsyncSessionLocal
    from ..db.models import ChapterContinuityDB
    from sqlalchemy import select, and_

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ChapterContinuityDB).where(and_(
                    ChapterContinuityDB.novel_id == novel_id,
                    ChapterContinuityDB.chapter_idx == chapter_idx,
                )).limit(1)
            )
            c = result.scalar_one_or_none()
            if not c:
                return None
            return {
                "ending_text": c.ending_text or "",
                "scene": c.scene or {},
                "character_states": c.character_states or [],
                "plot_nodes": c.unresolved or [],
                "tension_points": c.tension_points or [],
                "continuity_score": c.continuity_score,
            }
    except Exception as e:
        logger.error("加载衔接钩子失败: %s", e)
        return None