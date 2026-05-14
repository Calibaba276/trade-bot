from functools import lru_cache
import logging

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from .logger import setup_logger

VAULT_URL = "https://glass-box.vault.azure.net/"
logger = setup_logger(__name__)


@lru_cache(maxsize=1)
def _get_secret_client():
    credentials = DefaultAzureCredential()
    return SecretClient(VAULT_URL, credentials)


def get_azure_secret(name):
    """Helper to pull secrets from Azure."""
    try:
        return _get_secret_client().get_secret(name).value
    except Exception as e:
        logger.error(f"Error fetching {name}: {e}")
        return None
