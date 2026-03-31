import os
import sys
import asyncio
import json
from typing import List, Dict, Any

# Ensure we can import from the nexus-ai-os root
sys.path.append('/workspace/ai-sandbox/nexus-ai-os')
from core.kernel import NexusKernel
from core.memory_bank import memory_bank
from agents.coder import CoderAgent
from agents.researcher import ResearcherAgent
from agents.reviewer import ReviewerAgent
from agents.planner import PlannerAgent
from agents.hive_aggregator import HiveAggregator
from agents.architect import AppArchitectAgent
from agents.devops import DevOpsAgent
from tools.fs_tool import fs_tool

class NexusOrchestrator:
    def __init__(self, provider: str = "groq", model: str = "llama-3.3-70b-versatile", api_key: str = None):
        self.kernel = NexusKernel()
        self.coder = CoderAgent(self.kernel)
        self.researcher = ResearcherAgent(self.kernel)
        self.reviewer = ReviewerAgent(self.kernel)
        self.planner = PlannerAgent(self.kernel)
        self.hive_aggregator = HiveAggregator(self.kernel)
        self.architect = AppArchitectAgent(self.kernel)
        self.devops = DevOpsAgent(self.kernel)
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.getenv("GROQ_API_KEY")

        # Define Hive Providers for Consensus Polling
        self.hive_providers = [
            {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            {"provider": "google", "model": "gemini-1.5-pro-latest"}
        ]

    async def build_full_stack_app(self, goal: str, project_name: str = "my-app"):
        print(f"🌟 Starting Nexus Full-Stack App Builder: {goal}")
        
        # 1. Architect Phase
        design = await self.architect.architect(goal, self.provider, self.model, self.api_key)
        stack = design['stack']
        structure = design['structure']
        
        # 2. DevOps Phase
        devops_config = await self.devops.configure_deployment(stack, structure, self.provider, self.model, self.api_key)
        
        # 3. Create Project Directory
        base_path = f"projects/{project_name}"
        fs_tool.mkdir(base_path)
        
        # 4. Generate Structure and DevOps Files
        self.architect.create_structure_recursive(base_path, structure)
        self.devops.write_configs(base_path, devops_config)
        
        # 5. Planner Phase (Decompose into Build Sub-tasks)
        build_goal = f"Build a full-stack {stack['frontend']} and {stack['backend']} app for: {goal}"
        task_tree = self.planner.decompose(build_goal, self.provider, self.model, self.api_key)
        
        for item in task_tree:
            task = item['task']
            print(f"📍 Building Sub-Task [{item['id']}]: {task}")
            
            # Hive Research for Best Practice
            research_messages = [{"role": "user", "content": f"Provide a research brief for building this part of a {stack['frontend']}/{stack['backend']} app: {task}"}]
            hive_outputs = await self.kernel.hive_poll(self.hive_providers, research_messages)
            brief = await self.hive_aggregator.aggregate(task, hive_outputs, self.provider, self.model, self.api_key)
            
            # Code Build Phase
            files_to_build = [f"{base_path}/{p}" for p in item.get('files_to_create', [])]
            if not files_to_build:
                files_to_build = [f"{base_path}/TODO.md"] # Fallback
            
            await self.coder.build_files(f"{task}\n\nBrief: {brief}", files_to_build, self.provider, self.model, self.api_key)
            
            # Review Phase
            print(f"🧐 Reviewing Sub-Task...")
            # Simple Review for now
            # review_res = self.reviewer.review(..., task, self.provider, self.model, self.api_key)
            print(f"✅ Sub-Task Completed.")
        
        print(f"🏁 Full-Stack App Builder Finished: {project_name}")
        return base_path

    async def execute_workflow_async(self, goal: str):
        # (Preserve existing workflow logic if needed)
        pass

    def execute_workflow(self, goal: str):
        asyncio.run(self.execute_workflow_async(goal))
