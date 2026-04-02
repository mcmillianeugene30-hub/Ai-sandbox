"""
SwarmBus + SwarmNode — Frontier v8.0
Multi-instance Nexus collaborative intelligence.

Architecture:
  SwarmBus  — shared message broker (SQLite-backed, upgradeable to Redis)
  SwarmNode — one instance of Nexus that publishes/subscribes on the bus
  SwarmOrchestrator — distributes tasks across nodes, aggregates results
"""
import os
import json
import uuid
import asyncio
import sqlite3
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

# Import config for paths
from backend.config import SWARM_DB_PATH
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class SwarmBus:
    """Lightweight SQLite message bus. Drop-in replaceable with Redis."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(SWARM_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
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
                status TEXT DEFAULT 'pending',
                created_at REAL,
                processed_at REAL
            );
            CREATE TABLE IF NOT EXISTS swarm_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                node_id TEXT,
                result TEXT,
                confidence REAL,
                created_at REAL
            );
        """)
        conn.commit()
        conn.close()

    def register_node(self, node_id: str, name: str,
                      specialization: str, capabilities: List[str]):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""INSERT OR REPLACE INTO swarm_nodes
                        (node_id, name, status, specialization, last_heartbeat, capabilities)
                        VALUES (?,?,?,?,?,?)""",
                     (node_id, name, "idle", specialization,
                      time.time(), json.dumps(capabilities)))
        conn.commit()
        conn.close()

    def heartbeat(self, node_id: str, status: str = "idle"):
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE swarm_nodes SET last_heartbeat=?, status=? WHERE node_id=?",
                     (time.time(), status, node_id))
        conn.commit()
        conn.close()

    def publish(self, from_node: str, to_node: Optional[str],
                msg_type: str, payload: dict) -> str:
        msg_id = str(uuid.uuid4())[:8]
        conn = sqlite3.connect(self.db_path)
        conn.execute("""INSERT INTO swarm_messages
                        (msg_id, from_node, to_node, msg_type, payload, created_at)
                        VALUES (?,?,?,?,?,?)""",
                     (msg_id, from_node, to_node, msg_type,
                      json.dumps(payload), time.time()))
        conn.commit()
        conn.close()
        return msg_id

    def consume(self, node_id: str, msg_type: str = None) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        query = """SELECT id, msg_id, from_node, msg_type, payload FROM swarm_messages
                   WHERE status='pending' AND (to_node=? OR to_node IS NULL)"""
        params = [node_id]
        if msg_type:
            query += " AND msg_type=?"
            params.append(msg_type)
        rows = conn.execute(query, params).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            conn.execute(f"UPDATE swarm_messages SET status='processed', processed_at=? WHERE id IN ({','.join('?'*len(ids))})",
                         [time.time()] + ids)
        conn.commit()
        conn.close()
        return [{"id": r[0], "msg_id": r[1], "from": r[2],
                 "type": r[3], "payload": json.loads(r[4])} for r in rows]

    def store_result(self, task_id: str, node_id: str,
                     result: Any, confidence: float = 0.8):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""INSERT INTO swarm_results
                        (task_id, node_id, result, confidence, created_at)
                        VALUES (?,?,?,?,?)""",
                     (task_id, node_id, json.dumps(result),
                      confidence, time.time()))
        conn.commit()
        conn.close()

    def get_results(self, task_id: str) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""SELECT node_id, result, confidence FROM swarm_results
                               WHERE task_id=? ORDER BY confidence DESC""",
                            (task_id,)).fetchall()
        conn.close()
        return [{"node": r[0], "result": json.loads(r[1]), "confidence": r[2]} for r in rows]

    def get_live_nodes(self, timeout_secs: int = 60) -> List[dict]:
        cutoff = time.time() - timeout_secs
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""SELECT node_id, name, status, specialization, capabilities
                               FROM swarm_nodes WHERE last_heartbeat > ?""",
                            (cutoff,)).fetchall()
        conn.close()
        return [{"node_id": r[0], "name": r[1], "status": r[2],
                 "spec": r[3], "caps": json.loads(r[4])} for r in rows]


class SwarmNode:
    """A single Nexus instance that participates in the swarm."""

    def __init__(self, kernel, bus: SwarmBus,
                 name: str, specialization: str,
                 capabilities: List[str] = None):
        self.kernel = kernel
        self.bus = bus
        self.node_id = str(uuid.uuid4())[:8]
        self.name = name
        self.spec = specialization
        self.caps = capabilities or ["chat", "code", "research"]
        self.bus.register_node(self.node_id, name, specialization, self.caps)
        logger.info(f"SwarmNode [{self.name}] online — ID: {self.node_id}")

    async def process_task(self, task: dict) -> dict:
        """Execute a task using this node's kernel."""
        self.bus.heartbeat(self.node_id, "working")
        prompt = task.get("prompt", "")
        context = task.get("context", "")
        full_prompt = f"{context}\n\nTask: {prompt}" if context else prompt

        messages = [
            {"role": "system", "content": f"You are a specialized AI node ({self.spec}). Be precise and thorough."},
            {"role": "user", "content": full_prompt}
        ]
        try:
            result = await self.kernel.chat_async(
                "groq", "llama-3.3-70b-versatile", messages
            )
            self.bus.heartbeat(self.node_id, "idle")
            return {"status": "ok", "result": result, "node": self.name}
        except Exception as e:
            self.bus.heartbeat(self.node_id, "error")
            logger.error(f"SwarmNode {self.name} error: {e}")
            return {"status": "error", "error": str(e), "node": self.name}

    async def listen_and_work(self, iterations: int = 5) -> List[dict]:
        """Poll the bus and execute any pending tasks."""
        results = []
        for _ in range(iterations):
            messages = self.bus.consume(self.node_id, msg_type="TASK")
            for msg in messages:
                task_id = msg["payload"].get("task_id", msg["msg_id"])
                result = await self.process_task(msg["payload"])
                self.bus.store_result(task_id, self.node_id, result, 0.85)
                self.bus.publish(self.node_id, msg["from"], "RESULT",
                                 {"task_id": task_id, "result": result})
                results.append(result)
            self.bus.heartbeat(self.node_id)
            await asyncio.sleep(2)
        return results


class SwarmOrchestrator:
    """Distributes a complex goal across multiple SwarmNodes and aggregates."""

    def __init__(self, kernel, bus: SwarmBus):
        self.kernel = kernel
        self.bus = bus

    def _split_goal(self, goal: str, num_nodes: int) -> List[dict]:
        """Naively split goal into sub-tasks; use AI for smarter splitting."""
        return [{"id": i, "prompt": f"Sub-task {i+1} of {num_nodes}: {goal}",
                 "focus": f"Part {i+1}"} for i in range(num_nodes)]

    async def ai_split(self, goal: str, num_nodes: int) -> List[dict]:
        """Use the kernel to intelligently decompose a goal for the swarm."""
        prompt = f"""You are the Nexus Swarm Orchestrator. Split this goal into {num_nodes} independent parallel sub-tasks for {num_nodes} AI nodes.
Goal: {goal}
Each node has specializations: research, coding, analysis, review, documentation.
Return JSON array: [{{"node_spec":"...", "prompt":"...", "context":"..."}}]"""
        try:
            resp = await self.kernel.chat_async(
                "groq", "llama-3.3-70b-versatile",
                [{"role": "user", "content": prompt}]
            )
            if "```json" in resp:
                resp = resp.split("```json")[1].split("```")[0]
            elif "[" in resp:
                resp = resp[resp.find("["):resp.rfind("]")+1]
            tasks = json.loads(resp)
            for i, t in enumerate(tasks):
                t["task_id"] = str(uuid.uuid4())[:8]
            return tasks
        except Exception as e:
            logger.error(f"AI split error: {e}")
            return self._split_goal(goal, num_nodes)

    async def aggregate_results(self, task_id: str, results: List[dict]) -> str:
        """Synthesize multiple node results into one consensus answer."""
        if not results:
            return "No results received."
        if len(results) == 1:
            return results[0].get("result", {}).get("result", "")

        combined = "\n\n".join([
            f"--- Node {r['node']} ---\n{r.get('result', {}).get('result', '')}"
            for r in results if r.get("status") == "ok"
        ])
        
        prompt = f"""You are the Swarm Consensus Engine. Multiple AI nodes worked on the same goal.
Synthesize their outputs into one final, comprehensive answer:

{combined}

Produce a single unified response."""
        
        try:
            return await self.kernel.chat_async(
                "groq", "llama-3.3-70b-versatile",
                [{"role": "user", "content": prompt}]
            )
        except Exception as e:
            logger.error(f"Aggregate error: {e}")
            return combined

    async def run_swarm(self, goal: str, nodes: List[SwarmNode],
                        log_fn=None) -> dict:
        """Full swarm execution: split → distribute → gather → aggregate."""
        def log(msg):
            logger.info(msg)
            if log_fn:
                log_fn(msg)

        log(f"🐝 SwarmOrchestrator: Activating {len(nodes)} nodes for goal:")
        log(f"   '{goal[:80]}...'")

        log("🧩 Decomposing goal into parallel sub-tasks...")
        sub_tasks = await self.ai_split(goal, len(nodes))
        log(f"   Created {len(sub_tasks)} sub-tasks")

        task_map = {}
        for i, (node, sub) in enumerate(zip(nodes, sub_tasks)):
            task_id = sub.get("task_id", str(uuid.uuid4())[:8])
            self.bus.publish("orchestrator", node.node_id, "TASK",
                             {"task_id": task_id, "prompt": sub["prompt"],
                              "context": sub.get("context", "")})
            task_map[task_id] = node.name
            log(f"   📤 Task {task_id} → Node [{node.name}]")

        log("⚡ All nodes executing in parallel...")
        node_results = await asyncio.gather(*[n.listen_and_work(3) for n in nodes])

        all_results = [r for nr in node_results for r in nr]
        log(f"   Collected {len(all_results)} results from swarm")

        log("🧠 Synthesizing consensus from all nodes...")
        consensus = await self.aggregate_results("swarm", all_results)

        live = self.bus.get_live_nodes()
        log(f"✅ Swarm complete. {len(live)} nodes still live.")

        return {
            "goal": goal,
            "nodes_used": len(nodes),
            "sub_tasks": len(sub_tasks),
            "raw_results": all_results,
            "consensus": consensus
        }
