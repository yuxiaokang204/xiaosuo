"""
文风精修师Agent - 合并原StyleAgent + EditAgent + ReviewAgent
职责：文风设计 + 精修编辑 + 品质审查
"""
from typing import Dict
from .base import BaseAgent
from .prompts import STYLE_EDITOR_SYSTEM_PROMPT, build_style_editor_user_prompt, sanitize_chapter_content


class StyleEditorAgent(BaseAgent):
    """文风精修师 - 集文风设计、精修编辑、品质审查于一身"""

    AGENT_ID = "style_editor"
    AGENT_NAME = "文风精修师"
    CAPABILITIES = ["style", "editing", "review", "refinement"]
    EXPECTS_JSON = True

    async def execute(self, context: Dict) -> Dict[str, object]:
        content = str(context.get("content", ""))
        theme = str(context.get("theme", ""))
        platform = str(context.get("platform", "番茄"))
        context_summary = str(context.get("context_summary", ""))
        edit_focus = str(context.get("edit_focus", ""))
        mode = str(context.get("mode", "full"))  # full/style_only/edit_only/review_only

        # 根据模式调整任务
        if mode == "style_only":
            # 仅文风设计 — v3.0: 明确要求JSON输出
            user_prompt = f"""故事类型：{theme}
目标平台：{platform}

请生成严格的JSON格式文风指南，包含以下字段：
- genre_style: 该类型的核心文风特征（30字内）
- vocabulary_field: 核心词汇场和禁用词清单
- sentence_blueprints: 3-5种高频句式模板
- sensory_ratio: 感官描写比例（visual/auditory/tactile/olfactory/gustatory，和为100）
- paragraph_rules: 段落规则（max_lines, dialogue_break, beat_spacing）
- anti_ai_patterns: AI味禁用表达列表（至少8个）

请严格按照JSON格式输出，不要添加任何额外文字。"""
            result = await self._call_llm(STYLE_EDITOR_SYSTEM_PROMPT, user_prompt, expects_json=True)
            data = result.get("data") or {}
            return {
                "success": True,
                "mode": "style_only",
                "style_guide": data.get("style_guide", {}),
                "provider": result.get("provider"),
                "latency_ms": result.get("latency_ms"),
            }

        elif mode == "edit_only":
            # 仅精修编辑
            user_prompt = build_style_editor_user_prompt(
                content=content,
                theme=theme,
                platform=platform,
                context_summary=context_summary,
                edit_focus=edit_focus,
            )
            result = await self._call_llm(STYLE_EDITOR_SYSTEM_PROMPT, user_prompt, expects_json=True)
            data = result.get("data") or {}
            edited_content = data.get("edited_content", content)
            # 清洗内容
            edited_content = sanitize_chapter_content(edited_content)
            return {
                "success": True,
                "mode": "edit_only",
                "edited_content": edited_content,
                "provider": result.get("provider"),
                "latency_ms": result.get("latency_ms"),
            }

        elif mode == "review_only":
            # 仅品质审查
            user_prompt = f"待审查内容：\n{content}\n\n前文概要：{context_summary}\n请从7个维度评分，给出改进建议。"
            result = await self._call_llm(STYLE_EDITOR_SYSTEM_PROMPT, user_prompt, expects_json=True)
            data = result.get("data") or {}
            return {
                "success": True,
                "mode": "review_only",
                "review": data.get("review", {}),
                "provider": result.get("provider"),
                "latency_ms": result.get("latency_ms"),
            }

        else:
            # 全流程：文风设计 + 精修编辑 + 品质审查
            user_prompt = build_style_editor_user_prompt(
                content=content,
                theme=theme,
                platform=platform,
                context_summary=context_summary,
                edit_focus=edit_focus,
            )
            result = await self._call_llm(STYLE_EDITOR_SYSTEM_PROMPT, user_prompt, expects_json=True)

            data = result.get("data") or {}
            edited_content = data.get("edited_content", content)
            # 清洗内容
            edited_content = sanitize_chapter_content(edited_content)

            return {
                "success": True,
                "mode": "full",
                "style_guide": data.get("style_guide", {}),
                "edited_content": edited_content,
                "review": data.get("review", {}),
                "provider": result.get("provider"),
                "latency_ms": result.get("latency_ms"),
                "raw": result.get("raw"),
            }

    def _mock_fallback(self, user_prompt: str) -> Dict:
        """生成 mock 文风精修结果"""
        return {
            "style_guide": {
                "genre_style": "玄幻史诗风",
                "vocabulary_field": {
                    "core_terms": ["灵力", "魂力", "神识"],
                    "taboo_words": ["眼中闪过一丝", "心中涌起一股", "只见"],
                },
                "sentence_blueprints": [
                    {"pattern": "短句+动作", "usage": "战斗场景", "example": "剑光一闪，血花飞溅。"}
                ],
                "sensory_ratio": {"visual": 40, "auditory": 25, "tactile": 20, "olfactory": 10, "gustatory": 5},
                "paragraph_rules": {"max_lines": 5, "dialogue_break": "换人必换行"},
                "anti_ai_patterns": ["眼中闪过一丝", "心中涌起一股", "与此同时"],
            },
            "edited_content": "（精修后的内容）",
            "review": {
                "overall_score": 7.5,
                "dimension_scores": {
                    "opening_impact": 8.0,
                    "language_precision": 7.0,
                    "paragraph_rhythm": 8.0,
                    "show_dont_tell": 7.5,
                    "dialogue_quality": 7.0,
                    "chapter_completeness": 8.0,
                    "consistency": 7.0,
                },
                "strengths": ["开头冲击力强", "节奏紧凑"],
                "issues": [],
                "suggestions": ["可以增加更多感官描写"],
            },
        }