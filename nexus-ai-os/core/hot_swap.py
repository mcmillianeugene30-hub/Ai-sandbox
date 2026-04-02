"""Hot-swap engine for live-reloading Nexus agent and core modules."""
import importlib
import logging
import os
import sys

from core.kernel import PROJECT_ROOT

logger = logging.getLogger(__name__)


class HotSwapEngine:
    """Reload agent or core modules at runtime without restarting the process."""

    def __init__(self, base_path: str = PROJECT_ROOT) -> None:
        self.base_path = base_path
        if self.base_path not in sys.path:
            sys.path.append(self.base_path)
        logger.info("HotSwapEngine ready (base_path=%s)", self.base_path)

    def reload_agent(self, agent_name: str) -> bool:
        """Reload a specific agent module (e.g. ``'coder'``) in-place."""
        module_path = f"agents.{agent_name}"
        if module_path in sys.modules:
            try:
                importlib.reload(sys.modules[module_path])
                logger.info("Hot-Swap: agent '%s' reloaded.", agent_name)
                return True
            except Exception as exc:
                logger.error("Hot-Swap reload failed for agent '%s': %s", agent_name, exc, exc_info=True)
                return False
        logger.warning("Hot-Swap: agent '%s' not in sys.modules — was it ever imported?", agent_name)
        return False

    def reload_core(self, core_module: str) -> bool:
        """Reload a core module (e.g. ``'kernel'``) in-place."""
        module_path = f"core.{core_module}"
        if module_path in sys.modules:
            try:
                importlib.reload(sys.modules[module_path])
                logger.info("Hot-Swap: core module '%s' reloaded.", core_module)
                return True
            except Exception as exc:
                logger.error("Hot-Swap reload failed for core '%s': %s", core_module, exc, exc_info=True)
                return False
        logger.warning("Hot-Swap: core module '%s' not in sys.modules.", core_module)
        return False


hot_swapper = HotSwapEngine()
