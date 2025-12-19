"""AWS Session Manager - manages boto3 sessions with Vault-provided credentials."""

import logging
from typing import Any

import boto3
from botocore.config import Config

from ..config import settings
from .vault_client import AWSCredentials, VaultClient

logger = logging.getLogger(__name__)


class AWSSessionManager:
    """Manages AWS sessions using temporary credentials from Vault.

    This manager:
    - Obtains STS credentials from Vault
    - Creates boto3 sessions with those credentials
    - Provides clients for any AWS service
    - Tracks active credentials for renewal/revocation
    """

    def __init__(self, vault_client: VaultClient) -> None:
        self._vault_client = vault_client
        self._current_credentials: AWSCredentials | None = None
        self._session: boto3.Session | None = None
        self._boto_config = Config(
            retries={"max_attempts": 5, "mode": "adaptive"},
            connect_timeout=30,
            read_timeout=120,
        )

    @property
    def has_valid_session(self) -> bool:
        """Check if we have a valid session with credentials."""
        return self._current_credentials is not None and self._session is not None

    @property
    def current_lease_id(self) -> str | None:
        """Get the current credential lease ID."""
        return self._current_credentials.lease_id if self._current_credentials else None

    @property
    def lease_duration(self) -> int | None:
        """Get remaining lease duration in seconds."""
        return self._current_credentials.lease_duration if self._current_credentials else None

    def initialize_session(
        self,
        role: str | None = None,
        ttl: str | None = None,
        region: str | None = None,
    ) -> None:
        """Initialize a new AWS session with Vault credentials.

        Args:
            role: Vault AWS role to use
            ttl: Requested credential TTL
            region: AWS region for the session
        """
        logger.info("Initializing AWS session with Vault credentials")

        # Get fresh credentials from Vault
        self._current_credentials = self._vault_client.get_sts_credentials(
            role=role,
            ttl=ttl,
        )

        # Create boto3 session with the temporary credentials
        self._session = boto3.Session(
            aws_access_key_id=self._current_credentials.access_key,
            aws_secret_access_key=self._current_credentials.secret_key,
            aws_session_token=self._current_credentials.session_token,
            region_name=region or settings.aws_region,
        )

        logger.info(
            f"AWS session initialized, region={region or settings.aws_region}, "
            f"lease_ttl={self._current_credentials.lease_duration}s"
        )

    def get_client(self, service_name: str, region: str | None = None) -> Any:
        """Get a boto3 client for the specified AWS service.

        Args:
            service_name: AWS service name (e.g., 's3', 'ec2', 'dynamodb')
            region: Optional region override

        Returns:
            boto3 client for the service

        Raises:
            RuntimeError: If session not initialized
        """
        if not self.has_valid_session:
            raise RuntimeError("AWS session not initialized. Call initialize_session() first.")

        return self._session.client(
            service_name,
            region_name=region,
            config=self._boto_config,
        )

    def get_resource(self, service_name: str, region: str | None = None) -> Any:
        """Get a boto3 resource for the specified AWS service.

        Args:
            service_name: AWS service name
            region: Optional region override

        Returns:
            boto3 resource for the service
        """
        if not self.has_valid_session:
            raise RuntimeError("AWS session not initialized. Call initialize_session() first.")

        return self._session.resource(
            service_name,
            region_name=region,
            config=self._boto_config,
        )

    def refresh_credentials(self, ttl: str | None = None) -> None:
        """Refresh credentials by getting new ones from Vault.

        This revokes the old credentials and obtains new ones.

        Args:
            ttl: Requested TTL for new credentials
        """
        logger.info("Refreshing AWS credentials")

        # Revoke old credentials if we have them
        if self._current_credentials:
            try:
                self._vault_client.revoke_lease(self._current_credentials.lease_id)
            except Exception as e:
                logger.warning(f"Failed to revoke old credentials: {e}")

        # Get new credentials
        self.initialize_session(ttl=ttl)

    def revoke_credentials(self) -> None:
        """Revoke current credentials and clear session.

        Call this when done with AWS operations to immediately invalidate
        the temporary credentials.
        """
        if self._current_credentials:
            logger.info("Revoking AWS credentials")
            try:
                self._vault_client.revoke_lease(self._current_credentials.lease_id)
            except Exception as e:
                logger.warning(f"Failed to revoke credentials: {e}")
            finally:
                self._current_credentials = None
                self._session = None
        else:
            logger.debug("No credentials to revoke")

    def get_caller_identity(self) -> dict[str, str]:
        """Get the AWS identity for current credentials.

        Useful for verifying credentials and getting the assumed role ARN.

        Returns:
            Dict with UserId, Account, and Arn
        """
        sts = self.get_client("sts")
        return sts.get_caller_identity()
