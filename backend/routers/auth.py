"""
Authentication router for Project Nexus.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.config import SECRET_KEY, ALGORITHM, TOKEN_EXP_MINUTES, PLAN_CONFIG
from backend.database import get_user_by_username, _add_credits, init_db, DB_PATH
from backend.utils.logging import get_logger
import sqlite3

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


class RegisterRequest(BaseModel):
    username: str
    password: str
    plan: str = "STARTER"


def make_token(username: str) -> str:
    """Generate a JWT token for a user."""
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXP_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get the current authenticated user from JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = get_user_by_username(username)
        if not user:
            raise HTTPException(401, "Invalid token")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Get the current user and verify they are an admin."""
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return user


@router.post("/register")
async def register(req: RegisterRequest):
    """Register a new user."""
    plan = req.plan.upper()
    if plan not in PLAN_CONFIG:
        raise HTTPException(400, f"Invalid plan. Choose: {list(PLAN_CONFIG.keys())}")
    
    plan_credits = PLAN_CONFIG[plan]["credits"]
    plan_expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO users (username, hashed_password, plan_type, credits, plan_expires) VALUES (?,?,?,?,?)",
            (req.username, ph.hash(req.password), plan, plan_credits, plan_expires)
        )
        conn.commit()
        uid = conn.execute("SELECT id FROM users WHERE username=?", (req.username,)).fetchone()[0]
        conn.close()
        _add_credits(uid, plan_credits, 'SUBSCRIPTION', f"{plan} plan activation")
        logger.info(f"User registered: {req.username} with plan {plan}")
        return {
            "status": "success",
            "plan": plan,
            "credits": plan_credits,
            "message": f"Account created. {plan_credits} credits added. Plan valid until {plan_expires[:10]}."
        }
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(400, "Username already exists")


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    user = get_user_by_username(form_data.username)
    if not user:
        raise HTTPException(400, "Invalid credentials")
    
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT hashed_password FROM users WHERE username=?",
        (form_data.username,)
    ).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(400, "Invalid credentials")
    
    try:
        ph.verify(row[0], form_data.password)
    except VerifyMismatchError:
        raise HTTPException(400, "Invalid credentials")
    
    logger.info(f"User logged in: {form_data.username}")
    return {"access_token": make_token(form_data.username), "token_type": "bearer"}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user info."""
    return user
