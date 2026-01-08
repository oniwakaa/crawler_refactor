import os
import sys
from dotenv import load_dotenv
from supabase import create_client
import json

# Adjust path to include root for imports if needed, but we can just use direct supabase here
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not set.")
        return

    supabase = create_client(url, key)
    
    try:
        # Fetch latest job
        response = supabase.table("jobs") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        if not response.data:
            print("No jobs found.")
            return

        job = response.data[0]
        print(json.dumps(job, indent=2, default=str))
        
        # If job ID exists, lets also check if there are any leads for it
        job_id = job.get("id")
        if job_id:
            leads_resp = supabase.table("leads") \
                .select("count", count="exact") \
                .eq("job_id", job_id) \
                .execute()
            print(f"\nLeads found for this job: {leads_resp.count}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
