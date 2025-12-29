#!/bin/bash
set -e

ACA_NAME="b2b-backend-app"
RESOURCE_GROUP="rg-b2b-leadgen-eu"
KEY_FILE="config/ollama_key"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ ! -f "$KEY_FILE" ]; then
    echo "Error: Key file $KEY_FILE not found!"
    exit 1
fi

echo -e "${BLUE}Reading key from $KEY_FILE...${NC}"
SECRET_VALUE=$(cat $KEY_FILE)

echo -e "${BLUE}Updating secret 'ollama-key' in Container App $ACA_NAME...${NC}"
az containerapp secret set \
  --name $ACA_NAME \
  --resource-group $RESOURCE_GROUP \
  --secrets "ollama-key=$SECRET_VALUE"

echo -e "${GREEN}Secret updated successfully!${NC}"
