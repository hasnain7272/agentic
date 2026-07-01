import logging
import os
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class SemanticCodeGraph:
    """
    Semantic Code Graph using ChromaDB for AST-level semantic search.
    """
    def __init__(self):
        try:
            import chromadb
            from chromadb.config import Settings
            # Create a local persistent chromadb
            db_path = str(Path.cwd() / ".chroma_db")
            self.client = chromadb.PersistentClient(path=db_path, settings=Settings(anonymized_telemetry=False))
            self.collection = self.client.get_or_create_collection(name="project_codebase")
            self.enabled = True
        except ImportError:
            logger.warning("[SemanticCodeGraph] ChromaDB not installed. Semantic memory disabled.")
            self.enabled = False

    async def index_workspace(self, session_id: str, workspace_path: str):
        """Index a workspace into ChromaDB."""
        if not self.enabled: return
        logger.info(f"[SemanticCodeGraph] Indexing workspace {workspace_path} for session {session_id}")
        
        # Super simplified chunking for prototype implementation
        import glob
        files = glob.glob(f"{workspace_path}/**/*.py", recursive=True) + glob.glob(f"{workspace_path}/**/*.ts", recursive=True)
        
        docs = []
        metadatas = []
        ids = []
        
        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Chunk by 500 characters
                    chunks = [content[i:i+500] for i in range(0, len(content), 500)]
                    for idx, chunk in enumerate(chunks):
                        docs.append(chunk)
                        metadatas.append({"session_id": session_id, "file": fpath})
                        ids.append(f"{session_id}_{fpath}_{idx}")
            except Exception:
                continue

        if docs:
            # Upsert into ChromaDB
            self.collection.upsert(
                documents=docs,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"[SemanticCodeGraph] Indexed {len(docs)} chunks for {session_id}")

    async def retrieve_context(self, session_id: str, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Retrieve most relevant code chunks for a query."""
        if not self.enabled: return []
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"session_id": session_id}
            )
            
            context = []
            if results and results.get("documents") and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    context.append({
                        "file": results["metadatas"][0][i]["file"],
                        "content": results["documents"][0][i]
                    })
            return context
        except Exception as e:
            logger.error(f"[SemanticCodeGraph] Retrieval failed: {e}")
            return []

# Singleton
_graph = None

def get_semantic_graph() -> SemanticCodeGraph:
    global _graph
    if _graph is None:
        _graph = SemanticCodeGraph()
    return _graph
