#!/usr/bin/env python3
import requests
import json
import time
import subprocess
import sys
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def get_valid_user_id():
    """Fetch a valid user_id from Supabase to ensure FK constraints are met."""
    print("Fetching valid user_id from Supabase...")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("Warning: Missing SUPABASE_URL or keys in .env. Using fallback ID.")
        return "240a01b6-3d01-4702-82d5-5158673388a0" # Fallback

    try:
        supabase = create_client(url, key)
        # Try profiles
        response = supabase.table("profiles").select("id").limit(1).execute()
        if response.data:
            return response.data[0]['id']
        
        # Try jobs
        response = supabase.table("jobs").select("user_id").limit(1).execute()
        if response.data:
             return response.data[0]['user_id']
             
        print("Warning: No profiles or jobs found. Using fallback ID.")
        return "240a01b6-3d01-4702-82d5-5158673388a0"
    except Exception as e:
        print(f"Error fetching user_id: {e}")
        return "240a01b6-3d01-4702-82d5-5158673388a0"

def get_azure_fqdn(app_name="b2b-backend-app", resource_group="rg-b2b-leadgen-eu"):
    print(f"Fetching FQDN for {app_name}...")
    try:
        cmd = [
            "az", "containerapp", "show",
            "--name", app_name,
            "--resource-group", resource_group,
            "--query", "properties.configuration.ingress.fqdn",
            "--output", "tsv"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        fqdn = result.stdout.strip()
        print(f"FQDN: {fqdn}")
        return fqdn
    except subprocess.CalledProcessError as e:
        print(f"Error fetching FQDN: {e.stderr}")
        sys.exit(1)

def run_test(fqdn):
    base_url = f"https://{fqdn}"
    search_endpoint = f"{base_url}/search"
    
    user_id = get_valid_user_id()
    print(f"Using User ID: {user_id}")
    
    payload = {
        "query": "Founder Italiani of Tech Startups",
        "max_results": 5,
        "user_id": user_id
    }
    
    print(f"Starting Search Request to {search_endpoint}...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    start_time = time.time()
    
    # 1. Initiate Search
    try:
        resp = requests.post(search_endpoint, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        job_id = data.get("job_id")
        print(f"Job Initiated. ID: {job_id}")
    except Exception as e:
        print(f"Failed to initiate search: {e}")
        try:
             print(f"Response: {resp.text}")
        except:
             pass
        # Capture logs immediately if failed
        capture_logs(tail=50)
        sys.exit(1)

    # 2. Poll for Completion
    status_endpoint = f"{base_url}/jobs/{job_id}"
    print(f"Polling Status at {status_endpoint}...")
    
    max_retries = 60 # 5 minutes max (5s * 60)
    for i in range(max_retries):
        try:
            status_resp = requests.get(status_endpoint, timeout=30)
            status_resp.raise_for_status()
            status_data = status_resp.json()
            status = status_data.get("status")
            
            elapsed = time.time() - start_time
            print(f"[{elapsed:.1f}s] Status: {status}")
            
            if status == "completed":
                print("\nSUCCESS: Job Completed!")
                print(f"Total Duration: {elapsed:.2f}s")
                print("Result Metadata:")
                print(json.dumps(status_data, indent=2))
                return True
            elif status == "failed":
                print("\nFAILURE: Job Failed.")
                print(f"Error: {status_data.get('error')}")
                capture_logs(tail=100)
                return False
            
            time.sleep(5)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

    print("\nTIMEOUT: Job did not complete in time.")
    capture_logs(tail=100)
    return False

def capture_logs(tail=100):
    print("\nCapturing Azure Container App Logs...")
    try:
        cmd = [
            "az", "containerapp", "logs", "show",
            "--name", "b2b-backend-app",
            "--resource-group", "rg-b2b-leadgen-eu",
            "--tail", str(tail)
        ]
        subprocess.run(cmd, check=False)
    except Exception as e:
        print(f"Failed to capture logs: {e}")

if __name__ == "__main__":
    fqdn = get_azure_fqdn()
    success = run_test(fqdn)
    if not success:
        sys.exit(1)
