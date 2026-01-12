
import os
import subprocess
import sys

def main():
    secrets = {}
    try:
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("'").strip('"')
                    secrets[key] = value
    except FileNotFoundError:
        print("Error: .env file not found")
        sys.exit(1)

    # Map env vars to secret names
    mapping = {
        "SUPABASE_URL": "supabase-url",
        "SUPABASE_SERVICE_KEY": "supabase-key",
        "FIRECRAWL_API_KEY": "firecrawl-key",
        "APIFY_API_TOKEN": "apify-key",
        "ALLOWED_ORIGINS": "allowed-origins"
        # "OLLAMA_SSH_KEY": "ollama-ssh-key" # Skip complex handling for now, assume done
    }

    cmd_args = []
    for env_var, secret_name in mapping.items():
        if env_var in secrets:
            val = secrets[env_var]
            cmd_args.append(f"{secret_name}={val}")
        else:
            print(f"Warning: {env_var} not found in .env")

    if not cmd_args:
        print("No valid secrets found to update.")
        sys.exit(1)

    cmd = [
        "az", "containerapp", "secret", "set",
        "--name", "b2b-backend-app",
        "--resource-group", "rg-b2b-leadgen-eu",
        "--secrets"
    ] + cmd_args

    print(f"Executing: {' '.join(cmd[:8])} [secrets hidden]")
    
    # Execute
    subprocess.check_call(cmd)
    print("Secrets updated successfully.")

if __name__ == "__main__":
    main()
