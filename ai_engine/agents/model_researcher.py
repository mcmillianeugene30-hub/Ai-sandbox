"""Model research agent for discovering and persisting available provider models."""
import json
import logging
import os
from typing import Any, Dict, List

import httpx

from core.kernel import NexusKernel, PROJECT_ROOT, RENDER_DISK_PATH

logger = logging.getLogger(__name__)

MODEL_REGISTRY_PATH = os.path.join(PROJECT_ROOT, "core", "model_registry.json")
MODEL_RESEARCH_CACHE = os.path.join(RENDER_DISK_PATH, "model_research")


class AutonomousModelResearcher:
    """Discover model catalogs from supported providers and persist a consolidated registry."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel
        self.groq_key = os.environ.get("GROQ_API_KEY", "")
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        os.makedirs(MODEL_RESEARCH_CACHE, exist_ok=True)

    async def fetch_groq_models(self) -> List[Dict[str, Any]]:
        """Fetch available Groq models."""
        if not self.groq_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {self.groq_key}"},
                )
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                return [
                    {
                        "provider": "groq",
                        "id": model["id"],
                        "owned_by": model.get("owned_by", "groq"),
                        "context_window": model.get("context_window", 8192),
                    }
                    for model in models
                ]
            logger.error("fetch_groq_models failed status=%s body=%s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("fetch_groq_models exception: %s", exc, exc_info=True)
        return []

    async def fetch_openrouter_models(self) -> List[Dict[str, Any]]:
        """Fetch available OpenRouter models."""
        if not self.openrouter_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {self.openrouter_key}"},
                )
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                return [
                    {
                        "provider": "openrouter",
                        "id": model["id"],
                        "owned_by": model.get("architecture", {}).get("modality", "unknown"),
                        "context_window": model.get("context_length", 0),
                    }
                    for model in models
                ]
            logger.error("fetch_openrouter_models failed status=%s body=%s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("fetch_openrouter_models exception: %s", exc, exc_info=True)
        return []

    async def fetch_gemini_models(self) -> List[Dict[str, Any]]:
        """Fetch available Gemini models."""
        if not self.gemini_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={self.gemini_key}"
                )
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return [
                    {
                        "provider": "google",
                        "id": model.get("name", "").replace("models/", ""),
                        "owned_by": "google",
                        "context_window": model.get("inputTokenLimit", 0),
                    }
                    for model in models
                ]
            logger.error("fetch_gemini_models failed status=%s body=%s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("fetch_gemini_models exception: %s", exc, exc_info=True)
        return []

    async def discover_models(self) -> List[Dict[str, Any]]:
        """Fetch and consolidate model catalogs across all supported providers."""
        import asyncio

        try:
            groq_models, openrouter_models, gemini_models = await asyncio.gather(
                self.fetch_groq_models(),
                self.fetch_openrouter_models(),
                self.fetch_gemini_models(),
            )
            models = groq_models + openrouter_models + gemini_models
            logger.info("AutonomousModelResearcher discovered %d models", len(models))
            return models
        except Exception as exc:
            logger.error("discover_models failed: %s", exc, exc_info=True)
            return []

    def save_registry(self, models: List[Dict[str, Any]]) -> bool:
        """Persist the consolidated model registry to core/model_registry.json."""
        try:
            with open(MODEL_REGISTRY_PATH, "w", encoding="utf-8") as handle:
                json.dump(models, handle, indent=2)
            logger.info("Model registry saved to %s", MODEL_REGISTRY_PATH)
            return True
        except Exception as exc:
            logger.error("save_registry failed: %s", exc, exc_info=True)
            return False
