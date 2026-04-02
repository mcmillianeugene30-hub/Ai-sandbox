"""
Admin router for Project Nexus.
"""
import json
from datetime import datetime
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import PLAN_CONFIG, DB_PATH
from backend.database import _add_credits
from backend.routers.auth import get_admin_user
from backend.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/stats")
async def admin_stats(admin: dict = Depends(get_admin_user)):
    """Get admin dashboard statistics."""
    conn = sqlite3.connect(DB_PATH)
    
    total_spend = conn.execute("SELECT SUM(cost_usd) FROM usage_logs").fetchone()[0] or 0
    total_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin=0").fetchone()[0]
    
    arr_estimate = 0
    plan_rows = conn.execute(
        "SELECT plan_type, COUNT(*) FROM users WHERE is_admin=0 GROUP BY plan_type"
    ).fetchall()
    
    plan_breakdown = []
    for pr in plan_rows:
        plan_name, cnt = pr[0], pr[1]
        price = PLAN_CONFIG.get(plan_name, {}).get("price", 0)
        mrr = cnt * price
        arr_estimate += mrr * 12
        plan_breakdown.append({"plan": plan_name, "users": cnt, "mrr": mrr})
    
    models = [
        {"model": r[0], "count": r[1], "cost": r[2]}
        for r in conn.execute(
            "SELECT model, COUNT(*), SUM(cost_usd) FROM usage_logs GROUP BY model"
        ).fetchall()
    ]
    
    recent = [
        {"id": r[0], "time": r[1], "provider": r[2], "model": r[3], "cost": r[4], "status": r[5]}
        for r in conn.execute(
            "SELECT id, timestamp, provider, model, cost_usd, status FROM usage_logs ORDER BY id DESC LIMIT 20"
        ).fetchall()
    ]
    
    conn.close()
    
    return {
        "total_spend": total_spend,
        "total_users": total_users,
        "arr_estimate": arr_estimate,
        "plan_breakdown": plan_breakdown,
        "models": models,
        "recent_logs": recent
    }


@router.get("/users")
async def admin_users(admin: dict = Depends(get_admin_user)):
    """List all users."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, username, plan_type, credits, plan_expires, is_admin FROM users"
    ).fetchall()
    conn.close()
    
    return [
        {"id": r[0], "username": r[1], "plan": r[2], "credits": r[3], "expires": r[4], "admin": r[5]}
        for r in rows
    ]


@router.post("/users/{user_id}/grant")
async def grant_credits(user_id: int, amount: float, admin: dict = Depends(get_admin_user)):
    """Grant credits to a user."""
    _add_credits(user_id, amount, 'BONUS', f"Admin grant by {admin['username']}")
    logger.info(f"Admin {admin['username']} granted {amount} credits to user {user_id}")
    return {"status": "credited", "amount": amount}


@router.post("/users/{user_id}/set-plan")
async def set_plan(user_id: int, plan: str, admin: dict = Depends(get_admin_user)):
    """Set a user's subscription plan."""
    plan = plan.upper()
    if plan not in PLAN_CONFIG:
        raise HTTPException(400, "Invalid plan")
    
    exp = (datetime.utcnow() + timedelta(days=30)).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE users SET plan_type=?, plan_expires=? WHERE id=?",
        (plan, exp, user_id)
    )
    conn.commit()
    conn.close()
    
    _add_credits(user_id, PLAN_CONFIG[plan]["credits"], 'SUBSCRIPTION', f"Plan set by admin to {plan}")
    logger.info(f"Admin {admin['username']} set user {user_id} plan to {plan}")
    
    return {"status": "updated", "plan": plan}


@router.post("/star/{log_id}")
async def toggle_star(log_id: int, admin: dict = Depends(get_admin_user)):
    """Toggle star status on a log entry."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE usage_logs SET is_starred=1-is_starred WHERE id=?", (log_id,))
    conn.commit()
    conn.close()
    logger.info(f"Admin toggled star on log {log_id}")
    return {"status": "toggled"}


@router.get("/export")
async def export_starred(admin: dict = Depends(get_admin_user)):
    """Export starred conversations as JSONL for fine-tuning."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT prompt, response FROM usage_logs WHERE is_starred=1"
    ).fetchall()
    conn.close()
    
    jsonl = "\n".join(
        json.dumps({
            "messages": [
                {"role": "user", "content": r[0]},
                {"role": "assistant", "content": r[1]}
            ]
        })
        for r in rows
    )
    
    return StreamingResponse(
        iter([jsonl]),
        media_type="application/x-jsonlines",
        headers={"Content-Disposition": "attachment;filename=finetune.jsonl"}
    )
