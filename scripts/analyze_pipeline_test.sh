#!/bin/bash

# Analysis Script for Pipeline Test
# Usage: ./scripts/analyze_pipeline_test.sh <log_file> [artifact_file]

LOG_FILE=$1
ARTIFACT=$2

if [ -z "$LOG_FILE" ]; then
  echo "Usage: $0 <log_file> [artifact_file]"
  exit 1
fi

if [ -z "$ARTIFACT" ]; then
  # Try to find the most recent artifact
  ARTIFACT=$(ls -t artifacts/*.json | head -n 1)
  echo "Auto-detected artifact: $ARTIFACT"
fi

echo "=================================================="
echo "Pipeline Quality Assessment Analysis"
echo "Date: $(date)"
echo "Log: $LOG_FILE"
echo "Artifact: $ARTIFACT"
echo "=================================================="

# 1. Discovery and Success
echo ""
echo "## 1. Discovery and Success Metrics"
REQUESTED=50
DISCOVERED_LOG=$(grep -oE "Found pages.*count=[0-9]+" $LOG_FILE | grep -oE "[0-9]+")
# If not found in log (e.g. still running or different format), try Task plan
if [ -z "$DISCOVERED_LOG" ]; then
    DISCOVERED_LOG=$(grep -oE "\"max_results\": [0-9]+" $LOG_FILE | head -n 1 | awk '{print $2}' | tr -d ',')
fi

SCRAPED=$(jq 'length' $ARTIFACT 2>/dev/null || echo "0")
echo "Requested Profiles: $REQUESTED"
echo "Discovered Profiles: ${DISCOVERED_LOG:-Unknown}"
echo "Successfully Scraped: $SCRAPED"

# 2. Field Completeness
echo ""
echo "## 2. Field Completeness Analysis"
TOTAL=$SCRAPED
if [ "$TOTAL" -gt 0 ]; then
    NAME=$(jq '[.[] | select(.name != null and .name != "")] | length' $ARTIFACT)
    LINKEDIN=$(jq '[.[] | select(.linkedin != null and .linkedin != "")] | length' $ARTIFACT)
    COMPANY=$(jq '[.[] | select(.company != null and .company != "")] | length' $ARTIFACT)
    ROLE=$(jq '[.[] | select(.role != null and .role != "")] | length' $ARTIFACT)
    DOMAIN=$(jq '[.[] | select(.company_domain != null and .company_domain != "")] | length' $ARTIFACT)
    EMAIL=$(jq '[.[] | select(.email != null and .email != "")] | length' $ARTIFACT)
    PHONE=$(jq '[.[] | select(.phone_number != null and .phone_number != "")] | length' $ARTIFACT)

    echo "Name: $NAME ($(( NAME * 100 / TOTAL ))%)"
    echo "LinkedIn: $LINKEDIN ($(( LINKEDIN * 100 / TOTAL ))%)"
    echo "Company: $COMPANY ($(( COMPANY * 100 / TOTAL ))%)"
    echo "Role: $ROLE ($(( ROLE * 100 / TOTAL ))%)"
    echo "Domain: $DOMAIN ($(( DOMAIN * 100 / TOTAL ))%)"
    echo "Email: $EMAIL ($(( EMAIL * 100 / TOTAL ))%)"
    echo "Phone: $PHONE ($(( PHONE * 100 / TOTAL ))%)"
else
    echo "No leads to analyze."
fi

# 3. Quality Score
echo ""
echo "## 3. Lead Quality Distribution"
# Use jq to calculate
jq -r '.[] | 
  (if .name then 20 else 0 end + 
   if .company then 20 else 0 end + 
   if .company_domain then 15 else 0 end + 
   if .email then 25 else 0 end + 
   if .phone_number then 15 else 0 end + 
   if .role then 5 else 0 end) as $score |
  (if $score >= 80 then "High"
   elif $score >= 50 then "Medium"
   elif $score >= 20 then "Low"
   else "Incomplete" end) as $tier |
  "\($tier): \($score)"' $ARTIFACT | sort | uniq -c

# 4. Account Distribution
echo ""
echo "## 4. Account Distribution"
grep "account_selected" $LOG_FILE | grep -oE "account_id=[0-9]+" | sort | uniq -c || echo "No account selection logs found."

# 5. Detection
echo ""
echo "## 5. Detection Indicators (grep matches)"
grep -iE "checkpoint|challenge|captcha|verification|unusual activity|429|rate limit|too many requests|authentication_required|session_invalid" $LOG_FILE | sort | uniq -c || echo "None found."

echo ""
echo "Analysis Complete."
