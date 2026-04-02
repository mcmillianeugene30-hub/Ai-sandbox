"""
Billing router for Project Nexus.
"""
from datetime import datetime, timedelta
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import PLAN_CONFIG, TOPUP_PACKS, DB_PATH
from backend.database import _add_credits
from backend.routers.auth import get_current_user, get_admin_user
from backend.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class TopupRequest(BaseModel):
    pack_id: str


@router.get("/plans")
async def list_plans():
    """List available subscription plans."""
    return PLAN_CONFIG


@router.get("/packs")
async def list_packs():
    """List available top-up packs."""
    return TOPUP_PACKS


@router.post("/topup")
async def topup(req: TopupRequest, user: dict = Depends(get_current_user)):
    """Purchase a credit top-up pack."""
    pack = TOPUP_PACKS.get(req.pack_id.lower())
    if not pack:
        raise HTTPException(400, f"Unknown pack. Choose: {list(TOPUP_PACKS.keys())}")
    
    _add_credits(user["id"], pack["credits"], 'TOPUP', pack["label"])
    
    conn = sqlite3.connect(DB_PATH)
    new_bal = conn.execute("SELECT credits FROM users WHERE id=?", (user["id"],)).fetchone()[0]
    conn.close()
    
    logger.info(f"User {user['id']} purchased {req.pack_id} pack")
    return {
        "status": "success",
        "pack": pack["label"],
        "credits_added": pack["credits"],
        "new_balance": new_bal,
        "note": f"Simulated payment of ${pack['price']}. Integrate Stripe webhook to trigger this in production."
    }


@router.post("/upgrade")
async def upgrade_plan(new_plan: str, user: dict = Depends(get_current_user)):
    """Upgrade user subscription plan."""
    plan = new_plan.upper()
    if plan not in PLAN_CONFIG:
        raise HTTPException(400, "Invalid plan")
    
    bonus = PLAN_CONFIG[plan]["credits"]
    exp = (datetime.utcnow() + timedelta(days=30)).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE users SET plan_type=?, plan_expires=? WHERE id=?",
        (plan, exp, user["id"])
    )
    conn.commit()
    conn.close()
    
    _add_credits(user["id"], bonus, 'SUBSCRIPTION', f"Upgraded to {plan}")
    logger.info(f"User {user['id']} upgraded to {plan}")
    
    return {
        "status": "upgraded",
        "plan": plan,
        "credits_added": bonus,
        "expires": exp[:10]
    }


@router.get("/ledger")
async def my_ledger(user: dict = Depends(get_current_user)):
    """Get user's credit ledger."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT amount, type, description, timestamp FROM credit_ledger WHERE user_id=? ORDER BY id DESC LIMIT 50",
        (user["id"],)
    ).fetchall()
    conn.close()
    
    return [
        {"amount": r[0], "type": r[1], "description": r[2], "time": r[3]}
        for r in rows
    ]


@router.get("/status")
async def billing_status(user: dict = Depends(get_current_user)):
    """Get current billing status."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT plan_type, credits, plan_expires FROM users WHERE id=?",
        (user["id"],)
    ).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(404, "User not found")
    
    return {
        "plan": row[0],
        "credits": row[1],
        "plan_expires": row[2]
    }
