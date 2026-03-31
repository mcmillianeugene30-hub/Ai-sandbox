import json
from typing import List, Dict, Any

class HiveAggregator:
    def __init__(self, kernel):
        self.kernel = kernel

    async def aggregate(self, prompt: str, hive_outputs: List[Dict[str, Any]], provider: str, model: str, api_key: str = None) -> str:
        """Synthesize multiple model responses into a single 'Hive Consensus' output."""
        print(f"🐝 Hive Aggregator: Processing {len(hive_outputs)} responses...")
        
        # Prepare the synthesis prompt
        synthesis_prompt = f"""You are the Nexus Hive Aggregator. You have been given multiple responses from different AI models for the following prompt:
        
User Prompt: {prompt}

---
RESPONSES:
"""
        for i, res in enumerate(hive_outputs):
            if res['status'] == 'success':
                synthesis_prompt += f"Model {i+1} ({res['provider']}/{res['model']}):\n{res['content']}\n\n"
        
        synthesis_prompt += """---
        
Task: 
1. Identify the consensus across all models (common patterns, shared truths).
2. Identify any conflicts or unique insights from specific models.
3. Synthesize the 'Best Version' of the response, combining the most accurate and useful parts of all responses.
4. Output the final synthesized result only."""

        messages = [{"role": "user", "content": synthesis_prompt}]
        
        consensus_output = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
        print(f"✅ Hive Consensus Synthesized.")
        return consensus_output

    async def judge_hive(self, prompt: str, consensus: str, provider: str, model: str, api_key: str = None) -> dict:
        """Have a judge evaluate the Hive's final consensus output."""
        judge_prompt = f"""You are the Nexus Hive Judge. Evaluate the quality of the final Hive Consensus response for the given user prompt.
        
User Prompt: {prompt}
Hive Consensus Response:
{consensus}

Output your verdict as a JSON with keys: 'quality_score' (0-10), 'consensus_strength' (LOW/MED/HIGH), and 'feedback' (1 sentence)."""

        messages = [{"role": "user", "content": judge_prompt}]
        
        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            if "{" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}")+1]
            
            review_data = json.loads(res_content)
            print(f"⚖️ Hive Verdict: Score {review_data.get('quality_score', 'N/A')}/10 - Consensus: {review_data.get('consensus_strength', 'N/A')}")
            return review_data
        except Exception as e:
            print(f"⚠️ Hive Judge Error: {str(e)}")
            return {"quality_score": 0, "consensus_strength": "LOW", "feedback": f"Judge failed: {str(e)}"}
