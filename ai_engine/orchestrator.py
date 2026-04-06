import asyncio
import logging
from typing import List, Dict, Any, Optional
from core.kernel import kernel
from agents.researcher import ResearcherAgent
from agents.coder import CoderAgent
from agents.reviewer import ReviewerAgent
from agents.data_analyst import DataAnalystAgent

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self):
        self.researcher = ResearcherAgent(kernel)
        self.coder = CoderAgent(kernel)
        self.reviewer = ReviewerAgent(kernel)
        self.analyst = DataAnalystAgent(kernel)

    async def execute_chain(self, chain: List[Dict[str, Any]], initial_input: str, api_key: str = None) -> List[Dict[str, Any]]:
        """
        Execute a chain of agents. Each node in the chain can be an agent call.
        Chain format: [{"id": "n1", "type": "researcher", "provider": "groq", "model": "..."}, ...]
        """
        results = []
        current_input = initial_input

        for node in chain:
            node_type = node.get("type")
            provider = node.get("provider", "groq")
            model = node.get("model", "llama-3.3-70b-versatile")
            
            logger.info(f"Orchestrator: Executing node {node_type}")
            
            try:
                if node_type == "researcher":
                    output = await self.researcher.research(current_input, provider, model, api_key=api_key)
                elif node_type == "coder":
                    # For visual chain, we might just generate one file or a main script
                    files = await self.coder.build_files(current_input, ["main.py"], provider, model, api_key=api_key)
                    output = files.get("main.py", "Error: No code generated.")
                elif node_type == "reviewer":
                    audit = await self.reviewer.review(current_input, provider, model, api_key=api_key)
                    output = f"Score: {audit.get('score', 0)}\nVerdict: {audit.get('verdict', 'N/A')}\nIssues: {audit.get('issues', [])}"
                elif node_type == "llm":
                    output = await kernel.chat_async(provider, model, [{"role": "user", "content": current_input}], api_key=api_key)
                elif node_type == "analyst":
                    goal = node.get("goal", "Identify trends")
                    res = await self.analyst.analyze(current_input, goal, provider, model, api_key=api_key)
                    output = f"Summary: {res.get('summary', 'N/A')}\nTrends: {res.get('trends', [])}"
                else:
                    output = f"Unknown node type: {node_type}"
                
                results.append({"node_id": node.get("id"), "type": node_type, "output": output})
                current_input = output # Pass output to next node
            except Exception as e:
                logger.error(f"Node {node_type} failed: {e}")
                results.append({"node_id": node.get("id"), "type": node_type, "error": str(e)})
                break # Stop chain on error

        return results

orchestrator = AgentOrchestrator()
