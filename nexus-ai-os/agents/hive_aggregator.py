"""Hive aggregation agent for synthesising multi-model outputs into a consensus."""
import json
import logging
from typing import Any, Dict, List, Optional

from core.kernel import NexusKernel

logger = logging.getLogger(__name__)


class HiveAggregator:
    """Aggregate and judge hive outputs produced by NexusKernel.hive_poll()."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel

    async def aggregate(
        self,
        prompt: str,
        hive_outputs: List[Dict[str, Any]],
        provider: str,
        model: str,
        api_key: Optional[str] = None,
    ) -> str:
        """Synthesize successful hive responses into a single consensus answer."""
        logger.info("HiveAggregator.aggregate outputs=%d", len(hive_outputs))
        synthesis_prompt = (
            "You are the Nexus Hive Aggregator. You have been given multiple responses from different AI models for the following prompt:\n\n"
            f"User Prompt: {prompt}\n\n---\nRESPONSES:\n"
        )
        for index, res in enumerate(hive_outputs, start=1):
            if res.get("status", "success") == "success":
                synthesis_prompt += (
                    f"Model {index} ({res.get('provider')}/{res.get('model', 'unknown')}):\n"
                    f"{res.get('content', '')}\n\n"
                )
        synthesis_prompt += (
            "---\n\nTask:\n"
            "1. Identify the consensus across all models (common patterns, shared truths).\n"
            "2. Identify any conflicts or unique insights from specific models.\n"
            "3. Synthesize the 'Best Version' of the response, combining the most accurate and useful parts of all responses.\n"
            "4. Output the final synthesized result only."
        )
        messages = [{"role": "user", "content": synthesis_prompt}]

        try:
            consensus_output = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            logger.info("HiveAggregator aggregate complete")
            return consensus_output
        except Exception as exc:
            logger.error("HiveAggregator.aggregate failed: %s", exc, exc_info=True)
            return f"Hive aggregation failed: {exc}"

    async def judge_hive(
        self,
        prompt: str,
        consensus: str,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate the final hive consensus and return a structured verdict."""
        logger.info("HiveAggregator.judge_hive prompt=%s", prompt)
        judge_prompt = f"""You are the Nexus Hive Judge.

Original Prompt: {prompt}
Consensus Answer: {consensus}

Evaluate the consensus answer for correctness, completeness, and actionability.
Return JSON with keys: status, score, feedback."""
        messages = [{"role": "user", "content": judge_prompt}]

        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            if "```json" in res_content:
                res_content = res_content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "{" in res_content and "}" in res_content:
                res_content = res_content[res_content.find("{"):res_content.rfind("}") + 1]
            return json.loads(res_content)
        except Exception as exc:
            logger.error("HiveAggregator.judge_hive failed: %s", exc, exc_info=True)
            return {"status": "REJECT", "score": 0, "feedback": f"Hive judgement failed: {exc}"}
