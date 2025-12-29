#!/bin/bash

ACA_NAME="b2b-backend-app"
RESOURCE_GROUP="rg-b2b-leadgen-eu"
ENDPOINT_URL=$(az containerapp show --name $ACA_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn --output tsv)

echo "App URL: https://$ENDPOINT_URL"

echo "Checking Revision Status..."
az containerapp revision list --name $ACA_NAME --resource-group $RESOURCE_GROUP --output table

echo "Waiting for 10 seconds for service to stabilize..."
sleep 10

echo "Testing /search endpoint..."
START_TIME=$(date +%s)
# Simple search query test
curl -s -w "\nResponse Code: %{http_code}\nTime: %{time_total}s\n" \
  -X POST "https://$ENDPOINT_URL/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "software companies in berlin", "max_results": 1}' > search_result.json

END_TIME=$(date +%s)
echo "Total Script Duration: $((END_TIME - START_TIME)) seconds"

cat search_result.json
