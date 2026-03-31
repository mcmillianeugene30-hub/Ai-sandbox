import asyncio
import sys
import os
from typing import List, Dict, Any

# Ensure we can import from the backend
sys.path.append('/workspace/ai-sandbox/backend')
from providers import get_provider

class NexusKernel:
    def __init__(self):
        self.state = {"logs": [], "artifacts": []}

    async def chat_async(self, provider_name: str, model: str, messages: list, api_key: str = None) -> str:
        provider = get_provider(provider_name)
        if not provider:
            raise Exception(f"Provider {provider_name} not found.")
        
        # Mapping API keys from environment if not provided
        if not api_key:
             env_key_map = {"gemini": "GOOGLE_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
             api_key = os.getenv(env_key_map.get(provider_name.lower()))
        
        # Use a thread for the synchronous chat_complete call to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: provider.chat_complete(model=model, messages=messages, api_key=api_key)
        )
        return response["choices"][0]["message"]["content"]

    async def hive_poll(self, providers_models: List[Dict[str, str]], messages: list) -> List[Dict[str, str]]:
        """Poll multiple models in parallel for a consensus vote."""
        tasks = []
        for pm in providers_models:
            tasks.append(self.chat_async(pm['provider'], pm['model'], messages))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        outputs = []
        for i, res in enumerate(results):
            pm = providers_models[i]
            if isinstance(res, Exception):
                outputs.append({"provider": pm['provider'], "model": pm['model'], "content": f"Error: {str(res)}", "status": "failed"})
            else:
                outputs.append({"provider": pm['provider'], "model": pm['model'], "content": res, "status": "success"})
        
        return outputs

    # Synchronous wrapper for backward compatibility
    def chat(self, provider_name: str, model: str, messages: list, api_key: str = None) -> str:
        return asyncio.run(self.chat_async(provider_name, model, messages, api_key))
