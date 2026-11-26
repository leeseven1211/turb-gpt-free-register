# -*- coding: utf-8 -*-
"""优惠筛选隔离基准的纯函数约束。"""

from tools.benchmarks import benchmark_account_promotions as benchmark


def test_synthetic_definitions_cover_nine_offer_rows_and_expected_keys():
    definitions = benchmark.synthetic_offer_definitions()

    assert len(definitions) == 9
    assert {item.plan for item in definitions} == {"team", "go", "plus"}
    assert {item.kind for item in definitions} == {"free_trial", "discount"}
    assert len(benchmark.synthetic_expected_offer_names(definitions)) == 9


def test_legacy_offer_codes_preserve_json_and_legacy_plus_semantics():
    json_offers = [
        {
            "plan": "plus",
            "kind": "discount",
            "eligible": True,
            "discount_percentage": 50,
            "duration_num_periods": 2,
            "duration_period": "month",
        },
        {
            "plan": "team",
            "kind": "free_trial",
            "eligible": True,
            "discount_percentage": None,
        },
    ]

    assert benchmark.legacy_offer_codes(json_offers) == [
        "plus_50",
        "plus_50_2m",
        "team_eligible",
    ]
    assert benchmark.legacy_offer_codes(
        None,
        legacy_kind="discount",
        legacy_percentage=50,
        legacy_periods=2,
        legacy_period="month",
    ) == ["plus_50", "plus_50_2m"]


def test_sample_summary_omits_p95_when_sample_count_is_below_thirty():
    summary = benchmark.summarize_samples(
        [{"milliseconds": float(value)} for value in range(1, 4)]
    )

    assert summary["samples"] == 3
    assert "p95_ms" not in summary


def test_cli_cannot_bypass_isolated_environment_with_hidden_mode():
    parser = benchmark._parser()

    try:
        parser.parse_args(["--isolated"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("不应接受可复用 schema 的 --isolated 入口")


def test_synthetic_truth_deduplicates_same_offer_across_countries():
    definitions = benchmark.synthetic_offer_definitions()
    truth = benchmark.synthetic_offer_truth(50, definitions)

    team_key = benchmark._offer_key(definitions[0])
    assert team_key in truth
    assert all(isinstance(value, set) for value in truth.values())
    assert len(truth[team_key]) == len(set(truth[team_key]))


def test_id_to_ordinal_mapping_does_not_assume_sequential_database_ids():
    mapping = {101: 9007, 205: 9001, 999: 9004}

    assert benchmark.map_account_ids_to_ordinals([999, 101], mapping) == {9004, 9007}


def test_dynamic_facet_truth_rejects_extra_keys_and_wrong_counts():
    expected = {"offer_v1_a": {1, 4}, "offer_v1_b": {2}}

    assert benchmark.validate_dynamic_facet_truth(
        {"offer_v1_a": 2, "offer_v1_b": 1}, expected
    ) is True
    for actual in (
        {"offer_v1_a": 3, "offer_v1_b": 1},
        {"offer_v1_a": 2, "offer_v1_b": 1, "offer_v1_extra": 1},
    ):
        try:
            benchmark.validate_dynamic_facet_truth(actual, expected)
        except AssertionError:
            continue
        raise AssertionError(f"错误 key/count 未被拒绝: {actual}")


def test_old_facets_only_projects_json_for_legacy_offer_filters():
    for values in ((), ("free_trial",), ("half_price",)):
        sql, _params = benchmark._old_facets_query(values)
        assert "jsonb_array_elements" not in sql

    sql, _params = benchmark._old_facets_query(("team_eligible",))
    assert "jsonb_array_elements" in sql
