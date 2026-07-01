"""
Semantic Memory Service (Cortex)

Provides long-term, vector-based memory for the agent using ChromaDB.
Automatically indexes tool results and allows the agent to query past knowledge.
"""
import logging
import os
import time
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from src.infrastructure.runtime.paths import workspace_root

logger = logging.getLogger(__name__)

class SemanticMemory:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SemanticMemory, cls).__new__(cls)
            cls._instance._init_db()
        return cls._instance
        
    def _init_db(self):
        self.db_path = str(workspace_root() / ".chromadb")
        os.makedirs(self.db_path, exist_ok=True)
        try:
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(anonymized_telemetry=False)
            )
            # We use one collection per tenant/session conceptually, but for now 
            # we'll store everything in 'agent_memory' and filter by metadata.
            self.collection = self.client.get_or_create_collection(
                name="agent_memory",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"[SemanticMemory] Initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"[SemanticMemory] Failed to initialize ChromaDB: {e}")
            self.client = None
            
    async def index_event(self, session_id: str, tenant_id: str, event_type: str, content: str, task_id: Optional[str] = None):
        """Index an event (thought, tool result, etc.) into long-term memory."""
        if not self.client or not content.strip():
            return
            
        doc_id = f"{session_id}_{int(time.time() * 1000)}"
        
        try:
            self.collection.add(
                documents=[content],
                metadatas=[{
                    "session_id": session_id,
                    "tenant_id": tenant_id,
                    "event_type": event_type,
                    "task_id": task_id or "unknown",
                    "timestamp": time.time()
                }],
                ids=[doc_id]
            )
            logger.debug(f"[SemanticMemory] Indexed event {doc_id} ({event_type})")
        except Exception as e:
            logger.error(f"[SemanticMemory] Failed to index event: {e}")

    async def query_memory(self, session_id: str, tenant_id: str, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant past events based on semantic similarity."""
        if not self.client or not query_text.strip():
            return []
            
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where={
                    "$and": [
                        {"session_id": session_id},
                        {"tenant_id": tenant_id}
                    ]
                }
            )
            
            formatted_results = []
            if results and results.get("documents") and len(results["documents"]) > 0:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i]
                    formatted_results.append({
                        "content": doc,
                        "event_type": meta.get("event_type"),
                        "timestamp": meta.get("timestamp")
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"[SemanticMemory] Query failed: {e}")
            return []

semantic_memory = SemanticMemory()
