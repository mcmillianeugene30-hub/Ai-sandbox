import importlib
import sys
import os

class HotSwapEngine:
    def __init__(self, base_path="/workspace/ai-sandbox/nexus-ai-os"):
        self.base_path = base_path
        if self.base_path not in sys.path:
            sys.path.append(self.base_path)

    def reload_agent(self, agent_name: str):
        """Reload a specific agent module (e.g., 'agents.coder') on the fly."""
        module_path = f"agents.{agent_name}"
        if module_path in sys.modules:
            importlib.reload(sys.modules[module_path])
            print(f"🔄 Hot-Swap: Agent '{agent_name}' reloaded with new code.")
            return True
        return False

    def reload_core(self, core_module: str):
        """Reload a core kernel module (e.g., 'core.kernel')."""
        module_path = f"core.{core_module}"
        if module_path in sys.modules:
            importlib.reload(sys.modules[module_path])
            print(f"🚀 Hot-Swap: Core module '{core_module}' reloaded.")
            return True
        return False

hot_swapper = HotSwapEngine()
