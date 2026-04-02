"""
Project Nexus Configuration
Centralized configuration and secrets management using environment variables.
"""
import os
from pathlib import Path

# Project Root
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
NEXUS_AI_OS_DIR = PROJECT_ROOT / "nexus_ai_os"

# Data Directories
DATA_DIR = Path(os.environ.get("RENDER_DISK_PATH", BACKEND_DIR / "data"))
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DB_DIR = BACKEND_DIR / "chroma_db"
MEMORY_DB_DIR = NEXUS_AI_OS_DIR / "memory_db"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DB_DIR.mkdir(parents=True, exist_ok=True)

# Database Paths
DB_PATH = DATA_DIR / "usage.db"
SWARM_DB_PATH = MEMORY_DB_DIR / "swarm.db"

# Security
SECRET_KEY = os.environ.get("SECRET_KEY", "nexus_super_secret_key_2026")
ALGORITHM = "HS256"
TOKEN_EXP_MINUTES = int(os.environ.get("TOKEN_EXP_MINUTES", "600"))

# API Keys (loaded from environment)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
RENDER_SERVICE_ID = os.environ.get("RENDER_SERVICE_ID", "")

# Frontend URL
FRONTEND_URL = os.environ.get("FRONTEND_URL", "*")
RENDER_SERVICE_URL = os.environ.get("RENDER_SERVICE_URL", "https://nexus-backend.onrender.com")

# Pricing Configuration
CREDIT_PRICE_USD = 0.10  # 1 credit = $0.10

PLAN_CONFIG = {
    "STARTER": {
        "price": 9.00,
        "credits": 90,
        "models": ["llama-3.1-8b-instant", "gemini-1.5-flash", "mistral-7b"]
    },
    "PRO": {
        "price": 29.00,
        "credits": 150,
        "models": [
            "llama-3.1-8b-instant", "llama-3.3-70b-versatile",
            "gemini-1.5-flash", "gemini-1.5-pro", "mistral-7b", "llama3"
        ]
    },
    "ENTERPRISE": {
        "price": 99.00,
        "credits": 600,
        "models": ["*"]  # all models
    },
}

# Action Costs (credits per action)
ACTION_COSTS = {
    "chat": 0.1,
    "agent_step": 1.0,
    "deploy": 5.0,
    "rag_query": 0.5,
}

# Top-up Packs
TOPUP_PACKS = {
    "micro": {"price": 5.00, "credits": 55, "label": "Micro Pack (+10% bonus)"},
    "builder": {"price": 10.00, "credits": 115, "label": "Builder Pack (+15% bonus)"},
    "power": {"price": 25.00, "credits": 300, "label": "Power Pack (+20% bonus)"},
    "studio": {"price": 50.00, "credits": 650, "label": "Studio Pack (+30% bonus)"},
}

# Provider Model Lists
AVAILABLE_MODELS = {
    "gemini": ["gemini-1.5-flash", "gemini-1.5-pro"],
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    "openrouter": ["gpt-4o", "claude-sonnet-4", "gpt-3.5-turbo"],
    "ollama": ["llama3", "mistral", "phi3"]
}
