"""Orchestrator Agent - coordinates all specialized agents."""

import asyncio
import json
import logging
from typing import Any

from .base_agent import AgentResult, AgentTool, BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Orchestrator that coordinates specialized agents.

    The Orchestrator:
    - Receives high-level tasks from users
    - Decomposes tasks into subtasks
    - Delegates to appropriate specialized agents
    - Aggregates results and provides final response
    - Has read-only access to Vault (can verify but not modify)
    """

    def __init__(
        self,
        aws_agent: "BaseAgent | None" = None,
        vault_agent: "BaseAgent | None" = None,
        mcp_agent: "BaseAgent | None" = None,
        **kwargs: Any,
    ) -> None:
        self._aws_agent = aws_agent
        self._vault_agent = vault_agent
        self._mcp_agent = mcp_agent
        super().__init__(name="Orchestrator", **kwargs)

    @property
    def system_prompt(self) -> str:
        return """You are the Orchestrator Agent, responsible for coordinating a team of specialized agents to accomplish complex tasks.

Your specialized agents are:
1. **AWS Agent** - Handles all AWS operations (S3, EC2, Lambda, DynamoDB, etc.)
2. **Vault Agent** - Manages HashiCorp Vault operations (secrets, credentials, leases)
3. **MCP Agent** - Manages MCP server operations and tool discovery

Your responsibilities:
- Analyze incoming tasks and break them into subtasks
- Delegate subtasks to the appropriate specialized agent
- Coordinate multi-step workflows that span multiple agents
- Aggregate results and provide clear summaries
- Handle errors gracefully and retry with different approaches if needed

Guidelines:
- Always use the most specific agent for each subtask
- For AWS operations, always ensure credentials are valid via Vault Agent first
- Provide clear, actionable responses
- If a task fails, explain why and suggest alternatives
- Never expose sensitive credentials in responses

When delegating:
- Use delegate_to_aws for cloud infrastructure operations
- Use delegate_to_vault for credential and secret management
- Use delegate_to_mcp for MCP server management and tool discovery
- Use execute_workflow for multi-step operations requiring multiple agents"""

    @property
    def vault_role(self) -> str:
        return "orchestrator-role"  # Read-only, can delegate but not act directly

    def set_agents(
        self,
        aws_agent: "BaseAgent | None" = None,
        vault_agent: "BaseAgent | None" = None,
        mcp_agent: "BaseAgent | None" = None,
    ) -> None:
        """Set or update the specialized agents."""
        if aws_agent:
            self._aws_agent = aws_agent
        if vault_agent:
            self._vault_agent = vault_agent
        if mcp_agent:
            self._mcp_agent = mcp_agent

    def _register_tools(self) -> None:
        """Register orchestrator-specific tools."""

        self.register_tool(
            AgentTool(
                name="delegate_to_aws",
                description="Delegate a task to the AWS Agent for cloud operations (S3, EC2, Lambda, etc.)",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The task to delegate to AWS Agent",
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context data for the task",
                        },
                    },
                    "required": ["task"],
                },
                handler=self._delegate_to_aws,
            )
        )

        self.register_tool(
            AgentTool(
                name="delegate_to_vault",
                description="Delegate a task to the Vault Agent for credential and secret management",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The task to delegate to Vault Agent",
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context data for the task",
                        },
                    },
                    "required": ["task"],
                },
                handler=self._delegate_to_vault,
            )
        )

        self.register_tool(
            AgentTool(
                name="delegate_to_mcp",
                description="Delegate a task to the MCP Agent for MCP server management",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The task to delegate to MCP Agent",
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context data for the task",
                        },
                    },
                    "required": ["task"],
                },
                handler=self._delegate_to_mcp,
            )
        )

        self.register_tool(
            AgentTool(
                name="execute_parallel",
                description="Execute multiple independent tasks in parallel. Use when tasks don't depend on each other for maximum speed.",
                parameters={
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "description": "List of independent tasks to run simultaneously",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "agent": {
                                        "type": "string",
                                        "enum": ["aws", "vault", "mcp"],
                                    },
                                    "task": {"type": "string"},
                                },
                                "required": ["agent", "task"],
                            },
                        },
                    },
                    "required": ["tasks"],
                },
                handler=self._execute_parallel,
            )
        )

        self.register_tool(
            AgentTool(
                name="execute_workflow",
                description="Execute a workflow with dependencies. Use when some tasks depend on results of others.",
                parameters={
                    "type": "object",
                    "properties": {
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow",
                        },
                        "steps": {
                            "type": "array",
                            "description": "List of workflow steps",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "agent": {
                                        "type": "string",
                                        "enum": ["aws", "vault", "mcp"],
                                    },
                                    "task": {"type": "string"},
                                    "depends_on": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                        "description": "Indices of steps this depends on",
                                    },
                                },
                                "required": ["agent", "task"],
                            },
                        },
                    },
                    "required": ["workflow_name", "steps"],
                },
                handler=self._execute_workflow,
            )
        )

    async def _delegate_to_aws(
        self, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Delegate task to AWS Agent."""
        if not self._aws_agent:
            return {"error": "AWS Agent not configured"}

        logger.info(f"Orchestrator: delegating to AWS Agent: {task[:50]}...")
        result = await self._aws_agent.run(task, context)

        return {
            "agent": "aws",
            "success": result.success,
            "output": result.output,
            "data": result.data,
            "error": result.error,
        }

    async def _delegate_to_vault(
        self, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Delegate task to Vault Agent."""
        if not self._vault_agent:
            return {"error": "Vault Agent not configured"}

        logger.info(f"Orchestrator: delegating to Vault Agent: {task[:50]}...")
        result = await self._vault_agent.run(task, context)

        return {
            "agent": "vault",
            "success": result.success,
            "output": result.output,
            "data": result.data,
            "error": result.error,
        }

    async def _delegate_to_mcp(
        self, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Delegate task to MCP Agent."""
        if not self._mcp_agent:
            return {"error": "MCP Agent not configured"}

        logger.info(f"Orchestrator: delegating to MCP Agent: {task[:50]}...")
        result = await self._mcp_agent.run(task, context)

        return {
            "agent": "mcp",
            "success": result.success,
            "output": result.output,
            "data": result.data,
            "error": result.error,
        }

    async def _execute_parallel(
        self, tasks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Execute multiple independent tasks in parallel.

        All tasks run simultaneously using asyncio.gather().
        Use this when tasks don't depend on each other.

        Example:
        tasks = [
            {"agent": "aws", "task": "list S3 buckets"},
            {"agent": "aws", "task": "list EC2 instances"},
            {"agent": "vault", "task": "check credential status"},
        ]
        # All 3 run at the same time!
        """
        logger.info(f"Orchestrator: executing {len(tasks)} tasks in parallel")

        async def run_task(idx: int, task_def: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            agent_name = task_def["agent"]
            task = task_def["task"]

            if agent_name == "aws":
                result = await self._delegate_to_aws(task)
            elif agent_name == "vault":
                result = await self._delegate_to_vault(task)
            elif agent_name == "mcp":
                result = await self._delegate_to_mcp(task)
            else:
                result = {"error": f"Unknown agent: {agent_name}"}

            return idx, result

        # Run all tasks in parallel
        parallel_tasks = [run_task(i, t) for i, t in enumerate(tasks)]
        results_tuples = await asyncio.gather(*parallel_tasks, return_exceptions=True)

        # Process results
        results = []
        succeeded = 0
        failed = 0

        for item in results_tuples:
            if isinstance(item, Exception):
                results.append({"error": str(item)})
                failed += 1
            else:
                idx, result = item
                results.append(result)
                if result.get("success", False) or not result.get("error"):
                    succeeded += 1
                else:
                    failed += 1

        logger.info(f"Parallel execution complete: {succeeded} succeeded, {failed} failed")

        return {
            "parallel": True,
            "total_tasks": len(tasks),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "success": failed == 0,
        }

    async def _execute_workflow(
        self, workflow_name: str, steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Execute a multi-step workflow with parallel execution where possible.

        Uses a dependency graph to determine which steps can run in parallel.
        Steps with no dependencies or whose dependencies are complete run together.

        Example workflow:
        [
            {"agent": "vault", "task": "check credentials"},           # Step 0 - no deps
            {"agent": "aws", "task": "list S3", "depends_on": [0]},    # Step 1 - waits for 0
            {"agent": "aws", "task": "list EC2", "depends_on": [0]},   # Step 2 - waits for 0
            {"agent": "mcp", "task": "summarize", "depends_on": [1,2]} # Step 3 - waits for 1,2
        ]

        Execution:
        - Wave 1: Step 0 (alone, no deps)
        - Wave 2: Steps 1 & 2 (parallel, both depend only on 0)
        - Wave 3: Step 3 (waits for 1 & 2)
        """
        logger.info(f"Orchestrator: executing workflow '{workflow_name}' with {len(steps)} steps")

        results: dict[int, dict[str, Any]] = {}
        completed: set[int] = set()
        failed: set[int] = set()

        # Build dependency graph
        def get_ready_steps() -> list[int]:
            """Get steps that are ready to execute (all dependencies satisfied)."""
            ready = []
            for i, step in enumerate(steps):
                if i in completed or i in failed:
                    continue
                deps = set(step.get("depends_on", []))
                # Check if all dependencies are completed (not failed)
                if deps <= completed and not (deps & failed):
                    ready.append(i)
            return ready

        async def execute_step(step_idx: int) -> tuple[int, dict[str, Any]]:
            """Execute a single step and return (index, result)."""
            step = steps[step_idx]
            agent_name = step["agent"]
            task = step["task"]
            depends_on = step.get("depends_on", [])

            # Build context from dependencies
            context = {}
            for dep_idx in depends_on:
                if dep_idx in results:
                    context[f"step_{dep_idx}_result"] = results[dep_idx]

            logger.info(f"Workflow '{workflow_name}': executing step {step_idx} ({agent_name})")

            # Delegate to appropriate agent
            if agent_name == "aws":
                result = await self._delegate_to_aws(task, context)
            elif agent_name == "vault":
                result = await self._delegate_to_vault(task, context)
            elif agent_name == "mcp":
                result = await self._delegate_to_mcp(task, context)
            else:
                result = {"error": f"Unknown agent: {agent_name}"}

            return step_idx, result

        # Execute in waves
        wave_num = 0
        while len(completed) + len(failed) < len(steps):
            ready_steps = get_ready_steps()

            if not ready_steps:
                # No steps ready but not all complete - deadlock or all remaining have failed deps
                remaining = set(range(len(steps))) - completed - failed
                logger.error(f"Workflow '{workflow_name}': deadlock detected, remaining steps: {remaining}")
                break

            wave_num += 1
            logger.info(f"Workflow '{workflow_name}': wave {wave_num} executing steps {ready_steps}")

            # Execute ready steps in parallel
            tasks = [execute_step(idx) for idx in ready_steps]
            wave_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for item in wave_results:
                if isinstance(item, Exception):
                    logger.error(f"Step execution error: {item}")
                    continue

                step_idx, result = item
                results[step_idx] = result

                if result.get("success", False) or not result.get("error"):
                    completed.add(step_idx)
                else:
                    failed.add(step_idx)
                    logger.warning(f"Step {step_idx} failed: {result.get('error')}")

        # Build final results list in order
        ordered_results = [results.get(i, {"error": "Not executed"}) for i in range(len(steps))]

        success = len(failed) == 0 and len(completed) == len(steps)

        logger.info(
            f"Workflow '{workflow_name}' {'completed' if success else 'finished with errors'}: "
            f"{len(completed)}/{len(steps)} steps succeeded in {wave_num} waves"
        )

        return {
            "workflow": workflow_name,
            "success": success,
            "completed_steps": len(completed),
            "failed_steps": len(failed),
            "total_steps": len(steps),
            "waves_executed": wave_num,
            "results": ordered_results,
            "error": f"{len(failed)} steps failed" if failed else None,
        }
