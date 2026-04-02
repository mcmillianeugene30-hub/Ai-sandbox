"""
HotSwapEngine — Runtime module reloading for Nexus AI-OS.
Enables dynamic code updates without restart.
"""
import importlib
import sys
from pathlib import Path
from typing import Optional

from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Calculate base path from this file location
BASE_PATH = Path(__file__).parent.parent.resolve()


class HotSwapEngine:
    """Engine for hot-swapping modules at runtime."""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path) if base_path else BASE_PATH
        self._ensure_in_path()
    
    def _ensure_in_path(self):
        """Ensure the base path is in sys.path for imports."""
        str_path = str(self.base_path)
        if str_path not in sys.path:
            sys.path.insert(0, str_path)
            logger.debug(f"Added {str_path} to sys.path")

    def reload_agent(self, agent_name: str) -> bool:
        """Reload a specific agent module (e.g., 'agents.coder') on the fly."""
        module_path = f"nexus_ai_os.agents.{agent_name}"
        if module_path in sys.modules:
            try:
                importlib.reload(sys.modules[module_path])
                logger.info(f"Hot-Swap: Agent '{agent_name}' reloaded with new code.")
                return True
            except Exception as e:
                logger.error(f"Hot-Swap: Failed to reload agent '{agent_name}': {e}")
                return False
        logger.warning(f"Hot-Swap: Agent '{agent_name}' not found in sys.modules")
        return False

    def reload_core(self, core_module: str) -> bool:
        """Reload a core kernel module (e.g., 'nexus_ai_os.core.kernel')."""
        module_path = f"nexus_ai_os.core.{core_module}"
        if module_path in sys.modules:
            try:
                importlib.reload(sys.modules[module_path])
                logger.info(f"Hot-Swap: Core module '{core_module}' reloaded.")
                return True
            except Exception as e:
                logger.error(f"Hot-Swap: Failed to reload core '{core_module}': {e}")
                return False
        logger.warning(f"Hot-Swap: Core module '{core_module}' not found in sys.modules")
        return False
    
    def reload_tool(self, tool_name: str) -> bool:
        """Reload a tool module (e.g., 'tools.fs_tool') on the fly."""
        module_path = f"nexus_ai_os.tools.{tool_name}"
        if module_path in sys.modules:
            try:
                importlib.reload(sys.modules[module_path])
                logger.info(f"Hot-Swap: Tool '{tool_name}' reloaded with new code.")
                return True
            except Exception as e:
                logger.error(f"Hot-Swap: Failed to reload tool '{tool_name}': {e}")
                return False
        logger.warning(f"Hot-Swap: Tool '{tool_name}' not found in sys.modules")
        return False


# Global hot swapper instance
hot_swapper = HotSwapEngine()
