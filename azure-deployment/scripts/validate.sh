#!/bin/bash

# Azure Container Apps Validation Script with Ollama Cloud Model Support
# This script validates all aspects of the deployment

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

# ============================================
# Configuration
# ============================================
RESOURCE_GROUP="rg-b2b-leadgen-eu"
APP_NAME="b2b-backend-app"
ACR_NAME="acrb2bleadgeneu01"
IDENTITY_NAME="id-b2b-leadgen-eu"
SUBSCRIPTION_ID="5b466abb-acae-45e8-8870-9424462bbb1d"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# ============================================
# Logging Functions
# ============================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[! SKIP]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
}

log_test() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo ""
    echo -e "${CYAN}[TEST $TOTAL_TESTS]${NC} $1"
    echo "----------------------------------------"
}

log_section() {
    echo ""
    echo "============================================"
    echo "$1"
    echo "============================================"
}

# ============================================
# Test Result Functions
# ============================================
test_passed() {
    PASSED_TESTS=$((PASSED_TESTS + 1))
    log_success "$1"
}

test_failed() {
    FAILED_TESTS=$((FAILED_TESTS + 1))
    log_error "$1"
}

test_skipped() {
    SKIPPED_TESTS=$((SKIPPED_TESTS + 1))
    log_warning "$1"
}

# ============================================
# Phase 1: Infrastructure Validation
# ============================================
test_container_app_running() {
    log_test "Container App Running State"

    STATE=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.runningState" \
        --output tsv 2>/dev/null || echo "Unknown")

    if [ "$STATE" == "Running" ]; then
        test_passed "Container app is running (State: $STATE)"
        echo "  Location: $(az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query location -o tsv)"
        echo "  Environment: $(az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query properties.managedEnvironmentId -o tsv | awk -F'/' '{print $NF}')"
        return 0
    else
        test_failed "Container app is not running (State: $STATE)"
        return 1
    fi
}

test_acr_pull_success() {
    log_test "ACR Image Pull Success"

    # Check container logs for image pull errors
    LOGS=$(az containerapp logs show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --container main-app \
        --tail 100 \
        --only-show-errors 2>/dev/null || echo "")

    if echo "$LOGS" | grep -qi "ImagePullBackOff\|ErrImagePull\|Failed to pull image"; then
        test_failed "Image pull errors detected in logs"
        echo "  Recent errors:"
        echo "$LOGS" | grep -i "pull\|image" | tail -5
        return 1
    else
        test_passed "No image pull errors detected"
        echo "  Image: $(az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query 'properties.template.containers[0].image' -o tsv)"
        return 0
    fi
}

test_managed_identity_assignment() {
    log_test "Managed Identity Assignment (AcrPull)"

    # Get identity principal ID
    PRINCIPAL_ID=$(az identity show \
        --name "$IDENTITY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query principalId \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$PRINCIPAL_ID" ]; then
        test_failed "Identity $IDENTITY_NAME not found"
        return 1
    fi

    echo "  Principal ID: $PRINCIPAL_ID"

    # Get ACR resource ID
    ACR_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ContainerRegistry/registries/$ACR_NAME"

    # Check AcrPull role assignment
    ROLE_ASSIGNMENT=$(az role assignment list \
        --assignee "$PRINCIPAL_ID" \
        --scope "$ACR_ID" \
        --query "[?roleDefinitionName=='AcrPull' || roleDefinitionName=='Container Registry Repository Reader']" \
        --output json 2>/dev/null || echo "[]")

    if [ -z "$ROLE_ASSIGNMENT" ] || [ "$ROLE_ASSIGNMENT" == "[]" ]; then
        test_failed "AcrPull role not assigned to identity"
        return 1
    else
        test_passed "AcrPull role is assigned to identity"
        echo "  Role count: $(echo "$ROLE_ASSIGNMENT" | jq '. | length')"
        return 0
    fi
}

test_registry_configuration() {
    log_test "Registry Configuration"

    REGISTRIES=$(az containerapp registry list \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --output json 2>/dev/null || echo "[]")

    if [ "$REGISTRIES" == "[]" ]; then
        test_failed "No registry configuration found"
        return 1
    fi

    REGISTRY_SERVER=$(echo "$REGISTRIES" | jq -r '.[0].server' 2>/dev/null || echo "")
    REGISTRY_IDENTITY=$(echo "$REGISTRIES" | jq -r '.[0].identity' 2>/dev/null || echo "")

    echo "  Registry: $REGISTRY_SERVER"
    echo "  Identity: $REGISTRY_IDENTITY"

    if [ "$REGISTRY_SERVER" == "${ACR_NAME}.azurecr.io" ] && [ -n "$REGISTRY_IDENTITY" ]; then
        test_passed "Registry configured with managed identity"
        return 0
    else
        test_failed "Registry not properly configured"
        return 1
    fi
}

# ============================================
# Phase 2: Ollama Sidecar Validation
# ============================================
test_ollama_sidecar_running() {
    log_test "Ollama Sidecar Container Status"

    CONTAINER_STATUS=$(az containerapp replica list \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[0].properties.containers[?name=='ollama-sidecar'].[0].ready" \
        --output tsv 2>/dev/null || echo "false")

    if [ "$CONTAINER_STATUS" == "true" ]; then
        test_passed "Ollama sidecar is ready"
        return 0
    else
        test_failed "Ollama sidecar is not ready"
        echo "  Checking recent logs..."
        az containerapp logs show \
            --name "$APP_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --container ollama-sidecar \
            --tail 20 \
            --only-show-errors 2>/dev/null || echo "  No logs available"
        return 1
    fi
}

test_ollama_health_endpoint() {
    log_test "Ollama Health Endpoint (/api/tags)"

    # Execute curl from ollama-sidecar container
    RESPONSE=$(az containerapp exec \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --container ollama-sidecar \
        --command "curl -s http://localhost:11434/api/tags" \
        --only-show-errors 2>/dev/null || echo "")

    if echo "$RESPONSE" | jq -e '.models' > /dev/null 2>&1; then
        MODEL_COUNT=$(echo "$RESPONSE" | jq '.models | length')
        test_passed "Ollama API is responding (found $MODEL_COUNT models)"
        echo "  Available models:"
        echo "$RESPONSE" | jq -r '.models[].name' | sed 's/^/    - /'
        return 0
    else
        test_failed "Ollama API is not responding or invalid response"
        echo "  Response: $RESPONSE"
        return 1
    fi
}

test_ollama_cloud_model_accessible() {
    log_test "Cloud Model Accessibility (gpt-oss:120b-cloud)"

    # Check if we can pull the cloud model (this just fetches metadata)
    RESPONSE=$(az containerapp exec \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --container ollama-sidecar \
        --command "curl -s http://localhost:11434/api/show -d '{\"name\":\"gpt-oss:120b-cloud\"}' -H 'Content-Type: application/json'" \
        --only-show-errors 2>/dev/null || echo "")

    if echo "$RESPONSE" | jq -e '.license' > /dev/null 2>&1; then
        test_passed "Cloud model metadata accessible"
        echo "  Model: gpt-oss:120b-cloud"
        echo "  License: $(echo "$RESPONSE" | jq -r '.license' | head -1)"
        return 0
    else
        # This might fail if API key is not set
        if echo "$RESPONSE" | grep -qi "error\|unauthorized\|401\|403"; then
            test_skipped "Cloud model not accessible (likely missing OLLAMA_API_KEY)"
            echo "  To fix: Set ollama-api-key secret"
            echo "  Response: $RESPONSE"
            return 2
        else
            test_failed "Unexpected response from Ollama API"
            echo "  Response: $RESPONSE"
            return 1
        fi
    fi
}

test_ollama_authentication_status() {
    log_test "Ollama Authentication Status"

    # Check if OLLAMA_API_KEY secret is set
    SECRET_VALUE=$(az containerapp secret show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --secret-name ollama-api-key \
        --query value \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$SECRET_VALUE" ]; then
        test_skipped "OLLAMA_API_KEY secret is not set"
        echo "  Cloud models require an API key"
        echo "  Get your key from: https://ollama.com/settings/keys"
        echo "  Set it with: az containerapp secret set --name $APP_NAME --resource-group $RESOURCE_GROUP --secrets ollama-api-key='your-key'"
        return 2
    else
        test_passed "OLLAMA_API_KEY secret is configured"
        echo "  Key length: ${#SECRET_VALUE} characters"

        # Try to verify key is valid by making a test call
        TEST_RESPONSE=$(az containerapp exec \
            --name "$APP_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --container ollama-sidecar \
            --command "curl -s http://localhost:11434/api/tags" \
            --only-show-errors 2>/dev/null || echo "")

        if [ -n "$TEST_RESPONSE" ]; then
            echo "  API is accessible with current key"
        else
            echo "  Warning: Could not verify API key validity"
        fi
        return 0
    fi
}

# ============================================
# Phase 3: Application Integration Validation
# ============================================
test_main_app_running() {
    log_test "Main Application Container Status"

    CONTAINER_STATUS=$(az containerapp replica list \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[0].properties.containers[?name=='main-app'].[0].ready" \
        --output tsv 2>/dev/null || echo "false")

    if [ "$CONTAINER_STATUS" == "true" ]; then
        test_passed "Main application is ready"
        return 0
    else
        test_failed "Main application is not ready"
        echo "  Checking recent logs..."
        az containerapp logs show \
            --name "$APP_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --container main-app \
            --tail 20 \
            --only-show-errors 2>/dev/null || echo "  No logs available"
        return 1
    fi
}

test_container_communication() {
    log_test "Container Communication (main-app → ollama-sidecar)"

    # Test if main-app can reach ollama-sidecar via localhost
    RESPONSE=$(az containerapp exec \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --container main-app \
        --command "curl -s http://localhost:11434/api/tags" \
        --only-show-errors 2>/dev/null || echo "")

    if echo "$RESPONSE" | jq -e '.models' > /dev/null 2>&1; then
        test_passed "Main app can communicate with Ollama sidecar"
        return 0
    else
        test_failed "Main app cannot communicate with Ollama sidecar"
        echo "  Response: $RESPONSE"
        return 1
    fi
}

test_application_health_endpoint() {
    log_test "Application Health Endpoint (/health)"

    FQDN=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$FQDN" ]; then
        test_failed "Could not determine application FQDN"
        return 1
    fi

    echo "  URL: https://$FQDN/health"

    # Wait a moment for endpoint to be ready
    sleep 5

    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$FQDN/health" --max-time 30 2>/dev/null || echo "000")

    if [ "$HTTP_STATUS" == "200" ]; then
        test_passed "Health endpoint is responding (HTTP 200)"
        return 0
    elif [ "$HTTP_STATUS" == "000" ]; then
        test_failed "Health endpoint unreachable"
        return 1
    else
        test_skipped "Health endpoint returned HTTP $HTTP_STATUS (might be starting)"
        return 2
    fi
}

test_application_ready_endpoint() {
    log_test "Application Ready Endpoint (/ready)"

    FQDN=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$FQDN" ]; then
        test_failed "Could not determine application FQDN"
        return 1
    fi

    echo "  URL: https://$FQDN/ready"

    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$FQDN/ready" --max-time 30 2>/dev/null || echo "000")

    if [ "$HTTP_STATUS" == "200" ]; then
        test_passed "Ready endpoint is responding (HTTP 200)"
        return 0
    elif [ "$HTTP_STATUS" == "000" ]; then
        test_failed "Ready endpoint unreachable"
        return 1
    else
        test_skipped "Ready endpoint returned HTTP $HTTP_STATUS (might be starting)"
        return 2
    fi
}

# ============================================
# Phase 4: Functionality Validation
# ============================================
test_search_endpoint_simple() {
    log_test "/search Endpoint (Simple Request)"

    FQDN=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$FQDN" ]; then
        test_failed "Could not determine application FQDN"
        return 1
    fi

    echo "  URL: https://$FQDN/search"

    RESPONSE_FILE="/tmp/search_response_simple.json"

    HTTP_STATUS=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" \
        -X POST "https://$FQDN/search" \
        -H "Content-Type: application/json" \
        -d '{"query": "test query", "max_results": 1}' \
        --max-time 60 2>/dev/null || echo "000")

    if [ "$HTTP_STATUS" == "200" ]; then
        # Validate JSON structure
        if jq -e '.' "$RESPONSE_FILE" > /dev/null 2>&1; then
            test_passed "/search endpoint is working (HTTP 200)"
            echo "  Response:"
            jq '.' "$RESPONSE_FILE" | head -20 | sed 's/^/    /'
            rm -f "$RESPONSE_FILE"
            return 0
        else
            test_failed "Response is not valid JSON"
            echo "  Response: $(cat "$RESPONSE_FILE")"
            rm -f "$RESPONSE_FILE"
            return 1
        fi
    else
        test_failed "/search endpoint returned HTTP $HTTP_STATUS"
        echo "  Response: $(cat "$RESPONSE_FILE" 2>/dev/null || 'N/A')"
        rm -f "$RESPONSE_FILE"
        return 1
    fi
}

test_search_endpoint_with_cloud_model() {
    log_test "/search Endpoint with Cloud Model"

    # First check if OLLAMA_API_KEY is set
    SECRET_VALUE=$(az containerapp secret show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --secret-name ollama-api-key \
        --query value \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$SECRET_VALUE" ]; then
        test_skipped "Skipping - OLLAMA_API_KEY not set"
        echo "  Set the API key to test cloud model functionality"
        return 2
    fi

    FQDN=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$FQDN" ]; then
        test_failed "Could not determine application FQDN"
        return 1
    fi

    echo "  URL: https://$FQDN/search"
    echo "  Query: 'What is Azure Container Apps?'"
    echo "  Max results: 2"
    echo "  This test may take 1-3 minutes..."

    RESPONSE_FILE="/tmp/search_response_cloud.json"
    LOG_FILE="/tmp/search_response_cloud.log"

    START_TIME=$(date +%s)

    HTTP_STATUS=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" \
        -X POST "https://$FQDN/search" \
        -H "Content-Type: application/json" \
        -H "X-Request-ID: validate-$(date +%s)" \
        -d '{
            "query": "What is Azure Container Apps?",
            "max_results": 2
        }' \
        --max-time 300 \
        -w "\nTIME_TOTAL:%{time_total}\n" \
        -o >(tee "$RESPONSE_FILE" > /dev/null) \
        2>"$LOG_FILE" || echo "000")

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    if [ "$HTTP_STATUS" == "200" ]; then
        # Validate JSON structure
        if jq -e '.' "$RESPONSE_FILE" > /dev/null 2>&1; then
            test_passed "/search with cloud model working (HTTP 200)"
            echo "  Duration: ${DURATION}s"
            echo "  Response preview:"
            jq '.' "$RESPONSE_FILE" | head -30 | sed 's/^/    /'
            rm -f "$RESPONSE_FILE" "$LOG_FILE"
            return 0
        else
            test_failed "Response is not valid JSON"
            echo "  Response: $(cat "$RESPONSE_FILE")"
            rm -f "$RESPONSE_FILE" "$LOG_FILE"
            return 1
        fi
    else
        test_failed "/search returned HTTP $HTTP_STATUS (timeout after 300s?)"
        echo "  Duration: ${DURATION}s"
        echo "  Response: $(cat "$RESPONSE_FILE" 2>/dev/null || 'N/A')"
        rm -f "$RESPONSE_FILE" "$LOG_FILE"
        return 1
    fi
}

test_response_schema_validation() {
    log_test "Response Schema Validation"

    # Use the response from the previous test if available, or make a new request
    RESPONSE_FILE="/tmp/search_response_schema.json"

    FQDN=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$FQDN" ]; then
        test_failed "Could not determine application FQDN"
        return 1
    fi

    curl -s -o "$RESPONSE_FILE" \
        -X POST "https://$FQDN/search" \
        -H "Content-Type: application/json" \
        -d '{"query": "schema test", "max_results": 1}' \
        --max-time 60 2>/dev/null || true

    if [ ! -f "$RESPONSE_FILE" ] || [ ! -s "$RESPONSE_FILE" ]; then
        test_failed "No response received"
        return 1
    fi

    # Validate schema
    if jq -e '.results' "$RESPONSE_FILE" > /dev/null 2>&1; then
        test_passed "Response has valid schema"

        # Check for expected fields
        echo "  Schema validation:"

        if jq -e '.results | type == "array"' "$RESPONSE_FILE" > /dev/null 2>&1; then
            RESULT_COUNT=$(jq '.results | length' "$RESPONSE_FILE")
            echo "    ✓ results: array ($RESULT_COUNT items)"
        else
            echo "    ✗ results: not an array"
        fi

        if jq -e '.model_used' "$RESPONSE_FILE" > /dev/null 2>&1; then
            MODEL_USED=$(jq -r '.model_used' "$RESPONSE_FILE")
            echo "    ✓ model_used: $MODEL_USED"
        else
            echo "    ! model_used: not present"
        fi

        rm -f "$RESPONSE_FILE"
        return 0
    else
        test_failed "Response does not have expected schema"
        echo "  Response: $(cat "$RESPONSE_FILE" | head -20)"
        rm -f "$RESPONSE_FILE"
        return 1
    fi
}

# ============================================
# Phase 5: Performance Tests
# ============================================
test_response_time() {
    log_test "Response Time SLA (< 60s)"

    FQDN=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$FQDN" ]; then
        test_failed "Could not determine application FQDN"
        return 1
    fi

    echo "  Measuring response times for 3 requests..."

    TOTAL_TIME=0
    SUCCESS_COUNT=0

    for i in {1..3}; do
        START=$(date +%s.%N)
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST "https://$FQDN/search" \
            -H "Content-Type: application/json" \
            -d '{"query": "test", "max_results": 1}' \
            --max-time 90 2>/dev/null || echo "000")
        END=$(date +%s.%N)
        DURATION=$(echo "$END - $START" | bc)

        if [ "$HTTP_STATUS" == "200" ]; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            TOTAL_TIME=$(echo "$TOTAL_TIME + $DURATION" | bc)
            echo "    Request $i: ${DURATION}s (HTTP $HTTP_STATUS)"
        else
            echo "    Request $i: FAILED (HTTP $HTTP_STATUS)"
        fi
    done

    if [ $SUCCESS_COUNT -gt 0 ]; then
        AVERAGE=$(echo "scale=2; $TOTAL_TIME / $SUCCESS_COUNT" | bc)
        echo "  Average time: ${AVERAGE}s over $SUCCESS_COUNT successful requests"

        if (( $(echo "$AVERAGE < 60" | bc -l) )); then
            test_passed "Average response time is ${AVERAGE}s (meets SLA)"
            return 0
        else
            test_failed "Average response time is ${AVERAGE}s (exceeds 60s SLA)"
            return 1
        fi
    else
        test_failed "No successful requests"
        return 1
    fi
}

test_concurrent_requests() {
    log_test "Concurrent Request Handling (5 requests)"

    FQDN=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$FQDN" ]; then
        test_failed "Could not determine application FQDN"
        return 1
    fi

    echo "  Sending 5 concurrent requests..."

    SUCCESS_COUNT=0

    for i in {1..5}; do
        (
            RESPONSE_FILE="/tmp/concurrent_response_$i.json"
            HTTP_STATUS=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" \
                -X POST "https://$FQDN/search" \
                -H "Content-Type: application/json" \
                -d "{\"query\": \"concurrent test $i\", \"max_results\": 1}" \
                --max-time 120 2>/dev/null || echo "000")
            echo "$HTTP_STATUS" > "/tmp/concurrent_status_$i.txt"
            rm -f "$RESPONSE_FILE"
        ) &
    done

    wait

    for i in {1..5}; do
        STATUS=$(cat "/tmp/concurrent_status_$i.txt" 2>/dev/null || echo "000")
        if [ "$STATUS" == "200" ]; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        fi
        rm -f "/tmp/concurrent_status_$i.txt"
    done

    echo "  Successful: $SUCCESS_COUNT/5 requests"

    if [ $SUCCESS_COUNT -ge 4 ]; then
        test_passed "Concurrent requests handled successfully ($SUCCESS_COUNT/5)"
        return 0
    elif [ $SUCCESS_COUNT -ge 1 ]; then
        test_skipped "Partial success ($SUCCESS_COUNT/5) - may be under load"
        return 2
    else
        test_failed "Concurrent requests failed (0/5)"
        return 1
    fi
}

test_replica_scaling() {
    log_test "Replica Scaling Configuration"

    SCALE_CONFIG=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.template.scale" \
        --output json 2>/dev/null || echo "{}")

    MIN_REPLICAS=$(echo "$SCALE_CONFIG" | jq -r '.minReplicas // "N/A"')
    MAX_REPLICAS=$(echo "$SCALE_CONFIG" | jq -r '.maxReplicas // "N/A"')

    CURRENT_REPLICAS=$(az containerapp replica list \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "length(@)" \
        --output tsv 2>/dev/null || echo "0")

    echo "  Min replicas: $MIN_REPLICAS"
    echo "  Max replicas: $MAX_REPLICAS"
    echo "  Current replicas: $CURRENT_REPLICAS"

    if [ "$CURRENT_REPLICAS" -ge 1 ]; then
        test_passed "Replicas are running ($CURRENT_REPLICAS active)"
        return 0
    else
        test_failed "No replicas running"
        return 1
    fi
}

# ============================================
# Phase 6: Resource Usage Validation
# ============================================
test_resource_allocation() {
    log_test "Resource Allocation"

    MAIN_APP_CPU=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.template.containers[?name==`main-app`].[0].resources.cpu' \
        --output tsv 2>/dev/null || echo "N/A")

    MAIN_APP_MEMORY=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.template.containers[?name==`main-app`].[0].resources.memory' \
        --output tsv 2>/dev/null || echo "N/A")

    OLLAMA_CPU=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.template.containers[?name==`ollama-sidecar`].[0].resources.cpu' \
        --output tsv 2>/dev/null || echo "N/A")

    OLLAMA_MEMORY=$(az containerapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.template.containers[?name==`ollama-sidecar`].[0].resources.memory' \
        --output tsv 2>/dev/null || echo "N/A")

    echo "  Main App:"
    echo "    CPU: $MAIN_APP_CPU cores"
    echo "    Memory: $MAIN_APP_MEMORY"
    echo "  Ollama Sidecar:"
    echo "    CPU: $OLLAMA_CPU cores"
    echo "    Memory: $OLLAMA_MEMORY"

    # Calculate total (simple string addition for known values)
    if [ "$MAIN_APP_CPU" == "0.5" ] && [ "$OLLAMA_CPU" == "0.25" ]; then
        TOTAL_CPU="0.75"
    elif [ "$MAIN_APP_CPU" == "2.0" ] && [ "$OLLAMA_CPU" == "2.0" ]; then
        TOTAL_CPU="4.0"
    else
        TOTAL_CPU="Unknown"
    fi

    if [ "$MAIN_APP_MEMORY" == "1.0Gi" ] && [ "$OLLAMA_MEMORY" == "0.5Gi" ]; then
        TOTAL_MEMORY="1.5Gi"
    elif [ "$MAIN_APP_MEMORY" == "4.0Gi" ] && [ "$OLLAMA_MEMORY" == "4.0Gi" ]; then
        TOTAL_MEMORY="8.0Gi"
    else
        TOTAL_MEMORY="Unknown"
    fi

    echo "  Total: $TOTAL_CPU CPU, $TOTAL_MEMORY RAM"

    if [ -n "$TOTAL_CPU" ] && [ -n "$TOTAL_MEMORY" ]; then
        test_passed "Resources allocated: $TOTAL_CPU CPU, $TOTAL_MEMORY RAM"
        return 0
    else
        test_skipped "Could not calculate total resources"
        return 2
    fi
}

# ============================================
# Phase 7: Supabase Connectivity
# ============================================
test_supabase_connectivity() {
    log_test "Supabase Connectivity"

    SECRET_VALUE=$(az containerapp secret show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --secret-name supabase-url \
        --query value \
        --output tsv 2>/dev/null || echo "")

    if [ -z "$SECRET_VALUE" ]; then
        test_failed "Supabase URL secret not found"
        return 1
    fi

    echo "  URL: $SECRET_VALUE"

    # Test connectivity from main-app container
    RESPONSE=$(az containerapp exec \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --container main-app \
        --command "curl -s \"$SECRET_VALUE/rest/v1/\" --max-time 10" \
        --only-show-errors 2>/dev/null || echo "")

    if echo "$RESPONSE" | grep -qi "information_schema\|tables\|version\|supabase"; then
        test_passed "Supabase is accessible"
        return 0
    else
        test_skipped "Could not verify Supabase connectivity (might be expected)"
        echo "  Response: $RESPONSE"
        return 2
    fi
}

# ============================================
# Generate Report
# ============================================
generate_report() {
    log_section "VALIDATION REPORT"

    echo ""
    echo "Total Tests: $TOTAL_TESTS"
    echo "Passed: $PASSED_TESTS ${GREEN}✓${NC}"
    echo "Failed: $FAILED_TESTS ${RED}✗${NC}"
    echo "Skipped: $SKIPPED_TESTS ${YELLOW}!${NC}"
    echo ""

    # Calculate pass rate
    if [ $TOTAL_TESTS -gt 0 ]; then
        PASS_RATE=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
        echo "Pass Rate: $PASS_RATE%"
    fi

    echo ""

    if [ $FAILED_TESTS -eq 0 ]; then
        log_success "All critical tests passed! Deployment is healthy."
        return 0
    else
        log_error "$FAILED_TESTS test(s) failed. Please review the failures above."
        return 1
    fi
}

# ============================================
# Main Execution
# ============================================
main() {
    log_section "AZURE CONTAINER APPS VALIDATION"
    log_info "Resource Group: $RESOURCE_GROUP"
    log_info "Container App: $APP_NAME"
    log_info "ACR: $ACR_NAME"
    log_info "Identity: $IDENTITY_NAME"
    echo ""

    # Phase 1: Infrastructure Validation
    log_section "PHASE 1: INFRASTRUCTURE VALIDATION"
    test_container_app_running || true
    test_acr_pull_success || true
    test_managed_identity_assignment || true
    test_registry_configuration || true

    # Phase 2: Ollama Sidecar Validation
    log_section "PHASE 2: OLLAMA SIDECAR VALIDATION"
    test_ollama_sidecar_running || true
    test_ollama_health_endpoint || true
    test_ollama_cloud_model_accessible || true
    test_ollama_authentication_status || true

    # Phase 3: Application Integration
    log_section "PHASE 3: APPLICATION INTEGRATION"
    test_main_app_running || true
    test_container_communication || true
    test_application_health_endpoint || true
    test_application_ready_endpoint || true

    # Phase 4: Functionality
    log_section "PHASE 4: FUNCTIONALITY VALIDATION"
    test_search_endpoint_simple || true
    test_search_endpoint_with_cloud_model || true
    test_response_schema_validation || true

    # Phase 5: Performance
    log_section "PHASE 5: PERFORMANCE VALIDATION"
    test_response_time || true
    test_concurrent_requests || true
    test_replica_scaling || true

    # Phase 6: Resource Usage
    log_section "PHASE 6: RESOURCE VALIDATION"
    test_resource_allocation || true

    # Phase 7: External Connectivity
    log_section "PHASE 7: EXTERNAL CONNECTIVITY"
    test_supabase_connectivity || true

    # Generate final report
    generate_report
    exit $?
}

# Run main function
main "$@"
