"""End-to-end test of the orchestrator with 6-Skill pipeline."""
import asyncio
import sys
import time

# Windows event loop policy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.backend.core.orchestrator import NovelOrchestrator


async def main():
    print("=" * 60)
    print("  端到端编排测试 - 6-Skill 方案A")
    print("=" * 60)

    # Create orchestrator
    orch = NovelOrchestrator(
        title="测试小说 - 异世觉醒",
        theme="玄幻/异世",
        tone="热血、冒险",
        chapter_count=3,
        platform="小说平台",
        novel_id="test_001",
    )

    # Progress callback
    events = []
    async def on_progress(event, data):
        events.append((event, time.time()))
        if event in ("stage_done", "run_all_done", "chapter_done"):
            print(f"  ? {event}: {data.get('stage', '') or data.get('total', '') or data.get('index', '')}")

    orch._progress_callback = on_progress

    print(f"\n[配置] 章节数: 3, Provider: mock")
    print(f"[启动] 执行全流程编排 (planning -> worldbuilding -> characters -> opening_hook -> style -> outlining -> drafting -> editing -> review)")
    print("-" * 60)

    start_time = time.time()
    result = await orch.run_all()
    elapsed = time.time() - start_time

    print("-" * 60)
    print(f"\n[完成] 总耗时: {elapsed:.2f}s")
    print(f"  状态: {result.get('success', False)}")
    print(f"  阶段结果:")
    for stage, data in result.get("results", {}).items():
        if stage.startswith("__"):
            continue
        ok = "?" if data.get("success") else "?"
        mock_note = "[mock]" if data.get("__mock__") else ""
        print(f"    {ok} {stage:20s} {mock_note}")

    # Verify chapters
    chapters = orch.state.chapters
    print(f"\n  生成章节数: {len(chapters)}")
    for i, ch in enumerate(chapters):
        wc = ch.get("word_count", 0)
        status = ch.get("status", "")
        preview = ch.get("content", "")[:60].replace("\n", " ")
        print(f"    第{i+1}章: {ch.get('title', '')} | {wc}字 | [{status}] | {preview}...")

    # Final verdict
    status = result.get("results", {}).get("__status__", "")
    if status == "completed" and result.get("success") and len(chapters) >= 3:
        print(f"\n? 测试通过！编排流程完整执行，共生成 {len(chapters)} 章")
        return 0
    else:
        print(f"\n? 测试未完全通过 (状态: {status}, 章节数: {len(chapters)})")
        return 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
