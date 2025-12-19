"""S3 MCP Tools - operations for Amazon S3."""

import json
import logging
from typing import Any

from mcp.types import Tool

from .base import AWSToolBase

logger = logging.getLogger(__name__)


class S3Tools(AWSToolBase):
    """MCP tools for Amazon S3 operations."""

    def get_tools(self) -> list[Tool]:
        """Return S3 tools."""
        return [
            Tool(
                name="s3_list_buckets",
                description="List all S3 buckets in the AWS account",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="s3_list_objects",
                description="List objects in an S3 bucket with optional prefix filter",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bucket": {
                            "type": "string",
                            "description": "S3 bucket name",
                        },
                        "prefix": {
                            "type": "string",
                            "description": "Optional prefix to filter objects",
                            "default": "",
                        },
                        "max_keys": {
                            "type": "integer",
                            "description": "Maximum number of objects to return",
                            "default": 100,
                        },
                    },
                    "required": ["bucket"],
                },
            ),
            Tool(
                name="s3_get_object",
                description="Get the contents of an S3 object (for text files)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bucket": {
                            "type": "string",
                            "description": "S3 bucket name",
                        },
                        "key": {
                            "type": "string",
                            "description": "Object key (path)",
                        },
                    },
                    "required": ["bucket", "key"],
                },
            ),
            Tool(
                name="s3_put_object",
                description="Upload content to an S3 object",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bucket": {
                            "type": "string",
                            "description": "S3 bucket name",
                        },
                        "key": {
                            "type": "string",
                            "description": "Object key (path)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to upload",
                        },
                        "content_type": {
                            "type": "string",
                            "description": "MIME type of the content",
                            "default": "text/plain",
                        },
                    },
                    "required": ["bucket", "key", "content"],
                },
            ),
            Tool(
                name="s3_delete_object",
                description="Delete an S3 object",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bucket": {
                            "type": "string",
                            "description": "S3 bucket name",
                        },
                        "key": {
                            "type": "string",
                            "description": "Object key (path)",
                        },
                    },
                    "required": ["bucket", "key"],
                },
            ),
            Tool(
                name="s3_get_bucket_info",
                description="Get information about an S3 bucket (location, versioning, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bucket": {
                            "type": "string",
                            "description": "S3 bucket name",
                        },
                    },
                    "required": ["bucket"],
                },
            ),
        ]

    async def handle_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Handle S3 tool invocation."""
        try:
            s3 = self.session.get_client("s3")

            if name == "s3_list_buckets":
                return await self._list_buckets(s3)
            elif name == "s3_list_objects":
                return await self._list_objects(s3, arguments)
            elif name == "s3_get_object":
                return await self._get_object(s3, arguments)
            elif name == "s3_put_object":
                return await self._put_object(s3, arguments)
            elif name == "s3_delete_object":
                return await self._delete_object(s3, arguments)
            elif name == "s3_get_bucket_info":
                return await self._get_bucket_info(s3, arguments)
            else:
                return self._format_error(name, ValueError(f"Unknown tool: {name}"))

        except Exception as e:
            logger.error(f"S3 tool error: {e}")
            return self._format_error(name, e)

    async def _list_buckets(self, s3: Any) -> dict[str, Any]:
        """List all S3 buckets."""
        response = s3.list_buckets()
        buckets = [
            {
                "name": b["Name"],
                "creation_date": b["CreationDate"].isoformat(),
            }
            for b in response.get("Buckets", [])
        ]
        return self._format_success("s3_list_buckets", {"buckets": buckets})

    async def _list_objects(self, s3: Any, args: dict[str, Any]) -> dict[str, Any]:
        """List objects in a bucket."""
        response = s3.list_objects_v2(
            Bucket=args["bucket"],
            Prefix=args.get("prefix", ""),
            MaxKeys=args.get("max_keys", 100),
        )

        objects = [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            }
            for obj in response.get("Contents", [])
        ]

        return self._format_success(
            "s3_list_objects",
            {
                "bucket": args["bucket"],
                "prefix": args.get("prefix", ""),
                "objects": objects,
                "is_truncated": response.get("IsTruncated", False),
            },
        )

    async def _get_object(self, s3: Any, args: dict[str, Any]) -> dict[str, Any]:
        """Get object contents."""
        response = s3.get_object(Bucket=args["bucket"], Key=args["key"])

        # Read content (assume text for now)
        content = response["Body"].read().decode("utf-8")

        return self._format_success(
            "s3_get_object",
            {
                "bucket": args["bucket"],
                "key": args["key"],
                "content": content,
                "content_type": response.get("ContentType", "unknown"),
                "size": response.get("ContentLength", 0),
            },
        )

    async def _put_object(self, s3: Any, args: dict[str, Any]) -> dict[str, Any]:
        """Upload object to S3."""
        s3.put_object(
            Bucket=args["bucket"],
            Key=args["key"],
            Body=args["content"].encode("utf-8"),
            ContentType=args.get("content_type", "text/plain"),
        )

        return self._format_success(
            "s3_put_object",
            {
                "bucket": args["bucket"],
                "key": args["key"],
                "message": "Object uploaded successfully",
            },
        )

    async def _delete_object(self, s3: Any, args: dict[str, Any]) -> dict[str, Any]:
        """Delete an S3 object."""
        s3.delete_object(Bucket=args["bucket"], Key=args["key"])

        return self._format_success(
            "s3_delete_object",
            {
                "bucket": args["bucket"],
                "key": args["key"],
                "message": "Object deleted successfully",
            },
        )

    async def _get_bucket_info(self, s3: Any, args: dict[str, Any]) -> dict[str, Any]:
        """Get bucket information."""
        bucket = args["bucket"]

        # Get location
        try:
            location = s3.get_bucket_location(Bucket=bucket)
            region = location.get("LocationConstraint") or "us-east-1"
        except Exception:
            region = "unknown"

        # Get versioning
        try:
            versioning = s3.get_bucket_versioning(Bucket=bucket)
            versioning_status = versioning.get("Status", "Disabled")
        except Exception:
            versioning_status = "unknown"

        return self._format_success(
            "s3_get_bucket_info",
            {
                "bucket": bucket,
                "region": region,
                "versioning": versioning_status,
            },
        )
