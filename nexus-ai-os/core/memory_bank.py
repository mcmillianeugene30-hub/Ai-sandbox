import chromadb
from chromadb.utils import embedding_functions
import os
import json

class MemoryBank:
    _instance = None
    _client = None
    _collection = None

    def __new__(cls, persist_path=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            persist_path = persist_path or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "memory_db"
            )
            try:
                cls._client = chromadb.PersistentClient(path=persist_path)
                embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
                cls._collection = cls._client.get_or_create_collection(
                    name="nexus_memories",
                    embedding_function=embed_fn
                )
            except Exception as e:
                print(f"⚠️ MemoryBank initialization deferred: {e}")
                cls._client = None
                cls._collection = None
        return cls._instance

    def _ensure_initialized(self):
        """Lazy initialization to avoid permission issues during import"""
        if self._collection is None:
            persist_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "memory_db"
            )
            os.makedirs(persist_path, exist_ok=True)
            self._client = chromadb.PersistentClient(path=persist_path)
            embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self._collection = self._client.get_or_create_collection(
                name="nexus_memories",
                embedding_function=embed_fn
            )

    def store_success(self, task: str, code: str, brief: str = ""):
        try:
            self._ensure_initialized()
            if self._collection is None:
                print("⚠️ MemoryBank unavailable, skipping storage")
                return

            self._collection.add(
                documents=[f"Task: {task}\nBrief: {brief}\nCode:\n{code}"],
                metadatas=[{"task": task, "type": "success_reference"}],
                ids=[f"mem_{os.urandom(4).hex()}"]
            )
            print(f"💾 Memory Stored: Successful execution of '{task[:30]}...' saved to bank.")
        except Exception as e:
            print(f"⚠️ Failed to store memory: {e}")

    def query(self, task_query: str, n_results: int = 2):
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
            print(f"⚠️ Failed to query memory: {e}")
            return []

# Global instance - initialized lazily
memory_bank = MemoryBank()
