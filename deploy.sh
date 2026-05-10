#!/usr/bin/env bash
# Manual deploy / inspection helper for text-to-audio.
#
# Day-to-day deploys go through .github/workflows/deploy.yml on push to main.
# This script is a fallback for: redeploying Lambda code without a commit,
# probing the live API, and documenting the resource map.
#
# Usage:
#   ./deploy.sh lambda     # zip + update-function-code
#   ./deploy.sh smoke      # POST a 1-word test, save mp3, file-check it
#   ./deploy.sh resources  # print resource IDs / ARNs

set -euo pipefail

PROFILE="portfolio-user"
REGION="us-east-1"
FN_NAME="jimmy-text-to-audio"
API_ID="yhrh1k32ra"
ENDPOINT="https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod/synthesize"

# Read the API key from the deployed index.html so deploy.sh stays out of
# git secrets territory. The token is a public rate-limit key (embedded in
# the page on purpose), not a secret.
#
# Edit this regex if RATE_LIMIT_TOKEN is renamed or quote style changes in index.html.
extract_token() {
  grep -oE "const RATE_LIMIT_TOKEN[[:space:]]*=[[:space:]]*'[^']+'" index.html \
    | sed -E "s/.*'([^']+)'/\\1/"
}

cmd_lambda() {
  echo "▸ Zipping lambda_function.py"
  zip -j lambda.zip lambda_function.py
  echo "▸ aws lambda update-function-code"
  aws --profile "$PROFILE" --region "$REGION" lambda update-function-code \
    --function-name "$FN_NAME" \
    --zip-file fileb://lambda.zip \
    --no-cli-pager \
    --query '{State, LastUpdateStatus, CodeSha256}'
  rm lambda.zip
  echo "✓ Lambda updated."
}

cmd_smoke() {
  local TOKEN
  TOKEN="$(extract_token)"
  if [[ -z "$TOKEN" ]]; then
    echo "✗ Could not extract RATE_LIMIT_TOKEN from index.html" >&2
    exit 1
  fi
  echo "▸ POST /synthesize (Joanna, 'Hello world')"
  curl -s -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $TOKEN" \
    -H "Accept: audio/mpeg" \
    -d '{"text":"Hello world","voiceId":"Joanna","rate":"100%"}' \
    -o /tmp/tta-smoke.mp3 \
    -w "HTTP %{http_code}  size %{size_download}B\n"
  file /tmp/tta-smoke.mp3
}

cmd_resources() {
  cat <<EOF
Resource map (read-only)

Frontend:
  Bucket:        jimmy-text-to-audio (private, OAC-scoped)
  CloudFront:    E1BM7FLW1T9GAM
  Alias:         text-to-audio.jimmyhubbard2.cc
  OAC:           text-to-audio-oac (signs S3 origin requests)

Backend:
  Lambda:        $FN_NAME
  Lambda role:   jimmy-text-to-audio-role (AWSLambdaBasicExecutionRole + PollyAccess inline)
  API Gateway:   jimmy-text-to-audio-api ($API_ID), prod stage
  Endpoint:      $ENDPOINT
  Usage plan:    text-to-audio-portfolio-plan (10 rps / 20 burst, 1000/day)
  API key:       text-to-audio-portfolio (embedded as RATE_LIMIT_TOKEN in index.html)

Cost control:
  Budget:        text-to-audio-polly-monthly (\$5/mo, FORECASTED 80% + ACTUAL 100% → email)
EOF
}

case "${1:-}" in
  lambda)    cmd_lambda ;;
  smoke)     cmd_smoke ;;
  resources) cmd_resources ;;
  *)
    echo "Usage: $0 {lambda|smoke|resources}" >&2
    exit 1
    ;;
esac
