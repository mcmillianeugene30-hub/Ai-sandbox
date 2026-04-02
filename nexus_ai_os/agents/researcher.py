"""
ResearcherAgent — Researches topics using RAG and MemoryBank.
"""
from backend.rag_manager import rag_manager
from nexus_ai_os.core.memory_bank import memory_bank
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class ResearcherAgent:
    """Agent that researches topics using RAG and memory."""
    
    def __init__(self, kernel):
        self.kernel = kernel

    async def research(
        self,
        topic: str,
        provider: str,
        model: str,
        api_key: str = None
    ) -> str:
        """Research a topic using local RAG and memory bank."""
        logger.info(f"Researching Topic: {topic}")
        
        # 1. Local RAG search (Technical Docs)
        local_context = rag_manager.query(topic)
        
        # 2. MemoryBank search (Past Successes)
        past_successes = memory_bank.query(topic)
        success_context = "\n".join(past_successes) if past_successes else "None found."
        
        # 3. Reasoning to synthesize findings
        messages = [
            {
                "role": "system",
                "content": "You are a professional AI Researcher. Synthesize the provided technical context and past successful examples into a concise brief for a Coder Agent."
            },
            {
                "role": "user",
                "content": f"Topic: {topic}\n\nTechnical Docs (RAG): {local_context}\n\nPast Successes (MemoryBank): {success_context}\n\nPlease provide a research brief."
            }
        ]
        
        try:
            brief = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            logger.info("Research Brief Ready (with Memory hits).")
            return brief
        except Exception as e:
            logger.error(f"Research error: {e}")
            return f"Research failed: {e}"
