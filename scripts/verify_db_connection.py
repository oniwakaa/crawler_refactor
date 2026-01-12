import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv
import uuid
import datetime

load_dotenv()

def verify_supabase():
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("MISSING URL OR KEY")
        return

    print(f"Connecting to {url} with key ending in ...{key[-5:]}")
    
    try:
        supabase: Client = create_client(url, key)
        print("Client initialized.")
        
        # Step 1: Get a valid User ID
        print("Fetching a valid User ID from profiles...")
        valid_user_id = None
        try:
            # Try getting from profiles
            response = supabase.table("profiles").select("id").limit(1).execute()
            if response.data:
                valid_user_id = response.data[0]['id']
                print(f"Found user_id from profiles: {valid_user_id}")
            else:
                # Try getting from existing jobs if profiles are empty/locked
                 print("No profiles found. Checking existing jobs for user_id...")
                 response = supabase.table("jobs").select("user_id").limit(1).execute()
                 if response.data and response.data[0]['user_id']:
                     valid_user_id = response.data[0]['user_id']
                     print(f"Found user_id from jobs: {valid_user_id}")
        except Exception as e:
            print(f"Failed to fetch user_id: {e}")

        if not valid_user_id:
            print("CRITICAL: Could not find a valid user_id. Cannot proceed with INSERT tests due to foreign key constraints.")
            print("Skipping Write Tests.")
            return

        # Step 2: Test Job Insert
        print("Testing INSERT permission on 'jobs'...")
        job_id = str(uuid.uuid4())
        try:
            dummy_job = {
                "id": job_id,
                "query": "verification_test_e2e",
                "status": "pending",
                "user_id": valid_user_id
            }
            supabase.table("jobs").insert(dummy_job).execute()
            print(f"INSERT 'jobs' SUCCESS. Job ID: {job_id}")
            
        except Exception as e:
             print(f"INSERT 'jobs' FAILED: {e}")
             return

        # Step 3: Test Lead Insert
        print("Testing INSERT permission on 'leads'...")
        try:
            dummy_lead = {
                "job_id": job_id,
                "name": "Test Lead",
                "company": "Test Corp",
                "role": "Tester",
                "email": "test@example.com", # Valid format
                "confidence_score": 0.9,
                "metadata": {"source": "verification_script"}
            }
            supabase.table("leads").insert(dummy_lead).execute()
            print("INSERT 'leads' SUCCESS.")
            
        except Exception as e:
            print(f"INSERT 'leads' FAILED: {e}")
            
        # Cleanup
        try:
            print("Cleaning up...")
            supabase.table("jobs").delete().eq("id", job_id).execute()
            print("Cleanup done.")
        except Exception as e:
             print(f"Cleanup failed (manual delete might be needed for job {job_id}): {e}")

    except Exception as master_e:
        print(f"Initialization FAILED: {master_e}")

if __name__ == "__main__":
    verify_supabase()
