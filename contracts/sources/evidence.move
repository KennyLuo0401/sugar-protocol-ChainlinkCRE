/// Evidence module — submit supporting or contradicting evidence for claims.
///
/// Design:
/// - Anyone can submit evidence (permissionless, like Claim)
/// - Evidence links to a Claim via claim_id
/// - edge_type indicates relationship (supports, contradicts, etc.)
/// - Evidence is a Shared Object for community visibility
module sugar_protocol::evidence;

use std::string::String;
use sui::event;
use sugar_protocol::types;
use sugar_protocol::claim::Claim;

// =========================================================================
// Errors
// =========================================================================

#[error]
const EInvalidEdgeType: vector<u8> = b"Invalid edge type value";

// =========================================================================
// Structs
// =========================================================================

/// A piece of evidence supporting or contradicting a claim.
/// Shared Object — community-visible.
public struct Evidence has key, store {
    id: UID,
    claim_id: ID,
    content: String,
    source_url: String,
    edge_type: u8,          // relationship to claim (supports, contradicts, etc.)
    submitter: address,
}

// =========================================================================
// Events
// =========================================================================

public struct EvidenceSubmitted has copy, drop {
    evidence_id: ID,
    claim_id: ID,
    edge_type: u8,
    submitter: address,
}

// =========================================================================
// Public functions
// =========================================================================

/// Submit evidence linked to a claim. Passing &Claim proves on-chain existence.
/// Permissionless — anyone can call.
public fun submit_evidence(
    claim: &Claim,
    content: String,
    source_url: String,
    edge_type: u8,
    ctx: &mut TxContext,
) {
    assert!(types::is_valid_edge_type(edge_type), EInvalidEdgeType);

    let evidence = Evidence {
        id: object::new(ctx),
        claim_id: object::id(claim),
        content,
        source_url,
        edge_type,
        submitter: ctx.sender(),
    };

    event::emit(EvidenceSubmitted {
        evidence_id: object::id(&evidence),
        claim_id: object::id(claim),
        edge_type,
        submitter: ctx.sender(),
    });

    transfer::public_share_object(evidence);
}

// =========================================================================
// Getters
// =========================================================================

public fun evidence_claim_id(e: &Evidence): ID { e.claim_id }
public fun evidence_content(e: &Evidence): String { e.content }
public fun evidence_source_url(e: &Evidence): String { e.source_url }
public fun evidence_edge_type(e: &Evidence): u8 { e.edge_type }
public fun evidence_submitter(e: &Evidence): address { e.submitter }
