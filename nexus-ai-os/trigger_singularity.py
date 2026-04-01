import sqlite3
import sys
import os
import asyncio

sys.path.append('/workspace/ai-sandbox/nexus-ai-os')
from core.kernel import NexusKernel
from agents.self_monitor import SelfMonitorAgent, RecursiveCoderAgent
from core.hot_swap import hot_swapper

async def trigger_evolution():
    # 1. Simulate Failures (Gemini timeouts)
    conn = sqlite3.connect('/workspace/ai-sandbox/backend/usage.db')
    cursor = conn.cursor()
    for _ in range(15):
        cursor.execute("INSERT INTO usage_logs (provider, model, latency_ms, status) VALUES ('gemini', 'gemini-1.5-pro', 0, 'error: timeout')")
    conn.commit()
    conn.close()
    print("🚩 Bottleneck Simulated: 15 Gemini Timeouts added to logs.")

    # 2. Kernel Initialization
    kernel = NexusKernel()
    monitor = SelfMonitorAgent(kernel)
    coder = RecursiveCoderAgent(kernel)
    
    # 3. Analyze & Propose (Using Groq for reasoning)
    print("🧠 Analyzing system logs for evolution...")
    proposal = await monitor.analyze_performance("groq", "llama-3.3-70b-versatile")
    print(f"💡 Proposal: {proposal[:100]}...")

    # 4. Self-Upgrade (Rewrite Kernel)
    print("🛠️ Upgrading Kernel...")
    target = "/workspace/ai-sandbox/nexus-ai-os/core/kernel.py"
    success = await coder.self_upgrade_core(proposal, target, "groq", "llama-3.3-70b-versatile")

    # 5. Hot-Swap
    if success:
        hot_swapper.reload_core("kernel")
        print("🚀 EVOLUTION COMPLETE: Kernel has been hot-swapped with optimized routing logic.")
    else:
        print("⚠️ Evolution failed.")

if __name__ == "__main__":
    asyncio.run(trigger_evolution())
