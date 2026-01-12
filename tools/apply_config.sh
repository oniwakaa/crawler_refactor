#!/bin/bash
set -e

# Load env vars
set -a
source .env
set +a

# Get Subscription ID if not set
if [ -z "$SUBSCRIPTION_ID" ]; then
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
fi
export SUBSCRIPTION_ID

echo "Applying configuration from azure-deployment/container-app.yaml..."

# Substitute variables and update
envsubst '${SUBSCRIPTION_ID}' < azure-deployment/container-app.yaml > azure-deployment/container-app-processed.yaml

az containerapp update \
    --name b2b-backend-app \
    --resource-group rg-b2b-leadgen-eu \
    --yaml azure-deployment/container-app-processed.yaml

echo "Configuration updated successfully."
rm azure-deployment/container-app-processed.yaml
