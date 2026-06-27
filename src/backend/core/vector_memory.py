"""
向量记忆存储 — ChromaDB 持久化 + 语义检索
v5.3: 为 NovelMemory 提供持久化向量存储后端
"""
import logging
from typing import Dict, List, Optional, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


class VectorMemoryStore:
    """基于 ChromaDB 的向量记忆存储

    特性：
    - 持久化存储（重启不丢失）
    - 语义相似度搜索
    - 自动衰减（按时间加权）
    - 跨小说记忆复用
    """

    def __init__(self, persist_path: str = "./data/vector_memory", collection_name: str = "novel_memory"):
        self._persist_path = persist_path
        self._collection_name = collection_name
        self._client = None
        self._collection = None
        self._init_client()

    def _init_client(self):
        """初始化 ChromaDB 客户端"""
        try:
            self._client = chromadb.PersistentClient(
                path=self._persist_path,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"[VectorMemory] ChromaDB 初始化成功, 当前 {self._collection.count()} 条记忆")
        except Exception as e:
            logger.warning(f"[VectorMemory] ChromaDB 初始化失败，回退内存模式: {e}")
            self._client = None
            self._collection = None
            self._memory_cache: List[Dict] = []

    # ── 公共接口 ──

    def add_memory(self, text: str, metadata: Optional[Dict] = None,
                   memory_id: Optional[str] = None, novel_id: Optional[str] = None) -> str:
        """添加记忆项"""
        metadata = metadata or {}
        if novel_id:
            metadata["novel_id"] = novel_id
        metadata["timestamp"] = str(metadata.get("timestamp", ""))

        if self._collection is not None:
            import uuid
            memory_id = memory_id or str(uuid.uuid4())
            self._collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[memory_id],
            )
            logger.debug(f"[VectorMemory] 添加记忆: {memory_id[:8]}... ({len(text)}字)")
        else:
            memory_id = memory_id or f"mem_{len(self._memory_cache)}"
            self._memory_cache.append({"id": memory_id, "text": text, "metadata": metadata,
                                       "timestamp": metadata.get("timestamp", "")})

        return memory_id

    def search(self, query: str, top_k: int = 5, novel_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """语义搜索记忆"""
        if self._collection is not None:
            where_filter = {"novel_id": novel_id} if novel_id else None
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter,
            )
            items = []
            for i, doc_id in enumerate(results.get("ids", [[]])[0]):
                items.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                })
            return items
        else:
            # 回退：简单关键词匹配
            results = []
            for item in self._memory_cache:
                if novel_id and item.get("metadata", {}).get("novel_id") != novel_id:
                    continue
                score = self._simple_match(query, item["text"])
                if score > 0:
                    results.append({"id": item["id"], "text": item["text"],
                                    "metadata": item.get("metadata", {}), "score": score})
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

    def get_by_novel(self, novel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取指定小说的所有记忆"""
        if self._collection is not None:
            results = self._collection.get(
                where={"novel_id": novel_id},
                limit=limit,
            )
            items = []
            for i, doc_id in enumerate(results.get("ids", [])):
                items.append({
                    "id": doc_id,
                    "text": results["documents"][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][i] if results.get("metadatas") else {},
                })
            return items
        else:
            return [m for m in self._memory_cache
                    if m.get("metadata", {}).get("novel_id") == novel_id][:limit]

    def delete(self, memory_id: str):
        """删除记忆"""
        if self._collection is not None:
            self._collection.delete(ids=[memory_id])
        else:
            self._memory_cache = [m for m in self._memory_cache if m["id"] != memory_id]

    def clear_novel(self, novel_id: str):
        """清除指定小说的所有记忆"""
        if self._collection is not None:
            self._collection.delete(where={"novel_id": novel_id})
        else:
            self._memory_cache = [m for m in self._memory_cache
                                  if m.get("metadata", {}).get("novel_id") != novel_id]

    def count(self) -> int:
        """记忆总数"""
        if self._collection is not None:
            return self._collection.count()
        return len(self._memory_cache)

    def is_available(self) -> bool:
        """向量存储是否可用"""
        return self._collection is not None

    # ── 内部方法 ──

    def _simple_match(self, query: str, text: str) -> float:
        """简单关键词匹配（回退模式）"""
        query_words = set(query)
        text_words = set(text)
        if not query_words:
            return 0
        overlap = query_words & text_words
        return len(overlap) / len(query_words)


# 全局单例
_vector_store: Optional[VectorMemoryStore] = None


def get_vector_memory_store() -> VectorMemoryStore:
    """获取全局向量记忆存储实例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorMemoryStore()
    return _vector_store