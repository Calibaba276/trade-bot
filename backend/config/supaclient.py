from supabase import create_client, Client

from backend.config.secrets import get_azure_secret

SUPABASE_URL = get_azure_secret("SUPABASE-URL")
SUPABASE_KEY = get_azure_secret("SUPABASE-KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)