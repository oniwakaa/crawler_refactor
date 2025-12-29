import sys
import os
import time
import uuid
from dotenv import load_dotenv
from supabase import create_client, Client

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    sys.exit(1)

supabase: Client = create_client(url, key)

def test_signup_raw():
    # Use a gmail alias which is usually trusted but unique
    unique_id = int(time.time())
    test_email = f"carlo.bizzaro.test+{unique_id}@gmail.com"
    test_password = "Password123!"
    
    print(f"Attempting signup for: {test_email}")
    
    try:
        response = supabase.auth.sign_up({
            "email": test_email,
            "password": test_password,
            "options": {
                "data": {
                    "full_name": "Debug User",
                    "role": "Tester",
                    "company": "DebugCorp"
                }
            }
        })
        
        if response.user:
            print(f"✅ Signup Successful! User ID: {response.user.id}")
            print(f"Confirmation sent: {response.user.confirmation_sent_at}")
        else:
            print("⚠️ Signup returned no user object (unexpected success state?)")
            
    except Exception as e:
        print("\n❌ SIGNUP FAILED")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        
        # Try to inspect deeper if it's an API error
        if hasattr(e, 'code'):
            print(f"Status Code: {e.code}")
        if hasattr(e, 'details'):
            print(f"Details: {e.details}")

if __name__ == "__main__":
    test_signup_raw()
