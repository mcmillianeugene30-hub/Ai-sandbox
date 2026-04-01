from typing import List, Dict, Any, Optional, AsyncGenerator
import json
import asyncio
from fastapi import FastAPI, HTTPException, Header, Request, UploadFile, File, Form, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import os
import time
import sqlite3
import shutil
import jwt
from datetime import datetime, timedelta
from passlib.hash import argon2

# Nexus Integration Imports
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

# --- CONFIG ---
SECRET_KEY = "nexus_super_secret_key_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 600

app = FastAPI(title="AI Sandbox API v6 + Admin & Billing")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/admin/login")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE ---
DB_PATH = "usage.db"

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
            cost_usd REAL DEFAULT 0,
            is_starred INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            hashed_password TEXT,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pricing_config (
            provider TEXT,
            model TEXT,
            input_cost_1m REAL,
            output_cost_1m REAL,
            PRIMARY KEY (provider, model)
        )
    ''')
    
    # Default Admin: nexus / nexus2026
    hashed_pwd = argon2.hash("nexus2026")
    cursor.execute("INSERT OR IGNORE INTO users (username, hashed_password, is_admin) VALUES (?, ?, ?)",
                   ("nexus", hashed_pwd, 1))
    
    # 2026 Pricing
    default_pricing = [
        ('groq', 'llama-3.3-70b-versatile', 0.59, 0.79),
        ('groq', 'llama-3.1-8b-instant', 0.05, 0.08),
        ('google', 'gemini-1.5-pro', 3.50, 10.50),
        ('google', 'gemini-1.5-flash', 0.075, 0.30),
        ('openrouter', 'gpt-4o', 5.00, 15.00)
    ]
    cursor.executemany("INSERT OR IGNORE INTO pricing_config VALUES (?, ?, ?, ?)", default_pricing)
    conn.commit()
    conn.close()

init_db()

# --- AUTH UTILS ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def verify_admin(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        if not user or not user[0]: raise Exception()
        return username
    except:
        raise HTTPException(status_code=401, detail="Unauthorized")

# --- PRICING ---
def calculate_cost(provider, model, prompt, response):
    in_tokens = len(prompt) / 4
    out_tokens = len(response) / 4
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT input_cost_1m, output_cost_1m FROM pricing_config WHERE provider = ? AND model = ?", (provider, model))
    rates = cursor.fetchone()
    conn.close()
    if not rates: return 0
    return ((in_tokens / 1_000_000) * rates[0]) + ((out_tokens / 1_000_000) * rates[1])

def log_usage(provider, model, latency_ms, status, prompt="", response=""):
    cost = calculate_cost(provider, model, prompt, response)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO usage_logs (provider, model, latency_ms, status, prompt, response, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (provider, model, latency_ms, status, prompt, response, cost))
    conn.commit()
    conn.close()

# --- ENDPOINTS ---
@app.post("/api/v1/admin/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT hashed_password FROM users WHERE username = ?", (form_data.username,))
    user = cursor.fetchone()
    conn.close()
    if not user or not argon2.verify(form_data.password, user[0]):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {"access_token": create_access_token({"sub": form_data.username}), "token_type": "bearer"}

@app.get("/api/v1/admin/stats")
async def get_stats(token: str = Depends(oauth2_scheme)):
    await verify_admin(token)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(cost_usd) FROM usage_logs")
    total = cursor.fetchone()[0] or 0
    cursor.execute("SELECT model, COUNT(*), SUM(cost_usd) FROM usage_logs GROUP BY model")
    models = [{"model": r[0], "count": r[1], "cost": r[2]} for r in cursor.fetchall()]
    cursor.execute("SELECT id, timestamp, provider, model, cost_usd, status FROM usage_logs ORDER BY id DESC LIMIT 20")
    recent = [{"id": r[0], "time": r[1], "provider": r[2], "model": r[3], "cost": r[4], "status": r[5]} for r in cursor.fetchall()]
    conn.close()
    return {"total_spend": total, "models": models, "recent_logs": recent}

@app.get("/api/v1/nexus/app-build")
async def stream_nexus_app_build(task: str, token: str):
    await verify_admin(token)
    kernel = NexusKernel()
    architect = AppArchitectAgent(kernel)
    devops = DevOpsAgent(kernel)
    planner = PlannerAgent(kernel)
    researcher = ResearcherAgent(kernel)
    coder = CoderAgent(kernel)
    hive_aggregator = HiveAggregator(kernel)

    async def app_build_generator():
        try:
            # 1. Architect
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'architect'})}\n\n"
            yield f"data: {json.dumps({'type': 'log', 'agent': 'architect', 'message': 'Architecting 2026 tech stack...' })}\n\n"
            design = await architect.architect(task, "groq", "llama-3.3-70b-versatile")
            yield f"data: {json.dumps({'type': 'design', 'design': design})}\n\n"
            
            project_name = task.lower().replace(" ", "-")[:20]
            base_path = f"projects/{project_name}"
            fs_tool.mkdir(base_path)
            architect.create_structure_recursive(base_path, design['structure'])

            # 2. DevOps
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'devops'})}\n\n"
            yield f"data: {json.dumps({'type': 'log', 'agent': 'devops', 'message': 'Generating Docker/CI configs...' })}\n\n"
            devops_config = await devops.configure_deployment(design['stack'], design['structure'], "groq", "llama-3.3-70b-versatile")
            devops.write_configs(base_path, devops_config)

            # 3. Planner & Build
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'planner'})}\n\n"
            task_tree = planner.decompose(f"Build {task}", "groq", "llama-3.3-70b-versatile")
            
            for step in task_tree:
                sub_task = step['task']
                yield f"data: {json.dumps({'type': 'log', 'agent': 'researcher', 'message': f'Hive Polling for {sub_task}...' })}\n\n"
                
                # Simplified Hive Poll for demo
                hive_providers = [{"provider": "groq", "model": "llama-3.3-70b-versatile"}]
                hive_outputs = await kernel.hive_poll(hive_providers, [{"role": "user", "content": sub_task}])
                brief = await hive_aggregator.aggregate(sub_task, hive_outputs, "groq", "llama-3.3-70b-versatile")

                yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'coder'})}\n\n"
                files = [f"{base_path}/{p}" for p in step.get('files_to_create', [])]
                if not files: files = [f"{base_path}/main.py"]
                await coder.build_files(f"{sub_task}\nBrief: {brief}", files, "groq", "llama-3.3-70b-versatile")
                yield f"data: {json.dumps({'type': 'log', 'agent': 'coder', 'message': f'Files generated: {files}' })}\n\n"

            yield f"data: {json.dumps({'type': 'complete', 'project_path': base_path})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(app_build_generator(), media_type="text/event-stream")

@app.post("/api/v1/admin/star/{log_id}")
async def toggle_star(log_id: int, token: str = Depends(oauth2_scheme)):
    await verify_admin(token)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE usage_logs SET is_starred = 1 - is_starred WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/v1/admin/starred")
async def get_starred_logs(token: str = Depends(oauth2_scheme)):
    await verify_admin(token)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, provider, model, prompt, response FROM usage_logs WHERE is_starred = 1 ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "time": r[1], "provider": r[2], "model": r[3], "prompt": r[4], "response": r[5]} for r in rows]

@app.get("/api/v1/admin/export")
async def export_starred(token: str = Depends(oauth2_scheme)):
    await verify_admin(token)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT prompt, response FROM usage_logs WHERE is_starred = 1")
    rows = cursor.fetchall()
    conn.close()
    
    # Format for fine-tuning (JSONL)
    jsonl_content = ""
    for r in rows:
        item = {
            "messages": [
                {"role": "user", "content": r[0]},
                {"role": "assistant", "content": r[1]}
            ]
        }
        jsonl_content += json.dumps(item) + "\n"
    
    return StreamingResponse(
        iter([jsonl_content]),
        media_type="application/x-jsonlines",
        headers={"Content-Disposition": "attachment; filename=fine_tuning_data.jsonl"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
