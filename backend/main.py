from typing import List, Dict, Any, Optional, AsyncGenerator
import json
import asyncio
from fastapi import FastAPI, HTTPException, Header, Request, UploadFile, File, Form, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os, time, sqlite3, shutil, jwt
from datetime import datetime, timedelta
from argon2 import PasswordHasher as _PH
from argon2.exceptions import VerifyMismatchError as _VME
_ph = _PH()

class argon2:
    @staticmethod
    def hash(password: str) -> str:
        return _ph.hash(password)
    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        try: return _ph.verify(hashed, password)
        except _VME: return False

import sys

# Set up Python path for nexus-ai-os imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEXUS_OS_PATH = os.environ.get("NEXUS_OS_PATH", os.path.join(PROJECT_ROOT, "nexus-ai-os"))
if NEXUS_OS_PATH not in sys.path:
    sys.path.insert(0, NEXUS_OS_PATH)
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.kernel import NexusKernel
from agents.architect import AppArchitectAgent
from agents.devops import DevOpsAgent
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.coder import CoderAgent
from agents.reviewer import ReviewerAgent
from agents.hive_aggregator import HiveAggregator
from agents.auto_deploy import AutoDeployAgent
from agents.model_researcher import AutonomousModelResearcher
from core.swarm import SwarmBus, SwarmNode, SwarmOrchestrator
from tools.fs_tool import fs_tool
import providers
from rag_manager import rag_manager

# Shared swarm bus (singleton per process)
_swarm_bus = SwarmBus()

# ─── CONFIG ───────────────────────────────────────────────────────────────────
SECRET_KEY = "nexus_super_secret_key_2026"
ALGORITHM  = "HS256"
TOKEN_EXP_MINUTES = 600

# Pricing: $1 = 10 credits, $0.10 per credit
CREDIT_PRICE_USD = 0.10   # 1 credit = $0.10

# Plans: { name: (price_usd, credits_monthly, models_allowed) }
PLAN_CONFIG = {
    "STARTER":    {"price": 9.00,  "credits": 90,  "models": ["llama-3.1-8b-instant","gemini-1.5-flash","mistral-7b"]},
    "PRO":        {"price": 29.00, "credits": 150, "models": ["llama-3.1-8b-instant","llama-3.3-70b-versatile",
                                                                "gemini-1.5-flash","gemini-1.5-pro","mistral-7b","llama3"]},
    "ENTERPRISE": {"price": 99.00, "credits": 600, "models": ["*"]},  # all models
}

# Per-action credit burns (flat fee per agent step, on top of token cost)
ACTION_COSTS = {
    "chat":       0.1,   # basic chat completion
    "agent_step": 1.0,   # each Nexus agent activation (architect, planner, coder…)
    "deploy":     5.0,   # each project deploy
    "rag_query":  0.5,   # knowledge base query
}

# Top-up packs: { pack_id: (price_usd, credits_with_bonus) }
TOPUP_PACKS = {
    "micro":   {"price": 5.00,  "credits": 55,  "label": "Micro Pack (+10% bonus)"},
    "builder": {"price": 10.00, "credits": 115, "label": "Builder Pack (+15% bonus)"},
    "power":   {"price": 25.00, "credits": 300, "label": "Power Pack (+20% bonus)"},
    "studio":  {"price": 50.00, "credits": 650, "label": "Studio Pack (+30% bonus)"},
}

app = FastAPI(title="Project Nexus API v7.1 — Subscription & Credits")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "*")
app.add_middleware(CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:8080"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

# ─── DATABASE ─────────────────────────────────────────────────────────────────
# Render persistent disk mounts at /opt/render/project/src/data
DATA_DIR = os.environ.get("RENDER_DISK_PATH",
           os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "usage.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        hashed_password TEXT,
        is_admin INTEGER DEFAULT 0,
        plan_type TEXT DEFAULT 'NONE',
        credits REAL DEFAULT 0,
        plan_expires TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS credit_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        type TEXT,
        description TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        provider TEXT, model TEXT,
        latency_ms INTEGER, status TEXT,
        prompt TEXT, response TEXT,
        cost_usd REAL DEFAULT 0,
        credits_used REAL DEFAULT 0,
        is_starred INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS pricing_config (
        provider TEXT, model TEXT,
        input_cost_1m REAL, output_cost_1m REAL,
        PRIMARY KEY (provider, model)
    )''')

    # ── Seed admin (nexus / nexus2026) — unlimited ENTERPRISE
    c.execute("INSERT OR IGNORE INTO users (username, hashed_password, is_admin, plan_type, credits) VALUES (?,?,?,?,?)",
              ("nexus", argon2.hash("nexus2026"), 1, "ENTERPRISE", 9_999_999))

    # ── Seed 2026 provider pricing
    c.executemany("INSERT OR IGNORE INTO pricing_config VALUES (?,?,?,?)", [
        ('groq',        'llama-3.3-70b-versatile', 0.59,  0.79),
        ('groq',        'llama-3.1-8b-instant',    0.05,  0.08),
        ('google',      'gemini-1.5-pro',           3.50,  10.50),
        ('google',      'gemini-1.5-flash',         0.075, 0.30),
        ('openrouter',  'gpt-4o',                   5.00,  15.00),
        ('openrouter',  'claude-sonnet-4',          3.00,  15.00),
    ])

    conn.commit(); conn.close()

init_db()

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────
def make_token(username: str) -> str:
    return jwt.encode({"sub": username, "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXP_MINUTES)},
                      SECRET_KEY, algorithm=ALGORITHM)

async def get_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT id,username,is_admin,plan_type,credits,plan_expires FROM users WHERE username=?",
                           (username,)).fetchone()
        conn.close()
        if not row: raise Exception()
        return {"id":row[0],"username":row[1],"is_admin":row[2],"plan":row[3],"credits":row[4],"plan_expires":row[5]}
    except:
        raise HTTPException(401, "Unauthorized")

async def get_admin(user=Depends(get_user)):
    if not user["is_admin"]: raise HTTPException(403, "Admin required")
    return user

# ─── CREDIT ENGINE ────────────────────────────────────────────────────────────
def _deduct(user_id: int, amount: float, desc: str) -> bool:
    """Atomic credit deduction. Returns False if insufficient balance."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-? WHERE id=? AND credits>=?", (amount, user_id, amount))
    ok = c.rowcount == 1
    if ok:
        c.execute("INSERT INTO credit_ledger (user_id,amount,type,description) VALUES (?,?,?,?)",
                  (user_id, -amount, 'USAGE', desc))
    conn.commit(); conn.close()
    return ok

def _add_credits(user_id: int, amount: float, type_: str, desc: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits+? WHERE id=?", (amount, user_id))
    c.execute("INSERT INTO credit_ledger (user_id,amount,type,description) VALUES (?,?,?,?)",
              (user_id, amount, type_, desc))
    conn.commit(); conn.close()

def token_cost_credits(provider, model, prompt, response) -> tuple[float, float]:
    conn = sqlite3.connect(DB_PATH)
    rates = conn.execute("SELECT input_cost_1m,output_cost_1m FROM pricing_config WHERE provider=? AND model=?",
                         (provider, model)).fetchone()
    conn.close()
    if not rates: return 0.0, 0.0
    in_tok, out_tok = len(prompt)/4, len(response)/4
    cost_usd = ((in_tok/1e6)*rates[0]) + ((out_tok/1e6)*rates[1])
    return cost_usd, cost_usd / CREDIT_PRICE_USD

def log_usage(user_id, provider, model, latency_ms, status_, prompt="", response=""):
    cost_usd, credits = token_cost_credits(provider, model, prompt, response)
    if credits > 0:
        _deduct(user_id, credits, f"token cost: {model}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO usage_logs (user_id,provider,model,latency_ms,status,prompt,response,cost_usd,credits_used) VALUES (?,?,?,?,?,?,?,?,?)",
                 (user_id, provider, model, latency_ms, status_, prompt, response, cost_usd, credits))
    conn.commit(); conn.close()

def check_model_access(user_plan: str, model: str):
    allowed = PLAN_CONFIG.get(user_plan, {}).get("models", [])
    if "*" not in allowed and model not in allowed:
        raise HTTPException(403, f"Model '{model}' requires a higher plan. Upgrade to access it.")

def require_credits(user_id: int, credits: float, desc: str):
    if not _deduct(user_id, credits, desc):
        raise HTTPException(402, "Insufficient credits. Please top up your account.")

# ─── AUTH ENDPOINTS ───────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str
    plan: str = "STARTER"

@app.post("/api/v1/auth/register")
async def register(req: RegisterRequest):
    plan = req.plan.upper()
    if plan not in PLAN_CONFIG:
        raise HTTPException(400, f"Invalid plan. Choose: {list(PLAN_CONFIG.keys())}")
    plan_credits = PLAN_CONFIG[plan]["credits"]
    plan_expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO users (username,hashed_password,plan_type,credits,plan_expires) VALUES (?,?,?,?,?)",
                     (req.username, argon2.hash(req.password), plan, plan_credits, plan_expires))
        conn.commit()
        uid = conn.execute("SELECT id FROM users WHERE username=?", (req.username,)).fetchone()[0]
        conn.close()
        _add_credits(uid, plan_credits, 'SUBSCRIPTION', f"{plan} plan activation")
        return {"status": "success", "plan": plan, "credits": plan_credits,
                "message": f"Account created. {plan_credits} credits added. Plan valid until {plan_expires[:10]}."}
    except Exception as e:
        conn.close()
        raise HTTPException(400, "Username already exists")

@app.post("/api/v1/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT hashed_password FROM users WHERE username=?", (form_data.username,)).fetchone()
    conn.close()
    if not row or not argon2.verify(form_data.password, row[0]):
        raise HTTPException(400, "Invalid credentials")
    return {"access_token": make_token(form_data.username), "token_type": "bearer"}

@app.get("/api/v1/user/me")
async def get_me(user=Depends(get_user)):
    return user

# ─── CHAT COMPLETION ENDPOINTS ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    provider: str
    model: str
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False
    kb_enabled: bool = False

@app.get("/models")
async def get_models():
    """Return available models for each provider"""
    return {
        "gemini": ["gemini-1.5-flash", "gemini-1.5-pro"],
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "openrouter": ["gpt-4o", "claude-sonnet-4", "gpt-3.5-turbo"],
        "ollama": ["llama3", "mistral", "phi3"]
    }

@app.post("/chat/completions")
async def chat_completion(req: ChatRequest, x_api_key: str = Header(None)):
    """Main chat completion endpoint with streaming and RAG support"""
    api_key = x_api_key or os.environ.get(f"{req.provider.upper()}_API_KEY")

    if not api_key and req.provider != "ollama":
        raise HTTPException(401, f"API key required for {req.provider}. Set {req.provider.upper()}_API_KEY environment variable or provide x-api-key header.")

    provider = providers.get_provider(req.provider)
    if not provider:
        raise HTTPException(400, f"Unknown provider: {req.provider}")

    # RAG integration
    if req.kb_enabled:
        last_message = req.messages[-1]["content"]
        context = rag_manager.query(last_message, n_results=3)
        if context:
            req.messages = [
                {"role": "system", "content": f"Use the following context to answer:\n\n{context}"},
                *req.messages[:-1],
                {"role": "user", "content": f"Based on the context above, {req.messages[-1]['content']}"}
            ]

    start_time = time.time()

    if req.stream:
        async def generate():
            try:
                full_content = ""
                async for chunk in provider.stream_complete(req.model, req.messages, api_key):
                    yield chunk
                    # Extract content for logging
                    try:
                        chunk_data = json.loads(chunk) if isinstance(chunk, str) else chunk
                        if "choices" in chunk_data and "delta" in chunk_data["choices"][0]:
                            full_content += chunk_data["choices"][0]["delta"].get("content", "")
                    except:
                        pass
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                raise
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        try:
            response = provider.chat_complete(req.model, req.messages, api_key,
                                            temperature=req.temperature, max_tokens=req.max_tokens)
            latency_ms = int((time.time() - start_time) * 1000)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Log usage (without user for now)
            log_usage(0, req.provider, req.model, latency_ms, "success",
                     req.messages[-1]["content"] if req.messages else "", content)
            return response
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            log_usage(0, req.provider, req.model, latency_ms, "error",
                     req.messages[-1]["content"] if req.messages else "", str(e))
            raise HTTPException(500, f"Provider error: {str(e)}")

# ─── RAG / KNOWLEDGE BASE ENDPOINTS ────────────────────────────────────────────
@app.post("/kb/upload")
async def kb_upload(file: UploadFile = File(...)):
    """Upload a document to the knowledge base"""
    try:
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        if file.filename.lower().endswith('.pdf'):
            rag_manager.ingest_pdf(temp_path, file.filename)
        else:
            # Assume text
            with open(temp_path, "r", encoding="utf-8") as f:
                text = f.read()
            rag_manager.ingest_text(text, file.filename, {"filename": file.filename})

        os.remove(temp_path)
        return {"status": "success", "message": "Document indexed successfully"}
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {str(e)}")

@app.get("/kb/docs")
async def list_kb_docs():
    """List documents in knowledge base"""
    try:
        docs = rag_manager.list_documents()
        return {"documents": docs.get('ids', [])}
    except Exception as e:
        raise HTTPException(500, f"Failed to list documents: {str(e)}")

# ─── BILLING ENDPOINTS ────────────────────────────────────────────────────────
class TopupRequest(BaseModel):
    pack_id: str  # micro / builder / power / studio

@app.post("/api/v1/billing/topup")
async def topup(req: TopupRequest, user=Depends(get_user)):
    pack = TOPUP_PACKS.get(req.pack_id.lower())
    if not pack: raise HTTPException(400, f"Unknown pack. Choose: {list(TOPUP_PACKS.keys())}")
    _add_credits(user["id"], pack["credits"], 'TOPUP', pack["label"])
    conn = sqlite3.connect(DB_PATH)
    new_bal = conn.execute("SELECT credits FROM users WHERE id=?", (user["id"],)).fetchone()[0]
    conn.close()
    return {"status":"success","pack":pack["label"],"credits_added":pack["credits"],"new_balance":new_bal,
            "note": f"Simulated payment of ${pack['price']}. Integrate Stripe webhook to trigger this in production."}

@app.get("/api/v1/billing/plans")
async def list_plans():
    return PLAN_CONFIG

@app.get("/api/v1/billing/packs")
async def list_packs():
    return TOPUP_PACKS

@app.post("/api/v1/billing/upgrade")
async def upgrade_plan(new_plan: str, user=Depends(get_user)):
    plan = new_plan.upper()
    if plan not in PLAN_CONFIG: raise HTTPException(400, "Invalid plan")
    bonus = PLAN_CONFIG[plan]["credits"]
    exp = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET plan_type=?, plan_expires=? WHERE id=?", (plan, exp, user["id"]))
    conn.commit(); conn.close()
    _add_credits(user["id"], bonus, 'SUBSCRIPTION', f"Upgraded to {plan}")
    return {"status": "upgraded", "plan": plan, "credits_added": bonus, "expires": exp[:10]}

@app.get("/api/v1/billing/ledger")
async def my_ledger(user=Depends(get_user)):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT amount,type,description,timestamp FROM credit_ledger WHERE user_id=? ORDER BY id DESC LIMIT 50",
                        (user["id"],)).fetchall()
    conn.close()
    return [{"amount":r[0],"type":r[1],"description":r[2],"time":r[3]} for r in rows]

# ─── ADMIN ENDPOINTS ──────────────────────────────────────────────────────────
@app.get("/api/v1/admin/stats")
async def admin_stats(admin=Depends(get_admin)):
    conn = sqlite3.connect(DB_PATH)
    total_spend  = conn.execute("SELECT SUM(cost_usd) FROM usage_logs").fetchone()[0] or 0
    total_users  = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin=0").fetchone()[0]
    arr_estimate = 0
    plan_rows = conn.execute("SELECT plan_type,COUNT(*) FROM users WHERE is_admin=0 GROUP BY plan_type").fetchall()
    plan_breakdown = []
    for pr in plan_rows:
        plan_name, cnt = pr[0], pr[1]
        price = PLAN_CONFIG.get(plan_name, {}).get("price", 0)
        mrr = cnt * price
        arr_estimate += mrr * 12
        plan_breakdown.append({"plan": plan_name, "users": cnt, "mrr": mrr})
    models = [{"model":r[0],"count":r[1],"cost":r[2]} for r in
              conn.execute("SELECT model,COUNT(*),SUM(cost_usd) FROM usage_logs GROUP BY model").fetchall()]
    recent = [{"id":r[0],"time":r[1],"provider":r[2],"model":r[3],"cost":r[4],"status":r[5]} for r in
              conn.execute("SELECT id,timestamp,provider,model,cost_usd,status FROM usage_logs ORDER BY id DESC LIMIT 20").fetchall()]
    conn.close()
    return {"total_spend":total_spend,"total_users":total_users,"arr_estimate":arr_estimate,
            "plan_breakdown":plan_breakdown,"models":models,"recent_logs":recent}

@app.get("/api/v1/admin/users")
async def admin_users(admin=Depends(get_admin)):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id,username,plan_type,credits,plan_expires,is_admin FROM users").fetchall()
    conn.close()
    return [{"id":r[0],"username":r[1],"plan":r[2],"credits":r[3],"expires":r[4],"admin":r[5]} for r in rows]

@app.post("/api/v1/admin/users/{user_id}/grant")
async def grant_credits(user_id: int, amount: float, admin=Depends(get_admin)):
    _add_credits(user_id, amount, 'BONUS', f"Admin grant by {admin['username']}")
    return {"status": "credited", "amount": amount}

@app.post("/api/v1/admin/users/{user_id}/set-plan")
async def set_plan(user_id: int, plan: str, admin=Depends(get_admin)):
    plan = plan.upper()
    if plan not in PLAN_CONFIG: raise HTTPException(400, "Invalid plan")
    exp = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET plan_type=?,plan_expires=? WHERE id=?", (plan, exp, user_id))
    conn.commit(); conn.close()
    _add_credits(user_id, PLAN_CONFIG[plan]["credits"], 'SUBSCRIPTION', f"Plan set by admin to {plan}")
    return {"status": "updated", "plan": plan}

@app.post("/api/v1/admin/star/{log_id}")
async def toggle_star(log_id: int, admin=Depends(get_admin)):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE usage_logs SET is_starred=1-is_starred WHERE id=?", (log_id,))
    conn.commit(); conn.close()
    return {"status": "toggled"}

@app.get("/api/v1/admin/export")
async def export_starred(admin=Depends(get_admin)):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT prompt,response FROM usage_logs WHERE is_starred=1").fetchall()
    conn.close()
    jsonl = "\n".join(json.dumps({"messages":[{"role":"user","content":r[0]},{"role":"assistant","content":r[1]}]}) for r in rows)
    return StreamingResponse(iter([jsonl]), media_type="application/x-jsonlines",
                             headers={"Content-Disposition":"attachment;filename=finetune.jsonl"})

# ─── CHAT COMPLETIONS (core sandbox) ─────────────────────────────────────────
class ChatRequest(BaseModel):
    provider: str
    model: str
    messages: List[Dict[str, Any]]
    temperature: float = 0.7
    stream: bool = False
    kb_enabled: bool = False

@app.post("/api/v1/chat/completions")
async def chat_completions(req: ChatRequest, user=Depends(get_user)):
    check_model_access(user["plan"], req.model)
    require_credits(user["id"], ACTION_COSTS["chat"], f"chat: {req.model}")
    import sys as _sys; _sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from providers import get_provider
    provider = get_provider(req.provider)
    if not provider: raise HTTPException(400, f"Unknown provider: {req.provider}")
    messages = req.messages
    if req.kb_enabled:
        from rag_manager import rag_manager
        query = next((m["content"] for m in reversed(messages) if m["role"]=="user"), "")
        ctx = rag_manager.query(query)
        if ctx: messages = [{"role":"system","content":f"Context:\n{ctx}"}] + messages
    env_key = {"groq":"GROQ_API_KEY","google":"GEMINI_API_KEY","openrouter":"OPENROUTER_API_KEY"}.get(req.provider,"")
    api_key = os.environ.get(env_key,"")
    t0 = time.time()
    try:
        result = provider.chat_complete(model=req.model, messages=messages,
                                        temperature=req.temperature, api_key=api_key)
        latency = int((time.time()-t0)*1000)
        content = result["choices"][0]["message"]["content"]
        log_usage(user["id"], req.provider, req.model, latency, "ok",
                  messages[-1].get("content",""), content)
        return result
    except Exception as e:
        log_usage(user["id"], req.provider, req.model, 0, f"error:{str(e)[:50]}")
        raise HTTPException(500, str(e))

@app.get("/api/v1/models")
async def list_models():
    return {"models": {
        "groq":       ["llama-3.3-70b-versatile","llama-3.1-8b-instant"],
        "google":     ["gemini-1.5-pro","gemini-1.5-flash"],
        "openrouter": ["gpt-4o","claude-sonnet-4","mistral-7b"],
        "ollama":     ["llama3","mistral","phi3"]
    }}

# ─── KB / RAG ─────────────────────────────────────────────────────────────────
@app.post("/api/v1/kb/upload")
async def kb_upload(file: UploadFile = File(...), user=Depends(get_user)):
    require_credits(user["id"], ACTION_COSTS["rag_query"], "KB upload")
    import sys as _sys; _sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from rag_manager import rag_manager
    dest = os.path.join(DATA_DIR, "uploads", file.filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f: f.write(await file.read())
    if file.filename.endswith(".pdf"): rag_manager.ingest_pdf(dest)
    else: rag_manager.ingest_text(open(dest).read())
    return {"status": "indexed", "file": file.filename}

# ─── SINGULARITY / SELF-MONITOR ───────────────────────────────────────────────
@app.post("/api/v1/singularity/evolve")
async def trigger_evolution(admin=Depends(get_admin)):
    from agents.self_monitor import SelfMonitorAgent, RecursiveCoderAgent
    from core.hot_swap import hot_swapper
    kernel  = NexusKernel()
    monitor = SelfMonitorAgent(kernel, db_path=DB_PATH)
    coder   = RecursiveCoderAgent(kernel)
    logs    = []
    def log(m): logs.append(m); print(m)
    log("🧠 Self-Monitor: Analysing usage logs...")
    proposal = await monitor.analyze_performance("groq","llama-3.3-70b-versatile")
    log(f"💡 Proposal: {proposal[:120]}...")
    target = os.path.join(NEXUS_OS_PATH, "core", "kernel.py")
    success = await coder.self_upgrade_core(proposal, target, "groq","llama-3.3-70b-versatile")
    if success:
        hot_swapper.reload_core("kernel")
        log("🚀 EVOLUTION COMPLETE — Kernel hot-swapped.")
    else:
        log("⚠️ Evolution attempt failed — kernel unchanged.")
    return {"success": success, "proposal_preview": proposal[:300], "logs": logs}

@app.get("/api/v1/singularity/status")
async def evolution_status(admin=Depends(get_admin)):
    kernel_path = os.path.join(NEXUS_OS_PATH, "core", "kernel.py")
    mtime = os.path.getmtime(kernel_path) if os.path.exists(kernel_path) else 0
    conn = sqlite3.connect(DB_PATH)
    errors = conn.execute("SELECT COUNT(*) FROM usage_logs WHERE status LIKE 'error%'").fetchone()[0]
    total  = conn.execute("SELECT COUNT(*) FROM usage_logs").fetchone()[0]
    conn.close()
    return {"kernel_last_modified": datetime.fromtimestamp(mtime).isoformat() if mtime else None,
            "total_requests": total, "error_count": errors,
            "error_rate": round(errors/total*100,1) if total else 0}

# ─── ANALYTICS ────────────────────────────────────────────────────────────────
@app.get("/api/v1/analytics")
async def analytics(user=Depends(get_user)):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""SELECT provider,COUNT(*),SUM(cost_usd),AVG(latency_ms)
                           FROM usage_logs WHERE user_id=? GROUP BY provider""",
                        (user["id"],)).fetchall()
    conn.close()
    return [{"provider":r[0],"requests":r[1],"cost":r[2],"avg_latency":r[3]} for r in rows]

# ─── NEXUS APP BUILDER (credit-gated) ─────────────────────────────────────────
@app.get("/api/v1/nexus/app-build")
async def stream_nexus_app_build(task: str, token: str):
    user_row = None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT id,plan_type,credits FROM users WHERE username=?",
                           (payload["sub"],)).fetchone()
        conn.close()
        if not row: raise Exception()
        user_row = {"id": row[0], "plan": row[1], "credits": row[2]}
    except:
        raise HTTPException(401, "Unauthorized")

    if user_row["plan"] not in ("PRO","ENTERPRISE"):
        raise HTTPException(403, "Full-Stack App Builder requires PRO or ENTERPRISE plan.")

    # Pre-charge: 7 agent steps × 1cr = 7 credits upfront
    require_credits(user_row["id"], 7, "App-build workflow (7 agent steps)")

    kernel = NexusKernel()
    architect    = AppArchitectAgent(kernel)
    devops       = DevOpsAgent(kernel)
    planner      = PlannerAgent(kernel)
    hive_agg     = HiveAggregator(kernel)
    coder        = CoderAgent(kernel)

    async def gen():
        try:
            for agent, msg, extra_fn in [
                ("architect", "Architecting 2026 tech stack...", None),
            ]:
                yield f"data: {json.dumps({'type':'agent_start','agent':agent})}\n\n"
                yield f"data: {json.dumps({'type':'log','agent':agent,'message':msg})}\n\n"

            design = await architect.architect(task, "groq", "llama-3.3-70b-versatile")
            yield f"data: {json.dumps({'type':'design','design':design})}\n\n"

            project_name = task.lower().replace(" ","-")[:20]
            base_path = f"projects/{project_name}"
            fs_tool.mkdir(base_path)
            architect.create_structure_recursive(base_path, design['structure'])

            yield f"data: {json.dumps({'type':'agent_start','agent':'devops'})}\n\n"
            dc = await devops.configure_deployment(design['stack'], design['structure'], "groq", "llama-3.3-70b-versatile")
            devops.write_configs(base_path, dc)
            yield f"data: {json.dumps({'type':'log','agent':'devops','message':'Docker + CI/CD configs written.'})}\n\n"

            yield f"data: {json.dumps({'type':'agent_start','agent':'planner'})}\n\n"
            task_tree = await planner.decompose(f"Build {task}", "groq", "llama-3.3-70b-versatile")

            for step in task_tree:
                sub = step['task']
                yield f"data: {json.dumps({'type':'log','agent':'researcher','message':f'Hive Poll: {sub}'})}\n\n"
                hive_out = await kernel.hive_poll([{"provider":"groq","model":"llama-3.3-70b-versatile"}],
                                                   [{"role":"user","content":sub}])
                brief = await hive_agg.aggregate(sub, hive_out, "groq", "llama-3.3-70b-versatile")
                yield f"data: {json.dumps({'type':'agent_start','agent':'coder'})}\n\n"
                files = [f"{base_path}/{p}" for p in step.get('files_to_create', [])] or [f"{base_path}/main.py"]
                await coder.build_files(f"{sub}\nBrief:{brief}", files, "groq", "llama-3.3-70b-versatile")
                yield f"data: {json.dumps({'type':'log','agent':'coder','message':f'Files built: {files}'})}\n\n"

            yield f"data: {json.dumps({'type':'complete','project_path':base_path})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

# ─── FRONTIER 1: AUTO-DEPLOY ──────────────────────────────────────────────────
@app.post("/api/v1/autodeploy/trigger")
async def trigger_deploy(admin=Depends(get_admin)):
    kernel = NexusKernel()
    agent  = AutoDeployAgent(kernel)
    service_url = os.environ.get("RENDER_SERVICE_URL",
                                  "https://nexus-backend.onrender.com")
    logs = []
    result = await agent.full_deploy_pipeline(service_url, log_fn=logs.append)
    return {"result": result, "logs": logs}

@app.get("/api/v1/autodeploy/status")
async def deploy_status(admin=Depends(get_admin)):
    render_key = os.environ.get("RENDER_API_KEY","")
    svc_id     = os.environ.get("RENDER_SERVICE_ID","")
    if not render_key or not svc_id:
        return {"status": "unconfigured",
                "message": "Set RENDER_API_KEY and RENDER_SERVICE_ID env vars"}
    import httpx
    async with httpx.AsyncClient() as c:
        r = await c.get(f"https://api.render.com/v1/services/{svc_id}/deploys?limit=3",
                        headers={"Authorization": f"Bearer {render_key}"})
    return {"deploys": r.json() if r.status_code == 200 else [], "http": r.status_code}

# ─── FRONTIER 2: AUTONOMOUS MODEL DISCOVERY ───────────────────────────────────
@app.post("/api/v1/models/discover")
async def discover_models(admin=Depends(get_admin)):
    kernel   = NexusKernel()
    explorer = AutonomousModelResearcher(kernel)
    logs = []
    result = await explorer.discover_and_register(DB_PATH, log_fn=logs.append)
    return {"result": result, "logs": logs}

@app.get("/api/v1/models/registry")
async def get_model_registry(user=Depends(get_user)):
    import json as _json
    from agents.model_researcher import MODEL_REGISTRY_PATH
    if not os.path.exists(MODEL_REGISTRY_PATH):
        return {"models": {}, "last_updated": None}
    with open(MODEL_REGISTRY_PATH) as f:
        return _json.load(f)

# ─── FRONTIER 3: SWARM INTELLIGENCE ──────────────────────────────────────────
class SwarmRequest(BaseModel):
    goal: str
    num_nodes: int = 3

@app.post("/api/v1/swarm/run")
async def run_swarm(req: SwarmRequest, admin=Depends(get_admin)):
    if req.num_nodes < 1 or req.num_nodes > 8:
        raise HTTPException(400, "num_nodes must be 1–8")
    kernel = NexusKernel()
    orch   = SwarmOrchestrator(kernel, _swarm_bus)
    specs  = ["research", "coding", "analysis", "review",
              "documentation", "testing", "optimization", "security"]
    nodes  = [SwarmNode(kernel, _swarm_bus,
                        name=f"Node-{i+1}",
                        specialization=specs[i % len(specs)])
              for i in range(req.num_nodes)]
    logs = []
    result = await orch.run_swarm(req.goal, nodes, log_fn=logs.append)
    return {"result": result, "logs": logs}

@app.get("/api/v1/swarm/nodes")
async def swarm_nodes(user=Depends(get_user)):
    return {"nodes": _swarm_bus.get_live_nodes()}

@app.get("/api/v1/swarm/stream")
async def swarm_stream(goal: str, num_nodes: int = 3, token: str = ""):
    """SSE endpoint so Dashboard can watch the swarm in real-time."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        conn = sqlite3.connect(DB_PATH)
        row  = conn.execute("SELECT is_admin FROM users WHERE username=?",
                            (payload["sub"],)).fetchone()
        conn.close()
        if not row or not row[0]: raise Exception()
    except:
        raise HTTPException(401, "Unauthorized")

    kernel = NexusKernel()
    orch   = SwarmOrchestrator(kernel, _swarm_bus)
    specs  = ["research", "coding", "analysis", "review"]
    n      = min(max(num_nodes, 1), 4)
    nodes  = [SwarmNode(kernel, _swarm_bus, f"Node-{i+1}", specs[i % len(specs)])
              for i in range(n)]

    async def swarm_gen():
        def emit(msg):
            return f"data: {json.dumps({'type':'log','message':msg})}\n\n"
        yield f"data: {json.dumps({'type':'start','nodes':n,'goal':goal[:80]})}\n\n"
        logs = []
        try:
            result = await orch.run_swarm(goal, nodes, log_fn=logs.append)
            for l in logs:
                yield emit(l)
            yield f"data: {json.dumps({'type':'complete','consensus':result['consensus'][:500],'nodes_used':result['nodes_used']})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

    return StreamingResponse(swarm_gen(), media_type="text/event-stream")

# ─── HEALTH & ROOT ────────────────────────────────────────────────────────────
@app.get("/health")
async def health(): return {"status": "ok", "version": "8.0"}

@app.get("/")
async def root(): return {"name": "Project Nexus API", "version": "8.0", "docs": "/docs"}

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    pricing_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "pricing.html"
    )
    with open(pricing_path, "r") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
