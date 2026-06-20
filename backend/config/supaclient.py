from supabase import create_client, Client

from backend.config.secrets import get_azure_secret

SUPABASE_URL = get_azure_secret("SUPABASE-URL")

# Prefer the service role key (bypasses RLS for backend operations).
# Falls back to the anon key if the service role key hasn't been added yet.
_service_key = get_azure_secret("SUPABASE-SERVICE-ROLE-KEY")
SUPABASE_KEY = _service_key or get_azure_secret("SUPABASE-KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)