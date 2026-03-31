import sys
import os
import json
from typing import Dict, Any, List

sys.path.append('/workspace/ai-sandbox/nexus-ai-os')
from tools.shell import ShellTool, PythonExecutor
from core.memory_bank import memory_bank
from tools.fs_tool import fs_tool

class CoderAgent:
    def __init__(self, kernel):
        self.kernel = kernel
        self.py_exec = PythonExecutor()

    async def build_files(self, task: str, files_to_create: List[str], provider: str, model: str, api_key: str = None, max_retries: int = 3):
        print(f"🚀 Building Full-Stack Files for Task: {task}")
        
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
            print(f"🧠 Coder Reasoning (Attempt {i+1})...")
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            
            try:
                if "```json" in res_content:
                    res_content = res_content.split("```json")[1].split("```")[0].strip()
                elif "{" in res_content:
                    res_content = res_content[res_content.find("{"):res_content.rfind("}")+1]
                
                generated = json.loads(res_content)
                for path, content in generated.get('files', {}).items():
                    fs_tool.write_file(path, content)
                
                print(f"✅ Full-Stack Code Generation Completed.")
                return generated
            except Exception as e:
                print(f"⚠️ Coding Error: {str(e)}. Retrying...")
                messages.append({"role": "assistant", "content": res_content})
                messages.append({"role": "user", "content": f"The JSON was invalid or code was incomplete. Error: {str(e)}. Please fix and try again."})
        
        return {"files": {}}

    def self_correct(self, task: str, provider: str, model: str, api_key: str = None, max_retries: int = 5):
        # (Preserve existing single-file self-correction logic if needed)
        pass
