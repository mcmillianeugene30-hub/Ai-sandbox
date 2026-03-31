import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from typing import List, Dict, Any

# Initialize ChromaDB
persist_directory = "chroma_db"
client = chromadb.PersistentClient(path=persist_directory)

# Use a lightweight local embedding model
default_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

class RAGManager:
    def __init__(self, collection_name: str = "default_kb"):
        self.collection = client.get_or_create_collection(
            name=collection_name, 
            embedding_function=default_ef
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len,
        )

    def ingest_text(self, text: str, doc_id: str, metadata: Dict[str, Any] = None):
        chunks = self.splitter.split_text(text)
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [metadata or {} for _ in range(len(chunks))]
        self.collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )

    def ingest_pdf(self, file_path: str, doc_id: str):
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        self.ingest_text(text, doc_id, {"source": os.path.basename(file_path)})

    def query(self, query_text: str, n_results: int = 3) -> str:
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        # Flatten results into a single context string
        context = "\n---\n".join(results['documents'][0])
        return context

    def list_documents(self):
        # This is a bit limited in ChromaDB without custom tracking
        return self.collection.get()

# Global manager instance
rag_manager = RAGManager()
