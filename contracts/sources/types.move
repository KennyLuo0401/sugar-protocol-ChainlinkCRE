/// Shared constants for Sugar Protocol on-chain modules.
/// Tier levels, claim types, and edge types are represented as u8
/// to keep storage cost minimal and avoid struct overhead.
module sugar_protocol::types;

// =========================================================================
// Entity Tier (mirrors interfaces.py EntityTier)
// =========================================================================
const TIER_COUNTRY: u8 = 0;
const TIER_DOMAIN: u8 = 1;
const TIER_EVENT: u8 = 2;
const TIER_ORGANIZATION: u8 = 3;
const TIER_PERSON: u8 = 4;
const TIER_ASSET: u8 = 5;
const TIER_MAX: u8 = 5;

// =========================================================================
// Claim Type (mirrors interfaces.py ClaimType)
// =========================================================================
const CLAIM_FACTUAL: u8 = 0;
const CLAIM_OPINION: u8 = 1;
const CLAIM_PREDICTION: u8 = 2;
const CLAIM_TYPE_MAX: u8 = 2;

// =========================================================================
// Edge / Bond Type (mirrors interfaces.py EdgeType)
// =========================================================================
const EDGE_CONTAINS: u8 = 0;
const EDGE_DERIVES: u8 = 1;
const EDGE_SUPPORTS: u8 = 2;
const EDGE_CONTRADICTS: u8 = 3;
const EDGE_CAUSAL: u8 = 4;
const EDGE_RELATED: u8 = 5;
const EDGE_TYPE_MAX: u8 = 5;

// =========================================================================
// Validation helpers — called by registry.move & claim.move
// =========================================================================

public fun is_valid_tier(tier: u8): bool { tier <= TIER_MAX }
public fun is_valid_claim_type(ct: u8): bool { ct <= CLAIM_TYPE_MAX }
public fun is_valid_edge_type(et: u8): bool { et <= EDGE_TYPE_MAX }

// Tier getters
public fun tier_country(): u8 { TIER_COUNTRY }
public fun tier_domain(): u8 { TIER_DOMAIN }
public fun tier_event(): u8 { TIER_EVENT }
public fun tier_organization(): u8 { TIER_ORGANIZATION }
public fun tier_person(): u8 { TIER_PERSON }
public fun tier_asset(): u8 { TIER_ASSET }

// Claim type getters
public fun claim_factual(): u8 { CLAIM_FACTUAL }
public fun claim_opinion(): u8 { CLAIM_OPINION }
public fun claim_prediction(): u8 { CLAIM_PREDICTION }

// Edge type getters
public fun edge_contains(): u8 { EDGE_CONTAINS }
public fun edge_derives(): u8 { EDGE_DERIVES }
public fun edge_supports(): u8 { EDGE_SUPPORTS }
public fun edge_contradicts(): u8 { EDGE_CONTRADICTS }
public fun edge_causal(): u8 { EDGE_CAUSAL }
public fun edge_related(): u8 { EDGE_RELATED }
