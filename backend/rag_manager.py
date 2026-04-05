import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from typing import List, Dict, Any

class RAGManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _ensure_initialized(self):
        if self._initialized:
            return

        try:
            # Vercel Serverless (Read-only FS fallback to /tmp)
            if os.environ.get("VERCEL") == "1":
                persist_directory = "/tmp/nexus_chroma"
            # Use Render persistent disk path if available
            elif os.environ.get("RENDER_DISK_PATH"):
                persist_directory = os.path.join(os.environ.get("RENDER_DISK_PATH"), "chroma_db")
            else:
                persist_directory = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "chroma_db"
                )
            os.makedirs(persist_directory, exist_ok=True)

            self.client = chromadb.PersistentClient(path=persist_directory)
            self.default_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self.collection = self.client.get_or_create_collection(
                name="default_kb",
                embedding_function=self.default_ef
            )
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100,
                length_function=len,
            )
            self._initialized = True
        except Exception as e:
            print(f"⚠️ RAGManager initialization deferred: {e}")
            self._initialized = False

    def ingest_text(self, text: str, doc_id: str, metadata: Dict[str, Any] = None):
        try:
            self._ensure_initialized()
            if not self._initialized:
                raise RuntimeError("RAGManager not initialized")

            chunks = self.splitter.split_text(text)
            ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
            metadatas = [metadata or {} for _ in range(len(chunks))]
            self.collection.add(
                documents=chunks,
                ids=ids,
                metadatas=metadatas
            )
        except Exception as e:
            print(f"⚠️ Failed to ingest text: {e}")
            raise

    def ingest_pdf(self, file_path: str, doc_id: str):
        try:
            self._ensure_initialized()
            if not self._initialized:
                raise RuntimeError("RAGManager not initialized")

            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            self.ingest_text(text, doc_id, {"source": os.path.basename(file_path)})
        except Exception as e:
            print(f"⚠️ Failed to ingest PDF: {e}")
            raise

    def query(self, query_text: str, n_results: int = 3) -> str:
        try:
            self._ensure_initialized()
            if not self._initialized:
                return ""

            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            # Flatten results into a single context string
            context = "\n---\n".join(results['documents'][0])
            return context
        except Exception as e:
            print(f"⚠️ Failed to query RAG: {e}")
            return ""

    def list_documents(self):
        try:
            self._ensure_initialized()
            if not self._initialized:
                return {}

            return self.collection.get()
        except Exception as e:
            print(f"⚠️ Failed to list documents: {e}")
            return {}

# Global manager instance
rag_manager = RAGManager()
