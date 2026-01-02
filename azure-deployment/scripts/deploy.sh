#!/bin/bash

# Azure Container Apps Deployment Script with Ollama Cloud Model Support
# This script fixes ACR identity issues and deploys the container app

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

# ============================================
# Configuration
# ============================================
RESOURCE_GROUP="rg-b2b-leadgen-eu"
APP_NAME="b2b-backend-app"
ENV_NAME="aca-env-b2b-eu"
ACR_NAME="acrb2bleadgeneu01"
IDENTITY_NAME="id-b2b-leadgen-eu"
SUBSCRIPTION_ID="5b466abb-acae-45e8-8870-9424462bbb1d"
LOCATION="westeurope"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================
# Logging Functions
# ============================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo ""
    echo "============================================"
    echo "$1"
    echo "============================================"
}

# ============================================
# Prerequisites Check
# ============================================
check_prerequisites() {
    log_section "Checking Prerequisites"

    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it from https://docs.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    fi
    log_success "Azure CLI is installed"

    # Check if user is logged in
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi
    log_success "Logged in to Azure"

    # Check if correct subscription is active
    CURRENT_SUB=$(az account show --query id -o tsv)
    if [ "$CURRENT_SUB" != "$SUBSCRIPTION_ID" ]; then
        log_warning "Current subscription is $CURRENT_SUB"
        log_info "Setting subscription to $SUBSCRIPTION_ID"
        az account set --subscription "$SUBSCRIPTION_ID"
    fi
    log_success "Correct subscription is active: $SUBSCRIPTION_ID"
}

# ============================================
# Step 1: Verify Current Deployment State
# ============================================
verify_current_state() {
    log_section "Step 1: Verifying Current Deployment State"

    # Check if container app exists
    if ! az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
        log_warning "Container app $APP_NAME does not exist yet"
        return 0
    fi

    log_info "Container app exists: $APP_NAME"

    # Get current app state
    APP_STATE=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.runningState" \
        --output tsv)

    log_info "Current state: $APP_STATE"

    # Check registry configuration
    log_info "Checking registry configuration..."
    az containerapp registry list \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --output json || true

    # Check identity configuration
    log_info "Checking identity configuration..."
    az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "identity" \
        --output json || true
}

# ============================================
# Step 2: Fix ACR Managed Identity
# ============================================
fix_acr_identity() {
    log_section "Step 2: Fixing ACR Managed Identity"

    # Get identity resource ID
    IDENTITY_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ManagedIdentity/userAssignedIdentities/$IDENTITY_NAME"

    log_info "Using identity: $IDENTITY_NAME"
    log_info "Identity resource ID: $IDENTITY_RESOURCE_ID"

    # Check if identity exists
    if ! az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
        log_error "Identity $IDENTITY_NAME does not exist in resource group $RESOURCE_GROUP"
        exit 1
    fi
    log_success "Identity exists: $IDENTITY_NAME"

    # Get identity principal ID
    PRINCIPAL_ID=$(az identity show \
        --name "$IDENTITY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query principalId \
        --output tsv)

    log_info "Principal ID: $PRINCIPAL_ID"

    # Get ACR resource ID
    ACR_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ContainerRegistry/registries/$ACR_NAME"

    log_info "ACR resource ID: $ACR_ID"

    # Check if ACR exists
    if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
        log_error "ACR $ACR_NAME does not exist in resource group $RESOURCE_GROUP"
        exit 1
    fi
    log_success "ACR exists: $ACR_NAME"

    # Check AcrPull role assignment
    log_info "Checking AcrPull role assignment..."
    ROLE_ASSIGNMENT=$(az role assignment list \
        --assignee "$PRINCIPAL_ID" \
        --scope "$ACR_ID" \
        --query "[?roleDefinitionName=='AcrPull']" \
        --output json)

    if [ -z "$ROLE_ASSIGNMENT" ] || [ "$ROLE_ASSIGNMENT" == "[]" ]; then
        log_warning "AcrPull role not assigned. Assigning now..."

        # Assign AcrPull role
        az role assignment create \
            --assignee "$PRINCIPAL_ID" \
            --scope "$ACR_ID" \
            --role AcrPull \
            --output none

        log_success "AcrPull role assigned to identity"
    else
        log_success "AcrPull role already assigned"
    fi

    # Update container app to use identity for registry
    log_info "Updating container app registry configuration..."

    # Remove old registry configuration if exists
    az containerapp registry remove \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --server "${ACR_NAME}.azurecr.io" \
        --only-show-errors \
        2>/dev/null || true

    # Add registry with managed identity
    az containerapp registry set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --server "${ACR_NAME}.azurecr.io" \
        --identity "$IDENTITY_RESOURCE_ID" \
        --only-show-errors

    log_success "Registry configured with managed identity"
}

# ============================================
# Step 3: Configure Secrets
# ============================================
configure_secrets() {
    log_section "Step 3: Configuring Secrets"

    # Check if OLLAMA_API_KEY is set as environment variable
    if [ -z "$OLLAMA_API_KEY" ]; then
        log_warning "OLLAMA_API_KEY environment variable is not set"
        log_info "You can set it before running this script:"
        log_info "export OLLAMA_API_KEY='your-api-key-here'"
        log_info ""
        log_info "Or get your API key from: https://ollama.com/settings/keys"

        # Prompt for API key
        echo ""
        read -p "Enter your Ollama API key (or press Enter to skip and configure later): " OLLAMA_API_KEY_INPUT

        if [ -z "$OLLAMA_API_KEY_INPUT" ]; then
            log_warning "OLLAMA_API_KEY will be set to empty. You must configure it later!"
            OLLAMA_API_KEY=""
        else
            OLLAMA_API_KEY="$OLLAMA_API_KEY_INPUT"
        fi
    else
        log_success "OLLAMA_API_KEY found in environment variable"
    fi

    # Set secrets
    log_info "Setting secrets..."

    az containerapp secret set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --secrets \
            supabase-url="${SUPABASE_URL:-SET_VIA_ENV}" \
            supabase-key="${SUPABASE_KEY:-SET_VIA_ENV}" \
            firecrawl-key="${FIRECRAWL_KEY:-SET_VIA_ENV}" \
            ollama-api-key="$OLLAMA_API_KEY" \
        --only-show-errors

    log_success "Secrets configured"

    if [ -z "$OLLAMA_API_KEY" ]; then
        log_warning "OLLAMA_API_KEY is empty. You must set it for cloud models to work!"
        log_info "Set it with:"
        log_info "az containerapp secret set --name $APP_NAME --resource-group $RESOURCE_GROUP --secrets ollama-api-key='your-key'"
    fi
}

# ============================================
# Step 4: Deploy Container App
# ============================================
deploy_container_app() {
    log_section "Step 4: Deploying Container App"

    YAML_PATH="$(dirname "$0")/../container-app-cloud.yaml"

    if [ ! -f "$YAML_PATH" ]; then
        log_error "YAML file not found: $YAML_PATH"
        exit 1
    fi

    log_info "Using YAML file: $YAML_PATH"

    # Deploy using YAML
    log_info "Deploying container app..."

    az containerapp update \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --yaml "$YAML_PATH" \
        --only-show-errors

    log_success "Container app deployment initiated"
}

# ============================================
# Step 5: Monitor Deployment
# ============================================
monitor_deployment() {
    log_section "Step 5: Monitoring Deployment"

    log_info "Waiting for deployment to complete..."
    log_info "This may take 2-5 minutes..."

    # Wait for up to 10 minutes
    MAX_WAIT=600
    ELAPSED=0

    while [ $ELAPSED -lt $MAX_WAIT ]; do
        # Check if app is running
        STATE=$(az containerapp show \
            --name "$APP_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --query "properties.runningState" \
            --output tsv 2>/dev/null || echo "Unknown")

        if [ "$STATE" == "Running" ]; then
            log_success "Container app is running!"
            break
        elif [ "$STATE" == "Failed" ] || [ "$STATE" == "Degraded" ]; then
            log_error "Container app is in $STATE state"
            log_info "Checking logs for errors..."
            az containerapp logs show \
                --name "$APP_NAME" \
                --resource-group "$RESOURCE_GROUP" \
                --tail 50 \
                --only-show-errors || true
            exit 1
        fi

        log_info "Current state: $STATE. Waiting... (${ELAPSED}s/$MAX_WAIT)"
        sleep 30
        ELAPSED=$((ELAPSED + 30))
    done

    if [ $ELAPSED -ge $MAX_WAIT ]; then
        log_error "Deployment timed out after $MAX_WAIT seconds"
        exit 1
    fi
}

# ============================================
# Step 6: Verify Deployment
# ============================================
verify_deployment() {
    log_section "Step 6: Verifying Deployment"

    # Check replicas
    log_info "Checking replicas..."
    REPLICAS=$(az containerapp replica list \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "length(@)" \
        --output tsv)

    log_info "Number of replicas: $REPLICAS"

    if [ "$REPLICAS" -eq 0 ]; then
        log_error "No replicas found"
        exit 1
    fi

    log_success "Replicas are running"

    # Get FQDN
    FQDN=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv)

    log_success "Application URL: https://$FQDN"

    # Test health endpoint
    log_info "Testing health endpoint..."
    sleep 30  # Wait for containers to fully start

    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$FQDN/health" || echo "000")

    if [ "$HEALTH_STATUS" == "200" ]; then
        log_success "Health endpoint is responding (HTTP $HEALTH_STATUS)"
    else
        log_warning "Health endpoint returned HTTP $HEALTH_STATUS"
        log_info "This might be normal if containers are still starting up"
    fi

    # Show recent logs
    log_info "Recent logs (main-app):"
    az containerapp logs show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --container main-app \
        --tail 20 \
        --only-show-errors || true

    log_info ""
    log_info "Recent logs (ollama-sidecar):"
    az containerapp logs show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --container ollama-sidecar \
        --tail 20 \
        --only-show-errors || true
}

# ============================================
# Step 7: Post-Deployment Instructions
# ============================================
post_deployment_instructions() {
    log_section "Post-Deployment Instructions"

    log_success "Deployment completed successfully!"
    echo ""
    log_info "Next Steps:"
    echo ""
    echo "1. If you haven't set OLLAMA_API_KEY, set it now:"
    echo "   az containerapp secret set --name $APP_NAME --resource-group $RESOURCE_GROUP --secrets ollama-api-key='your-api-key'"
    echo ""
    echo "2. Monitor logs:"
    echo "   az containerapp logs show --name $APP_NAME --resource-group $RESOURCE_GROUP --follow"
    echo ""
    echo "3. Check replica status:"
    echo "   az containerapp replica list --name $APP_NAME --resource-group $RESOURCE_GROUP"
    echo ""
    echo "4. Test the /search endpoint:"
    echo "   curl -X POST https://$FQDN/search \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"query\": \"test\", \"max_results\": 1}'"
    echo ""
    echo "5. Run validation tests:"
    echo "   ./azure-deployment/scripts/validate.sh"
    echo ""
    echo "6. If you encounter issues, check the troubleshooting guide in:"
    echo "   azure-deployment/container-app-cloud.yaml"
    echo ""
}

# ============================================
# Main Execution
# ============================================
main() {
    log_info "Azure Container Apps Deployment Script"
    log_info "Resource Group: $RESOURCE_GROUP"
    log_info "Container App: $APP_NAME"
    log_info "Location: $LOCATION"
    echo ""

    # Run deployment steps
    check_prerequisites
    verify_current_state
    fix_acr_identity
    configure_secrets
    deploy_container_app
    monitor_deployment
    verify_deployment
    post_deployment_instructions

    log_section "Deployment Complete!"
    log_success "Your container app is now deployed with Ollama Cloud Model support"
}

# Run main function
main "$@"
