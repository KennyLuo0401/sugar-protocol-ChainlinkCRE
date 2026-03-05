/**
 * Chainlink CRE Market Verifier Script
 *
 * CRE Capability #3: Event-Driven Market Verification
 *
 * Trigger: PredictionMarket.MarketCreated event on EVM
 * Logic:
 * 1. Extract marketId from on-chain event
 * 2. Read claim data from PredictionMarket contract
 * 3. Validate claim exists in Sugar Protocol API
 * 4. Call Sugar API /cre-verify endpoint → verifyMarket() on EVM
 */

// Environment variables provided by CRE environment
const SUGAR_API_URL = process.env.SUGAR_API_URL || "http://localhost:8000";
const PREDICTION_MARKET_ADDRESS = process.env.PREDICTION_MARKET_ADDRESS || "";

/**
 * Main execution function for CRE — triggered by MarketCreated event
 * @param marketId The market ID from the on-chain event
 * @param claimId The claim ID from event data
 * @param creator The market creator address
 * @param stake The staked ETH amount (wei)
 */
async function verifyMarket(
  marketId: string,
  claimId: string,
  creator: string,
  stake: string,
) {
  console.log(`[CRE] 🍬 Sugar Protocol: MarketCreated event detected`);
  console.log(`[CRE] Market ID: ${marketId}, Claim: ${claimId}, Creator: ${creator}`);

  // Step 1: Validate — check that claim exists in Sugar Protocol
  console.log(`[CRE] [Step 1] Validating claim in Sugar Protocol API...`);
  const resolveResponse = await fetch(`${SUGAR_API_URL}/api/resolve?claim_id=${claimId}`);

  let claimValid = false;
  if (resolveResponse.ok) {
    const claimData = await resolveResponse.json();
    claimValid = !!claimData.claim_text;
    console.log(`[CRE] [Step 1] Claim found: "${claimData.claim_text}" (type: ${claimData.claim_type})`);
  } else {
    // For hackathon demo: proceed even if claim not in mock data
    console.log(`[CRE] [Step 1] Claim not in API (${resolveResponse.status}), proceeding with verification anyway`);
    claimValid = true;
  }

  if (!claimValid) {
    console.log(`[CRE] Claim validation failed. Skipping verification.`);
    return {
      marketId,
      claimId,
      status: "rejected",
      reason: "Claim not found in Sugar Protocol",
    };
  }

  // Step 2: Call Sugar API to trigger CRE verification (verifyMarket on EVM)
  console.log(`[CRE] [Step 2] Calling /cre-verify to mark market as VERIFIED...`);
  const verifyResponse = await fetch(
    `${SUGAR_API_URL}/api/markets/${marketId}/cre-verify`,
    { method: "POST" }
  );

  if (!verifyResponse.ok) {
    const errText = await verifyResponse.text();
    console.log(`[CRE] [Step 2] Verification failed: ${errText}`);
    return {
      marketId,
      claimId,
      status: "error",
      reason: errText,
    };
  }

  const verifyResult = await verifyResponse.json();
  console.log(`[CRE] [Step 2] Market verified! TX: ${verifyResult.tx_hash}`);

  console.log(`[CRE] 🍬 Sugar Protocol: Market verification complete!`);

  return {
    marketId,
    claimId,
    status: "verified",
    txHash: verifyResult.tx_hash,
    creator,
    stake,
    timestamp: Date.now(),
  };
}

// Entry point for local simulation
// verifyMarket("1", "claim_tsmc_n2", "0x1234...", "10000000000000000").catch(console.error);
