"""
EditAgent - 文风精修师Skill
精修章节内容，检查一致性，提供编辑建议
"""
import logging
from typing import Any, Dict

from .base import BaseAgent
from .prompts import (
    STYLE_EDITOR_SYSTEM_PROMPT,
    build_style_editor_user_prompt,
    build_style_editor_system_prompt,
    sanitize_chapter_content,
)

logger = logging.getLogger(__name__)


class EditAgent(BaseAgent):
    """
    EditAgent - 章节精修Agent（文风精修师）
    
    职责：
    - 精修章节内容：语言凝练、节奏优化、AI味清除
    - 一致性检查：世界观、角色性格、前文细节
    - 提供多维度编辑建议
    - 支持深度精修模式（POLISH）
    """

    AGENT_ID = "edit"
    CAPABILITIES = ["editing", "review", "consistency"]
    EXPECTS_JSON = True  # 返回JSON格式（含edited_content + review）

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行章节精修
        
        Args:
            context: 包含以下字段的上下文:
                - content: 待精修的章节内容
                - instructions: 编辑指令/重点方向
                - theme: 故事主题
                - platform: 目标平台（默认"番茄"）
                - context_summary: 前文概要（用于一致性检查）
                - depth_level: 深度级别（0=SKELETON, 1=EDIT, 2+=POLISH）
                
        Returns:
            {
                "success": True,
                "original": "...",
                "edited": "精修后的内容...",
                "changes_count": 100,
                "review": {...},  # 多维度评分
                "platform": "番茄",
                "provider": "...",
                "latency_ms": 1234,
                "fallback": False,
            }
        """
        original_content = str(context.get("content", ""))
        instructions = str(context.get("instructions", ""))
        theme = str(context.get("theme", ""))
        platform = str(context.get("platform", "番茄"))
        context_summary = str(context.get("context_summary", ""))
        depth_level = int(context.get("depth_level", 1))

        if not original_content:
            logger.warning("[EditAgent] 输入内容为空")
            return {"success": False, "error": "content is empty"}

        # 构建动态 System Prompt
        system_prompt = build_style_editor_system_prompt(depth_level)

        user_prompt = build_style_editor_user_prompt(
            content=original_content,
            theme=theme,
            platform=platform,
            context_summary=context_summary,
            edit_focus=instructions,
            depth_level=depth_level,
        )

        logger.info(f"[EditAgent] 开始精修章节 (platform={platform}, depth={depth_level})")

        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expects_json=True,
            max_tokens=8000,
        )

        data = result.get("data") or {}
        edited_content = data.get("edited_content", original_content)
        # 清洗内容
        edited_content = sanitize_chapter_content(edited_content)
        review = data.get("review", {})

        changes_count = abs(len(edited_content) - len(original_content))

        logger.info(f"[EditAgent] 精修完成: changes={changes_count}, "
                     f"score={review.get('overall_score', 0)}, provider={result.get('provider', 'unknown')}")

        return {
            "success": True,
            "original": original_content,
            "edited": edited_content,
            "changes_count": changes_count,
            "review": review,
            "platform": platform,
            "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"),
            "fallback": result.get("fallback", False),
        }

    def _mock_fallback(self, user_prompt: str) -> Dict[str, Any]:
        """JSON解析失败时的兜底数据"""
        return {
            "edited_content": "（精修异常，使用原文本）",
            "review": {
                "overall_score": 7.0,
                "dimension_scores": {},
                "strengths": [],
                "issues": [],
                "suggestions": ["内容生成异常，建议使用原文本"],
            },
        }
