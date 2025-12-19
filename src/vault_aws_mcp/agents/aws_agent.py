"""
AWS Agent - Agent specializat pentru operațiuni AWS S3.

Acest agent folosește Claude pentru a "gândi" și decide ce tool să folosească.
Are acces la 3 tools pentru managementul bucket-urilor S3:
- s3_create_bucket: creează un bucket nou
- s3_list_buckets: listează toate bucket-urile
- s3_delete_bucket: șterge un bucket

Fluxul:
1. Primește o cerere de la utilizator (ex: "creează bucket test123")
2. Claude analizează cererea și decide să folosească s3_create_bucket
3. Tool-ul execută operațiunea AWS folosind credențiale din Vault
4. Rezultatul este returnat utilizatorului
"""

import logging
from typing import Any

from .base_agent import AgentTool, BaseAgent

logger = logging.getLogger(__name__)


class AWSAgent(BaseAgent):
    """Agent pentru operațiuni S3 bucket."""

    def __init__(
        self,
        vault_client: Any = None,
        session_manager: Any = None,
        **kwargs: Any,
    ) -> None:
        """
        Inițializează AWS Agent.

        Args:
            vault_client: Client Vault pentru credențiale AWS
            session_manager: Manager sesiune AWS (boto3)
            **kwargs: Argumente pentru BaseAgent (api_key, model, etc.)
        """
        self._vault_client = vault_client
        self._session_manager = session_manager
        super().__init__(name="AWS-Agent", **kwargs)

    @property
    def system_prompt(self) -> str:
        """Prompt-ul sistem care definește comportamentul agentului."""
        return """You are an AWS S3 Agent that manages S3 buckets.

Available tools:
- s3_create_bucket: Create a new S3 bucket
- s3_list_buckets: List all S3 buckets
- s3_delete_bucket: Delete an S3 bucket (must be empty)

When asked to perform an operation:
1. Use the appropriate tool
2. Report the result clearly

Always use the exact bucket name provided by the user."""

    @property
    def vault_role(self) -> str:
        return "aws-agent-role"

    def _get_session_manager(self) -> Any:
        """Obține sau creează session manager pentru AWS."""
        if self._session_manager:
            return self._session_manager

        # Inițializare lazy - creăm session manager la prima utilizare
        if not self._vault_client:
            from ..services.vault_client import VaultClient
            self._vault_client = VaultClient()

        from ..services.aws_session_manager import AWSSessionManager
        self._session_manager = AWSSessionManager(self._vault_client)
        self._session_manager.initialize_session()
        return self._session_manager

    def _register_tools(self) -> None:
        """Înregistrează cele 3 tools pentru S3 buckets."""

        # Tool 1: Creează bucket
        self.register_tool(
            AgentTool(
                name="s3_create_bucket",
                description="Create a new S3 bucket",
                parameters={
                    "type": "object",
                    "properties": {
                        "bucket_name": {
                            "type": "string",
                            "description": "Bucket name (must be globally unique)",
                        },
                    },
                    "required": ["bucket_name"],
                },
                handler=self._s3_create_bucket,
            )
        )

        # Tool 2: Listează buckets
        self.register_tool(
            AgentTool(
                name="s3_list_buckets",
                description="List all S3 buckets",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._s3_list_buckets,
            )
        )

        # Tool 3: Șterge bucket
        self.register_tool(
            AgentTool(
                name="s3_delete_bucket",
                description="Delete an S3 bucket (must be empty)",
                parameters={
                    "type": "object",
                    "properties": {
                        "bucket_name": {
                            "type": "string",
                            "description": "Bucket name to delete",
                        },
                    },
                    "required": ["bucket_name"],
                },
                handler=self._s3_delete_bucket,
            )
        )

    async def _s3_create_bucket(self, bucket_name: str) -> dict[str, Any]:
        """
        Creează un bucket S3 nou.

        Args:
            bucket_name: Numele bucket-ului (trebuie să fie unic global)

        Returns:
            Dict cu success/error și detalii
        """
        try:
            session_mgr = self._get_session_manager()
            s3 = session_mgr.get_client("s3")

            # Creăm bucket-ul (us-east-1 nu necesită LocationConstraint)
            s3.create_bucket(Bucket=bucket_name)

            logger.info(f"Bucket created: {bucket_name}")
            return {
                "success": True,
                "bucket_name": bucket_name,
                "message": f"Bucket '{bucket_name}' created successfully",
            }
        except Exception as e:
            error_msg = str(e)
            if "BucketAlreadyOwnedByYou" in error_msg:
                return {
                    "success": True,
                    "bucket_name": bucket_name,
                    "message": "Bucket already exists and you own it",
                }
            logger.error(f"Failed to create bucket: {e}")
            return {"success": False, "error": error_msg}

    async def _s3_list_buckets(self) -> dict[str, Any]:
        """
        Listează toate bucket-urile S3.

        Returns:
            Dict cu lista de buckets
        """
        try:
            session_mgr = self._get_session_manager()
            s3 = session_mgr.get_client("s3")
            response = s3.list_buckets()

            buckets = [
                {
                    "name": b["Name"],
                    "created": b["CreationDate"].isoformat(),
                }
                for b in response.get("Buckets", [])
            ]

            return {
                "success": True,
                "count": len(buckets),
                "buckets": buckets,
            }
        except Exception as e:
            logger.error(f"Failed to list buckets: {e}")
            return {"success": False, "error": str(e)}

    async def _s3_delete_bucket(self, bucket_name: str) -> dict[str, Any]:
        """
        Șterge un bucket S3 (trebuie să fie gol).

        Args:
            bucket_name: Numele bucket-ului de șters

        Returns:
            Dict cu success/error
        """
        try:
            session_mgr = self._get_session_manager()
            s3 = session_mgr.get_client("s3")

            s3.delete_bucket(Bucket=bucket_name)

            logger.info(f"Bucket deleted: {bucket_name}")
            return {
                "success": True,
                "bucket_name": bucket_name,
                "message": f"Bucket '{bucket_name}' deleted successfully",
            }
        except Exception as e:
            logger.error(f"Failed to delete bucket: {e}")
            return {"success": False, "error": str(e)}
