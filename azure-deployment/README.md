# Azure Container Apps Deployment with Ollama Cloud Models

## 📋 Overview

This deployment configures an Azure Container App with Ollama Cloud Model support, enabling AI-powered inference without requiring local GPU resources. The architecture uses a lightweight sidecar pattern where the main application communicates with Ollama via localhost, while actual model inference runs on Ollama's cloud infrastructure.

### Key Features

- ✅ **ACR Managed Identity Authentication** - No hardcoded credentials
- ✅ **Ollama Cloud Models** - Zero local GPU requirements
- ✅ **Sidecar Architecture** - Main app and Ollama in same pod
- ✅ **Health Probes** - Automatic monitoring and recovery
- ✅ **Minimal Resource Usage** - 0.75 CPU cores, 1.5Gi RAM total
- ✅ **West Europe Deployment** - Optimized for your region

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│            Azure Container App (Pod)                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────┐      ┌─────────────────────┐   │
│  │   Main Application │      │  Ollama Sidecar     │   │
│  │   (Port 8000)      │◄────►│  (Port 11434)       │   │
│  │                    │      │                     │   │
│  │  • Backend Logic   │      │  • Ollama Daemon    │   │
│  │  • Supabase Client │      │  • API Proxy        │   │
│  │  • Search Endpoint │      │  • Auth Manager     │   │
│  └────────────────────┘      └─────────────────────┘   │
│           ▲                              │              │
│           │                              ▼              │
│    ┌──────┴──────────────────────────────────┐        │
│    │    Shared Volume (EmptyDir)             │        │
│    │    • Ollama auth tokens                 │        │
│    │    • Model metadata                     │        │
│    └─────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Ollama Cloud   │
                    │  (120B Model)   │
                    │  • GPU Servers  │
                    │  • Inference    │
                    └─────────────────┘
```

### Communication Flow

1. **Main App** receives `/search` request
2. **Main App** calls `http://localhost:11434/api/chat`
3. **Ollama Sidecar** validates API key and forwards request
4. **Ollama Cloud** processes inference on GPUs
5. **Response** streams back through sidecar to main app
6. **Main App** returns results to caller

---

## 📦 Prerequisites

### Required Tools

- **Azure CLI** (version 2.0.55+)
  ```bash
  # Install from: https://docs.microsoft.com/cli/azure/install-azure-cli
  az --version
  ```

- **jq** (for JSON parsing in scripts)
  ```bash
  # macOS
  brew install jq
  
  # Linux
  sudo apt-get install jq
  ```

### Azure Resources

Ensure you have:
- ✅ Active Azure subscription
- ✅ Resource group: `rg-b2b-leadgen-eu`
- ✅ Container Apps environment: `aca-env-b2b-eu`
- ✅ Azure Container Registry: `acrb2bleadgeneu01`
- ✅ Managed identity: `id-b2b-leadgen-eu`
- ✅ Container images pushed to ACR

### Ollama Account

- ✅ Ollama.com account (free)
- ✅ API key generated from: https://ollama.com/settings/keys

---

## 🚀 Quick Start

### Step 1: Set Ollama API Key

**Critical**: You must set your Ollama API key before deployment.

```bash
# Get your API key from: https://ollama.com/settings/keys
export OLLAMA_API_KEY='sk-xxxxxxxxxxxxxxxxxxxxxxxx'
```

### Step 2: Run Deployment Script

```bash
cd /Users/carlo/Desktop/pr_prj/crw_ref/azure-deployment/scripts

# Make scripts executable
chmod +x deploy.sh validate.sh

# Run deployment
./deploy.sh
```

The script will:
1. ✅ Verify prerequisites and login status
2. ✅ Check current deployment state
3. ✅ Fix ACR managed identity configuration
4. ✅ Configure secrets (Supabase, Firecrawl, Ollama)
5. ✅ Deploy container app from YAML
6. ✅ Monitor deployment status
7. ✅ Verify deployment success

### Step 3: Validate Deployment

```bash
./validate.sh
```

This runs comprehensive tests across 7 phases:
- Infrastructure validation
- Ollama sidecar validation
- Application integration
- Functionality tests
- Performance tests
- Resource validation
- External connectivity

---

## ⚙️ Configuration

### Resource Allocation

| Component | CPU | Memory | Purpose |
|-----------|-----|--------|---------|
| **main-app** | 0.5 cores | 1.0Gi | Backend logic, Supabase client |
| **ollama-sidecar** | 0.25 cores | 0.5Gi | Ollama daemon only (no model weights) |
| **Total** | **0.75 cores** | **1.5Gi** | Fits in Consumption plan |

### Environment Variables

#### Main Application

```bash
# Supabase
SUPABASE_URL=<from-secret>
SUPABASE_SERVICE_KEY=<from-secret>

# Firecrawl
FIRECRAWL_API_KEY=<from-secret>

# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:120b-cloud
OLLAMA_API_KEY=<from-secret>
OLLAMA_REQUEST_TIMEOUT=600  # 10 minutes

# Application
PORT=8000
LOG_LEVEL=INFO
```

#### Ollama Sidecar

```bash
OLLAMA_HOST=0.0.0.0:11434
OLLAMA_API_KEY=<from-secret>
OLLAMA_MODELS=/root/.ollama/models
OLLAMA_KEEP_ALIVE=-1
OLLAMA_NUM_PARALLEL=4
OLLAMA_LOAD_TIMEOUT=5m
```

### Secrets

The following secrets are configured:

| Secret Name | Value | Source |
|-------------|-------|--------|
| `supabase-url` | (Your Supabase project URL) | Set via CLI/env |
| `supabase-key` | (Your Supabase service key) | Set via CLI/env |
| `firecrawl-key` | (Your Firecrawl API key) | Set via CLI/env |
| `ollama-api-key` | (Your Ollama API key) | From https://ollama.com/settings/keys |

---

## 🔧 Manual Configuration

### Set Ollama API Key (if skipped during deployment)

```bash
az containerapp secret set \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secrets ollama-api-key='sk-your-api-key-here'

# Trigger a revision update
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix update-api-key-$(date +%s)
```

### Update Container Image

```bash
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --image acrb2bleadgeneu01.azurecr.io/b2b-backend:v2.0 \
  --revision-suffix image-update-$(date +%s)
```

### Scale Resources

```bash
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --cpu 1.0 \
  --memory 2.0Gi \
  --revision-suffix scale-up-$(date +%s)
```

---

## 🔍 Monitoring & Troubleshooting

### Check Container Status

```bash
# Get application status
az containerapp show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --query "{state: properties.runningState, url: properties.configuration.ingress.fqdn}"

# List replicas
az containerapp replica list \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --output table
```

### View Logs

```bash
# Follow all logs
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --follow

# View main-app logs
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container main-app \
  --tail 100

# View ollama-sidecar logs
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container ollama-sidecar \
  --tail 100
```

### Test Endpoints

```bash
# Get FQDN
FQDN=$(az containerapp show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

# Health check
curl "https://$FQDN/health"

# Search endpoint (simple)
curl -X POST "https://$FQDN/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "max_results": 1}'

# Search endpoint (with cloud model)
curl -X POST "https://$FQDN/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is Azure?", "max_results": 2}'
```

### Common Issues

#### Issue: ImagePullBackOff

**Symptom**: Container fails to start with "ImagePullBackOff"

**Solution**:
```bash
# Check registry configuration
az containerapp registry list \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu

# Verify AcrPull role is assigned
PRINCIPAL_ID=$(az identity show \
  --name id-b2b-leadgen-eu \
  --resource-group rg-b2b-leadgen-eu \
  --query principalId -o tsv)

az role assignment list \
  --assignee $PRINCIPAL_ID \
  --scope "/subscriptions/5b466abb-acae-45e8-8870-9424462bbb1d/resourceGroups/rg-b2b-leadgen-eu/providers/Microsoft.ContainerRegistry/registries/acrb2bleadgeneu01" \
  --query "[?roleDefinitionName=='AcrPull']"
```

#### Issue: Ollama Authentication Failed

**Symptom**: "Unauthorized" or "401" errors in logs

**Solution**:
```bash
# Verify API key is set
az containerapp secret show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secret-name ollama-api-key

# If empty, set it
az containerapp secret set \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secrets ollama-api-key='your-new-key'

# Redeploy
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix fix-auth-$(date +%s)
```

#### Issue: /search Timeout

**Symptom**: Requests timeout after 300 seconds

**Solution**:
```bash
# Check if Ollama sidecar is running
az containerapp replica list \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --query "[0].properties.containers[?name=='ollama-sidecar']"

# Increase timeout in configuration
# Update OLLAMA_REQUEST_TIMEOUT env var to 900 (15 minutes)

# Use smaller model for testing
# Change OLLAMA_MODEL to qwen2.5:7b-cloud
```

#### Issue: Container Restart Loop

**Symptom**: Containers keep restarting

**Solution**:
```bash
# Check recent logs
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container main-app \
  --tail 50

# Check health probe configuration
az containerapp show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --query 'properties.template.containers[].probes'

# Increase probe timeouts if needed
```

---

## 📊 Performance & Scaling

### Expected Performance

| Metric | Target | Notes |
|--------|--------|-------|
| **Cold Start** | < 60s | First request after deployment |
| **Warm Request** | < 30s | Subsequent requests |
| **Cloud Model (120B)** | 30-90s | Depends on query complexity |
| **Concurrent Requests** | 4+ | Limited by OLLAMA_NUM_PARALLEL |
| **Throughput** | ~40 req/hr | With default resources |

### Scaling Strategies

#### Vertical Scaling (Increase Resources)

```bash
# Scale up for better performance
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --cpu 1.0 \
  --memory 2.0Gi \
  --revision-suffix scale-up-$(date +%s)
```

#### Horizontal Scaling (Multiple Replicas)

```bash
# Enable multiple replicas
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --min-replicas 2 \
  --max-replicas 5 \
  --revision-suffix scale-out-$(date +%s)
```

#### Workload Profiles (Dedicated Resources)

```bash
# Move to Dedicated workload profile for better performance
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --workload-profile-name dedicated-profile \
  --revision-suffix dedicated-$(date +%s)
```

---

## 💰 Cost Considerations

### Azure Costs

| Resource | Cost (Monthly) | Notes |
|----------|----------------|-------|
| **Container App** | ~$10-30 | Consumption plan, pay-per-use |
| **Egress Data** | ~$0.087/GB | Outbound data transfer |
| **ACR** | ~$5-10 | Standard tier |

### Ollama Cloud Costs

- **Free tier**: Limited requests per month
- **Paid tier**: Per-request pricing (check https://ollama.com/pricing)
- **Note**: Only cloud model usage incurs costs, local models are free

### Cost Optimization Tips

1. ✅ Use smaller models when possible (e.g., `qwen2.5:7b-cloud` instead of `gpt-oss:120b-cloud`)
2. ✅ Cache responses to reduce API calls
3. ✅ Use streaming responses for better UX
4. ✅ Monitor and adjust replica count based on traffic
5. ✅ Set appropriate timeouts to avoid hanging requests

---

## 🔒 Security

### Managed Identity

- ✅ No hardcoded ACR credentials
- ✅ AcrPull role assigned to managed identity
- ✅ Automatic token rotation by Azure

### Secrets Management

- ✅ Secrets stored in Azure Container Apps
- ✅ Not visible in logs or diagnostics
- ✅ Can be rotated without redeployment

### Network Security

- ✅ Internal communication via localhost
- ✅ No public exposure of Ollama port
- ✅ TLS termination at Azure edge

---

## 📚 Additional Resources

### Official Documentation

- **Azure Container Apps**: https://learn.microsoft.com/azure/container-apps/
- **Ollama Cloud Models**: https://ollama.com/blog/cloud
- **ACR Managed Identity**: https://learn.microsoft.com/azure/container-registry/container-registry-authentication-managed-identity
- **Ollama API**: https://github.com/ollama/ollama/blob/main/docs/api.md

### Available Cloud Models

Browse available models at: https://ollama.com/search?c=cloud

Popular options:
- `gpt-oss:120b-cloud` - 120B parameters (current default)
- `qwen2.5:7b-cloud` - 7B parameters (faster, cheaper)
- `gemma3:27b-cloud` - 27B parameters (balanced)

### Tools & Utilities

```bash
# Install Azure CLI extensions
az extension add --name containerapp
az extension add --name log-analytics

# Install jq for JSON parsing
brew install jq  # macOS
sudo apt-get install jq  # Linux
```

---

## 🆘 Support

### Getting Help

1. Check logs: `az containerapp logs show --follow`
2. Run validation: `./scripts/validate.sh`
3. Review troubleshooting section above
4. Check Azure status: https://status.azure.com/

### Contact Information

- **Project Repository**: `/Users/carlo/Desktop/pr_prj/crw_ref`
- **Deployment Scripts**: `/Users/carlo/Desktop/pr_prj/crw_ref/azure-deployment/scripts`
- **Configuration**: `/Users/carlo/Desktop/pr_prj/crw_ref/azure-deployment/container-app-cloud.yaml`

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-XX | Initial deployment with Ollama Cloud support |
| 1.1 | 2025-01-XX | Added comprehensive validation scripts |
| 1.2 | 2025-01-XX | Fixed ACR managed identity configuration |

---

## ✅ Deployment Checklist

Before deploying, ensure:

- [ ] Azure CLI installed and logged in
- [ ] Correct subscription is active (`5b466abb-acae-45e8-8870-9424462bbb1d`)
- [ ] Ollama API key generated and set in environment
- [ ] Container images pushed to ACR (`acrb2bleadgeneu01`)
- [ ] Managed identity exists (`id-b2b-leadgen-eu`)
- [ ] Resource group exists (`rg-b2b-leadgen-eu`)
- [ ] Environment exists (`aca-env-b2b-eu`)

After deploying, verify:

- [ ] Container app is running (not Degraded/Failed)
- [ ] Both containers are ready
- [ ] Health endpoint returns 200
- [ ] /search endpoint returns valid JSON
- [ ] Ollama sidecar is accessible via localhost
- [ ] No ImagePullBackOff errors in logs
- [ ] AcrPull role is assigned to identity

---

**Deployment completed successfully! 🎉**

For issues or questions, refer to the troubleshooting section or run the validation script.