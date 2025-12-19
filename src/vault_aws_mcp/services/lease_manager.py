"""Lease Manager - handles automatic renewal and cleanup of Vault leases."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from ..config import settings
from .vault_client import VaultClient

logger = logging.getLogger(__name__)


@dataclass
class LeaseInfo:
    """Information about an active lease."""

    lease_id: str
    created_at: datetime
    duration: int  # seconds
    renewable: bool
    last_renewed: datetime | None = None
    renewal_count: int = 0

    @property
    def expires_at(self) -> datetime:
        """Calculate when this lease expires."""
        base_time = self.last_renewed or self.created_at
        return base_time + timedelta(seconds=self.duration)

    @property
    def seconds_remaining(self) -> int:
        """Get seconds remaining until expiration."""
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))

    @property
    def needs_renewal(self) -> bool:
        """Check if lease should be renewed based on threshold."""
        return (
            self.renewable
            and self.seconds_remaining <= settings.lease_renew_threshold_seconds
        )


@dataclass
class LeaseManager:
    """Manages Vault lease lifecycle - renewal, tracking, and cleanup.

    This manager:
    - Tracks all active leases
    - Automatically renews leases before expiration
    - Provides cleanup on shutdown
    - Emits callbacks when leases expire
    """

    vault_client: VaultClient
    _leases: dict[str, LeaseInfo] = field(default_factory=dict)
    _renewal_task: asyncio.Task | None = field(default=None, repr=False)
    _running: bool = field(default=False)
    _on_lease_expired: Callable[[str], None] | None = field(default=None, repr=False)

    def register_lease(
        self,
        lease_id: str,
        duration: int,
        renewable: bool = True,
    ) -> LeaseInfo:
        """Register a new lease for tracking.

        Args:
            lease_id: The Vault lease ID
            duration: Lease duration in seconds
            renewable: Whether the lease can be renewed

        Returns:
            LeaseInfo object for the registered lease
        """
        lease_info = LeaseInfo(
            lease_id=lease_id,
            created_at=datetime.now(),
            duration=duration,
            renewable=renewable,
        )
        self._leases[lease_id] = lease_info

        logger.info(
            f"Registered lease {lease_id[:16]}..., "
            f"expires in {duration}s, renewable={renewable}"
        )

        return lease_info

    def unregister_lease(self, lease_id: str) -> None:
        """Remove a lease from tracking.

        Args:
            lease_id: The lease ID to remove
        """
        if lease_id in self._leases:
            del self._leases[lease_id]
            logger.debug(f"Unregistered lease {lease_id[:16]}...")

    def get_lease(self, lease_id: str) -> LeaseInfo | None:
        """Get information about a tracked lease."""
        return self._leases.get(lease_id)

    @property
    def active_leases(self) -> list[LeaseInfo]:
        """Get all active leases."""
        return list(self._leases.values())

    @property
    def leases_needing_renewal(self) -> list[LeaseInfo]:
        """Get leases that need to be renewed."""
        return [lease for lease in self._leases.values() if lease.needs_renewal]

    async def renew_lease(self, lease_id: str) -> bool:
        """Renew a specific lease.

        Args:
            lease_id: The lease to renew

        Returns:
            True if renewal succeeded, False otherwise
        """
        lease_info = self._leases.get(lease_id)
        if not lease_info:
            logger.warning(f"Attempted to renew unknown lease: {lease_id[:16]}...")
            return False

        if not lease_info.renewable:
            logger.warning(f"Lease {lease_id[:16]}... is not renewable")
            return False

        try:
            response = self.vault_client.renew_lease(lease_id)

            # Update lease info
            lease_info.last_renewed = datetime.now()
            lease_info.duration = response["lease_duration"]
            lease_info.renewal_count += 1

            logger.info(
                f"Renewed lease {lease_id[:16]}..., "
                f"new duration={lease_info.duration}s, "
                f"renewal #{lease_info.renewal_count}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to renew lease {lease_id[:16]}...: {e}")
            return False

    async def revoke_lease(self, lease_id: str) -> bool:
        """Revoke a specific lease.

        Args:
            lease_id: The lease to revoke

        Returns:
            True if revocation succeeded
        """
        try:
            self.vault_client.revoke_lease(lease_id)
            self.unregister_lease(lease_id)
            return True
        except Exception as e:
            logger.error(f"Failed to revoke lease {lease_id[:16]}...: {e}")
            return False

    async def revoke_all_leases(self) -> None:
        """Revoke all tracked leases. Call on shutdown."""
        logger.info(f"Revoking {len(self._leases)} active leases")

        for lease_id in list(self._leases.keys()):
            await self.revoke_lease(lease_id)

    async def _renewal_loop(self) -> None:
        """Background task that renews leases before expiration."""
        logger.info("Starting lease renewal loop")

        while self._running:
            try:
                # Check for leases needing renewal
                for lease in self.leases_needing_renewal:
                    await self.renew_lease(lease.lease_id)

                # Check for expired leases
                now = datetime.now()
                for lease_id, lease in list(self._leases.items()):
                    if lease.expires_at <= now:
                        logger.warning(f"Lease {lease_id[:16]}... has expired")
                        self.unregister_lease(lease_id)
                        if self._on_lease_expired:
                            self._on_lease_expired(lease_id)

                # Sleep before next check (check every 30 seconds)
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in renewal loop: {e}")
                await asyncio.sleep(5)

        logger.info("Lease renewal loop stopped")

    async def start(self, on_lease_expired: Callable[[str], None] | None = None) -> None:
        """Start the lease manager background tasks.

        Args:
            on_lease_expired: Callback when a lease expires
        """
        if self._running:
            return

        self._running = True
        self._on_lease_expired = on_lease_expired

        if settings.lease_auto_renew:
            self._renewal_task = asyncio.create_task(self._renewal_loop())

        logger.info("Lease manager started")

    async def stop(self) -> None:
        """Stop the lease manager and cleanup."""
        logger.info("Stopping lease manager")
        self._running = False

        if self._renewal_task:
            self._renewal_task.cancel()
            try:
                await self._renewal_task
            except asyncio.CancelledError:
                pass

        # Revoke all active leases on shutdown
        await self.revoke_all_leases()

        logger.info("Lease manager stopped")
