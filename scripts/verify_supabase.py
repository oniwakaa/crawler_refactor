import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

from server.db import supabase

def test_connection():
    print(f"Testing Supabase connection to {os.environ.get('SUPABASE_URL')}...")
    
    tables_to_check = ["leads", "profiles", "user_settings", "conversations", "messages"]
    
    for table in tables_to_check:
        try:
            print(f"Checking table '{table}'...")
            # We limit to 0 just to check metadata/existence without fetching rows
            response = supabase.table(table).select("*").limit(0).execute()
            print(f"✅ Table '{table}' exists.")
        except Exception as e:
            error_msg = str(e)
            if "relation" in error_msg and "does not exist" in error_msg:
                 print(f"❌ Table '{table}' DOES NOT EXIST.")
            elif "404" in error_msg: # Supabase/PostgREST often returns 404 for missing table
                 print(f"❌ Table '{table}' NOT FOUND (404).")
            else:
                print(f"⚠️ Error checking '{table}': {error_msg}")

if __name__ == "__main__":
    test_connection()
