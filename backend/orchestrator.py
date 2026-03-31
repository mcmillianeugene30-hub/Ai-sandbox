import asyncio
from typing import List, Dict, Any
from .providers import get_provider
from .rag_manager import rag_manager

class AgentOrchestrator:
    async def execute_chain(self, chain: List[Dict[str, Any]], initial_input: str, api_key: str = None) -> List[Dict[str, Any]]:
        results = []
        current_input = initial_input
        
        for step in chain:
            node_type = step.get("type")
            if node_type == "llm":
                provider = get_provider(step["provider"])
                # Simple LLM call
                messages = [{"role": "user", "content": current_input}]
                if step.get("system_prompt"):
                    messages.insert(0, {"role": "system", "content": step["system_prompt"]})
                
                # Assume synchronous for now or wrap in run_in_executor if needed
                response = provider.chat_complete(
                    model=step["model"],
                    messages=messages,
                    api_key=api_key or step.get("api_key")
                )
                output = response["choices"][0]["message"]["content"]
                results.append({"node": step["id"], "output": output})
                current_input = output # Chain output to next input
            
            elif node_type == "rag":
                context = rag_manager.query(current_input)
                current_input = f"Context: {context}\n\nQuery: {current_input}"
                results.append({"node": step["id"], "output": current_input})
                
        return results

orchestrator = AgentOrchestrator()
