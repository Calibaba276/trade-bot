"""
vault.py
--------
Thin wrapper around Azure Key Vault for fetching MT5 credentials.

Design decisions:
  - Uses DefaultAzureCredential — on the Azure VM this automatically picks up
    the Managed Identity with zero configuration. No client secrets, no env
    vars beyond the vault URL.
  - Secrets are cached in-process for the lifetime of the worker. MT5
    credentials don't rotate mid-session, so re-fetching on every signal
    would be wasteful and add latency.
  - Cache can be explicitly invalidated per secret name — useful if you
    rotate a password and restart a specific worker without restarting all.
  - The `password` field in broker_accounts rows is treated as the secret
    name. Column name stays as `password` — this module is the only place
    that knows the value is a Key Vault reference, not a plaintext password.

Usage in worker.py:
    from vault import VaultClient

    vault  = VaultClient(vault_url=os.environ["AZURE_VAULT_URL"])
    secret = vault.get_secret(account["password"])   # account["password"] is the secret name
    mt5.initialize(..., password=secret, ...)
"""

from __future__ import annotations

import threading
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import (
    ResourceNotFoundError,
    HttpResponseError,
    ClientAuthenticationError,
)

from ..config.logger import setup_logger

logger = setup_logger(__name__)
GLASS_BOX_VAULT_URL = "https://glass-box.vault.azure.net/"


class VaultClient:
    """
    Process-level Key Vault client with in-memory secret caching.

    One instance is sufficient per worker process — instantiate once at
    startup and pass the reference wherever credentials are needed.
    """

    def __init__(self, vault_url: Optional[str] = None) -> None:
        """
        Args:
            vault_url: Full vault URI, e.g. https://glass-box.vault.azure.net/
                       Defaults to https://glass-box.vault.azure.net/ if not passed.
        """
        self._vault_url = vault_url or GLASS_BOX_VAULT_URL
        if not self._vault_url:
            raise RuntimeError(
                "Vault URL not provided. Pass vault_url= or configure GLASS_BOX_VAULT_URL."
            )

        # DefaultAzureCredential tries credential sources in order:
        #   1. Environment variables (useful for local dev / CI)
        #   2. Workload Identity (AKS)
        #   3. Managed Identity  ← what fires on the Azure VM in production
        #   4. Azure CLI         ← what fires on your local dev machine
        # No configuration needed — it just works in both environments.
        self._credential = DefaultAzureCredential()
        self._client     = SecretClient(
            vault_url=self._vault_url,
            credential=self._credential,
        )

        # Cache: secret_name → plaintext value
        # Protected by a lock so multiple worker threads can share one instance
        # safely if needed (though typically one VaultClient per process).
        self._cache: dict[str, str] = {}
        self._lock  = threading.Lock()

        logger.info(f"[VAULT] Client initialised — vault={self._vault_url}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_secret(self, secret_name: str) -> str:
        """
        Fetch a secret by name, returning the plaintext value.

        Returns from cache on subsequent calls within the same process.
        Raises RuntimeError on auth failure or missing secret so the
        worker fails fast at startup rather than silently using a bad password.

        Args:
            secret_name: The value stored in broker_accounts.password —
                         e.g. "mt5-123456-ICMarkets-password"
        """
        with self._lock:
            if secret_name in self._cache:
                logger.debug(f"[VAULT] Cache hit — secret={secret_name}")
                return self._cache[secret_name]

        # Fetch outside the lock so one slow network call doesn't block
        # other threads trying to read different secrets simultaneously.
        value = self._fetch(secret_name)

        with self._lock:
            self._cache[secret_name] = value

        return value

    def invalidate(self, secret_name: str) -> None:
        """
        Remove a secret from the cache.

        Call this before restarting a worker after a password rotation so
        the next get_secret() call fetches the new value from Key Vault.
        """
        with self._lock:
            removed = self._cache.pop(secret_name, None)
        if removed is not None:
            logger.info(f"[VAULT] Cache invalidated — secret={secret_name}")

    def invalidate_all(self) -> None:
        """Clear the entire cache — forces re-fetch of all secrets."""
        with self._lock:
            self._cache.clear()
        logger.info("[VAULT] Full cache cleared")

    def prefetch(self, secret_names: list[str]) -> None:
        """
        Eagerly fetch a list of secrets at startup.

        Lets orchestrator.py warm the cache for all accounts before any
        worker subprocess needs credentials, surfacing auth errors early
        rather than mid-trade.
        """
        logger.info(f"[VAULT] Prefetching {len(secret_names)} secrets…")
        for name in secret_names:
            try:
                self.get_secret(name)
                logger.info(f"[VAULT] Prefetched — secret={name}")
            except Exception as exc:
                # Log and continue — individual worker will fail at its own startup
                logger.error(f"[VAULT] Prefetch failed for secret={name}: {exc}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch(self, secret_name: str) -> str:
        """
        Single network call to Key Vault.  All Azure SDK exceptions are
        translated into descriptive RuntimeErrors so callers don't need to
        import azure packages just to handle errors.
        """
        logger.info(f"[VAULT] Fetching secret={secret_name}")
        try:
            secret = self._client.get_secret(secret_name)

            if secret.value is None:
                raise RuntimeError(
                    f"[VAULT] Secret '{secret_name}' exists but has a null value. "
                    f"Check the Key Vault entry."
                )

            return secret.value

        except ClientAuthenticationError as exc:
            raise RuntimeError(
                f"[VAULT] Authentication failed — is the Managed Identity enabled "
                f"on the VM and granted 'Get' access to the vault?\n{exc}"
            ) from exc

        except ResourceNotFoundError:
            raise RuntimeError(
                f"[VAULT] Secret '{secret_name}' not found in vault '{self._vault_url}'. "
                f"Check the secret name in broker_accounts.password matches exactly "
                f"(case-sensitive, hyphens vs underscores)."
            ) from None

        except HttpResponseError as exc:
            raise RuntimeError(
                f"[VAULT] HTTP error fetching secret '{secret_name}': {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Module-level convenience singleton
# ---------------------------------------------------------------------------
# Lets worker.py do a simple one-liner import without managing the instance:
#
#   from vault import vault
#   password = vault.get_secret(account["password"])
#
# The singleton is initialised lazily on first access so import-time errors
# (missing env var) only surface when the module is actually used.

_singleton: Optional[VaultClient] = None
_singleton_lock = threading.Lock()


def _get_singleton() -> VaultClient:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = VaultClient()
    return _singleton


class _VaultProxy:
    """Lazy proxy so `from vault import vault` works before AZURE_VAULT_URL is set."""

    def get_secret(self, secret_name: str) -> str:
        return _get_singleton().get_secret(secret_name)

    def invalidate(self, secret_name: str) -> None:
        _get_singleton().invalidate(secret_name)

    def invalidate_all(self) -> None:
        _get_singleton().invalidate_all()

    def prefetch(self, secret_names: list[str]) -> None:
        _get_singleton().prefetch(secret_names)


vault = _VaultProxy()