import json
import os
import sqlite3

class SelfMonitorAgent:
    def __init__(self, kernel, db_path="/workspace/ai-sandbox/backend/usage.db"):
        self.kernel = kernel
        self.db_path = db_path

    async def analyze_performance(self, provider: str, model: str, api_key: str = None):
        print("🧠 Self-Monitor: Analyzing OS logs for optimization...")
        
        # 1. Fetch recent logs
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT provider, model, latency_ms, status FROM usage_logs ORDER BY timestamp DESC LIMIT 100")
        logs = cursor.fetchall()
        conn.close()
        
        # 2. Reasoning to identify bottlenecks
        log_summary = json.dumps(logs)
        messages = [
            {"role": "system", "content": "You are the Nexus Self-Monitor. Identify performance bottlenecks or recurring errors in the OS and propose a 'Core Upgrade' (Python script)."},
            {"role": "user", "content": f"Recent Usage Logs: {log_summary}\n\nPlease analyze and propose a specific kernel optimization."}
        ]
        
        proposal = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
        print("💡 Self-Monitor: Optimization Proposal Ready.")
        return proposal

class RecursiveCoderAgent:
    def __init__(self, kernel):
        self.kernel = kernel

    async def self_upgrade_core(self, proposal: str, target_file: str, provider: str, model: str, api_key: str = None):
        print(f"🛠️ Recursive Coder: Upgrading Kernel Module: {target_file}")

        # 1. Design the code upgrade
        prompt = f"""You are the Nexus Recursive Coder. Your goal is to rewrite a part of your own source code to improve the OS based on the proposal.

Proposal: {proposal}
Target File: {target_file}

Task:
1. Write the COMPLETE updated Python source code for the target file.
2. Ensure the new code is backward-compatible and fixes the identified issue.
3. Output the final code inside a single Python code block like this:
```python
# Your code here
```"""

        messages = [{"role": "user", "content": prompt}]

        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            
            # Extract code from Markdown block
            if "```python" in res_content:
                new_code = res_content.split("```python")[1].split("```")[0].strip()
            elif "```" in res_content:
                new_code = res_content.split("```")[1].split("```")[0].strip()
            else:
                new_code = res_content.strip()

            if not new_code or "import" not in new_code:
                raise Exception("Invalid or empty code generated.")

            # 2. Apply the upgrade (DANGEROUS: High-level autonomy)
            with open(target_file, "w") as f:
                f.write(new_code)

            print(f"✅ Recursive Upgrade: {target_file} successfully rewritten.")
            return True
        except Exception as e:
            print(f"⚠️ Upgrade Error: {str(e)}")
            return False
