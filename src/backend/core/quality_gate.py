"""
质量门控 (QualityGate) — 章节质量检查和评分

评分维度:
- 情节连贯性 (plot_coherence): 故事逻辑是否通顺
- 人物一致性 (character_consistency): 角色行为是否符合设定
- 文笔流畅度 (writing_fluency): 语言表达是否流畅自然

返回:
- 各维度评分 (0-10)
- 总体评分
- 修改建议列表
"""
import json
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from ..llm.gateway import LLMGateway, LLMMessage, get_gateway


@dataclass
class QualityScore:
    """质量评分结果"""
    plot_coherence: float = 0.0      # 情节连贯性
    character_consistency: float = 0.0  # 人物一致性
    writing_fluency: float = 0.0      # 文笔流畅度
    overall_score: float = 0.0        # 总体评分
    suggestions: List[str] = field(default_factory=list)  # 修改建议
    passed: bool = False              # 是否通过质量门控

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plot_coherence": round(self.plot_coherence, 2),
            "character_consistency": round(self.character_consistency, 2),
            "writing_fluency": round(self.writing_fluency, 2),
            "overall_score": round(self.overall_score, 2),
            "suggestions": self.suggestions,
            "passed": self.passed,
        }


class QualityGate:
    """
    质量门控 — 检查章节内容质量
    
    使用示例:
        gate = QualityGate(gateway=llm_gateway, threshold=7.0)
        result = await gate.check_quality(chapter_content, outline)
        if result.passed:
            # 接受章节
        else:
            # 根据 suggestions 修改后重新检查
    """

    # 默认质量阈值
    DEFAULT_THRESHOLD = 7.0

    # 各维度权重
    WEIGHTS = {
        "plot_coherence": 0.4,
        "character_consistency": 0.3,
        "writing_fluency": 0.3,
    }

    def __init__(
        self,
        gateway: Optional[LLMGateway] = None,
        threshold: float = DEFAULT_THRESHOLD,
        enable_llm_check: bool = True,
    ):
        """
        Args:
            gateway: LLM 网关实例，用于智能评分
            threshold: 质量阈值，低于此值认为不合格
            enable_llm_check: 是否启用 LLM 智能评分（否则使用规则评分）
        """
        self.gateway = gateway or get_gateway()
        self.threshold = threshold
        self.enable_llm_check = enable_llm_check

    async def check_quality(
        self,
        chapter_content: str,
        outline: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Dict[str, Any]]] = None,
        world_settings: Optional[Dict[str, Any]] = None,
    ) -> QualityScore:
        """
        检查章节质量

        Args:
            chapter_content: 章节正文内容
            outline: 章节大纲（可选）
            characters: 角色列表（可选）
            world_settings: 世界观设定（可选）

        Returns:
            QualityScore 评分结果
        """
        if not chapter_content or len(chapter_content.strip()) < 100:
            return QualityScore(
                suggestions=["内容过短，建议至少包含完整的情节段落"],
                passed=False,
            )

        if self.enable_llm_check:
            return await self._llm_score(chapter_content, outline, characters, world_settings)
        else:
            return self._rule_score(chapter_content, outline)

    async def _llm_score(
        self,
        chapter_content: str,
        outline: Optional[Dict[str, Any]],
        characters: Optional[List[Dict[str, Any]]],
        world_settings: Optional[Dict[str, Any]],
    ) -> QualityScore:
        """使用 LLM 进行智能评分"""
        # 构建评分 prompt
        context_parts = []
        if outline:
            context_parts.append(f"大纲：{json.dumps(outline, ensure_ascii=False)}")
        if characters:
            char_names = [c.get("name", "") for c in characters if isinstance(c, dict)]
            context_parts.append(f"角色：{', '.join(char_names)}")
        if world_settings:
            context_parts.append(f"世界观：{json.dumps(world_settings, ensure_ascii=False)}")

        context = "\n".join(context_parts) if context_parts else "无额外上下文"

        system_prompt = """你是一个专业的小说质量评审师。请根据以下维度对章节内容评分（0-10分）：

1. 情节连贯性 (plot_coherence): 故事逻辑是否通顺，前后是否矛盾
2. 人物一致性 (character_consistency): 角色行为是否符合设定，性格是否稳定
3. 文笔流畅度 (writing_fluency): 语言表达是否流畅，是否有病句或重复

请严格按照以下 JSON 格式返回，不要包含其他内容：
{
    "plot_coherence": 8.5,
    "character_consistency": 7.0,
    "writing_fluency": 8.0,
    "suggestions": ["建议加强开头吸引力", "人物对话可以更自然"]
}"""

        user_prompt = f"""请对以下章节进行质量评审：

【上下文】
{context}

【章节内容】
{chapter_content[:8000]}

请评分并给出修改建议（总分保留1位小数）："""

        response = await self.gateway.generate(
            messages=[LLMMessage(role="user", content=user_prompt)],
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500,
        )

        if response.error:
            print(f"[QualityGate] LLM 评分失败: {response.error}，使用规则评分")
            return self._rule_score(chapter_content, outline)

        return self._parse_llm_score(response.content)

    def _parse_llm_score(self, content: str) -> QualityScore:
        """解析 LLM 返回的评分"""
        # 尝试提取 JSON
        json_match = re.search(r'\{[^{}]*"plot_coherence"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return self._create_score_from_dict(data)
            except json.JSONDecodeError:
                pass

        # 尝试提取带 ```json 的块
        json_block = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', content)
        if json_block:
            try:
                data = json.loads(json_block.group(1))
                return self._create_score_from_dict(data)
            except json.JSONDecodeError:
                pass

        # 降级：返回默认低分
        return QualityScore(
            suggestions=["LLM 评分解析失败，请检查内容格式"],
            passed=False,
        )

    def _create_score_from_dict(self, data: Dict[str, Any]) -> QualityScore:
        """从字典创建评分结果"""
        plot = float(data.get("plot_coherence", 0))
        char = float(data.get("character_consistency", 0))
        write = float(data.get("writing_fluency", 0))

        weights = self.WEIGHTS
        overall = round(
            plot * weights["plot_coherence"]
            + char * weights["character_consistency"]
            + write * weights["writing_fluency"],
            2,
        )

        suggestions = data.get("suggestions", [])
        if not suggestions:
            if overall < self.threshold:
                suggestions.append(f"总体评分 {overall} 低于阈值 {self.threshold}，需要修改")

        return QualityScore(
            plot_coherence=plot,
            character_consistency=char,
            writing_fluency=write,
            overall_score=overall,
            suggestions=suggestions,
            passed=overall >= self.threshold,
        )

    def _rule_score(
        self,
        chapter_content: str,
        outline: Optional[Dict[str, Any]] = None,
    ) -> QualityScore:
        """
        基于规则的质量评分（不依赖 LLM）

        检查项:
        - 字数是否达标（最少 1500 字）
        - 段落数量（至少 3 段）
        - 是否有标点符号
        - 大纲匹配度（如果提供大纲）
        """
        suggestions = []
        scores = {}

        # 1. 字数检查
        word_count = len(chapter_content.strip())
        if word_count < 500:
            scores["plot_coherence"] = 2.0
            suggestions.append(f"字数严重不足（{word_count}字），建议至少 1500 字")
        elif word_count < 1500:
            scores["plot_coherence"] = 5.0
            suggestions.append(f"字数偏少（{word_count}字），建议充实内容")
        else:
            scores["plot_coherence"] = 7.0

        # 2. 段落检查
        paragraphs = [p.strip() for p in chapter_content.split("\n\n") if p.strip()]
        if len(paragraphs) < 3:
            scores["writing_fluency"] = 3.0
            suggestions.append("段落过少，建议分段以增强可读性")
        elif len(paragraphs) < 5:
            scores["writing_fluency"] = 6.0
        else:
            scores["writing_fluency"] = 7.5

        # 3. 标点检查
        has_punctuation = any(c in chapter_content for c in "，。！？；：""''（）")
        if not has_punctuation:
            scores["writing_fluency"] = max(scores["writing_fluency"] - 2.0, 0)
            suggestions.append("缺少中文标点符号")

        # 4. 大纲匹配度
        if outline:
            outline_summary = outline.get("summary", "") or outline.get("title", "")
            if outline_summary and outline_summary in chapter_content[:500]:
                scores["plot_coherence"] = min(scores["plot_coherence"] + 1.0, 10.0)
            else:
                scores["plot_coherence"] = max(scores["plot_coherence"] - 1.0, 0)
                suggestions.append("章节内容与大纲摘要匹配度不高")

        # 计算加权总分
        weights = self.WEIGHTS
        overall = round(
            scores.get("plot_coherence", 0) * weights["plot_coherence"]
            + scores.get("character_consistency", 5.0) * weights["character_consistency"]
            + scores.get("writing_fluency", 0) * weights["writing_fluency"],
            2,
        )

        return QualityScore(
            plot_coherence=scores.get("plot_coherence", 5.0),
            character_consistency=scores.get("character_consistency", 5.0),
            writing_fluency=scores.get("writing_fluency", 5.0),
            overall_score=overall,
            suggestions=suggestions if suggestions else ["内容基本合格"],
            passed=overall >= self.threshold,
        )

    def set_threshold(self, threshold: float):
        """设置质量阈值"""
        self.threshold = threshold

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "threshold": self.threshold,
            "enable_llm_check": self.enable_llm_check,
            "weights": self.WEIGHTS,
        }
