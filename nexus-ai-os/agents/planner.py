import json
import asyncio

class PlannerAgent:
    def __init__(self, kernel):
        self.kernel = kernel

    async def decompose(self, goal: str, provider: str, model: str, api_key: str = None) -> list:
        print(f"🗺️ Decomposing Goal: {goal}")

        prompt = f"""You are the Nexus Strategic Planner. Decompose the following high-level user goal into a list of 2-4 concrete technical sub-tasks for the Coder and Researcher agents.
    Goal: {goal}

    Output your plan as a JSON list of objects with keys: 'id' (task_1, task_2, etc.), 'task' (description), 'dependencies' (list of IDs)."""

        messages = [{"role": "user", "content": prompt}]

        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            if "```json" in res_content:
                res_content = res_content.split("```json")[1].split("```")[0].strip()
            elif "[" in res_content:
                res_content = res_content[res_content.find("["):res_content.rfind("]")+1]

            plan = json.loads(res_content)
            print(f"📋 Task Tree Generated: {len(plan)} sub-tasks.")
            return plan
        except Exception as e:
            print(f"⚠️ Planner Error: {str(e)}. Defaulting to single-step execution.")
            return [{"id": "task_1", "task": goal, "dependencies": []}]
