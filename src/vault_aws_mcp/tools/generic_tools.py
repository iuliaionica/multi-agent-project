"""Generic AWS MCP Tools - extensible tools for any AWS service."""

import json
import logging
from typing import Any

from mcp.types import Tool

from .base import AWSToolBase

logger = logging.getLogger(__name__)


class GenericAWSTools(AWSToolBase):
    """Generic MCP tools for any AWS service.

    These tools allow dynamic invocation of any AWS service API,
    making the MCP server extensible without code changes.
    """

    def get_tools(self) -> list[Tool]:
        """Return generic AWS tools."""
        return [
            Tool(
                name="aws_call",
                description=(
                    "Execute any AWS API call. This is a generic tool that can call "
                    "any AWS service operation. Use this for services not covered by "
                    "specific tools (DynamoDB, Lambda, SQS, SNS, etc.)"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "AWS service name (e.g., 'dynamodb', 'lambda', 'sqs', 'sns')",
                        },
                        "operation": {
                            "type": "string",
                            "description": "API operation name (e.g., 'list_tables', 'invoke', 'send_message')",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Parameters for the API call",
                            "default": {},
                        },
                        "region": {
                            "type": "string",
                            "description": "Optional AWS region override",
                        },
                    },
                    "required": ["service", "operation"],
                },
            ),
            Tool(
                name="aws_get_caller_identity",
                description="Get the AWS identity and account info for current credentials",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="aws_list_regions",
                description="List all available AWS regions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Optional service to filter regions by availability",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="vault_credential_status",
                description="Get status of current Vault-managed AWS credentials",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="vault_refresh_credentials",
                description="Force refresh of AWS credentials from Vault",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ttl": {
                            "type": "string",
                            "description": "Requested TTL for new credentials (e.g., '1h', '30m')",
                            "default": "1h",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="vault_revoke_credentials",
                description="Revoke current AWS credentials immediately",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
        ]

    async def handle_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Handle generic tool invocation."""
        try:
            if name == "aws_call":
                return await self._aws_call(arguments)
            elif name == "aws_get_caller_identity":
                return await self._get_caller_identity()
            elif name == "aws_list_regions":
                return await self._list_regions(arguments)
            elif name == "vault_credential_status":
                return await self._credential_status()
            elif name == "vault_refresh_credentials":
                return await self._refresh_credentials(arguments)
            elif name == "vault_revoke_credentials":
                return await self._revoke_credentials()
            else:
                return self._format_error(name, ValueError(f"Unknown tool: {name}"))

        except Exception as e:
            logger.error(f"Generic tool error: {e}")
            return self._format_error(name, e)

    async def _aws_call(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a generic AWS API call."""
        service = args["service"]
        operation = args["operation"]
        parameters = args.get("parameters", {})
        region = args.get("region")

        logger.info(f"AWS call: {service}.{operation}")

        client = self.session.get_client(service, region=region)

        # Get the operation method
        if not hasattr(client, operation):
            return self._format_error(
                "aws_call",
                ValueError(f"Unknown operation '{operation}' for service '{service}'"),
            )

        method = getattr(client, operation)
        response = method(**parameters)

        # Clean up response (remove ResponseMetadata)
        if isinstance(response, dict):
            response.pop("ResponseMetadata", None)

        return self._format_success(
            "aws_call",
            {
                "service": service,
                "operation": operation,
                "result": self._serialize_response(response),
            },
        )

    async def _get_caller_identity(self) -> dict[str, Any]:
        """Get current AWS identity."""
        identity = self.session.get_caller_identity()
        identity.pop("ResponseMetadata", None)

        return self._format_success(
            "aws_get_caller_identity",
            {
                "user_id": identity.get("UserId"),
                "account": identity.get("Account"),
                "arn": identity.get("Arn"),
            },
        )

    async def _list_regions(self, args: dict[str, Any]) -> dict[str, Any]:
        """List AWS regions."""
        ec2 = self.session.get_client("ec2")

        kwargs: dict[str, Any] = {"AllRegions": True}
        if args.get("service"):
            # Filter would require checking service availability per region
            pass

        response = ec2.describe_regions(**kwargs)

        regions = [
            {
                "name": r["RegionName"],
                "endpoint": r["Endpoint"],
                "opt_in_status": r.get("OptInStatus", "opt-in-not-required"),
            }
            for r in response.get("Regions", [])
        ]

        return self._format_success("aws_list_regions", {"regions": regions})

    async def _credential_status(self) -> dict[str, Any]:
        """Get credential status."""
        return self._format_success(
            "vault_credential_status",
            {
                "has_valid_session": self.session.has_valid_session,
                "lease_id": self.session.current_lease_id,
                "lease_duration_seconds": self.session.lease_duration,
            },
        )

    async def _refresh_credentials(self, args: dict[str, Any]) -> dict[str, Any]:
        """Refresh credentials."""
        ttl = args.get("ttl", "1h")
        self.session.refresh_credentials(ttl=ttl)

        return self._format_success(
            "vault_refresh_credentials",
            {
                "message": "Credentials refreshed successfully",
                "lease_id": self.session.current_lease_id,
                "lease_duration_seconds": self.session.lease_duration,
            },
        )

    async def _revoke_credentials(self) -> dict[str, Any]:
        """Revoke current credentials."""
        self.session.revoke_credentials()

        return self._format_success(
            "vault_revoke_credentials",
            {"message": "Credentials revoked successfully"},
        )

    def _serialize_response(self, obj: Any) -> Any:
        """Serialize AWS response to JSON-safe format."""
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        elif isinstance(obj, dict):
            return {k: self._serialize_response(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_response(i) for i in obj]
        return obj
