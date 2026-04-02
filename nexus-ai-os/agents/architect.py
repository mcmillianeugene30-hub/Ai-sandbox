"""Application architecture agent for designing production-ready app structures."""
import json
import logging
from typing import Any, Dict, Optional

from core.kernel import NexusKernel

logger = logging.getLogger(__name__)


class AppArchitectAgent:
    """Design a full-stack architecture proposal from a high-level goal."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel

    async def architect(self, goal: str, provider: str, model: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Return a JSON architecture design with stack, structure, and dependencies."""
        logger.info("AppArchitectAgent.architect goal=%s", goal)
        prompt = f"""You are the Nexus App Architect. Your goal is to design a modern, full-stack application structure based on the user's high-level requirement.

User Goal: {goal}

Task:
1. Select a modern, high-performance tech stack (Frontend, Backend, Database).
   - 2026 Standards: Next.js (Frontend), FastAPI/Hono (Backend), Drizzle/SQLModel (ORM), SQLite/PostgreSQL (DB).
2. Design a complete directory and file structure (e.g., 'frontend/', 'backend/', 'docker/', etc.).
3. List the core dependencies (npm packages, pip requirements).
4. Output your design as a JSON object with keys: 'stack', 'structure' (nested object showing folders and files), and 'dependencies' (list of requirements).

Ensure the structure follows best practices for 2026 production apps (Dockerized, clean separation of concerns)."""
        messages = [{"role": "user", "content": prompt}]

        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            if "```json" in res_content:
                res_content = res_content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "{" in res_content and "}" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}") + 1]

            design = json.loads(res_content)
            logger.info("AppArchitectAgent architecture generated")
            return design
        except Exception as exc:
            logger.error("AppArchitectAgent.architect failed: %s", exc, exc_info=True)
            return {"stack": {}, "structure": {}, "dependencies": [], "error": str(exc)}
