"""
PlannerAgent — Decomposes goals into sub-tasks.
"""
import json

from backend.utils.logging import get_logger

logger = get_logger(__name__)


class PlannerAgent:
    """Agent that decomposes goals into actionable sub-tasks."""
    
    def __init__(self, kernel):
        self.kernel = kernel

    async def decompose(
        self,
        goal: str,
        provider: str,
        model: str,
        api_key: str = None
    ) -> list:
        """Decompose a goal into sub-tasks."""
        logger.info(f"Decomposing Goal: {goal}")

        prompt = f"""You are the Nexus Strategic Planner. Decompose the following high-level user goal into a list of 2-4 concrete technical sub-tasks for the Coder and Researcher agents.

Goal: {goal}

Output your plan as a JSON list of objects with keys: 'id' (task_1, task_2, etc.), 'task' (description), 'dependencies' (list of IDs), 'files_to_create' (list of file paths)."""

        messages = [{"role": "user", "content": prompt}]

        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            if "```json" in res_content:
                res_content = res_content.split("```json")[1].split("```")[0].strip()
            elif "[" in res_content:
                res_content = res_content[res_content.find("["):res_content.rfind("]")+1]

            plan = json.loads(res_content)
            logger.info(f"Task Tree Generated: {len(plan)} sub-tasks.")
            return plan
        except Exception as e:
            logger.error(f"Planner Error: {e}. Defaulting to single-step execution.")
            return [{"id": "task_1", "task": goal, "dependencies": [], "files_to_create": []}]
