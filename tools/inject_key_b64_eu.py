import subprocess
import base64

PRIVATE_KEY_CONTENT = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtz
c2gtZWQyNTUxOQAAACCIiyiil8FwPj4XXPVOocH3cTaiDrxoFYVpLGvla7AiRQAA
AIgZ0oW5GdKFuQAAAAtzc2gtZWQyNTUxOQAAACCIiyiil8FwPj4XXPVOocH3cTai
DrxoFYVpLGvla7AiRQAAAEBthsneKGCglrRGuV7MhEXrleKVdvc0GhSO3KmCT2IV
BYiLKKKXwXA+Phdc9U6hwfdxNqIOvGgVhWksa+VrsCJFAAAAAAECAwQF
-----END OPENSSH PRIVATE KEY-----"""

def main():
    b64_key = base64.b64encode(PRIVATE_KEY_CONTENT.encode('utf-8')).decode('utf-8')
    target = "/root/.ollama/id_ed25519"
    cmd_str = f"mkdir -p /root/.ollama && echo {b64_key} | base64 -d > {target} && chmod 600 {target} && ls -l {target}"
    
    print(f"Injecting key to {target}...")
    
    full_cmd = [
        "az", "containerapp", "exec", 
        "--name", "b2b-backend-app", 
        "--resource-group", "rg-b2b-leadgen-eu",
        "--container", "ollama-sidecar", 
        "--command", f"sh -c '{cmd_str}'"
    ]
    
    try:
        subprocess.run(full_cmd, check=True)
        print("Success.")
    except subprocess.CalledProcessError as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()
