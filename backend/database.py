"""
Database initialization and shared database logic for Project Nexus.
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from backend.config import DB_PATH, PLAN_CONFIG, CREDIT_PRICE_USD
from backend.utils.logging import get_logger

logger = get_logger(__name__)


def init_db() -> None:
    """Initialize the SQLite database with all required tables."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        hashed_password TEXT,
        is_admin INTEGER DEFAULT 0,
        plan_type TEXT DEFAULT 'NONE',
        credits REAL DEFAULT 0,
        plan_expires TEXT
    )''')
    
    # Credit ledger table
    c.execute('''CREATE TABLE IF NOT EXISTS credit_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        type TEXT,
        description TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    
    # Usage logs table
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
    
    # Pricing configuration table
    c.execute('''CREATE TABLE IF NOT EXISTS pricing_config (
        provider TEXT, model TEXT,
        input_cost_1m REAL, output_cost_1m REAL,
        PRIMARY KEY (provider, model)
    )''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


def seed_admin_user() -> None:
    """Seed the admin user if it doesn't exist."""
    from backend.config import PLAN_CONFIG
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    
    ph = PasswordHasher()
    
    def argon2_hash(password: str) -> str:
        return ph.hash(password)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (username, hashed_password, is_admin, plan_type, credits) VALUES (?,?,?,?,?)",
        ("nexus", argon2_hash("nexus2026"), 1, "ENTERPRISE", 9_999_999)
    )
    conn.commit()
    conn.close()
    logger.info("Admin user seeded")


def seed_pricing_config() -> None:
    """Seed the default pricing configuration."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executemany("INSERT OR IGNORE INTO pricing_config VALUES (?,?,?,?)", [
        ('groq', 'llama-3.3-70b-versatile', 0.59, 0.79),
        ('groq', 'llama-3.1-8b-instant', 0.05, 0.08),
        ('google', 'gemini-1.5-pro', 3.50, 10.50),
        ('google', 'gemini-1.5-flash', 0.075, 0.30),
        ('openrouter', 'gpt-4o', 5.00, 15.00),
        ('openrouter', 'claude-sonnet-4', 3.00, 15.00),
    ])
    conn.commit()
    conn.close()
    logger.info("Pricing configuration seeded")


def _deduct(user_id: int, amount: float, desc: str) -> bool:
    """Atomic credit deduction. Returns False if insufficient balance."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-? WHERE id=? AND credits>=?", (amount, user_id, amount))
    ok = c.rowcount == 1
    if ok:
        c.execute(
            "INSERT INTO credit_ledger (user_id, amount, type, description) VALUES (?,?,?,?)",
            (user_id, -amount, 'USAGE', desc)
        )
        logger.info(f"Deducted {amount} credits from user {user_id}: {desc}")
    conn.commit()
    conn.close()
    return ok


def _add_credits(user_id: int, amount: float, type_: str, desc: str) -> None:
    """Add credits to a user's account."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits+? WHERE id=?", (amount, user_id))
    c.execute(
        "INSERT INTO credit_ledger (user_id, amount, type, description) VALUES (?,?,?,?)",
        (user_id, amount, type_, desc)
    )
    conn.commit()
    conn.close()
    logger.info(f"Added {amount} credits to user {user_id}: {desc}")


def token_cost_credits(provider: str, model: str, prompt: str, response: str) -> Tuple[float, float]:
    """Calculate token cost in USD and credits."""
    conn = sqlite3.connect(DB_PATH)
    rates = conn.execute(
        "SELECT input_cost_1m, output_cost_1m FROM pricing_config WHERE provider=? AND model=?",
        (provider, model)
    ).fetchone()
    conn.close()
    
    if not rates:
        return 0.0, 0.0
    
    in_tok, out_tok = len(prompt) / 4, len(response) / 4
    cost_usd = ((in_tok / 1e6) * rates[0]) + ((out_tok / 1e6) * rates[1])
    return cost_usd, cost_usd / CREDIT_PRICE_USD


def log_usage(user_id: int, provider: str, model: str, latency_ms: int, status_: str,
              prompt: str = "", response: str = "") -> None:
    """Log usage to the database and deduct token costs."""
    cost_usd, credits = token_cost_credits(provider, model, prompt, response)
    
    if credits > 0:
        _deduct(user_id, credits, f"token cost: {model}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO usage_logs (user_id, provider, model, latency_ms, status, prompt, response, cost_usd, credits_used) VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, provider, model, latency_ms, status_, prompt, response, cost_usd, credits)
    )
    conn.commit()
    conn.close()
    logger.debug(f"Logged usage for user {user_id}: {provider}/{model}")


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user data by username."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, username, is_admin, plan_type, credits, plan_expires FROM users WHERE username=?",
        (username,)
    ).fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "username": row[1],
        "is_admin": row[2],
        "plan": row[3],
        "credits": row[4],
        "plan_expires": row[5]
    }


def check_model_access(user_plan: str, model: str) -> bool:
    """Check if a user's plan allows access to a specific model."""
    allowed = PLAN_CONFIG.get(user_plan, {}).get("models", [])
    return "*" in allowed or model in allowed


def require_credits(user_id: int, credits: float, desc: str) -> bool:
    """Check if user has enough credits and deduct if so."""
    return _deduct(user_id, credits, desc)
