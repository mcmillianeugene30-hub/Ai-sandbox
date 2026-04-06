"""Planning agent for decomposing a high-level goal into execution steps."""
import json
import logging
from typing import Any, Dict, List, Optional

from core.kernel import NexusKernel

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Generate a concise execution plan for downstream Nexus agents."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel

    async def decompose(self, goal: str, provider: str, model: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Decompose a goal into 2-4 structured tasks, with safe fallback on failure."""
        logger.info("PlannerAgent.decompose goal=%s", goal)
        prompt = (
            "You are the Nexus Strategic Planner. Decompose the following high-level user goal "
            "into a list of 2-4 concrete technical sub-tasks for the Coder and Researcher agents.\n\n"
            f"Goal: {goal}\n\n"
            "Output your plan as a JSON list of objects with keys: 'id' (task_1, task_2, etc.), "
            "'task' (description), 'dependencies' (list of IDs)."
        )
        messages = [{"role": "user", "content": prompt}]

        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            if "```json" in res_content:
                res_content = res_content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "[" in res_content and "]" in res_content:
                res_content = res_content[res_content.find("["):res_content.rfind("]") + 1]

            plan = json.loads(res_content)
            logger.info("PlannerAgent produced %d tasks", len(plan))
            return plan
        except Exception as exc:
            logger.error("PlannerAgent.decompose failed: %s", exc, exc_info=True)
            return [{"id": "task_1", "task": goal, "dependencies": []}]
