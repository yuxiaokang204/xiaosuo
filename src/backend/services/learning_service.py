"""
统计式风格指纹学习服务 - L3 工具层
从用户编辑中提取风格指纹，注入到 Prompt 中
保留 LearningEngine 的逻辑，迁移到新架构
"""
import os
import json
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


# ── 数据模型 ──

@dataclass
class StyleFingerprint:
    """风格指纹"""
    user_id: str
    preferred_words: Dict[str, List[str]]  # 原词 -> 偏好替换词
    sentence_patterns: List[str]           # 偏好句式
    anti_patterns: List[str]               # 反模式（AI味用语）
    style_tags: Dict[str, float]          # 风格标签权重
    created_at: float
    updated_at: float
    edit_count: int

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "preferred_words": self.preferred_words,
            "sentence_patterns": self.sentence_patterns,
            "anti_patterns": self.anti_patterns,
            "style_tags": self.style_tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "edit_count": self.edit_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "StyleFingerprint":
        return cls(
            user_id=data["user_id"],
            preferred_words=data.get("preferred_words", {}),
            sentence_patterns=data.get("sentence_patterns", []),
            anti_patterns=data.get("anti_patterns", []),
            style_tags=data.get("style_tags", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            edit_count=data.get("edit_count", 0),
        )


# ── Token 估算（与 memory_service 共享） ──

def estimate_tokens(text: str) -> int:
    """简单中文 Token 估算"""
    if not text:
        return 0
    chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    english = len(text) - chinese
    return int(chinese / 1.5 + english / 4) + 10


# ── LearningService ──

class LearningService:
    """
    统计式风格指纹学习服务（L3 工具层）
    
    功能:
    - 从用户编辑中学习风格偏好
    - 构建风格指纹（词汇替换、句式偏好、反模式）
    - 将风格约束注入到 Prompt 中
    - 持久化到 JSON 文件
    """

    # 默认反 AI 模式
    DEFAULT_ANTI_PATTERNS = [
        "眼中闪过一丝",
        "心中涌起一股",
        "忍不住",
        "与此同时",
        "不由得",
        "禁不住",
        "不禁",
        "不禁心中",
        "一股",
        "猛地",
        "瞳孔骤缩",
        "浑身一震",
        "倒吸一口凉气",
    ]

    # 默认风格标签
    DEFAULT_STYLE_TAGS = {
        "literary": 0.3,
        "concise": 0.4,
        "vivid": 0.3,
    }

    def __init__(self, persist_dir: str = "./style_data"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.fingerprints: Dict[str, StyleFingerprint] = {}
        self._load_from_disk()
        logger.info("[LearningService] 初始化完成，已加载 %d 个用户指纹", len(self.fingerprints))

    # ── 学习接口 ──

    async def learn_from_edit(
        self,
        original: str,
        edited: str,
        user_id: str = "default",
    ) -> bool:
        """
        从用户编辑中学习风格偏好
        
        Args:
            original: 原始文本
            edited: 编辑后的文本
            user_id: 用户 ID
        """
        if not original or not edited or original == edited:
            return False

        try:
            # 提取风格指纹
            fingerprint = self._extract_fingerprint(original, edited)

            # 更新用户指纹
            self._update_fingerprint(user_id, fingerprint)

            # 持久化
            self._save_to_disk(user_id)

            logger.info(
                "[LearningService] 从编辑中学习: user=%s, 替换词汇=%d, 新增反模式=%d",
                user_id,
                len(fingerprint.preferred_words),
                len(fingerprint.anti_patterns),
            )
            return True
        except Exception as e:
            logger.error("[LearningService] 学习编辑失败: %s", e)
            return False

    async def learn_from_feedback(
        self,
        before_text: str,
        after_text: str,
        user_id: str = "default",
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        从用户反馈中学习（兼容 LearningEngine 接口）
        
        Args:
            before_text: 修改前文本
            after_text: 修改后文本
            user_id: 用户 ID
            metadata: 附加元数据（角色名称等）
        """
        if not before_text or not after_text:
            return False

        try:
            # 词汇替换学习
            if before_text and after_text:
                self._analyze_pattern_changes(before_text, after_text, user_id)

            # 角色偏好学习
            if metadata and after_text:
                char_name = metadata.get("character_name")
                if char_name:
                    logger.info(
                        "[LearningService] 学习角色偏好: %s (%s)",
                        char_name, user_id,
                    )

            # 负面模式学习
            if before_text and after_text:
                fp = self._extract_fingerprint(before_text, after_text)
                self._update_fingerprint(user_id, fp)

            self._save_to_disk(user_id)
            return True
        except Exception as e:
            logger.error("[LearningService] 学习反馈失败: %s", e)
            return False

    # ── Prompt 注入接口 ──

    async def apply_style_constraints(
        self,
        prompt: str,
        user_id: str = "default",
    ) -> str:
        """
        将风格指纹注入到 Prompt 中
        
        Args:
            prompt: 原始 prompt
            user_id: 用户 ID
        """
        fp = self.fingerprints.get(user_id)
        if not fp or fp.edit_count == 0:
            return prompt

        constraints = self._build_constraints(fp)
        return f"{prompt}\n\n【风格约束】\n{constraints}"

    # ── 查询接口 ──

    def get_fingerprint(self, user_id: str) -> Optional[StyleFingerprint]:
        """获取用户风格指纹"""
        return self.fingerprints.get(user_id)

    async def get_statistics(self, user_id: str = "default") -> Dict:
        """
        获取学习统计
        
        Returns:
            {
                "edit_count": N,
                "word_preferences_count": N,
                "anti_patterns_count": N,
                "style_tags": {...},
                "top_patterns": [...],
            }
        """
        fp = self.fingerprints.get(user_id)
        if not fp:
            return {
                "edit_count": 0,
                "word_preferences_count": 0,
                "anti_patterns_count": 0,
                "style_tags": {},
                "top_patterns": [],
            }

        # 统计 Top 模式
        top_patterns = sorted(
            fp.preferred_words.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )[:10]

        return {
            "edit_count": fp.edit_count,
            "word_preferences_count": len(fp.preferred_words),
            "anti_patterns_count": len(fp.anti_patterns),
            "style_tags": fp.style_tags,
            "top_patterns": [
                {"word": word, "replacements": replacements}
                for word, replacements in top_patterns
            ],
        }

    async def clear_learning(self, user_id: str = "default") -> bool:
        """清除用户学习数据"""
        if user_id in self.fingerprints:
            del self.fingerprints[user_id]
            self._save_to_disk(user_id)
            logger.info("[LearningService] 清除用户学习数据: %s", user_id)
            return True
        return False

    # ── 内部方法 ──

    def _extract_fingerprint(self, original: str, edited: str) -> StyleFingerprint:
        """
        从原始和编辑后的文本中提取风格指纹
        
        分析:
        1. 词汇替换（原词 -> 新词）
        2. 句式变化（检测重复模式）
        3. 反模式检测（AI味用语）
        """
        try:
            import jieba
        except ImportError:
            jieba = None

        preferred_words = {}
        anti_patterns = []
        sentence_patterns = []

        if jieba:
            # 分词对比
            original_tokens = set(jieba.lcut(original))
            edited_tokens = set(jieba.lcut(edited))

            # 检测新增和移除的词汇
            added_tokens = edited_tokens - original_tokens
            removed_tokens = original_tokens - edited_tokens

            # 构建词汇偏好映射
            for added in added_tokens:
                if len(added) >= 2 and len(added) <= 10:  # 过滤单字词和过长词
                    # 查找对应的已移除词汇
                    for removed in removed_tokens:
                        if len(removed) == len(added):
                            if removed not in preferred_words:
                                preferred_words[removed] = []
                            if added not in preferred_words[removed]:
                                preferred_words[removed].append(added)

            # 检测反模式
            for token in added_tokens:
                if len(token) >= 3 and any(p in token for p in ["不禁", "忍不住", "心中", "眼中"]):
                    if token not in anti_patterns:
                        anti_patterns.append(token)

            # 检测句式模式（连续 2-3 个词的重复）
            edited_words = jieba.lcut(edited)
            for i in range(len(edited_words) - 2):
                pattern = "".join(edited_words[i:i+3])
                if len(pattern) >= 4 and len(pattern) <= 15:
                    sentence_patterns.append(pattern)
        else:
            # 无 jieba 时的简单字符对比
            original_words = original.split()
            edited_words = edited.split()

            for i in range(min(len(original_words), len(edited_words))):
                if original_words[i] != edited_words[i]:
                    if original_words[i] not in preferred_words:
                        preferred_words[original_words[i]] = []
                    if edited_words[i] not in preferred_words[original_words[i]]:
                        preferred_words[original_words[i]].append(edited_words[i])

        # 合并已有反模式
        existing_fp = self.fingerprints.get("default") or self.fingerprints.get("user_001")
        if existing_fp:
            anti_patterns = list(set(anti_patterns + existing_fp.anti_patterns))

        return StyleFingerprint(
            user_id="temp",
            preferred_words=preferred_words,
            sentence_patterns=sentence_patterns[:20],  # 限制数量
            anti_patterns=anti_patterns,
            style_tags=dict(self.DEFAULT_STYLE_TAGS),
            created_at=time.time(),
            updated_at=time.time(),
            edit_count=0,
        )

    def _update_fingerprint(self, user_id: str, new_fp: StyleFingerprint) -> None:
        """
        更新用户指纹
        
        合并新旧指纹：
        - 词汇偏好：追加（去重）
        - 反模式：合并
        - 编辑计数：+1
        """
        existing = self.fingerprints.get(user_id)

        if existing:
            # 合并词汇偏好
            for word, replacements in new_fp.preferred_words.items():
                if word not in existing.preferred_words:
                    existing.preferred_words[word] = []
                for rep in replacements:
                    if rep not in existing.preferred_words[word]:
                        existing.preferred_words[word].append(rep)

            # 合并反模式
            for pattern in new_fp.anti_patterns:
                if pattern not in existing.anti_patterns:
                    existing.anti_patterns.append(pattern)

            # 更新统计
            existing.edit_count += 1
            existing.updated_at = time.time()

            logger.debug(
                "[LearningService] 更新指纹: user=%s, 编辑次数=%d",
                user_id, existing.edit_count,
            )
        else:
            # 创建新指纹
            self.fingerprints[user_id] = StyleFingerprint(
                user_id=user_id,
                preferred_words=new_fp.preferred_words,
                sentence_patterns=new_fp.sentence_patterns,
                anti_patterns=new_fp.anti_patterns + list(self.DEFAULT_ANTI_PATTERNS),
                style_tags=dict(self.DEFAULT_STYLE_TAGS),
                created_at=time.time(),
                updated_at=time.time(),
                edit_count=1,
            )

    def _analyze_pattern_changes(self, before: str, after: str, user_id: str) -> None:
        """
        分析模式变化（兼容 LearningEngine）
        
        对比原文和编辑后的文本，检测词汇替换
        """
        fp = self.fingerprints.get(user_id)
        if not fp:
            return

        before_words = before.split()
        after_words = after.split()

        for i in range(min(len(before_words), len(after_words))):
            if before_words[i] != after_words[i]:
                word = before_words[i]
                replacement = after_words[i]

                if word not in fp.preferred_words:
                    fp.preferred_words[word] = []
                if replacement not in fp.preferred_words[word]:
                    fp.preferred_words[word].append(replacement)

    def _build_constraints(self, fingerprint: StyleFingerprint) -> str:
        """
        构建风格约束字符串
        
        格式:
        【风格约束】
        1. 词汇偏好：原词 -> [替换词1, 替换词2]
        2. 反模式（避免使用）：...
        3. 风格标签：...
        """
        lines = []

        # 词汇偏好
        if fingerprint.preferred_words:
            lines.append("【词汇偏好】")
            top_words = sorted(
                fingerprint.preferred_words.items(),
                key=lambda x: len(x[1]),
                reverse=True,
            )[:10]
            for word, replacements in top_words:
                lines.append(f"  - {word} → [{', '.join(replacements)}]")

        # 反模式
        if fingerprint.anti_patterns:
            lines.append("\n【避免使用】")
            for pattern in fingerprint.anti_patterns[:15]:
                lines.append(f"  - {pattern}")

        # 风格标签
        if fingerprint.style_tags:
            lines.append("\n【风格标签】")
            for tag, weight in sorted(
                fingerprint.style_tags.items(),
                key=lambda x: -x[1],
            ):
                lines.append(f"  - {tag}: {weight:.1%}")

        return "\n".join(lines)

    # ── 持久化 ──

    def _load_from_disk(self) -> None:
        """从磁盘加载指纹"""
        for file_path in self.persist_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    user_id = data.get("user_id", file_path.stem)
                    self.fingerprints[user_id] = StyleFingerprint.from_dict(data)
                logger.debug("[LearningService] 加载指纹: %s", user_id)
            except Exception as e:
                logger.warning("[LearningService] 加载指纹失败 %s: %s", file_path, e)

    def _save_to_disk(self, user_id: str) -> None:
        """保存指纹到磁盘"""
        fp = self.fingerprints.get(user_id)
        if not fp:
            return

        file_path = self.persist_dir / f"{user_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(fp.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug("[LearningService] 保存指纹: %s", user_id)
        except Exception as e:
            logger.error("[LearningService] 保存指纹失败 %s: %s", user_id, e)

    # ── 兼容 LearningEngine 的方法 ──

    def get_learned_constraints(self, user_id: str = "default") -> Dict:
        """获取学习到的约束（兼容旧接口）"""
        fp = self.fingerprints.get(user_id)
        if not fp:
            return {
                "style_patterns_count": 0,
                "word_preferences_count": 0,
                "anti_ai_patterns_count": 0,
                "feedback_count": 0,
                "top_patterns": [],
            }

        top_patterns = sorted(
            fp.preferred_words.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )[:5]

        return {
            "style_patterns_count": len(fp.sentence_patterns),
            "word_preferences_count": len(fp.preferred_words),
            "anti_ai_patterns_count": len(fp.anti_patterns),
            "feedback_count": fp.edit_count,
            "top_patterns": [
                {"pattern": word, "count": len(replacements)}
                for word, replacements in top_patterns
            ],
        }

    def apply_preference(self, content: str, user_id: str = "default") -> str:
        """应用风格偏好到内容（兼容旧接口）"""
        fp = self.fingerprints.get(user_id)
        if not fp:
            return content

        result = content

        # 移除 AI 味道
        for pattern in fp.anti_patterns:
            if pattern in result:
                import random
                # 查找是否有推荐替换
                replacements = fp.preferred_words.get(pattern, [])
                if replacements:
                    result = result.replace(pattern, random.choice(replacements))
                else:
                    # 简单处理：删除
                    result = result.replace(pattern, "")

        # 应用词汇偏好
        for word, preferred_words in fp.preferred_words.items():
            if word in result and preferred_words:
                import random
                result = result.replace(word, random.choice(preferred_words))

        return result
