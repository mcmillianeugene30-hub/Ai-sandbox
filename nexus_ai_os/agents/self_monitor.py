"""
Self-Monitor Agent — Autonomous evolution logic.
Analyzes usage logs and proposes kernel optimizations.
"""
import json
import os
import sqlite3
from typing import Optional
from pathlib import Path

from backend.config import DB_PATH
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class SelfMonitorAgent:
    """Agent that monitors system performance and proposes improvements."""
    
    def __init__(self, kernel, db_path: str = None):
        self.kernel = kernel
        self.db_path = db_path or str(DB_PATH)

    async def analyze_performance(self, provider: str, model: str, api_key: str = None) -> str:
        """Analyze usage logs and propose optimizations."""
        logger.info("Self-Monitor: Analyzing OS logs for optimization...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT provider, model, latency_ms, status FROM usage_logs ORDER BY timestamp DESC LIMIT 100"
            )
            logs = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            logs = []
        
        log_summary = json.dumps(logs)
        messages = [
            {
                "role": "system",
                "content": "You are the Nexus Self-Monitor. Identify performance bottlenecks or recurring errors in the OS and propose a 'Core Upgrade' (Python script)."
            },
            {
                "role": "user",
                "content": f"Recent Usage Logs: {log_summary}\n\nPlease analyze and propose a specific kernel optimization."
            }
        ]
        
        try:
            proposal = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            logger.info("Self-Monitor: Optimization Proposal Ready.")
            return proposal
        except Exception as e:
            logger.error(f"Self-monitor analysis failed: {e}")
            return f"Analysis failed: {e}"


class RecursiveCoderAgent:
    """Agent that can rewrite its own code for self-improvement."""
    
    def __init__(self, kernel):
        self.kernel = kernel

    async def self_upgrade_core(
        self,
        proposal: str,
        target_file: str,
        provider: str,
        model: str,
        api_key: str = None
    ) -> bool:
        """Rewrite kernel module based on optimization proposal."""
        logger.info(f"Recursive Coder: Upgrading Kernel Module: {target_file}")

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
                raise ValueError("Invalid or empty code generated.")

            # Apply the upgrade
            with open(target_file, "w") as f:
                f.write(new_code)

            logger.info(f"Recursive Upgrade: {target_file} successfully rewritten.")
            return True
        except Exception as e:
            logger.error(f"Upgrade Error: {e}")
            return False
