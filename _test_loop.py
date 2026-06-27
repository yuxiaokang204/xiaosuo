"""End-to-end test of the 6-Skill LOOP architecture."""
import asyncio
import sys
import time

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.backend.core.orchestrator import NovelOrchestrator, SkillLoopConfig


async def test_loop_config():
    """Test SkillLoopConfig depth and temperature profiles."""
    print("--- Test: SkillLoopConfig ---")
    cfg = SkillLoopConfig()
    assert cfg.depth_for_loop(0) == "SKELETON", f"Expected SKELETON got {cfg.depth_for_loop(0)}"
    assert cfg.depth_for_loop(1) == "DETAIL"
    assert cfg.depth_for_loop(2) == "POLISH"
    assert cfg.depth_for_loop(3) == "REFINE"
    temp_0 = cfg.temperature_for_loop(0)
    temp_2 = cfg.temperature_for_loop(2)
    assert temp_0 > temp_2, f"Expected decreasing temp, got {temp_0} -> {temp_2}"
    print(f"  ? Depth levels OK. temp(0)={temp_0}, temp(2)={temp_2}")


async def test_full_loop_3_iterations():
    """Test 3 main loops: SKELETON -> DETAIL -> POLISH."""
    print("\n" + "=" * 60)
    print("  Test: 3-Loop 完整编排")
    print("=" * 60)

    orch = NovelOrchestrator(
        title="Loop测试小说",
        theme="玄幻冒险",
        tone="热血",
        chapter_count=5,
        platform="番茄",
    )

    events = []
    async def on_progress(event, data):
        events.append(event)

    orch._progress_callback = on_progress

    result = await orch.run_all_loop(max_loops=3)

    # 验证结果
    assert result.get("success"), "Loop should return success=True"
    assert result.get("mode") == "loop", f"Expected mode='loop', got '{result.get('mode')}'"
    assert result.get("total_loops") == 3, f"Expected 3 loops, got {result.get('total_loops')}"

    # 验证章节
    chapter_count = len(orch.state.chapters)
    print(f"\n  ? 生成章节数: {chapter_count}")
    assert chapter_count >= 5, f"Expected >=5 chapters, got {chapter_count}"

    for i, ch in enumerate(orch.state.chapters):
        wc = ch.get("word_count", 0)
        status = ch.get("status", "")
        content_len = len(ch.get("content", ""))
        print(f"    Chapter {i+1}: {wc}字, [{status}], content={content_len}")
        assert content_len > 0, f"Chapter {i+1} has empty content!"

    # 验证状态
    state = result.get("state", {})
    print(f"\n  ? 状态元数据:")
    print(f"    current_loop={state.get('current_loop')}")
    print(f"    loops_completed={state.get('loops_completed')}")
    print(f"    depth_level={state.get('depth_level')}")
    print(f"    errors={len(orch.state.errors)}")

    # 验证事件流
    loop_events = [e for e in events if "loop" in e.lower()]
    print(f"  ? Loop相关事件数: {len(loop_events)}")
    print(f"  ? 总事件数: {len(events)}")

    assert len(orch.state.errors) == 0, f"Unexpected errors: {orch.state.errors}"

    return True


async def test_chapter_pipeline_loop_aware():
    """Test ChapterPipeline with different loop_metadata."""
    print("\n" + "=" * 60)
    print("  Test: ChapterPipeline 深度感知")
    print("=" * 60)

    from src.backend.core.chapter_pipeline import ChapterPipeline

    # async emit function
    async def async_emit(*args, **kwargs):
        pass

    # 测试不同深度
    for depth in [0, 1, 2]:
        pipeline = ChapterPipeline(agents={}, emit=async_emit)
        loop_metadata = {"loop": depth, "depth": SkillLoopConfig().depth_for_loop(depth),
                         "depth_level": depth}
        print(f"\n  Depth {depth}: {loop_metadata['depth']}")
        result = await pipeline.run(
            chapter_idx=1,
            title="测试章节",
            summary="测试概要",
            context={
                "title": "测试小说",
                "theme": "玄幻",
                "world": "现代都市背景",
                "characters": "主角: 林风",
                "style": "快节奏",
            },
            loop_metadata=loop_metadata,
        )
        print(f"    标题: {result.title}")
        print(f"    字数: {result.word_count}")
        print(f"    评分: {result.overall_score}")
        assert result.content and len(result.content) > 0

    print("\n  ? ChapterPipeline深度感知测试通过")
    return True


async def main():
    start = time.time()

    print("=" * 60)
    print(" 6-Skill LOOP 架构 端到端测试")
    print("=" * 60)

    # Test 1
    await test_loop_config()

    # Test 2
    result2 = await test_full_loop_3_iterations()
    if result2:
        print("\n? 3-Loop编排测试通过")

    # Test 3
    result3 = await test_chapter_pipeline_loop_aware()
    if result3:
        print("\n? ChapterPipeline深度感知测试通过")

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f" ? 全部测试完成，耗时 {elapsed:.2f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
