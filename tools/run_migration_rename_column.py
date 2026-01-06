
import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def run_migration():
    """
    Renames the linkedin_url column to linkedin to match the specific Pydantic model
    in the currently deployed application.
    """
    logger.info("NOTE: Please run this SQL in your Supabase SQL Editor:")
    logger.info("ALTER TABLE public.leads RENAME COLUMN linkedin_url TO linkedin;")

if __name__ == "__main__":
    run_migration()
