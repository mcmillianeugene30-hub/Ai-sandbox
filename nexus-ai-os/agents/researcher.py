import sys
import os
sys.path.append('/workspace/ai-sandbox/backend')
from rag_manager import rag_manager
from core.memory_bank import memory_bank

class ResearcherAgent:
    def __init__(self, kernel):
        self.kernel = kernel

    def research(self, topic: str, provider: str, model: str, api_key: str = None) -> str:
        print(f"🔍 Researching Topic: {topic}")
        
        # 1. Local RAG search (Technical Docs)
        local_context = rag_manager.query(topic)
        
        # 2. MemoryBank search (Past Successes)
        past_successes = memory_bank.query(topic)
        success_context = "\n".join(past_successes) if past_successes else "None found."
        
        # 3. Reasoning to synthesize findings
        messages = [
            {"role": "system", "content": "You are a professional AI Researcher. Synthesize the provided technical context and past successful examples into a concise brief for a Coder Agent."},
            {"role": "user", "content": f"Topic: {topic}\n\nTechnical Docs (RAG): {local_context}\n\nPast Successes (MemoryBank): {success_context}\n\nPlease provide a research brief."}
        ]
        
        brief = self.kernel.chat(provider, model, messages, api_key=api_key)
        print(f"📄 Research Brief Ready (with Memory hits).")
        return brief
