"""
RAGManager — Retrieval-Augmented Generation knowledge base management.
Handles document ingestion, embedding, and querying using ChromaDB.
"""
import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from typing import List, Dict, Any, Optional
from pathlib import Path

from backend.config import CHROMA_DB_DIR
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class RAGManager:
    """Singleton RAG manager for document storage and retrieval."""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _ensure_initialized(self):
        """Lazy initialization of ChromaDB client."""
        if self._initialized:
            return

        try:
            persist_directory = str(CHROMA_DB_DIR)
            Path(persist_directory).mkdir(parents=True, exist_ok=True)

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
            logger.debug("RAGManager initialized successfully")
        except Exception as e:
            logger.warning(f"RAGManager initialization deferred: {e}")
            self._initialized = False

    def ingest_text(self, text: str, doc_id: str, metadata: Dict[str, Any] = None):
        """Ingest text content into the knowledge base."""
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
            logger.info(f"Ingested text document: {doc_id} ({len(chunks)} chunks)")
        except Exception as e:
            logger.error(f"Failed to ingest text: {e}")
            raise

    def ingest_pdf(self, file_path: str, doc_id: str):
        """Ingest a PDF file into the knowledge base."""
        try:
            self._ensure_initialized()
            if not self._initialized:
                raise RuntimeError("RAGManager not initialized")

            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            self.ingest_text(text, doc_id, {"source": os.path.basename(file_path)})
            logger.info(f"Ingested PDF: {doc_id}")
        except Exception as e:
            logger.error(f"Failed to ingest PDF: {e}")
            raise

    def query(self, query_text: str, n_results: int = 3) -> str:
        """Query the knowledge base and return relevant context."""
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
            logger.warning(f"Failed to query RAG: {e}")
            return ""

    def list_documents(self) -> Dict[str, Any]:
        """List all documents in the knowledge base."""
        try:
            self._ensure_initialized()
            if not self._initialized:
                return {}

            return self.collection.get()
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return {}

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the knowledge base."""
        try:
            self._ensure_initialized()
            if not self._initialized:
                return False

            # Delete by ID pattern (chunks use doc_id_N format)
            self.collection.delete(where={"source": doc_id})
            logger.info(f"Deleted document: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False


# Global manager instance
rag_manager = RAGManager()
