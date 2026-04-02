"""
AppArchitectAgent — Designs full-stack application architecture.
"""
import json
from typing import Dict, Any

from backend.utils.logging import get_logger
from nexus_ai_os.tools.fs_tool import fs_tool

logger = get_logger(__name__)


class AppArchitectAgent:
    """Agent that designs full-stack application architecture."""
    
    def __init__(self, kernel):
        self.kernel = kernel

    async def architect(
        self,
        goal: str,
        provider: str,
        model: str,
        api_key: str = None
    ) -> Dict[str, Any]:
        """Design a full-stack application based on the goal."""
        logger.info(f"Architecting Full-Stack App for: {goal}")
        
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
                res_content = res_content.split("```json")[1].split("```")[0].strip()
            elif "{" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}")+1]
            
            design = json.loads(res_content)
            logger.info("App Architecture Design Completed.")
            return design
        except Exception as e:
            logger.error(f"Architecture Error: {e}")
            return {
                "stack": {"frontend": "React/Next.js", "backend": "FastAPI", "db": "SQLite"},
                "structure": {
                    "frontend": {},
                    "backend": {"main.py": "", "requirements.txt": ""},
                    "docker": {"Dockerfile": ""}
                },
                "dependencies": ["fastapi", "uvicorn", "next", "react"]
            }

    def create_structure_recursive(self, base_path: str, structure: Dict[str, Any]):
        """Create directory structure recursively."""
        for name, content in structure.items():
            current_path = f"{base_path}/{name}"
            if isinstance(content, dict):
                fs_tool.mkdir(current_path)
                self.create_structure_recursive(current_path, content)
            else:
                fs_tool.write_file(current_path, content)
