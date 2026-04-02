"""Code review agent for evaluating generated code against task requirements."""
import json
import logging
from typing import Any, Dict, Optional

from core.kernel import NexusKernel

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """Review generated code for correctness, security, and best practices."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel

    async def review(self, code: str, task: str, provider: str, model: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Return a structured review verdict for the supplied code."""
        logger.info("ReviewerAgent.review task=%s", task)
        review_prompt = f"""You are a professional Code Auditor. Evaluate the following Python code for correctness, security, and best practices based on the original task.
Task: {task}
Code:
{code}

Output your final verdict as a JSON with keys: 'status' (PASS/REJECT), 'score' (0-10), and 'feedback' (1 sentence)."""
        messages = [{"role": "user", "content": review_prompt}]

        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            if "```json" in res_content:
                res_content = res_content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "{" in res_content and "}" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}") + 1]

            review_data = json.loads(res_content)
            logger.info("ReviewerAgent score=%s status=%s", review_data.get("score"), review_data.get("status"))
            return review_data
        except Exception as exc:
            logger.error("ReviewerAgent.review failed: %s", exc, exc_info=True)
            return {"status": "REJECT", "score": 0, "feedback": f"Review failed: {exc}"}
