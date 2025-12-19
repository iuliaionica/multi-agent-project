"""Base class for AWS MCP tools."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from mcp.types import Tool

from ..services.aws_session_manager import AWSSessionManager

logger = logging.getLogger(__name__)


class AWSToolBase(ABC):
    """Base class for AWS tool implementations.

    Subclasses should implement get_tools() to define available MCP tools
    and handle_tool() to execute tool calls.
    """

    def __init__(self, session_manager: AWSSessionManager) -> None:
        self._session_manager = session_manager

    @property
    def session(self) -> AWSSessionManager:
        """Get the AWS session manager."""
        return self._session_manager

    @abstractmethod
    def get_tools(self) -> list[Tool]:
        """Return list of MCP tools provided by this class."""
        ...

    @abstractmethod
    async def handle_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Handle a tool invocation.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        ...

    def _format_error(self, operation: str, error: Exception) -> dict[str, Any]:
        """Format an error response."""
        return {
            "success": False,
            "error": str(error),
            "operation": operation,
        }

    def _format_success(self, operation: str, data: Any) -> dict[str, Any]:
        """Format a success response."""
        return {
            "success": True,
            "operation": operation,
            "data": data,
        }
