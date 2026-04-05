"""Data Analyst Agent for processing and visualizing tabular data."""
import json
import logging
from typing import Any, Dict, List, Optional
from core.kernel import NexusKernel

logger = logging.getLogger(__name__)

class DataAnalystAgent:
    """Analyze datasets, identify trends, and propose visualizations."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel

    async def analyze(
        self,
        data_summary: str,
        goal: str,
        provider: str = "groq",
        model: str = "llama-3.3-70b-versatile",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform a deep analysis on a data summary."""
        logger.info(f"DataAnalyst: Analyzing data for goal: {goal}")
        
        prompt = f"""You are the Nexus Data Analyst. 
        
        Dataset Summary: {data_summary}
        Analysis Goal: {goal}
        
        Task:
        1. Identify key trends and anomalies.
        2. Propose 3 specific visualizations (chart type, X-axis, Y-axis).
        3. Provide a high-level executive summary.
        
        Output your findings in JSON:
        {{
          "trends": ["...", "..."],
          "visualizations": [
            {{"type": "bar", "x": "...", "y": "...", "title": "..."}}
          ],
          "summary": "..."
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        try:
            res_content = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            return self.kernel.extract_json(res_content)
        except Exception as exc:
            logger.error(f"DataAnalyst failed: {exc}", exc_info=True)
            return {"error": str(exc)}
