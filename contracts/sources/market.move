/// Truth Market — binary prediction market for verifiable claims.
///
/// Design (Version A — fixed-ratio payout, hackathon scope):
/// - TruthMarket is a Shared Object: anyone can stake FOR or AGAINST
/// - StakeReceipt is an Owned Object transferred to the staker
/// - AdminCap holder creates markets and triggers resolution
/// - Winners split the total pool proportionally to their stake
/// - for_percentage tracks live market sentiment for frontend display
#[allow(lint(self_transfer))]
module sugar_protocol::market;

use std::string::String;
use sui::coin::{Self, Coin};
use sui::balance::{Self, Balance};
use sui::sui::SUI;
use sui::clock::Clock;
use sui::event;
use sugar_protocol::registry::AdminCap;

// =========================================================================
// Errors
// =========================================================================

#[error]
const EMarketExpired: vector<u8> = b"Market has passed its deadline";
#[error]
const EMarketAlreadyResolved: vector<u8> = b"Market has already been resolved";
#[error]
const EMarketNotResolved: vector<u8> = b"Market has not been resolved yet";
#[error]
const EWrongMarket: vector<u8> = b"Receipt does not belong to this market";
#[error]
const EWrongSide: vector<u8> = b"Receipt is on the losing side";
#[error]
const EZeroStake: vector<u8> = b"Stake amount must be greater than zero";
#[error]
const EPoolEmpty: vector<u8> = b"Winning pool is empty";

// =========================================================================
// Structs
// =========================================================================

/// A binary prediction market tied to a Claim.
/// Shared Object — anyone can read and stake.
public struct TruthMarket has key {
    id: UID,
    claim_id: ID,
    question: String,
    for_pool: Balance<SUI>,
    against_pool: Balance<SUI>,
    for_staked: u64,        // cumulative FOR stakes (never decremented)
    against_staked: u64,    // cumulative AGAINST stakes (never decremented)
    deadline: u64,
    resolved: bool,
    outcome: bool,          // meaningful only when resolved == true
    for_percentage: u64,    // 0-100, updated on every stake; frontend display
    creator: address,
}

/// Proof of stake — held by the staker, burned on claim_winnings.
public struct StakeReceipt has key, store {
    id: UID,
    market_id: ID,
    amount: u64,
    is_for: bool,
    staker: address,
}

// =========================================================================
// Events
// =========================================================================

public struct MarketCreated has copy, drop {
    market_id: ID,
    claim_id: ID,
    question: String,
    deadline: u64,
}

public struct Staked has copy, drop {
    market_id: ID,
    staker: address,
    amount: u64,
    is_for: bool,
    for_percentage: u64,
}

public struct MarketResolved has copy, drop {
    market_id: ID,
    outcome: bool,
}

public struct WinningsClaimed has copy, drop {
    market_id: ID,
    staker: address,
    payout: u64,
}

// =========================================================================
// Public functions
// =========================================================================

/// Create a new Truth Market for a claim. Requires AdminCap.
public fun create_market(
    _: &AdminCap,
    claim_id: ID,
    question: String,
    deadline: u64,
    ctx: &mut TxContext,
) {
    let market = TruthMarket {
        id: object::new(ctx),
        claim_id,
        question,
        for_pool: balance::zero(),
        against_pool: balance::zero(),
        for_staked: 0,
        against_staked: 0,
        deadline,
        resolved: false,
        outcome: false,
        for_percentage: 50, // neutral starting point
        creator: ctx.sender(),
    };

    event::emit(MarketCreated {
        market_id: object::id(&market),
        claim_id,
        question,
        deadline,
    });

    transfer::share_object(market);
}

/// Stake SUI in favour of the claim being true.
public fun stake_for(
    market: &mut TruthMarket,
    stake: Coin<SUI>,
    clock: &Clock,
    ctx: &mut TxContext,
) {
    let amount = coin::value(&stake);
    assert!(amount > 0, EZeroStake);
    assert!(!market.resolved, EMarketAlreadyResolved);
    assert!(clock.timestamp_ms() < market.deadline, EMarketExpired);

    market.for_pool.join(coin::into_balance(stake));
    market.for_staked = market.for_staked + amount;
    update_percentage(market);

    let receipt = StakeReceipt {
        id: object::new(ctx),
        market_id: object::id(market),
        amount,
        is_for: true,
        staker: ctx.sender(),
    };

    event::emit(Staked {
        market_id: object::id(market),
        staker: ctx.sender(),
        amount,
        is_for: true,
        for_percentage: market.for_percentage,
    });

    transfer::transfer(receipt, ctx.sender());
}

/// Stake SUI against the claim (claim is false).
public fun stake_against(
    market: &mut TruthMarket,
    stake: Coin<SUI>,
    clock: &Clock,
    ctx: &mut TxContext,
) {
    let amount = coin::value(&stake);
    assert!(amount > 0, EZeroStake);
    assert!(!market.resolved, EMarketAlreadyResolved);
    assert!(clock.timestamp_ms() < market.deadline, EMarketExpired);

    market.against_pool.join(coin::into_balance(stake));
    market.against_staked = market.against_staked + amount;
    update_percentage(market);

    let receipt = StakeReceipt {
        id: object::new(ctx),
        market_id: object::id(market),
        amount,
        is_for: false,
        staker: ctx.sender(),
    };

    event::emit(Staked {
        market_id: object::id(market),
        staker: ctx.sender(),
        amount,
        is_for: false,
        for_percentage: market.for_percentage,
    });

    transfer::transfer(receipt, ctx.sender());
}

/// Resolve the market. Only AdminCap holder can call (triggered by backend
/// after CRE workflow writes result to EVM).
public fun resolve(
    _: &AdminCap,
    market: &mut TruthMarket,
    outcome: bool,
) {
    assert!(!market.resolved, EMarketAlreadyResolved);

    market.resolved = true;
    market.outcome = outcome;
    // Final percentage reflects outcome
    market.for_percentage = if (outcome) 100 else 0;

    event::emit(MarketResolved {
        market_id: object::id(market),
        outcome,
    });
}

/// Claim winnings by burning a StakeReceipt on the winning side.
/// Payout = (staker_amount / winning_pool_total) * total_pool
public fun claim_winnings(
    market: &mut TruthMarket,
    receipt: StakeReceipt,
    ctx: &mut TxContext,
) {
    assert!(market.resolved, EMarketNotResolved);
    assert!(receipt.market_id == object::id(market), EWrongMarket);
    assert!(receipt.is_for == market.outcome, EWrongSide);

    // Use original staked totals (not current pool values) for proportional calc
    let winning_staked = if (market.outcome) market.for_staked else market.against_staked;
    assert!(winning_staked > 0, EPoolEmpty);

    let total_staked = market.for_staked + market.against_staked;

    // payout = receipt.amount * total_staked / winning_staked
    // Use u128 to avoid overflow on multiplication
    let payout = (
        (receipt.amount as u128) * (total_staked as u128) / (winning_staked as u128)
    ) as u64;

    // Take payout from losing pool first, then winning pool for remainder
    let mut payout_balance = balance::zero<SUI>();

    if (market.outcome) {
        // Winner is FOR side — drain against_pool (loser) first, then for_pool
        let from_against = min(payout, market.against_pool.value());
        if (from_against > 0) {
            payout_balance.join(market.against_pool.split(from_against));
        };
        let remaining = payout - from_against;
        if (remaining > 0) {
            payout_balance.join(market.for_pool.split(remaining));
        };
    } else {
        // Winner is AGAINST side — drain for_pool (loser) first, then against_pool
        let from_for = min(payout, market.for_pool.value());
        if (from_for > 0) {
            payout_balance.join(market.for_pool.split(from_for));
        };
        let remaining = payout - from_for;
        if (remaining > 0) {
            payout_balance.join(market.against_pool.split(remaining));
        };
    };

    let staker = receipt.staker;

    event::emit(WinningsClaimed {
        market_id: object::id(market),
        staker,
        payout,
    });

    // Burn the receipt
    let StakeReceipt { id, market_id: _, amount: _, is_for: _, staker: _ } = receipt;
    object::delete(id);

    // Send payout to staker
    transfer::public_transfer(coin::from_balance(payout_balance, ctx), staker);
}

// =========================================================================
// Internal helpers
// =========================================================================

fun update_percentage(market: &mut TruthMarket) {
    let for_val = market.for_pool.value();
    let against_val = market.against_pool.value();
    let total = for_val + against_val;
    market.for_percentage = if (total == 0) {
        50
    } else {
        ((for_val as u128) * 100 / (total as u128)) as u64
    };
}

fun min(a: u64, b: u64): u64 {
    if (a < b) a else b
}

// =========================================================================
// Getters
// =========================================================================

public fun market_claim_id(market: &TruthMarket): ID { market.claim_id }
public fun market_question(market: &TruthMarket): String { market.question }
public fun market_for_pool_value(market: &TruthMarket): u64 { market.for_pool.value() }
public fun market_against_pool_value(market: &TruthMarket): u64 { market.against_pool.value() }
public fun market_for_staked(market: &TruthMarket): u64 { market.for_staked }
public fun market_against_staked(market: &TruthMarket): u64 { market.against_staked }
public fun market_deadline(market: &TruthMarket): u64 { market.deadline }
public fun market_resolved(market: &TruthMarket): bool { market.resolved }
public fun market_outcome(market: &TruthMarket): bool { market.outcome }
public fun market_for_percentage(market: &TruthMarket): u64 { market.for_percentage }
public fun market_creator(market: &TruthMarket): address { market.creator }

public fun receipt_market_id(receipt: &StakeReceipt): ID { receipt.market_id }
public fun receipt_amount(receipt: &StakeReceipt): u64 { receipt.amount }
public fun receipt_is_for(receipt: &StakeReceipt): bool { receipt.is_for }
public fun receipt_staker(receipt: &StakeReceipt): address { receipt.staker }

// =========================================================================
// Test-only helpers
// =========================================================================

#[test_only]
public fun destroy_receipt_for_testing(receipt: StakeReceipt) {
    let StakeReceipt { id, market_id: _, amount: _, is_for: _, staker: _ } = receipt;
    object::delete(id);
}
