"""
NexusKernel — Core AI orchestration layer.
Provides unified async chat interface and multi-provider polling (Hive).
"""
import logging
import os
from typing import List, Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)


class NexusKernel:
    """Core AI orchestration kernel for Nexus AI-OS."""
    
    def __init__(self):
        self.logging_level = logging.INFO
        self._configure_logging()
    
    def _configure_logging(self) -> None:
        """Configure logging for the kernel."""
        logging.basicConfig(
            level=self.logging_level,
            format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        )
    
    async def chat_async(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None
    ) -> str:
        """
        Async chat completion for AI provider communication.
        
        Args:
            provider: AI provider name (groq, gemini, openrouter, ollama)
            model: Model identifier
            messages: List of message dicts with 'role' and 'content'
            api_key: Optional API key (falls back to env var)
        
        Returns:
            Response content string
        """
        try:
            # Import providers from backend
            from backend.providers import get_provider
            
            # Get API key from environment if not provided
            if not api_key:
                api_key = os.environ.get(f"{provider.upper()}_API_KEY")
            
            if not api_key and provider != "ollama":
                raise ValueError(f"API key required for {provider}")
            
            ai_provider = get_provider(provider)
            if not ai_provider:
                raise ValueError(f"Unknown provider: {provider}")
            
            response = ai_provider.chat_complete(model, messages, api_key)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content
        except Exception as e:
            logger.error(f"Chat async error: {e}")
            raise
    
    async def hive_poll(
        self,
        providers: List[Dict[str, str]],
        messages: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Poll multiple providers for consensus.
        
        Args:
            providers: List of provider config dicts with 'provider' and 'model'
            messages: List of message dicts
        
        Returns:
            List of response dicts with 'provider' and 'content'
        """
        from backend.providers import get_provider
        
        results = []
        for prov_config in providers:
            try:
                provider_name = prov_config.get("provider")
                model = prov_config.get("model", "llama-3.3-70b-versatile")
                api_key = os.environ.get(f"{provider_name.upper()}_API_KEY")
                
                if provider_name == "ollama" or api_key:
                    ai_provider = get_provider(provider_name)
                    if ai_provider:
                        response = ai_provider.chat_complete(model, messages, api_key)
                        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                        results.append({"provider": provider_name, "content": content})
            except Exception as e:
                logger.error(f"Hive poll error for {prov_config}: {e}")
        
        return results


def main():
    """Main entry point for standalone kernel execution."""
    import asyncio
    
    kernel = NexusKernel()
    logger.info("NexusKernel initialized")
    
    # Example usage
    async def demo():
        try:
            result = await kernel.chat_async(
                "groq",
                "llama-3.3-70b-versatile",
                [{"role": "user", "content": "Hello, Nexus!"}]
            )
            logger.info(f"Demo response: {result}")
        except Exception as e:
            logger.error(f"Demo error: {e}")
    
    asyncio.run(demo())


if __name__ == "__main__":
    main()
