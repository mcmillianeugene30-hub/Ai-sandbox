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
sys.path.append('/workspace/ai-sandbox/nexus-ai-os')
from core.kernel import NexusKernel
from agents.architect import AppArchitectAgent
from agents.devops import DevOpsAgent
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.coder import CoderAgent
from agents.reviewer import ReviewerAgent
from agents.hive_aggregator import HiveAggregator
from tools.fs_tool import fs_tool

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

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DB_PATH = "usage.db"

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
            task_tree = planner.decompose(f"Build {task}", "groq", "llama-3.3-70b-versatile")

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

# ─── STATIC PRICING PAGE ──────────────────────────────────────────────────────
@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    with open("../frontend/pricing.html","r") as f: return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
