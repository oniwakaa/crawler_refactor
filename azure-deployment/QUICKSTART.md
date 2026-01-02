# Quick Start Guide - Azure Container Apps Deployment

## 🚀 Get Deployed in 5 Minutes

### Prerequisites Check
```bash
# 1. Verify Azure CLI is installed
az --version

# 2. Verify you're logged in
az account show

# 3. Install jq (for scripts)
brew install jq  # macOS
# OR
sudo apt-get install jq  # Linux
```

---

### Step 1: Get Your Ollama API Key (Required!)

⚠️ **You MUST do this first or cloud models won't work!**

1. Go to https://ollama.com and sign up (free)
2. Navigate to https://ollama.com/settings/keys
3. Click "Create API Key"
4. Copy the key (starts with `sk-`)
5. Set it as environment variable:

```bash
export OLLAMA_API_KEY='sk-your-actual-api-key-here'
```

---

### Step 2: Run Deployment

```bash
# Navigate to deployment scripts
cd /Users/carlo/Desktop/pr_prj/crw_ref/azure-deployment/scripts

# Make scripts executable
chmod +x deploy.sh validate.sh

# Run deployment (this takes 2-5 minutes)
./deploy.sh
```

**What this does:**
- ✅ Fixes ACR managed identity authentication
- ✅ Configures all secrets (Supabase, Firecrawl, Ollama)
- ✅ Deploys container app with Ollama sidecar
- ✅ Sets up health probes and monitoring
- ✅ Monitors deployment until it's running

---

### Step 3: Validate Deployment

```bash
# Run comprehensive validation tests
./validate.sh
```

**This tests:**
- Container app is running
- ACR images are pulling successfully
- Ollama sidecar is accessible
- `/search` endpoint is working
- Cloud models are accessible

**Expected Result:** Most tests should pass (✓). Some may be skipped (!) if you haven't set the API key yet.

---

### Step 4: Test Your Application

```bash
# Get your app URL
FQDN=$(az containerapp show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

echo "Your app URL: https://$FQDN"

# Test health endpoint
curl "https://$FQDN/health"

# Test search endpoint
curl -X POST "https://$FQDN/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "max_results": 1}'
```

---

## 🎯 What's Been Deployed

| Component | URL | Purpose |
|-----------|-----|---------|
| **Main App** | `https://<your-app>.azurecontainerapps.io` | Backend with `/search` endpoint |
| **Ollama Sidecar** | `localhost:11434` (internal) | Proxies requests to Ollama Cloud |
| **Supabase** | Pre-configured | Data storage |

---

## 📊 Resource Usage

Your deployment uses minimal resources:

| Resource | Amount | Cost |
|----------|--------|------|
| **CPU** | 0.75 cores total | ~$10-30/month |
| **Memory** | 1.5Gi total | Included in base cost |
| **Ollama Cloud** | Pay-per-request | Free tier available |

---

## 🔧 Common Commands

### Check Deployment Status
```bash
az containerapp show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --query "{state: properties.runningState, url: properties.configuration.ingress.fqdn}"
```

### View Logs
```bash
# Follow all logs
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --follow

# View specific container logs
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container ollama-sidecar \
  --tail 50
```

### Update API Key
```bash
az containerapp secret set \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secrets ollama-api-key='sk-new-key-here'

az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix update-key-$(date +%s)
```

---

## ⚠️ Troubleshooting Quick Fixes

### Problem: ImagePullBackOff
```bash
# This means ACR authentication failed
# The deployment script should have fixed this, but if not:

# 1. Verify AcrPull role is assigned
PRINCIPAL_ID=$(az identity show \
  --name id-b2b-leadgen-eu \
  --resource-group rg-b2b-leadgen-eu \
  --query principalId -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --scope "/subscriptions/5b466abb-acae-45e8-8870-9424462bbb1d/resourceGroups/rg-b2b-leadgen-eu/providers/Microsoft.ContainerRegistry/registries/acrb2bleadgeneu01" \
  --role AcrPull

# 2. Redeploy
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix fix-acr-$(date +%s)
```

### Problem: Cloud Model Authentication Failed
```bash
# This means your OLLAMA_API_KEY is not set or invalid

# 1. Verify key is set
az containerapp secret show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secret-name ollama-api-key

# 2. If missing, set it
az containerapp secret set \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secrets ollama-api-key='sk-your-key'

# 3. Redeploy
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix fix-key-$(date +%s)
```

### Problem: /search Timeout
```bash
# Cloud models can take 30-90 seconds for first request
# If it times out after 300s:

# 1. Check if Ollama sidecar is running
az containerapp replica list \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu

# 2. Increase timeout (edit container-app-cloud.yaml)
# Set OLLAMA_REQUEST_TIMEOUT=900

# 3. Or use a smaller/faster model
# Set OLLAMA_MODEL=qwen2.5:7b-cloud
```

---

## 📚 Next Steps & Documentation

### For More Details:
- **Full Documentation**: `azure-deployment/README.md`
- **Ollama Setup**: `azure-deployment/OLLAMA_SETUP.md`
- **Configuration**: `azure-deployment/container-app-cloud.yaml`

### Learn More:
- **Azure Container Apps**: https://learn.microsoft.com/azure/container-apps/
- **Ollama Cloud Models**: https://ollama.com/blog/cloud
- **Available Models**: https://ollama.com/search?c=cloud

---

## ✅ Success Indicators

Your deployment is successful if:

- [ ] Container app shows "Running" status
- [ ] Both containers (main-app and ollama-sidecar) are ready
- [ ] `/health` endpoint returns 200
- [ ] `/search` endpoint returns valid JSON
- [ ] Validation script shows mostly passing tests

---

## 🎉 You're Live!

Your Azure Container App with Ollama Cloud Models is now deployed and ready to use!

**Application URL:** Check the output of Step 4

**Expected Performance:**
- First request: 30-60 seconds (cold start)
- Subsequent requests: 10-30 seconds (warm)
- Cloud model (120B): 30-90 seconds per query

---

**Need Help?** Run `./validate.sh` for detailed diagnostics or check the full README.