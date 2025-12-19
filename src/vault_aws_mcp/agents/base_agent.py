"""Base Agent class for all specialized agents."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class AgentTool:
    """Definition of a tool available to an agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]


@dataclass
class AgentMessage:
    """A message in the agent conversation."""

    role: str  # "user", "assistant", or "system"
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    """Result from an agent execution."""

    success: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    messages: list[AgentMessage] = field(default_factory=list)


class BaseAgent(ABC):
    """Base class for specialized agents using Claude API.

    Each agent has:
    - A specific role and system prompt
    - Access to specific tools
    - Its own Vault role for credentials (least privilege)
    """

    def __init__(
        self,
        name: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        api_key: str | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.max_tokens = max_tokens
        self._client = Anthropic(api_key=api_key) if api_key else Anthropic()
        self._tools: dict[str, AgentTool] = {}
        self._conversation: list[dict[str, Any]] = []

        # Register agent-specific tools
        self._register_tools()

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        ...

    @property
    @abstractmethod
    def vault_role(self) -> str:
        """Return the Vault role this agent should use."""
        ...

    @abstractmethod
    def _register_tools(self) -> None:
        """Register tools specific to this agent."""
        ...

    def register_tool(self, tool: AgentTool) -> None:
        """Register a tool for this agent."""
        self._tools[tool.name] = tool
        logger.debug(f"Agent {self.name}: registered tool {tool.name}")

    def get_tools_schema(self) -> list[dict[str, Any]]:
        """Get tools in Claude API format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a registered tool."""
        if name not in self._tools:
            return {"error": f"Unknown tool: {name}"}

        tool = self._tools[name]
        try:
            logger.info(f"Agent {self.name}: executing tool {name}")
            result = await tool.handler(**arguments)
            return result
        except Exception as e:
            logger.error(f"Agent {self.name}: tool {name} failed: {e}")
            return {"error": str(e)}

    async def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute a task using this agent.

        Args:
            task: The task description for the agent
            context: Optional context data from orchestrator or other agents

        Returns:
            AgentResult with the outcome
        """
        logger.info(f"Agent {self.name}: starting task")

        # Build the user message with optional context
        user_content = task
        if context:
            user_content = f"Context: {json.dumps(context)}\n\nTask: {task}"

        messages = [{"role": "user", "content": user_content}]
        collected_messages: list[AgentMessage] = []

        # Agentic loop - continue until no more tool calls
        while True:
            try:
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt,
                    tools=self.get_tools_schema() if self._tools else [],
                    messages=messages,
                )
            except Exception as e:
                logger.error(f"Agent {self.name}: API error: {e}")
                return AgentResult(
                    success=False,
                    output="",
                    error=str(e),
                    messages=collected_messages,
                )

            # Process response
            assistant_content = []
            tool_calls = []
            text_output = ""

            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            # Add assistant message
            messages.append({"role": "assistant", "content": assistant_content})
            collected_messages.append(
                AgentMessage(
                    role="assistant",
                    content=text_output,
                    tool_calls=tool_calls,
                )
            )

            # If no tool calls, we're done
            if response.stop_reason == "end_turn" or not tool_calls:
                logger.info(f"Agent {self.name}: task completed")
                return AgentResult(
                    success=True,
                    output=text_output,
                    messages=collected_messages,
                )

            # Execute tool calls
            tool_results = []
            for tool_call in tool_calls:
                result = await self._execute_tool(
                    tool_call["name"],
                    tool_call["input"],
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    }
                )

            # Add tool results to conversation
            messages.append({"role": "user", "content": tool_results})
            collected_messages.append(
                AgentMessage(
                    role="user",
                    content="",
                    tool_results=tool_results,
                )
            )

    def reset(self) -> None:
        """Reset the agent's conversation history."""
        self._conversation = []
