"""Self-monitoring agents for performance analysis and guided core refactoring."""
import json
import logging
import os
import sqlite3
from typing import Optional

from core.kernel import NexusKernel, PROJECT_ROOT, RENDER_DISK_PATH

logger = logging.getLogger(__name__)

DEFAULT_USAGE_DB = os.path.join(RENDER_DISK_PATH, "usage.db")


class SelfMonitorAgent:
    """Analyze historical usage logs and propose kernel optimizations."""

    def __init__(self, kernel: NexusKernel, db_path: str = DEFAULT_USAGE_DB):
        self.kernel = kernel
        self.db_path = db_path

    async def analyze_performance(self, provider: str, model: str, api_key: Optional[str] = None) -> str:
        """Read recent usage logs and return an LLM-generated optimization proposal."""
        logger.info("SelfMonitorAgent.analyze_performance db_path=%s", self.db_path)
        logs = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT provider, model, latency_ms, status FROM usage_logs ORDER BY timestamp DESC LIMIT 100"
            )
            logs = cursor.fetchall()
            conn.close()
        except Exception as exc:
            logger.error("SelfMonitorAgent log query failed: %s", exc, exc_info=True)

        log_summary = json.dumps(logs)
        messages = [
            {
                "role": "system",
                "content": "You are the Nexus Self-Monitor. Identify performance bottlenecks or recurring errors in the OS and propose a 'Core Upgrade' (Python script).",
            },
            {
                "role": "user",
                "content": f"Recent Usage Logs: {log_summary}\n\nPlease analyze and propose a specific kernel optimization.",
            },
        ]

        try:
            proposal = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            logger.info("SelfMonitorAgent proposal generated")
            return proposal
        except Exception as exc:
            logger.error("SelfMonitorAgent.analyze_performance failed: %s", exc, exc_info=True)
            return f"Performance analysis unavailable: {exc}"


class RecursiveCoderAgent:
    """Generate updated core-file source code from a self-monitor proposal."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel

    async def self_upgrade_core(
        self,
        proposal: str,
        target_file: str,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
    ) -> str:
        """Return the full updated source code for a target core file."""
        logger.info("RecursiveCoderAgent.self_upgrade_core target_file=%s", target_file)
        prompt = f"""You are the Nexus Recursive Coder. Your goal is to rewrite a part of your own source code to improve the OS based on the proposal.

Proposal: {proposal}
Target File: {target_file}

Task:
1. Write the COMPLETE updated Python source code for the target file.
2. Ensure the new code is backward-compatible and fixes the identified issue.
3. Output the final code only."""
        messages = [{"role": "user", "content": prompt}]

        try:
            return await self.kernel.chat_async(provider, model, messages, api_key=api_key)
        except Exception as exc:
            logger.error("RecursiveCoderAgent.self_upgrade_core failed: %s", exc, exc_info=True)
            return f"Upgrade generation failed: {exc}"
