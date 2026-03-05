#[test_only]
module sugar_protocol::core_tests {
    use std::string;
    use std::vector;
    use sui::test_scenario::{Self, Scenario};
    use sui::clock::{Self};
    use sui::object;
    use sugar_protocol::core::{Self, SugarGrain};

    const ADMIN: address = @0xA;
    const USER: address = @0xB;

    fun init_test_scenario(): Scenario {
        test_scenario::begin(ADMIN)
    }

    // ── 正常路徑測試 ──

    #[test]
    fun test_mint_genesis_grain() {
        let scenario = init_test_scenario();
        let ctx = test_scenario::ctx(&mut scenario);

        let clock = clock::create_for_testing(ctx);
        clock::share_for_testing(clock);

        test_scenario::next_tx(&mut scenario, USER);
        {
            let clock = test_scenario::take_shared<sui::clock::Clock>(&scenario);
            let ctx = test_scenario::ctx(&mut scenario);

            core::mint_grain(
                string::utf8(b"Bitcoin is a decentralized currency."),
                vector::empty<sui::object::ID>(),
                0, // GENESIS
                string::utf8(b"https://whitepaper.io"),
                &clock,
                ctx
            );

            test_scenario::return_shared(clock);
        };

        // 驗證共享物件已建立，並用 getter 檢查欄位
        test_scenario::next_tx(&mut scenario, USER);
        {
            let grain = test_scenario::take_shared<SugarGrain>(&scenario);
            assert!(core::bond_type(&grain) == 0, 0);
            assert!(core::purity_score(&grain) == 100, 0);
            assert!(*core::content(&grain) == string::utf8(b"Bitcoin is a decentralized currency."), 0);
            assert!(vector::is_empty(core::parents(&grain)), 0);
            test_scenario::return_shared(grain);
        };

        test_scenario::end(scenario);
    }

    #[test]
    fun test_mint_derived_grain_with_parent() {
        let scenario = init_test_scenario();
        let ctx = test_scenario::ctx(&mut scenario);

        let clock = clock::create_for_testing(ctx);
        clock::share_for_testing(clock);

        // 1. 先鑄造一顆創世糖粒
        test_scenario::next_tx(&mut scenario, USER);
        {
            let clock = test_scenario::take_shared<sui::clock::Clock>(&scenario);
            let ctx = test_scenario::ctx(&mut scenario);

            core::mint_grain(
                string::utf8(b"Bitcoin"),
                vector::empty<sui::object::ID>(),
                0,
                string::utf8(b"https://example.com"),
                &clock,
                ctx
            );

            test_scenario::return_shared(clock);
        };

        // 2. 取得創世糖粒的 ID，鑄造衍生糖粒
        test_scenario::next_tx(&mut scenario, USER);
        {
            let genesis_grain = test_scenario::take_shared<SugarGrain>(&scenario);
            let genesis_id = object::id(&genesis_grain);
            let clock = test_scenario::take_shared<sui::clock::Clock>(&scenario);
            let ctx = test_scenario::ctx(&mut scenario);

            let parents = vector::empty<sui::object::ID>();
            vector::push_back(&mut parents, genesis_id);

            core::mint_grain(
                string::utf8(b"Bitcoin is bullish"),
                parents,
                1, // DERIVED
                string::utf8(b"https://example.com"),
                &clock,
                ctx
            );

            test_scenario::return_shared(genesis_grain);
            test_scenario::return_shared(clock);
        };

        // 3. 驗證兩顆糖粒都存在
        test_scenario::next_tx(&mut scenario, USER);
        {
            let grain1 = test_scenario::take_shared<SugarGrain>(&scenario);
            let grain2 = test_scenario::take_shared<SugarGrain>(&scenario);
            test_scenario::return_shared(grain1);
            test_scenario::return_shared(grain2);
        };

        test_scenario::end(scenario);
    }

    #[test]
    fun test_update_purity_score() {
        let scenario = init_test_scenario();
        let ctx = test_scenario::ctx(&mut scenario);

        let clock = clock::create_for_testing(ctx);
        clock::share_for_testing(clock);

        test_scenario::next_tx(&mut scenario, USER);
        {
            let clock = test_scenario::take_shared<sui::clock::Clock>(&scenario);
            let ctx = test_scenario::ctx(&mut scenario);

            core::mint_grain(
                string::utf8(b"Test purity"),
                vector::empty<sui::object::ID>(),
                0,
                string::utf8(b"https://example.com"),
                &clock,
                ctx
            );

            test_scenario::return_shared(clock);
        };

        test_scenario::next_tx(&mut scenario, USER);
        {
            let grain = test_scenario::take_shared<SugarGrain>(&scenario);
            assert!(core::purity_score(&grain) == 100, 0);
            core::update_purity_score(&mut grain, 42);
            assert!(core::purity_score(&grain) == 42, 0);
            test_scenario::return_shared(grain);
        };

        test_scenario::end(scenario);
    }

    // ── bond_type 邊界驗證 ──

    #[test]
    fun test_all_valid_bond_types() {
        let scenario = init_test_scenario();
        let ctx = test_scenario::ctx(&mut scenario);

        let clock = clock::create_for_testing(ctx);
        clock::share_for_testing(clock);

        // 測試 bond_type 0 (GENESIS) 到 4 (CORROBORATES) 都合法
        let bond_type = 0u8;
        while (bond_type <= 4) {
            test_scenario::next_tx(&mut scenario, USER);
            {
                let clock = test_scenario::take_shared<sui::clock::Clock>(&scenario);
                let ctx = test_scenario::ctx(&mut scenario);

                core::mint_grain(
                    string::utf8(b"Test content"),
                    vector::empty<sui::object::ID>(),
                    bond_type,
                    string::utf8(b"https://example.com"),
                    &clock,
                    ctx
                );

                test_scenario::return_shared(clock);
            };
            bond_type = bond_type + 1;
        };

        test_scenario::end(scenario);
    }

    #[test, expected_failure(abort_code = sugar_protocol::core::EInvalidBondType)]
    fun test_bond_type_5_aborts() {
        let scenario = init_test_scenario();
        let ctx = test_scenario::ctx(&mut scenario);

        let clock = clock::create_for_testing(ctx);
        clock::share_for_testing(clock);

        test_scenario::next_tx(&mut scenario, USER);
        {
            let clock = test_scenario::take_shared<sui::clock::Clock>(&scenario);
            let ctx = test_scenario::ctx(&mut scenario);

            // bond_type 5 超出範圍，應該 abort
            core::mint_grain(
                string::utf8(b"Invalid bond type"),
                vector::empty<sui::object::ID>(),
                5,
                string::utf8(b"https://example.com"),
                &clock,
                ctx
            );

            test_scenario::return_shared(clock);
        };

        test_scenario::end(scenario);
    }

    #[test, expected_failure(abort_code = sugar_protocol::core::EInvalidBondType)]
    fun test_bond_type_255_aborts() {
        let scenario = init_test_scenario();
        let ctx = test_scenario::ctx(&mut scenario);

        let clock = clock::create_for_testing(ctx);
        clock::share_for_testing(clock);

        test_scenario::next_tx(&mut scenario, USER);
        {
            let clock = test_scenario::take_shared<sui::clock::Clock>(&scenario);
            let ctx = test_scenario::ctx(&mut scenario);

            // u8 最大值 255，也應該 abort
            core::mint_grain(
                string::utf8(b"Max u8 bond type"),
                vector::empty<sui::object::ID>(),
                255,
                string::utf8(b"https://example.com"),
                &clock,
                ctx
            );

            test_scenario::return_shared(clock);
        };

        test_scenario::end(scenario);
    }
}
