"""
NexusKernel — Production Async Routing Engine
Provides unified chat_async() and hive_poll() interfaces for all agents.

Environment:
    NEXUS_OS_PATH   — root of the nexus-ai-os package (auto-detected)
    RENDER_DISK_PATH — persistent storage mount; falls back to ./data
"""
import os
import sys
import logging

# ─── Path bootstrap (must run before any local imports) ───────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("NEXUS_OS_PATH", PROJECT_ROOT)

# Persistent storage root (Render disk or local fallback)
RENDER_DISK_PATH: str = os.environ.get(
    "RENDER_DISK_PATH",
    os.path.join(PROJECT_ROOT, "data"),
)

logger = logging.getLogger(__name__)


class NexusKernel:
    """
    Central async routing kernel for Nexus AI OS.

    Responsibilities:
    - Route chat completions to the correct AI provider via backend.providers.
    - Fan-out hive polls across multiple providers and collect results.
    - Expose a consistent interface so every agent is provider-agnostic.
    """

    def __init__(self) -> None:
        """Initialise the kernel; no I/O performed at construction time."""
        logger.info("NexusKernel initialised (PROJECT_ROOT=%s)", PROJECT_ROOT)

    # ──────────────────────────────────────────────────────────────────────────
    # Public async API
    # ──────────────────────────────────────────────────────────────────────────

    async def chat_async(
        self,
        provider: str,
        model: str,
        messages: list,
        api_key: str = None,
    ) -> str:
        """
        Send *messages* to *model* on *provider* and return the assistant text.

        Args:
            provider:  Provider slug, e.g. ``"groq"``, ``"google"``, ``"openrouter"``, ``"ollama"``.
            model:     Model identifier understood by the provider.
            messages:  OpenAI-style list of ``{"role": ..., "content": ...}`` dicts.
            api_key:   Optional override; falls back to ``{PROVIDER}_API_KEY`` env var.

        Returns:
            The assistant message content as a string.

        Raises:
            ValueError: If no API key is available for a key-gated provider.
            RuntimeError: If the provider is unknown or the call fails.
        """
        try:
            from backend.providers import get_provider  # local import — avoids circular deps at boot

            resolved_key = api_key or os.environ.get(f"{provider.upper()}_API_KEY")
            if not resolved_key and provider != "ollama":
                raise ValueError(
                    f"No API key for provider '{provider}'. "
                    f"Set {provider.upper()}_API_KEY in the environment."
                )

            ai_provider = get_provider(provider)
            if ai_provider is None:
                raise RuntimeError(f"Unknown provider: '{provider}'")

            response = ai_provider.chat_complete(model, messages, resolved_key)
            content: str = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            logger.debug("chat_async OK provider=%s model=%s chars=%d", provider, model, len(content))
            return content

        except (ValueError, RuntimeError):
            raise
        except Exception as exc:
            logger.error("chat_async failed provider=%s model=%s error=%s", provider, model, exc, exc_info=True)
            raise RuntimeError(f"chat_async failed for {provider}/{model}: {exc}") from exc

    async def hive_poll(self, providers: list, messages: list) -> list:
        """
        Fan-out the same *messages* to every entry in *providers* and collect results.

        Args:
            providers: List of provider config dicts, each containing at least::

                    {"provider": "groq", "model": "llama-3.3-70b-versatile"}

            messages:  OpenAI-style message list forwarded to every provider.

        Returns:
            List of result dicts::

                {"provider": str, "model": str, "content": str}

            Failed providers are logged and silently omitted from the result list.
        """
        import asyncio

        async def _call_one(prov_config: dict) -> dict | None:
            provider_name = prov_config.get("provider", "")
            model = prov_config.get("model", "llama-3.3-70b-versatile")
            try:
                content = await self.chat_async(provider_name, model, messages)
                return {"provider": provider_name, "model": model, "content": content}
            except Exception as exc:
                logger.warning(
                    "hive_poll: provider=%s model=%s skipped error=%s",
                    provider_name, model, exc,
                )
                return None

        raw = await asyncio.gather(*[_call_one(p) for p in providers])
        results = [r for r in raw if r is not None]
        logger.info("hive_poll: %d/%d providers responded", len(results), len(providers))
        return results


# Module-level singleton — all agents import this directly
kernel = NexusKernel()
