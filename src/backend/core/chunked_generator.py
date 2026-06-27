"""
分块生成器 — 解决大上下文 prompt 导致的输出截断问题

核心思路：
1. 动态计算 max_tokens：根据上下文长度和目标字数自动计算
2. 分块生成：将长章节拆分为多个 chunk 依次生成，每块 2000 字
3. 流式聚合：分块流式输出时聚合 token 并推送

适用场景：
- 章节正文生成（8-Agent 协同写作管道的 Draft Agent）
- 需要输出 2000-3000+ 字长文本的任何场景
"""
import asyncio
from typing import Any, Callable, Dict, List, Optional

from ..llm.client import LLMClient, LLMMessage


def calculate_optimal_max_tokens(context_length: int, target_words: int = 3000) -> int:
    """
    根据上下文长度和目标字数计算最优 max_tokens。

    中文估算公式：
      - 1 个中文字 ≈ 1.5-2 个 token（含 BPE 开销）
      - LLM 生成时通常有 20-30% 的 over-generation
      - 预留 15% 的 safety margin（确保结尾不被截断）

    公式：target_words * 3.0 * 1.3 (over-gen) * 1.15 (margin) ≈ target_words * 4.5
    最低 10000（保证有足够空间完成章节结尾）。
    """
    # 基础估算：每个中文字需要 2.5-3.0 个 token，加结尾安全余量
    base_tokens = int(target_words * 3.2)

    # 上下文越长，需要越大的 max_tokens（上下文占用了响应空间的预算）
    context_penalty = int(context_length * 0.12)

    # 综合计算，增加结尾安全余量
    optimal = max(10000, base_tokens + context_penalty + 1500)

    # 上限保护（防止单个 API 调用过大）
    return min(optimal, 40000)


async def chunked_generate_stream(
    client: LLMClient,
    messages: List[LLMMessage],
    system_prompt: str,
    temperature: float,
    target_words: int = 3000,
    chunk_size: int = 2500,
    emit: Optional[Callable] = None,
    chapter_idx: int = 0,
) -> str:
    """
    流式分块生成。每块约 chunk_size 字，依次生成并拼接。

    每块的 prompt 包含前面块的输出作为上下文，确保连贯性。
    最后一块特别要求写出完整的章节结尾。
    """
    full_text = ""
    chunks = []
    current_messages = list(messages)

    # 估算需要多少块
    estimated_chunks = max(1, (target_words + chunk_size - 1) // chunk_size)

    for chunk_idx in range(estimated_chunks):
        is_last_chunk = (chunk_idx == estimated_chunks - 1)

        # 如果不是第一块，追加前面输出到消息中作为上下文
        if chunk_idx > 0:
            if is_last_chunk:
                context_msg = (
                    f"（接续上文，以下是之前的内容。请继续写并完成本章结尾：\n"
                    f"1. 自然过渡到本章的高潮和收束\n"
                    f"2. 在结尾留下悬念或下一章钩子（伏笔、疑问、突发变故等）\n"
                    f"3. 不要重复前文，不要总结，直接继续情节\n\n"
                    f"前文内容：\n{full_text[-chunk_size * 2:]}）"
                )
            else:
                context_msg = (
                    f"（接续上文，以下是之前的内容。请继续写，不要重复，不要总结，直接继续情节：\n\n{full_text[-chunk_size * 2:]}）"
                )
            current_messages.append(LLMMessage(role="user", content=context_msg))

        # 动态计算当前块的 max_tokens
        ctx_len = sum(len(m.content) if hasattr(m, "content") else len(str(m)) for m in current_messages)
        remaining_target = max(chunk_size, target_words - len(full_text))
        current_max_tokens = calculate_optimal_max_tokens(ctx_len, remaining_target)

        # 流式生成当前块
        chunk_full_text = ""
        try:
            async for token_chunk in client.generate_stream(
                current_messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=current_max_tokens,
            ):
                if token_chunk.get("type") == "token":
                    chunk_full_text += token_chunk["content"]
                    full_text += token_chunk["content"]

                    # 推送流式 token（所有块都推送，确保实时性）
                    if emit:
                        await emit("chapter_token", {
                            "index": chapter_idx,
                            "token": token_chunk["content"],
                            "partial": full_text,
                        })

                elif token_chunk.get("type") == "done":
                    break

        except Exception as e:
            print(f"[ChunkedGenerator] 第 {chunk_idx + 1} 块流式生成失败: {e}，回退到非流式")
            # 回退到非流式生成
            result = await client.generate(
                current_messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=current_max_tokens,
            )
            chunk_full_text = result.content if hasattr(result, "content") else str(result)
            full_text += chunk_full_text

        chunks.append(chunk_full_text)

        # 如果已经足够长，提前结束
        if len(full_text) >= target_words * 1.1:
            break

    # 推送最终结果
    if emit:
        await emit("chapter_token", {
            "index": chapter_idx,
            "token": "",
            "partial": full_text,
            "final": True,
        })

    return full_text


async def chunked_generate(
    client: LLMClient,
    messages: List[LLMMessage],
    system_prompt: str,
    temperature: float,
    target_words: int = 3000,
    chunk_size: int = 2500,
) -> str:
    """
    非流式分块生成。适用于不需要实时推送的场景。
    """
    full_text = ""
    chunks = []
    current_messages = list(messages)

    estimated_chunks = max(1, (target_words + chunk_size - 1) // chunk_size)

    for chunk_idx in range(estimated_chunks):
        is_last_chunk = (chunk_idx == estimated_chunks - 1)

        if chunk_idx > 0:
            if is_last_chunk:
                context_msg = (
                    f"（接续上文，请继续写并完成本章结尾：\n"
                    f"1. 自然过渡到本章的高潮和收束\n"
                    f"2. 在结尾留下悬念或下一章钩子\n"
                    f"3. 不要重复前文，不要总结\n\n"
                    f"前文内容：\n{full_text[-chunk_size * 2:]}）"
                )
            else:
                context_msg = (
                    f"（接续上文：\n\n{full_text[-chunk_size * 2:]}）"
                )
            current_messages.append(LLMMessage(role="user", content=context_msg))

        ctx_len = sum(len(m.content) if hasattr(m, "content") else len(str(m)) for m in current_messages)
        remaining_target = max(chunk_size, target_words - len(full_text))
        current_max_tokens = calculate_optimal_max_tokens(ctx_len, remaining_target)

        try:
            result = await client.generate(
                current_messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=current_max_tokens,
            )
            chunk_text = result.content if hasattr(result, "content") else str(result)
            full_text += chunk_text
            chunks.append(chunk_text)
        except Exception as e:
            print(f"[ChunkedGenerator] 第 {chunk_idx + 1} 块生成失败: {e}")
            chunks.append(f"[第 {chunk_idx + 1} 块生成失败]")
            continue

        if len(full_text) >= target_words * 1.1:
            break

    return full_text
