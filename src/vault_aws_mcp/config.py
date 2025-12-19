"""Configuration management for Vault AWS MCP Server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="VAULT_AWS_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Vault configuration
    vault_addr: str = Field(
        default="http://127.0.0.1:8200",
        description="HashiCorp Vault server address",
    )
    vault_token: str | None = Field(
        default=None,
        description="Vault authentication token (optional if using other auth methods)",
    )
    vault_namespace: str | None = Field(
        default=None,
        description="Vault namespace (for Vault Enterprise)",
    )
    vault_aws_mount_path: str = Field(
        default="aws",
        description="Mount path for AWS secrets engine in Vault",
    )
    vault_aws_role: str = Field(
        default="mcp-agent-role",
        description="Vault AWS role to use for generating credentials",
    )
    vault_kv_path: str = Field(
        default="secret/aws",
        description="KV path for static AWS credentials (alternative to AWS secrets engine)",
    )
    vault_use_kv: bool = Field(
        default=True,
        description="Use KV secrets instead of AWS secrets engine",
    )

    # AWS configuration (fallback when Vault is not available)
    aws_region: str = Field(
        default="us-east-1",
        description="Default AWS region",
    )
    aws_fallback_enabled: bool = Field(
        default=False,
        description="Enable fallback to local AWS credentials when Vault is unavailable",
    )

    # Lease management
    lease_ttl: str = Field(
        default="1h",
        description="Default TTL for AWS credential leases",
    )
    lease_auto_renew: bool = Field(
        default=True,
        description="Automatically renew leases before expiration",
    )
    lease_renew_threshold_seconds: int = Field(
        default=300,
        description="Renew lease when this many seconds remain",
    )

    # Server configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )


settings = Settings()
