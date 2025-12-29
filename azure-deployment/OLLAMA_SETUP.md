# Ollama API Key Setup Guide

## 🎯 Purpose

This guide will help you obtain and configure your Ollama API key, which is required for using Ollama Cloud Models in your Azure Container Apps deployment.

**Why is this needed?**
- Ollama Cloud Models require authentication via API key
- The API key enables your container to access 120B+ parameter models without local GPU requirements
- Without this key, cloud model requests will fail with "Unauthorized" errors

---

## 📝 Prerequisites

- ✅ An email address (for Ollama account)
- ✅ Web browser (Chrome, Firefox, Safari, or Edge)
- ✅ Terminal/Command line access (for configuring Azure)
- ✅ Azure CLI installed and logged in

---

## 🚀 Step-by-Step Setup

### Step 1: Create Ollama Account

1. **Navigate to Ollama**
   - Go to: https://ollama.com
   - Click "Sign Up" in the top-right corner

2. **Create Account**
   - Enter your email address
   - Create a password
   - Click "Create Account"

3. **Verify Email**
   - Check your inbox for verification email
   - Click the verification link
   - Your account is now active!

4. **Sign In**
   - Click "Sign In" in the top-right corner
   - Enter your email and password
   - Click "Sign In"

**Note**: Ollama offers a free tier with limited API calls. Check pricing at https://ollama.com/pricing for usage limits.

---

### Step 2: Generate API Key

1. **Access Settings**
   - After signing in, click on your profile icon (top-right)
   - Select "Settings" from the dropdown menu
   - Or go directly to: https://ollama.com/settings

2. **Navigate to API Keys**
   - In the left sidebar, click "API Keys"
   - Or go directly to: https://ollama.com/settings/keys

3. **Create New API Key**
   - Click the "Create API Key" button
   - A modal will appear

4. **Name Your Key (Optional)**
   - Enter a descriptive name (e.g., "Azure Container Apps - Production")
   - This helps you identify keys in your dashboard
   - Click "Create"

5. **Copy Your API Key**
   - ⚠️ **IMPORTANT**: Your API key will be shown only once!
   - Copy it immediately to a secure location
   - Format: `sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - The key starts with `sk-` followed by alphanumeric characters

6. **Store Safely**
   - Save the key in a password manager
   - Never commit it to Git repositories
   - Never share it publicly

**Example API Key Format:**
```
sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```

---

### Step 3: Configure API Key in Azure

#### Option A: Using Deployment Script (Recommended)

```bash
# 1. Set the API key as an environment variable
export OLLAMA_API_KEY='sk-your-actual-api-key-here'

# 2. Run the deployment script
cd /Users/carlo/Desktop/pr_prj/crw_ref/azure-deployment/scripts
./deploy.sh

# The script will automatically:
# - Prompt for API key if not set
# - Configure it as a secret in Azure
# - Deploy the container app
```

#### Option B: Manual Configuration

```bash
# 1. Set the secret directly in Azure Container Apps
az containerapp secret set \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secrets ollama-api-key='sk-your-actual-api-key-here'

# 2. Trigger a revision update to apply the secret
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix update-api-key-$(date +%s)

# 3. Wait for deployment to complete
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --follow
```

#### Option C: Using Azure Portal

1. **Navigate to Container App**
   - Go to Azure Portal: https://portal.azure.com
   - Search for "Container Apps"
   - Select `b2b-backend-app`
   - Go to "Settings" → "Secrets"

2. **Add Secret**
   - Click "Add secret"
   - Name: `ollama-api-key`
   - Value: `sk-your-actual-api-key-here`
   - Click "Add"

3. **Apply Changes**
   - Click "Apply" to save
   - This triggers a new revision deployment

4. **Monitor Deployment**
   - Go to "Overview" tab
   - Watch the "Revision" status
   - Wait for "Running" state

---

### Step 4: Verify API Key Configuration

#### Test 1: Check Secret is Set

```bash
az containerapp secret show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secret-name ollama-api-key
```

**Expected Output:**
```json
{
  "name": "ollama-api-key",
  "value": "sk-************"  # Masked value is normal
}
```

#### Test 2: Verify Ollama Sidecar Can Access API

```bash
# Execute a command in the Ollama sidecar container
az containerapp exec \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container ollama-sidecar \
  --command "curl -s http://localhost:11434/api/tags | head -20"
```

**Expected Output:**
```json
{
  "models": [
    {
      "name": "gpt-oss:120b-cloud",
      "modified_at": "2024-01-01T00:00:00Z",
      "size": 0,
      "digest": "sha256:..."
    }
  ]
}
```

**If you see an error:**
```
{"error":"Unauthorized"} or {"error":"401"}
```
→ Your API key is invalid or not configured properly. Return to Step 3.

#### Test 3: Run Full Validation

```bash
cd /Users/carlo/Desktop/pr_prj/crw_ref/azure-deployment/scripts
./validate.sh
```

Look for these test results:
- ✅ `OLLAMA_API_KEY secret is configured`
- ✅ `Cloud model metadata accessible`
- ✅ `/search endpoint with Cloud Model` passes

---

## 🔐 Security Best Practices

### ✅ Do:
- Store API keys in password managers (1Password, Bitwarden, etc.)
- Use environment variables for scripts
- Rotate keys periodically (every 90 days)
- Monitor usage in Ollama dashboard
- Use separate keys for different environments (dev/staging/prod)

### ❌ Don't:
- Never commit API keys to Git
- Never hardcode keys in application code
- Never share keys via email or chat
- Never log keys in console output
- Never use production keys in development

---

## 🔄 Rotating API Key

### When to Rotate:
- ✅ Key has been compromised
- ✅ Every 90 days (best practice)
- ✅ When changing team members
- ✅ Suspected unauthorized usage

### How to Rotate:

```bash
# 1. Generate new API key in Ollama dashboard
#    (Follow Step 2 above)

# 2. Update secret in Azure
az containerapp secret set \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secrets ollama-api-key='sk-new-api-key-here'

# 3. Trigger revision update
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix rotate-api-key-$(date +%s)

# 4. Verify new key is working
az containerapp exec \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container ollama-sidecar \
  --command "curl -s http://localhost:11434/api/tags"

# 5. Delete old key in Ollama dashboard
#    Go to: https://ollama.com/settings/keys
#    Find old key and click "Delete"
```

---

## 🐛 Troubleshooting

### Issue: "API key not found" Error

**Symptoms:**
- Logs show: `API key not found` or `Missing API key`
- Deployment fails validation tests

**Solutions:**

```bash
# 1. Check if secret exists
az containerapp secret list \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --query "[?name=='ollama-api-key']"

# 2. If missing, create it
az containerapp secret set \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secrets ollama-api-key='sk-your-key'

# 3. Redeploy to apply
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix fix-secret-$(date +%s)
```

---

### Issue: "Unauthorized" or "401" Error

**Symptoms:**
- Cloud model requests fail with 401/403 errors
- Ollama API returns authentication errors

**Solutions:**

```bash
# 1. Verify API key is correct
#    Double-check you copied the full key including 'sk-' prefix

# 2. Test API key manually
curl https://ollama.com/api/tags \
  -H "Authorization: Bearer sk-your-actual-key-here"

# 3. If manual test fails, regenerate key
#    Go to: https://ollama.com/settings/keys
#    Delete old key, create new one

# 4. Update secret with new key
az containerapp secret set \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --secrets ollama-api-key='sk-new-key'

# 5. Redeploy
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix fix-auth-$(date +%s)
```

---

### Issue: "Rate limit exceeded" Error

**Symptoms:**
- Requests fail with rate limit errors
- Intermittent failures after some requests

**Solutions:**

```bash
# 1. Check your usage in Ollama dashboard
#    Go to: https://ollama.com/settings/usage

# 2. Wait for rate limit to reset
#    Free tier limits: ~100 requests/day (varies)

# 3. Upgrade to paid tier if needed
#    Go to: https://ollama.com/pricing

# 4. Implement request caching in your app
#    Reduce unnecessary API calls
```

---

### Issue: Container not picking up new secret

**Symptoms:**
- Secret is updated but container still uses old key
- Changes not reflected in running container

**Solutions:**

```bash
# 1. Force revision update
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --revision-suffix force-update-$(date +%s)

# 2. Wait for new revision to be active
az containerapp revision list \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu

# 3. Scale down to 0, then back up (nuclear option)
az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --min-replicas 0

# Wait for scale down...
sleep 60

az containerapp update \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --min-replicas 1
```

---

## 📊 Monitoring API Usage

### Check Usage in Ollama Dashboard

1. **Navigate to Usage**
   - Go to: https://ollama.com/settings/usage
   - View current month's usage
   - Check rate limit status

2. **Set Up Alerts** (if available)
   - Configure usage threshold alerts
   - Get notified before hitting limits

### Monitor in Azure

```bash
# Check logs for API errors
az containerapp logs show \
  --name b2b-backend-app \
  --resource-group rg-b2b-leadgen-eu \
  --container ollama-sidecar \
  --tail 100 | grep -i "api\|key\|auth\|error"
```

---

## 🎓 Additional Resources

### Documentation
- **Ollama Cloud Models**: https://ollama.com/blog/cloud
- **API Documentation**: https://github.com/ollama/ollama/blob/main/docs/api.md
- **Pricing**: https://ollama.com/pricing
- **Terms of Service**: https://ollama.com/terms

### Support
- **Ollama Support**: https://ollama.com/support
- **Community Forum**: https://github.com/ollama/ollama/discussions
- **Twitter/X**: @ollama

---

## ✅ Setup Checklist

Before proceeding with deployment:

- [ ] Created Ollama account
- [ ] Verified email address
- [ ] Generated API key
- [ ] Copied API key to secure location
- [ ] Set API key as environment variable: `export OLLAMA_API_KEY='...'`
- [ ] Verified API key format (starts with `sk-`)
- [ ] Ran deployment script with API key
- [ ] Verified secret is configured in Azure
- [ ] Tested Ollama sidecar can access API
- [ ] Ran validation script successfully

---

## 🎉 You're Ready!

Once you've completed the checklist, your Azure Container Apps deployment is ready to use Ollama Cloud Models!

**Next Steps:**
1. Run the deployment script: `./azure-deployment/scripts/deploy.sh`
2. Run validation: `./azure-deployment/scripts/validate.sh`
3. Test the `/search` endpoint
4. Monitor usage in Ollama dashboard

**Need Help?**
- Check the troubleshooting section above
- Review the main README: `azure-deployment/README.md`
- Run validation script for detailed diagnostics

---

**Happy deploying! 🚀**