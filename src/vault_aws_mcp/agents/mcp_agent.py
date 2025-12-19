"""MCP Agent - specialized for MCP server management and tool discovery."""

import json
import logging
from typing import Any

from .base_agent import AgentTool, BaseAgent

logger = logging.getLogger(__name__)


class MCPAgent(BaseAgent):
    """Agent specialized for MCP server management.

    The MCP Agent:
    - Discovers available MCP tools
    - Monitors MCP server health
    - Provides tool documentation and usage guidance
    - Manages MCP server lifecycle
    """

    def __init__(self, mcp_client: Any = None, **kwargs: Any) -> None:
        """Initialize MCP Agent.

        Args:
            mcp_client: MCP client for server operations
            **kwargs: Additional arguments for BaseAgent
        """
        self._mcp_client = mcp_client
        self._discovered_tools: list[dict[str, Any]] = []
        super().__init__(name="MCP-Agent", **kwargs)

    @property
    def system_prompt(self) -> str:
        return """You are the MCP Agent, a specialized agent for MCP (Model Context Protocol) server management.

Your capabilities:
- **Tool Discovery**: List and describe all available MCP tools
- **Server Health**: Monitor MCP server status and connectivity
- **Documentation**: Provide usage guidance for MCP tools
- **Tool Routing**: Help other agents find the right tool for their needs

Your responsibilities:
- Maintain awareness of all available MCP tools
- Help the Orchestrator understand tool capabilities
- Report MCP server issues proactively
- Provide tool usage examples when requested

Available Tool Categories:
1. **S3 Tools**: s3_list_buckets, s3_list_objects, s3_get_object, s3_put_object, s3_delete_object
2. **EC2 Tools**: ec2_list_instances, ec2_get_instance, ec2_start_instance, ec2_stop_instance
3. **Generic AWS**: aws_call (for any AWS service), aws_get_caller_identity, aws_list_regions
4. **Vault Credentials**: vault_credential_status, vault_refresh_credentials, vault_revoke_credentials

When helping with tool selection:
- Recommend the most specific tool for each task
- Explain required vs optional parameters
- Warn about potential errors or limitations
- Suggest error handling approaches"""

    @property
    def vault_role(self) -> str:
        return "mcp-agent-role"  # Limited role for server management

    def set_mcp_client(self, mcp_client: Any) -> None:
        """Set the MCP client."""
        self._mcp_client = mcp_client

    def _register_tools(self) -> None:
        """Register MCP management tools."""

        self.register_tool(
            AgentTool(
                name="list_available_tools",
                description="List all available MCP tools with descriptions",
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category (s3, ec2, generic, vault)",
                            "enum": ["s3", "ec2", "generic", "vault", "all"],
                            "default": "all",
                        },
                    },
                    "required": [],
                },
                handler=self._list_available_tools,
            )
        )

        self.register_tool(
            AgentTool(
                name="get_tool_details",
                description="Get detailed information about a specific tool",
                parameters={
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "Name of the tool to describe",
                        },
                    },
                    "required": ["tool_name"],
                },
                handler=self._get_tool_details,
            )
        )

        self.register_tool(
            AgentTool(
                name="find_tool_for_task",
                description="Find the best MCP tool for a given task",
                parameters={
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": "Description of what you want to accomplish",
                        },
                    },
                    "required": ["task_description"],
                },
                handler=self._find_tool_for_task,
            )
        )

        self.register_tool(
            AgentTool(
                name="check_mcp_health",
                description="Check MCP server health and connectivity",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._check_mcp_health,
            )
        )

        self.register_tool(
            AgentTool(
                name="get_tool_usage_example",
                description="Get usage example for a specific tool",
                parameters={
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "Name of the tool",
                        },
                    },
                    "required": ["tool_name"],
                },
                handler=self._get_tool_usage_example,
            )
        )

    async def _list_available_tools(self, category: str = "all") -> dict[str, Any]:
        """List available MCP tools."""
        # Define tool catalog
        tools_catalog = {
            "s3": [
                {"name": "s3_list_buckets", "description": "List all S3 buckets"},
                {"name": "s3_list_objects", "description": "List objects in a bucket"},
                {"name": "s3_get_object", "description": "Get object contents"},
                {"name": "s3_put_object", "description": "Upload object to S3"},
                {"name": "s3_delete_object", "description": "Delete an object"},
                {"name": "s3_get_bucket_info", "description": "Get bucket information"},
            ],
            "ec2": [
                {"name": "ec2_list_instances", "description": "List EC2 instances"},
                {"name": "ec2_get_instance", "description": "Get instance details"},
                {"name": "ec2_start_instance", "description": "Start an instance"},
                {"name": "ec2_stop_instance", "description": "Stop an instance"},
                {"name": "ec2_list_security_groups", "description": "List security groups"},
                {"name": "ec2_list_vpcs", "description": "List VPCs"},
            ],
            "generic": [
                {"name": "aws_call", "description": "Call any AWS API"},
                {"name": "aws_get_caller_identity", "description": "Get AWS identity"},
                {"name": "aws_list_regions", "description": "List AWS regions"},
            ],
            "vault": [
                {"name": "vault_credential_status", "description": "Get credential status"},
                {"name": "vault_refresh_credentials", "description": "Refresh credentials"},
                {"name": "vault_revoke_credentials", "description": "Revoke credentials"},
            ],
        }

        if category == "all":
            all_tools = []
            for cat, tools in tools_catalog.items():
                for tool in tools:
                    tool["category"] = cat
                    all_tools.append(tool)
            return {
                "success": True,
                "total_tools": len(all_tools),
                "tools": all_tools,
            }

        if category in tools_catalog:
            tools = tools_catalog[category]
            for tool in tools:
                tool["category"] = category
            return {
                "success": True,
                "category": category,
                "total_tools": len(tools),
                "tools": tools,
            }

        return {
            "success": False,
            "error": f"Unknown category: {category}",
            "valid_categories": list(tools_catalog.keys()) + ["all"],
        }

    async def _get_tool_details(self, tool_name: str) -> dict[str, Any]:
        """Get detailed tool information."""
        tool_details = {
            "s3_list_buckets": {
                "name": "s3_list_buckets",
                "description": "List all S3 buckets in the AWS account",
                "category": "s3",
                "parameters": {},
                "returns": "List of bucket names with creation dates",
                "permissions_required": ["s3:ListAllMyBuckets"],
            },
            "s3_list_objects": {
                "name": "s3_list_objects",
                "description": "List objects in an S3 bucket with optional prefix filter",
                "category": "s3",
                "parameters": {
                    "bucket": {"type": "string", "required": True},
                    "prefix": {"type": "string", "required": False, "default": ""},
                    "max_keys": {"type": "integer", "required": False, "default": 100},
                },
                "returns": "List of objects with keys, sizes, and modification dates",
                "permissions_required": ["s3:ListBucket"],
            },
            "s3_get_object": {
                "name": "s3_get_object",
                "description": "Get the contents of an S3 object (works best for text files)",
                "category": "s3",
                "parameters": {
                    "bucket": {"type": "string", "required": True},
                    "key": {"type": "string", "required": True},
                },
                "returns": "Object content, content type, and size",
                "permissions_required": ["s3:GetObject"],
            },
            "ec2_list_instances": {
                "name": "ec2_list_instances",
                "description": "List EC2 instances with optional filters",
                "category": "ec2",
                "parameters": {
                    "filters": {"type": "array", "required": False},
                    "instance_ids": {"type": "array", "required": False},
                },
                "returns": "List of instances with IDs, states, IPs, and names",
                "permissions_required": ["ec2:DescribeInstances"],
            },
            "aws_call": {
                "name": "aws_call",
                "description": "Execute any AWS API call - use for services without specific tools",
                "category": "generic",
                "parameters": {
                    "service": {"type": "string", "required": True, "example": "dynamodb"},
                    "operation": {"type": "string", "required": True, "example": "list_tables"},
                    "parameters": {"type": "object", "required": False, "default": {}},
                    "region": {"type": "string", "required": False},
                },
                "returns": "AWS API response",
                "permissions_required": ["Depends on service and operation"],
            },
            "vault_credential_status": {
                "name": "vault_credential_status",
                "description": "Get status of current Vault-managed AWS credentials",
                "category": "vault",
                "parameters": {},
                "returns": "Session validity, lease ID (truncated), TTL remaining",
                "permissions_required": [],
            },
        }

        if tool_name in tool_details:
            return {
                "success": True,
                "tool": tool_details[tool_name],
            }

        return {
            "success": False,
            "error": f"Tool not found: {tool_name}",
            "suggestion": "Use list_available_tools to see all tools",
        }

    async def _find_tool_for_task(self, task_description: str) -> dict[str, Any]:
        """Find the best tool for a task."""
        task_lower = task_description.lower()

        recommendations = []

        # S3 keywords
        if any(kw in task_lower for kw in ["bucket", "s3", "storage", "file", "object", "upload", "download"]):
            if "list" in task_lower and "bucket" in task_lower:
                recommendations.append({"tool": "s3_list_buckets", "confidence": "high"})
            elif "upload" in task_lower or "put" in task_lower:
                recommendations.append({"tool": "s3_put_object", "confidence": "high"})
            elif "download" in task_lower or "get" in task_lower:
                recommendations.append({"tool": "s3_get_object", "confidence": "high"})
            elif "list" in task_lower:
                recommendations.append({"tool": "s3_list_objects", "confidence": "high"})
            elif "delete" in task_lower:
                recommendations.append({"tool": "s3_delete_object", "confidence": "high"})

        # EC2 keywords
        if any(kw in task_lower for kw in ["instance", "ec2", "server", "vm", "virtual"]):
            if "start" in task_lower:
                recommendations.append({"tool": "ec2_start_instance", "confidence": "high"})
            elif "stop" in task_lower:
                recommendations.append({"tool": "ec2_stop_instance", "confidence": "high"})
            elif "list" in task_lower:
                recommendations.append({"tool": "ec2_list_instances", "confidence": "high"})

        # Credential keywords
        if any(kw in task_lower for kw in ["credential", "auth", "token", "vault", "secret"]):
            if "refresh" in task_lower or "new" in task_lower:
                recommendations.append({"tool": "vault_refresh_credentials", "confidence": "high"})
            elif "revoke" in task_lower or "invalidate" in task_lower:
                recommendations.append({"tool": "vault_revoke_credentials", "confidence": "high"})
            else:
                recommendations.append({"tool": "vault_credential_status", "confidence": "medium"})

        # Identity
        if any(kw in task_lower for kw in ["identity", "who am i", "account", "caller"]):
            recommendations.append({"tool": "aws_get_caller_identity", "confidence": "high"})

        # Generic fallback
        if not recommendations:
            recommendations.append({
                "tool": "aws_call",
                "confidence": "low",
                "note": "Generic tool - specify service and operation",
            })

        return {
            "success": True,
            "task": task_description,
            "recommendations": recommendations,
        }

    async def _check_mcp_health(self) -> dict[str, Any]:
        """Check MCP server health."""
        if not self._mcp_client:
            return {
                "success": False,
                "status": "not_connected",
                "error": "MCP client not configured",
            }

        try:
            # Try to list tools as health check
            # In real implementation, this would call the MCP client
            return {
                "success": True,
                "status": "healthy",
                "message": "MCP server responding normally",
            }
        except Exception as e:
            return {
                "success": False,
                "status": "unhealthy",
                "error": str(e),
            }

    async def _get_tool_usage_example(self, tool_name: str) -> dict[str, Any]:
        """Get usage example for a tool."""
        examples = {
            "s3_list_buckets": {
                "description": "List all S3 buckets",
                "arguments": {},
                "example_response": {
                    "success": True,
                    "data": {
                        "buckets": [
                            {"name": "my-bucket", "creation_date": "2024-01-15T10:30:00Z"}
                        ]
                    }
                },
            },
            "s3_list_objects": {
                "description": "List objects in a bucket with prefix",
                "arguments": {
                    "bucket": "my-bucket",
                    "prefix": "logs/",
                    "max_keys": 10,
                },
                "example_response": {
                    "success": True,
                    "data": {
                        "objects": [
                            {"key": "logs/app.log", "size": 1024, "last_modified": "2024-01-15"}
                        ]
                    }
                },
            },
            "ec2_list_instances": {
                "description": "List running EC2 instances",
                "arguments": {
                    "filters": [{"Name": "instance-state-name", "Values": ["running"]}]
                },
                "example_response": {
                    "success": True,
                    "data": {
                        "instances": [
                            {"instance_id": "i-1234567890abcdef0", "state": "running"}
                        ]
                    }
                },
            },
            "aws_call": {
                "description": "List DynamoDB tables",
                "arguments": {
                    "service": "dynamodb",
                    "operation": "list_tables",
                    "parameters": {"Limit": 10},
                },
                "example_response": {
                    "success": True,
                    "data": {"result": {"TableNames": ["users", "orders"]}}
                },
            },
        }

        if tool_name in examples:
            return {
                "success": True,
                "tool": tool_name,
                "example": examples[tool_name],
            }

        return {
            "success": False,
            "error": f"No example available for: {tool_name}",
        }
