"""Vault Agent - specialized for HashiCorp Vault operations."""

import json
import logging
from typing import Any

from .base_agent import AgentTool, BaseAgent

logger = logging.getLogger(__name__)


class VaultAgent(BaseAgent):
    """Agent specialized for HashiCorp Vault operations.

    The Vault Agent:
    - Manages AWS credential leases (create, renew, revoke)
    - Handles secret operations
    - Monitors credential health and expiration
    - Has elevated Vault permissions for credential management
    """

    def __init__(self, mcp_client: Any = None, **kwargs: Any) -> None:
        """Initialize Vault Agent.

        Args:
            mcp_client: MCP client for calling Vault tools
            **kwargs: Additional arguments for BaseAgent
        """
        self._mcp_client = mcp_client
        super().__init__(name="Vault-Agent", **kwargs)

    @property
    def system_prompt(self) -> str:
        return """You are the Vault Agent, a specialized agent for HashiCorp Vault operations.

Your capabilities:
- **Credential Management**: Create, renew, and revoke AWS STS credentials
- **Lease Management**: Monitor active leases, check TTLs, handle renewals
- **Status Monitoring**: Check Vault connection, credential health

Your responsibilities:
- Ensure agents have valid, non-expired credentials
- Proactively renew credentials before expiration
- Revoke credentials when no longer needed (security best practice)
- Report credential status to the Orchestrator
- Handle Vault errors gracefully

Security Guidelines:
- Never expose raw credentials in responses
- Always use the minimum necessary TTL
- Revoke credentials immediately when done
- Monitor for unusual credential patterns
- Report any authentication failures

Lease Lifecycle:
1. **Create**: Request new STS credentials with appropriate TTL
2. **Monitor**: Track lease expiration, warn when renewal needed
3. **Renew**: Extend lease before expiration if still needed
4. **Revoke**: Immediately invalidate credentials when done

When reporting:
- Include lease ID (truncated for security)
- Report TTL remaining
- Warn when credentials expire soon (< 5 minutes)
- Never include actual access keys or secrets"""

    @property
    def vault_role(self) -> str:
        return "vault-admin-role"  # Elevated role for credential management

    def set_mcp_client(self, mcp_client: Any) -> None:
        """Set the MCP client for Vault operations."""
        self._mcp_client = mcp_client

    def _register_tools(self) -> None:
        """Register Vault operation tools."""

        self.register_tool(
            AgentTool(
                name="get_credential_status",
                description="Get current AWS credential status (lease ID, TTL remaining)",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._get_credential_status,
            )
        )

        self.register_tool(
            AgentTool(
                name="refresh_credentials",
                description="Request new AWS credentials from Vault",
                parameters={
                    "type": "object",
                    "properties": {
                        "ttl": {
                            "type": "string",
                            "description": "Requested TTL (e.g., '1h', '30m')",
                            "default": "1h",
                        },
                    },
                    "required": [],
                },
                handler=self._refresh_credentials,
            )
        )

        self.register_tool(
            AgentTool(
                name="revoke_credentials",
                description="Immediately revoke current AWS credentials",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._revoke_credentials,
            )
        )

        self.register_tool(
            AgentTool(
                name="check_vault_health",
                description="Check Vault server health and connectivity",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._check_vault_health,
            )
        )

        self.register_tool(
            AgentTool(
                name="get_lease_info",
                description="Get detailed information about a specific lease",
                parameters={
                    "type": "object",
                    "properties": {
                        "lease_id": {
                            "type": "string",
                            "description": "The lease ID to query",
                        },
                    },
                    "required": ["lease_id"],
                },
                handler=self._get_lease_info,
            )
        )

        self.register_tool(
            AgentTool(
                name="ensure_valid_credentials",
                description="Ensure credentials are valid, refreshing if needed",
                parameters={
                    "type": "object",
                    "properties": {
                        "min_ttl_seconds": {
                            "type": "integer",
                            "description": "Minimum TTL required in seconds",
                            "default": 300,
                        },
                    },
                    "required": [],
                },
                handler=self._ensure_valid_credentials,
            )
        )

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool through the MCP client."""
        if not self._mcp_client:
            return {"error": "MCP client not configured"}

        try:
            result = await self._mcp_client.call_tool(tool_name, arguments)
            if isinstance(result, str):
                return json.loads(result)
            return result
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return {"error": str(e)}

    async def _get_credential_status(self) -> dict[str, Any]:
        """Get credential status via MCP."""
        result = await self._call_mcp_tool("vault_credential_status", {})

        # Add security analysis
        if result.get("success") and result.get("data"):
            data = result["data"]
            ttl = data.get("lease_duration_seconds", 0)

            if ttl <= 0:
                result["warning"] = "No active credentials"
            elif ttl < 300:
                result["warning"] = f"Credentials expire in {ttl}s - renewal recommended"
            elif ttl < 600:
                result["info"] = f"Credentials expire in {ttl}s - monitor closely"

        return result

    async def _refresh_credentials(self, ttl: str = "1h") -> dict[str, Any]:
        """Refresh credentials via MCP."""
        logger.info(f"Vault Agent: refreshing credentials with TTL {ttl}")
        result = await self._call_mcp_tool("vault_refresh_credentials", {"ttl": ttl})

        if result.get("success"):
            result["info"] = f"New credentials obtained with TTL {ttl}"

        return result

    async def _revoke_credentials(self) -> dict[str, Any]:
        """Revoke credentials via MCP."""
        logger.info("Vault Agent: revoking credentials")
        result = await self._call_mcp_tool("vault_revoke_credentials", {})

        if result.get("success"):
            result["info"] = "Credentials revoked - AWS access terminated"

        return result

    async def _check_vault_health(self) -> dict[str, Any]:
        """Check Vault health (simulated via credential check)."""
        # Try to get credential status as a health check
        result = await self._get_credential_status()

        if result.get("error"):
            return {
                "success": False,
                "vault_status": "unhealthy",
                "error": result["error"],
            }

        return {
            "success": True,
            "vault_status": "healthy",
            "has_credentials": result.get("data", {}).get("has_valid_session", False),
        }

    async def _get_lease_info(self, lease_id: str) -> dict[str, Any]:
        """Get lease information."""
        # Get current status
        status = await self._get_credential_status()

        if status.get("data", {}).get("lease_id") == lease_id:
            return {
                "success": True,
                "lease_id": lease_id[:16] + "...",  # Truncate for security
                "lease_duration_seconds": status["data"].get("lease_duration_seconds"),
                "is_current": True,
            }

        return {
            "success": False,
            "error": "Lease not found or not current",
        }

    async def _ensure_valid_credentials(self, min_ttl_seconds: int = 300) -> dict[str, Any]:
        """Ensure credentials are valid with minimum TTL."""
        logger.info(f"Vault Agent: ensuring credentials with min TTL {min_ttl_seconds}s")

        # Check current status
        status = await self._get_credential_status()

        if not status.get("success"):
            # No credentials, get new ones
            return await self._refresh_credentials()

        data = status.get("data", {})
        current_ttl = data.get("lease_duration_seconds", 0)

        if not data.get("has_valid_session") or current_ttl < min_ttl_seconds:
            logger.info(f"Current TTL {current_ttl}s < {min_ttl_seconds}s - refreshing")
            return await self._refresh_credentials()

        return {
            "success": True,
            "action": "none",
            "info": f"Credentials valid with {current_ttl}s remaining",
            "lease_id": data.get("lease_id", "")[:16] + "..." if data.get("lease_id") else None,
        }
