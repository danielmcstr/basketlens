"""Integration tests for Phase 1 Docker infrastructure, polyglot connections, and schemas."""

from __future__ import annotations

import urllib.request

from basketlens import PROJECT_ROOT, check_all_connections, initialize_all_schemas
from basketlens.connections import (
    cassandra_session_scope,
    get_mongo_client,
    get_mongo_db,
    get_redis_client,
)
from basketlens.schemas.cassandra_schema import CASSANDRA_TABLES, ensure_cassandra_schema
from basketlens.schemas.mongo_schema import (
    HOUSEHOLDS_COLLECTION,
    ensure_mongo_indexes,
    explain_query,
)
from basketlens.schemas.redis_schema import (
    campaign_coupons_key,
    campaign_key,
    clear_redis_namespace,
    compute_campaign_ttl_seconds,
    coupon_key,
    household_campaigns_key,
    household_coupons_key,
    profile_key,
    ranking_week_key,
    store_week_displays_key,
)


def test_docker_compose_manifest_pins_required_images_and_containers() -> None:
    """Verify docker-compose.yml defines pinned images, containers, heap settings, and UIs."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    assert compose_path.is_file()
    content = compose_path.read_text(encoding="utf-8")

    for expected in (
        "mongo:8.0.4",
        "basketlens-mongo",
        "cassandra:5.0.2",
        "basketlens-cassandra",
        "MAX_HEAP_SIZE: \"1536M\"",
        "HEAP_NEWSIZE: \"384M\"",
        "redis:7.4.2-alpine",
        "basketlens-redis",
        "mongo-express:1.0.2-20-alpine3.19",
        "delermando/cassandra-web:0.4.0",
        "rediscommander/redis-commander:latest",
        "service_healthy",
    ):
        assert expected in content, f"Missing expected entry in docker-compose.yml: {expected}"


def test_web_uis_respond_http_200() -> None:
    """Verify mongo-express (8081), cassandra-web (3000), and redis-commander (8082) respond."""
    for url in (
        "http://localhost:8081",
        "http://localhost:3000",
        "http://localhost:8082",
    ):
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            assert response.status == 200, f"Expected HTTP 200 from {url}, got {response.status}"


def test_check_all_connections_healthy() -> None:
    """Verify check_all_connections reports True for MongoDB, Cassandra, and Redis."""
    status = check_all_connections()
    assert status == {
        "mongodb": True,
        "cassandra": True,
        "redis": True,
    }


def test_mongo_indexes_and_explain_query() -> None:
    """Verify idempotent creation of the 3 households indexes and explain('executionStats')."""
    client = get_mongo_client()
    try:
        db = get_mongo_db(client=client)
        # Call twice to assert idempotency
        ensure_mongo_indexes(db)
        index_info = ensure_mongo_indexes(db)

        assert "idx_household_key_unique" in index_info
        assert index_info["idx_household_key_unique"]["key"] == [("household_key", 1)]
        assert index_info["idx_household_key_unique"].get("unique") is True

        assert "idx_demographics_class1_class3" in index_info
        assert index_info["idx_demographics_class1_class3"]["key"] == [
            ("demographics.classification_1", 1),
            ("demographics.classification_3", 1),
        ]

        assert "idx_behavior_avg_weekly_spend_desc" in index_info
        assert index_info["idx_behavior_avg_weekly_spend_desc"]["key"] == [
            ("behavior_summary.avg_weekly_spend", -1),
        ]

        plan = explain_query(db[HOUSEHOLDS_COLLECTION], {"household_key": 208})
        assert "queryPlanner" in plan
        assert "executionStats" in plan
        assert "idx_household_key_unique" in str(plan["queryPlanner"]["winningPlan"])
    finally:
        client.close()


def test_cassandra_keyspace_and_four_query_driven_tables() -> None:
    """Verify keyspace `basketlens` and the 4 query-driven CQL tables and column types."""
    with cassandra_session_scope() as session:
        tables = ensure_cassandra_schema(session)
        assert set(CASSANDRA_TABLES).issubset(set(tables))

        # Verify clustering order of transactions_by_household
        clustering_rows = list(
            session.execute(
                """
                SELECT column_name, kind, clustering_order, position
                FROM system_schema.columns
                WHERE keyspace_name = 'basketlens'
                  AND table_name = 'transactions_by_household'
                """
            )
        )
        col_map = {row.column_name: row for row in clustering_rows}
        assert col_map["household_key"].kind == "partition_key"
        assert col_map["week_no"].kind == "clustering"
        assert col_map["week_no"].clustering_order == "desc"
        assert col_map["day"].kind == "clustering"
        assert col_map["day"].clustering_order == "desc"
        assert col_map["basket_id"].kind == "clustering"
        assert col_map["product_id"].kind == "clustering"

        # Verify causal_promotions_by_store_week uses text for display_type and mailer_page
        causal_cols = {
            row.column_name: row.type
            for row in session.execute(
                """
                SELECT column_name, type
                FROM system_schema.columns
                WHERE keyspace_name = 'basketlens'
                  AND table_name = 'causal_promotions_by_store_week'
                """
            )
        }
        assert causal_cols["display_type"] == "text"
        assert causal_cols["mailer_page"] == "text"


def test_redis_canonical_key_builders_and_namespace_cleanup() -> None:
    """Verify canonical Redis key builders for Case Study #208 and namespace operations."""
    assert profile_key(208) == "profile:208"
    assert household_campaigns_key(208) == "household:208:campaigns"
    assert household_coupons_key(208) == "household:208:coupons"
    assert campaign_key(22) == "campanha:22"
    assert campaign_coupons_key(22) == "campanha:22:coupons"
    assert coupon_key("51800000050") == "cupom:51800000050"
    assert ranking_week_key(93) == "ranking:week:93"
    assert store_week_displays_key(367, 93) == "store:367:week:93:displays"
    assert compute_campaign_ttl_seconds(end_day=656, reference_day=650, seconds_per_day=5) == 30

    redis_client = get_redis_client()
    try:
        test_key = "campanha:test_phase1_smoke"
        redis_client.hset(
            test_key,
            mapping={"description": "TypeB", "start_day": "624", "end_day": "656"},
        )
        redis_client.expire(test_key, 30)
        assert redis_client.hget(test_key, "description") == "TypeB"
        assert 0 < redis_client.ttl(test_key) <= 30

        deleted = clear_redis_namespace(client=redis_client, pattern="campanha:test_phase1_*")
        assert deleted == 1
        assert redis_client.exists(test_key) == 0
    finally:
        redis_client.close()


def test_initialize_all_schemas_end_to_end() -> None:
    """Verify initialize_all_schemas provisions MongoDB, Cassandra, and Redis in one call."""
    summary = initialize_all_schemas()
    assert summary["redis_ready"] is True
    assert set(CASSANDRA_TABLES).issubset(set(summary["cassandra_tables"]))
    assert "idx_household_key_unique" in summary["mongo_indexes"]
    assert "idx_demographics_class1_class3" in summary["mongo_indexes"]
    assert "idx_behavior_avg_weekly_spend_desc" in summary["mongo_indexes"]
