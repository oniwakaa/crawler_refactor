import sys
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

# Use SERVICE KEY for Admin Access
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    sys.exit(1)

supabase: Client = create_client(url, key)

def create_verified_user(email, password, full_name):
    print(f"Provisioning verified user: {email}...")
    
    try:
        attributes = {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": full_name,
                "role": "User",
                "company": "Personal"
            }
        }
        user = supabase.auth.admin.create_user(attributes)
        print(f"✅ User created successfully: {user.user.id}")
        return user.user.id
        
    except Exception as e:
        print(f"⚠️ Creation failed: {str(e)}")
        # If user already exists, we could try to verify them if we had their ID, 
        # but without ID lookup (dependent on lib version), it's harder.
        # Assuming the user knows their password or we created it just now.
        return None

if __name__ == "__main__":
    email = "carlobizzarocb@gmail.com"
    password = "Password123!"
    full_name = "Carlo Bizzaro"
    
    create_verified_user(email, password, full_name)
