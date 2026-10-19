"""End-to-end polyglot ingestion orchestrator for MongoDB, Cassandra, and Redis."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from basketlens.config import Settings, get_settings
from basketlens.ingestion.cassandra_loader import ingest_cassandra_data
from basketlens.ingestion.mongo_loader import ingest_mongo_households
from basketlens.ingestion.redis_loader import ingest_redis_state
from basketlens.schemas import initialize_all_schemas


def run_full_ingestion(
    cutoff_day: int = 711,
    reference_day: int = 650,
    seconds_per_day: int = 5,
    include_causal: bool = True,
    min_day: int | None = None,
    household_keys: Sequence[int] | None = None,
    tx_max_batches: int | None = None,
    sales_max_rows: int | None = None,
    causal_max_batches: int | None = None,
    include_weekly_showcases: bool = True,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Provision schemas and execute coordinated ingestion across MongoDB, Cassandra, and Redis.

    Database Interaction:
        [8 CSVs dunnhumby] ──► Polars scan_csv(streaming=True) / read_csv_batched(50_000)
                                 │
                                 ├──► 1. ingest_mongo_households() ──► [MongoDB db.households]
                                 │       • Upsert em lote (bulk_write) dos 2.500 domicílios
                                 │       • 801 c/ demographics + 1.699 sem demographics
                                 │       • behavior_summary (RFM) + recent_baskets ($slice: -5)
                                 │
                                 ├──► 2. ingest_cassandra_data()   ──► [Cassandra keyspace basketlens]
                                 │       • Prepared Statements + UNLOGGED BATCH por partição
                                 │       • Popula as 4 tabelas CQL orientadas à consulta
                                 │
                                 └──► 3. ingest_redis_state()      ──► [Redis Pipeline em Memória]
                                         • Popula campanhas/cupons ativos em reference_day c/ TTL
    """
    cfg = settings or get_settings()
    t0 = time.perf_counter()

    schema_summary = initialize_all_schemas()
    mongo_summary = ingest_mongo_households(
        cutoff_day=cutoff_day,
        settings=cfg,
    )
    cassandra_summary = ingest_cassandra_data(
        cutoff_day=cutoff_day,
        include_causal=include_causal,
        min_day=min_day,
        household_keys=household_keys,
        tx_max_batches=tx_max_batches,
        sales_max_rows=sales_max_rows,
        causal_max_batches=causal_max_batches,
        settings=cfg,
    )
    redis_summary = ingest_redis_state(
        reference_day=reference_day,
        seconds_per_day=seconds_per_day,
        include_weekly_showcases=include_weekly_showcases,
        settings=cfg,
    )

    elapsed_seconds = round(time.perf_counter() - t0, 3)
    return {
        "cutoff_day": cutoff_day,
        "reference_day": reference_day,
        "seconds_per_day": seconds_per_day,
        "elapsed_seconds": elapsed_seconds,
        "schemas": schema_summary,
        "mongodb": mongo_summary,
        "cassandra": cassandra_summary,
        "redis": redis_summary,
    }


__all__ = ["run_full_ingestion"]
