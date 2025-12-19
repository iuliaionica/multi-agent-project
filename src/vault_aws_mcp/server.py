"""Vault AWS MCP Server - Main entry point."""

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import settings
from .services.vault_client import VaultClient
from .services.aws_session_manager import AWSSessionManager
from .services.lease_manager import LeaseManager
from .tools.s3_tools import S3Tools
from .tools.ec2_tools import EC2Tools
from .tools.generic_tools import GenericAWSTools

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class VaultAWSMCPServer:
    """MCP Server for AWS operations with Vault credential management.

    Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                       MCP Client (Claude)                        │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      MCP Server (this)                          │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
    │  │  S3 Tools   │  │ EC2 Tools   │  │  Generic AWS Tools      │  │
    │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
    │                           │                                      │
    │                           ▼                                      │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │              AWS Session Manager                            ││
    │  │         (manages boto3 sessions with temp creds)            ││
    │  └─────────────────────────────────────────────────────────────┘│
    │                           │                                      │
    │                           ▼                                      │
    │  ┌──────────────────┐  ┌──────────────────────────────────────┐ │
    │  │  Vault Client    │  │       Lease Manager                  │ │
    │  │  (gets STS creds)│  │  (auto-renew, revoke on shutdown)    │ │
    │  └──────────────────┘  └──────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    HashiCorp Vault                              │
    │              (AWS Secrets Engine + STS)                         │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                         AWS STS                                  │
    │                 (AssumeRole → temp credentials)                  │
    └─────────────────────────────────────────────────────────────────┘
    """

    def __init__(self) -> None:
        self._server = Server("vault-aws-mcp")
        self._vault_client = VaultClient()
        self._session_manager = AWSSessionManager(self._vault_client)
        self._lease_manager = LeaseManager(vault_client=self._vault_client)

        # Initialize tool providers
        self._tool_providers = [
            S3Tools(self._session_manager),
            EC2Tools(self._session_manager),
            GenericAWSTools(self._session_manager),
        ]

        # Build tool registry
        self._tools: dict[str, Any] = {}
        for provider in self._tool_providers:
            for tool in provider.get_tools():
                self._tools[tool.name] = (tool, provider)

        # Register MCP handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register MCP server handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            """Return all available tools."""
            return [tool for tool, _ in self._tools.values()]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool invocation."""
            logger.info(f"Tool called: {name}")
            logger.debug(f"Arguments: {arguments}")

            # Ensure we have valid credentials
            if not self._session_manager.has_valid_session:
                await self._initialize_session()

            # Find and execute the tool
            if name not in self._tools:
                error_result = {
                    "success": False,
                    "error": f"Unknown tool: {name}",
                }
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

            _, provider = self._tools[name]
            result = await provider.handle_tool(name, arguments)

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _initialize_session(self) -> None:
        """Initialize AWS session with Vault credentials."""
        logger.info("Initializing AWS session")

        try:
            self._session_manager.initialize_session()

            # Register the lease for management
            if self._session_manager.current_lease_id:
                self._lease_manager.register_lease(
                    lease_id=self._session_manager.current_lease_id,
                    duration=self._session_manager.lease_duration or 3600,
                    renewable=True,
                )

        except ConnectionError as e:
            logger.warning(f"Vault not available: {e}")
            if settings.aws_fallback_enabled:
                logger.info("Falling back to local AWS credentials")
                # Create session with default credential chain
                import boto3
                self._session_manager._session = boto3.Session(
                    region_name=settings.aws_region
                )
                self._session_manager._current_credentials = None
            else:
                raise

    async def _on_lease_expired(self, lease_id: str) -> None:
        """Handle lease expiration."""
        logger.warning(f"Lease expired: {lease_id}")
        # Clear session to force re-authentication
        self._session_manager._current_credentials = None
        self._session_manager._session = None

    async def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting Vault AWS MCP Server")
        logger.info(f"Vault address: {settings.vault_addr}")
        logger.info(f"AWS role: {settings.vault_aws_role}")

        # Start lease manager
        await self._lease_manager.start(on_lease_expired=self._on_lease_expired)

        try:
            # Run the MCP server
            async with stdio_server() as (read_stream, write_stream):
                await self._server.run(
                    read_stream,
                    write_stream,
                    self._server.create_initialization_options(),
                )
        finally:
            # Cleanup
            await self._lease_manager.stop()
            logger.info("Server stopped")


def main() -> None:
    """Main entry point."""
    server = VaultAWSMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
