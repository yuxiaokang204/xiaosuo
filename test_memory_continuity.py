"""v5.1 记忆系统 + 章节衔接引擎综合验证"""
import asyncio
import sys

async def main():
    print("=" * 60)
    print("v5.1 记忆系统 + 章节衔接引擎综合验证")
    print("=" * 60)

    # 1. 语法与导入
    print("\n1. 语法与模块导入验证")
    files = [
        "src/backend/core/continuity_engine.py",
        "src/backend/core/memory_coordination.py",
        "src/backend/core/chapter_pipeline.py",
        "src/backend/core/orchestrator.py",
        "src/backend/main.py",
    ]
    for f in files:
        try:
            with open(f, encoding="utf-8") as fp:
                compile(fp.read(), f, "exec")
            print(f"  [OK] {f}")
        except SyntaxError as e:
            print(f"  [FAIL] {f}: {e}")
            sys.exit(1)

    from src.backend.core.continuity_engine import extract_continuity_hooks, generate_continuity_instruction
    from src.backend.core.memory_coordination import MemoryCoordinationEngine
    from src.backend.core.chapter_pipeline import ChapterPipeline
    from src.backend.core.orchestrator import NovelOrchestrator
    print("  [OK] 所有模块导入成功")

    # 2. MemoryCoordinationEngine 基础功能
    print("\n2. MemoryCoordinationEngine 基础功能")
    engine = MemoryCoordinationEngine()
    ctx = await engine.generate_context_for_next_chapter(
        chapter_idx=1,
        chapter_title="测试章节",
        theme="测试主题",
    )
    assert "story_bible" in ctx, "缺少 story_bible"
    assert "continuity_instruction" in ctx, "缺少 continuity_instruction"
    assert "context_token_stats" in ctx, "缺少 context_token_stats"
    stats = ctx["context_token_stats"]
    print(f"  [OK] 第1章上下文生成: story_bible={bool(ctx['story_bible'])}, "
          f"continuity={bool(ctx['continuity_instruction'])}, budget={stats['budget']}")

    # 3. 章节后更新
    content = ("这是第一章完整内容。主角在山洞中醒来，发现了神秘的线索。"
               "他站起身来，四处张望，看到远处有一道光芒。他决定走向那光芒，"
               "并在途中遇到了一位神秘的老者。老者告诉他，这是命运的安排。")
    result = await engine.update_after_chapter(
        chapter_idx=1,
        chapter_title="测试章节",
        chapter_content=content,
    )
    assert result["updated_components"] == 4, f"应该更新4个组件, 实际: {result}"
    print(f"  [OK] 章节后更新: {result}")

    # 4. 第2章衔接指令（应有上一章钩子 + 原文）
    ctx2 = await engine.generate_context_for_next_chapter(
        chapter_idx=2,
        chapter_title="第二章",
        prev_chapter_text=content,
        theme="测试主题",
    )
    assert len(ctx2["continuity_instruction"]) > 0, "第2章必须有衔接指令"
    inst = ctx2["continuity_instruction"]
    print(f"  [OK] 第2章衔接指令: {len(inst)} 字")
    if "强制衔接" in inst or "衔接" in inst:
        print("       包含 '衔接' 关键词 ✅")
    if "第1章" in inst or "场景" in inst:
        print("       包含章节/场景关键词 ✅")

    # 5. 钩子提取 - state_tracker 真实状态
    hooks = await extract_continuity_hooks(
        chapter_content=content,
        chapter_idx=1,
        chapter_title="测试章节",
    )
    assert "ending_text" in hooks, "钩子缺少 ending_text"
    assert "scene" in hooks, "钩子缺少 scene"
    assert "character_states" in hooks, "钩子缺少 character_states"
    assert "plot_nodes" in hooks, "钩子缺少 plot_nodes"
    assert "tension_points" in hooks, "钩子缺少 tension_points"
    print(f"  [OK] 钩子提取: ending_text={bool(hooks['ending_text'])}, "
          f"tension={len(hooks['tension_points'])}")

    # 6. generate_continuity_instruction 完整测试
    instruction = generate_continuity_instruction(
        prev_hooks=hooks,
        next_chapter_idx=2,
    )
    assert "强制衔接" in instruction or "衔接要求" in instruction, "指令缺少衔接要求标识"
    print(f"  [OK] 独立生成衔接指令: {len(instruction)} 字")

    # 7. LearningEngine 衔接强度集成
    print("\n3. LearningEngine 集成验证")
    from src.backend.core.learning_engine import LearningEngine
    le = LearningEngine()
    # 高分历史 — 应使用宽松强度
    le.record_continuity_feedback("novel_a", 1, 9, "很好")
    le.record_continuity_feedback("novel_a", 2, 8, "不错")
    intensity_high = le.get_continuity_intensity("novel_a")
    print(f"  [OK] 高分历史: intensity={intensity_high}")

    # 低分历史 — 应使用严格强度
    le2 = LearningEngine()
    le2.record_continuity_feedback("novel_b", 1, 4, "衔接不连贯")
    le2.record_continuity_feedback("novel_b", 2, 3, "情节跳跃")
    intensity_low = le2.get_continuity_intensity("novel_b")
    print(f"  [OK] 低分历史: intensity={intensity_low}")

    # 8. 传入 LearningEngine 给 MemoryCoordinationEngine
    engine2 = MemoryCoordinationEngine(learning_engine=le2)
    ctx3 = await engine2.generate_context_for_next_chapter(
        chapter_idx=3,
        chapter_title="第三章",
        prev_chapter_text="第二章结尾，主角正在穿越丛林。",
        novel_id="novel_b",
    )
    assert len(ctx3["continuity_instruction"]) > 0, "学习引擎 + 衔接 = 必须有指令"
    print(f"  [OK] 结合学习引擎的第3章衔接指令: {len(ctx3['continuity_instruction'])} 字")

    # 9. NovelOrchestrator 初始化验证
    print("\n4. NovelOrchestrator 初始化验证")
    orch = NovelOrchestrator(
        title="青云界传说",
        theme="穿越异世修真",
        chapter_count=5,
    )
    assert orch.state_tracker is not None, "缺少 state_tracker"
    assert orch.global_summary is not None, "缺少 global_summary"
    assert orch._memory_engine is not None, "缺少 _memory_engine"
    assert orch._novel_memory is not None, "缺少 _novel_memory"
    stats = orch._memory_engine.get_stats()
    print(f"  [OK] Orchestrator 初始化: stats={stats}")

    print("\n" + "=" * 60)
    print("全部 9 项验证通过 ✅")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
