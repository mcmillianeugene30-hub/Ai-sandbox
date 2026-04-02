"""
CoderAgent — Generates production-ready code.
"""
import json
from typing import Dict, Any, List

from backend.utils.logging import get_logger
from nexus_ai_os.tools.fs_tool import fs_tool

logger = get_logger(__name__)


class CoderAgent:
    """Agent that generates production-ready code."""
    
    def __init__(self, kernel):
        self.kernel = kernel

    async def build_files(
        self,
        task: str,
        files_to_create: List[str],
        provider: str,
        model: str,
        api_key: str = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Generate code for the given task and files."""
        logger.info(f"Building Full-Stack Files for Task: {task}")
        
        prompt = f"""You are the Nexus Full-Stack Coder. Your goal is to generate high-quality, production-ready code for the following task and files.
        
Task: {task}
Files to Create: {files_to_create}

Task:
1. Write the complete source code for each requested file.
2. Ensure cross-file consistency (e.g., API endpoints in 'backend/' must match 'frontend/' calls).
3. Follow 2026 best practices: TypeScript, FastAPI, React Hooks, Tailwind CSS.
4. Output your code as a JSON object with keys: 'files' (key-value mapping of paths to file content).

Output ONLY the JSON object."""

        messages = [{"role": "user", "content": prompt}]
        
        for i in range(max_retries):
            logger.info(f"Coder Reasoning (Attempt {i+1})...")
            
            try:
                res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
                
                if "```json" in res_content:
                    res_content = res_content.split("```json")[1].split("```")[0].strip()
                elif "{" in res_content:
                    res_content = res_content[res_content.find("{"):res_content.rfind("}")+1]
                
                generated = json.loads(res_content)
                for path, content in generated.get('files', {}).items():
                    fs_tool.write_file(path, content)
                
                logger.info("Full-Stack Code Generation Completed.")
                return generated
            except Exception as e:
                logger.warning(f"Coding Error: {e}. Retrying...")
                messages.append({"role": "assistant", "content": res_content})
                messages.append({
                    "role": "user",
                    "content": f"The JSON was invalid or code was incomplete. Error: {e}. Please fix and try again."
                })
        
        return {"files": {}}

    def self_correct(
        self,
        task: str,
        provider: str,
        model: str,
        api_key: str = None,
        max_retries: int = 5
    ):
        """Self-correction logic for code generation."""
        # TODO: Implement self-correction
        pass
