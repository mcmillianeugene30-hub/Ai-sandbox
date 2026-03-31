class ReviewerAgent:
    def __init__(self, kernel):
        self.kernel = kernel

    def review(self, code: str, task: str, provider: str, model: str, api_key: str = None) -> dict:
        print(f"🧐 Reviewing Code for Task: {task}")
        
        review_prompt = f"""You are a professional Code Auditor. Evaluate the following Python code for correctness, security, and best practices based on the original task.
Task: {task}
Code:
{code}

Output your final verdict as a JSON with keys: 'status' (PASS/REJECT), 'score' (0-10), and 'feedback' (1 sentence)."""

        messages = [{"role": "user", "content": review_prompt}]
        
        try:
            res_content = self.kernel.chat(provider, model, messages, api_key=api_key)
            # Find JSON block
            if "```json" in res_content:
                res_content = res_content.split("```json")[1].split("```")[0].strip()
            elif "{" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}")+1]
            
            import json
            review_data = json.loads(res_content)
            print(f"📊 Review Score: {review_data.get('score', 'N/A')}/10 - Status: {review_data.get('status', 'N/A')}")
            return review_data
        except Exception as e:
            print(f"⚠️ Review Error: {str(e)}")
            return {"status": "REJECT", "score": 0, "feedback": f"Review failed: {str(e)}"}
