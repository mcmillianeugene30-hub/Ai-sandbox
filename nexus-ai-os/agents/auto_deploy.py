"""
AutoDeployAgent — Frontier v8.0
Autonomous cloud deployment via Render API.
Handles: trigger deploy → poll status → health check → auto-rollback.
"""
import os
import time
import httpx
import asyncio
from typing import Optional

RENDER_API = "https://api.render.com/v1"

class AutoDeployAgent:
    def __init__(self, kernel):
        self.kernel = kernel
        self.render_api_key = os.environ.get("RENDER_API_KEY", "")
        self.service_id     = os.environ.get("RENDER_SERVICE_ID", "")  # srv-xxxx
        self.headers        = {"Authorization": f"Bearer {self.render_api_key}",
                               "Accept": "application/json"}

    # ── 1. Trigger a new deploy ───────────────────────────────────────────────
    async def trigger_deploy(self, clear_cache: bool = False) -> dict:
        if not self.render_api_key or not self.service_id:
            return {"status": "skipped", "reason": "RENDER_API_KEY or RENDER_SERVICE_ID not set"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{RENDER_API}/services/{self.service_id}/deploys",
                headers=self.headers,
                json={"clearCache": "clear" if clear_cache else "do_not_clear"}
            )
        if resp.status_code in (200, 201):
            data = resp.json()
            deploy_id = data.get("id", "unknown")
            print(f"🚀 AutoDeploy: Deploy triggered. ID={deploy_id}")
            return {"status": "triggered", "deploy_id": deploy_id}
        return {"status": "error", "detail": resp.text}

    # ── 2. Poll deploy status until done ─────────────────────────────────────
    async def poll_deploy(self, deploy_id: str, timeout: int = 300) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{RENDER_API}/services/{self.service_id}/deploys/{deploy_id}",
                    headers=self.headers
                )
            if resp.status_code == 200:
                state = resp.json().get("status", "unknown")
                print(f"   ↳ Deploy status: {state}")
                if state in ("live", "deactivated"):
                    return {"status": state, "deploy_id": deploy_id}
                if state in ("build_failed", "update_failed", "canceled"):
                    return {"status": "failed", "state": state, "deploy_id": deploy_id}
            await asyncio.sleep(10)
        return {"status": "timeout", "deploy_id": deploy_id}

    # ── 3. Health check the live URL ─────────────────────────────────────────
    async def health_check(self, url: str, retries: int = 5) -> bool:
        for i in range(retries):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(f"{url}/health")
                if resp.status_code == 200:
                    print(f"✅ Health check passed: {url}/health")
                    return True
            except Exception:
                pass
            print(f"   ↳ Health check attempt {i+1}/{retries} failed. Retrying...")
            await asyncio.sleep(15)
        return False

    # ── 4. Rollback to previous deploy ───────────────────────────────────────
    async def rollback(self) -> dict:
        # Get list of deploys, activate the previous live one
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{RENDER_API}/services/{self.service_id}/deploys?limit=5",
                headers=self.headers
            )
        if resp.status_code != 200:
            return {"status": "rollback_error", "detail": resp.text}

        deploys = resp.json()
        # Find last "live" deploy that isn't current
        prev = next((d for d in deploys if d.get("status") == "live"), None)
        if not prev:
            return {"status": "no_rollback_target"}

        prev_id = prev["id"]
        async with httpx.AsyncClient() as client:
            rb = await client.post(
                f"{RENDER_API}/services/{self.service_id}/deploys/{prev_id}/rollback",
                headers=self.headers
            )
        print(f"⏪ Rollback to {prev_id}: {rb.status_code}")
        return {"status": "rolled_back", "deploy_id": prev_id}

    # ── 5. Full autonomous deploy pipeline ───────────────────────────────────
    async def full_deploy_pipeline(self, service_url: str, log_fn=None) -> dict:
        def log(msg): 
            print(msg)
            if log_fn: log_fn(msg)

        log("🔧 AutoDeployAgent: Starting full deploy pipeline...")

        # Step 1: Trigger
        trigger = await self.trigger_deploy()
        if trigger["status"] != "triggered":
            log(f"❌ Deploy trigger failed: {trigger}")
            return trigger
        deploy_id = trigger["deploy_id"]
        log(f"✅ Deploy triggered — ID: {deploy_id}")

        # Step 2: Poll
        log("⏳ Polling deploy status (up to 5 minutes)...")
        result = await self.poll_deploy(deploy_id)
        log(f"   Deploy result: {result['status']}")

        # Step 3: Health check or rollback
        if result["status"] == "live":
            log(f"🩺 Running health check on {service_url}...")
            healthy = await self.health_check(service_url)
            if healthy:
                log("🎉 Deployment successful and healthy!")
                return {"status": "success", "deploy_id": deploy_id, "url": service_url}
            else:
                log("⚠️ Health check failed — initiating rollback...")
                rb = await self.rollback()
                log(f"⏪ Rollback result: {rb}")
                return {"status": "rolled_back", "reason": "health_check_failed"}
        else:
            log(f"❌ Deploy failed ({result['status']}) — initiating rollback...")
            rb = await self.rollback()
            return {"status": "rolled_back", "reason": result["status"]}
