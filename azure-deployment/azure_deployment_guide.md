# Azure Deployment Guide for B2B Lead Gen

**Target Audience:** Developers, AI Agents & DevOps Engineers
**Purpose:** A definitive guide to deploying the B2B Lead Gen Backend on Azure Container Apps, capturing critical configurations, secret management, and troubleshooting steps.

---

## 1. Architecture Overview

The deployment consists of an **Azure Container App** with two containers (Sidecar pattern):

1.  **`main-app`**:
    *   **Image**: `b2b-backend:v6` (Python/FastAPI)
    *   **Port**: 8000 (Target Port)
    *   **Responsibility**: API, Pipeline Orchestration, Database Interaction.
2.  **`ollama-sidecar`**:
    *   **Image**: `ollama/ollama:latest`
    *   **Port**: 11434 (Internal access only via `localhost`)
    *   **Responsibility**: Proxying requests to **Ollama Cloud Models**.

---

## 2. Ollama Cloud Models & Localhost

**What are they?**
Ollama Cloud Models (e.g., `gpt-oss:120b-cloud`) enable you to run massive models (100B+ parameters) without needing 100GB+ of VRAM locally.

**How it works with Localhost:**
1.  **The Proxy**: The `ollama-sidecar` running on `localhost:11434` acts as a lightweight **proxy**.
2.  **No Heavy Lifting**: When the main app sends a request to `localhost:11434`, the sidecar does NOT run inference locally. Instead, it securely forwards the request to Ollama's Cloud.
3.  **Authentication**: This requires an authenticated session. The sidecar must have a valid SSH key (mounted via secrets) to authorize the request with Ollama's servers.

**Why this matters:**
You can deploy a small container (e.g., 0.5 vCPU / 1GB RAM) and still access state-of-the-art 120B models. The resource usage is network-bound, not compute-bound.

---

## 3. Prerequisites & Setup

### Tools Required
- Azure CLI (`az`)
- Docker Desktop
- Python 3.11+ (for helper scripts)

### Environment Variables (`.env`)
The system relies on a local `.env` file mapped to Azure Secrets.
**Required Variables:**
```bash
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
FIRECRAWL_API_KEY=...
APIFY_API_TOKEN=...
OLLAMA_SSH_KEY=...          # CRITICAL: Required for Cloud Model access
ALLOWED_ORIGINS="https://amplify-staging.vercel.app,https://amplify-production.vercel.app"
```

---

## 4. Secret Management

Secrets are **NOT** stored in the repo. They are injected from your local `.env` file using a custom Python script.

**Script**: `tools/update_secrets.py`
- Parses `.env`.
- Maps keys to Azure Secret names (e.g., `OLLAMA_SSH_KEY` -> `ollama-ssh-key`).
- Executes `az containerapp secret set`.

**Usage:**
```bash
python tools/update_secrets.py
```

---

## 5. Deployment Workflow

### Step 1: Build & Push Docker Image
Use Azure Container Registry (ACR) to build the image.
```bash
az acr build --registry acrb2bleadgeneu01 --image b2b-backend:v6 --file backend.Dockerfile .
```

### Step 2: Configure `container-app.yaml`
Ensure the YAML references the new image tag and maps secrets to environment variables.

**Key Snippet (Secrets):**
```yaml
      env:
        - name: OLLAMA_SSH_KEY
          secretRef: ollama-ssh-key
```

### Step 3: Apply Configuration (Deploy)
Use the helper script to substitute variables (like Subscription ID) and apply the YAML.
```bash
bash tools/apply_config.sh
```

---

## 6. Critical Configurations

### CORS (Frontend Access)
CORS is handled in `server/api.py`.
- **Dynamic Regex**: We use `allow_origin_regex` to match:
    1.  Explicit `ALLOWED_ORIGINS` (from secrets).
    2.  Vercel Wildcards: `https://amplify-*.vercel.app`.

---

## 7. Verification & Troubleshooting

### Health Check
```bash
curl https://<YOUR-APP-URL>/health
# Expected: {"status":"healthy","database":"connected"}
```

### Check Logs
If the pipeline fails, check the logs. Note that network timeouts talking to Ollama Cloud can look like crashes.
```bash
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container main-app \
  --tail 100
```

### Restore Models (After Restart)
The sidecar's storage is ephemeral. After a restart, you must re-pull the manifest (which is fast for cloud models) to re-register the model proxy.
```bash
az containerapp exec \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container ollama-sidecar \
  --command "ollama pull gpt-oss:120b-cloud"
```
