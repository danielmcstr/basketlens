"""Integration tests for Phase 3 Event Replay engine, Cache-Aside 360º view, and Business Questions."""

from __future__ import annotations

import json

from basketlens import PROJECT_ROOT
from basketlens.connections import get_redis_client
from basketlens.ingestion import ingest_redis_state
from basketlens.queries import (
    benchmark_cache_aside_latency,
    build_360_view,
    get_active_campaigns_for_household,
    get_avg_weekly_spend_by_demographic,
    get_household_product_history,
    get_household_profile_and_recent_history,
    get_product_causal_promotion_lift,
    get_store_weekly_showcase,
)
from basketlens.replay import (
    prepare_replay_baseline,
    replay_range,
    restore_full_historical_state,
)
from basketlens.schemas.redis_schema import clear_redis_namespace


def test_zero_in_memory_and_no_allow_filtering_in_replay_and_queries() -> None:
    """Verify replay uses out-of-core Polars and query library never reads CSVs or uses ALLOW FILTERING."""
    replay_source = (PROJECT_ROOT / "src/basketlens/replay/engine.py").read_text(encoding="utf-8")
    assert "pl.read_csv(" not in replay_source
    assert "pl.scan_csv(" in replay_source

    for rel_path in (
        "src/basketlens/queries/view_360.py",
        "src/basketlens/queries/business_questions.py",
    ):
        source = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        assert "read_csv" not in source, f"Forbidden CSV read in {rel_path}"
        assert "scan_csv" not in source, f"Query module {rel_path} must query databases directly"
        # Ensure no CQL string contains ALLOW FILTERING
        cql_Allow = [
            line
            for line in source.splitlines()
            if "ALLOW FILTERING" in line and not line.strip().startswith("#") and "docstring" not in line
        ]
        assert not cql_Allow, f"Forbidden ALLOW FILTERING in {rel_path}: {cql_Allow}"


def test_event_replay_day_654_checkout_and_campaign_22_expiration() -> None:
    """Verify baseline at Day 649, John Smith (#208) Day 654 checkout/redemption, and Day 657 TTL expiry."""
    try:
        baseline = prepare_replay_baseline(cutoff_day=649, seconds_per_day=5)
        assert baseline["household_208_baseline"]["last_day"] == 647
        assert len(baseline["household_208_baseline"]["recent_basket_ids"]) == 5

        logs_650_654 = replay_range(
            start_day=650,
            end_day=654,
            seconds_per_day=5,
            watch_household=208,
            prime_watched_cache_each_day=True,
        )
        day_654 = logs_650_654[-1]
        assert day_654["day"] == 654

        w208 = day_654["watched_household"]
        assert w208["purchased_today"] is True
        assert 41531980403 in w208["basket_ids_today"]
        assert "51800000050" in w208["redeemed_coupons_today"]
        assert w208["cache_existed_before_del"] is True
        assert w208["cache_del_executed"] is True
        assert w208["cache_exists_after_del"] is False
        assert w208["mongo_last_day"] == 654
        assert w208["mongo_recent_baskets_count"] == 5
        assert 41531980403 in w208["mongo_recent_basket_ids"]

        # Verify Cassandra transactions_by_household and transactions_by_household_product have Day 654
        q1_654 = get_household_profile_and_recent_history(208, limit=10)
        assert q1_654["recent_transactions"][0]["day"] == 654
        assert q1_654["recent_transactions"][0]["basket_id"] == 41531980403

        prod_654 = get_household_product_history(208, 1017772)
        assert prod_654["purchases"][0]["day"] == 654
        assert prod_654["purchases"][0]["basket_id"] == 41531980403

        # Advance through Day 657 and verify Campaign 22 (END_DAY = 656) expires in Redis
        logs_655_657 = replay_range(
            start_day=655,
            end_day=657,
            seconds_per_day=2,
            watch_household=208,
        )
        day_657 = logs_655_657[-1]
        assert day_657["redis"]["campaign_22_ttl"] <= 0

        redis_client = get_redis_client()
        try:
            assert redis_client.ttl("campanha:22") <= 0
        finally:
            redis_client.close()

        active_after_656 = get_active_campaigns_for_household(208)
        active_ids = [c["campaign"] for c in active_after_656["active_campaigns"]]
        assert 22 not in active_ids
    finally:
        # Restore full historical state (cutoff_day=711, reference_day=650) for subsequent tests
        restore_full_historical_state(cutoff_day=711, reference_day=650, seconds_per_day=5)


def test_build_360_view_cache_aside_miss_and_hit() -> None:
    """Verify `build_360_view(208)` transitions from Cache Miss (MongoDB) to Cache Hit (Redis)."""
    ingest_redis_state(reference_day=650, seconds_per_day=5)
    clear_redis_namespace(pattern="profile:*")

    miss_view = build_360_view(208, limit_transactions=15, use_cache=True)
    assert miss_view["cache"]["cache_hit"] is False
    assert miss_view["cache"]["source"] == "mongodb"
    assert miss_view["cache"]["ttl_remaining_seconds"] > 0
    assert miss_view["profile"] is not None
    assert len(miss_view["recent_transactions"]) == 15
    assert miss_view["active_campaign_count"] >= 1

    hit_view = build_360_view(208, limit_transactions=15, use_cache=True)
    assert hit_view["cache"]["cache_hit"] is True
    assert hit_view["cache"]["source"] == "redis"
    assert hit_view["behavior_summary"]["total_baskets"] == 140

    bench = benchmark_cache_aside_latency(household_key=208, iterations=5)
    assert bench["avg_cache_miss_ms"] > 0
    assert bench["avg_cache_hit_ms"] > 0


def test_business_questions_1_2_3_and_trade_marketing_bonus() -> None:
    """Verify Business Questions 1, 2, 3 and Trade Marketing bonus queries."""
    ingest_redis_state(reference_day=650, seconds_per_day=5)

    # Question 1: Profile + ordered recent history
    q1 = get_household_profile_and_recent_history(208, limit=20)
    assert q1["profile"]["household_key"] == 208
    assert len(q1["recent_baskets"]) == 5
    assert len(q1["recent_transactions"]) == 20
    week_day_pairs = [(r["week_no"], r["day"]) for r in q1["recent_transactions"]]
    assert week_day_pairs == sorted(week_day_pairs, reverse=True)

    # Question 2: Active campaigns and coupons on Day 650
    q2 = get_active_campaigns_for_household(208)
    camp_22_list = [c for c in q2["active_campaigns"] if c["campaign"] == 22]
    assert len(camp_22_list) == 1
    camp_22 = camp_22_list[0]
    assert camp_22["description"] == "TypeB"
    assert camp_22["start_day"] == 624
    assert camp_22["end_day"] == 656
    assert camp_22["ttl_seconds"] > 0
    coupon_upcs = [c["coupon_upc"] for c in camp_22["coupons"]]
    assert "51800000050" in coupon_upcs

    # Question 3: Average weekly spend by `classification_1` and `classification_3`
    q3_c1 = get_avg_weekly_spend_by_demographic("classification_1")
    assert q3_c1["total_demographic_households"] == 801
    assert q3_c1["allow_filtering_used"] is False
    assert len(q3_c1["groups"]) == 6
    assert sum(g["household_count"] for g in q3_c1["groups"]) == 801
    assert all(g["avg_weekly_spend"] > 0 for g in q3_c1["groups"])

    q3_c3 = get_avg_weekly_spend_by_demographic("classification_3")
    assert q3_c3["total_demographic_households"] == 801
    assert q3_c3["allow_filtering_used"] is False
    assert len(q3_c3["groups"]) == 12
    assert sum(g["household_count"] for g in q3_c3["groups"]) == 801

    # Bonus Trade Marketing: Product 72717 causal lift & weekly showcase
    lift_72717 = get_product_causal_promotion_lift(72717)
    assert lift_72717["product_id"] == 72717
    week40 = [w for w in lift_72717["weekly_breakdown"] if w["week_no"] == 40]
    assert len(week40) == 1
    assert week40[0]["total_units"] == 2
    assert week40[0]["total_sales"] == 2.5
    assert "2" in week40[0]["active_display_codes"]
    assert "A" in week40[0]["active_mailer_codes"]

    showcase = get_store_weekly_showcase(store_id=288, week_no=94, top_n=10)
    assert len(showcase["top_commodities"]) == 10
    assert showcase["displayed_products_count"] > 0


def test_notebooks_03_and_04_executed_with_outputs() -> None:
    """Verify notebooks 03 and 04 exist and contain executed code cell outputs."""
    for nb_name in (
        "03_event_replay_streaming.ipynb",
        "04_polyglot_360_analytics.ipynb",
    ):
        nb_path = PROJECT_ROOT / "notebooks" / nb_name
        assert nb_path.is_file(), f"Missing notebook {nb_path}"
        nb_data = json.loads(nb_path.read_text(encoding="utf-8"))
        code_cells = [c for c in nb_data.get("cells", []) if c.get("cell_type") == "code"]
        assert len(code_cells) >= 4
        for cell in code_cells:
            assert cell.get("execution_count") is not None
            assert len(cell.get("outputs", [])) > 0
