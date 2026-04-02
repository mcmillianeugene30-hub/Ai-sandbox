"""
MemoryBank — Vector database for agent memory.
Stores successful executions and retrieves relevant context.
"""
import chromadb
from chromadb.utils import embedding_functions
import os
from pathlib import Path
from typing import List, Optional

from backend.config import MEMORY_DB_DIR
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class MemoryBank:
    """Singleton vector database for agent memory storage and retrieval."""
    
    _instance = None
    _client = None
    _collection = None

    def __new__(cls, persist_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._persist_path = persist_path or str(MEMORY_DB_DIR)
            cls._instance._initialized = False
        return cls._instance

    def _ensure_initialized(self):
        """Lazy initialization to avoid issues during import."""
        if self._initialized:
            return
        
        try:
            Path(self._persist_path).mkdir(parents=True, exist_ok=True)
            
            self._client = chromadb.PersistentClient(path=self._persist_path)
            embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self._collection = self._client.get_or_create_collection(
                name="nexus_memories",
                embedding_function=embed_fn
            )
            self._initialized = True
            logger.debug("MemoryBank initialized successfully")
        except Exception as e:
            logger.warning(f"MemoryBank initialization deferred: {e}")
            self._client = None
            self._collection = None

    def store_success(self, task: str, code: str, brief: str = ""):
        """Store a successful execution in the memory bank."""
        try:
            self._ensure_initialized()
            if self._collection is None:
                logger.warning("MemoryBank unavailable, skipping storage")
                return

            import secrets
            doc_id = f"mem_{secrets.token_hex(4)}"
            
            self._collection.add(
                documents=[f"Task: {task}\nBrief: {brief}\nCode:\n{code}"],
                metadatas=[{"task": task, "type": "success_reference"}],
                ids=[doc_id]
            )
            logger.info(f"Memory Stored: Successful execution of '{task[:30]}...' saved to bank.")
        except Exception as e:
            logger.warning(f"Failed to store memory: {e}")

    def query(self, task_query: str, n_results: int = 2) -> List[str]:
        """Query the memory bank for relevant past executions."""
        try:
            self._ensure_initialized()
            if self._collection is None:
                return []

            results = self._collection.query(
                query_texts=[task_query],
                n_results=n_results
            )
            return results['documents'][0] if results['documents'] else []
        except Exception as e:
            logger.warning(f"Failed to query memory: {e}")
            return []


# Global instance - initialized lazily
memory_bank = MemoryBank()
