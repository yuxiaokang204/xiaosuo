"""
回归测试 — 针对 2026-06 审计修复的缺陷，使用真实 assert（区别于 test_project.py 的 try/except 吞异常）。

运行:
    python test_regression.py
全部通过时退出码为 0；任一 assert 失败立即抛出并以非 0 退出。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASSED = []


def check(name, fn):
    fn()
    PASSED.append(name)
    print(f"  ✅ {name}")


# ────────────────────────────────────────────────────────────
# 1. global_summary 情节阶段判断（旧 bug：'发展'阶段永不可达，7 章即误判'收束'）
# ────────────────────────────────────────────────────────────
def test_plot_progress_phases():
    from src.backend.core.global_summary import GlobalSummary

    gs = GlobalSummary()
    gs.set_target_chapters(10)
    for i in range(1, 11):
        gs.add_chapter_summary(chapter=i, title=f"第{i}章", summary="x")
        phase = gs.get_plot_progress()["phase"]
        # 旧实现下 i>=3 永远不可能是"发展"；这里断言它至少在前期可达
        if i == 3:
            assert phase == "发展", f"第3章应为'发展'，实际 {phase}"
        if i == 7:
            assert phase in ("高潮",), f"10章计划下第7章应为'高潮'而非过早'收束'，实际 {phase}"
        if i == 10:
            assert phase == "收束", f"最后一章应为'收束'，实际 {phase}"

    # 无目标章节数时也不应崩溃，且'发展'可达
    gs2 = GlobalSummary()
    for i in range(1, 4):
        gs2.add_chapter_summary(chapter=i, title=f"第{i}章", summary="x")
    assert gs2.get_plot_progress()["phase"] == "发展", "无目标时前期应为'发展'"


# ────────────────────────────────────────────────────────────
# 2. learning_engine 偏好去重（旧 bug：重复反馈被 random.choice 概率放大）
# ────────────────────────────────────────────────────────────
def test_learning_dedup():
    from src.backend.core.learning_engine import LearningEngine
    from src.backend.models.schemas import UserFeedback, FeedbackType

    eng = LearningEngine()
    for _ in range(5):
        eng.learn_from_feedback(UserFeedback(
            feedback_type=FeedbackType.STYLE_EDIT,
            before_text="忽然", after_text="骤然",
        ))
    prefs = eng.word_preferences["忽然"]
    assert prefs.count("骤然") == 1, f"重复反馈不应堆叠，实际 {prefs}"

    # 负反馈也应去重
    for _ in range(3):
        eng.learn_from_feedback(UserFeedback(
            feedback_type=FeedbackType.DELETION, before_text="这是AI腔",
        ))
    matches = [p for p in eng.anti_ai_patterns if p["pattern"] == "这是AI腔"]
    assert len(matches) == 1, f"负反模式应去重，实际 {len(matches)}"


# ────────────────────────────────────────────────────────────
# 3. memory 短期记忆有界 + token 估算统一
# ────────────────────────────────────────────────────────────
def test_memory_bounds_and_tokens():
    from src.backend.core import memory as mem_mod
    from src.backend.core.memory import NovelMemory, estimate_tokens

    m = NovelMemory()
    for i in range(mem_mod._SHORT_TERM_MAX + 50):
        m.update_with_chapter(title=f"第{i}章", content="内容" * 10)
    assert len(m.short_term_memory) <= mem_mod._SHORT_TERM_MAX, \
        f"短期记忆应有上限 {mem_mod._SHORT_TERM_MAX}，实际 {len(m.short_term_memory)}"

    # token 估算：中文按 ~1.5 字/token，非负且单调
    assert estimate_tokens("") == 0
    assert estimate_tokens("你好世界") > 0
    assert estimate_tokens("一" * 150) > estimate_tokens("一" * 15)


# ────────────────────────────────────────────────────────────
# 4. models 外键 / 索引（旧 bug：多个引用列为裸 Column(String)）
# ────────────────────────────────────────────────────────────
def test_models_fk_and_index():
    from src.backend.db import models as M

    def fk_targets(col):
        return {fk.column.table.name for fk in col.foreign_keys}

    # 关系目标列应有外键
    assert fk_targets(M.CharacterRelationshipDB.__table__.c.target_character_id) == {"characters"}, \
        "target_character_id 应外键到 characters"
    # 自引用父章节
    assert fk_targets(M.ChapterDB.__table__.c.parent_chapter_id) == {"chapters"}, \
        "parent_chapter_id 应自引用 chapters"
    # 用户反馈关联小说/章节
    assert fk_targets(M.UserFeedbackDB.__table__.c.novel_id) == {"novels"}
    # 关键查询列应建索引
    assert M.NovelDB.__table__.c.status.index is True, "novels.status 应建索引"
    assert M.ChapterDB.__table__.c.status.index is True, "chapters.status 应建索引"
    assert M.UserFeedbackDB.__table__.c.feedback_type.index is True, "feedback_type 应建索引"


# ────────────────────────────────────────────────────────────
# 5. database：SQL echo 默认关闭（由 SQL_ECHO 控制）
# ────────────────────────────────────────────────────────────
def test_sql_echo_default_off():
    # 默认环境（未设置 SQL_ECHO）下 engine.echo 应为 False
    import importlib
    from src.backend.db import database as db_mod
    importlib.reload(db_mod)
    assert db_mod.engine.echo is False, "默认应关闭 SQL echo（设 SQL_ECHO=true 才开启）"


def main():
    print("运行回归测试...\n")
    tests = [
        ("情节阶段判断修复", test_plot_progress_phases),
        ("学习引擎偏好去重", test_learning_dedup),
        ("记忆有界 + token 统一", test_memory_bounds_and_tokens),
        ("模型外键/索引", test_models_fk_and_index),
        ("SQL echo 默认关闭", test_sql_echo_default_off),
    ]
    for name, fn in tests:
        check(name, fn)
    print(f"\n全部通过：{len(PASSED)}/{len(tests)}")


if __name__ == "__main__":
    main()
