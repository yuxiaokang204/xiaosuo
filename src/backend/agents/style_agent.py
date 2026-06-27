"""
StyleAgent - 开篇钩子师Skill
生成开篇钩子设计（黄金三章方案）+ 分析用户偏好并生成写作风格指南
"""
import logging
from typing import Any, Dict

from .base import BaseAgent
from .prompts import (
    OPENING_HOOK_SYSTEM_PROMPT,
    build_opening_hook_user_prompt,
    build_opening_hook_system_prompt,
)

logger = logging.getLogger(__name__)


class StyleAgent(BaseAgent):
    """
    StyleAgent - 开篇钩子师Agent
    
    职责：
    - 设计黄金三章开篇方案（第一章抛钩子，第二章给期待/反转，第三章给小回报）
    - 分析用户偏好并生成写作风格指南
    - 输出词汇场、句式模板、禁用词清单
    - 平台适配（番茄/飞卢/起点/七猫/书旗）
    """

    AGENT_ID = "style"
    CAPABILITIES = ["hook", "opening", "style"]
    EXPECTS_JSON = True

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行开篇钩子设计
        
        Args:
            context: 包含以下字段的上下文:
                - theme: 故事主题/类型
                - platform: 目标平台（默认"番茄"）
                - world_info: 世界观背景
                - character_info: 主角设定
                - outline_info: 前三章大纲（可选）
                - preference: 风格偏好（可选）
                - samples: 参考文本样本（可选）
                - depth_level: 深度级别（0=SKELETON, 1=FULL, 2+=REVIEW）
                
        Returns:
            根据 depth_level 返回不同结果：
            - depth=1: 黄金三章完整设计方案
            - depth=0: 简洁钩子方向
            - depth>=2: 黄金三章有效性审查报告
            
            {
                "success": True,
                "chapter_1": {...},
                "chapter_2": {...},
                "chapter_3": {...},
                "platform": "番茄",
                "provider": "...",
                "latency_ms": 1234,
                "fallback": False,
            }
        """
        theme = str(context.get("theme", ""))
        platform = str(context.get("platform", "番茄"))
        world_info = str(context.get("world_info", ""))
        character_info = str(context.get("character_info", ""))
        outline_info = str(context.get("outline_info", ""))
        preference = str(context.get("preference", "默认风格"))
        samples = str(context.get("samples", ""))
        depth_level = int(context.get("depth_level", 1))

        # 合并 preference 和 samples
        if samples:
            preference += f"\n参考文本样本：\n{samples}"

        # 构建动态 System Prompt
        system_prompt = build_opening_hook_system_prompt(depth_level)

        user_prompt = build_opening_hook_user_prompt(
            theme=theme,
            platform=platform,
            world_info=world_info,
            character_info=character_info,
            outline_info=outline_info,
            depth_level=depth_level,
        )

        logger.info(f"[StyleAgent] 开始设计开篇钩子 (platform={platform}, depth={depth_level})")

        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expects_json=True,
            max_tokens=6000,
        )

        data = result.get("data") or {}

        if depth_level >= 2:
            # POLISH模式：返回审查报告
            return {
                "success": True,
                "effectiveness_score": data.get("effectiveness_score", 7.0),
                "chapter_1_review": data.get("chapter_1_review", ""),
                "chapter_2_review": data.get("chapter_2_review", ""),
                "chapter_3_review": data.get("chapter_3_review", ""),
                "issues": data.get("issues", []),
                "platform": platform,
                "provider": result.get("provider"),
                "latency_ms": result.get("latency_ms"),
                "fallback": result.get("fallback", False),
            }

        # 标准模式：返回黄金三章设计方案
        logger.info(f"[StyleAgent] 开篇钩子设计完成 (platform={platform}), "
                     f"provider={result.get('provider', 'unknown')}")

        return {
            "success": True,
            "chapter_1": data.get("chapter_1", {}),
            "chapter_2": data.get("chapter_2", {}),
            "chapter_3": data.get("chapter_3", {}),
            "platform_notes": data.get("platform_notes", ""),
            "platform": platform,
            "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"),
            "fallback": result.get("fallback", False),
        }

    def _mock_fallback(self, _user_prompt: str) -> Dict[str, Any]:
        """JSON解析失败时的兜底数据"""
        return {
            "chapter_1": {
                "title": "第一章 待定",
                "opening_300_words_plan": "在第一章前300字内设置冲突/悬念/反差/危机",
                "first_conflict": "主角面临第一个困境",
                "protagonist_first_impression": "展现主角核心特征",
                "ending_hook": "第一章结尾设置期待点",
            },
            "chapter_2": {
                "title": "第二章 待定",
                "twist_design": "意想不到的转折",
                "expectation_build": "建立读者期待",
                "key_character_intro": "引入关键配角",
                "ending_hook": "第二章结尾设置期待点",
            },
            "chapter_3": {
                "title": "第三章 待定",
                "small_win": "主角解决第一个小困境",
                "satisfaction_point": "给读者满足感",
                "bigger_suspense": "埋下更大悬念",
                "ending_hook": "第三章结尾设置期待点",
            },
            "platform_notes": "",
        }
