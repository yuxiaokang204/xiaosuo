"""
PlotAgent - 情节分析Agent
分析当前情节状态，提供推进建议和因果链验证
"""
import logging
from typing import Any, Dict

from .base import BaseAgent
from .prompts import (
    STORY_ARCHITECT_SYSTEM_PROMPT,
    build_story_architect_user_prompt,
    build_story_architect_system_prompt,
)

logger = logging.getLogger(__name__)


class PlotAgent(BaseAgent):
    """
    PlotAgent - 情节分析Agent（故事架构师）
    
    职责：
    - 分析当前叙事状态和情节进度
    - 设计后续情节发展（因果链、张力曲线、信息释放节奏）
    - 识别未解决的悬念和伏笔
    - 提供节奏调整建议
    - 支持深度分析模式（POLISH）
    """

    AGENT_ID = "plot"
    CAPABILITIES = ["plot", "structure", "analysis"]
    EXPECTS_JSON = True

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行情节分析
        
        Args:
            context: 包含以下字段的上下文:
                - summaries: 章节摘要列表
                - characters: 当前活跃角色状态
                - theme: 故事主题
                - platform: 目标平台（默认"番茄"）
                - depth_level: 深度级别（0=SKELETON, 1=ANALYZE, 2+=POLISH）
                
        Returns:
            {
                "success": True,
                "analysis": "当前叙事状态分析...",
                "tension_curve": {...},
                "next_plot_points": [...],
                "unresolved_items": [...],
                "pacing_suggestion": "...",
                "causality_check": "...",
                "platform": "番茄",
                "provider": "...",
                "latency_ms": 1234,
                "fallback": False,
            }
        """
        summaries = str(context.get("summaries", ""))
        characters = str(context.get("characters", ""))
        theme = str(context.get("theme", ""))
        platform = str(context.get("platform", "番茄"))
        depth_level = int(context.get("depth_level", 1))

        if not summaries:
            logger.warning("[PlotAgent] 输入摘要为空")
            return {"success": False, "error": "summaries is empty"}

        # 构建动态 System Prompt
        system_prompt = build_story_architect_system_prompt(depth_level)

        user_prompt = (
            f"故事类型：{theme}\n"
            f"目标平台：{platform}\n"
            f"近期叙事摘要：\n{summaries}\n"
            f"当前活跃角色状态：{characters}\n"
            f"请分析当前叙事状态，设计后续情节发展。"
            f"关注：因果链、张力曲线、信息释放节奏。"
        )

        logger.info(f"[PlotAgent] 开始情节分析 (platform={platform}, depth={depth_level})")

        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expects_json=True,
            max_tokens=6000,
        )

        data = result.get("data") or {}

        logger.info(f"[PlotAgent] 情节分析完成: "
                     f"plot_points={len(data.get('next_plot_moves', []))}, "
                     f"provider={result.get('provider', 'unknown')}")

        return {
            "success": True,
            "analysis": data.get("current_state_analysis", ""),
            "tension_curve": data.get("tension_curve", {}),
            "next_plot_points": data.get("next_plot_moves", []),
            "unresolved_items": data.get("thread_management", {}).get("pending_reveals", []),
            "pacing_suggestion": data.get("pacing_advice", ""),
            "causality_check": data.get("causality_check", ""),
            "platform": platform,
            "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"),
            "fallback": result.get("fallback", False),
        }

    def _mock_fallback(self, _user_prompt: str) -> Dict[str, Any]:
        """JSON解析失败时的兜底数据"""
        return {
            "analysis": "当前处于故事中段，主角已完成初步成长，但主要冲突尚未解决。"
                        "读者对反派动机缺乏了解，需在接下来的章节中推进主线。",
            "tension_curve": {
                "overall": "整体张力呈上升趋势，需在高潮前保持紧张感",
                "peaks": ["高潮点1（第X章）", "高潮点2（第Y章）"],
            },
            "next_plot_points": [
                {
                    "title": "引入关键情报",
                    "description": "让主角获得关于反派计划的关键情报，推动其做出新的抉择。",
                    "foreshadowing": "情报中提到的某个人名，将在后续成为关键人物。",
                },
                {
                    "title": "重要盟友反水",
                    "description": "一个看似盟友的角色暴露自己的真实目的，增加紧张感。",
                    "foreshadowing": "其之前在对话中留下的细微破绽此刻变得合理。",
                },
            ],
            "unresolved_items": ["主角的真实身世", "反派组织幕后首领身份", "远古力量的来源"],
            "pacing_suggestion": "建议节奏紧张，对话减少，动作与决策主导。",
            "causality_check": "因果链基本完整，建议加强事件之间的直接因果关系。",
        }
