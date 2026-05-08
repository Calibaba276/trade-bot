from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

VAULT_URL = "https://calibabasecret.vault.azure.net/"


@lru_cache(maxsize=1)
def _get_secret_client():
    credentials = DefaultAzureCredential()
    return SecretClient(VAULT_URL, credentials)


def get_azure_secret(name):
    """Helper to pull secrets from Azure."""
    try:
        return _get_secret_client().get_secret(name).value
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return None

