import json
from typing import Dict, Any, List

class AppArchitectAgent:
    def __init__(self, kernel):
        self.kernel = kernel

    async def architect(self, goal: str, provider: str, model: str, api_key: str = None) -> Dict[str, Any]:
        print(f"🏗️ Architecting Full-Stack App for: {goal}")
        
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
            print(f"✅ App Architecture Design Completed.")
            return design
        except Exception as e:
            print(f"⚠️ Architecture Error: {str(e)}")
            return {
                "stack": {"frontend": "React/Next.js", "backend": "FastAPI", "db": "SQLite"},
                "structure": {"frontend": {}, "backend": {"main.py": "", "requirements.txt": ""}, "docker": {"Dockerfile": ""}},
                "dependencies": ["fastapi", "uvicorn", "next", "react"]
            }

    def create_structure_recursive(self, base_path: str, structure: Dict[str, Any]):
        from tools.fs_tool import fs_tool
        for name, content in structure.items():
            current_path = f"{base_path}/{name}"
            if isinstance(content, dict):
                fs_tool.mkdir(current_path)
                self.create_structure_recursive(current_path, content)
            else:
                fs_tool.write_file(current_path, content)
