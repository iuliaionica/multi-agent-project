"""Agent System - Main entry point for the multi-agent system."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from .orchestrator import OrchestratorAgent
from .aws_agent import AWSAgent
from .vault_agent import VaultAgent
from .mcp_agent import MCPAgent
from .github_agent import GitHubAgent
from .base_agent import AgentResult

logger = logging.getLogger(__name__)


@dataclass
class AgentSystemConfig:
    """Configuration for the agent system."""

    anthropic_api_key: str | None = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096


class MCPClientWrapper:
    """Wrapper for MCP client to standardize tool calls."""

    def __init__(self, mcp_server: Any = None) -> None:
        self._server = mcp_server

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool."""
        if not self._server:
            raise RuntimeError("MCP server not initialized")

        # In a real implementation, this would call the MCP server
        # For now, we'll import and use the tools directly
        from ..tools import S3Tools, EC2Tools, GenericAWSTools
        from ..services import VaultClient, AWSSessionManager

        # This would be connected to the actual MCP server
        # For demonstration, showing the interface
        raise NotImplementedError(
            "Connect this to your MCP server instance. "
            "See agent_system.create_with_mcp_server() for integration."
        )


class AgentSystem:
    """Multi-agent system with Orchestrator coordinating specialized agents.

    Usage:
        # Create the agent system
        system = AgentSystem.create()

        # Run a task
        result = await system.run("List all S3 buckets and check EC2 instances")

        # Or use specific agents directly
        aws_result = await system.aws_agent.run("List S3 buckets")
    """

    def __init__(
        self,
        orchestrator: OrchestratorAgent,
        aws_agent: AWSAgent,
        vault_agent: VaultAgent,
        mcp_agent: MCPAgent,
        github_agent: GitHubAgent,
    ) -> None:
        self.orchestrator = orchestrator
        self.aws_agent = aws_agent
        self.vault_agent = vault_agent
        self.mcp_agent = mcp_agent
        self.github_agent = github_agent

    @classmethod
    def create(
        cls,
        config: AgentSystemConfig | None = None,
        mcp_client: Any = None,
    ) -> "AgentSystem":
        """Create a new agent system.

        Args:
            config: System configuration
            mcp_client: Optional MCP client for AWS operations

        Returns:
            Configured AgentSystem instance
        """
        config = config or AgentSystemConfig()

        # Create specialized agents
        aws_agent = AWSAgent(
            mcp_client=mcp_client,
            model=config.model,
            max_tokens=config.max_tokens,
            api_key=config.anthropic_api_key,
        )

        vault_agent = VaultAgent(
            mcp_client=mcp_client,
            model=config.model,
            max_tokens=config.max_tokens,
            api_key=config.anthropic_api_key,
        )

        mcp_agent = MCPAgent(
            mcp_client=mcp_client,
            model=config.model,
            max_tokens=config.max_tokens,
            api_key=config.anthropic_api_key,
        )

        github_agent = GitHubAgent(
            model=config.model,
            max_tokens=config.max_tokens,
            api_key=config.anthropic_api_key,
        )

        # Create orchestrator with references to all agents
        orchestrator = OrchestratorAgent(
            aws_agent=aws_agent,
            vault_agent=vault_agent,
            mcp_agent=mcp_agent,
            github_agent=github_agent,
            model=config.model,
            max_tokens=config.max_tokens,
            api_key=config.anthropic_api_key,
        )

        logger.info("Agent system created successfully")
        return cls(
            orchestrator=orchestrator,
            aws_agent=aws_agent,
            vault_agent=vault_agent,
            mcp_agent=mcp_agent,
            github_agent=github_agent,
        )

    @classmethod
    async def create_with_mcp_server(
        cls,
        config: AgentSystemConfig | None = None,
    ) -> "AgentSystem":
        """Create agent system with integrated MCP server.

        This starts the MCP server and connects all agents to it.
        """
        from ..server import VaultAWSMCPServer

        config = config or AgentSystemConfig()

        # Create MCP server
        mcp_server = VaultAWSMCPServer()

        # Create wrapper
        mcp_client = MCPClientWrapper(mcp_server)

        # Create system with MCP client
        system = cls.create(config=config, mcp_client=mcp_client)

        logger.info("Agent system created with MCP server integration")
        return system

    async def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Run a task through the orchestrator.

        The orchestrator will decompose the task and delegate to appropriate agents.

        Args:
            task: High-level task description
            context: Optional context data

        Returns:
            AgentResult with the outcome
        """
        logger.info(f"Agent system: processing task: {task[:100]}...")

        # Ensure credentials are valid before starting
        credential_check = await self.vault_agent.run(
            "Ensure we have valid AWS credentials with at least 5 minutes TTL"
        )

        if not credential_check.success:
            logger.warning("Credential check failed, proceeding anyway")

        # Run through orchestrator
        result = await self.orchestrator.run(task, context)

        return result

    async def run_direct(
        self,
        agent: str,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Run a task directly on a specific agent (bypassing orchestrator).

        Args:
            agent: Agent name ("aws", "vault", "mcp")
            task: Task description
            context: Optional context

        Returns:
            AgentResult from the specific agent
        """
        agents = {
            "aws": self.aws_agent,
            "vault": self.vault_agent,
            "mcp": self.mcp_agent,
            "github": self.github_agent,
            "orchestrator": self.orchestrator,
        }

        if agent not in agents:
            return AgentResult(
                success=False,
                output="",
                error=f"Unknown agent: {agent}. Valid: {list(agents.keys())}",
            )

        return await agents[agent].run(task, context)

    def reset_all(self) -> None:
        """Reset all agents' conversation history."""
        self.orchestrator.reset()
        self.aws_agent.reset()
        self.vault_agent.reset()
        self.mcp_agent.reset()
        self.github_agent.reset()
        logger.info("All agents reset")


async def main() -> None:
    """Example usage of the agent system."""
    import os

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create system
    config = AgentSystemConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    system = AgentSystem.create(config)

    # Example tasks
    tasks = [
        "What MCP tools are available for S3 operations?",
        "Check the status of our AWS credentials",
        "List all S3 buckets in the account",
    ]

    for task in tasks:
        print(f"\n{'='*60}")
        print(f"Task: {task}")
        print("="*60)

        result = await system.run(task)

        print(f"Success: {result.success}")
        print(f"Output: {result.output[:500]}...")
        if result.error:
            print(f"Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
