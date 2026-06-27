"""
ReviewAgent - 质量审查Agent
多维度评价章节质量，提供评分和改进建议
"""
import logging
from typing import Any, Dict

from .base import BaseAgent
from .prompts import (
    STYLE_EDITOR_SYSTEM_PROMPT,
    build_style_editor_system_prompt,
)

logger = logging.getLogger(__name__)


class ReviewAgent(BaseAgent):
    """
    ReviewAgent - 质量审查Agent
    
    职责：
    - 从7个维度对章节内容进行质量评分
    - 识别优点、问题和改进建议
    - 一致性检查（世界观、角色性格、前文细节）
    - 输出结构化评分报告
    """

    AGENT_ID = "review"
    CAPABILITIES = ["review", "analysis", "scoring"]
    EXPECTS_JSON = True

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行质量审查
        
        Args:
            context: 包含以下字段的上下文:
                - content: 待审查的章节内容
                - context: 前文概要/上下文
                - theme: 故事主题
                - platform: 目标平台（默认"番茄"）
                - depth_level: 深度级别（0=快速, 1=标准, 2+=严格）
                
        Returns:
            {
                "success": True,
                "overall_score": 7.5,
                "dimension_scores": {...},
                "strengths": ["优点1", "优点2"],
                "issues": [{"type": "...", "text": "..."}],
                "suggestions": ["建议1", "建议2"],
                "word_count": 3000,
                "platform": "番茄",
                "provider": "...",
                "latency_ms": 1234,
                "fallback": False,
            }
        """
        content = str(context.get("content", ""))
        context_summary = str(context.get("context", ""))
        theme = str(context.get("theme", ""))
        platform = str(context.get("platform", "番茄"))
        depth_level = int(context.get("depth_level", 1))

        if not content:
            logger.warning("[ReviewAgent] 输入内容为空")
            return {"success": False, "error": "content is empty"}

        # 构建动态 System Prompt
        system_prompt = build_style_editor_system_prompt(depth_level)

        user_prompt = (
            f"目标平台：{platform}\n"
            f"故事类型：{theme}\n"
            f"待审查内容：\n{content}\n"
            f"\n前文概要：{context_summary}\n"
            f"请从7个维度评分，给出改进建议。"
        )

        logger.info(f"[ReviewAgent] 开始审查章节 (platform={platform}, depth={depth_level})")

        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expects_json=True,
            max_tokens=6000,
        )

        data = result.get("data") or {}
        review = data.get("review", {})

        logger.info(f"[ReviewAgent] 审查完成: score={review.get('overall_score', 0)}, "
                     f"issues={len(review.get('issues', []))}, "
                     f"provider={result.get('provider', 'unknown')}")

        return {
            "success": True,
            "overall_score": review.get("overall_score", 7.0),
            "dimension_scores": review.get("dimension_scores", {}),
            "strengths": review.get("strengths", []),
            "issues": review.get("issues", []),
            "suggestions": review.get("suggestions", []),
            "word_count": len(content),
            "platform": platform,
            "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"),
            "fallback": result.get("fallback", False),
        }

    def _mock_fallback(self, _user_prompt: str) -> Dict[str, Any]:
        """JSON解析失败时的兜底数据"""
        return {
            "overall_score": 7.5,
            "dimension_scores": {
                "opening_impact": 7.0,
                "language_precision": 7.0,
                "paragraph_rhythm": 7.0,
                "show_dont_tell": 7.0,
                "dialogue_quality": 7.0,
                "chapter_completeness": 7.0,
                "consistency": 7.0,
            },
            "strengths": ["情节推进清晰", "人物动机合理", "语言流畅"],
            "issues": [
                {"type": "plot", "severity": "info", "text": "中段缺少紧张感", "location": ""},
                {"type": "pacing", "severity": "info", "text": "某些过渡段落略长", "location": ""},
            ],
            "suggestions": ["增加反派存在感", "缩短过渡描写"],
            "word_count": 1200,
        }
