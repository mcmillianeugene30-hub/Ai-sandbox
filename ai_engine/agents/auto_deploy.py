"""Render deployment agent for triggering, monitoring, and validating deployments."""
import asyncio
import logging
import os
import time
from typing import Dict, Optional

import httpx

from core.kernel import NexusKernel

logger = logging.getLogger(__name__)

RENDER_API = "https://api.render.com/v1"


class AutoDeployAgent:
    """Automate Render deploy lifecycle management for Nexus services."""

    def __init__(self, kernel: NexusKernel):
        self.kernel = kernel
        self.render_api_key = os.environ.get("RENDER_API_KEY", "")
        self.service_id = os.environ.get("RENDER_SERVICE_ID", "")
        self.headers = {
            "Authorization": f"Bearer {self.render_api_key}",
            "Accept": "application/json",
        }

    async def trigger_deploy(self, clear_cache: bool = False) -> Dict[str, str]:
        """Trigger a new Render deploy and return its identifier."""
        if not self.render_api_key or not self.service_id:
            return {"status": "skipped", "reason": "RENDER_API_KEY or RENDER_SERVICE_ID not set"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{RENDER_API}/services/{self.service_id}/deploys",
                    headers=self.headers,
                    json={"clearCache": "clear" if clear_cache else "do_not_clear"},
                )
            if resp.status_code in (200, 201):
                deploy_id = resp.json().get("id", "unknown")
                logger.info("Render deploy triggered id=%s", deploy_id)
                return {"status": "triggered", "deploy_id": deploy_id}
            logger.error("trigger_deploy failed status=%s body=%s", resp.status_code, resp.text)
            return {"status": "error", "detail": resp.text}
        except Exception as exc:
            logger.error("trigger_deploy exception: %s", exc, exc_info=True)
            return {"status": "error", "detail": str(exc)}

    async def poll_deploy(self, deploy_id: str, timeout: int = 300) -> Dict[str, str]:
        """Poll Render until the deploy reaches a terminal state or timeout expires."""
        start = time.time()
        try:
            while time.time() - start < timeout:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        f"{RENDER_API}/services/{self.service_id}/deploys/{deploy_id}",
                        headers=self.headers,
                    )
                if resp.status_code == 200:
                    deploy = resp.json()
                    status = deploy.get("status", "unknown")
                    logger.info("poll_deploy id=%s status=%s", deploy_id, status)
                    if status in {"live", "build_failed", "update_failed", "canceled"}:
                        return {"status": status, "deploy_id": deploy_id}
                else:
                    logger.error("poll_deploy failed status=%s body=%s", resp.status_code, resp.text)
                    return {"status": "error", "detail": resp.text}
                await asyncio.sleep(10)
            return {"status": "timeout", "deploy_id": deploy_id}
        except Exception as exc:
            logger.error("poll_deploy exception: %s", exc, exc_info=True)
            return {"status": "error", "detail": str(exc), "deploy_id": deploy_id}

    async def health_check(self, health_url: str, retries: int = 5) -> Dict[str, str]:
        """Perform repeated health checks against the deployed service URL."""
        try:
            for attempt in range(1, retries + 1):
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(health_url)
                if resp.status_code == 200:
                    logger.info("health_check passed url=%s attempt=%d", health_url, attempt)
                    return {"status": "healthy", "url": health_url}
                logger.warning("health_check non-200 url=%s status=%s attempt=%d", health_url, resp.status_code, attempt)
                await asyncio.sleep(5)
            return {"status": "unhealthy", "url": health_url}
        except Exception as exc:
            logger.error("health_check exception url=%s error=%s", health_url, exc, exc_info=True)
            return {"status": "error", "url": health_url, "detail": str(exc)}
