#!/bin/bash
set -e

RESOURCE_GROUP="rg-b2b-leadgen-eu"
APP_NAME="b2b-backend-app"
IMAGE_TAG="b2b-backend:v4"
ACR_NAME="acrb2bleadgeneu01"

echo "Updating Container App image only..."
# This respects existing secrets and config, only changing the image
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --image "$ACR_NAME.azurecr.io/$IMAGE_TAG" \
  --container-name "main-app" \
  --output table

echo "Deployment update initiated."
