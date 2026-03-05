/// Claim module — open submission, entity linking, flagging.
///
/// Design rationale:
/// - Anyone can submit a Claim (no AdminCap required)
/// - Claim stores entity_ids as vector<ID> (cannot wrap Shared Objects)
/// - link_to_entity takes &Entity to prove existence, then stores its ID
/// - Claims are Shared Objects so the community can flag them
module sugar_protocol::claim;

use std::string::String;
use sui::event;
use sugar_protocol::types;
use sugar_protocol::registry::Entity;

// =========================================================================
// Errors
// =========================================================================

#[error]
const EAlreadyLinked: vector<u8> = b"Claim is already linked to this entity";
#[error]
const EInvalidClaimType: vector<u8> = b"Invalid claim type value";

// =========================================================================
// Structs
// =========================================================================

/// A discourse claim extracted from an article.
/// Shared Object — community can link entities or flag.
public struct Claim has key, store {
    id: UID,
    text: String,
    claim_type: u8,
    verifiable: bool,
    source_url: String,
    entity_ids: vector<ID>,
    submitter: address,
    is_flagged: bool,
}

// =========================================================================
// Events
// =========================================================================

public struct ClaimSubmitted has copy, drop {
    claim_id: ID,
    submitter: address,
}

public struct ClaimLinked has copy, drop {
    claim_id: ID,
    entity_id: ID,
}

public struct ClaimFlagged has copy, drop {
    claim_id: ID,
    flagger: address,
}

// =========================================================================
// Public functions
// =========================================================================

/// Submit a new claim. Permissionless — anyone can call.
public fun submit_claim(
    text: String,
    claim_type: u8,
    verifiable: bool,
    source_url: String,
    ctx: &mut TxContext,
) {
    assert!(types::is_valid_claim_type(claim_type), EInvalidClaimType);

    let claim = Claim {
        id: object::new(ctx),
        text,
        claim_type,
        verifiable,
        source_url,
        entity_ids: vector[],
        submitter: ctx.sender(),
        is_flagged: false,
    };

    event::emit(ClaimSubmitted {
        claim_id: object::id(&claim),
        submitter: ctx.sender(),
    });

    transfer::public_share_object(claim);
}

/// Link a Claim to an Entity. Passing &Entity proves on-chain existence.
public fun link_to_entity(claim: &mut Claim, entity: &Entity) {
    let entity_id = object::id(entity);
    assert!(!claim.entity_ids.contains(&entity_id), EAlreadyLinked);

    claim.entity_ids.push_back(entity_id);
    event::emit(ClaimLinked {
        claim_id: object::id(claim),
        entity_id,
    });
}

/// Flag a claim as disputed. Permissionless.
public fun flag_claim(claim: &mut Claim, ctx: &TxContext) {
    claim.is_flagged = true;
    event::emit(ClaimFlagged {
        claim_id: object::id(claim),
        flagger: ctx.sender(),
    });
}

// =========================================================================
// Getters
// =========================================================================

public fun claim_text(claim: &Claim): String { claim.text }
public fun claim_type(claim: &Claim): u8 { claim.claim_type }
public fun claim_verifiable(claim: &Claim): bool { claim.verifiable }
public fun claim_source_url(claim: &Claim): String { claim.source_url }
public fun claim_entity_ids(claim: &Claim): &vector<ID> { &claim.entity_ids }
public fun claim_submitter(claim: &Claim): address { claim.submitter }
public fun claim_is_flagged(claim: &Claim): bool { claim.is_flagged }
