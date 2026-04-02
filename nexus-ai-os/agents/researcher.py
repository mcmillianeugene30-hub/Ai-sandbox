"""Research agent for synthesising local RAG context and stored memories."""
import logging
import os
import sys
from typing import Optional

from core.kernel import NexusKernel, PROJECT_ROOT
from core.memory_bank import memory_bank

BACKEND_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "backend"))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from rag_manager import rag_manager  # type: ignore

logger = logging.getLogger(__name__)


class ResearcherAgent:
    """Produce research briefs using RAG, memories, and NexusKernel chat routing."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel

    async def research(self, topic: str, provider: str, model: str, api_key: Optional[str] = None) -> str:
        """Return a concise research brief for the given topic."""
        logger.info("ResearcherAgent.research topic=%s", topic)
        try:
            local_context = rag_manager.query(topic)
        except Exception as exc:
            logger.error("ResearcherAgent local RAG query failed: %s", exc, exc_info=True)
            local_context = ""

        try:
            past_successes = memory_bank.query(topic)
            success_context = "\n".join(past_successes) if past_successes else "None found."
        except Exception as exc:
            logger.error("ResearcherAgent memory query failed: %s", exc, exc_info=True)
            success_context = "None found."

        messages = [
            {
                "role": "system",
                "content": "You are a professional AI Researcher. Synthesize the provided technical context and past successful examples into a concise brief for a Coder Agent.",
            },
            {
                "role": "user",
                "content": (
                    f"Topic: {topic}\n\n"
                    f"Technical Docs (RAG): {local_context}\n\n"
                    f"Past Successes (MemoryBank): {success_context}\n\n"
                    "Please provide a research brief."
                ),
            },
        ]

        try:
            brief = await self.kernel.chat_async(provider, model, messages, api_key=api_key)
            logger.info("ResearcherAgent research brief generated")
            return brief
        except Exception as exc:
            logger.error("ResearcherAgent.research failed: %s", exc, exc_info=True)
            return f"Research unavailable: {exc}"
