from fastapi import FastAPI, HTTPException, Header, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import time
import sqlite3
import json
import asyncio
import shutil
from .providers import get_provider
from .rag_manager import rag_manager

app = FastAPI(title="AI Sandbox API v3")

# Database setup
DB_PATH = "usage.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            provider TEXT,
            model TEXT,
            latency_ms INTEGER,
            status TEXT,
            prompt TEXT,
            response TEXT,
            is_starred INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def log_usage(provider, model, latency_ms, status, prompt="", response=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO usage_logs (provider, model, latency_ms, status, prompt, response) VALUES (?, ?, ?, ?, ?, ?)",
                   (provider, model, latency_ms, status, prompt, response))
    conn.commit()
    conn.close()

@app.post("/api/v1/star/{log_id}")
async def star_log(log_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE usage_logs SET is_starred = 1 WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/v1/export/finetune")
async def export_finetune():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT prompt, response FROM usage_logs WHERE is_starred = 1")
    rows = cursor.fetchall()
    conn.close()
    
    jsonl_content = ""
    for r in rows:
        entry = {
            "messages": [
                {"role": "user", "content": r[0]},
                {"role": "assistant", "content": r[1]}
            ]
        }
        jsonl_content += json.dumps(entry) + "\n"
    
    return StreamingResponse(
        iter([jsonl_content]),
        media_type="application/jsonl",
        headers={"Content-Disposition": "attachment; filename=finetune_data.jsonl"}
    )

class JudgeRequest(BaseModel):
    judge_provider: str
    judge_model: str
    prompt: str
    response_a: str
    response_b: str

@app.post("/api/v1/judge")
async def judge_responses(request: JudgeRequest, x_api_key: Optional[str] = Header(None)):
    provider_instance = get_provider(request.judge_provider)
    if not provider_instance:
        raise HTTPException(status_code=400, detail="Judge provider not supported.")
    
    judge_prompt = f"""Please act as an impartial judge and evaluate the quality of the responses provided by two AI assistants to the user prompt displayed below. 
User Prompt: {request.prompt}

Response A: {request.response_a}
Response B: {request.response_b}

Evaluate based on helpfulness, relevance, accuracy, and depth. 
Output your final verdict as '[[A]]' if A is better, '[[B]]' if B is better, or '[[C]]' for a tie. 
Provide a brief 1-sentence explanation before the verdict."""

    try:
        # Use the standard chat_complete but with the judge prompt
        # We need to map the API key if not provided
        if not x_api_key:
             env_key_map = {"gemini": "GOOGLE_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
             x_api_key = os.getenv(env_key_map.get(request.judge_provider.lower()))

        response = provider_instance.chat_complete(
            model=request.judge_model,
            messages=[{"role": "user", "content": judge_prompt}],
            api_key=x_api_key
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatCompletionRequest(BaseModel):
    provider: str
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False
    kb_enabled: Optional[bool] = False

@app.post("/api/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, x_api_key: Optional[str] = Header(None)):
    provider_instance = get_provider(request.provider)
    if not provider_instance:
        raise HTTPException(status_code=400, detail=f"Provider '{request.provider}' not supported.")
    
    if not x_api_key and request.provider.lower() != "ollama":
        env_key_map = {
            "gemini": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY"
        }
        x_api_key = os.getenv(env_key_map.get(request.provider.lower()))
        
    if not x_api_key and request.provider.lower() != "ollama":
        raise HTTPException(status_code=401, detail=f"Missing API key for {request.provider}.")

    messages = request.messages
    if request.kb_enabled:
        # Get context from Knowledge Base
        last_user_message = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), "")
        context = rag_manager.query(last_user_message)
        if context:
            # Inject context into system message or first message
            context_prompt = f"Context from Knowledge Base:\n{context}\n\nUse the above context to answer the user's question."
            if messages[0]['role'] == 'system':
                messages[0]['content'] += f"\n\n{context_prompt}"
            else:
                messages.insert(0, {"role": "system", "content": context_prompt})

    start_time = time.time()

    if request.stream:
        async def stream_generator():
            full_response = ""
            try:
                async for chunk in provider_instance.stream_complete(
                    model=request.model,
                    messages=messages,
                    api_key=x_api_key,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens
                ):
                    yield f"data: {chunk}\n\n"
                    # Accumulate for logging
                    try:
                        data = json.loads(chunk)
                        delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        full_response += delta
                    except: pass
                
                last_user_prompt = messages[-1]["content"] if messages else ""
                log_usage(request.provider, request.model, int((time.time() - start_time) * 1000), "success", last_user_prompt, full_response)
            except Exception as e:
                log_usage(request.provider, request.model, 0, f"error: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    try:
        response = provider_instance.chat_complete(
            model=request.model,
            messages=messages,
            api_key=x_api_key,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        latency = int((time.time() - start_time) * 1000)
        last_user_prompt = messages[-1]["content"] if messages else ""
        assistant_res = response["choices"][0]["message"]["content"]
        log_usage(request.provider, request.model, latency, "success", last_user_prompt, assistant_res)
        return response
    except Exception as e:
        log_usage(request.provider, request.model, 0, f"error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/kb/upload")
async def upload_to_kb(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        if file.filename.endswith(".pdf"):
            rag_manager.ingest_pdf(file_path, file.filename)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            rag_manager.ingest_text(content, file.filename)
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics")
async def get_analytics():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT provider, model, AVG(latency_ms), COUNT(*) FROM usage_logs GROUP BY provider, model")
    rows = cursor.fetchall()
    conn.close()
    return [{"provider": r[0], "model": r[1], "avg_latency": r[2], "count": r[3]} for r in rows]

@app.get("/api/v1/models")
async def list_models():
    return {
        "gemini": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
        "groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "openrouter": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "meta-llama/llama-3.1-405b"],
        "ollama": ["llama3", "mistral", "phi3"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
