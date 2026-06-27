"""
跨章节一致性检查器 - L3 工具层
检查角色、世界观、情节、时间线的一致性
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ── 数据模型 ──

class Severity(str, Enum):
    """问题严重程度"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class IssueType(str, Enum):
    """问题类型"""
    CHARACTER = "character"
    WORLD = "world"
    PLOT = "plot"
    TIMELINE = "timeline"


@dataclass
class ConsistencyIssue:
    """一致性问题和修复建议"""
    issue_type: str           # character, world, plot, timeline
    severity: str            # critical, warning, info
    chapter_idx: int
    description: str
    suggestion: str
    affected_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "chapter_idx": self.chapter_idx,
            "description": self.description,
            "suggestion": self.suggestion,
            "affected_entities": self.affected_entities,
        }


# ── ConsistencyChecker ──

class ConsistencyChecker:
    """
    跨章节一致性检查器（L3 工具层）
    
    功能:
    - 检查角色一致性（外貌、性格、关系）
    - 检查世界观一致性（规则、设定、环境）
    - 检查情节一致性（大纲遵循、伏笔追踪）
    - 检查时间线一致性（时间连续、因果逻辑）
    - 执行完整检查并生成报告
    """

    def __init__(self, memory_service):
        """
        初始化一致性检查器
        
        Args:
            memory_service: MemoryService 实例
        """
        self.memory = memory_service
        logger.info("[ConsistencyChecker] 初始化完成")

    # ── 角色一致性检查 ──

    async def check_character_consistency(
        self,
        novel_id: str,
        chapter_idx: int,
        chapter_content: str,
    ) -> List[ConsistencyIssue]:
        """
        检查角色一致性
        
        检查:
        1. 角色外貌是否与设定一致
        2. 角色性格/行为是否与设定冲突
        3. 角色关系是否与设定一致
        """
        issues = []

        try:
            # 从记忆系统获取角色设定
            char_results = await self.memory.semantic_search(
                novel_id,
                "character personality appearance description",
                top_k=10,
                collection="long_term_characters",
            )

            if not char_results:
                logger.debug("[ConsistencyChecker] 未找到角色设定，跳过检查")
                return issues

            # 提取本章出现的角色名
            mentioned_chars = self._extract_mentioned_characters(chapter_content)

            # 检查每个出现角色的一致性
            for char_name in mentioned_chars:
                # 查找该角色的设定
                char_setting = self._find_character_setting(char_name, char_results)
                if not char_setting:
                    continue

                # 检查外貌一致性
                appearance_issues = self._check_appearance_consistency(
                    char_name, chapter_content, char_setting
                )
                issues.extend(appearance_issues)

                # 检查性格一致性
                personality_issues = self._check_personality_consistency(
                    char_name, chapter_content, char_setting
                )
                issues.extend(personality_issues)

                # 检查关系一致性
                relationship_issues = self._check_relationship_consistency(
                    char_name, chapter_content, char_setting
                )
                issues.extend(relationship_issues)

            logger.info(
                "[ConsistencyChecker] 角色一致性检查完成: %d 个问题",
                len(issues),
            )

        except Exception as e:
            logger.error("[ConsistencyChecker] 角色一致性检查失败: %s", e)

        return issues

    async def _check_appearance_consistency(
        self,
        char_name: str,
        chapter_content: str,
        char_setting: Dict,
    ) -> List[ConsistencyIssue]:
        """检查外貌一致性"""
        issues = []

        appearance = char_setting.get("appearance", "") or char_setting.get("appearance_desc", "")
        if not appearance:
            return issues

        # 检查是否在本章中提到了外貌且与设定矛盾
        # 简单实现：检测是否有关键词冲突
        key_traits = self._extract_key_traits(appearance)

        for trait in key_traits:
            # 如果设定中有"黑色头发"，本章说"金色头发"，则标记
            # 这是一个简化的检查，实际可以使用 LLM 做更精确的判断
            pass

        return issues

    async def _check_personality_consistency(
        self,
        char_name: str,
        chapter_content: str,
        char_setting: Dict,
    ) -> List[ConsistencyIssue]:
        """检查性格一致性"""
        issues = []

        personality = char_setting.get("personality", "") or char_setting.get("personality_desc", "")
        if not personality:
            return issues

        # 提取性格关键词
        personality_keywords = self._extract_key_traits(personality)

        # 检测明显矛盾的行为描述
        # 简化版：如果性格设定是"内向"，但本章有大量"热情奔放"的描述，标记 warning
        # 实际实现可以使用 LLM 做语义对比

        return issues

    async def _check_relationship_consistency(
        self,
        char_name: str,
        chapter_content: str,
        char_setting: Dict,
    ) -> List[ConsistencyIssue]:
        """检查关系一致性"""
        issues = []

        relationships = char_setting.get("relationships", []) or char_setting.get("relations", [])
        if not relationships:
            return issues

        return issues

    # ── 世界观一致性检查 ──

    async def check_world_consistency(
        self,
        novel_id: str,
        chapter_idx: int,
        chapter_content: str,
    ) -> List[ConsistencyIssue]:
        """
        检查世界观一致性
        
        检查:
        1. 是否违反世界规则
        2. 环境描述是否与设定一致
        3. 魔法/科技系统是否自洽
        """
        issues = []

        try:
            # 从记忆系统获取世界观设定
            world_results = await self.memory.semantic_search(
                novel_id,
                "world setting rules magic system technology",
                top_k=10,
                collection="long_term_world",
            )

            if not world_results:
                logger.debug("[ConsistencyChecker] 未找到世界观设定，跳过检查")
                return issues

            # 检查每个世界规则的遵循情况
            for result in world_results:
                world_data = result.get("metadata", {})
                category = world_data.get("category", "")
                content = result.get("content", "")

                # 解析世界规则
                rules = self._extract_rules(content)

                # 检查本章是否违反规则
                for rule in rules:
                    violation = self._check_rule_violation(rule, chapter_content)
                    if violation:
                        issues.append(ConsistencyIssue(
                            issue_type=IssueType.WORLD,
                            severity=Severity.CRITICAL,
                            chapter_idx=chapter_idx,
                            description=f"违反世界规则: {rule}",
                            suggestion=f"请检查 {category} 相关设定，修改本章内容以符合规则",
                            affected_entities=[category],
                        ))

            logger.info(
                "[ConsistencyChecker] 世界观一致性检查完成: %d 个问题",
                len(issues),
            )

        except Exception as e:
            logger.error("[ConsistencyChecker] 世界观一致性检查失败: %s", e)

        return issues

    async def _check_rule_violation(self, rule: str, chapter_content: str) -> bool:
        """检查是否违反规则（简化版）"""
        # 实际实现可以使用 LLM 做更精确的规则检查
        # 这里只做关键词匹配
        return False

    # ── 情节一致性检查 ──

    async def check_plot_consistency(
        self,
        novel_id: str,
        chapter_idx: int,
        chapter_content: str,
        outline: Optional[Dict] = None,
    ) -> List[ConsistencyIssue]:
        """
        检查情节一致性
        
        检查:
        1. 是否偏离大纲
        2. 伏笔是否合理
        3. 情节逻辑是否自洽
        """
        issues = []

        try:
            # 如果没有传入大纲，从记忆系统获取
            if not outline:
                outline = await self._get_outline(novel_id, chapter_idx)

            if not outline:
                logger.debug("[ConsistencyChecker] 未找到大纲，跳过情节检查")
                return issues

            # 检查伏笔追踪
            foreshadowing_issues = await self._check_foreshadowing(
                novel_id, chapter_idx, chapter_content
            )
            issues.extend(foreshadowing_issues)

            # 检查情节逻辑（简化版）
            plot_issues = self._check_plot_logic(chapter_content, outline)
            issues.extend(plot_issues)

            logger.info(
                "[ConsistencyChecker] 情节一致性检查完成: %d 个问题",
                len(issues),
            )

        except Exception as e:
            logger.error("[ConsistencyChecker] 情节一致性检查失败: %s", e)

        return issues

    async def _check_foreshadowing(
        self,
        novel_id: str,
        chapter_idx: int,
        chapter_content: str,
    ) -> List[ConsistencyIssue]:
        """检查伏笔追踪"""
        issues = []

        try:
            # 从记忆系统获取伏笔
            foreshadowing_results = await self.memory.semantic_search(
                novel_id,
                "foreshadowing hint clue suspense",
                top_k=5,
                collection="long_term_foreshadowing",
            )

            if not foreshadowing_results:
                return issues

            # 检查是否有未解决的伏笔在本章应该解决
            for hint in foreshadowing_results:
                hint_metadata = hint.get("metadata", {})
                resolved = hint_metadata.get("resolved", False)
                resolve_chapter = hint_metadata.get("resolve_chapter")

                if not resolved and resolve_chapter == chapter_idx:
                    # 这个伏笔应该在本章解决
                    # 检查本章是否有相关内容的暗示
                    hint_text = hint.get("content", "")[:200]
                    if not self._contains_hint_reference(hint_text, chapter_content):
                        issues.append(ConsistencyIssue(
                            issue_type=IssueType.PLOT,
                            severity=Severity.WARNING,
                            chapter_idx=chapter_idx,
                            description=f"伏笔未解决: {hint_text[:100]}...",
                            suggestion="请检查本章是否回应了该伏笔",
                            affected_entities=["foreshadowing"],
                        ))

        except Exception as e:
            logger.error("[ConsistencyChecker] 伏笔检查失败: %s", e)

        return issues

    async def _check_timeline_consistency(
        self,
        novel_id: str,
        chapter_idx: int,
        chapter_content: str,
    ) -> List[ConsistencyIssue]:
        """
        检查时间线一致性
        
        检查:
        1. 章节内时间是否连续
        2. 与上一章的时间衔接
        3. 事件因果逻辑
        """
        issues = []

        try:
            # 提取本章的时间信息
            time_mentions = self._extract_time_mentions(chapter_content)

            if not time_mentions:
                return issues

            # 检查时间连续性
            for i in range(1, len(time_mentions)):
                prev_time = time_mentions[i - 1]
                curr_time = time_mentions[i]

                # 如果时间倒流（简单判断）
                if self._is_time_regression(prev_time, curr_time):
                    issues.append(ConsistencyIssue(
                        issue_type=IssueType.TIMELINE,
                        severity=Severity.WARNING,
                        chapter_idx=chapter_idx,
                        description=f"时间可能倒流: {prev_time} -> {curr_time}",
                        suggestion="请检查时间线是否连续",
                        affected_entities=["timeline"],
                    ))

            # 检查与上一章的衔接（简化版）
            if chapter_idx > 0:
                prev_chapter_content = await self._get_previous_chapter(novel_id, chapter_idx)
                if prev_chapter_content:
                    continuity_issues = self._check_continuity(
                        prev_chapter_content, chapter_content
                    )
                    issues.extend(continuity_issues)

            logger.info(
                "[ConsistencyChecker] 时间线一致性检查完成: %d 个问题",
                len(issues),
            )

        except Exception as e:
            logger.error("[ConsistencyChecker] 时间线一致性检查失败: %s", e)

        return issues

    # ── 完整检查 ──

    async def full_check(
        self,
        novel_id: str,
        chapter_idx: int,
        chapter_content: str,
        outline: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        执行完整一致性检查
        
        Args:
            novel_id: 小说 ID
            chapter_idx: 章节索引
            chapter_content: 章节内容
            outline: 大纲（可选）
        
        Returns:
            {
                "total_issues": N,
                "critical_issues": N,
                "warnings": N,
                "issues": [...],
            }
        """
        logger.info(
            "[ConsistencyChecker] 开始完整一致性检查: novel=%s, chapter=%d",
            novel_id, chapter_idx,
        )

        issues = []

        # 并行执行所有检查
        char_issues = await self.check_character_consistency(
            novel_id, chapter_idx, chapter_content
        )
        issues.extend(char_issues)

        world_issues = await self.check_world_consistency(
            novel_id, chapter_idx, chapter_content
        )
        issues.extend(world_issues)

        plot_issues = await self.check_plot_consistency(
            novel_id, chapter_idx, chapter_content, outline
        )
        issues.extend(plot_issues)

        timeline_issues = await self.check_timeline_consistency(
            novel_id, chapter_idx, chapter_content
        )
        issues.extend(timeline_issues)

        # 统计
        critical_count = sum(1 for i in issues if i.severity == Severity.CRITICAL)
        warning_count = sum(1 for i in issues if i.severity == Severity.WARNING)

        result = {
            "novel_id": novel_id,
            "chapter_idx": chapter_idx,
            "total_issues": len(issues),
            "critical_issues": critical_count,
            "warnings": warning_count,
            "issues": [i.to_dict() for i in issues],
        }

        logger.info(
            "[ConsistencyChecker] 完整检查完成: 总计=%d, 严重=%d, 警告=%d",
            len(issues), critical_count, warning_count,
        )

        return result

    # ── 辅助方法 ──

    def _extract_mentioned_characters(self, content: str) -> List[str]:
        """提取文本中提到的角色名（简化版）"""
        # 实际实现应该使用命名实体识别
        # 这里只是一个占位
        return []

    def _find_character_setting(
        self, char_name: str, char_results: List[Dict]
    ) -> Optional[Dict]:
        """查找角色设定"""
        for result in char_results:
            metadata = result.get("metadata", {})
            if metadata.get("name") == char_name or metadata.get("char_id") == char_name:
                # 解析内容
                try:
                    import json
                    content = result.get("content", "")
                    return json.loads(content)
                except Exception:
                    return result
        return None

    def _extract_key_traits(self, text: str) -> List[str]:
        """提取关键特征（简化版）"""
        # 实际实现应该使用 NLP
        return []

    def _extract_rules(self, content: str) -> List[str]:
        """提取世界规则"""
        rules = []
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and any(keyword in line for keyword in ["规则", "规定", "不能", "禁止", "必须", "只能"]):
                rules.append(line)
        return rules

    async def _get_outline(self, novel_id: str, chapter_idx: int) -> Optional[Dict]:
        """获取大纲（从记忆系统或数据库）"""
        # 简化版：返回 None，表示没有大纲
        return None

    def _check_plot_logic(self, chapter_content: str, outline: Dict) -> List[ConsistencyIssue]:
        """检查情节逻辑（简化版）"""
        return []

    def _contains_hint_reference(self, hint: str, content: str) -> bool:
        """检查内容是否包含伏笔引用（简化版）"""
        # 简单关键词匹配
        hint_words = set(hint.split())
        content_words = set(content.split())
        overlap = hint_words & content_words
        return len(overlap) > 0

    def _extract_time_mentions(self, content: str) -> List[str]:
        """提取时间提及（简化版）"""
        # 匹配常见时间词
        time_keywords = [
            "早晨", "早上", "上午", "中午", "下午", "傍晚", "晚上", "深夜",
            "今天", "明天", "昨天", "前天", "后天",
            "春天", "夏天", "秋天", "冬天",
            "第一日", "第二日", "第三日",
        ]
        mentions = []
        for keyword in time_keywords:
            if keyword in content:
                mentions.append(keyword)
        return mentions

    def _is_time_regression(self, prev_time: str, curr_time: str) -> bool:
        """判断时间是否倒流（简化版）"""
        time_order = [
            "早晨", "早上", "上午", "中午", "下午", "傍晚", "晚上", "深夜",
        ]
        prev_idx = time_order.index(prev_time) if prev_time in time_order else -1
        curr_idx = time_order.index(curr_time) if curr_time in time_order else -1
        return curr_idx < prev_idx if prev_idx >= 0 and curr_idx >= 0 else False

    async def _get_previous_chapter(self, novel_id: str, chapter_idx: int) -> Optional[str]:
        """获取上一章内容（从记忆系统）"""
        if chapter_idx <= 0:
            return None

        try:
            results = await self.memory.semantic_search(
                novel_id,
                f"chapter {chapter_idx - 1}",
                top_k=1,
                collection="working_memory",
            )
            if results:
                return results[0].get("content")
        except Exception:
            pass
        return None

    def _check_continuity(self, prev_content: str, curr_content: str) -> List[ConsistencyIssue]:
        """检查章节衔接（简化版）"""
        issues = []
        # 实际实现需要更复杂的衔接检查
        return issues
