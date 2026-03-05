#[test_only]
module sugar_protocol::sugar_tests;

use sui::test_scenario::{Self as ts};
use sui::coin::{Self, Coin};
use sui::sui::SUI;
use sui::clock;
use sugar_protocol::types;
use sugar_protocol::registry::{Self, AdminCap, Registry, Entity};
use sugar_protocol::claim::{Self, Claim};
use sugar_protocol::market::{Self, TruthMarket, StakeReceipt};
use sugar_protocol::evidence::{Self, Evidence};

// =========================================================================
// types.move tests
// =========================================================================

#[test]
fun test_tier_validation() {
    assert!(types::is_valid_tier(0)); // country
    assert!(types::is_valid_tier(5)); // asset
    assert!(!types::is_valid_tier(6));
    assert!(!types::is_valid_tier(255));
}

#[test]
fun test_claim_type_validation() {
    assert!(types::is_valid_claim_type(0)); // factual
    assert!(types::is_valid_claim_type(2)); // prediction
    assert!(!types::is_valid_claim_type(3));
}

#[test]
fun test_edge_type_validation() {
    assert!(types::is_valid_edge_type(0)); // contains
    assert!(types::is_valid_edge_type(5)); // related
    assert!(!types::is_valid_edge_type(6));
}

#[test]
fun test_type_getters() {
    assert!(types::tier_country() == 0);
    assert!(types::tier_person() == 4);
    assert!(types::claim_factual() == 0);
    assert!(types::claim_prediction() == 2);
    assert!(types::edge_contradicts() == 3);
}

// =========================================================================
// registry.move tests
// =========================================================================

#[test]
fun test_create_entity() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    // init: creates AdminCap + Registry
    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    // create entity
    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();

        registry::create_entity(
            &admin_cap,
            &mut reg,
            b"tsmc".to_string(),
            b"TSMC".to_string(),
            types::tier_organization(),
            b"TW".to_string(),
            b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );

        assert!(registry::registry_entity_count(&reg) == 1);
        assert!(registry::contains(&reg, b"tsmc".to_string()));

        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    ts::end(scenario);
}

#[test]
fun test_create_multiple_entities() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();

        registry::create_entity(
            &admin_cap, &mut reg,
            b"bitcoin".to_string(), b"Bitcoin".to_string(),
            types::tier_asset(), b"".to_string(), b"crypto".to_string(),
            ts::ctx(&mut scenario),
        );

        registry::create_entity(
            &admin_cap, &mut reg,
            b"taiwan".to_string(), b"Taiwan".to_string(),
            types::tier_country(), b"TW".to_string(), b"".to_string(),
            ts::ctx(&mut scenario),
        );

        assert!(registry::registry_entity_count(&reg) == 2);

        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = registry::EEntityAlreadyExists)]
fun test_duplicate_entity_fails() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();

        registry::create_entity(
            &admin_cap, &mut reg,
            b"tsmc".to_string(), b"TSMC".to_string(),
            types::tier_organization(), b"TW".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );

        // duplicate — should abort
        registry::create_entity(
            &admin_cap, &mut reg,
            b"tsmc".to_string(), b"TSMC duplicate".to_string(),
            types::tier_organization(), b"TW".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );

        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = registry::EInvalidTier)]
fun test_invalid_tier_fails() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();

        registry::create_entity(
            &admin_cap, &mut reg,
            b"bad".to_string(), b"Bad".to_string(),
            99, // invalid tier
            b"".to_string(), b"".to_string(),
            ts::ctx(&mut scenario),
        );

        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    ts::end(scenario);
}

#[test]
fun test_update_entity() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();
        registry::create_entity(
            &admin_cap, &mut reg,
            b"tsmc".to_string(), b"TSMC".to_string(),
            types::tier_organization(), b"TW".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut entity = scenario.take_shared<Entity>();

        registry::update_entity(
            &admin_cap, &mut entity,
            b"Taiwan Semiconductor".to_string(),
            types::tier_organization(),
            b"TW".to_string(),
            b"semiconductor".to_string(),
        );

        assert!(registry::entity_label(&entity) == b"Taiwan Semiconductor".to_string());

        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(entity);
    };

    ts::end(scenario);
}

#[test]
fun test_add_alias() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();
        registry::create_entity(
            &admin_cap, &mut reg,
            b"tsmc".to_string(), b"TSMC".to_string(),
            types::tier_organization(), b"TW".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut entity = scenario.take_shared<Entity>();

        registry::add_alias(&admin_cap, &mut entity, b"台積電".to_string());
        registry::add_alias(&admin_cap, &mut entity, b"2330.TW".to_string());

        assert!(registry::entity_aliases(&entity).length() == 2);

        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(entity);
    };

    ts::end(scenario);
}

#[test]
fun test_get_entity_id() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();
        registry::create_entity(
            &admin_cap, &mut reg,
            b"tsmc".to_string(), b"TSMC".to_string(),
            types::tier_organization(), b"TW".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    ts::next_tx(&mut scenario, admin);
    {
        let reg = scenario.take_shared<Registry>();
        let entity = scenario.take_shared<Entity>();

        let looked_up_id = registry::get_entity_id(&reg, b"tsmc".to_string());
        assert!(looked_up_id == object::id(&entity));

        ts::return_shared(reg);
        ts::return_shared(entity);
    };

    ts::end(scenario);
}

// =========================================================================
// claim.move tests
// =========================================================================

#[test]
fun test_submit_claim() {
    let user = @0xBBBB;
    let mut scenario = ts::begin(user);

    ts::next_tx(&mut scenario, user);
    {
        claim::submit_claim(
            b"TSMC Q4 revenue exceeded expectations".to_string(),
            types::claim_factual(),
            true,
            b"https://example.com/article1".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    ts::next_tx(&mut scenario, user);
    {
        let claim_obj = scenario.take_shared<Claim>();
        assert!(claim::claim_text(&claim_obj) == b"TSMC Q4 revenue exceeded expectations".to_string());
        assert!(claim::claim_type(&claim_obj) == types::claim_factual());
        assert!(claim::claim_verifiable(&claim_obj) == true);
        assert!(claim::claim_submitter(&claim_obj) == user);
        assert!(claim::claim_is_flagged(&claim_obj) == false);
        assert!(claim::claim_entity_ids(&claim_obj).length() == 0);
        ts::return_shared(claim_obj);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = claim::EInvalidClaimType)]
fun test_invalid_claim_type_fails() {
    let user = @0xBBBB;
    let mut scenario = ts::begin(user);

    ts::next_tx(&mut scenario, user);
    {
        claim::submit_claim(
            b"test".to_string(),
            99, // invalid
            true,
            b"https://example.com".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    ts::end(scenario);
}

#[test]
fun test_link_claim_to_entity() {
    let admin = @0xAAAA;
    let user = @0xBBBB;
    let mut scenario = ts::begin(admin);

    // init registry
    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    // create entity
    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();
        registry::create_entity(
            &admin_cap, &mut reg,
            b"tsmc".to_string(), b"TSMC".to_string(),
            types::tier_organization(), b"TW".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    // submit claim (as user)
    ts::next_tx(&mut scenario, user);
    {
        claim::submit_claim(
            b"TSMC plans new fab in Arizona".to_string(),
            types::claim_factual(),
            true,
            b"https://example.com/tsmc-arizona".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    // link claim to entity
    ts::next_tx(&mut scenario, user);
    {
        let mut claim_obj = scenario.take_shared<Claim>();
        let entity_obj = scenario.take_shared<Entity>();

        claim::link_to_entity(&mut claim_obj, &entity_obj);

        assert!(claim::claim_entity_ids(&claim_obj).length() == 1);

        ts::return_shared(claim_obj);
        ts::return_shared(entity_obj);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = claim::EAlreadyLinked)]
fun test_duplicate_link_fails() {
    let admin = @0xAAAA;
    let user = @0xBBBB;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();
        registry::create_entity(
            &admin_cap, &mut reg,
            b"tsmc".to_string(), b"TSMC".to_string(),
            types::tier_organization(), b"TW".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    ts::next_tx(&mut scenario, user);
    {
        claim::submit_claim(
            b"test claim".to_string(),
            types::claim_factual(), true,
            b"https://example.com".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    ts::next_tx(&mut scenario, user);
    {
        let mut claim_obj = scenario.take_shared<Claim>();
        let entity_obj = scenario.take_shared<Entity>();

        claim::link_to_entity(&mut claim_obj, &entity_obj);
        claim::link_to_entity(&mut claim_obj, &entity_obj); // duplicate — should abort

        ts::return_shared(claim_obj);
        ts::return_shared(entity_obj);
    };

    ts::end(scenario);
}

#[test]
fun test_flag_claim() {
    let user = @0xBBBB;
    let flagger = @0xCCCC;
    let mut scenario = ts::begin(user);

    ts::next_tx(&mut scenario, user);
    {
        claim::submit_claim(
            b"Controversial claim".to_string(),
            types::claim_opinion(), false,
            b"https://example.com".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    // different user flags it
    ts::next_tx(&mut scenario, flagger);
    {
        let mut claim_obj = scenario.take_shared<Claim>();
        assert!(claim::claim_is_flagged(&claim_obj) == false);

        claim::flag_claim(&mut claim_obj, ts::ctx(&mut scenario));

        assert!(claim::claim_is_flagged(&claim_obj) == true);
        ts::return_shared(claim_obj);
    };

    ts::end(scenario);
}

#[test]
fun test_link_claim_to_multiple_entities() {
    let admin = @0xAAAA;
    let user = @0xBBBB;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    // create two entities
    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut reg = scenario.take_shared<Registry>();

        registry::create_entity(
            &admin_cap, &mut reg,
            b"tsmc".to_string(), b"TSMC".to_string(),
            types::tier_organization(), b"TW".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );

        registry::create_entity(
            &admin_cap, &mut reg,
            b"nvidia".to_string(), b"NVIDIA".to_string(),
            types::tier_organization(), b"US".to_string(), b"semiconductor".to_string(),
            ts::ctx(&mut scenario),
        );

        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(reg);
    };

    // submit claim
    ts::next_tx(&mut scenario, user);
    {
        claim::submit_claim(
            b"TSMC manufactures NVIDIA chips".to_string(),
            types::claim_factual(), true,
            b"https://example.com/supply-chain".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    // link to both entities in one transaction
    ts::next_tx(&mut scenario, user);
    {
        let mut claim_obj = scenario.take_shared<Claim>();
        let entity1 = scenario.take_shared<Entity>();
        let entity2 = scenario.take_shared<Entity>();

        claim::link_to_entity(&mut claim_obj, &entity1);
        claim::link_to_entity(&mut claim_obj, &entity2);
        assert!(claim::claim_entity_ids(&claim_obj).length() == 2);

        ts::return_shared(claim_obj);
        ts::return_shared(entity1);
        ts::return_shared(entity2);
    };

    ts::end(scenario);
}

// =========================================================================
// market.move tests
// =========================================================================

#[test]
fun test_create_market() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let claim_id = object::id_from_address(@0x1234);

        market::create_market(
            &admin_cap,
            claim_id,
            b"Will TSMC N2 hit mass production by Q3 2026?".to_string(),
            1000000,
            ts::ctx(&mut scenario),
        );

        ts::return_to_sender(&scenario, admin_cap);
    };

    ts::next_tx(&mut scenario, admin);
    {
        let mkt = scenario.take_shared<TruthMarket>();
        assert!(market::market_for_pool_value(&mkt) == 0);
        assert!(market::market_against_pool_value(&mkt) == 0);
        assert!(market::market_resolved(&mkt) == false);
        assert!(market::market_for_percentage(&mkt) == 50);
        assert!(market::market_deadline(&mkt) == 1000000);
        ts::return_shared(mkt);
    };

    ts::end(scenario);
}

#[test]
fun test_stake_for_and_against() {
    let admin = @0xAAAA;
    let user1 = @0xBBBB;
    let user2 = @0xCCCC;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        market::create_market(
            &admin_cap,
            object::id_from_address(@0x1234),
            b"Test question".to_string(),
            999999999999,
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
    };

    // user1 stakes FOR 100 SUI
    ts::next_tx(&mut scenario, user1);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let stake_coin = coin::mint_for_testing<SUI>(100, ts::ctx(&mut scenario));

        market::stake_for(&mut mkt, stake_coin, &clk, ts::ctx(&mut scenario));

        assert!(market::market_for_pool_value(&mkt) == 100);
        assert!(market::market_for_percentage(&mkt) == 100);

        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // user2 stakes AGAINST 300 SUI
    ts::next_tx(&mut scenario, user2);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let stake_coin = coin::mint_for_testing<SUI>(300, ts::ctx(&mut scenario));

        market::stake_against(&mut mkt, stake_coin, &clk, ts::ctx(&mut scenario));

        assert!(market::market_against_pool_value(&mkt) == 300);
        assert!(market::market_for_percentage(&mkt) == 25);

        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // verify receipts
    ts::next_tx(&mut scenario, user1);
    {
        let receipt = scenario.take_from_sender<StakeReceipt>();
        assert!(market::receipt_amount(&receipt) == 100);
        assert!(market::receipt_is_for(&receipt) == true);
        assert!(market::receipt_staker(&receipt) == user1);
        ts::return_to_sender(&scenario, receipt);
    };

    ts::next_tx(&mut scenario, user2);
    {
        let receipt = scenario.take_from_sender<StakeReceipt>();
        assert!(market::receipt_amount(&receipt) == 300);
        assert!(market::receipt_is_for(&receipt) == false);
        ts::return_to_sender(&scenario, receipt);
    };

    ts::end(scenario);
}

#[test]
fun test_resolve_and_claim_winnings() {
    let admin = @0xAAAA;
    let winner = @0xBBBB;
    let loser = @0xCCCC;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        market::create_market(
            &admin_cap,
            object::id_from_address(@0x1234),
            b"Test question".to_string(),
            999999999999,
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
    };

    // winner stakes FOR 200
    ts::next_tx(&mut scenario, winner);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(200, ts::ctx(&mut scenario));
        market::stake_for(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // loser stakes AGAINST 300
    ts::next_tx(&mut scenario, loser);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(300, ts::ctx(&mut scenario));
        market::stake_against(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // resolve TRUE
    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut mkt = scenario.take_shared<TruthMarket>();
        market::resolve(&admin_cap, &mut mkt, true);
        assert!(market::market_resolved(&mkt) == true);
        assert!(market::market_outcome(&mkt) == true);
        assert!(market::market_for_percentage(&mkt) == 100);
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(mkt);
    };

    // winner claims — payout = 200 * 500 / 200 = 500
    ts::next_tx(&mut scenario, winner);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let receipt = scenario.take_from_sender<StakeReceipt>();
        market::claim_winnings(&mut mkt, receipt, ts::ctx(&mut scenario));
        assert!(market::market_for_pool_value(&mkt) == 0);
        assert!(market::market_against_pool_value(&mkt) == 0);
        ts::return_shared(mkt);
    };

    ts::next_tx(&mut scenario, winner);
    {
        let payout_coin = scenario.take_from_sender<Coin<SUI>>();
        assert!(coin::value(&payout_coin) == 500);
        ts::return_to_sender(&scenario, payout_coin);
    };

    ts::end(scenario);
}

#[test]
fun test_resolve_against_side_wins() {
    let admin = @0xAAAA;
    let user_for = @0xBBBB;
    let user_against = @0xCCCC;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        market::create_market(
            &admin_cap,
            object::id_from_address(@0x1234),
            b"Test question".to_string(),
            999999999999,
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
    };

    ts::next_tx(&mut scenario, user_for);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(100, ts::ctx(&mut scenario));
        market::stake_for(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    ts::next_tx(&mut scenario, user_against);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(400, ts::ctx(&mut scenario));
        market::stake_against(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // resolve FALSE
    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut mkt = scenario.take_shared<TruthMarket>();
        market::resolve(&admin_cap, &mut mkt, false);
        assert!(market::market_for_percentage(&mkt) == 0);
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(mkt);
    };

    // user_against claims — 400 * 500 / 400 = 500
    ts::next_tx(&mut scenario, user_against);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let receipt = scenario.take_from_sender<StakeReceipt>();
        market::claim_winnings(&mut mkt, receipt, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
    };

    ts::next_tx(&mut scenario, user_against);
    {
        let payout_coin = scenario.take_from_sender<Coin<SUI>>();
        assert!(coin::value(&payout_coin) == 500);
        ts::return_to_sender(&scenario, payout_coin);
    };

    ts::end(scenario);
}

#[test]
fun test_multiple_winners_proportional() {
    let admin = @0xAAAA;
    let w1 = @0xBBBB;
    let w2 = @0xCCCC;
    let loser = @0xDDDD;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        market::create_market(
            &admin_cap,
            object::id_from_address(@0x1234),
            b"Test".to_string(),
            999999999999,
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
    };

    // w1 FOR 100
    ts::next_tx(&mut scenario, w1);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(100, ts::ctx(&mut scenario));
        market::stake_for(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // w2 FOR 300
    ts::next_tx(&mut scenario, w2);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(300, ts::ctx(&mut scenario));
        market::stake_for(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // loser AGAINST 600
    ts::next_tx(&mut scenario, loser);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(600, ts::ctx(&mut scenario));
        market::stake_against(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // resolve TRUE
    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut mkt = scenario.take_shared<TruthMarket>();
        market::resolve(&admin_cap, &mut mkt, true);
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(mkt);
    };

    // w1 claims: 100 * 1000 / 400 = 250
    ts::next_tx(&mut scenario, w1);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let receipt = scenario.take_from_sender<StakeReceipt>();
        market::claim_winnings(&mut mkt, receipt, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
    };

    ts::next_tx(&mut scenario, w1);
    {
        let payout_coin = scenario.take_from_sender<Coin<SUI>>();
        assert!(coin::value(&payout_coin) == 250);
        ts::return_to_sender(&scenario, payout_coin);
    };

    // w2 claims: 300 * 1000 / 400 = 750
    ts::next_tx(&mut scenario, w2);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let receipt = scenario.take_from_sender<StakeReceipt>();
        market::claim_winnings(&mut mkt, receipt, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
    };

    ts::next_tx(&mut scenario, w2);
    {
        let payout_coin = scenario.take_from_sender<Coin<SUI>>();
        assert!(coin::value(&payout_coin) == 750);
        ts::return_to_sender(&scenario, payout_coin);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = market::EMarketAlreadyResolved)]
fun test_stake_after_resolve_fails() {
    let admin = @0xAAAA;
    let user = @0xBBBB;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        market::create_market(
            &admin_cap,
            object::id_from_address(@0x1234),
            b"Test".to_string(),
            999999999999,
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
    };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut mkt = scenario.take_shared<TruthMarket>();
        market::resolve(&admin_cap, &mut mkt, true);
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(mkt);
    };

    ts::next_tx(&mut scenario, user);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(100, ts::ctx(&mut scenario));
        market::stake_for(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = market::EMarketAlreadyResolved)]
fun test_double_resolve_fails() {
    let admin = @0xAAAA;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        market::create_market(
            &admin_cap,
            object::id_from_address(@0x1234),
            b"Test".to_string(),
            999999999999,
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
    };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut mkt = scenario.take_shared<TruthMarket>();
        market::resolve(&admin_cap, &mut mkt, true);
        market::resolve(&admin_cap, &mut mkt, false); // should abort
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(mkt);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = market::EMarketNotResolved)]
fun test_claim_before_resolve_fails() {
    let admin = @0xAAAA;
    let user = @0xBBBB;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        market::create_market(
            &admin_cap,
            object::id_from_address(@0x1234),
            b"Test".to_string(),
            999999999999,
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
    };

    ts::next_tx(&mut scenario, user);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(100, ts::ctx(&mut scenario));
        market::stake_for(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    ts::next_tx(&mut scenario, user);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let receipt = scenario.take_from_sender<StakeReceipt>();
        market::claim_winnings(&mut mkt, receipt, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = market::EWrongSide)]
fun test_loser_claim_fails() {
    let admin = @0xAAAA;
    let loser = @0xBBBB;
    let mut scenario = ts::begin(admin);

    ts::next_tx(&mut scenario, admin);
    { registry::init_for_testing(ts::ctx(&mut scenario)); };

    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        market::create_market(
            &admin_cap,
            object::id_from_address(@0x1234),
            b"Test".to_string(),
            999999999999,
            ts::ctx(&mut scenario),
        );
        ts::return_to_sender(&scenario, admin_cap);
    };

    ts::next_tx(&mut scenario, loser);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let clk = clock::create_for_testing(ts::ctx(&mut scenario));
        let coin = coin::mint_for_testing<SUI>(100, ts::ctx(&mut scenario));
        market::stake_against(&mut mkt, coin, &clk, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
        clock::destroy_for_testing(clk);
    };

    // resolve TRUE — AGAINST loses
    ts::next_tx(&mut scenario, admin);
    {
        let admin_cap = scenario.take_from_sender<AdminCap>();
        let mut mkt = scenario.take_shared<TruthMarket>();
        market::resolve(&admin_cap, &mut mkt, true);
        ts::return_to_sender(&scenario, admin_cap);
        ts::return_shared(mkt);
    };

    ts::next_tx(&mut scenario, loser);
    {
        let mut mkt = scenario.take_shared<TruthMarket>();
        let receipt = scenario.take_from_sender<StakeReceipt>();
        market::claim_winnings(&mut mkt, receipt, ts::ctx(&mut scenario));
        ts::return_shared(mkt);
    };

    ts::end(scenario);
}

// =========================================================================
// evidence.move tests
// =========================================================================

#[test]
fun test_submit_evidence() {
    let user = @0xBBBB;
    let mut scenario = ts::begin(user);

    // submit a claim first
    ts::next_tx(&mut scenario, user);
    {
        claim::submit_claim(
            b"TSMC N2 will ship in Q3 2026".to_string(),
            types::claim_prediction(),
            true,
            b"https://example.com/tsmc".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    // submit evidence supporting the claim
    ts::next_tx(&mut scenario, user);
    {
        let claim_obj = scenario.take_shared<Claim>();

        evidence::submit_evidence(
            &claim_obj,
            b"TSMC CEO confirmed N2 timeline at earnings call".to_string(),
            b"https://reuters.com/tsmc-earnings".to_string(),
            types::edge_supports(),
            ts::ctx(&mut scenario),
        );

        ts::return_shared(claim_obj);
    };

    // verify evidence
    ts::next_tx(&mut scenario, user);
    {
        let ev = scenario.take_shared<Evidence>();
        assert!(evidence::evidence_content(&ev) == b"TSMC CEO confirmed N2 timeline at earnings call".to_string());
        assert!(evidence::evidence_edge_type(&ev) == types::edge_supports());
        assert!(evidence::evidence_submitter(&ev) == user);
        ts::return_shared(ev);
    };

    ts::end(scenario);
}

#[test]
fun test_submit_contradicting_evidence() {
    let user1 = @0xBBBB;
    let user2 = @0xCCCC;
    let mut scenario = ts::begin(user1);

    ts::next_tx(&mut scenario, user1);
    {
        claim::submit_claim(
            b"Bitcoin will reach 100k by end of year".to_string(),
            types::claim_prediction(),
            false,
            b"https://example.com".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    // user2 submits contradicting evidence
    ts::next_tx(&mut scenario, user2);
    {
        let claim_obj = scenario.take_shared<Claim>();

        evidence::submit_evidence(
            &claim_obj,
            b"Federal Reserve signals rate hikes, bearish for crypto".to_string(),
            b"https://bloomberg.com/fed".to_string(),
            types::edge_contradicts(),
            ts::ctx(&mut scenario),
        );

        ts::return_shared(claim_obj);
    };

    ts::next_tx(&mut scenario, user2);
    {
        let ev = scenario.take_shared<Evidence>();
        assert!(evidence::evidence_edge_type(&ev) == types::edge_contradicts());
        assert!(evidence::evidence_submitter(&ev) == user2);
        ts::return_shared(ev);
    };

    ts::end(scenario);
}

#[test, expected_failure(abort_code = evidence::EInvalidEdgeType)]
fun test_invalid_edge_type_evidence_fails() {
    let user = @0xBBBB;
    let mut scenario = ts::begin(user);

    ts::next_tx(&mut scenario, user);
    {
        claim::submit_claim(
            b"Test claim".to_string(),
            types::claim_factual(), true,
            b"https://example.com".to_string(),
            ts::ctx(&mut scenario),
        );
    };

    ts::next_tx(&mut scenario, user);
    {
        let claim_obj = scenario.take_shared<Claim>();
        evidence::submit_evidence(
            &claim_obj,
            b"Some evidence".to_string(),
            b"https://example.com".to_string(),
            99, // invalid edge type
            ts::ctx(&mut scenario),
        );
        ts::return_shared(claim_obj);
    };

    ts::end(scenario);
}
