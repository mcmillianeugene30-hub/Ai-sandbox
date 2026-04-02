"""
AutonomousModelResearcher — Frontier v8.0
Scans OpenRouter, Groq, and Gemini APIs for newly available models,
evaluates them, and auto-registers the best ones into the Nexus Kernel.
"""
import os
import json
import httpx
import sqlite3
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

from backend.config import PROJECT_ROOT, GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY
from backend.utils.logging import get_logger

logger = get_logger(__name__)

MODEL_REGISTRY_PATH = Path(PROJECT_ROOT) / "nexus_ai_os" / "core" / "model_registry.json"


class AutonomousModelResearcher:
    """Agent that discovers and evaluates new AI models."""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.groq_key = GROQ_API_KEY
        self.openrouter_key = OPENROUTER_API_KEY
        self.gemini_key = GEMINI_API_KEY

    async def fetch_groq_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from Groq API."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {self.groq_key}"}
                )
            
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                return [
                    {
                        "provider": "groq",
                        "id": m["id"],
                        "owned_by": m.get("owned_by", "groq"),
                        "context_window": m.get("context_window", 8192)
                    }
                    for m in models
                ]
        except Exception as e:
            logger.warning(f"Groq model fetch error: {e}")
        return []

    async def fetch_openrouter_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from OpenRouter API."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "HTTP-Referer": "https://nexus-ai-os.vercel.app"
                    }
                )
            
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                # Only include FREE models
                free_models = [
                    m for m in models
                    if str(m.get("pricing", {}).get("prompt", "1")) == "0"
                ]
                return [
                    {
                        "provider": "openrouter",
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "context_window": m.get("context_length", 8192),
                        "is_free": True
                    }
                    for m in free_models[:20]
                ]
        except Exception as e:
            logger.warning(f"OpenRouter model fetch error: {e}")
        return []

    async def fetch_gemini_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from Gemini API."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={self.gemini_key}"
                )
            
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return [
                    {
                        "provider": "google",
                        "id": m["name"].replace("models/", ""),
                        "name": m.get("displayName", m["name"]),
                        "context_window": m.get("inputTokenLimit", 32768)
                    }
                    for m in models
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]
        except Exception as e:
            logger.warning(f"Gemini model fetch error: {e}")
        return []

    def load_registry(self) -> Dict[str, Any]:
        """Load the model registry from disk."""
        if MODEL_REGISTRY_PATH.exists():
            with open(MODEL_REGISTRY_PATH, "r") as f:
                return json.load(f)
        return {"models": {}, "last_updated": None}

    def save_registry(self, registry: Dict[str, Any]):
        """Save the model registry to disk."""
        MODEL_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        registry["last_updated"] = datetime.utcnow().isoformat()
        with open(MODEL_REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2)

    async def evaluate_model(self, model: Dict[str, Any], provider: str, model_id: str) -> Dict[str, Any]:
        """Use AI to evaluate a model's quality."""
        prompt = f"""You are the Nexus Model Evaluator. A new AI model has been discovered.

Model: {json.dumps(model, indent=2)}

Score it on:
1. Speed (1-10)
2. Intelligence (1-10)  
3. Cost efficiency (1-10 — free=10, cheap=7, expensive=3)
4. Best use case (one sentence)
5. Recommended plan tier (STARTER / PRO / ENTERPRISE)

Respond as JSON: {{"speed": N, "intelligence": N, "cost": N, "use_case": "...", "tier": "...", "overall": N}}"""

        try:
            response = await self.kernel.chat_async(
                "groq", "llama-3.3-70b-versatile",
                [{"role": "user", "content": prompt}]
            )
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "{" in response:
                response = response[response.find("{"):response.rfind("}")+1]
            return json.loads(response)
        except Exception as e:
            logger.warning(f"Model evaluation error: {e}")
            return {
                "speed": 5, "intelligence": 5, "cost": 5,
                "use_case": "General purpose", "tier": "PRO", "overall": 5
            }

    def register_model_in_db(self, provider: str, model_id: str, is_free: bool, db_path: str):
        """Register a new model in the pricing_config database."""
        try:
            input_cost = 0.00 if is_free else 1.00
            output_cost = 0.00 if is_free else 2.00
            
            conn = sqlite3.connect(db_path)
            conn.execute(
                """INSERT OR IGNORE INTO pricing_config
                   (provider, model, input_cost_1m, output_cost_1m)
                   VALUES (?,?,?,?)""",
                (provider, model_id, input_cost, output_cost)
            )
            conn.commit()
            conn.close()
            logger.info(f"Registered: {provider}/{model_id} (free={is_free})")
        except Exception as e:
            logger.warning(f"DB register error: {e}")

    async def discover_and_register(
        self,
        db_path: str,
        log_fn: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Run a full discovery cycle."""
        def log(msg):
            logger.info(msg)
            if log_fn:
                log_fn(msg)

        log("🔍 AutonomousModelResearcher: Starting discovery cycle...")
        registry = self.load_registry()
        known_ids = set(registry["models"].keys())

        # Parallel fetch from all providers
        groq_models, or_models, gemini_models = await asyncio.gather(
            self.fetch_groq_models(),
            self.fetch_openrouter_models(),
            self.fetch_gemini_models()
        )

        all_models = groq_models + or_models + gemini_models
        log(f"   Found {len(all_models)} total models ({len(groq_models)} Groq, "
            f"{len(or_models)} OpenRouter free, {len(gemini_models)} Gemini)")

        new_models = [m for m in all_models if m["id"] not in known_ids]
        log(f"   🆕 {len(new_models)} NEW models discovered!")

        results = {"discovered": len(new_models), "registered": [], "evaluated": []}

        for model in new_models[:10]:  # evaluate top 10 new per cycle
            log(f"   🧠 Evaluating: {model['provider']}/{model['id']}")
            score = await self.evaluate_model(model, model["provider"], model["id"])
            model["score"] = score
            registry["models"][model["id"]] = model

            # Auto-register if overall score >= 6
            if score.get("overall", 0) >= 6:
                is_free = model.get("is_free", model["provider"] in ("groq", "google"))
                self.register_model_in_db(model["provider"], model["id"], is_free, db_path)
                results["registered"].append(f"{model['provider']}/{model['id']}")
                log(f"   ✅ Auto-registered {model['id']} (score={score['overall']}/10, tier={score.get('tier')})")
            else:
                log(f"   ⏭️  Skipped {model['id']} (score={score.get('overall', '?')}/10)")
            
            results["evaluated"].append({"model": model["id"], "score": score})

        self.save_registry(registry)
        log(f"🎯 Discovery complete. Registered {len(results['registered'])} new models.")
        return results
