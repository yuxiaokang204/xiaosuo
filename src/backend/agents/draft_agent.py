"""
DraftAgent - 专业写手Skill
根据大纲和上下文创作章节正文，支持流式输出
"""
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from .base import BaseAgent
from .prompts import (
    DRAFT_SYSTEM_PROMPT,
    build_draft_user_prompt,
    build_draft_system_prompt,
    sanitize_chapter_content,
)

logger = logging.getLogger(__name__)


class DraftAgent(BaseAgent):
    """
    DraftAgent - 章节内容生成Agent（专业写手）
    
    职责：
    - 根据章节大纲、世界观、角色设定生成完整章节内容
    - 支持流式输出（yield），便于实时推送到前端
    - 自动清洗元标签和AI味表达
    - 平台适配（番茄/飞卢/起点/七猫/书旗）
    """

    AGENT_ID = "draft"
    CAPABILITIES = ["writing", "draft"]
    EXPECTS_JSON = False  # 返回纯文本内容

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行章节内容生成
        
        Args:
            context: 包含以下字段的上下文:
                - chapter_title: 章节标题
                - chapter_outline: 章节大纲
                - summaries: 前文摘要
                - characters: 角色设定
                - world: 世界观设定
                - context_clues: 线索/伏笔
                - style_guide: 文风指南
                - ending_hook_type: 结尾类型
                - platform: 目标平台（默认"番茄"）
                - theme: 故事主题
                - depth_level: 深度级别（0=SKELETON, 1=DETAIL, 2+=POLISH）
                
        Returns:
            {
                "success": True,
                "chapter_title": "...",
                "content": "生成的章节内容...",
                "word_count": 3000,
                "platform": "番茄",
                "provider": "...",
                "latency_ms": 1234,
                "fallback": False,
            }
        """
        chapter_title = str(context.get("chapter_title", "未命名章节"))
        chapter_outline = str(context.get("chapter_outline", ""))
        summaries = str(context.get("summaries", ""))
        characters = str(context.get("characters", ""))
        world = str(context.get("world", ""))
        context_clues = str(context.get("context_clues", ""))
        foreshadowing = str(context.get("foreshadowing", ""))
        style_guide = str(context.get("style_guide", ""))
        ending_hook_type = str(context.get("ending_hook_type", ""))
        platform = str(context.get("platform", "番茄"))
        theme = str(context.get("theme", ""))
        title = str(context.get("title", ""))
        genre = str(context.get("genre", ""))
        tone = str(context.get("tone", ""))
        depth_level = int(context.get("depth_level", 1))

        # 合并 context_clues 和 foreshadowing（兼容旧接口）
        combined_clues = context_clues or foreshadowing

        # 构建动态 System Prompt（根据 depth_level）
        system_prompt = build_draft_system_prompt(depth_level)

        user_prompt = build_draft_user_prompt(
            chapter_title=chapter_title,
            chapter_outline=chapter_outline,
            context_summaries=summaries,
            characters_info=characters,
            world_info=world,
            context_clues=combined_clues,
            style_guide=style_guide,
            ending_hook_type=ending_hook_type,
            platform=platform,
            depth_level=depth_level,
            title=title,
            genre=genre,
            tone=tone,
        )

        logger.info(f"[DraftAgent] 开始生成章节: {chapter_title} (platform={platform}, depth={depth_level})")

        # 调用 LLM（非流式，返回完整内容）
        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expects_json=False,
            max_tokens=8000,
        )

        content = result.get("content", "")
        # 清洗内容：移除元标签、修复AI味表达
        content = sanitize_chapter_content(content)

        logger.info(f"[DraftAgent] 章节生成完成: {chapter_title}, "
                     f"字数={len(content)}, provider={result.get('provider', 'unknown')}")

        return {
            "success": True,
            "chapter_title": chapter_title,
            "content": content,
            "word_count": len(content),
            "platform": platform,
            "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"),
            "fallback": result.get("fallback", False),
        }

    async def execute_stream(self, context: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式生成章节内容
        
        以生成器方式逐块返回内容，前端可以实时显示。
        
        Yields:
            {"type": "chunk", "content": "部分内容..."}
            {"type": "done", "content": "完整内容", "word_count": 3000}
            {"type": "error", "error": "错误信息"}
        """
        chapter_title = str(context.get("chapter_title", "未命名章节"))
        chapter_outline = str(context.get("chapter_outline", ""))
        summaries = str(context.get("summaries", ""))
        characters = str(context.get("characters", ""))
        world = str(context.get("world", ""))
        context_clues = str(context.get("context_clues", ""))
        style_guide = str(context.get("style_guide", ""))
        ending_hook_type = str(context.get("ending_hook_type", ""))
        platform = str(context.get("platform", "番茄"))
        theme = str(context.get("theme", ""))
        depth_level = int(context.get("depth_level", 1))

        combined_clues = context_clues or ""

        system_prompt = build_draft_system_prompt(depth_level)

        user_prompt = build_draft_user_prompt(
            chapter_title=chapter_title,
            chapter_outline=chapter_outline,
            context_summaries=summaries,
            characters_info=characters,
            world_info=world,
            context_clues=combined_clues,
            style_guide=style_guide,
            ending_hook_type=ending_hook_type,
            platform=platform,
            depth_level=depth_level,
        )

        logger.info(f"[DraftAgent] 开始流式生成章节: {chapter_title}")

        full_content = ""
        try:
            # 使用 LLM Gateway 的流式接口
            from ..llm.gateway import get_gateway, LLMMessage

            gateway = get_gateway()
            messages = [LLMMessage(role="user", content=user_prompt)]

            async for chunk in gateway.generate_stream(
                messages=messages,
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=8000,
                system_prompt=system_prompt,
            ):
                if chunk.get("type") == "error":
                    error_msg = chunk.get("error", "流式生成失败")
                    logger.error(f"[DraftAgent] 流式生成错误: {error_msg}")
                    yield {
                        "type": "error",
                        "error": error_msg,
                        "partial_content": full_content,
                    }
                    return

                text = chunk.get("content", "")
                if text:
                    full_content += text
                    # 清洗后返回
                    cleaned = sanitize_chapter_content(text)
                    yield {
                        "type": "chunk",
                        "content": cleaned,
                        "word_count": len(full_content),
                    }

            # 最终完成
            final_content = sanitize_chapter_content(full_content)
            yield {
                "type": "done",
                "content": final_content,
                "word_count": len(final_content),
                "chapter_title": chapter_title,
                "platform": platform,
                "fallback": False,
            }

        except Exception as e:
            import traceback
            logger.error(f"[DraftAgent] 流式生成异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            yield {
                "type": "error",
                "error": f"{type(e).__name__}: {e}",
                "partial_content": sanitize_chapter_content(full_content),
            }

    def _mock_fallback(self, user_prompt: str) -> Dict[str, Any]:
        """JSON解析失败时的兜底数据"""
        return {
            "note": "mock_fallback",
            "content": "（本章内容生成异常，使用占位文本）\n" + (user_prompt[:200] if user_prompt else ""),
            "word_count": 0,
        }
