"""Batched Polars ingestion for Apache Cassandra query-driven tables."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import Any

import polars as pl
from cassandra.cluster import Session
from cassandra.concurrent import execute_concurrent_with_args

from basketlens.config import Settings, get_settings
from basketlens.connections import get_cassandra_cluster_and_session
from basketlens.ingestion.mongo_loader import TRANSACTION_SCHEMA_OVERRIDES, _collect_streaming
from basketlens.schemas.cassandra_schema import ensure_cassandra_schema

INSERT_TX_BY_HH_CQL = """
INSERT INTO transactions_by_household (
    household_key, week_no, day, basket_id, product_id,
    quantity, sales_value, store_id, trans_time,
    retail_disc, coupon_disc, coupon_match_disc
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
""".strip()

INSERT_TX_BY_HH_PROD_CQL = """
INSERT INTO transactions_by_household_product (
    household_key, product_id, day, basket_id, week_no,
    quantity, sales_value, store_id,
    retail_disc, coupon_disc, coupon_match_disc
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
""".strip()

INSERT_SALES_BY_PROD_WEEK_CQL = """
INSERT INTO sales_by_product_week (
    product_id, week_no, total_units, total_sales, total_baskets
) VALUES (?, ?, ?, ?, ?);
""".strip()

INSERT_CAUSAL_BY_STORE_WEEK_CQL = """
INSERT INTO causal_promotions_by_store_week (
    store_id, week_no, product_id, display_type, mailer_page
) VALUES (?, ?, ?, ?, ?);
""".strip()

CAUSAL_SCHEMA_OVERRIDES: dict[str, pl.DataType] = {
    "PRODUCT_ID": pl.Int64,
    "STORE_ID": pl.Int64,
    "WEEK_NO": pl.Int64,
    "display": pl.Utf8,
    "mailer": pl.Utf8,
}


def _execute_chunked_prepared(
    session: Session,
    single_cql: str,
    rows: list[tuple[Any, ...]],
    concurrency: int = 64,
    group_size: int = 25,
) -> int:
    """Execute prepared statements concurrently, grouping full chunks into UNLOGGED batches."""
    if not rows:
        return 0

    total = len(rows)
    full_chunks = (total // group_size) * group_size

    if full_chunks > 0:
        batch_cql = (
            "BEGIN UNLOGGED BATCH "
            + " ".join([single_cql] * group_size)
            + " APPLY BATCH;"
        )
        batch_stmt = session.prepare(batch_cql)
        grouped_params: list[tuple[Any, ...]] = []
        for idx in range(0, full_chunks, group_size):
            flat: list[Any] = []
            for row in rows[idx : idx + group_size]:
                flat.extend(row)
            grouped_params.append(tuple(flat))
        execute_concurrent_with_args(
            session,
            batch_stmt,
            grouped_params,
            concurrency=concurrency,
            results_generator=False,
        )

    remainder = rows[full_chunks:]
    if remainder:
        single_stmt = session.prepare(single_cql)
        execute_concurrent_with_args(
            session,
            single_stmt,
            remainder,
            concurrency=concurrency,
            results_generator=False,
        )

    return total


def _df_to_tx_tuples(
    df: pl.DataFrame,
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    """Convert a Polars DataFrame slice into parameter tuples for both transaction tables."""
    hh_tuples: list[tuple[Any, ...]] = []
    hh_prod_tuples: list[tuple[Any, ...]] = []

    for row in df.iter_rows(named=True):
        hh_key = int(row["household_key"])
        week_no = int(row["WEEK_NO"])
        day = int(row["DAY"])
        basket_id = int(row["BASKET_ID"])
        product_id = int(row["PRODUCT_ID"])
        quantity = int(row["QUANTITY"])
        sales_value = round(float(row["SALES_VALUE"] or 0.0), 2)
        store_id = int(row["STORE_ID"])
        trans_time = int(row["TRANS_TIME"])
        retail_disc = round(float(row["RETAIL_DISC"] or 0.0), 2)
        coupon_disc = round(float(row["COUPON_DISC"] or 0.0), 2)
        coupon_match_disc = round(float(row["COUPON_MATCH_DISC"] or 0.0), 2)

        hh_tuples.append(
            (
                hh_key,
                week_no,
                day,
                basket_id,
                product_id,
                quantity,
                sales_value,
                store_id,
                trans_time,
                retail_disc,
                coupon_disc,
                coupon_match_disc,
            )
        )
        hh_prod_tuples.append(
            (
                hh_key,
                product_id,
                day,
                basket_id,
                week_no,
                quantity,
                sales_value,
                store_id,
                retail_disc,
                coupon_disc,
                coupon_match_disc,
            )
        )

    return hh_tuples, hh_prod_tuples


def ingest_cassandra_transactions(
    cutoff_day: int = 711,
    min_day: int | None = None,
    household_keys: Sequence[int] | None = None,
    batch_size: int | None = None,
    max_batches: int | None = None,
    session: Session | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Ingest `transaction_data.csv` via `pl.read_csv_batched` into both transaction tables."""
    cfg = settings or get_settings()
    effective_batch_size = batch_size or cfg.batch_size
    owns_cluster = session is None
    cluster = None

    try:
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(settings=cfg)
        ensure_cassandra_schema(session, keyspace=cfg.cassandra_keyspace)
        session.set_keyspace(cfg.cassandra_keyspace)

        tx_path = cfg.csv_path("transaction_data.csv")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            reader = pl.read_csv_batched(
                tx_path,
                batch_size=effective_batch_size,
                schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
            )

        hh_filter_set = set(int(h) for h in household_keys) if household_keys is not None else None
        batches_processed = 0
        rows_written = 0

        while True:
            if max_batches is not None and batches_processed >= max_batches:
                break
            batches = reader.next_batches(1)
            if not batches:
                break

            batch_df = batches[0].filter(pl.col("DAY") <= cutoff_day)
            if min_day is not None:
                batch_df = batch_df.filter(
                    (pl.col("DAY") >= min_day)
                    | (pl.col("household_key") == cfg.case_study_household)
                    | (pl.col("PRODUCT_ID") == 72717)
                )
            if hh_filter_set is not None:
                batch_df = batch_df.filter(
                    pl.col("household_key").is_in(list(hh_filter_set))
                    | (pl.col("household_key") == cfg.case_study_household)
                )

            batches_processed += 1
            if batch_df.is_empty():
                continue

            hh_tuples, hh_prod_tuples = _df_to_tx_tuples(batch_df)
            _execute_chunked_prepared(
                session,
                INSERT_TX_BY_HH_CQL,
                hh_tuples,
                concurrency=cfg.cassandra_concurrency,
            )
            _execute_chunked_prepared(
                session,
                INSERT_TX_BY_HH_PROD_CQL,
                hh_prod_tuples,
                concurrency=cfg.cassandra_concurrency,
            )
            rows_written += len(hh_tuples)

        # Ensure Case Study household #208, product 72717, and all 801 demographic households are represented
        if max_batches is not None:
            hh208_df = _collect_streaming(
                pl.scan_csv(tx_path, schema_overrides=TRANSACTION_SCHEMA_OVERRIDES).filter(
                    (pl.col("DAY") <= cutoff_day)
                    & (
                        (pl.col("household_key") == cfg.case_study_household)
                        | (pl.col("PRODUCT_ID").is_in([72717, 1017772, 862349, 1029743]))
                    )
                )
            )
            demo_hh_df = (
                _collect_streaming(
                    pl.scan_csv(tx_path, schema_overrides=TRANSACTION_SCHEMA_OVERRIDES)
                    .filter(pl.col("DAY") <= cutoff_day)
                    .join(
                        pl.scan_csv(cfg.csv_path("hh_demographic.csv")).select("household_key"),
                        on="household_key",
                        how="inner",
                    )
                )
                .sort(["household_key", "DAY", "BASKET_ID"], descending=[False, True, True])
                .group_by("household_key", maintain_order=True)
                .head(8)
            )
            combined_df = pl.concat([hh208_df, demo_hh_df]).unique(
                subset=["household_key", "WEEK_NO", "DAY", "BASKET_ID", "PRODUCT_ID"]
            )
            if not combined_df.is_empty():
                hh_tuples, hh_prod_tuples = _df_to_tx_tuples(combined_df)
                _execute_chunked_prepared(
                    session,
                    INSERT_TX_BY_HH_CQL,
                    hh_tuples,
                    concurrency=cfg.cassandra_concurrency,
                )
                _execute_chunked_prepared(
                    session,
                    INSERT_TX_BY_HH_PROD_CQL,
                    hh_prod_tuples,
                    concurrency=cfg.cassandra_concurrency,
                )
                rows_written += len(hh_tuples)

        return {
            "cutoff_day": cutoff_day,
            "batches_processed": batches_processed,
            "rows_written": rows_written,
        }
    finally:
        if owns_cluster and cluster is not None:
            cluster.shutdown()


def ingest_sales_by_product_week(
    cutoff_day: int = 711,
    min_week: int | None = None,
    product_ids: Sequence[int] | None = None,
    max_rows: int | None = None,
    batch_size: int = 10_000,
    session: Session | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Aggregate `(product_id, week_no)` out-of-core via Polars and load `sales_by_product_week`."""
    cfg = settings or get_settings()
    owns_cluster = session is None
    cluster = None

    try:
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(settings=cfg)
        ensure_cassandra_schema(session, keyspace=cfg.cassandra_keyspace)
        session.set_keyspace(cfg.cassandra_keyspace)

        tx_lf = pl.scan_csv(
            cfg.csv_path("transaction_data.csv"),
            schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
        ).filter(pl.col("DAY") <= cutoff_day)

        if min_week is not None:
            tx_lf = tx_lf.filter(
                (pl.col("WEEK_NO") >= min_week) | (pl.col("PRODUCT_ID") == 72717)
            )
        if product_ids is not None:
            target_prods = list({* (int(p) for p in product_ids), 72717})
            tx_lf = tx_lf.filter(pl.col("PRODUCT_ID").is_in(target_prods))

        agg_df = _collect_streaming(
            tx_lf.group_by(["PRODUCT_ID", "WEEK_NO"]).agg(
                pl.col("QUANTITY").sum().alias("total_units"),
                pl.col("SALES_VALUE").sum().round(2).alias("total_sales"),
                pl.col("BASKET_ID").n_unique().alias("total_baskets"),
            )
        ).sort(["PRODUCT_ID", "WEEK_NO"])

        if max_rows is not None and agg_df.height > max_rows:
            priority_df = agg_df.filter(
                pl.col("PRODUCT_ID").is_in([72717, 1017772, 862349, 1029743])
            )
            rest_df = agg_df.filter(
                ~pl.col("PRODUCT_ID").is_in([72717, 1017772, 862349, 1029743])
            ).head(max(0, max_rows - priority_df.height))
            agg_df = pl.concat([priority_df, rest_df])

        rows_written = 0
        tuples_buffer: list[tuple[Any, ...]] = []
        for row in agg_df.iter_rows(named=True):
            tuples_buffer.append(
                (
                    int(row["PRODUCT_ID"]),
                    int(row["WEEK_NO"]),
                    int(row["total_units"] or 0),
                    round(float(row["total_sales"] or 0.0), 2),
                    int(row["total_baskets"] or 0),
                )
            )
            if len(tuples_buffer) >= batch_size:
                rows_written += _execute_chunked_prepared(
                    session,
                    INSERT_SALES_BY_PROD_WEEK_CQL,
                    tuples_buffer,
                    concurrency=cfg.cassandra_concurrency,
                )
                tuples_buffer.clear()

        if tuples_buffer:
            rows_written += _execute_chunked_prepared(
                session,
                INSERT_SALES_BY_PROD_WEEK_CQL,
                tuples_buffer,
                concurrency=cfg.cassandra_concurrency,
            )

        return {
            "cutoff_day": cutoff_day,
            "rows_written": rows_written,
        }
    finally:
        if owns_cluster and cluster is not None:
            cluster.shutdown()


def resolve_cutoff_week(cutoff_day: int = 711, settings: Settings | None = None) -> int:
    """Resolve the maximum `WEEK_NO` corresponding to `DAY <= cutoff_day`."""
    cfg = settings or get_settings()
    max_week_df = _collect_streaming(
        pl.scan_csv(
            cfg.csv_path("transaction_data.csv"),
            schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
        )
        .filter(pl.col("DAY") <= cutoff_day)
        .select(pl.col("WEEK_NO").max().alias("max_week"))
    )
    val = max_week_df["max_week"][0]
    return int(val) if val is not None else max(1, (cutoff_day + 6) // 7)


def ingest_causal_promotions(
    cutoff_week: int = 102,
    min_week: int | None = None,
    store_ids: Sequence[int] | None = None,
    product_ids: Sequence[int] | None = None,
    batch_size: int | None = None,
    max_batches: int | None = None,
    session: Session | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Ingest `causal_data.csv` via `pl.read_csv_batched` into `causal_promotions_by_store_week`."""
    cfg = settings or get_settings()
    effective_batch_size = batch_size or cfg.batch_size
    owns_cluster = session is None
    cluster = None

    try:
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(settings=cfg)
        ensure_cassandra_schema(session, keyspace=cfg.cassandra_keyspace)
        session.set_keyspace(cfg.cassandra_keyspace)

        causal_path = cfg.csv_path("causal_data.csv")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            reader = pl.read_csv_batched(
                causal_path,
                batch_size=effective_batch_size,
                schema_overrides=CAUSAL_SCHEMA_OVERRIDES,
            )

        store_set = [int(s) for s in store_ids] if store_ids is not None else None
        prod_set = [int(p) for p in product_ids] if product_ids is not None else None
        batches_processed = 0
        rows_written = 0

        while True:
            if max_batches is not None and batches_processed >= max_batches:
                break
            batches = reader.next_batches(1)
            if not batches:
                break

            batch_df = batches[0].filter(pl.col("WEEK_NO") <= cutoff_week)
            if min_week is not None:
                batch_df = batch_df.filter(
                    (pl.col("WEEK_NO") >= min_week) | (pl.col("PRODUCT_ID") == 72717)
                )
            if store_set is not None:
                batch_df = batch_df.filter(
                    pl.col("STORE_ID").is_in(store_set) | (pl.col("PRODUCT_ID") == 72717)
                )
            if prod_set is not None:
                batch_df = batch_df.filter(
                    pl.col("PRODUCT_ID").is_in(prod_set) | (pl.col("PRODUCT_ID") == 72717)
                )

            batches_processed += 1
            if batch_df.is_empty():
                continue

            causal_tuples = [
                (
                    int(row["STORE_ID"]),
                    int(row["WEEK_NO"]),
                    int(row["PRODUCT_ID"]),
                    str(row["display"]),
                    str(row["mailer"]),
                )
                for row in batch_df.iter_rows(named=True)
            ]
            rows_written += _execute_chunked_prepared(
                session,
                INSERT_CAUSAL_BY_STORE_WEEK_CQL,
                causal_tuples,
                concurrency=cfg.cassandra_concurrency,
            )

        # Ensure PDF case study product 72717 and key products are always completely present up to cutoff_week
        if max_batches is not None:
            p72717_df = _collect_streaming(
                pl.scan_csv(causal_path, schema_overrides=CAUSAL_SCHEMA_OVERRIDES).filter(
                    (pl.col("WEEK_NO") <= cutoff_week)
                    & (pl.col("PRODUCT_ID").is_in([72717, 1017772, 862349]))
                )
            )
            if not p72717_df.is_empty():
                p72717_tuples = [
                    (
                        int(row["STORE_ID"]),
                        int(row["WEEK_NO"]),
                        int(row["PRODUCT_ID"]),
                        str(row["display"]),
                        str(row["mailer"]),
                    )
                    for row in p72717_df.iter_rows(named=True)
                ]
                _execute_chunked_prepared(
                    session,
                    INSERT_CAUSAL_BY_STORE_WEEK_CQL,
                    p72717_tuples,
                    concurrency=cfg.cassandra_concurrency,
                )
                rows_written += len(p72717_tuples)

        return {
            "cutoff_week": cutoff_week,
            "batches_processed": batches_processed,
            "rows_written": rows_written,
        }
    finally:
        if owns_cluster and cluster is not None:
            cluster.shutdown()


def ingest_cassandra_data(
    cutoff_day: int = 711,
    include_causal: bool = True,
    min_day: int | None = None,
    household_keys: Sequence[int] | None = None,
    tx_max_batches: int | None = None,
    sales_max_rows: int | None = None,
    causal_max_batches: int | None = None,
    batch_size: int | None = None,
    session: Session | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Orchestrate batched ingestion into all 4 Cassandra query-driven tables.

    Database Interaction:
        [transaction_data.csv + causal_data.csv] ──► Polars read_csv_batched / scan_csv
          └──► [Apache Cassandra keyspace basketlens] (Prepared Statements + UNLOGGED BATCH)
                 ├── 1. transactions_by_household         ((household_key), week_no DESC, day DESC)
                 ├── 2. transactions_by_household_product ((household_key, product_id), day DESC)
                 ├── 3. sales_by_product_week             ((product_id), week_no DESC)
                 └── 4. causal_promotions_by_store_week   ((store_id, week_no), product_id ASC)
    """
    cfg = settings or get_settings()
    owns_cluster = session is None
    cluster = None

    try:
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(settings=cfg)
        ensure_cassandra_schema(session, keyspace=cfg.cassandra_keyspace)
        session.set_keyspace(cfg.cassandra_keyspace)

        cutoff_week = resolve_cutoff_week(cutoff_day=cutoff_day, settings=cfg)

        tx_stats = ingest_cassandra_transactions(
            cutoff_day=cutoff_day,
            min_day=min_day,
            household_keys=household_keys,
            batch_size=batch_size,
            max_batches=tx_max_batches,
            session=session,
            settings=cfg,
        )
        sales_stats = ingest_sales_by_product_week(
            cutoff_day=cutoff_day,
            max_rows=sales_max_rows,
            session=session,
            settings=cfg,
        )
        causal_stats: dict[str, int] = {
            "cutoff_week": cutoff_week,
            "batches_processed": 0,
            "rows_written": 0,
        }
        if include_causal:
            causal_stats = ingest_causal_promotions(
                cutoff_week=cutoff_week,
                batch_size=batch_size,
                max_batches=causal_max_batches,
                session=session,
                settings=cfg,
            )

        return {
            "cutoff_day": cutoff_day,
            "cutoff_week": cutoff_week,
            "transactions": tx_stats,
            "sales_by_product_week": sales_stats,
            "causal_promotions": causal_stats,
        }
    finally:
        if owns_cluster and cluster is not None:
            cluster.shutdown()


__all__ = [
    "CAUSAL_SCHEMA_OVERRIDES",
    "INSERT_CAUSAL_BY_STORE_WEEK_CQL",
    "INSERT_SALES_BY_PROD_WEEK_CQL",
    "INSERT_TX_BY_HH_CQL",
    "INSERT_TX_BY_HH_PROD_CQL",
    "ingest_cassandra_data",
    "ingest_cassandra_transactions",
    "ingest_causal_promotions",
    "ingest_sales_by_product_week",
    "resolve_cutoff_week",
]


