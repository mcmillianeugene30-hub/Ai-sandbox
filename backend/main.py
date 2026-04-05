"""
Project Nexus API — v9.0 Production-Ready
Single unified FastAPI application.
All endpoints under /api/v1 except /health and / (root).
"""

# ─── STANDARD LIBRARY ─────────────────────────────────────────────────────────
import os
import sys
import json
import time
import uuid
import sqlite3
import asyncio
import shutil
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, AsyncGenerator

# ─── SLOWAPI ──────────────────────────────────────────────────────────────────
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# ─── PYTHON PATH ─ resolve once at module level ────────────────────────────────
PROJECT_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR   = os.path.dirname(os.path.abspath(__file__))
NEXUS_OS_PATH = os.environ.get("NEXUS_OS_PATH", os.path.join(PROJECT_ROOT, "nexus-ai-os"))

for _p in (NEXUS_OS_PATH, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ─── THIRD-PARTY ──────────────────────────────────────────────────────────────
import jwt
import tiktoken
from argon2 import PasswordHasher as _PH
from argon2.exceptions import VerifyMismatchError as _VME
from fastapi import (
    FastAPI, HTTPException, Depends, Header,
    UploadFile, File, Form, Request, status,
    BackgroundTasks
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

# ─── LOCAL IMPORTS ────────────────────────────────────────────────────────────
import providers
from rag_manager import rag_manager

# Nexus-OS imports (guarded so a missing optional dep doesn't crash startup)
try:
    from core.kernel   import NexusKernel
    from core.swarm    import SwarmBus, SwarmNode, SwarmOrchestrator
    from core.hot_swap import hot_swapper
    from agents.architect      import AppArchitectAgent
    from agents.devops         import DevOpsAgent
    from agents.planner        import PlannerAgent
    from agents.researcher     import ResearcherAgent
    from agents.coder          import CoderAgent
    from agents.reviewer       import ReviewerAgent
    from agents.hive_aggregator import HiveAggregator
    from agents.auto_deploy    import AutoDeployAgent
    from agents.model_researcher import AutonomousModelResearcher, MODEL_REGISTRY_PATH
    from agents.self_monitor   import SelfMonitorAgent, RecursiveCoderAgent
    from tools.fs_tool         import fs_tool
    _NEXUS_AVAILABLE = True
except ImportError as _e:
    print(f"⚠️  Nexus-OS modules not fully loaded: {_e}")
    _NEXUS_AVAILABLE = False

# ─── CRYPTO HELPERS ───────────────────────────────────────────────────────────
_ph = _PH()

class argon2:
    @staticmethod
    def hash(password: str) -> str:
        return _ph.hash(password)

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        try:
            return _ph.verify(hashed, password)
        except _VME:
            return False

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
SECRET_KEY         = os.environ.get("SECRET_KEY", "nexus_super_secret_key_2026")
ALGORITHM          = "HS256"
TOKEN_EXP_MINUTES  = int(os.environ.get("TOKEN_EXP_MINUTES", 600))

CREDIT_PRICE_USD = 0.10  # 1 credit = $0.10

PLAN_CONFIG: Dict[str, Any] = {
    "STARTER": {
        "price":   9.00,
        "credits": 90,
        "models":  ["llama-3.1-8b-instant", "gemini-1.5-flash", "mistral-7b"],
    },
    "PRO": {
        "price":   29.00,
        "credits": 150,
        "models":  [
            "llama-3.1-8b-instant", "llama-3.3-70b-versatile",
            "gemini-1.5-flash", "gemini-1.5-pro",
            "mistral-7b", "llama3",
        ],
    },
    "ENTERPRISE": {
        "price":   99.00,
        "credits": 600,
        "models":  ["*"],
    },
}

ACTION_COSTS: Dict[str, float] = {
    "chat":       0.1,
    "agent_step": 1.0,
    "deploy":     5.0,
    "rag_query":  0.5,
}

TOPUP_PACKS: Dict[str, Any] = {
    "micro":   {"price": 5.00,  "credits": 55,  "label": "Micro Pack (+10% bonus)"},
    "builder": {"price": 10.00, "credits": 115, "label": "Builder Pack (+15% bonus)"},
    "power":   {"price": 25.00, "credits": 300, "label": "Power Pack (+20% bonus)"},
    "studio":  {"price": 50.00, "credits": 650, "label": "Studio Pack (+30% bonus)"},
}

AVAILABLE_MODELS: Dict[str, List[str]] = {
    "groq":       ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    "google":     ["gemini-1.5-pro", "gemini-1.5-flash"],
    "openrouter": ["gpt-4o", "claude-sonnet-4", "mistral-7b", "gpt-3.5-turbo"],
    "ollama":     ["llama3", "mistral", "phi3"],
}

PROVIDER_ENV_KEYS: Dict[str, str] = {
    "groq":       "GROQ_API_KEY",
    "google":     "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

# ─── PERSISTENT STORAGE ───────────────────────────────────────────────────────
DATA_DIR    = os.environ.get(
    "RENDER_DISK_PATH",
    os.path.join(BACKEND_DIR, "data"),
)
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
CHROMA_DIR  = os.environ.get(
    "CHROMA_DB_PATH",
    os.path.join(BACKEND_DIR, "chroma_db"),
)
DB_PATH = os.path.join(DATA_DIR, "usage.db")

os.makedirs(DATA_DIR,    exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR,  exist_ok=True)

# ─── DATABASE SETUP ───────────────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    """Return a new thread-local SQLite connection (WAL mode for concurrency)."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_conn()
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT    UNIQUE NOT NULL,
            hashed_password TEXT    NOT NULL,
            is_admin        INTEGER DEFAULT 0,
            plan_type       TEXT    DEFAULT 'NONE',
            credits         REAL    DEFAULT 0,
            plan_expires    TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS credit_ledger (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      REAL    NOT NULL,
            type        TEXT    NOT NULL,
            description TEXT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP,
            provider     TEXT,
            model        TEXT,
            latency_ms   INTEGER,
            status       TEXT,
            prompt       TEXT,
            response     TEXT,
            cost_usd     REAL DEFAULT 0,
            credits_used REAL DEFAULT 0,
            is_starred   INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pricing_config (
            provider        TEXT,
            model           TEXT,
            input_cost_1m   REAL,
            output_cost_1m  REAL,
            PRIMARY KEY (provider, model)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            token       TEXT UNIQUE NOT NULL,
            expires_at  DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Seed admin user (idempotent)
    c.execute(
        "INSERT OR IGNORE INTO users (username, hashed_password, is_admin, plan_type, credits) "
        "VALUES (?,?,?,?,?)",
        ("nexus", argon2.hash("nexus2026"), 1, "ENTERPRISE", 9_999_999),
    )

    # Seed 2026 provider pricing
    c.executemany(
        "INSERT OR IGNORE INTO pricing_config VALUES (?,?,?,?)",
        [
            ("groq",       "llama-3.3-70b-versatile", 0.59,  0.79),
            ("groq",       "llama-3.1-8b-instant",    0.05,  0.08),
            ("google",     "gemini-1.5-pro",           3.50, 10.50),
            ("google",     "gemini-1.5-flash",         0.075, 0.30),
            ("openrouter", "gpt-4o",                   5.00, 15.00),
            ("openrouter", "claude-sonnet-4",          3.00, 15.00),
        ],
    )

    conn.commit()
    conn.close()


init_db()

# ─── SWARM BUS (singleton per process) ────────────────────────────────────────
_swarm_bus = SwarmBus() if _NEXUS_AVAILABLE else None

# ─── FASTAPI APP ──────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "Project Nexus API",
    version     = "9.0",
    description = "Unified production-ready AI sandbox — credits, RAG, agents, swarm.",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://ai-sandbox-nexus.vercel.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins      = [FRONTEND_URL, "http://localhost:3000", "http://localhost:8080"],
    allow_origin_regex = r"https://.*\.vercel\.app",
    allow_methods      = ["*"],
    allow_headers      = ["*"],
    allow_credentials  = True,
)

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────
def make_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXP_MINUTES),
        "type": "access"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def make_refresh_token(user_id: int) -> str:
    token = uuid.uuid4().hex
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES (?,?,?)",
        (user_id, token, expires_at)
    )
    conn.commit()
    conn.close()
    return token


async def get_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise ValueError("Missing sub claim")
        conn = get_conn()
        row  = conn.execute(
            "SELECT id, username, is_admin, plan_type, credits, plan_expires "
            "FROM users WHERE username=?",
            (username,),
        ).fetchone()
        conn.close()
        if not row:
            raise ValueError("User not found")
        return {
            "id":          row[0],
            "username":    row[1],
            "is_admin":    row[2],
            "plan":        row[3],
            "credits":     row[4],
            "plan_expires": row[5],
        }
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized — invalid or expired token.")


async def get_admin(user: Dict = Depends(get_user)) -> Dict[str, Any]:
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def _decode_token_param(token: str) -> Dict[str, Any]:
    """Decode a JWT passed as query-param (used by SSE endpoints)."""
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        conn = get_conn()
        row  = conn.execute(
            "SELECT id, username, is_admin, plan_type, credits FROM users WHERE username=?",
            (username,),
        ).fetchone()
        conn.close()
        if not row:
            raise ValueError("Not found")
        return {"id": row[0], "username": row[1], "is_admin": row[2], "plan": row[3], "credits": row[4]}
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ─── CREDIT ENGINE ────────────────────────────────────────────────────────────
def _deduct(user_id: int, amount: float, desc: str) -> bool:
    """Atomically deduct `amount` credits using BEGIN IMMEDIATE for write-lock."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute(
            "UPDATE users SET credits = credits - ? WHERE id = ? AND credits >= ?",
            (amount, user_id, amount),
        )
        ok = c.rowcount == 1
        if ok:
            c.execute(
                "INSERT INTO credit_ledger (user_id, amount, type, description) VALUES (?,?,?,?)",
                (user_id, -amount, "USAGE", desc),
            )
        conn.commit()
        return ok
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def _add_credits(user_id: int, amount: float, type_: str, desc: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE users SET credits = credits + ? WHERE id = ?",
        (amount, user_id),
    )
    conn.execute(
        "INSERT INTO credit_ledger (user_id, amount, type, description) VALUES (?,?,?,?)",
        (user_id, amount, type_, desc),
    )
    conn.commit()
    conn.close()


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Return estimated token count for a given text."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def token_cost_credits(provider: str, model: str, prompt: str, response: str):
    """Return (cost_usd, credits) based on token counts and stored pricing."""
    conn  = get_conn()
    rates = conn.execute(
        "SELECT input_cost_1m, output_cost_1m FROM pricing_config WHERE provider=? AND model=?",
        (provider, model),
    ).fetchone()
    conn.close()
    if not rates:
        return 0.0, 0.0
    
    in_tok    = count_tokens(prompt, model)
    out_tok   = count_tokens(response, model)
    cost_usd  = (in_tok / 1_000_000) * rates[0] + (out_tok / 1_000_000) * rates[1]
    return cost_usd, cost_usd / CREDIT_PRICE_USD


def log_usage(
    user_id:    int,
    provider:   str,
    model:      str,
    latency_ms: int,
    status_:    str,
    prompt:     str = "",
    response:   str = "",
) -> None:
    """Log a usage event and deduct token-cost credits (if any)."""
    cost_usd, credits = token_cost_credits(provider, model, prompt, response)
    if credits > 0:
        _deduct(user_id, credits, f"token cost: {model}")
    conn = get_conn()
    conn.execute(
        "INSERT INTO usage_logs "
        "(user_id, provider, model, latency_ms, status, prompt, response, cost_usd, credits_used) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, provider, model, latency_ms, status_, prompt, response, cost_usd, credits),
    )
    conn.commit()
    conn.close()


def check_model_access(user_plan: str, model: str) -> None:
    allowed = PLAN_CONFIG.get(user_plan, {}).get("models", [])
    if "*" not in allowed and model not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Model '{model}' is not available on the {user_plan} plan. Please upgrade.",
        )


def require_credits(user_id: int, amount: float, desc: str) -> None:
    if not _deduct(user_id, amount, desc):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please top up your account.",
        )


def _nexus_required() -> None:
    if not _NEXUS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Nexus-OS modules are not available in this environment.",
        )

# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=40)
    password: str = Field(..., min_length=6)
    plan: str     = Field("STARTER")

class ChatRequest(BaseModel):
    provider:    str
    model:       str
    messages:    List[Dict[str, Any]]
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens:  int   = Field(1024, ge=1, le=32768)
    stream:      bool  = False
    kb_enabled:  bool  = False

class TopupRequest(BaseModel):
    pack_id: str

class SwarmRequest(BaseModel):
    goal:      str
    num_nodes: int = Field(3, ge=1, le=8)

class AppBuildRequest(BaseModel):
    task:     str
    provider: str = "groq"
    model:    str = "llama-3.3-70b-versatile"

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH / ROOT
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND JOBS
# ═══════════════════════════════════════════════════════════════════════════════

async def autonomous_evolution_loop():
    """Autonomous background check for system errors and self-evolution."""
    while True:
        await asyncio.sleep(3600) # Check every hour
        try:
            conn = get_conn()
            # Calculate error rate in last 100 requests
            total = conn.execute("SELECT count(*) FROM usage_logs").fetchone()[0]
            if total > 50:
                errors = conn.execute(
                    "SELECT count(*) FROM usage_logs WHERE status != 'ok' AND timestamp > datetime('now', '-1 hour')"
                ).fetchone()[0]
                recent = conn.execute(
                    "SELECT count(*) FROM usage_logs WHERE timestamp > datetime('now', '-1 hour')"
                ).fetchone()[0]
                
                error_rate = errors / recent if recent > 0 else 0
                if error_rate > 0.15: # 15% error rate threshold
                    print(f"🧬 [SINGULARITY] High error rate detected ({error_rate:.2%}). Triggering evolution...")
                    # Trigger the evolution agent logic here or call internal function
                    # await singularity_evolve_internal()
            conn.close()
        except Exception as e:
            print(f"⚠️ Autonomous check failed: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(autonomous_evolution_loop())


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOKS  —  /api/v1/billing/webhook
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/billing/webhook", tags=["Billing"])
async def billing_webhook(request: Request):
    """Stripe/Lemon Squeezy Webhook Listener."""
    return {"status": "received"}


# ═══════════════════════════════════════════════════════════════════════════════
# WORKSPACES  —  /api/v1/workspaces
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/workspaces", tags=["Workspaces"])
async def list_workspaces(user: Dict = Depends(get_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, created_at FROM workspaces WHERE user_id=?",
        (user["id"],)
    ).fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "created": r[2]} for r in rows]


@app.post("/api/v1/workspaces", tags=["Workspaces"])
async def create_workspace(name: str, user: Dict = Depends(get_user)):
    conn = get_conn()
    conn.execute("INSERT INTO workspaces (user_id, name) VALUES (?,?)", (user["id"], name))
    conn.commit()
    conn.close()
    return {"status": "created"}


@app.put("/api/v1/workspaces/{ws_id}", tags=["Workspaces"])
async def update_workspace(ws_id: int, config: str = Form(...), user: Dict = Depends(get_user)):
    conn = get_conn()
    conn.execute(
        "UPDATE workspaces SET config=? WHERE id=? AND user_id=?",
        (config, ws_id, user["id"])
    )
    conn.commit()
    conn.close()
    return {"status": "updated"}


@app.get("/api/v1/workspaces/{ws_id}", tags=["Workspaces"])
async def get_workspace(ws_id: int, user: Dict = Depends(get_user)):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, name, config FROM workspaces WHERE id=? AND user_id=?",
        (ws_id, user["id"])
    ).fetchone()
    conn.close()
    if not row: raise HTTPException(404, "Workspace not found.")
    return {"id": row[0], "name": row[1], "config": row[2]}


# ═══════════════════════════════════════════════════════════════════════════════
# JUDGE  —  /api/v1/judge
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/judge", tags=["Chat"])
async def run_judge(req: JudgeRequest, user: Dict = Depends(get_user)):
    """LLM-as-a-Judge pairwise evaluation."""
    require_credits(user["id"], 2.0, "LLM Judge evaluation")
    
    prompt = f"""You are an impartial judge evaluating two AI responses.
    
    Original Prompt: {req.prompt}
    
    Response A: {req.res_a}
    Response B: {req.res_b}
    
    Rubric: {req.rubric}
    
    Output your verdict in JSON:
    {{
      "winner": "A" | "B" | "TIE",
      "score_a": 0-10,
      "score_b": 0-10,
      "reasoning": "..."
    }}
    """
    
    # Use a high-quality model for judging
    provider = providers.get_provider("groq")
    api_key = os.environ.get("GROQ_API_KEY", "")
    res = provider.chat_complete("llama-3.3-70b-versatile", [{"role": "user", "content": prompt}], api_key)
    
    content = res["choices"][0]["message"]["content"]
    verdict = kernel.extract_json(content)
    
    log_usage(user["id"], "judge", "llama-3.3-70b", 0, "ok", req.prompt, content)
    return verdict


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR  —  /api/v1/orchestrator/run
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/orchestrator/run", tags=["Nexus Agents"])
async def run_orchestrator(req: OrchestratorRequest, user: Dict = Depends(get_user)):
    """Run a visual graph/chain of agents."""
    require_credits(user["id"], float(len(req.chain)), "Orchestrator graph run")
    
    from orchestrator import orchestrator
    env_key = os.environ.get("GROQ_API_KEY", "")
    results = await orchestrator.execute_chain(req.chain, req.input, api_key=env_key)
    return {"results": results}


@app.get("/health", tags=["Meta"])
async def health():
    return {
        "status":       "ok",
        "version":      "9.0",
        "nexus_agents": _NEXUS_AVAILABLE,
        "timestamp":    datetime.utcnow().isoformat(),
    }


@app.get("/", tags=["Meta"])
async def root():
    return {
        "name":    "Project Nexus API",
        "version": "9.0",
        "docs":    "/docs",
    }


@app.get("/pricing", response_class=HTMLResponse, tags=["Meta"])
async def pricing_page():
    pricing_path = os.path.join(PROJECT_ROOT, "frontend", "pricing.html")
    try:
        with open(pricing_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="pricing.html not found.")

# ═══════════════════════════════════════════════════════════════════════════════
# AUTH  —  /api/v1/auth/*
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/auth/register", tags=["Auth"])
@limiter.limit("5/minute")
async def register(req: RegisterRequest, request: Request):
    plan = req.plan.upper()
    if plan not in PLAN_CONFIG:
        raise HTTPException(400, f"Invalid plan. Choose from: {list(PLAN_CONFIG.keys())}")

    plan_credits = PLAN_CONFIG[plan]["credits"]
    plan_expires = (datetime.utcnow() + timedelta(days=30)).isoformat()

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, hashed_password, plan_type, credits, plan_expires) "
            "VALUES (?,?,?,?,?)",
            (req.username, argon2.hash(req.password), plan, plan_credits, plan_expires),
        )
        conn.commit()
        uid = conn.execute(
            "SELECT id FROM users WHERE username=?", (req.username,)
        ).fetchone()[0]
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Username already exists.")
    finally:
        conn.close()

    _add_credits(uid, plan_credits, "SUBSCRIPTION", f"{plan} plan activation")
    return {
        "status":  "success",
        "plan":    plan,
        "credits": plan_credits,
        "message": f"Account created. {plan_credits} credits added. Plan valid until {plan_expires[:10]}.",
    }


@app.post("/api/v1/auth/login", tags=["Auth"])
@limiter.limit("10/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_conn()
    row  = conn.execute(
        "SELECT id, hashed_password FROM users WHERE username=?",
        (form_data.username,),
    ).fetchone()
    conn.close()
    if not row or not argon2.verify(form_data.password, row[1]):
        raise HTTPException(400, "Invalid credentials.")
    
    access_token = make_token(form_data.username)
    refresh_token = make_refresh_token(row[0])
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.post("/api/v1/auth/refresh", tags=["Auth"])
async def refresh_token(refresh_token: str = Form(...)):
    conn = get_conn()
    row = conn.execute(
        "SELECT user_id, username FROM refresh_tokens "
        "JOIN users ON users.id = refresh_tokens.user_id "
        "WHERE token=? AND expires_at > ?",
        (refresh_token, datetime.utcnow().isoformat())
    ).fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(401, "Invalid or expired refresh token.")
    
    # Rotate refresh token
    conn.execute("DELETE FROM refresh_tokens WHERE token=?", (refresh_token,))
    conn.commit()
    
    new_access = make_token(row[1])
    new_refresh = make_refresh_token(row[0])
    conn.close()
    
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer"
    }


@app.get("/api/v1/user/me", tags=["Auth"])
async def get_me(user: Dict = Depends(get_user)):
    return user


@app.post("/api/v1/user/settings", tags=["Auth"])
async def update_settings(password: Optional[str] = Form(None), user: Dict = Depends(get_user)):
    if password:
        conn = get_conn()
        conn.execute(
            "UPDATE users SET hashed_password=? WHERE id=?",
            (argon2.hash(password), user["id"])
        )
        conn.commit()
        conn.close()
    return {"status": "updated"}

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS  —  /api/v1/models
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/models", tags=["Models"])
async def list_models():
    """Return all available models grouped by provider."""
    return {"models": AVAILABLE_MODELS}


@app.post("/api/v1/models/discover", tags=["Models"])
async def discover_models(admin: Dict = Depends(get_admin)):
    """Autonomously scan provider APIs for newly available models (admin only)."""
    _nexus_required()
    try:
        kernel   = NexusKernel()
        explorer = AutonomousModelResearcher(kernel)
        logs: List[str] = []
        result = await explorer.discover_and_register(DB_PATH, log_fn=logs.append)
        return {"result": result, "logs": logs}
    except Exception as e:
        raise HTTPException(500, f"Model discovery failed: {e}")


@app.get("/api/v1/models/registry", tags=["Models"])
async def get_model_registry(user: Dict = Depends(get_user)):
    """Return the locally cached model registry JSON."""
    _nexus_required()
    if not os.path.exists(MODEL_REGISTRY_PATH):
        return {"models": {}, "last_updated": None}
    try:
        with open(MODEL_REGISTRY_PATH) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(500, f"Could not read model registry: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# CHAT  —  /api/v1/chat/completions
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/chat/completions", tags=["Chat"])
async def chat_completions(req: ChatRequest, user: Dict = Depends(get_user)):
    """
    Unified chat completion endpoint.
    Supports: streaming, RAG context injection, credit deduction, and usage logging.
    """
    # ── Plan / credit checks ──────────────────────────────────────────────────
    check_model_access(user["plan"], req.model)
    require_credits(user["id"], ACTION_COSTS["chat"], f"chat: {req.model}")

    # ── Resolve provider ─────────────────────────────────────────────────────
    provider_impl = providers.get_provider(req.provider)
    if not provider_impl:
        raise HTTPException(400, f"Unknown provider: '{req.provider}'.")

    # ── Resolve API key ──────────────────────────────────────────────────────
    env_key = PROVIDER_ENV_KEYS.get(req.provider, "")
    api_key = os.environ.get(env_key, "")

    # ── RAG context injection ─────────────────────────────────────────────────
    messages = list(req.messages)
    if req.kb_enabled:
        try:
            last_user_msg = next(
                (m["content"] for m in reversed(messages) if m.get("role") == "user"),
                "",
            )
            ctx = rag_manager.query(last_user_msg, n_results=3)
            if ctx:
                messages = [{"role": "system", "content": f"Relevant context:\n\n{ctx}"}] + messages
        except Exception as rag_err:
            # RAG failure is non-fatal; log and continue without context
            print(f"⚠️ RAG query failed: {rag_err}")

    # ── Streaming response ────────────────────────────────────────────────────
    if req.stream:
        async def stream_gen() -> AsyncGenerator[str, None]:
            full_content = ""
            t0 = time.time()
            try:
                async for chunk in provider_impl.stream_complete(
                    req.model, messages, api_key,
                    temperature=req.temperature, max_tokens=req.max_tokens,
                ):
                    yield chunk
                    try:
                        data = json.loads(chunk.removeprefix("data: ").strip())
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        full_content += delta.get("content", "")
                    except Exception:
                        pass
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                latency = int((time.time() - t0) * 1000)
                log_usage(
                    user["id"], req.provider, req.model, latency,
                    "ok", messages[-1].get("content", ""), full_content,
                )

        return StreamingResponse(stream_gen(), media_type="text/event-stream")

    # ── Non-streaming response ────────────────────────────────────────────────
    t0 = time.time()
    try:
        result  = provider_impl.chat_complete(
            req.model, messages, api_key,
            temperature=req.temperature, max_tokens=req.max_tokens,
        )
        latency = int((time.time() - t0) * 1000)
        content = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        log_usage(user["id"], req.provider, req.model, latency, "ok",
                  messages[-1].get("content", ""), content)
        return result
    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        log_usage(user["id"], req.provider, req.model, latency,
                  f"error:{str(e)[:80]}", messages[-1].get("content", ""), "")
        raise HTTPException(500, f"Provider error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE  —  /api/v1/kb/*
# ═══════════════════════════════════════════════════════════════════════════════

def process_kb_file(dest: str, filename: str, user_id: int):
    """Background task for RAG indexing."""
    try:
        if filename.lower().endswith(".pdf"):
            rag_manager.ingest_pdf(dest, filename)
        else:
            with open(dest, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            rag_manager.ingest_text(text, filename, {"filename": filename})
        log_usage(user_id, "rag", "ingest", 0, "ok", filename, "")
    except Exception as e:
        print(f"⚠️ Background indexing failed for {filename}: {e}")


@app.post("/api/v1/kb/upload", tags=["Knowledge Base"])
async def kb_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: Dict       = Depends(get_user),
):
    """
    Upload a PDF or plain-text file for RAG indexing (background processed).
    """
    require_credits(user["id"], ACTION_COSTS["rag_query"], "KB upload")

    filename = file.filename or f"upload_{uuid.uuid4().hex}"
    dest     = os.path.join(UPLOADS_DIR, filename)

    try:
        content = await file.read()
        with open(dest, "wb") as fh:
            fh.write(content)

        background_tasks.add_task(process_kb_file, dest, filename, user["id"])
        return {"status": "processing", "file": filename, "message": "File received. Indexing in background."}
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(500, f"Upload failed: {e}")


@app.get("/api/v1/kb/docs", tags=["Knowledge Base"])
async def list_kb_docs(user: Dict = Depends(get_user)):
    """List all documents currently indexed in the knowledge base."""
    try:
        docs = rag_manager.list_documents()
        return {"documents": docs.get("ids", [])}
    except Exception as e:
        raise HTTPException(500, f"Failed to list documents: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# BILLING  —  /api/v1/billing/*
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/billing/plans", tags=["Billing"])
async def list_plans():
    return PLAN_CONFIG


@app.get("/api/v1/billing/packs", tags=["Billing"])
async def list_packs():
    return TOPUP_PACKS


@app.post("/api/v1/billing/topup", tags=["Billing"])
async def topup(req: TopupRequest, user: Dict = Depends(get_user)):
    pack = TOPUP_PACKS.get(req.pack_id.lower())
    if not pack:
        raise HTTPException(400, f"Unknown pack. Choose from: {list(TOPUP_PACKS.keys())}")
    _add_credits(user["id"], pack["credits"], "TOPUP", pack["label"])
    conn = get_conn()
    new_bal = conn.execute(
        "SELECT credits FROM users WHERE id=?", (user["id"],)
    ).fetchone()[0]
    conn.close()
    return {
        "status":        "success",
        "pack":          pack["label"],
        "credits_added": pack["credits"],
        "new_balance":   new_bal,
        "note":          f"Simulated payment of ${pack['price']:.2f}. "
                         "Integrate Stripe webhook to trigger this in production.",
    }


@app.post("/api/v1/billing/upgrade", tags=["Billing"])
async def upgrade_plan(new_plan: str, user: Dict = Depends(get_user)):
    plan = new_plan.upper()
    if plan not in PLAN_CONFIG:
        raise HTTPException(400, f"Invalid plan. Choose from: {list(PLAN_CONFIG.keys())}")
    exp = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn = get_conn()
    conn.execute(
        "UPDATE users SET plan_type=?, plan_expires=? WHERE id=?",
        (plan, exp, user["id"]),
    )
    conn.commit()
    conn.close()
    bonus = PLAN_CONFIG[plan]["credits"]
    _add_credits(user["id"], bonus, "SUBSCRIPTION", f"Upgraded to {plan}")
    return {"status": "upgraded", "plan": plan, "credits_added": bonus, "expires": exp[:10]}


@app.get("/api/v1/billing/ledger", tags=["Billing"])
async def my_ledger(user: Dict = Depends(get_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT amount, type, description, timestamp FROM credit_ledger "
        "WHERE user_id=? ORDER BY id DESC LIMIT 50",
        (user["id"],),
    ).fetchall()
    conn.close()
    return [
        {"amount": r[0], "type": r[1], "description": r[2], "time": r[3]}
        for r in rows
    ]

# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS  —  /api/v1/analytics
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/analytics", tags=["Analytics"])
async def analytics(user: Dict = Depends(get_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT provider, COUNT(*), SUM(cost_usd), AVG(latency_ms) "
        "FROM usage_logs WHERE user_id=? GROUP BY provider",
        (user["id"],),
    ).fetchall()
    conn.close()
    return [
        {"provider": r[0], "requests": r[1], "cost_usd": r[2], "avg_latency_ms": r[3]}
        for r in rows
    ]

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN  —  /api/v1/admin/*
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/admin/stats", tags=["Admin"])
async def admin_stats(admin: Dict = Depends(get_admin)):
    conn = get_conn()
    total_spend  = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM usage_logs").fetchone()[0]
    total_users  = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin=0").fetchone()[0]

    plan_rows = conn.execute(
        "SELECT plan_type, COUNT(*) FROM users WHERE is_admin=0 GROUP BY plan_type"
    ).fetchall()

    arr_estimate   = 0.0
    plan_breakdown = []
    for plan_name, cnt in plan_rows:
        price = PLAN_CONFIG.get(plan_name, {}).get("price", 0)
        mrr   = cnt * price
        arr_estimate += mrr * 12
        plan_breakdown.append({"plan": plan_name, "users": cnt, "mrr": round(mrr, 2)})

    models = [
        {"model": r[0], "count": r[1], "cost_usd": r[2]}
        for r in conn.execute(
            "SELECT model, COUNT(*), COALESCE(SUM(cost_usd),0) FROM usage_logs GROUP BY model"
        ).fetchall()
    ]

    recent = [
        {"id": r[0], "time": r[1], "provider": r[2], "model": r[3], "cost_usd": r[4], "status": r[5]}
        for r in conn.execute(
            "SELECT id, timestamp, provider, model, cost_usd, status "
            "FROM usage_logs ORDER BY id DESC LIMIT 20"
        ).fetchall()
    ]
    conn.close()
    return {
        "total_spend_usd": round(total_spend, 4),
        "total_users":     total_users,
        "arr_estimate":    round(arr_estimate, 2),
        "plan_breakdown":  plan_breakdown,
        "models":          models,
        "recent_logs":     recent,
    }


@app.get("/api/v1/admin/users", tags=["Admin"])
async def admin_users(admin: Dict = Depends(get_admin)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, plan_type, credits, plan_expires, is_admin FROM users"
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "username": r[1], "plan": r[2], "credits": r[3],
         "expires": r[4], "admin": bool(r[5])}
        for r in rows
    ]


@app.post("/api/v1/admin/users/{user_id}/grant", tags=["Admin"])
async def grant_credits(user_id: int, amount: float, admin: Dict = Depends(get_admin)):
    try:
        _add_credits(user_id, amount, "BONUS", f"Admin grant by {admin['username']}")
        return {"status": "credited", "amount": amount}
    except Exception as e:
        raise HTTPException(500, f"Failed to grant credits: {e}")


@app.post("/api/v1/admin/users/{user_id}/set-plan", tags=["Admin"])
async def set_plan(user_id: int, plan: str, admin: Dict = Depends(get_admin)):
    plan = plan.upper()
    if plan not in PLAN_CONFIG:
        raise HTTPException(400, f"Invalid plan. Choose from: {list(PLAN_CONFIG.keys())}")
    exp = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn = get_conn()
    conn.execute(
        "UPDATE users SET plan_type=?, plan_expires=? WHERE id=?",
        (plan, exp, user_id),
    )
    conn.commit()
    conn.close()
    _add_credits(user_id, PLAN_CONFIG[plan]["credits"], "SUBSCRIPTION", f"Plan set by admin → {plan}")
    return {"status": "updated", "plan": plan}


@app.post("/api/v1/admin/star/{log_id}", tags=["Admin"])
async def toggle_star(log_id: int, admin: Dict = Depends(get_admin)):
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE usage_logs SET is_starred = 1 - is_starred WHERE id=?",
            (log_id,),
        )
        conn.commit()
        starred = conn.execute(
            "SELECT is_starred FROM usage_logs WHERE id=?", (log_id,)
        ).fetchone()
        conn.close()
        return {"status": "toggled", "is_starred": bool(starred[0]) if starred else None}
    except Exception as e:
        raise HTTPException(500, f"Toggle star failed: {e}")


@app.get("/api/v1/admin/export", tags=["Admin"])
async def export_starred(admin: Dict = Depends(get_admin)):
    """Export starred logs as JSONL fine-tuning dataset."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT prompt, response FROM usage_logs WHERE is_starred=1"
    ).fetchall()
    conn.close()
    jsonl = "\n".join(
        json.dumps({
            "messages": [
                {"role": "user",      "content": r[0]},
                {"role": "assistant", "content": r[1]},
            ]
        })
        for r in rows
    )
    return StreamingResponse(
        iter([jsonl]),
        media_type="application/x-jsonlines",
        headers={"Content-Disposition": "attachment; filename=finetune.jsonl"},
    )

# ═══════════════════════════════════════════════════════════════════════════════
# NEXUS APP BUILDER  —  /api/v1/nexus/app-build
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/nexus/app-build", tags=["Nexus Agents"])
async def stream_nexus_app_build(task: str, token: str):
    """
    SSE stream for the full-stack app-build pipeline.
    Requires PRO or ENTERPRISE plan. Pre-charges 7 agent-step credits.
    """
    _nexus_required()
    user_row = _decode_token_param(token)

    if user_row["plan"] not in ("PRO", "ENTERPRISE"):
        raise HTTPException(403, "Full-Stack App Builder requires PRO or ENTERPRISE plan.")

    require_credits(user_row["id"], 7, "App-build workflow (7 agent steps)")

    kernel    = NexusKernel()
    architect = AppArchitectAgent(kernel)
    devops    = DevOpsAgent(kernel)
    planner   = PlannerAgent(kernel)
    hive_agg  = HiveAggregator(kernel)
    coder     = CoderAgent(kernel)

    async def gen() -> AsyncGenerator[str, None]:
        try:
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'architect'})}\n\n"
            yield f"data: {json.dumps({'type': 'log', 'agent': 'architect', 'message': 'Architecting 2026 tech stack...'})}\n\n"

            design = await architect.architect(task, "groq", "llama-3.3-70b-versatile")
            yield f"data: {json.dumps({'type': 'design', 'design': design})}\n\n"

            project_name = task.lower().replace(" ", "-")[:20]
            base_path    = f"projects/{project_name}"
            fs_tool.mkdir(base_path)
            architect.create_structure_recursive(base_path, design.get("structure", {}))
            log_usage(user_row["id"], "agent", "architect", 0, "ok", task, "")

            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'devops'})}\n\n"
            dc = await devops.configure_deployment(
                design.get("stack"), design.get("structure"), "groq", "llama-3.3-70b-versatile"
            )
            devops.write_configs(base_path, dc)
            yield f"data: {json.dumps({'type': 'log', 'agent': 'devops', 'message': 'Docker + CI/CD configs written.'})}\n\n"
            log_usage(user_row["id"], "agent", "devops", 0, "ok", task, "")

            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'planner'})}\n\n"
            task_tree = await planner.decompose(f"Build {task}", "groq", "llama-3.3-70b-versatile")
            log_usage(user_row["id"], "agent", "planner", 0, "ok", task, "")

            for step in task_tree:
                sub = step.get("task", "")
                yield f"data: {json.dumps({'type': 'log', 'agent': 'hive', 'message': f'Hive Poll: {sub}'})}\n\n"
                hive_out = await kernel.hive_poll(
                    [{"provider": "groq", "model": "llama-3.3-70b-versatile"}],
                    [{"role": "user", "content": sub}],
                )
                brief = await hive_agg.aggregate(sub, hive_out, "groq", "llama-3.3-70b-versatile")

                yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'coder'})}\n\n"
                files = [f"{base_path}/{p}" for p in step.get("files_to_create", [])] \
                        or [f"{base_path}/main.py"]
                await coder.build_files(f"{sub}\nBrief:{brief}", files, "groq", "llama-3.3-70b-versatile")
                yield f"data: {json.dumps({'type': 'log', 'agent': 'coder', 'message': f'Files built: {files}'})}\n\n"
                log_usage(user_row["id"], "agent", "coder", 0, "ok", sub, "")

            yield f"data: {json.dumps({'type': 'complete', 'project_path': base_path})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-DEPLOY  —  /api/v1/autodeploy/*
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/autodeploy/trigger", tags=["AutoDeploy"])
async def trigger_deploy(admin: Dict = Depends(get_admin)):
    """Trigger a full Render deploy pipeline (admin only)."""
    _nexus_required()
    require_credits(admin["id"], ACTION_COSTS["deploy"], "Render deploy trigger")
    try:
        kernel      = NexusKernel()
        agent       = AutoDeployAgent(kernel)
        service_url = os.environ.get("RENDER_SERVICE_URL", "https://nexus-backend.onrender.com")
        logs: List[str] = []
        result = await agent.full_deploy_pipeline(service_url, log_fn=logs.append)
        log_usage(admin["id"], "autodeploy", "render", 0, "ok", "trigger", str(result)[:200])
        return {"result": result, "logs": logs}
    except Exception as e:
        raise HTTPException(500, f"Deploy failed: {e}")


@app.get("/api/v1/autodeploy/status", tags=["AutoDeploy"])
async def deploy_status(admin: Dict = Depends(get_admin)):
    """Fetch the latest deploys from the Render API."""
    render_key = os.environ.get("RENDER_API_KEY", "")
    svc_id     = os.environ.get("RENDER_SERVICE_ID", "")
    if not render_key or not svc_id:
        return {
            "status":  "unconfigured",
            "message": "Set RENDER_API_KEY and RENDER_SERVICE_ID environment variables.",
        }
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://api.render.com/v1/services/{svc_id}/deploys?limit=3",
                headers={"Authorization": f"Bearer {render_key}"},
            )
        return {"deploys": r.json() if r.status_code == 200 else [], "http_status": r.status_code}
    except Exception as e:
        raise HTTPException(502, f"Render API unreachable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SWARM  —  /api/v1/swarm/*
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/swarm/run", tags=["Swarm"])
async def run_swarm(req: SwarmRequest, admin: Dict = Depends(get_admin)):
    """Dispatch a swarm of specialised agent nodes toward a goal (admin only)."""
    _nexus_required()
    require_credits(admin["id"], req.num_nodes * ACTION_COSTS["agent_step"],
                    f"swarm: {req.num_nodes} nodes")
    try:
        kernel = NexusKernel()
        orch   = SwarmOrchestrator(kernel, _swarm_bus)
        specs  = ["research", "coding", "analysis", "review",
                  "documentation", "testing", "optimization", "security"]
        nodes  = [
            SwarmNode(kernel, _swarm_bus, name=f"Node-{i+1}", specialization=specs[i % len(specs)])
            for i in range(req.num_nodes)
        ]
        logs: List[str] = []
        result = await orch.run_swarm(req.goal, nodes, log_fn=logs.append)
        log_usage(admin["id"], "swarm", "orchestrator", 0, "ok", req.goal[:200], str(result)[:200])
        return {"result": result, "logs": logs}
    except Exception as e:
        raise HTTPException(500, f"Swarm run failed: {e}")


@app.get("/api/v1/swarm/nodes", tags=["Swarm"])
async def swarm_nodes(user: Dict = Depends(get_user)):
    """Return live node listing from the swarm bus."""
    _nexus_required()
    try:
        return {"nodes": _swarm_bus.get_live_nodes()}
    except Exception as e:
        raise HTTPException(500, f"Could not retrieve swarm nodes: {e}")


@app.get("/api/v1/swarm/stream", tags=["Swarm"])
async def swarm_stream(goal: str, num_nodes: int = 3, token: str = ""):
    """
    SSE real-time swarm execution stream.
    Authenticate via ?token= query param (admin JWT required).
    """
    _nexus_required()
    user_row = _decode_token_param(token)
    if not user_row["is_admin"]:
        raise HTTPException(403, "Admin access required.")

    n      = min(max(num_nodes, 1), 4)
    kernel = NexusKernel()
    orch   = SwarmOrchestrator(kernel, _swarm_bus)
    specs  = ["research", "coding", "analysis", "review"]
    nodes  = [
        SwarmNode(kernel, _swarm_bus, f"Node-{i+1}", specs[i % len(specs)])
        for i in range(n)
    ]

    async def swarm_gen() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'start', 'nodes': n, 'goal': goal[:80]})}\n\n"
        logs: List[str] = []
        try:
            result = await orch.run_swarm(goal, nodes, log_fn=logs.append)
            for msg in logs:
                yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'consensus': result.get('consensus', '')[:500], 'nodes_used': result.get('nodes_used')})}\n\n"
            log_usage(user_row["id"], "swarm", "stream", 0, "ok", goal[:200], "")
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(swarm_gen(), media_type="text/event-stream")

# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY (SELF-EVOLUTION)  —  /api/v1/singularity/*
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/singularity/evolve", tags=["Singularity"])
async def trigger_evolution(admin: Dict = Depends(get_admin)):
    """
    Trigger self-evolution: SelfMonitorAgent analyses logs, RecursiveCoderAgent
    rewrites the kernel, then hot_swapper reloads the module (admin only).
    """
    _nexus_required()
    require_credits(admin["id"], ACTION_COSTS["agent_step"] * 2, "singularity: evolve")
    try:
        kernel  = NexusKernel()
        monitor = SelfMonitorAgent(kernel, db_path=DB_PATH)
        coder   = RecursiveCoderAgent(kernel)
        logs: List[str] = []

        def _log(m: str) -> None:
            logs.append(m)
            print(m)

        _log("🧠 Self-Monitor: Analysing usage logs...")
        proposal = await monitor.analyze_performance("groq", "llama-3.3-70b-versatile")
        _log(f"💡 Proposal preview: {proposal[:120]}...")

        target  = os.path.join(NEXUS_OS_PATH, "core", "kernel.py")
        success = await coder.self_upgrade_core(
            proposal, target, "groq", "llama-3.3-70b-versatile"
        )

        if success:
            hot_swapper.reload_core("kernel")
            _log("🚀 EVOLUTION COMPLETE — Kernel hot-swapped.")
        else:
            _log("⚠️  Evolution attempt failed — kernel unchanged.")

        log_usage(admin["id"], "singularity", "evolve", 0,
                  "ok" if success else "failed", "evolve", proposal[:200])
        return {"success": success, "proposal_preview": proposal[:300], "logs": logs}
    except Exception as e:
        raise HTTPException(500, f"Evolution failed: {e}")


@app.get("/api/v1/singularity/status", tags=["Singularity"])
async def evolution_status(admin: Dict = Depends(get_admin)):
    """Return kernel file modification time and error-rate metrics."""
    kernel_path = os.path.join(NEXUS_OS_PATH, "core", "kernel.py")
    mtime = os.path.getmtime(kernel_path) if os.path.exists(kernel_path) else 0

    conn   = get_conn()
    errors = conn.execute(
        "SELECT COUNT(*) FROM usage_logs WHERE status LIKE 'error%'"
    ).fetchone()[0]
    total  = conn.execute("SELECT COUNT(*) FROM usage_logs").fetchone()[0]
    conn.close()

    return {
        "kernel_last_modified": datetime.fromtimestamp(mtime).isoformat() if mtime else None,
        "total_requests":       total,
        "error_count":          errors,
        "error_rate_pct":       round(errors / total * 100, 1) if total else 0,
        "nexus_os_path":        NEXUS_OS_PATH,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
