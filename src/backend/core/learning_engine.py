from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict
from ..models.schemas import UserFeedback, FeedbackType, StyleGuide

class PatternFrequency:
    def __init__(self):
        self.count = 0
        self.last_seen = datetime.now()

class LearningEngine:
    def __init__(self):
        self.style_patterns: Dict[str, PatternFrequency] = defaultdict(PatternFrequency)
        self.word_preferences: Dict[str, List[str]] = defaultdict(list)
        self.anti_ai_patterns: List[Dict] = self._init_anti_ai_patterns()
        self.feedback_history: List[UserFeedback] = []
        self.style_guide_updates: Dict[str, int] = defaultdict(int)
        # v5.0: 章节衔接反馈数据
        self._continuity_feedback: List[Dict] = []

    def _init_anti_ai_patterns(self) -> List[Dict]:
        return [
            {"pattern": "眼中闪过一丝", "replacements": ["眼神微动", "目光一凝", "眼底掠过"]},
            {"pattern": "心中涌起一股", "replacements": ["心底", "心头", "胸腔中"]},
            {"pattern": "忍不住", "replacements": ["不由得", "禁不住", "不禁"]},
            {"pattern": "与此同时", "replacements": ["这时", "此刻", "就在这时"]},
        ]

    def learn_from_feedback(self, feedback: UserFeedback):
        self.feedback_history.append(feedback)

        if feedback.feedback_type == FeedbackType.STYLE_EDIT:
            self._learn_style_edit(feedback)
        elif feedback.feedback_type == FeedbackType.CHARACTER_EDIT:
            self._learn_character_preference(feedback)
        elif feedback.feedback_type == FeedbackType.DELETION:
            self._learn_negative_pattern(feedback)

        if feedback.before_text and feedback.after_text:
            self._analyze_pattern_changes(feedback.before_text, feedback.after_text)

    def _learn_style_edit(self, feedback: UserFeedback):
        if feedback.after_text and feedback.before_text:
            key = feedback.before_text[:50]
            self.style_patterns[key].count += 1
            self.style_patterns[key].last_seen = datetime.now()

            # 去重：重复反馈不应在偏好列表里堆叠同一项，否则 random.choice 会被概率性放大
            prefs = self.word_preferences[feedback.before_text]
            if feedback.after_text not in prefs:
                prefs.append(feedback.after_text)

    def _learn_character_preference(self, feedback: UserFeedback):
        if feedback.metadata:
            char_name = feedback.metadata.get("character_name")
            if char_name:
                self.style_guide_updates[f"character_{char_name}"] += 1

    def _learn_negative_pattern(self, feedback: UserFeedback):
        if feedback.before_text:
            pat = feedback.before_text[:30]
            if not any(p.get("pattern") == pat for p in self.anti_ai_patterns):
                self.anti_ai_patterns.append({
                    "pattern": pat,
                    "replacements": [""]
                })

    def _analyze_pattern_changes(self, before: str, after: str):
        before_words = before.split()
        after_words = after.split()
        
        for i in range(min(len(before_words), len(after_words))):
            if before_words[i] != after_words[i]:
                prefs = self.word_preferences[before_words[i]]
                if after_words[i] not in prefs:
                    prefs.append(after_words[i])

    def apply_preference(self, content: str) -> str:
        result = content
        result = self._remove_ai_taste(result)
        result = self._apply_word_preferences(result)
        result = self._apply_style_patterns(result)
        return result

    def _remove_ai_taste(self, text: str) -> str:
        result = text
        
        for pattern_info in self.anti_ai_patterns:
            pattern = pattern_info["pattern"]
            replacements = pattern_info["replacements"]
            
            if pattern in result:
                import random
                if replacements:
                    replacement = random.choice(replacements)
                else:
                    replacement = ""
                result = result.replace(pattern, replacement)
        
        return result

    def _apply_word_preferences(self, text: str) -> str:
        result = text
        
        for word, preferred_words in self.word_preferences.items():
            if word in result and preferred_words:
                import random
                replacement = random.choice(preferred_words)
                result = result.replace(word, replacement)
        
        return result

    def _apply_style_patterns(self, text: str) -> str:
        result = text
        
        sorted_patterns = sorted(
            self.style_patterns.items(),
            key=lambda x: x[1].count,
            reverse=True
        )
        
        for pattern, freq in sorted_patterns[:10]:
            if pattern in result:
                if self.word_preferences.get(pattern):
                    result = result.replace(pattern, self.word_preferences[pattern][0])
        
        return result

    def update_style_guide(self, style_guide: StyleGuide, feedback: UserFeedback):
        if feedback.feedback_type == FeedbackType.STYLE_EDIT:
            if feedback.after_text:
                style_guide.vocabulary_preference.append(feedback.after_text)
        
        if feedback.feedback_type == FeedbackType.DELETION:
            if feedback.before_text:
                style_guide.anti_patterns.append(feedback.before_text)
        
        return style_guide

    def get_learned_constraints(self) -> Dict:
        return {
            "style_patterns_count": len(self.style_patterns),
            "word_preferences_count": len(self.word_preferences),
            "anti_ai_patterns_count": len(self.anti_ai_patterns),
            "feedback_count": len(self.feedback_history),
            "top_patterns": self._get_top_patterns(5),
        }

    def _get_top_patterns(self, limit: int) -> List[Dict]:
        sorted_items = sorted(
            self.style_patterns.items(),
            key=lambda x: x[1].count,
            reverse=True
        )
        return [
            {"pattern": pattern, "count": freq.count}
            for pattern, freq in sorted_items[:limit]
        ]

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_feedback": len(self.feedback_history),
            "style_edits": sum(1 for f in self.feedback_history if f.feedback_type == FeedbackType.STYLE_EDIT),
            "character_edits": sum(1 for f in self.feedback_history if f.feedback_type == FeedbackType.CHARACTER_EDIT),
            "learned_patterns": len(self.style_patterns),
            "top_10_patterns": self._get_top_patterns(10),
        }

    def clear_learning(self):
        self.style_patterns.clear()
        self.word_preferences.clear()
        self.feedback_history.clear()
        self.anti_ai_patterns = self._init_anti_ai_patterns()
        self._continuity_feedback.clear()

    # ── v5.0: 章节衔接学习 ──

    def record_continuity_feedback(self, novel_id: str, chapter_idx: int,
                                   score: int, comment: str = ""):
        """记录用户对章节衔接的评分，用于动态调整衔接强度"""
        self._continuity_feedback.append({
            "novel_id": novel_id,
            "chapter_idx": chapter_idx,
            "score": score,
            "comment": comment,
            "ts": datetime.now(),
        })

    def get_continuity_intensity(self, novel_id: str) -> Dict[str, Any]:
        """
        根据历史衔接评分返回衔接强度参数

        低分(≤5) → 高强度：更多指令、更严格
        高分(≥8) → 低强度：给 LLM 更多创作自由
        """
        recent = [f for f in self._continuity_feedback
                  if f.get("novel_id") == novel_id][-5:]
        if not recent:
            return {
                "instruction_count": 3,
                "strictness": "medium",
                "require_exact_scene": True,
                "require_state_continuity": True,
            }
        avg = sum(f["score"] for f in recent) / len(recent)
        if avg <= 5:
            return {
                "instruction_count": 5,
                "strictness": "hard",
                "require_exact_scene": True,
                "require_state_continuity": True,
            }
        elif avg >= 8:
            return {
                "instruction_count": 2,
                "strictness": "soft",
                "require_exact_scene": True,
                "require_state_continuity": False,
            }
        return {
            "instruction_count": 3,
            "strictness": "medium",
            "require_exact_scene": True,
            "require_state_continuity": True,
        }

    def get_continuity_statistics(self, novel_id: str) -> Dict[str, Any]:
        """获取衔接评分统计"""
        recent = [f for f in self._continuity_feedback
                  if f.get("novel_id") == novel_id]
        if not recent:
            return {"avg_score": 7, "total": 0, "trend": "stable"}
        scores = [f["score"] for f in recent]
        avg = sum(scores) / len(scores)
        # 趋势：最近 3 次 vs 前 3 次
        if len(scores) >= 6:
            recent_avg = sum(scores[-3:]) / 3
            older_avg = sum(scores[:3]) / 3
            if recent_avg > older_avg + 1:
                trend = "improving"
            elif recent_avg < older_avg - 1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        return {
            "avg_score": round(avg, 1),
            "total": len(scores),
            "trend": trend,
            "recent_scores": scores[-5:],
        }
