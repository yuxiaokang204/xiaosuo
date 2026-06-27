"""
基于 ChromaDB 的语义记忆服务 - L3 工具层增强版
提供向量化存储、语义检索、上下文构建、多集合管理等功能
"""
import os
import uuid
import json
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 常量 ──

DEFAULT_MAX_CONTEXT_TOKENS = 76800  # 128K * 0.6
COLLECTION_SPECS = [
    ("working_memory", "最近5章完整内容"),
    ("short_term_memory", "章节摘要链"),
    ("long_term_characters", "角色档案"),
    ("long_term_world", "世界观设定"),
    ("long_term_foreshadowing", "伏笔追踪"),
]


# ── 数据模型 ──

@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    collection: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "collection": self.collection,
        }


@dataclass
class TokenBudget:
    """Token 预算追踪"""
    max_tokens: int
    used_tokens: int = 0

    @property
    def remaining(self) -> int:
        return self.max_tokens - self.used_tokens

    def can_fit(self, tokens: int) -> bool:
        return self.remaining > 0 and tokens <= self.remaining

    def consume(self, tokens: int) -> None:
        self.used_tokens += tokens


# ── Token 估算 ──

def estimate_tokens(text: str) -> int:
    """简单中文 Token 估算（用于预算控制）"""
    if not text:
        return 0
    chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    english = len(text) - chinese
    return int(chinese / 1.5 + english / 4) + 10


# ── MemoryService ──

class MemoryService:
    """
    基于 ChromaDB 的语义记忆服务（L3 工具层）
    
    功能:
    - 5 个语义集合：工作记忆、短期记忆、角色/世界观/伏笔长期记忆
    - 按小说隔离存储
    - 自动向量检索相关章节
    - 构建章节上下文（Token 预算控制）
    - 降级到内存模式（无 ChromaDB 时）
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_data",
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    ):
        self.persist_directory = persist_directory
        self.max_context_tokens = max_context_tokens
        self._client = None
        self._collections: Dict[str, Any] = {}
        self._initialized = False
        # 内存回退存储：{novel_id: {collection: [MemoryEntry]}}
        self._fallback_store: Dict[str, Dict[str, List[MemoryEntry]]] = {}

    # ── 初始化 ──

    async def initialize(self):
        """初始化 ChromaDB 连接和多集合（异步包装）"""
        if self._initialized:
            return
        try:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(allow_reset=True),
            )

            # 创建 5 个集合
            for collection_name, description in COLLECTION_SPECS:
                collection = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine", "description": description},
                )
                self._collections[collection_name] = collection

            self._initialized = True
            logger.info("[MemoryService] ✅ ChromaDB 初始化成功: %s", self.persist_directory)
        except ImportError:
            logger.warning("[MemoryService] ⚠️ chromadb 未安装，使用内存回退模式")
            self._initialized = True
        except Exception as e:
            logger.warning("[MemoryService] ⚠️ ChromaDB 初始化失败: %s，使用内存回退模式", e)
            self._initialized = True

    def _ensure_initialized(self):
        """同步确保初始化完成"""
        if not self._initialized:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在运行事件循环中，异步调用需使用 create_task 外部包装
                raise RuntimeError("MemoryService 未初始化，请先 await initialize()")
            loop.run_until_complete(self.initialize())

    # ── 存储接口 ──

    async def store_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        存储章节到工作记忆和短期记忆
        
        Args:
            novel_id: 小说 ID
            chapter_id: 章节 ID
            content: 章节完整内容
            metadata: 附加元数据（章节标题、字数、索引等）
        """
        self._ensure_initialized()
        entry_id = f"ch_{novel_id}_{chapter_id}"

        if not self._client:
            return self._fallback_store_chapter(novel_id, chapter_id, content, metadata)

        try:
            # 存储到工作记忆（完整内容）
            meta = {**(metadata or {}), "novel_id": novel_id, "type": "chapter", "ts": time.time()}
            self._collections["working_memory"].add(
                documents=[content],
                metadatas=[meta],
                ids=[entry_id],
            )
            logger.debug("[MemoryService] 存储到工作记忆: %s", entry_id)

            # 存储到短期记忆（摘要）
            summary = self._generate_summary(content, chapter_id, metadata)
            short_id = f"st_{novel_id}_{chapter_id}"
            self._collections["short_term_memory"].add(
                documents=[summary],
                metadatas=[{**(metadata or {}), "novel_id": novel_id, "type": "summary", "ts": time.time()}],
                ids=[short_id],
            )
            logger.debug("[MemoryService] 存储到短期记忆: %s", short_id)

            return entry_id
        except Exception as e:
            logger.error("[MemoryService] 存储章节失败: %s，回退到内存模式", e)
            return self._fallback_store_chapter(novel_id, chapter_id, content, metadata)

    async def store_character(
        self,
        novel_id: str,
        char_id: str,
        character_data: Dict[str, Any],
    ) -> str:
        """存储角色到长期记忆"""
        self._ensure_initialized()
        entry_id = f"char_{novel_id}_{char_id}"

        if not self._client:
            return self._fallback_store_character(novel_id, char_id, character_data)

        try:
            content = json.dumps(character_data, ensure_ascii=False)
            meta = {
                "novel_id": novel_id,
                "char_id": char_id,
                "name": character_data.get("name", ""),
                "role": character_data.get("role", ""),
                "type": "character",
                "ts": time.time(),
            }
            self._collections["long_term_characters"].add(
                documents=[content],
                metadatas=[meta],
                ids=[entry_id],
            )
            logger.debug("[MemoryService] 存储角色: %s (%s)", entry_id, character_data.get("name", ""))
            return entry_id
        except Exception as e:
            logger.error("[MemoryService] 存储角色失败: %s", e)
            return self._fallback_store_character(novel_id, char_id, character_data)

    async def store_world_setting(
        self,
        novel_id: str,
        world_id: str,
        world_data: Dict[str, Any],
    ) -> str:
        """存储世界观到长期记忆"""
        self._ensure_initialized()
        entry_id = f"world_{novel_id}_{world_id}"

        if not self._client:
            return self._fallback_store_world(novel_id, world_id, world_data)

        try:
            content = json.dumps(world_data, ensure_ascii=False)
            meta = {
                "novel_id": novel_id,
                "world_id": world_id,
                "name": world_data.get("name", ""),
                "category": world_data.get("category", ""),
                "type": "world",
                "ts": time.time(),
            }
            self._collections["long_term_world"].add(
                documents=[content],
                metadatas=[meta],
                ids=[entry_id],
            )
            logger.debug("[MemoryService] 存储世界观: %s (%s)", entry_id, world_data.get("name", ""))
            return entry_id
        except Exception as e:
            logger.error("[MemoryService] 存储世界观失败: %s", e)
            return self._fallback_store_world(novel_id, world_id, world_data)

    async def add_foreshadowing(
        self,
        novel_id: str,
        hint: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """添加伏笔到长期记忆"""
        self._ensure_initialized()
        entry_id = f"foreshadow_{novel_id}_{uuid.uuid4().hex[:8]}"

        if not self._client:
            return self._fallback_store_foreshadow(novel_id, hint, metadata)

        try:
            meta = {
                **(metadata or {}),
                "novel_id": novel_id,
                "type": "foreshadowing",
                "hint": hint[:100],
                "ts": time.time(),
            }
            self._collections["long_term_foreshadowing"].add(
                documents=[hint],
                metadatas=[meta],
                ids=[entry_id],
            )
            logger.debug("[MemoryService] 添加伏笔: %s", entry_id)
            return entry_id
        except Exception as e:
            logger.error("[MemoryService] 添加伏笔失败: %s", e)
            return self._fallback_store_foreshadow(novel_id, hint, metadata)

    # ── 检索接口 ──

    async def semantic_search(
        self,
        novel_id: str,
        query: str,
        top_k: int = 5,
        collection: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        语义搜索（默认在所有集合中搜索）
        
        Args:
            novel_id: 小说 ID（用于过滤）
            query: 搜索查询
            top_k: 返回结果数量
            collection: 指定集合（None=搜索所有）
            filters: 额外过滤条件
        """
        self._ensure_initialized()

        if not self._client:
            return self._fallback_search(novel_id, query, top_k, collection, filters)

        try:
            all_results = []

            # 确定搜索范围
            if collection:
                search_collections = {collection: self._collections[collection]}
            else:
                search_collections = self._collections

            # 基础过滤条件（所有查询都加 novel_id）
            base_filters = {"novel_id": novel_id}
            if filters:
                base_filters.update(filters)

            for col_name, col in search_collections.items():
                if col_name.startswith("long_term_"):
                    # 长期记忆也加类型过滤
                    type_filter = base_filters.copy()
                    type_filter["type"] = col_name.replace("long_term_", "")
                else:
                    type_filter = base_filters.copy()

                try:
                    result = col.query(
                        query_texts=[query],
                        n_results=min(top_k, 10),
                        where=type_filter if type_filter else None,
                        include=["documents", "metadatas", "distances"],
                    )

                    for i in range(len(result["ids"][0])):
                        all_results.append({
                            "id": result["ids"][0][i],
                            "content": result["documents"][0][i],
                            "metadata": result["metadatas"][0][i],
                            "collection": col_name,
                            "distance": result["distances"][0][i],
                            "similarity": round(1.0 - result["distances"][0][i], 4),
                        })
                except Exception as e:
                    logger.warning("[MemoryService] 搜索集合 %s 失败: %s", col_name, e)

            # 按相似度排序
            all_results.sort(key=lambda x: -x["similarity"])
            return all_results[:top_k]

        except Exception as e:
            logger.error("[MemoryService] 搜索失败: %s，回退到内存模式", e)
            return self._fallback_search(novel_id, query, top_k, collection, filters)

    async def get_context(
        self,
        novel_id: str,
        chapter_idx: int,
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> Dict[str, Any]:
        """
        构建章节上下文（自动向量检索相关章节）
        
        流程:
        1. 从工作记忆获取最近 N 章
        2. 从短期记忆获取章节摘要
        3. 从长期记忆检索相关角色/世界观/伏笔
        4. 按重要性排序，直到 Token 预算用尽
        
        Returns:
            {
                "recent_chapters": [...],
                "summaries": [...],
                "characters": [...],
                "world_settings": [...],
                "foreshadowing": [...],
                "token_usage": {"used": N, "max": M},
            }
        """
        self._ensure_initialized()
        budget = TokenBudget(max_tokens=max_tokens)

        try:
            # 1. 获取最近章节（从工作记忆）
            recent_chapters = []
            for i in range(max(0, chapter_idx - 4), chapter_idx + 1):
                chapter_content = await self._get_chapter_at_index(novel_id, i)
                if chapter_content:
                    tokens = estimate_tokens(chapter_content)
                    if budget.can_fit(tokens):
                        recent_chapters.append({
                            "index": i,
                            "content": chapter_content,
                            "tokens": tokens,
                        })
                        budget.consume(tokens)

            # 2. 获取章节摘要（从短期记忆）
            summaries = []
            search_result = await self.semantic_search(
                novel_id,
                f"chapter summary section {chapter_idx}",
                top_k=3,
                collection="short_term_memory",
            )
            for item in search_result:
                tokens = estimate_tokens(item["content"])
                if budget.can_fit(tokens):
                    summaries.append(item)
                    budget.consume(tokens)

            # 3. 从长期记忆检索相关角色
            characters = []
            char_search = await self.semantic_search(
                novel_id,
                "character personality description background",
                top_k=5,
                collection="long_term_characters",
            )
            for item in char_search:
                tokens = estimate_tokens(item["content"])
                if budget.can_fit(tokens):
                    characters.append(item)
                    budget.consume(tokens)

            # 4. 从长期记忆检索相关世界观
            world_settings = []
            world_search = await self.semantic_search(
                novel_id,
                "world setting rules environment",
                top_k=3,
                collection="long_term_world",
            )
            for item in world_search:
                tokens = estimate_tokens(item["content"])
                if budget.can_fit(tokens):
                    world_settings.append(item)
                    budget.consume(tokens)

            # 5. 从长期记忆检索相关伏笔
            foreshadowing = []
            hint_search = await self.semantic_search(
                novel_id,
                "foreshadowing hint clue suspense",
                top_k=3,
                collection="long_term_foreshadowing",
            )
            for item in hint_search:
                tokens = estimate_tokens(item["content"])
                if budget.can_fit(tokens):
                    foreshadowing.append(item)
                    budget.consume(tokens)

            logger.info(
                "[MemoryService] 构建章节 %d 上下文，使用 Token: %d/%d",
                chapter_idx, budget.used_tokens, max_tokens,
            )

            return {
                "recent_chapters": recent_chapters,
                "summaries": summaries,
                "characters": characters,
                "world_settings": world_settings,
                "foreshadowing": foreshadowing,
                "token_usage": {
                    "used": budget.used_tokens,
                    "max": max_tokens,
                    "remaining": budget.remaining,
                },
            }

        except Exception as e:
            logger.error("[MemoryService] 构建上下文失败: %s", e)
            return {
                "recent_chapters": [],
                "summaries": [],
                "characters": [],
                "world_settings": [],
                "foreshadowing": [],
                "token_usage": {"used": 0, "max": max_tokens, "remaining": max_tokens},
                "error": str(e),
            }

    async def get_stats(self, novel_id: str) -> Dict[str, Any]:
        """获取记忆统计"""
        self._ensure_initialized()

        if not self._client:
            return self._fallback_stats(novel_id)

        try:
            stats = {"novel_id": novel_id, "collections": {}}
            for col_name in self._collections:
                try:
                    count = self._collections[col_name].count()
                    # 过滤该小说的记忆
                    filter_result = self._collections[col_name].get(
                        where={"novel_id": novel_id},
                        limit=1,
                    )
                    # 获取全部计数来估算
                    all_count = self._collections[col_name].count()
                    stats["collections"][col_name] = {
                        "total": all_count,
                        "novel_entries": len(filter_result["ids"]) if filter_result["ids"] else 0,
                    }
                except Exception:
                    stats["collections"][col_name] = {"error": "query_failed"}

            return stats
        except Exception as e:
            logger.error("[MemoryService] 获取统计失败: %s", e)
            return {"novel_id": novel_id, "error": str(e)}

    async def reset(self, novel_id: Optional[str] = None):
        """
        重置记忆（指定小说或全部）
        
        Args:
            novel_id: 重置指定小说的记忆，None=重置全部
        """
        self._ensure_initialized()

        if novel_id and self._client:
            # 删除指定小说的所有条目
            for col in self._collections.values():
                try:
                    col.delete(where={"novel_id": novel_id})
                    logger.info("[MemoryService] 重置小说记忆: %s", novel_id)
                except Exception as e:
                    logger.error("[MemoryService] 删除失败: %s", e)
        elif not novel_id and self._client:
            # 清空所有集合
            for col_name, col in self._collections.items():
                try:
                    col.delete(where={})
                    logger.info("[MemoryService] 清空集合: %s", col_name)
                except Exception as e:
                    logger.error("[MemoryService] 清空失败: %s", e)
            self._fallback_store.clear()
            logger.info("[MemoryService] 重置全部记忆完成")

    # ── 辅助方法 ──

    def _generate_summary(self, content: str, chapter_id: str, metadata: Optional[Dict] = None) -> str:
        """
        生成章节摘要（轻量版，用于短期记忆）
        
        取章节关键段落+元数据构建摘要
        """
        title = (metadata or {}).get("title", "")
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        # 取前 3 段和后 2 段 + 中间每 5 段取 1 段
        summary_lines = []
        if lines:
            summary_lines.extend(lines[:3])
            if len(lines) > 10:
                summary_lines.append("...")
                for i in range(5, len(lines) - 2, 5):
                    summary_lines.append(lines[i][:200])
            summary_lines.extend(lines[-2:])

        summary = "\n".join(summary_lines)[:3000]
        return f"[章节 {chapter_id}{f': {title}' if title else ''}]\n{summary}"

    async def _get_chapter_at_index(self, novel_id: str, chapter_idx: int) -> Optional[str]:
        """
        获取指定索引章节的内容
        
        从工作记忆中搜索章节索引匹配的条目
        """
        results = await self.semantic_search(
            novel_id,
            f"chapter {chapter_idx}",
            top_k=1,
            collection="working_memory",
            filters={"chapter_index": chapter_idx},
        )
        if results:
            return results[0].get("content")

        # 备用方案：用 chapter_id 模式匹配
        results = await self.semantic_search(
            novel_id,
            "content",
            top_k=10,
            collection="working_memory",
        )
        for r in results:
            meta = r.get("metadata", {})
            if meta.get("chapter_index") == chapter_idx:
                return r.get("content")
        return None

    # ── 内存回退实现 ──

    def _get_or_create_store(self, novel_id: str) -> Dict[str, List[MemoryEntry]]:
        if novel_id not in self._fallback_store:
            self._fallback_store[novel_id] = {col: [] for col in [c[0] for c in COLLECTION_SPECS]}
        return self._fallback_store[novel_id]

    def _fallback_store_chapter(
        self, novel_id: str, chapter_id: str, content: str, metadata: Optional[Dict] = None
    ) -> str:
        store = self._get_or_create_store(novel_id)
        entry_id = f"ch_{novel_id}_{chapter_id}"
        meta = {**(metadata or {}), "novel_id": novel_id, "type": "chapter"}
        store["working_memory"].append(
            MemoryEntry(id=entry_id, content=content, metadata=meta, collection="working_memory")
        )
        summary = self._generate_summary(content, chapter_id, metadata)
        store["short_term_memory"].append(
            MemoryEntry(
                id=f"st_{novel_id}_{chapter_id}",
                content=summary,
                metadata={**meta, "type": "summary"},
                collection="short_term_memory",
            )
        )
        return entry_id

    def _fallback_store_character(
        self, novel_id: str, char_id: str, character_data: Dict[str, Any]
    ) -> str:
        store = self._get_or_create_store(novel_id)
        entry_id = f"char_{novel_id}_{char_id}"
        content = json.dumps(character_data, ensure_ascii=False)
        meta = {
            "novel_id": novel_id,
            "char_id": char_id,
            "name": character_data.get("name", ""),
            "type": "character",
        }
        store["long_term_characters"].append(
            MemoryEntry(id=entry_id, content=content, metadata=meta, collection="long_term_characters")
        )
        return entry_id

    def _fallback_store_world(
        self, novel_id: str, world_id: str, world_data: Dict[str, Any]
    ) -> str:
        store = self._get_or_create_store(novel_id)
        entry_id = f"world_{novel_id}_{world_id}"
        content = json.dumps(world_data, ensure_ascii=False)
        meta = {
            "novel_id": novel_id,
            "world_id": world_id,
            "name": world_data.get("name", ""),
            "type": "world",
        }
        store["long_term_world"].append(
            MemoryEntry(id=entry_id, content=content, metadata=meta, collection="long_term_world")
        )
        return entry_id

    def _fallback_store_foreshadow(
        self, novel_id: str, hint: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        store = self._get_or_create_store(novel_id)
        entry_id = f"foreshadow_{novel_id}_{uuid.uuid4().hex[:8]}"
        meta = {**(metadata or {}), "novel_id": novel_id, "hint": hint[:100], "type": "foreshadowing"}
        store["long_term_foreshadowing"].append(
            MemoryEntry(id=entry_id, content=hint, metadata=meta, collection="long_term_foreshadowing")
        )
        return entry_id

    def _fallback_search(
        self,
        novel_id: str,
        query: str,
        top_k: int = 5,
        collection: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """简单的关键词匹配回退"""
        import jieba
        query_terms = set(jieba.lcut(query))
        if not query_terms:
            return []

        all_scores = []
        search_collections = [collection] if collection else [c[0] for c in COLLECTION_SPECS]

        for col_name in search_collections:
            for store_dict in self._fallback_store.values():
                if novel_id not in store_dict:
                    continue
                entries = store_dict.get(col_name, [])
                for entry in entries:
                    if entry.metadata.get("novel_id") != novel_id:
                        continue
                    content_terms = set(jieba.lcut(entry.content))
                    overlap = len(query_terms & content_terms)
                    if overlap > 0:
                        all_scores.append({
                            "id": entry.id,
                            "content": entry.content,
                            "metadata": entry.metadata,
                            "collection": col_name,
                            "similarity": overlap / max(len(query_terms), 1),
                        })

        all_scores.sort(key=lambda x: -x["similarity"])
        return all_scores[:top_k]

    def _fallback_stats(self, novel_id: str) -> Dict[str, Any]:
        store = self._fallback_store.get(novel_id, {})
        return {
            "novel_id": novel_id,
            "engine": "fallback",
            "collections": {
                col: len(entries) for col, entries in store.items()
            },
            "note": "ChromaDB 不可用，使用内存回退",
        }
