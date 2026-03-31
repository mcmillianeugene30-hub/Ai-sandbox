import chromadb
from chromadb.utils import embedding_functions
import os
import json

class MemoryBank:
    def __init__(self, persist_path="/workspace/ai-sandbox/nexus-ai-os/memory_db"):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        self.collection = self.client.get_or_create_collection(
            name="nexus_memories",
            embedding_function=self.embed_fn
        )

    def store_success(self, task: str, code: str, brief: str = ""):
        # Store successful task execution for future reference
        self.collection.add(
            documents=[f"Task: {task}\nBrief: {brief}\nCode:\n{code}"],
            metadatas=[{"task": task, "type": "success_reference"}],
            ids=[f"mem_{os.urandom(4).hex()}"]
        )
        print(f"💾 Memory Stored: Successful execution of '{task[:30]}...' saved to bank.")

    def query(self, task_query: str, n_results: int = 2):
        # Retrieve similar past successful tasks
        results = self.collection.query(
            query_texts=[task_query],
            n_results=n_results
        )
        return results['documents'][0] if results['documents'] else []

memory_bank = MemoryBank()
