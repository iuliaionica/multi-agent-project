"""HashiCorp Vault client for AWS credentials management."""

import logging
from dataclasses import dataclass
from typing import Any

import hvac
from hvac.exceptions import VaultError

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class AWSCredentials:
    """Temporary AWS credentials obtained from Vault via STS AssumeRole."""

    access_key: str
    secret_key: str
    session_token: str
    lease_id: str
    lease_duration: int  # seconds
    renewable: bool

    def to_boto3_credentials(self) -> dict[str, str]:
        """Convert to boto3 session credentials format."""
        return {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "aws_session_token": self.session_token,
        }


class VaultClient:
    """Client for interacting with HashiCorp Vault AWS Secrets Engine.

    This client uses Vault's AWS Secrets Engine configured with STS AssumeRole.
    Instead of creating IAM users, Vault calls AWS STS to assume an IAM role
    and returns temporary credentials that automatically expire.

    Flow:
    1. MCP Server requests credentials from Vault
    2. Vault calls AWS STS AssumeRole
    3. AWS returns temporary credentials (access key, secret key, session token)
    4. Vault wraps these in a lease and returns to MCP Server
    5. Credentials expire automatically (default 1h TTL)
    6. Vault can revoke credentials early if needed
    """

    def __init__(self) -> None:
        self._client: hvac.Client | None = None
        self._connected = False

    @property
    def client(self) -> hvac.Client:
        """Get or create the Vault client."""
        if self._client is None:
            self._client = hvac.Client(
                url=settings.vault_addr,
                token=settings.vault_token,
                namespace=settings.vault_namespace,
            )
        return self._client

    def is_connected(self) -> bool:
        """Check if connected and authenticated to Vault."""
        try:
            return self.client.is_authenticated()
        except Exception as e:
            logger.warning(f"Vault connection check failed: {e}")
            return False

    def get_kv_credentials(self) -> AWSCredentials:
        """Get AWS credentials from Vault KV store.

        Reads static credentials from KV path (e.g., secret/aws).

        Returns:
            AWSCredentials with access key and secret key
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to Vault")

        kv_path = settings.vault_kv_path
        logger.info(f"Reading AWS credentials from KV path: {kv_path}")

        try:
            # Parse path: "secret/aws" -> mount=secret, path=aws
            parts = kv_path.split("/", 1)
            mount_point = parts[0] if len(parts) > 1 else "secret"
            path = parts[1] if len(parts) > 1 else parts[0]

            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=mount_point,
            )

            data = response["data"]["data"]

            # Support multiple key naming conventions
            access_key = data.get("access_key_id") or data.get("access_key") or data.get("AWS_ACCESS_KEY_ID")
            secret_key = data.get("secret_access_key") or data.get("secret_key") or data.get("AWS_SECRET_ACCESS_KEY")

            if not access_key or not secret_key:
                raise VaultError(f"Missing credentials in KV. Expected 'access_key_id' and 'secret_access_key'")

            credentials = AWSCredentials(
                access_key=access_key,
                secret_key=secret_key,
                session_token="",
                lease_id=f"kv-static-{path}",
                lease_duration=0,
                renewable=False,
            )

            logger.info(f"Obtained credentials from KV path: {kv_path}")
            return credentials

        except Exception as e:
            logger.error(f"Failed to get credentials from KV: {e}")
            raise VaultError(f"Failed to read KV credentials: {e}")

    def get_sts_credentials(
        self,
        role: str | None = None,
        ttl: str | None = None,
    ) -> AWSCredentials:
        """Get AWS credentials from Vault.

        Uses KV secrets if vault_use_kv is True, otherwise AWS Secrets Engine.

        Args:
            role: Vault AWS role name (for AWS Secrets Engine)
            ttl: Requested TTL for credentials

        Returns:
            AWSCredentials
        """
        # Use KV secrets if configured
        if settings.vault_use_kv:
            return self.get_kv_credentials()

        # Otherwise use AWS Secrets Engine
        if not self.is_connected():
            raise ConnectionError("Not connected to Vault")

        role = role or settings.vault_aws_role
        ttl = ttl or settings.lease_ttl
        mount_point = settings.vault_aws_mount_path

        logger.info(f"Requesting STS credentials from Vault role: {role}")

        try:
            response = self.client.secrets.aws.generate_credentials(
                name=role,
                role_arn=None,
                ttl=ttl,
                mount_point=mount_point,
            )

            data = response["data"]
            lease_info = response

            credentials = AWSCredentials(
                access_key=data["access_key"],
                secret_key=data["secret_key"],
                session_token=data.get("security_token", ""),
                lease_id=lease_info["lease_id"],
                lease_duration=lease_info["lease_duration"],
                renewable=lease_info["renewable"],
            )

            logger.info(
                f"Obtained STS credentials, lease_id={credentials.lease_id}, "
                f"ttl={credentials.lease_duration}s"
            )

            return credentials

        except VaultError as e:
            logger.error(f"Failed to get credentials from Vault: {e}")
            raise

    def renew_lease(self, lease_id: str, increment: int | None = None) -> dict[str, Any]:
        """Renew a credential lease.

        Args:
            lease_id: The lease ID to renew
            increment: Requested lease extension in seconds

        Returns:
            Lease renewal response with new TTL
        """
        logger.info(f"Renewing lease: {lease_id}")

        try:
            response = self.client.sys.renew_lease(
                lease_id=lease_id,
                increment=increment,
            )
            logger.info(f"Lease renewed, new ttl={response['lease_duration']}s")
            return response
        except VaultError as e:
            logger.error(f"Failed to renew lease: {e}")
            raise

    def revoke_lease(self, lease_id: str) -> None:
        """Revoke a credential lease immediately.

        This invalidates the AWS credentials before their natural expiration.

        Args:
            lease_id: The lease ID to revoke
        """
        logger.info(f"Revoking lease: {lease_id}")

        try:
            self.client.sys.revoke_lease(lease_id=lease_id)
            logger.info("Lease revoked successfully")
        except VaultError as e:
            logger.error(f"Failed to revoke lease: {e}")
            raise

    def list_leases(self, prefix: str | None = None) -> list[str]:
        """List active leases.

        Args:
            prefix: Optional prefix to filter leases

        Returns:
            List of lease IDs
        """
        prefix = prefix or f"aws/creds/{settings.vault_aws_role}"

        try:
            response = self.client.sys.list_leases(prefix=prefix)
            return response.get("data", {}).get("keys", [])
        except VaultError as e:
            logger.warning(f"Failed to list leases: {e}")
            return []
