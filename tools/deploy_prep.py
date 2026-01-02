import os
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def main():
    # Read YAML
    yaml_path = Path("container-app-eu.yaml")
    if not yaml_path.exists():
        print("container-app-eu.yaml not found!")
        return
    
    # Get Managed Env ID (EU)
    try:
        result = subprocess.run(
            ["az", "containerapp", "env", "show", "--name", "aca-env-b2b-eu", "--resource-group", "rg-b2b-leadgen-eu", "--query", "id", "-o", "json"], 
            capture_output=True, text=True, check=True
        )
        env_id = json.loads(result.stdout)
        print(f"Found Managed Env ID: {env_id}")
    except Exception as e:
        print(f"Error getting managed env ID: {e}")
        return

    # Get ACR Password
    try:
        acr_result = subprocess.run(
            ["az", "acr", "credential", "show", "--name", "acrb2bleadgeneu01", "--query", "passwords[0].value", "-o", "tsv"],
            capture_output=True, text=True, check=True
        )
        acr_password = acr_result.stdout.strip()
    except Exception as e:
        print(f"Error getting ACR password: {e}")
        return

    content = yaml_path.read_text()
    
    # Replacements
    replacements = {
        "<MANAGED_ENV_ID>": env_id,
        "<SUPABASE_URL>": os.getenv("SUPABASE_URL", ""),
        "<SUPABASE_SERVICE_KEY>": os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", ""),
        "<FIRECRAWL_API_KEY>": os.getenv("FIRECRAWL_API_KEY", ""),
        "<ACR_PASSWORD>": acr_password
    }
    
    for key, value in replacements.items():
        if not value:
            print(f"Warning: Value for {key} is missing in environment.")
        content = content.replace(key, value)
        
    # Write to new file
    output_path = Path("container-app-deployed.yaml")
    output_path.write_text(content)
    print(f"Created {output_path} with injected secrets.")

if __name__ == "__main__":
    main()
