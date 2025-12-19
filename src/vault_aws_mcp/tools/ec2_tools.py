"""EC2 MCP Tools - operations for Amazon EC2."""

import logging
from typing import Any

from mcp.types import Tool

from .base import AWSToolBase

logger = logging.getLogger(__name__)


class EC2Tools(AWSToolBase):
    """MCP tools for Amazon EC2 operations."""

    def get_tools(self) -> list[Tool]:
        """Return EC2 tools."""
        return [
            Tool(
                name="ec2_list_instances",
                description="List EC2 instances with optional filters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "array",
                            "description": "Optional filters (e.g., [{'Name': 'instance-state-name', 'Values': ['running']}])",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "Name": {"type": "string"},
                                    "Values": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                            },
                            "default": [],
                        },
                        "instance_ids": {
                            "type": "array",
                            "description": "Optional list of instance IDs to describe",
                            "items": {"type": "string"},
                            "default": [],
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="ec2_get_instance",
                description="Get detailed information about a specific EC2 instance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instance_id": {
                            "type": "string",
                            "description": "EC2 instance ID",
                        },
                    },
                    "required": ["instance_id"],
                },
            ),
            Tool(
                name="ec2_start_instance",
                description="Start a stopped EC2 instance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instance_id": {
                            "type": "string",
                            "description": "EC2 instance ID to start",
                        },
                    },
                    "required": ["instance_id"],
                },
            ),
            Tool(
                name="ec2_stop_instance",
                description="Stop a running EC2 instance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instance_id": {
                            "type": "string",
                            "description": "EC2 instance ID to stop",
                        },
                    },
                    "required": ["instance_id"],
                },
            ),
            Tool(
                name="ec2_list_security_groups",
                description="List security groups with optional filters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "vpc_id": {
                            "type": "string",
                            "description": "Optional VPC ID to filter security groups",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="ec2_list_vpcs",
                description="List all VPCs in the account",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
        ]

    async def handle_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Handle EC2 tool invocation."""
        try:
            ec2 = self.session.get_client("ec2")

            if name == "ec2_list_instances":
                return await self._list_instances(ec2, arguments)
            elif name == "ec2_get_instance":
                return await self._get_instance(ec2, arguments)
            elif name == "ec2_start_instance":
                return await self._start_instance(ec2, arguments)
            elif name == "ec2_stop_instance":
                return await self._stop_instance(ec2, arguments)
            elif name == "ec2_list_security_groups":
                return await self._list_security_groups(ec2, arguments)
            elif name == "ec2_list_vpcs":
                return await self._list_vpcs(ec2)
            else:
                return self._format_error(name, ValueError(f"Unknown tool: {name}"))

        except Exception as e:
            logger.error(f"EC2 tool error: {e}")
            return self._format_error(name, e)

    async def _list_instances(self, ec2: Any, args: dict[str, Any]) -> dict[str, Any]:
        """List EC2 instances."""
        kwargs: dict[str, Any] = {}

        if args.get("filters"):
            kwargs["Filters"] = args["filters"]
        if args.get("instance_ids"):
            kwargs["InstanceIds"] = args["instance_ids"]

        response = ec2.describe_instances(**kwargs)

        instances = []
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instances.append(self._format_instance(instance))

        return self._format_success("ec2_list_instances", {"instances": instances})

    async def _get_instance(self, ec2: Any, args: dict[str, Any]) -> dict[str, Any]:
        """Get instance details."""
        response = ec2.describe_instances(InstanceIds=[args["instance_id"]])

        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                return self._format_success(
                    "ec2_get_instance",
                    {"instance": self._format_instance(instance, detailed=True)},
                )

        return self._format_error(
            "ec2_get_instance",
            ValueError(f"Instance {args['instance_id']} not found"),
        )

    async def _start_instance(self, ec2: Any, args: dict[str, Any]) -> dict[str, Any]:
        """Start an EC2 instance."""
        response = ec2.start_instances(InstanceIds=[args["instance_id"]])

        state_change = response.get("StartingInstances", [{}])[0]
        return self._format_success(
            "ec2_start_instance",
            {
                "instance_id": args["instance_id"],
                "previous_state": state_change.get("PreviousState", {}).get("Name"),
                "current_state": state_change.get("CurrentState", {}).get("Name"),
            },
        )

    async def _stop_instance(self, ec2: Any, args: dict[str, Any]) -> dict[str, Any]:
        """Stop an EC2 instance."""
        response = ec2.stop_instances(InstanceIds=[args["instance_id"]])

        state_change = response.get("StoppingInstances", [{}])[0]
        return self._format_success(
            "ec2_stop_instance",
            {
                "instance_id": args["instance_id"],
                "previous_state": state_change.get("PreviousState", {}).get("Name"),
                "current_state": state_change.get("CurrentState", {}).get("Name"),
            },
        )

    async def _list_security_groups(
        self, ec2: Any, args: dict[str, Any]
    ) -> dict[str, Any]:
        """List security groups."""
        kwargs: dict[str, Any] = {}

        if args.get("vpc_id"):
            kwargs["Filters"] = [{"Name": "vpc-id", "Values": [args["vpc_id"]]}]

        response = ec2.describe_security_groups(**kwargs)

        groups = [
            {
                "id": sg["GroupId"],
                "name": sg["GroupName"],
                "description": sg["Description"],
                "vpc_id": sg.get("VpcId"),
            }
            for sg in response.get("SecurityGroups", [])
        ]

        return self._format_success("ec2_list_security_groups", {"security_groups": groups})

    async def _list_vpcs(self, ec2: Any) -> dict[str, Any]:
        """List VPCs."""
        response = ec2.describe_vpcs()

        vpcs = [
            {
                "id": vpc["VpcId"],
                "cidr_block": vpc["CidrBlock"],
                "state": vpc["State"],
                "is_default": vpc.get("IsDefault", False),
                "tags": {
                    tag["Key"]: tag["Value"] for tag in vpc.get("Tags", [])
                },
            }
            for vpc in response.get("Vpcs", [])
        ]

        return self._format_success("ec2_list_vpcs", {"vpcs": vpcs})

    def _format_instance(
        self, instance: dict[str, Any], detailed: bool = False
    ) -> dict[str, Any]:
        """Format instance data."""
        tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}

        data = {
            "instance_id": instance["InstanceId"],
            "instance_type": instance["InstanceType"],
            "state": instance["State"]["Name"],
            "name": tags.get("Name", ""),
            "private_ip": instance.get("PrivateIpAddress"),
            "public_ip": instance.get("PublicIpAddress"),
        }

        if detailed:
            data.update(
                {
                    "launch_time": instance.get("LaunchTime", "").isoformat()
                    if instance.get("LaunchTime")
                    else None,
                    "vpc_id": instance.get("VpcId"),
                    "subnet_id": instance.get("SubnetId"),
                    "ami_id": instance.get("ImageId"),
                    "key_name": instance.get("KeyName"),
                    "security_groups": [
                        {"id": sg["GroupId"], "name": sg["GroupName"]}
                        for sg in instance.get("SecurityGroups", [])
                    ],
                    "tags": tags,
                }
            )

        return data
