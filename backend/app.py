"""
Project Nexus FastAPI Application
Main application entry point with modularized routers.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

from backend.config import FRONTEND_URL, PROJECT_ROOT, BACKEND_DIR
from backend.database import init_db, seed_admin_user, seed_pricing_config
from backend.utils.logging import setup_logger

# Import routers
from backend.routers import auth, chat, billing, admin, kb, nexus

# Setup logging
logger = setup_logger("nexus")

# Create FastAPI app
app = FastAPI(
    title="Project Nexus API",
    description="Autonomous AI Operating System API v8.0",
    version="8.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:8080"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(billing.router)
app.include_router(admin.router)
app.include_router(kb.router)
app.include_router(nexus.router)

# Static files (frontend)
try:
    frontend_path = PROJECT_ROOT / "frontend"
    if frontend_path.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("Starting Project Nexus API...")
    init_db()
    seed_admin_user()
    seed_pricing_config()
    logger.info("Project Nexus API started successfully")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "8.0.0"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Project Nexus API",
        "version": "8.0.0",
        "docs": "/docs",
        "endpoints": {
            "auth": "/api/v1/auth",
            "chat": "/api/v1/chat/completions",
            "models": "/api/v1/models",
            "billing": "/api/v1/billing",
            "admin": "/api/v1/admin",
            "kb": "/api/v1/kb",
            "nexus": "/api/v1"
        }
    }


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    """Serve pricing page."""
    pricing_path = PROJECT_ROOT / "frontend" / "pricing.html"
    if pricing_path.exists():
        with open(pricing_path, "r") as f:
            return f.read()
    raise HTTPException(404, "Pricing page not found")


# Legacy redirects for backward compatibility
@app.get("/models")
async def legacy_models():
    """Redirect to new models endpoint."""
    from backend.config import AVAILABLE_MODELS
    return AVAILABLE_MODELS


@app.post("/chat/completions")
async def legacy_chat_completions(request: Request):
    """Legacy chat completions endpoint."""
    from backend.routers.chat import chat_completions_legacy, ChatRequest
    import json
    
    body = await request.json()
    req = ChatRequest(**body)
    
    # Get API key from header
    api_key = request.headers.get("x-api-key")
    
    return await chat_completions_legacy(req, api_key)


@app.post("/kb/upload")
async def legacy_kb_upload(request: Request):
    """Legacy KB upload endpoint."""
    from fastapi import UploadFile, File
    from backend.routers.kb import kb_upload_legacy
    
    # This is a simplified redirect - in production you'd need to handle the file properly
    raise HTTPException(307, "Please use /api/v1/kb/upload")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
