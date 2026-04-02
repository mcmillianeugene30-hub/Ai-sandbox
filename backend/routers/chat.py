"""
Chat completion router for Project Nexus.
"""
import time
import json
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import AVAILABLE_MODELS, ACTION_COSTS, GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY
from backend.database import log_usage, check_model_access, require_credits
from backend.routers.auth import get_current_user
from backend.providers import get_provider
from backend.rag_manager import rag_manager
from backend.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatRequest(BaseModel):
    provider: str
    model: str
    messages: List[Dict[str, Any]]
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False
    kb_enabled: bool = False


@router.get("/models")
async def list_models():
    """Return available models for each provider."""
    return AVAILABLE_MODELS


@router.post("/chat/completions")
async def chat_completions(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    x_api_key: str = Header(None)
):
    """Main chat completion endpoint with streaming and RAG support."""
    # Check model access
    if not check_model_access(user.get("plan", "NONE"), req.model):
        raise HTTPException(403, f"Model '{req.model}' requires a higher plan. Upgrade to access it.")
    
    # Deduct action cost
    if not require_credits(user["id"], ACTION_COSTS["chat"], f"chat: {req.model}"):
        raise HTTPException(402, "Insufficient credits. Please top up your account.")
    
    # Get API key
    api_key_map = {
        "groq": GROQ_API_KEY,
        "gemini": GEMINI_API_KEY,
        "google": GEMINI_API_KEY,
        "openrouter": OPENROUTER_API_KEY
    }
    api_key = x_api_key or api_key_map.get(req.provider, "")
    
    if not api_key and req.provider != "ollama":
        raise HTTPException(
            401,
            f"API key required for {req.provider}. Set {req.provider.upper()}_API_KEY environment variable or provide x-api-key header."
        )
    
    # Get provider
    provider = get_provider(req.provider)
    if not provider:
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    
    # RAG integration
    messages = req.messages
    if req.kb_enabled:
        query = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if query:
            context = rag_manager.query(query)
            if context:
                messages = [{"role": "system", "content": f"Context:\n{context}"}] + messages
    
    start_time = time.time()
    
    if req.stream:
        async def generate():
            full_content = ""
            status = "success"
            try:
                async for chunk in provider.stream_complete(req.model, messages, api_key, temperature=req.temperature, max_tokens=req.max_tokens):
                    yield chunk
                    # Extract content for logging
                    try:
                        chunk_data = json.loads(chunk) if isinstance(chunk, str) else chunk
                        if "choices" in chunk_data and chunk_data["choices"]:
                            delta = chunk_data["choices"][0].get("delta", {})
                            full_content += delta.get("content", "")
                    except:
                        pass
            except Exception as e:
                status = f"error: {str(e)}"
                yield f'data: {{"error": "{str(e)}"}}\n\n'
            finally:
                latency_ms = int((time.time() - start_time) * 1000)
                prompt_content = messages[-1].get("content", "") if messages else ""
                log_usage(user["id"], req.provider, req.model, latency_ms, status, prompt_content, full_content)
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        try:
            response = provider.chat_complete(
                req.model, messages, api_key,
                temperature=req.temperature, max_tokens=req.max_tokens
            )
            latency_ms = int((time.time() - start_time) * 1000)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            log_usage(user["id"], req.provider, req.model, latency_ms, "success",
                     messages[-1].get("content", "") if messages else "", content)
            return response
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            log_usage(user["id"], req.provider, req.model, latency_ms, f"error: {str(e)}",
                     messages[-1].get("content", "") if messages else "", str(e))
            raise HTTPException(500, f"Provider error: {str(e)}")


# Legacy endpoint for backward compatibility
@router.post("/chat/completions/legacy")
async def chat_completions_legacy(
    req: ChatRequest,
    x_api_key: str = Header(None)
):
    """Legacy chat completion endpoint without auth (for testing)."""
    api_key_map = {
        "groq": GROQ_API_KEY,
        "gemini": GEMINI_API_KEY,
        "google": GEMINI_API_KEY,
        "openrouter": OPENROUTER_API_KEY
    }
    api_key = x_api_key or api_key_map.get(req.provider, "")
    
    if not api_key and req.provider != "ollama":
        raise HTTPException(401, f"API key required for {req.provider}")
    
    provider = get_provider(req.provider)
    if not provider:
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    
    messages = req.messages
    if req.kb_enabled:
        query = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if query:
            context = rag_manager.query(query)
            if context:
                messages = [{"role": "system", "content": f"Context:\n{context}"}] + messages
    
    start_time = time.time()
    
    if req.stream:
        async def generate():
            try:
                async for chunk in provider.stream_complete(req.model, messages, api_key):
                    yield chunk
            except Exception as e:
                yield f'data: {{"error": "{str(e)}"}}\n\n'
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        try:
            response = provider.chat_complete(req.model, messages, api_key)
            latency_ms = int((time.time() - start_time) * 1000)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            log_usage(0, req.provider, req.model, latency_ms, "success",
                     messages[-1].get("content", "") if messages else "", content)
            return response
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            log_usage(0, req.provider, req.model, latency_ms, f"error: {str(e)}")
            raise HTTPException(500, f"Provider error: {str(e)}")
