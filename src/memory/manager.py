"""
Memory System - Agent Memory and Knowledge Management

Provides working memory, archival memory, and knowledge retrieval.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.db.session import get_db
from src.db.models import MemoryModel, ArchivalMemoryModel
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages agent memory: working, episodic, and semantic."""
    
    def __init__(self):
        self._working_memory: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
    
    # ==================== WORKING MEMORY ====================
    
    async def set_working_memory(
        self,
        session_id: str,
        key: str,
        value: Any,
        ttl: int = None,
    ) -> None:
        """Set a value in working memory."""
        if session_id not in self._working_memory:
            self._working_memory[session_id] = {}
        
        self._working_memory[session_id][key] = {
            "value": value,
            "updated_at": datetime.utcnow(),
            "ttl": ttl or self._cache_ttl,
        }
        
        # Persist to database
        await self._persist_memory(session_id, key, value)
    
    async def get_working_memory(
        self,
        session_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a value from working memory."""
        # Check cache first
        if session_id in self._working_memory:
            entry = self._working_memory[session_id].get(key)
            if entry:
                return entry["value"]
        
        # Fallback to database
        return await self._load_memory(session_id, key, default)
    
    async def delete_working_memory(self, session_id: str, key: str) -> bool:
        """Delete a key from working memory."""
        if session_id in self._working_memory:
            if key in self._working_memory[session_id]:
                del self._working_memory[session_id][key]
                await self._delete_memory(session_id, key)
                return True
        return False
    
    async def clear_working_memory(self, session_id: str) -> None:
        """Clear all working memory for a session."""
        if session_id in self._working_memory:
            del self._working_memory[session_id]
        await self._clear_session_memories(session_id)
    
    async def _persist_memory(self, session_id: str, key: str, value: Any) -> None:
        """Persist memory to database."""
        try:
            async for db in get_db():
                from sqlalchemy import select
                result = await db.execute(
                    select(MemoryModel).where(
                        MemoryModel.session_id == session_id,
                        MemoryModel.key == key,
                    )
                )
                memory = result.scalar_one_or_none()
                
                if memory:
                    memory.value = json.dumps(value)
                    memory.updated_at = datetime.utcnow()
                else:
                    memory = MemoryModel(
                        session_id=session_id,
                        key=key,
                        value=json.dumps(value),
                    )
                    db.add(memory)
                
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to persist memory: {e}")
    
    async def _load_memory(self, session_id: str, key: str, default: Any = None) -> Any:
        """Load memory from database."""
        try:
            async for db in get_db():
                from sqlalchemy import select
                result = await db.execute(
                    select(MemoryModel).where(
                        MemoryModel.session_id == session_id,
                        MemoryModel.key == key,
                    )
                )
                memory = result.scalar_one_or_none()
                
                if memory:
                    value = json.loads(memory.value)
                    # Cache it
                    if session_id not in self._working_memory:
                        self._working_memory[session_id] = {}
                    self._working_memory[session_id][key] = {
                        "value": value,
                        "updated_at": datetime.utcnow(),
                    }
                    return value
                break
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
        
        return default
    
    async def _delete_memory(self, session_id: str, key: str) -> None:
        """Delete memory from database."""
        try:
            async for db in get_db():
                from sqlalchemy import delete
                await db.execute(
                    delete(MemoryModel).where(
                        MemoryModel.session_id == session_id,
                        MemoryModel.key == key,
                    )
                )
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
    
    async def _clear_session_memories(self, session_id: str) -> None:
        """Clear all memories for a session."""
        try:
            async for db in get_db():
                from sqlalchemy import delete
                await db.execute(
                    delete(MemoryModel).where(MemoryModel.session_id == session_id)
                )
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
    
    # ==================== ARCHIVAL MEMORY ====================
    
    async def store_archival(
        self,
        tenant_id: str,
        content: str,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
        embedding: List[float] = None,
    ) -> str:
        """Store a memory in long-term archival storage."""
        memory_id = f"mem-{uuid.uuid4().hex[:12]}"
        
        try:
            async for db in get_db():
                memory = ArchivalMemoryModel(
                    id=memory_id,
                    tenant_id=tenant_id,
                    content=content,
                    tags=tags or [],
                    metadata=metadata or {},
                    embedding=embedding,
                )
                db.add(memory)
                await db.commit()
                break
        except Exception as e:
            logger.error(f"Failed to store archival memory: {e}")
        
        return memory_id
    
    async def search_archival(
        self,
        tenant_id: str,
        query: str,
        tags: List[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Search archival memories by text and tags."""
        try:
            async for db in get_db():
                from sqlalchemy import select, or_, and_
                
                conditions = [ArchivalMemoryModel.tenant_id == tenant_id]
                
                if query:
                    # Simple text search (would use vector similarity in production)
                    conditions.append(
                        ArchivalMemoryModel.content.ilike(f"%{query}%")
                    )
                
                if tags:
                    for tag in tags:
                        conditions.append(
                            ArchivalMemoryModel.tags.contains([tag])
                        )
                
                result = await db.execute(
                    select(ArchivalMemoryModel)
                    .where(and_(*conditions))
                    .order_by(ArchivalMemoryModel.created_at.desc())
                    .limit(limit)
                )
                
                memories = result.scalars().all()
                return [
                    {
                        "id": m.id,
                        "content": m.content,
                        "tags": m.tags,
                        "metadata": m.metadata,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in memories
                ]
        except Exception as e:
            logger.error(f"Archival search failed: {e}")
            return []
    
    async def get_archival(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get archival memory by ID."""
        try:
            async for db in get_db():
                from sqlalchemy import select
                result = await db.execute(
                    select(ArchivalMemoryModel).where(
                        ArchivalMemoryModel.id == memory_id
                    )
                )
                memory = result.scalar_one_or_none()
                
                if memory:
                    return {
                        "id": memory.id,
                        "content": memory.content,
                        "tags": memory.tags,
                        "metadata": memory.metadata,
                        "created_at": memory.created_at.isoformat(),
                    }
                break
        except Exception as e:
            logger.error(f"Failed to get archival memory: {e}")
        return None
    
    async def update_archival(
        self,
        memory_id: str,
        content: str = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """Update archival memory."""
        try:
            async for db in get_db():
                from sqlalchemy import select
                result = await db.execute(
                    select(ArchivalMemoryModel).where(
                        ArchivalMemoryModel.id == memory_id
                    )
                )
                memory = result.scalar_one_or_none()
                
                if memory:
                    if content is not None:
                        memory.content = content
                    if tags is not None:
                        memory.tags = tags
                    if metadata is not None:
                        memory.metadata = metadata
                    
                    await db.commit()
                    return True
                break
        except Exception as e:
            logger.error(f"Failed to update archival memory: {e}")
        return False
    
    async def delete_archival(self, memory_id: str) -> bool:
        """Delete archival memory."""
        try:
            async for db in get_db():
                from sqlalchemy import delete
                await db.execute(
                    delete(ArchivalMemoryModel).where(
                        ArchivalMemoryModel.id == memory_id
                    )
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to delete archival memory: {e}")
        return False
    
    # ==================== CONVENIENCE METHODS ====================
    
    async def remember_fact(
        self,
        session_id: str,
        fact: str,
        category: str = "general",
    ) -> None:
        """Store a fact in working memory."""
        key = f"fact:{category}:{uuid.uuid4().hex[:8]}"
        await self.set_working_memory(session_id, key, fact)
    
    async def recall_facts(
        self,
        session_id: str,
        category: str = None,
    ) -> List[str]:
        """Recall facts from working memory."""
        facts = []
        if session_id in self._working_memory:
            for key, entry in self._working_memory[session_id].items():
                if key.startswith("fact:"):
                    if category is None or f":{category}:" in key:
                        facts.append(entry["value"])
        return facts
    
    async def set_context(
        self,
        session_id: str,
        context: Dict[str, Any],
    ) -> None:
        """Set entire context object."""
        await self.set_working_memory(session_id, "_context", context)
    
    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get entire context object."""
        return await self.get_working_memory(session_id, "_context", {})


# Global memory manager
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get or create global memory manager."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager