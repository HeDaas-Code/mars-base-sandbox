"""
记忆检索模块
基于 ChromaDB 单库 + metadata 过滤实现 NPC 记忆系统

metadata schema:
- agent_id: str        — 所属 NPC
- memory_type: str     — episodic / semantic
- timestamp: str       — 发生时间（Sol 编号）
- importance: float    — 重要度 0.0-1.0
- tags: str            — 标签（逗号分隔）
"""

import os
import uuid
from typing import List, Dict, Optional

import chromadb
from chromadb.config import Settings


class MemoryStore:
    """ChromaDB 记忆存储，单库 + agent_id metadata 过滤"""

    def __init__(self, persist_dir: str, collection_name: str = "heracles_memories"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "description": "赫拉克勒斯协议 - NPC 记忆库",
                "hnsw:space": "cosine",
            },
        )

    def add_memory(
        self,
        agent_id: str,
        content: str,
        memory_type: str = "episodic",
        timestamp: str = "Sol-100",
        importance: float = 0.5,
        tags: List[str] = None,
        emotional_intensity: float = 0.5,
        event_type: str = "episodic",
        memory_id: Optional[str] = None,
    ) -> str:
        """添加一条记忆

        Args:
            emotional_intensity: 情感强度 0.0-1.0（接口规范 §1）
            event_type: 事件类型枚举（接口规范 §2）
        """
        mem_id = memory_id or f"{agent_id}_{uuid.uuid4().hex[:8]}"
        metadata = {
            "agent_id": agent_id,
            "memory_type": memory_type,
            "timestamp": timestamp,
            "importance": importance,
            "emotional_intensity": emotional_intensity,
            "event_type": event_type,
            "tags": ",".join(tags) if tags else "",
        }

        self.collection.add(
            ids=[mem_id],
            documents=[content],
            metadatas=[metadata],
        )
        return mem_id

    def retrieve(
        self,
        agent_id: str,
        query: str,
        top_k: int = 3,
        memory_type: Optional[str] = None,
    ) -> List[Dict]:
        """检索记忆，按 agent_id 过滤

        检索排序公式（接口规范 §1.3）:
            final_score = relevance_score * retrieval_weight(emotional_intensity)
        """
        where_filter = {"agent_id": agent_id}
        if memory_type:
            where_filter = {
                "$and": [
                    {"agent_id": agent_id},
                    {"memory_type": memory_type},
                ]
            }

        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
        )

        memories = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                distance = results["distances"][0][i] if results.get("distances") else 0
                # cosine 距离: 0=完全相似, 2=完全不同
                # relevance = 1 - distance/2, 映射到 [0, 1]
                relevance = max(0.0, 1.0 - distance / 2)

                # 应用 emotional_intensity 检索权重（接口规范 §1.2）
                ei = meta.get("emotional_intensity", 0.5)
                weight = _retrieval_weight(ei)
                final_score = relevance * weight

                memories.append({
                    "content": doc,
                    "metadata": meta,
                    "relevance": relevance,
                    "final_score": final_score,
                })

            # 按 final_score 降序排列
            memories.sort(key=lambda m: m["final_score"], reverse=True)

        return memories

    def get_all_memories(self, agent_id: Optional[str] = None) -> List[Dict]:
        """获取所有记忆（调试用）"""
        where_filter = {"agent_id": agent_id} if agent_id else None
        results = self.collection.get(where=where_filter)
        memories = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"]):
                meta = results["metadatas"][i] if results.get("metadatas") else {}
                memories.append({
                    "id": results["ids"][i],
                    "content": doc,
                    "metadata": meta,
                })
        return memories

    def count(self, agent_id: Optional[str] = None) -> int:
        """获取记忆条数"""
        where_filter = {"agent_id": agent_id} if agent_id else None
        results = self.collection.get(where=where_filter)
        return len(results.get("ids", [])) if results else 0

    # ------------------------------------------------------------
    # 扩展方法（云逸 review P2 #8）
    # ------------------------------------------------------------

    def update_memory(
        self, mem_id: str, content: str, metadata: Optional[Dict] = None
    ) -> bool:
        """更新已有记忆的内容和/或 metadata"""
        try:
            self.collection.update(
                ids=[mem_id],
                documents=[content],
                metadatas=[metadata] if metadata else None,
            )
            return True
        except Exception as e:
            print(f"[WARN] 更新记忆失败 {mem_id}: {e}")
            return False

    def delete_memory(self, mem_id: str) -> bool:
        """删除指定记忆（记忆衰减/遗忘）"""
        try:
            self.collection.delete(ids=[mem_id])
            return True
        except Exception as e:
            print(f"[WARN] 删除记忆失败 {mem_id}: {e}")
            return False

    def batch_add(self, memories: List[Dict]) -> List[str]:
        """批量写入记忆（种子加载效率）

        Args:
            memories: [{"agent_id", "content", "memory_type",
                       "timestamp", "importance", "emotional_intensity",
                       "event_type", "tags", "memory_id"}]
        Returns:
            写入的 memory_id 列表
        """
        ids, docs, metas = [], [], []
        for m in memories:
            mid = m.get("memory_id") or f"{m['agent_id']}_{uuid.uuid4().hex[:8]}"
            ids.append(mid)
            docs.append(m["content"])
            metas.append({
                "agent_id": m["agent_id"],
                "memory_type": m.get("memory_type", "episodic"),
                "timestamp": m.get("timestamp", "Sol-100"),
                "importance": m.get("importance", 0.5),
                "emotional_intensity": m.get("emotional_intensity", 0.5),
                "event_type": m.get("event_type", "episodic"),
                "tags": ",".join(m["tags"]) if m.get("tags") else "",
            })
        if ids:
            self.collection.add(ids=ids, documents=docs, metadatas=metas)
        return ids


# ============================================================
# 模块级工具函数
# ============================================================

def _retrieval_weight(emotional_intensity: float) -> float:
    """根据 emotional_intensity 返回检索权重（接口规范 §1.2）

    | 区间     | 语义     | 权重 |
    |----------|----------|------|
    | 0.0-0.2  | 冷记忆   | ×0.8 |
    | 0.2-0.4  | 低情感   | ×1.0 |
    | 0.4-0.6  | 中情感   | ×1.2 |
    | 0.6-0.8  | 高情感   | ×1.5 |
    | 0.8-1.0  | 极高情感 | ×2.0 |
    """
    if emotional_intensity >= 0.8:
        return 2.0
    elif emotional_intensity >= 0.6:
        return 1.5
    elif emotional_intensity >= 0.4:
        return 1.2
    elif emotional_intensity >= 0.2:
        return 1.0
    else:
        return 0.8


# 全局 MemoryStore 实例（懒加载）
_memory_store: MemoryStore = None


def get_memory_store(persist_dir: str = None, collection_name: str = None) -> MemoryStore:
    """获取全局 MemoryStore 实例（懒加载）

    首次调用时从 config 初始化，后续调用返回同一实例。
    """
    global _memory_store
    if _memory_store is None:
        from .config import config
        _memory_store = MemoryStore(
            persist_dir=persist_dir or config.chroma_persist_dir,
            collection_name=collection_name or config.chroma_collection_name,
        )
    return _memory_store


def format_memories_for_prompt(memories: List[Dict]) -> str:
    """将检索到的记忆格式化为 Prompt 上下文"""
    if not memories:
        return "（无相关记忆）"

    lines = []
    for mem in memories:
        meta = mem.get("metadata", {})
        ts = meta.get("timestamp", "?")
        imp = meta.get("importance", 0)
        ei = meta.get("emotional_intensity", 0.5)
        etype = meta.get("event_type", "episodic")
        tags = meta.get("tags", "")
        content = mem["content"]
        lines.append(
            f"[{ts} | imp:{imp:.1f} ei:{ei:.1f} {etype} | {tags}] {content}"
        )

    return "\n".join(lines)
