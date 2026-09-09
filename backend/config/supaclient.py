from supabase import create_client, Client

from functools import lru_cache
from backend.config.secrets import get_azure_secret

SUPABASE_URL = get_azure_secret("SUPABASE-URL")
SUPABASE_KEY = get_azure_secret("SUPABASE-KEY")

@lru_cache(maxsize=2)
def supabase(SUPABASE_URL, SUPABASE_KEY) -> Client:
    client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return client