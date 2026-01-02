#!/bin/bash
set -e

# Configuration
RESOURCE_GROUP="rg-b2b-leadgen-eu"
LOCATION="westeurope"
IDENTITY_NAME="id-b2b-leadgen-eu"
ACR_NAME="acrb2bleadgeneu01"
ACA_NAME="aca-b2b-app"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting ACR Authentication Setup...${NC}"

# 1. Create User Assigned Identity
echo -e "${BLUE}Creating Managed Identity: ${IDENTITY_NAME}...${NC}"
az identity create --name $IDENTITY_NAME --resource-group $RESOURCE_GROUP --location $LOCATION

# Get Identity ID and Principal ID
echo -e "${BLUE}Retrieving Identity Details...${NC}"
IDENTITY_ID=$(az identity show --name $IDENTITY_NAME --resource-group $RESOURCE_GROUP --query id --output tsv)
PRINCIPAL_ID=$(az identity show --name $IDENTITY_NAME --resource-group $RESOURCE_GROUP --query principalId --output tsv)
echo "Identity ID: $IDENTITY_ID"
echo "Principal ID: $PRINCIPAL_ID"

# 2. Grant AcrPull Permission
echo -e "${BLUE}Granting AcrPull permission to Identity on ACR ${ACR_NAME}...${NC}"
ACR_ID=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query id --output tsv)

MAX_RETRIES=10
RETRY_COUNT=0
until az role assignment create --assignee $PRINCIPAL_ID --scope $ACR_ID --role AcrPull 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}Failed to grant role assignment after $MAX_RETRIES attempts.${NC}"
        exit 1
    fi
    echo "Principal not ready yet. Retrying in 10 seconds... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 10
done

# 3. Assign Identity to Container App (Config update happens in YAML, but we ensure identity exists on the resource)
# Note: The YAML update will actually handle the binding, but we can pre-assign here to be safe and verify.
echo -e "${BLUE}Ensuring Identity is assigned to Container App ${ACA_NAME}...${NC}"
# We will use the YAML deployment to formally assign it, but let's print the ID for the YAML file.

echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}Use the following Identity ID in your container-app.yaml:${NC}"
echo "$IDENTITY_ID"

# Save ID to a temp file for next steps if needed
echo "$IDENTITY_ID" > .identity_id_created
