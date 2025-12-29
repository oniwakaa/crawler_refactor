import os
from supabase import create_client, Client
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger()

# Load environment variables
load_dotenv()

def get_supabase_client() -> Client:
    """
    Initialize and return the Supabase client.
    Uses SUPABASE_SERVICE_KEY if available (for admin access), 
    otherwise falls back to SUPABASE_ANON_KEY.
    """
    url: str = os.environ.get("SUPABASE_URL")
    
    # Prefer Service Key for backend operations (bypass RLS)
    key: str = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

    if not url:
        logger.error("SUPABASE_URL is missing from environment variables")
        raise ValueError("SUPABASE_URL is missing")
        
    if not key:
        logger.error("Supabase Key (SERVICE or ANON) is missing from environment variables")
        raise ValueError("Supabase Key is missing")

    try:
        client: Client = create_client(url, key)
        return client
    except Exception as e:
        logger.error("Failed to initialize Supabase client", error=str(e))
        raise

# Singleton instance
supabase = get_supabase_client()
