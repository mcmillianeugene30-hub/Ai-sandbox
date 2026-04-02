"""DevOps agent for generating deployment configuration artifacts."""
import json
import logging
from typing import Any, Dict, Optional

from core.kernel import NexusKernel

logger = logging.getLogger(__name__)


class DevOpsAgent:
    """Design Docker, compose, and CI/CD configuration for Nexus projects."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel

    async def configure_deployment(
        self,
        stack: Dict[str, str],
        structure: Dict[str, Any],
        provider: str,
        model: str,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return deployment artifacts as a JSON object with docker and CI/CD content."""
        logger.info("DevOpsAgent.configure_deployment stack=%s", stack)
        prompt = f"""You are the Nexus DevOps Agent. Your goal is to design a robust, 2026-standard Dockerized deployment for the following full-stack application.

Tech Stack: {stack}
Project Structure: {structure}

Task:
1. Create optimized, multi-stage Dockerfiles for both 'frontend/' and 'backend/'.
2. Create a 'docker-compose.yml' that orchestrates all services (frontend, backend, and DB).
3. Create a GitHub Actions workflow for automated testing and deployment.
4. Output your design as a JSON object with keys: 'dockerfiles' (key-value mapping of paths to file content), 'compose' (docker-compose content), and 'ci_cd' (workflow file content).

Ensure you use 2026 standards: 'uv' for Python dependencies, 'pnpm' or 'bun' for Node.js, and multi-stage builds for minimal image size."""
        messages = [{"role": "user", "content": prompt}]

        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            if "```json" in res_content:
                res_content = res_content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "{" in res_content and "}" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}") + 1]

            config = json.loads(res_content)
            logger.info("DevOpsAgent deployment config generated")
            return config
        except Exception as exc:
            logger.error("DevOpsAgent.configure_deployment failed: %s", exc, exc_info=True)
            return {"dockerfiles": {}, "compose": "", "ci_cd": "", "error": str(exc)}
