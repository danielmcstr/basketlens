"""Polars out-of-core and batched ingestion pipelines for MongoDB, Cassandra, and Redis."""

from basketlens.ingestion.cassandra_loader import (
    ingest_cassandra_data,
    ingest_cassandra_transactions,
    ingest_causal_promotions,
    ingest_sales_by_product_week,
    resolve_cutoff_week,
)
from basketlens.ingestion.mongo_loader import (
    build_household_documents,
    compute_behavior_summaries,
    extract_recent_baskets,
    ingest_mongo_households,
    load_campaigns_received_map,
    load_demographics_map,
)
from basketlens.ingestion.pipeline import run_full_ingestion
from basketlens.ingestion.redis_loader import (
    ingest_redis_state,
    load_active_campaigns_to_redis,
    load_active_coupons_and_eligibility_to_redis,
    load_weekly_rankings_and_displays_to_redis,
)

__all__ = [
    "build_household_documents",
    "compute_behavior_summaries",
    "extract_recent_baskets",
    "ingest_cassandra_data",
    "ingest_cassandra_transactions",
    "ingest_causal_promotions",
    "ingest_mongo_households",
    "ingest_redis_state",
    "ingest_sales_by_product_week",
    "load_active_campaigns_to_redis",
    "load_active_coupons_and_eligibility_to_redis",
    "load_campaigns_received_map",
    "load_demographics_map",
    "load_weekly_rankings_and_displays_to_redis",
    "resolve_cutoff_week",
    "run_full_ingestion",
]
