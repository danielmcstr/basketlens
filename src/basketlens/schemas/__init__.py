"""Declarative schema and index provisioning for MongoDB, Cassandra, and Redis."""

from __future__ import annotations

from typing import Any

from basketlens.connections import get_redis_client
from basketlens.schemas.cassandra_schema import (
    CASSANDRA_TABLES,
    ensure_cassandra_schema,
    get_keyspace_ddl,
    get_table_ddls,
    list_cassandra_tables,
)
from basketlens.schemas.mongo_schema import (
    HOUSEHOLD_INDEX_MODELS,
    HOUSEHOLDS_COLLECTION,
    ensure_mongo_indexes,
    explain_query,
)
from basketlens.schemas.redis_schema import (
    REDIS_NAMESPACE_PATTERNS,
    campaign_coupons_key,
    campaign_key,
    clear_all_basketlens_keys,
    clear_redis_namespace,
    compute_campaign_ttl_seconds,
    coupon_key,
    household_campaigns_key,
    household_coupons_key,
    profile_key,
    ranking_week_key,
    store_week_displays_key,
)


def initialize_all_schemas() -> dict[str, Any]:
    """Provision MongoDB indexes, Cassandra keyspace/tables, and verify Redis readiness."""
    mongo_indexes = ensure_mongo_indexes()
    cassandra_tables = ensure_cassandra_schema()
    redis_client = get_redis_client()
    try:
        redis_ready = bool(redis_client.ping())
    finally:
        redis_client.close()

    return {
        "mongo_indexes": sorted(mongo_indexes.keys()),
        "cassandra_tables": cassandra_tables,
        "redis_ready": redis_ready,
    }


__all__ = [
    "CASSANDRA_TABLES",
    "HOUSEHOLDS_COLLECTION",
    "HOUSEHOLD_INDEX_MODELS",
    "REDIS_NAMESPACE_PATTERNS",
    "campaign_coupons_key",
    "campaign_key",
    "clear_all_basketlens_keys",
    "clear_redis_namespace",
    "compute_campaign_ttl_seconds",
    "coupon_key",
    "ensure_cassandra_schema",
    "ensure_mongo_indexes",
    "explain_query",
    "get_keyspace_ddl",
    "get_table_ddls",
    "household_campaigns_key",
    "household_coupons_key",
    "initialize_all_schemas",
    "list_cassandra_tables",
    "profile_key",
    "ranking_week_key",
    "store_week_displays_key",
]
