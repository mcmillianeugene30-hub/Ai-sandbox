"""
Knowledge Base / RAG router for Project Nexus.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from backend.config import UPLOADS_DIR, ACTION_COSTS
from backend.database import require_credits
from backend.routers.auth import get_current_user, get_admin_user
from backend.rag_manager import rag_manager
from backend.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/kb", tags=["knowledge-base"])


@router.post("/upload")
async def kb_upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a document to the knowledge base."""
    # Deduct credits for RAG upload
    if not require_credits(user["id"], ACTION_COSTS["rag_query"], "KB upload"):
        raise HTTPException(402, "Insufficient credits")
    
    try:
        dest = UPLOADS_DIR / file.filename
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(dest, "wb") as f:
            f.write(await file.read())
        
        if file.filename.endswith(".pdf"):
            rag_manager.ingest_pdf(str(dest), file.filename)
        else:
            with open(dest, "r", encoding="utf-8") as f:
                text = f.read()
            rag_manager.ingest_text(text, file.filename, {"filename": file.filename})
        
        logger.info(f"User {user['id']} uploaded {file.filename} to KB")
        return {"status": "indexed", "file": file.filename}
    except Exception as e:
        logger.error(f"KB upload failed: {e}")
        raise HTTPException(500, f"Upload failed: {str(e)}")


@router.get("/docs")
async def list_kb_docs(user: dict = Depends(get_current_user)):
    """List documents in the knowledge base."""
    try:
        docs = rag_manager.list_documents()
        return {"documents": docs.get('ids', [])}
    except Exception as e:
        logger.error(f"KB list failed: {e}")
        raise HTTPException(500, f"Failed to list documents: {str(e)}")


@router.delete("/docs/{doc_id}")
async def delete_kb_doc(doc_id: str, admin: dict = Depends(get_admin_user)):
    """Delete a document from the knowledge base (admin only)."""
    try:
        rag_manager.delete_document(doc_id)
        logger.info(f"Admin deleted KB doc {doc_id}")
        return {"status": "deleted", "doc_id": doc_id}
    except Exception as e:
        logger.error(f"KB delete failed: {e}")
        raise HTTPException(500, f"Failed to delete document: {str(e)}")


# Legacy endpoints for backward compatibility
@router.post("/upload/legacy")
async def kb_upload_legacy(file: UploadFile = File(...)):
    """Legacy KB upload without auth (for testing)."""
    try:
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        if file.filename.lower().endswith('.pdf'):
            rag_manager.ingest_pdf(temp_path, file.filename)
        else:
            with open(temp_path, "r", encoding="utf-8") as f:
                text = f.read()
            rag_manager.ingest_text(text, file.filename, {"filename": file.filename})
        
        os.remove(temp_path)
        return {"status": "success", "message": "Document indexed successfully"}
    except Exception as e:
        logger.error(f"KB legacy upload failed: {e}")
        raise HTTPException(500, f"Upload failed: {str(e)}")
