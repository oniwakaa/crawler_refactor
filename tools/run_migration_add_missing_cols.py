
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def run_migration():
    """
    Adds remaining missing columns (phone_number, source_url) to the leads table.
    """
    logger.info("NOTE: Please run this SQL in your Supabase SQL Editor:")
    logger.info("ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS phone_number text;")
    logger.info("ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS source_url text;")

if __name__ == "__main__":
    run_migration()
