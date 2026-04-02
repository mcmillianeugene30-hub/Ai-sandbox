"""
DevOpsAgent — Configures deployment and CI/CD pipelines.
"""
import json
from typing import Dict, Any

from backend.utils.logging import get_logger
from nexus_ai_os.tools.fs_tool import fs_tool

logger = get_logger(__name__)


class DevOpsAgent:
    """Agent that configures deployment and CI/CD pipelines."""
    
    def __init__(self, kernel):
        self.kernel = kernel

    async def configure_deployment(
        self,
        stack: Dict[str, str],
        structure: Dict[str, Any],
        provider: str,
        model: str,
        api_key: str = None
    ) -> Dict[str, Any]:
        """Configure deployment for the given tech stack."""
        logger.info(f"Configuring DevOps for Stack: {stack}")
        
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
                res_content = res_content.split("```json")[1].split("```")[0].strip()
            elif "{" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}")+1]
            
            config = json.loads(res_content)
            logger.info("DevOps Configuration Completed.")
            return config
        except Exception as e:
            logger.error(f"DevOps Error: {e}")
            return {
                "dockerfiles": {"backend/Dockerfile": "", "frontend/Dockerfile": ""},
                "compose": "version: '3.8'\nservices: ...",
                "ci_cd": "name: CI/CD\non: push: ..."
            }

    def write_configs(self, base_path: str, config: Dict[str, Any]):
        """Write deployment configurations to files."""
        for path, content in config.get('dockerfiles', {}).items():
            fs_tool.write_file(f"{base_path}/{path}", content)

        fs_tool.write_file(f"{base_path}/docker-compose.yml", config.get('compose', ''))
        fs_tool.mkdir(f"{base_path}/.github/workflows")
        fs_tool.write_file(f"{base_path}/.github/workflows/deploy.yml", config.get('ci_cd', ''))
