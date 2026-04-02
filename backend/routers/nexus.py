"""
Nexus AI-OS router for Project Nexus.
Handles singularity, swarm, auto-deploy, and app builder features.
"""
import json
import os
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import httpx
import jwt

from backend.config import (
    DB_PATH, SECRET_KEY, ALGORITHM, ACTION_COSTS,
    RENDER_API_KEY, RENDER_SERVICE_ID, RENDER_SERVICE_URL
)
from backend.database import require_credits, log_usage
from backend.routers.auth import get_admin_user, get_current_user
from backend.utils.logging import get_logger

# Nexus AI-OS imports
from nexus_ai_os.core.kernel import NexusKernel
from nexus_ai_os.core.swarm import SwarmBus, SwarmNode, SwarmOrchestrator
from nexus_ai_os.core.hot_swap import hot_swapper
from nexus_ai_os.agents.architect import AppArchitectAgent
from nexus_ai_os.agents.devops import DevOpsAgent
from nexus_ai_os.agents.planner import PlannerAgent
from nexus_ai_os.agents.hive_aggregator import HiveAggregator
from nexus_ai_os.agents.coder import CoderAgent
from nexus_ai_os.agents.auto_deploy import AutoDeployAgent
from nexus_ai_os.agents.model_researcher import AutonomousModelResearcher
from nexus_ai_os.agents.self_monitor import SelfMonitorAgent, RecursiveCoderAgent
from nexus_ai_os.tools.fs_tool import fs_tool

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["nexus"])

# Shared swarm bus (singleton per process)
_swarm_bus = SwarmBus()


# ─── SINGULARITY / SELF-MONITOR ───────────────────────────────────────────────

@router.post("/singularity/evolve")
async def trigger_evolution(admin: dict = Depends(get_admin_user)):
    """Trigger self-evolution of the Nexus kernel."""
    kernel = NexusKernel()
    monitor = SelfMonitorAgent(kernel)
    coder = RecursiveCoderAgent(kernel)
    logs = []
    
    def log(m):
        logs.append(m)
        logger.info(m)
    
    log("🧠 Self-Monitor: Analysing usage logs...")
    proposal = await monitor.analyze_performance("groq", "llama-3.3-70b-versatile")
    log(f"💡 Proposal: {proposal[:120]}...")
    
    # Use the new package path
    from nexus_ai_os.core import kernel as kernel_module
    target = kernel_module.__file__
    
    success = await coder.self_upgrade_core(proposal, target, "groq", "llama-3.3-70b-versatile")
    
    if success:
        hot_swapper.reload_core("kernel")
        log("🚀 EVOLUTION COMPLETE — Kernel hot-swapped.")
    else:
        log("⚠️ Evolution attempt failed — kernel unchanged.")
    
    return {"success": success, "proposal_preview": proposal[:300], "logs": logs}


@router.get("/singularity/status")
async def evolution_status(admin: dict = Depends(get_admin_user)):
    """Get evolution/singularity status."""
    from nexus_ai_os.core import kernel as kernel_module
    kernel_path = kernel_module.__file__
    mtime = os.path.getmtime(kernel_path) if os.path.exists(kernel_path) else 0
    
    conn = sqlite3.connect(DB_PATH)
    errors = conn.execute("SELECT COUNT(*) FROM usage_logs WHERE status LIKE 'error%'").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM usage_logs").fetchone()[0]
    conn.close()
    
    return {
        "kernel_last_modified": datetime.fromtimestamp(mtime).isoformat() if mtime else None,
        "total_requests": total,
        "error_count": errors,
        "error_rate": round(errors / total * 100, 1) if total else 0
    }


# ─── SWARM INTELLIGENCE ───────────────────────────────────────────────────────

@router.post("/swarm/run")
async def run_swarm(
    goal: str = Query(..., description="The goal for the swarm"),
    num_nodes: int = Query(3, ge=1, le=8),
    admin: dict = Depends(get_admin_user)
):
    """Run a swarm of AI nodes on a goal."""
    kernel = NexusKernel()
    orch = SwarmOrchestrator(kernel, _swarm_bus)
    
    specs = ["research", "coding", "analysis", "review", "documentation", "testing", "optimization", "security"]
    nodes = [
        SwarmNode(kernel, _swarm_bus, name=f"Node-{i+1}", specialization=specs[i % len(specs)])
        for i in range(num_nodes)
    ]
    
    logs = []
    result = await orch.run_swarm(goal, nodes, log_fn=logs.append)
    return {"result": result, "logs": logs}


@router.get("/swarm/nodes")
async def swarm_nodes(user: dict = Depends(get_current_user)):
    """Get live swarm nodes."""
    return {"nodes": _swarm_bus.get_live_nodes()}


@router.get("/swarm/stream")
async def swarm_stream(
    goal: str = Query(...),
    num_nodes: int = Query(3, ge=1, le=8),
    token: str = Query(...)
):
    """SSE endpoint to watch the swarm in real-time."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        from backend.database import get_user_by_username
        user = get_user_by_username(payload["sub"])
        if not user or not user.get("is_admin"):
            raise HTTPException(401, "Unauthorized")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Unauthorized")
    
    kernel = NexusKernel()
    orch = SwarmOrchestrator(kernel, _swarm_bus)
    specs = ["research", "coding", "analysis", "review"]
    n = min(max(num_nodes, 1), 4)
    nodes = [
        SwarmNode(kernel, _swarm_bus, f"Node-{i+1}", specs[i % len(specs)])
        for i in range(n)
    ]
    
    async def swarm_gen():
        def emit(msg):
            return f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"
        
        yield f"data: {json.dumps({'type': 'start', 'nodes': n, 'goal': goal[:80]})}\n\n"
        logs = []
        try:
            result = await orch.run_swarm(goal, nodes, log_fn=logs.append)
            for l in logs:
                yield emit(l)
            yield f"data: {json.dumps({'type': 'complete', 'consensus': result['consensus'][:500], 'nodes_used': result['nodes_used']})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(swarm_gen(), media_type="text/event-stream")


# ─── AUTO-DEPLOY ──────────────────────────────────────────────────────────────

@router.post("/autodeploy/trigger")
async def trigger_deploy(admin: dict = Depends(get_admin_user)):
    """Trigger automatic deployment."""
    kernel = NexusKernel()
    agent = AutoDeployAgent(kernel)
    logs = []
    
    result = await agent.full_deploy_pipeline(RENDER_SERVICE_URL, log_fn=logs.append)
    return {"result": result, "logs": logs}


@router.get("/autodeploy/status")
async def deploy_status(admin: dict = Depends(get_admin_user)):
    """Get deployment status from Render."""
    if not RENDER_API_KEY or not RENDER_SERVICE_ID:
        return {
            "status": "unconfigured",
            "message": "Set RENDER_API_KEY and RENDER_SERVICE_ID env vars"
        }
    
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys?limit=3",
            headers={"Authorization": f"Bearer {RENDER_API_KEY}"}
        )
    
    return {"deploys": r.json() if r.status_code == 200 else [], "http": r.status_code}


# ─── AUTONOMOUS MODEL DISCOVERY ───────────────────────────────────────────────

@router.post("/models/discover")
async def discover_models(admin: dict = Depends(get_admin_user)):
    """Discover and register new models from providers."""
    kernel = NexusKernel()
    explorer = AutonomousModelResearcher(kernel)
    logs = []
    
    result = await explorer.discover_and_register(str(DB_PATH), log_fn=logs.append)
    return {"result": result, "logs": logs}


@router.get("/models/registry")
async def get_model_registry(user: dict = Depends(get_current_user)):
    """Get the discovered model registry."""
    from nexus_ai_os.agents.model_researcher import MODEL_REGISTRY_PATH
    
    if not os.path.exists(MODEL_REGISTRY_PATH):
        return {"models": {}, "last_updated": None}
    
    with open(MODEL_REGISTRY_PATH) as f:
        return json.load(f)


# ─── NEXUS APP BUILDER ────────────────────────────────────────────────────────

@router.get("/nexus/app-build")
async def stream_nexus_app_build(task: str, token: str):
    """Stream app build process."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        from backend.database import get_user_by_username
        user = get_user_by_username(payload["sub"])
        if not user:
            raise HTTPException(401, "Unauthorized")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Unauthorized")
    
    if user.get("plan") not in ("PRO", "ENTERPRISE"):
        raise HTTPException(403, "Full-Stack App Builder requires PRO or ENTERPRISE plan.")
    
    # Pre-charge: 7 agent steps × 1cr = 7 credits upfront
    if not require_credits(user["id"], 7, "App-build workflow (7 agent steps)"):
        raise HTTPException(402, "Insufficient credits")
    
    kernel = NexusKernel()
    architect = AppArchitectAgent(kernel)
    devops = DevOpsAgent(kernel)
    planner = PlannerAgent(kernel)
    hive_agg = HiveAggregator(kernel)
    coder = CoderAgent(kernel)
    
    async def gen():
        try:
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'architect'})}\n\n"
            yield f"data: {json.dumps({'type': 'log', 'agent': 'architect', 'message': 'Architecting 2026 tech stack...'})}\n\n"
            
            design = await architect.architect(task, "groq", "llama-3.3-70b-versatile")
            yield f"data: {json.dumps({'type': 'design', 'design': design})}\n\n"
            
            project_name = task.lower().replace(" ", "-")[:20]
            base_path = f"projects/{project_name}"
            fs_tool.mkdir(base_path)
            architect.create_structure_recursive(base_path, design['structure'])
            
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'devops'})}\n\n"
            dc = await devops.configure_deployment(design['stack'], design['structure'], "groq", "llama-3.3-70b-versatile")
            devops.write_configs(base_path, dc)
            yield f"data: {json.dumps({'type': 'log', 'agent': 'devops', 'message': 'Docker + CI/CD configs written.'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'planner'})}\n\n"
            task_tree = await planner.decompose(f"Build {task}", "groq", "llama-3.3-70b-versatile")
            
            for step in task_tree:
                sub = step['task']
                yield f"data: {json.dumps({'type': 'log', 'agent': 'researcher', 'message': f'Hive Poll: {sub}'})}\n\n"
                hive_out = await kernel.hive_poll(
                    [{"provider": "groq", "model": "llama-3.3-70b-versatile"}],
                    [{"role": "user", "content": sub}]
                )
                brief = await hive_agg.aggregate(sub, hive_out, "groq", "llama-3.3-70b-versatile")
                yield f"data: {json.dumps({'type': 'agent_start', 'agent': 'coder'})}\n\n"
                files = [f"{base_path}/{p}" for p in step.get('files_to_create', [])] or [f"{base_path}/main.py"]
                await coder.build_files(f"{sub}\nBrief:{brief}", files, "groq", "llama-3.3-70b-versatile")
                yield f"data: {json.dumps({'type': 'log', 'agent': 'coder', 'message': f'Files built: {files}'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete', 'project_path': base_path})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(gen(), media_type="text/event-stream")


# ─── ANALYTICS ────────────────────────────────────────────────────────────────

@router.get("/analytics")
async def analytics(user: dict = Depends(get_current_user)):
    """Get user analytics."""
    import sqlite3
    from backend.config import DB_PATH
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT provider, COUNT(*), SUM(cost_usd), AVG(latency_ms)
           FROM usage_logs WHERE user_id=? GROUP BY provider""",
        (user["id"],)
    ).fetchall()
    conn.close()
    
    return [
        {"provider": r[0], "requests": r[1], "cost": r[2], "avg_latency": r[3]}
        for r in rows
    ]
