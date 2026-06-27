"""
记忆系统 - 支持三层架构（工作记忆/短期/长期）+ 动态重要性评分
- 工作记忆：最近 3 章完整内容
- 短期记忆：章节摘要链
- 长期记忆：角色信息 / 世界观设定 / 未解决伏笔
- 动态重要性评分 = base_score * (1 + log(引用次数+1)) * 时间衰减系数

引用次数统计：用户在章节内容中提到某角色、地点、设定词的次数
时间衰减：每过 5 章衰减 0.9，避免早期记忆过度占用上下文窗口
"""
import math
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional


def estimate_tokens(text: str) -> int:
    """统一的 token 估算：中文 ~1.5 字/token，英文 ~4 字符/token。
    与 llm.client.LLMClient.estimate_tokens 保持同一口径，避免预算计算前后不一致。"""
    if not text:
        return 0
    chinese = sum(1 for c in text if "一" <= c <= "鿿")
    english = len(text) - chinese
    return int(chinese / 1.5 + english / 4) + 10


# 短期记忆（章节摘要链）最大保留条数，防止长篇小说下无限增长
_SHORT_TERM_MAX = 200


class ModelConfig:
    """LLM 模型上下文配置"""
    GPT_4O_CONTEXT = 128000
    GPT_4O_MINI_CONTEXT = 128000
    DEFAULT_CONTEXT = 128000


class ImportanceLevel:
    CRITICAL = 3.0   # 3.0 分 - 如主角 / 核心世界规则 / 主要冲突
    HIGH = 2.0       # 2.0 分 - 如重要配角 / 关键地点 / 近期伏笔
    MEDIUM = 1.0     # 1.0 分 - 普通角色 / 一般设定 / 近期摘要
    LOW = 0.5        # 0.5 分 - 边缘信息


class MemoryItem:
    """一条可评分的记忆项"""
    def __init__(self, tag: str, content: str, base_level: float = 1.0,
                 keywords: Optional[List[str]] = None, created_at: Optional[float] = None):
        self.tag = tag
        self.content = content
        self.base_level = base_level
        self.keywords = keywords or []
        self.reference_count = 0
        self.last_referenced_at = time.time()
        self.created_at = created_at or time.time()

    def score(self, chapter_index: int = 0, now: Optional[float] = None) -> float:
        """动态评分：基础分 * (1 + log(引用次数+1)) * 时间衰减"""
        now = now or time.time()
        # 引用次数奖励（对频繁被提到的记忆项加分）
        freq_bonus = 1.0 + math.log(self.reference_count + 1) * 0.5
        # 时间衰减（越久未被引用越低）
        hours_since = max(1, (now - self.last_referenced_at) / 3600)
        time_decay = math.pow(0.95, hours_since / 2)
        # 章节位置衰减（越早期的章节越低）
        chapter_decay = math.pow(0.97, max(0, chapter_index - 3))
        return self.base_level * freq_bonus * time_decay * chapter_decay

    def bump_reference(self, hits: int = 1):
        self.reference_count += hits
        self.last_referenced_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "content": self.content[:200],
            "score": self.score(),
            "reference_count": self.reference_count,
            "base_level": self.base_level,
        }


class NovelMemory:
    """小说记忆系统 - 三层架构 + 动态评分"""
    def __init__(self, model_context_size: int = 128000):
        self.model_context_size = model_context_size
        self.max_context_tokens = int(model_context_size * 0.6)
        # 三层记忆
        self.working_memory: List[str] = []      # 最近 5 章正文
        self.short_term_memory: List[Dict] = []  # 章节摘要（含章节序号）
        self.long_term_memory: Dict[str, List] = {
            "characters": [],      # 角色
            "world_settings": [],  # 世界观规则
            "foreshadowing": [],   # 未解决伏笔
        }
        # 评分器
        self.importance_cache: Dict[str, MemoryItem] = {}
        # 章节计数器
        self.chapter_count = 0
        # 统计
        self._stats: Dict[str, Any] = {}

    # ────────── 写入层 ──────────
    def update_with_chapter(self, title: str, content: str):
        """写入新章节，更新三层记忆 + 统计引用次数"""
        self.chapter_count += 1
        # 工作记忆（最近 3 章）
        snippet = f"[{title}] {content[:500]}..."
        self.working_memory.append(snippet)
        if len(self.working_memory) > 5:
            self.working_memory = self.working_memory[-5:]
        # 短期记忆（章节摘要）
        self.short_term_memory.append({
            "chapter_idx": self.chapter_count,
            "title": title,
            "summary": content[:500],
            "created_at": time.time(),
        })
        # 限制摘要链长度，避免长篇小说下内存无限增长（读取上下文只用最近若干章）
        if len(self.short_term_memory) > _SHORT_TERM_MAX:
            self.short_term_memory = self.short_term_memory[-_SHORT_TERM_MAX:]
        # 统计每个长期记忆项在新章节文本中的关键词命中
        self._update_reference_counts(content)

    def store_characters(self, characters):
        items = []
        for char in characters:
            if isinstance(char, dict):
                name = char.get("name", "未知")
                personality = char.get("personality", "")
                background = char.get("background", "")
                role = char.get("role", "配角")
            else:
                name = getattr(char, "name", "未知")
                personality = getattr(char, "personality", "")
                background = getattr(char, "background", "")
                role = getattr(char, "role", "配角")
            entry = {
                "id": f"char_{name}",
                "name": name,
                "personality": personality,
                "background": background,
                "role": role,
                "keywords": [name],  # 用于关键词命中统计
            }
            items.append(entry)
            # 重要性评分：主角 CRITICAL，配角 HIGH
            base = ImportanceLevel.CRITICAL if "主角" in str(role) or "main" in str(role).lower() else ImportanceLevel.HIGH
            self.importance_cache[entry["id"]] = MemoryItem(
                tag="character", content=f"{name} - {personality}",
                base_level=base, keywords=[name],
            )
        self.long_term_memory["characters"] = items

    def store_world_settings(self, settings):
        items = []
        for s in settings:
            if isinstance(s, dict):
                name = s.get("name", "未知")
                desc = s.get("description", "")
                rules = s.get("rules", [])
            else:
                name = getattr(s, "name", "未知")
                desc = getattr(s, "description", "")
                rules = getattr(s, "rules", [])
            entry = {
                "id": f"world_{name}",
                "name": name,
                "description": desc,
                "rules": rules,
                "keywords": [name] + list(rules)[:3],
            }
            items.append(entry)
            self.importance_cache[entry["id"]] = MemoryItem(
                tag="world", content=f"{name}: {desc}",
                base_level=ImportanceLevel.CRITICAL,
                keywords=[name] + [str(r)[:10] for r in rules],
            )
        self.long_term_memory["world_settings"] = items

    def add_foreshadowing(self, hint: str):
        entry = {
            "id": f"fs_{len(self.long_term_memory.get('foreshadowing', []))}",
            "text": hint,
            "created_at": time.time(),
            "keywords": [hint[:10]],
        }
        self.long_term_memory.setdefault("foreshadowing", []).append(entry)
        self.importance_cache[entry["id"]] = MemoryItem(
            tag="foreshadowing", content=hint, base_level=ImportanceLevel.HIGH,
            keywords=[hint[:10]],
        )

    def resolve_foreshadowing(self, hint_or_keyword: str):
        """标记伏笔已回收"""
        lst = self.long_term_memory.get("foreshadowing", [])
        for entry in lst:
            if hint_or_keyword in entry.get("text", ""):
                entry["resolved"] = True
                # 回收后的伏笔降权
                key = entry.get("id")
                if key in self.importance_cache:
                    self.importance_cache[key].base_level = ImportanceLevel.LOW

    def _update_reference_counts(self, text: str):
        """扫描文本中的关键词，提升匹配记忆项的引用次数"""
        if not text:
            return
        for key, item in self.importance_cache.items():
            hits = 0
            for kw in item.keywords:
                if kw and len(kw) >= 2 and kw in text:
                    hits += 1
            if hits > 0:
                item.bump_reference(hits)

    # ────────── 读取 & 构建上下文 ──────────
    def get_context(self, current_chapter_title: str = "") -> Dict[str, Any]:
        """构建上下文：根据评分从高到低，直到 token 预算用尽"""
        items: List[MemoryItem] = []
        now = time.time()

        # 1) 长期记忆：角色
        for c in self.long_term_memory.get("characters", []):
            key = c.get("id")
            base = self.importance_cache.get(key)
            text = f"角色: {c.get('name','')} - {c.get('personality','')} - {c.get('background','')}"
            level = base.score(chapter_index=self.chapter_count, now=now) if base else ImportanceLevel.HIGH
            items.append(MemoryItem(tag="character", content=text, base_level=level))
        # 2) 长期记忆：世界设定
        for w in self.long_term_memory.get("world_settings", []):
            key = w.get("id")
            base = self.importance_cache.get(key)
            rules_str = "；".join(w.get("rules", []) or [])
            text = f"世界观: {w.get('name','')} - {w.get('description','')} 规则: {rules_str}"
            level = base.score(chapter_index=self.chapter_count, now=now) if base else ImportanceLevel.CRITICAL
            items.append(MemoryItem(tag="world", content=text, base_level=level))
        # 3) 未解决伏笔
        unres = [f for f in self.long_term_memory.get("foreshadowing", []) if not f.get("resolved")]
        for f in unres[-10:]:
            items.append(MemoryItem(tag="foreshadowing", content=f"伏笔: {f.get('text','')}",
                                    base_level=ImportanceLevel.HIGH))
        # 4) 短期记忆：最近 5 章摘要
        recent = self.short_term_memory[-5:]
        for idx, sm in enumerate(recent):
            age_bonus = 1.0 - 0.1 * (len(recent) - idx - 1)  # 越近的章节越高
            items.append(MemoryItem(tag="summary",
                                    content=f"第{sm.get('chapter_idx','?')}章: {sm.get('title','')} - {sm.get('summary','')}",
                                    base_level=ImportanceLevel.HIGH * age_bonus))
        # 5) 工作记忆（最近章节片段）
        for idx, wm in enumerate(self.working_memory):
            items.append(MemoryItem(tag="working", content=f"近章: {wm}",
                                    base_level=ImportanceLevel.MEDIUM * (1.0 - 0.1 * idx)))

        # 排序：按动态评分从高到低
        items.sort(key=lambda it: it.score(chapter_index=self.chapter_count, now=now), reverse=True)

        # 逐行放入上下文，直到预算耗尽
        summaries, characters, world, foreshadowing = [], [], [], []
        tokens_used = 0
        for item in items:
            tokens_estimate = estimate_tokens(item.content) + 20
            if tokens_used + tokens_estimate > self.max_context_tokens:
                continue
            tokens_used += tokens_estimate
            if item.tag == "character":
                characters.append(item.content)
            elif item.tag == "world":
                world.append(item.content)
            elif item.tag == "foreshadowing":
                foreshadowing.append(item.content)
            else:
                summaries.append(item.content)

        # 统计
        self._stats = {
            "total_items_scored": len(items),
            "tokens_budget": self.max_context_tokens,
            "tokens_used": tokens_used,
            "included_characters": len(characters),
            "included_world": len(world),
            "included_summaries": len(summaries),
            "included_foreshadowing": len(foreshadowing),
            "model_context_size": self.model_context_size,
            "chapter_count": self.chapter_count,
        }

        return {
            "summaries": summaries,
            "characters": characters,
            "world": world,
            "foreshadowing": foreshadowing,
            "context_budget": self.max_context_tokens,
            "current_chapter": current_chapter_title,
        }

    def get_context_stats(self) -> Dict[str, Any]:
        return self._stats or {
            "model_context_size": self.model_context_size,
            "max_context_tokens": self.max_context_tokens,
            "cached_importance_count": len(self.importance_cache),
            "working_memory_count": len(self.working_memory),
            "summary_chain_length": len(self.short_term_memory),
            "characters_count": len(self.long_term_memory.get("characters", [])),
            "world_settings_count": len(self.long_term_memory.get("world_settings", [])),
            "unresolved_foreshadowing": sum(1 for f in self.long_term_memory.get("foreshadowing", []) if not f.get("resolved")),
            "chapters_processed": self.chapter_count,
        }

    def top_items(self, limit: int = 10) -> List[Dict]:
        """查看当前最重要的记忆项（调试用）"""
        items = list(self.importance_cache.values())
        items.sort(key=lambda it: it.score(chapter_index=self.chapter_count), reverse=True)
        return [it.to_dict() for it in items[:limit]]

    # ── 语义检索（TF-IDF 轻量级实现，无需 ChromaDB）──

    def _tokenize(self, text: str) -> List[str]:
        """中文分词简化版：2-gram + 单字"""
        # 提取中文词
        chinese = re.findall(r'[\u4e00-\u9fff]+', text)
        tokens = []
        for seg in chinese:
            # 2-gram
            for i in range(len(seg) - 1):
                tokens.append(seg[i:i+2])
            # 3-gram（长词）
            for i in range(len(seg) - 2):
                tokens.append(seg[i:i+3])
        return tokens

    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        语义搜索：基于 TF-IDF 计算查询与所有记忆项的相似度
        返回 top_k 最相关的记忆项
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 构建文档集合
        documents = []
        for key, item in self.importance_cache.items():
            doc_tokens = self._tokenize(item.content)
            doc_tokens += self._tokenize(" ".join(item.keywords))
            documents.append({"id": key, "item": item, "tokens": doc_tokens})

        # TF-IDF 计算（简化版：TF * IDF 近似）
        doc_count = len(documents)
        scores = []
        for doc in documents:
            if not doc["tokens"]:
                continue
            # 计算查询在文档中的 TF-IDF 分数
            score = 0.0
            for qt in query_tokens:
                tf = doc["tokens"].count(qt) / max(len(doc["tokens"]), 1)
                # IDF: 多少文档包含这个词
                df = sum(1 for d in documents if qt in (d.get("tokens") or []))
                idf = math.log((doc_count + 1) / (df + 1)) + 1
                score += tf * idf
            if score > 0:
                scores.append({
                    **doc["item"].to_dict(),
                    "id": doc["id"],
                    "similarity": round(score, 4),
                })

        scores.sort(key=lambda x: -x["similarity"])
        return scores[:top_k]

    def search_by_keyword(self, keyword: str) -> List[Dict]:
        """
        关键词精确搜索（比语义搜索更快，用于角色名/地名查找）
        """
        results = []
        for key, item in self.importance_cache.items():
            if keyword in item.content or any(keyword in kw for kw in item.keywords):
                results.append({
                    **item.to_dict(),
                    "id": key,
                })
        return results

    def reset(self):
        """清空所有记忆，用于新小说开始时重置"""
        self.working_memory.clear()
        self.short_term_memory.clear()
        self.long_term_memory = {
            "characters": [],
            "world_settings": [],
            "foreshadowing": [],
        }
        self.importance_cache.clear()
        self.chapter_count = 0
        self._stats.clear()

    def __repr__(self) -> str:
        return (f"NovelMemory(chapters={self.chapter_count}, "
                f"budget={self.max_context_tokens} tokens, "
                f"items={len(self.importance_cache)})")
