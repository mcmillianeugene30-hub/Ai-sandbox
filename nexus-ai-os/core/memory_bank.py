"""Persistent vector-memory storage for Nexus AI OS."""
import json
import logging
import os
from typing import List, Optional

import chromadb
from chromadb.utils import embedding_functions

from core.kernel import PROJECT_ROOT, RENDER_DISK_PATH

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_PATH = os.path.join(RENDER_DISK_PATH, "memory_db")


class MemoryBank:
    """Singleton wrapper around ChromaDB for storing and querying execution memories."""

    _instance = None
    _client = None
    _collection = None

    def __new__(cls, persist_path: Optional[str] = None):
        """Create or reuse the singleton instance and lazily prepare persistence state."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.persist_path = persist_path or DEFAULT_MEMORY_PATH
            cls._instance._initialize_client()
        return cls._instance

    def _initialize_client(self) -> None:
        """Initialise the Chroma client and collection if possible."""
        try:
            os.makedirs(self.persist_path, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_path)
            embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self._collection = self._client.get_or_create_collection(
                name="nexus_memories",
                embedding_function=embed_fn,
            )
            logger.info("MemoryBank initialised at %s", self.persist_path)
        except Exception as exc:
            logger.warning("MemoryBank initialisation deferred: %s", exc, exc_info=True)
            self._client = None
            self._collection = None

    def _ensure_initialized(self) -> None:
        """Ensure the backing collection is available before a read/write operation."""
        if self._collection is None:
            self._initialize_client()

    def store_success(self, task: str, code: str, brief: str = "") -> bool:
        """Persist a successful task execution and optional brief for later reuse."""
        try:
            self._ensure_initialized()
            if self._collection is None:
                logger.error("store_success aborted: collection unavailable")
                return False

            payload = {"task": task, "code": code, "brief": brief}
            self._collection.add(
                documents=[json.dumps(payload)],
                metadatas=[{"task": task}],
                ids=[f"mem_{abs(hash(task + code))}"],
            )
            logger.info("Memory stored for task=%s", task)
            return True
        except Exception as exc:
            logger.error("store_success failed for task=%s error=%s", task, exc, exc_info=True)
            return False

    def query(self, query_text: str, n_results: int = 3) -> List[str]:
        """Query the memory bank and return matching stored document strings."""
        try:
            self._ensure_initialized()
            if self._collection is None:
                logger.error("query aborted: collection unavailable")
                return []

            results = self._collection.query(query_texts=[query_text], n_results=n_results)
            documents = results.get("documents", [[]])
            return documents[0] if documents else []
        except Exception as exc:
            logger.error("query failed for query_text=%s error=%s", query_text, exc, exc_info=True)
            return []


memory_bank = MemoryBank()
