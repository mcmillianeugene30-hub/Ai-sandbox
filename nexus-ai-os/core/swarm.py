"""
Swarm bus and orchestration primitives for Nexus AI OS.
Provides SQLite-backed inter-node messaging with persistent storage rooted on RENDER_DISK_PATH.
"""
import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.kernel import RENDER_DISK_PATH

logger = logging.getLogger(__name__)

SWARM_DB = os.path.join(RENDER_DISK_PATH, "memory_db", "swarm.db")


class SwarmBus:
    """Lightweight SQLite-backed message bus for inter-node coordination."""

    def __init__(self, db_path: str = SWARM_DB):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        """Create a SQLite connection configured for concurrent access."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self) -> None:
        """Create required swarm tables if they do not exist yet."""
        try:
            with self._connect() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS swarm_nodes (
                        node_id TEXT PRIMARY KEY,
                        name TEXT,
                        status TEXT DEFAULT 'idle',
                        specialization TEXT,
                        last_heartbeat REAL,
                        capabilities TEXT
                    );
                    CREATE TABLE IF NOT EXISTS swarm_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        msg_id TEXT UNIQUE,
                        from_node TEXT,
                        to_node TEXT,
                        msg_type TEXT,
                        payload TEXT,
                        created_at REAL,
                        consumed INTEGER DEFAULT 0
                    );
                    """
                )
            logger.info("SwarmBus initialised at %s", self.db_path)
        except Exception as exc:
            logger.error("SwarmBus initialisation failed: %s", exc, exc_info=True)
            raise

    def register_node(self, node_id: str, name: str, specialization: str, capabilities: List[str]) -> None:
        """Register or refresh a swarm node in the shared registry."""
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO swarm_nodes (node_id, name, status, specialization, last_heartbeat, capabilities)
                    VALUES (?, ?, 'idle', ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        name=excluded.name,
                        specialization=excluded.specialization,
                        last_heartbeat=excluded.last_heartbeat,
                        capabilities=excluded.capabilities
                    """,
                    (node_id, name, specialization, time.time(), json.dumps(capabilities)),
                )
            logger.debug("Swarm node registered node_id=%s", node_id)
        except Exception as exc:
            logger.error("register_node failed node_id=%s error=%s", node_id, exc, exc_info=True)
            raise

    def heartbeat(self, node_id: str, status: str = "idle") -> None:
        """Update heartbeat and status for a swarm node."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE swarm_nodes SET last_heartbeat=?, status=? WHERE node_id=?",
                    (time.time(), status, node_id),
                )
        except Exception as exc:
            logger.error("heartbeat failed node_id=%s error=%s", node_id, exc, exc_info=True)
            raise

    def publish(self, from_node: str, msg_type: str, payload: Dict[str, Any], to_node: Optional[str] = None) -> str:
        """Publish a directed or broadcast message to the swarm bus."""
        msg_id = str(uuid.uuid4())
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO swarm_messages (msg_id, from_node, to_node, msg_type, payload, created_at, consumed)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                    """,
                    (msg_id, from_node, to_node, msg_type, json.dumps(payload), time.time()),
                )
            logger.debug("Swarm message published msg_id=%s type=%s", msg_id, msg_type)
            return msg_id
        except Exception as exc:
            logger.error("publish failed from_node=%s type=%s error=%s", from_node, msg_type, exc, exc_info=True)
            raise

    def consume(self, node_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Consume pending directed and broadcast messages for a node."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM swarm_messages
                    WHERE consumed = 0 AND (to_node = ? OR to_node IS NULL)
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (node_id, limit),
                ).fetchall()
                message_ids = [row["id"] for row in rows]
                if message_ids:
                    conn.executemany(
                        "UPDATE swarm_messages SET consumed = 1 WHERE id = ?",
                        [(message_id,) for message_id in message_ids],
                    )

            messages = [
                {
                    "msg_id": row["msg_id"],
                    "from_node": row["from_node"],
                    "to_node": row["to_node"],
                    "msg_type": row["msg_type"],
                    "payload": json.loads(row["payload"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
            return messages
        except Exception as exc:
            logger.error("consume failed node_id=%s error=%s", node_id, exc, exc_info=True)
            return []


class SwarmNode:
    """Single Nexus node that communicates through a shared SwarmBus."""

    def __init__(self, bus: SwarmBus, name: str, specialization: str, capabilities: Optional[List[str]] = None):
        self.bus = bus
        self.node_id = str(uuid.uuid4())
        self.name = name
        self.specialization = specialization
        self.capabilities = capabilities or []
        self.bus.register_node(self.node_id, self.name, self.specialization, self.capabilities)

    async def start_heartbeat(self, interval: int = 15) -> None:
        """Continuously update the node heartbeat until the task is cancelled."""
        while True:
            try:
                self.bus.heartbeat(self.node_id, status="active")
            except Exception:
                logger.exception("start_heartbeat failed for node_id=%s", self.node_id)
            await asyncio.sleep(interval)

    async def poll_messages(self, interval: int = 5) -> List[Dict[str, Any]]:
        """Poll the swarm bus once after an optional wait interval."""
        await asyncio.sleep(interval)
        return self.bus.consume(self.node_id)


class SwarmOrchestrator:
    """High-level coordinator for dispatching work to swarm nodes and aggregating responses."""

    def __init__(self, bus: SwarmBus):
        self.bus = bus

    def dispatch_task(self, from_node: str, task: Dict[str, Any], to_node: Optional[str] = None) -> str:
        """Dispatch a task payload into the swarm."""
        return self.bus.publish(from_node=from_node, to_node=to_node, msg_type="task", payload=task)

    def publish_result(self, from_node: str, result: Dict[str, Any], to_node: Optional[str] = None) -> str:
        """Publish a result payload into the swarm."""
        return self.bus.publish(from_node=from_node, to_node=to_node, msg_type="result", payload=result)

    def collect_results(self, node_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Collect result messages that are available for the given node."""
        messages = self.bus.consume(node_id=node_id, limit=limit)
        return [message for message in messages if message.get("msg_type") == "result"]
