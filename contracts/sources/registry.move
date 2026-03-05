/// Entity Registry — global lookup table + Entity objects.
///
/// Design rationale (from SuiMove.md):
/// - Registry only stores canonical_id → Entity ID mapping (Table<String, ID>)
/// - Entity is an independent Shared Object to avoid contention
/// - AdminCap controls create/update operations
module sugar_protocol::registry;

use std::string::String;
use sui::table::{Self, Table};
use sui::event;
use sugar_protocol::types;

// =========================================================================
// Errors
// =========================================================================

#[error]
const EEntityAlreadyExists: vector<u8> = b"Entity with this canonical ID already exists";
#[error]
const EEntityNotFound: vector<u8> = b"Entity not found in the registry";
#[error]
const EInvalidTier: vector<u8> = b"Invalid tier value";

// =========================================================================
// Structs
// =========================================================================

/// Capability object — only the holder can create/update entities.
public struct AdminCap has key, store { id: UID }

/// Global registry mapping canonical_id → Entity object ID.
/// Shared Object — anyone can read, only AdminCap holder can write.
public struct Registry has key {
    id: UID,
    entities: Table<String, ID>,
    entity_count: u64,
}

/// A discourse entity (person, org, event, country, etc.).
/// Shared Object — readable by Claim module for link validation.
public struct Entity has key, store {
    id: UID,
    canonical_id: String,
    label: String,
    tier: u8,
    country: String,
    domain: String,
    aliases: vector<String>,
}

// =========================================================================
// Events
// =========================================================================

public struct EntityCreated has copy, drop {
    entity_id: ID,
    canonical_id: String,
}

public struct EntityUpdated has copy, drop {
    entity_id: ID,
    canonical_id: String,
}

// =========================================================================
// Init — publish-time setup
// =========================================================================

fun init(ctx: &mut TxContext) {
    transfer::public_transfer(AdminCap { id: object::new(ctx) }, ctx.sender());

    let registry = Registry {
        id: object::new(ctx),
        entities: table::new(ctx),
        entity_count: 0,
    };
    transfer::share_object(registry);
}

// =========================================================================
// Public functions
// =========================================================================

/// Create a new Entity and register it. Requires AdminCap.
public fun create_entity(
    _: &AdminCap,
    registry: &mut Registry,
    canonical_id: String,
    label: String,
    tier: u8,
    country: String,
    domain: String,
    ctx: &mut TxContext,
) {
    assert!(types::is_valid_tier(tier), EInvalidTier);
    assert!(!registry.entities.contains(canonical_id), EEntityAlreadyExists);

    let entity = Entity {
        id: object::new(ctx),
        canonical_id,
        label,
        tier,
        country,
        domain,
        aliases: vector[],
    };

    let entity_id = object::id(&entity);
    registry.entities.add(canonical_id, entity_id);
    registry.entity_count = registry.entity_count + 1;

    event::emit(EntityCreated { entity_id, canonical_id });
    transfer::public_share_object(entity);
}

/// Look up an Entity's object ID by canonical_id.
public fun get_entity_id(registry: &Registry, canonical_id: String): ID {
    assert!(registry.entities.contains(canonical_id), EEntityNotFound);
    *&registry.entities[canonical_id]
}

/// Check if a canonical_id exists in the registry.
public fun contains(registry: &Registry, canonical_id: String): bool {
    registry.entities.contains(canonical_id)
}

/// Update entity metadata. Requires AdminCap.
public fun update_entity(
    _: &AdminCap,
    entity: &mut Entity,
    label: String,
    tier: u8,
    country: String,
    domain: String,
) {
    assert!(types::is_valid_tier(tier), EInvalidTier);
    entity.label = label;
    entity.tier = tier;
    entity.country = country;
    entity.domain = domain;
    event::emit(EntityUpdated {
        entity_id: object::id(entity),
        canonical_id: entity.canonical_id,
    });
}

/// Add an alias to an entity. Requires AdminCap.
public fun add_alias(_: &AdminCap, entity: &mut Entity, alias: String) {
    entity.aliases.push_back(alias);
    event::emit(EntityUpdated {
        entity_id: object::id(entity),
        canonical_id: entity.canonical_id,
    });
}

// =========================================================================
// Getters — for composability (other modules / PTB reads)
// =========================================================================

public fun entity_canonical_id(entity: &Entity): String { entity.canonical_id }
public fun entity_label(entity: &Entity): String { entity.label }
public fun entity_tier(entity: &Entity): u8 { entity.tier }
public fun entity_country(entity: &Entity): String { entity.country }
public fun entity_domain(entity: &Entity): String { entity.domain }
public fun entity_aliases(entity: &Entity): &vector<String> { &entity.aliases }
public fun registry_entity_count(registry: &Registry): u64 { registry.entity_count }

// =========================================================================
// Test-only helpers
// =========================================================================

#[test_only]
public fun init_for_testing(ctx: &mut TxContext) {
    init(ctx);
}
