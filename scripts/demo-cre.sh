#!/bin/bash
# Demo CRE: Create market → Update config → Run cre simulate
# Prerequisites: backend running on localhost:8000

set -e

API="http://localhost:8000"
CONFIG="$(dirname "$0")/../cre-project/sugar-protocol/market-resolver/config.staging.json"
CLAIM_TEXT="台積電 2 奈米製程將於 2025 年開始量產"

echo "=== Sugar Protocol CRE Demo ==="
echo ""

# Step 1: Check backend is running
if ! curl -s "$API/api/resolve?claim_id=claim_tsmc_n2" > /dev/null 2>&1; then
  echo "ERROR: Backend not running. Start it first:"
  echo "  PYTHONPATH=. uvicorn api.main:app --reload --port 8000"
  exit 1
fi
echo "[1/3] Backend is running"

# Step 2: Create a fresh market on Sui Testnet
echo "[2/3] Creating market on Sui Testnet..."
RESULT=$(curl -s -X POST "$API/api/markets/create" \
  -H "Content-Type: application/json" \
  -d "{\"claim_text\": \"$CLAIM_TEXT\", \"deadline_days\": 7}")

MARKET_ID=$(echo "$RESULT" | jq -r '.market_id')
TX_DIGEST=$(echo "$RESULT" | jq -r '.tx_digest')

if [ "$MARKET_ID" = "null" ] || [ -z "$MARKET_ID" ]; then
  echo "ERROR: Market creation failed"
  echo "$RESULT" | jq .
  exit 1
fi

echo "  Market ID: $MARKET_ID"
echo "  TX Digest: $TX_DIGEST"

# Step 3: Update config.staging.json with new marketId
jq --arg mid "$MARKET_ID" '.marketId = $mid' "$CONFIG" > "$CONFIG.tmp" && mv "$CONFIG.tmp" "$CONFIG"
echo "[3/3] Updated config.staging.json"

echo ""
echo "=== Ready! Run CRE simulate: ==="
echo "  cd cre-project/sugar-protocol/market-resolver && cre workflow simulate -T staging-settings"
echo ""
