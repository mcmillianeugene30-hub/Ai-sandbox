"""
ReviewerAgent — Reviews code for correctness and security.
"""
import json

from backend.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewerAgent:
    """Agent that reviews code for correctness and security."""
    
    def __init__(self, kernel):
        self.kernel = kernel

    async def review(
        self,
        code: str,
        task: str,
        provider: str,
        model: str,
        api_key: str = None
    ) -> dict:
        """Review code for correctness and security."""
        logger.info(f"Reviewing Code for Task: {task}")
        
        review_prompt = f"""You are a professional Code Auditor. Evaluate the following Python code for correctness, security, and best practices based on the original task.

Task: {task}
Code:
{code}

Output your final verdict as a JSON with keys: 'status' (PASS/REJECT), 'score' (0-10), and 'feedback' (1 sentence)."""

        messages = [{"role": "user", "content": review_prompt}]
        
        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            # Find JSON block
            if "```json" in res_content:
                res_content = res_content.split("```json")[1].split("```")[0].strip()
            elif "{" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}")+1]
            
            review_data = json.loads(res_content)
            logger.info(f"Review Score: {review_data.get('score', 'N/A')}/10 - Status: {review_data.get('status', 'N/A')}")
            return review_data
        except Exception as e:
            logger.error(f"Review Error: {e}")
            return {"status": "REJECT", "score": 0, "feedback": f"Review failed: {e}"}
