"""Operational Day-by-Day Event Replay engine (Mode B) for BasketLens."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import polars as pl
import redis
from cassandra.cluster import Session
from cassandra.concurrent import execute_concurrent_with_args
from pymongo import UpdateOne
from pymongo.database import Database

from basketlens.config import Settings, get_settings
from basketlens.connections import (
    get_cassandra_cluster_and_session,
    get_mongo_client,
    get_mongo_db,
    get_redis_client,
)
from basketlens.ingestion.cassandra_loader import (
    INSERT_SALES_BY_PROD_WEEK_CQL,
    INSERT_TX_BY_HH_CQL,
    INSERT_TX_BY_HH_PROD_CQL,
    _df_to_tx_tuples,
    _execute_chunked_prepared,
    ingest_cassandra_data,
    resolve_cutoff_week,
)
from basketlens.ingestion.mongo_loader import (
    TRANSACTION_SCHEMA_OVERRIDES,
    _collect_streaming,
    ingest_mongo_households,
)
from basketlens.ingestion.redis_loader import (
    ingest_redis_state,
    load_active_campaigns_to_redis,
    load_active_coupons_and_eligibility_to_redis,
)
from basketlens.schemas.cassandra_schema import ensure_cassandra_schema
from basketlens.schemas.mongo_schema import HOUSEHOLDS_COLLECTION, ensure_mongo_indexes
from basketlens.schemas.redis_schema import (
    campaign_coupons_key,
    campaign_key,
    clear_redis_namespace,
    coupon_key,
    household_campaigns_key,
    household_coupons_key,
    profile_key,
)

COUPON_REDEMPT_SCHEMA_OVERRIDES: dict[str, pl.DataType] = {
    "household_key": pl.Int64,
    "DAY": pl.Int64,
    "COUPON_UPC": pl.Utf8,
    "CAMPAIGN": pl.Int64,
}


def _prune_cassandra_transactions_after_day(
    session: Session,
    cutoff_day: int,
    household_keys: Sequence[int],
    concurrency: int = 32,
) -> int:
    """Delete transactions with `day > cutoff_day` for specified households in Cassandra."""
    select_hh_stmt = session.prepare(
        "SELECT week_no, day, basket_id, product_id "
        "FROM transactions_by_household WHERE household_key = ?"
    )
    delete_hh_stmt = session.prepare(
        "DELETE FROM transactions_by_household "
        "WHERE household_key = ? AND week_no = ? AND day = ? AND basket_id = ? AND product_id = ?"
    )
    delete_hh_prod_stmt = session.prepare(
        "DELETE FROM transactions_by_household_product "
        "WHERE household_key = ? AND product_id = ? AND day = ? AND basket_id = ?"
    )

    hh_delete_args: list[tuple[int, int, int, int, int]] = []
    hh_prod_delete_args: list[tuple[int, int, int, int]] = []

    for hh_key in household_keys:
        rows = session.execute(select_hh_stmt, (int(hh_key),))
        for row in rows:
            if int(row.day) > cutoff_day:
                hh_delete_args.append(
                    (
                        int(hh_key),
                        int(row.week_no),
                        int(row.day),
                        int(row.basket_id),
                        int(row.product_id),
                    )
                )
                hh_prod_delete_args.append(
                    (
                        int(hh_key),
                        int(row.product_id),
                        int(row.day),
                        int(row.basket_id),
                    )
                )

    if hh_delete_args:
        execute_concurrent_with_args(
            session,
            delete_hh_stmt,
            hh_delete_args,
            concurrency=concurrency,
            results_generator=False,
        )
    if hh_prod_delete_args:
        execute_concurrent_with_args(
            session,
            delete_hh_prod_stmt,
            hh_prod_delete_args,
            concurrency=concurrency,
            results_generator=False,
        )

    return len(hh_delete_args)


def prepare_replay_baseline(
    cutoff_day: int = 649,
    seconds_per_day: int = 5,
    watch_households: Sequence[int] = (208,),
    reingest_cassandra_base: bool = False,
    db: Database[dict[str, Any]] | None = None,
    session: Session | None = None,
    redis_client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Prepare the baseline state across MongoDB, Cassandra, and Redis up to `cutoff_day`."""
    cfg = settings or get_settings()
    t0 = time.perf_counter()

    owns_mongo = db is None
    owns_cassandra = session is None
    owns_redis = redis_client is None
    mongo_client = None
    cluster = None

    try:
        if db is None:
            mongo_client = get_mongo_client(settings=cfg)
            db = get_mongo_db(settings=cfg, client=mongo_client)
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(settings=cfg)
        if redis_client is None:
            redis_client = get_redis_client(settings=cfg)

        ensure_mongo_indexes(db)
        ensure_cassandra_schema(session, keyspace=cfg.cassandra_keyspace)
        session.set_keyspace(cfg.cassandra_keyspace)

        # 1. MongoDB: rebuild all 2,500 household documents strictly up to `cutoff_day`
        mongo_stats = ingest_mongo_households(
            cutoff_day=cutoff_day,
            db=db,
            settings=cfg,
        )

        # 2. Cassandra: ensure baseline rows up to `cutoff_day` exist and prune `day > cutoff_day`
        # for watched households (e.g., John Smith #208) so replay starts from a clean slate
        row_check = session.execute(
            "SELECT day FROM transactions_by_household WHERE household_key = %s LIMIT 1",
            (cfg.case_study_household,),
        ).one()

        if reingest_cassandra_base or row_check is None:
            ingest_cassandra_data(
                cutoff_day=cutoff_day,
                include_causal=True,
                tx_max_batches=1,
                sales_max_rows=20000,
                causal_max_batches=1,
                session=session,
                settings=cfg,
            )

        target_households = sorted({int(cfg.case_study_household), *(int(h) for h in watch_households)})
        pruned_rows = _prune_cassandra_transactions_after_day(
            session=session,
            cutoff_day=cutoff_day,
            household_keys=target_households,
            concurrency=cfg.cassandra_concurrency,
        )

        # Ensure watched households have all transactions up to `cutoff_day`
        watch_tx_df = _collect_streaming(
            pl.scan_csv(
                cfg.csv_path("transaction_data.csv"),
                schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
            ).filter(
                (pl.col("DAY") <= cutoff_day)
                & (pl.col("household_key").is_in(target_households))
            )
        )
        if not watch_tx_df.is_empty():
            hh_tuples, hh_prod_tuples = _df_to_tx_tuples(watch_tx_df)
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

        # 3. Redis: clear profile cache & redemptions, load active state at `cutoff_day`
        clear_redis_namespace(client=redis_client, pattern="profile:*")
        clear_redis_namespace(client=redis_client, pattern="redemption:*")
        redis_stats = ingest_redis_state(
            reference_day=cutoff_day,
            seconds_per_day=seconds_per_day,
            include_weekly_showcases=True,
            client=redis_client,
            settings=cfg,
        )

        doc_208 = db[HOUSEHOLDS_COLLECTION].find_one(
            {"household_key": cfg.case_study_household},
            {"_id": 0, "household_key": 1, "behavior_summary": 1, "recent_baskets": 1},
        )

        return {
            "cutoff_day": cutoff_day,
            "seconds_per_day": seconds_per_day,
            "elapsed_seconds": round(time.perf_counter() - t0, 3),
            "mongodb": mongo_stats,
            "cassandra": {
                "watched_households": target_households,
                "pruned_future_rows": pruned_rows,
                "baseline_rows_verified": int(watch_tx_df.height),
            },
            "redis": {
                "active_campaign_count": redis_stats["active_campaign_count"],
                "active_campaigns": redis_stats["active_campaigns"],
                "active_coupons": redis_stats["active_coupons"],
                "eligible_households": redis_stats["eligible_households"],
            },
            "household_208_baseline": {
                "last_day": doc_208["behavior_summary"]["last_day"] if doc_208 else None,
                "total_baskets": doc_208["behavior_summary"]["total_baskets"] if doc_208 else None,
                "total_spend": doc_208["behavior_summary"]["total_spend"] if doc_208 else None,
                "recent_basket_ids": [
                    b["basket_id"] for b in (doc_208.get("recent_baskets", []) if doc_208 else [])
                ],
            },
        }
    finally:
        if owns_mongo and mongo_client is not None:
            mongo_client.close()
        if owns_cassandra and cluster is not None:
            cluster.shutdown()
        if owns_redis and redis_client is not None:
            redis_client.close()


def _sync_redis_campaigns_and_redemptions_for_day(
    day: int,
    seconds_per_day: int,
    redempt_df: pl.DataFrame,
    redis_client: redis.Redis,
    cfg: Settings,
) -> dict[str, Any]:
    """Rotate active/expired campaigns and process coupon redemptions for `day` in Redis."""
    all_campaigns_df = _collect_streaming(
        pl.scan_csv(cfg.csv_path("campaign_desc.csv")).sort("CAMPAIGN")
    )

    expired_campaign_ids: list[int] = []
    started_campaign_ids: list[int] = []
    active_campaigns: dict[int, dict[str, Any]] = {}

    for row in all_campaigns_df.iter_rows(named=True):
        cid = int(row["CAMPAIGN"])
        desc = str(row["DESCRIPTION"])
        start_day = int(row["START_DAY"])
        end_day = int(row["END_DAY"])

        if end_day < day:
            if redis_client.exists(campaign_key(cid)):
                expired_campaign_ids.append(cid)
        elif start_day <= day <= end_day:
            if start_day == day:
                started_campaign_ids.append(cid)
            # On the final day (end_day == day), assign 1 day slice (`seconds_per_day`)
            remaining_days = max(1, (end_day - day) + 1) if end_day == day else (end_day - day)
            ttl_sec = max(1, int(remaining_days) * int(seconds_per_day))
            active_campaigns[cid] = {
                "campaign": cid,
                "description": desc,
                "start_day": start_day,
                "end_day": end_day,
                "ttl_seconds": ttl_sec,
            }

    # Explicitly remove campaigns that ended before `day`
    if expired_campaign_ids:
        pipe = redis_client.pipeline(transaction=False)
        for cid in expired_campaign_ids:
            c_pool_key = campaign_coupons_key(cid)
            upcs = redis_client.smembers(c_pool_key)
            for upc in upcs:
                pipe.delete(coupon_key(upc))
            pipe.delete(c_pool_key)
            pipe.delete(campaign_key(cid))
        pipe.execute()

    # Load / refresh active campaigns and their coupons/eligibility
    load_active_campaigns_to_redis(
        reference_day=day,
        seconds_per_day=seconds_per_day,
        clear_existing=True,
        client=redis_client,
        settings=cfg,
    )
    load_active_coupons_and_eligibility_to_redis(
        active_campaigns=active_campaigns,
        clear_existing=True,
        client=redis_client,
        settings=cfg,
    )

    # Apply our exact TTLs (including final-day TTLs) on active campaign hashes
    if active_campaigns:
        pipe = redis_client.pipeline(transaction=False)
        for cid, meta in active_campaigns.items():
            pipe.expire(campaign_key(cid), int(meta["ttl_seconds"]))
            pipe.expire(campaign_coupons_key(cid), int(meta["ttl_seconds"]))
        pipe.execute()

    # Process coupon redemptions on `day`
    redemptions_processed: list[dict[str, Any]] = []
    redeemed_households: set[int] = set()
    if not redempt_df.is_empty():
        pipe = redis_client.pipeline(transaction=False)
        for row in redempt_df.iter_rows(named=True):
            hh_key = int(row["household_key"])
            upc = str(row["COUPON_UPC"])
            cid = int(row["CAMPAIGN"])
            redeemed_households.add(hh_key)

            # Remove redeemed coupon from the household's unredeemed set and log redemption
            pipe.srem(household_coupons_key(hh_key), upc)
            pipe.sadd(f"household:{hh_key}:redeemed_coupons", f"{day}:{cid}:{upc}")
            pipe.hincrby(coupon_key(upc), "redemptions_count", 1)
            redemptions_processed.append(
                {
                    "household_key": hh_key,
                    "day": day,
                    "coupon_upc": upc,
                    "campaign": cid,
                }
            )
        pipe.execute()

    return {
        "active_campaigns": active_campaigns,
        "started_campaigns": started_campaign_ids,
        "expired_campaigns": expired_campaign_ids,
        "redemptions_count": len(redemptions_processed),
        "redemptions": redemptions_processed,
        "redeemed_households": sorted(redeemed_households),
    }


def _update_cassandra_for_day(
    day: int,
    tx_df: pl.DataFrame,
    session: Session,
    cfg: Settings,
) -> dict[str, int]:
    """Insert `DAY == day` rows into Cassandra transaction tables and update weekly product sales."""
    if tx_df.is_empty():
        return {
            "transactions_inserted": 0,
            "product_weeks_updated": 0,
        }

    hh_tuples, hh_prod_tuples = _df_to_tx_tuples(tx_df)
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

    # Update `sales_by_product_week` for the week(s) touched on `day` (focusing on tracked products + top items)
    weeks_on_day = tx_df["WEEK_NO"].unique().to_list()
    touched_products = tx_df["PRODUCT_ID"].unique().to_list()
    priority_products = [p for p in touched_products if int(p) in {72717, 1017772, 862349, 1029743}]
    sample_products = list({*(int(p) for p in touched_products[:50]), *priority_products})

    sales_Updated = 0
    if sample_products and weeks_on_day:
        week_agg_df = _collect_streaming(
            pl.scan_csv(
                cfg.csv_path("transaction_data.csv"),
                schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
            )
            .filter(
                (pl.col("DAY") <= day)
                & (pl.col("WEEK_NO").is_in(weeks_on_day))
                & (pl.col("PRODUCT_ID").is_in(sample_products))
            )
            .group_by(["PRODUCT_ID", "WEEK_NO"])
            .agg(
                pl.col("QUANTITY").sum().alias("total_units"),
                pl.col("SALES_VALUE").sum().round(2).alias("total_sales"),
                pl.col("BASKET_ID").n_unique().alias("total_baskets"),
            )
        )
        sales_tuples = [
            (
                int(r["PRODUCT_ID"]),
                int(r["WEEK_NO"]),
                int(r["total_units"] or 0),
                round(float(r["total_sales"] or 0.0), 2),
                int(r["total_baskets"] or 0),
            )
            for r in week_agg_df.iter_rows(named=True)
        ]
        sales_Updated = _execute_chunked_prepared(
            session,
            INSERT_SALES_BY_PROD_WEEK_CQL,
            sales_tuples,
            concurrency=cfg.cassandra_concurrency,
        )

    return {
        "transactions_inserted": len(hh_tuples),
        "product_weeks_updated": sales_Updated,
    }


def _update_mongodb_for_day(
    day: int,
    tx_df: pl.DataFrame,
    db: Database[dict[str, Any]],
    cfg: Settings,
) -> dict[str, Any]:
    """Apply `$inc` on `behavior_summary` and `$push` with `$slice: -5` on `recent_baskets`."""
    if tx_df.is_empty():
        return {
            "households_updated": 0,
            "baskets_pushed": 0,
            "updated_household_keys": [],
        }

    prod_df = _collect_streaming(
        pl.scan_csv(cfg.csv_path("product.csv"))
        .select("PRODUCT_ID", "DEPARTMENT", "COMMODITY_DESC")
        .filter(pl.col("PRODUCT_ID").is_in(tx_df["PRODUCT_ID"].unique().to_list()))
    )
    enriched_df = tx_df.join(prod_df, on="PRODUCT_ID", how="left").sort(
        ["household_key", "BASKET_ID", "PRODUCT_ID"]
    )

    items_by_basket: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in enriched_df.iter_rows(named=True):
        key = (int(row["household_key"]), int(row["BASKET_ID"]))
        items_by_basket.setdefault(key, []).append(
            {
                "product_id": int(row["PRODUCT_ID"]),
                "commodity_desc": str(row["COMMODITY_DESC"] or "UNKNOWN"),
                "department": str(row["DEPARTMENT"] or "UNKNOWN"),
                "quantity": int(row["QUANTITY"]),
                "sales_value": round(float(row["SALES_VALUE"] or 0.0), 2),
            }
        )

    baskets_df = (
        enriched_df.group_by(["household_key", "BASKET_ID"])
        .agg(
            pl.col("DAY").max().alias("day"),
            pl.col("WEEK_NO").max().alias("week_no"),
            pl.col("STORE_ID").first().alias("store_id"),
            pl.col("SALES_VALUE").sum().alias("total"),
        )
        .sort(["household_key", "day", "BASKET_ID"])
    )

    baskets_by_hh: dict[int, list[dict[str, Any]]] = {}
    for row in baskets_df.iter_rows(named=True):
        hh_key = int(row["household_key"])
        basket_id = int(row["BASKET_ID"])
        baskets_by_hh.setdefault(hh_key, []).append(
            {
                "basket_id": basket_id,
                "day": int(row["day"]),
                "week_no": int(row["week_no"]),
                "store_id": int(row["store_id"]),
                "total": round(float(row["total"] or 0.0), 2),
                "items": items_by_basket.get((hh_key, basket_id), []),
            }
        )

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    collection = db[HOUSEHOLDS_COLLECTION]
    operations: list[UpdateOne] = []
    total_baskets_pushed = 0

    for hh_key, new_baskets in baskets_by_hh.items():
        day_spend = round(sum(float(b["total"]) for b in new_baskets), 2)
        day_baskets_count = len(new_baskets)
        total_baskets_pushed += day_baskets_count

        operations.append(
            UpdateOne(
                {"household_key": hh_key},
                {
                    "$inc": {
                        "behavior_summary.total_spend": day_spend,
                        "behavior_summary.total_baskets": day_baskets_count,
                    },
                    "$max": {
                        "behavior_summary.last_day": int(day),
                    },
                    "$set": {
                        "behavior_summary.updated_at": now_iso,
                    },
                    "$push": {
                        "recent_baskets": {
                            "$each": new_baskets,
                            "$sort": {"day": 1, "basket_id": 1},
                            "$slice": -cfg.recent_baskets_limit,
                        }
                    },
                },
            )
        )

    if operations:
        collection.bulk_write(operations, ordered=False)

    # Recompute derived averages (`avg_basket_value` and `avg_weekly_spend`) and round `total_spend`
    affected_keys = sorted(baskets_by_hh.keys())
    derived_ops: list[UpdateOne] = []
    for doc in collection.find(
        {"household_key": {"$in": affected_keys}},
        {"_id": 0, "household_key": 1, "behavior_summary": 1},
    ):
        hh_key = int(doc["household_key"])
        summary = doc.get("behavior_summary", {})
        total_spend = round(float(summary.get("total_spend", 0.0)), 2)
        total_baskets = max(1, int(summary.get("total_baskets", 1)))
        active_weeks = max(1, int(summary.get("active_weeks", 1)))
        derived_ops.append(
            UpdateOne(
                {"household_key": hh_key},
                {
                    "$set": {
                        "behavior_summary.total_spend": total_spend,
                        "behavior_summary.avg_basket_value": round(total_spend / total_baskets, 2),
                        "behavior_summary.avg_weekly_spend": round(total_spend / active_weeks, 2),
                    }
                },
            )
        )
    if derived_ops:
        collection.bulk_write(derived_ops, ordered=False)

    return {
        "households_updated": len(affected_keys),
        "baskets_pushed": total_baskets_pushed,
        "updated_household_keys": affected_keys,
    }


def replay_day(
    day: int,
    seconds_per_day: int = 5,
    watch_household: int = 208,
    db: Database[dict[str, Any]] | None = None,
    session: Session | None = None,
    redis_client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Simulate a single operational day (`DAY == day`) across Redis, Cassandra, and MongoDB."""
    cfg = settings or get_settings()
    t0 = time.perf_counter()

    owns_mongo = db is None
    owns_cassandra = session is None
    owns_redis = redis_client is None
    mongo_client = None
    cluster = None

    try:
        if db is None:
            mongo_client = get_mongo_client(settings=cfg)
            db = get_mongo_db(settings=cfg, client=mongo_client)
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(
                settings=cfg,
                keyspace=cfg.cassandra_keyspace,
            )
        if redis_client is None:
            redis_client = get_redis_client(settings=cfg)

        # Out-of-core Polars scan strictly for `DAY == day`
        tx_df = _collect_streaming(
            pl.scan_csv(
                cfg.csv_path("transaction_data.csv"),
                schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
            ).filter(pl.col("DAY") == day)
        )
        redempt_df = _collect_streaming(
            pl.scan_csv(
                cfg.csv_path("coupon_redempt.csv"),
                schema_overrides=COUPON_REDEMPT_SCHEMA_OVERRIDES,
            ).filter(pl.col("DAY") == day)
        )

        # (a) Redis campaign lifecycle, TTL rotation, and coupon redemptions
        redis_camp_stats = _sync_redis_campaigns_and_redemptions_for_day(
            day=day,
            seconds_per_day=seconds_per_day,
            redempt_df=redempt_df,
            redis_client=redis_client,
            cfg=cfg,
        )

        # (b) Cassandra transactional append
        cassandra_stats = _update_cassandra_for_day(
            day=day,
            tx_df=tx_df,
            session=session,
            cfg=cfg,
        )

        # (c) MongoDB incremental document update ($inc + $push with $slice: -5)
        mongo_stats = _update_mongodb_for_day(
            day=day,
            tx_df=tx_df,
            db=db,
            cfg=cfg,
        )

        # (d) Redis Cache-Aside invalidation (`DEL profile:{id}`) for all touched households
        touched_households = sorted(
            {
                *mongo_stats["updated_household_keys"],
                *redis_camp_stats["redeemed_households"],
            }
        )
        watch_cache_key = profile_key(watch_household)
        watch_cached_before = bool(redis_client.exists(watch_cache_key))
        invalidated_profiles = 0
        if touched_households:
            profile_keys = [profile_key(h) for h in touched_households]
            invalidated_profiles = int(redis_client.delete(*profile_keys))

        watch_invalidated = watch_household in touched_households

        # Build detailed telemetry for the watched case-study household (#208)
        watch_tx_df = tx_df.filter(pl.col("household_key") == watch_household)
        watch_redempt_df = redempt_df.filter(pl.col("household_key") == watch_household)
        watch_doc = db[HOUSEHOLDS_COLLECTION].find_one(
            {"household_key": watch_household},
            {"_id": 0, "household_key": 1, "behavior_summary": 1, "recent_baskets": 1},
        )
        ttl_camp_22 = int(redis_client.ttl(campaign_key(22)))

        return {
            "day": day,
            "week_no": int(tx_df["WEEK_NO"].max()) if not tx_df.is_empty() else resolve_cutoff_week(day, cfg),
            "seconds_per_day": seconds_per_day,
            "elapsed_seconds": round(time.perf_counter() - t0, 3),
            "events": {
                "transaction_rows": int(tx_df.height),
                "distinct_households": len(mongo_stats["updated_household_keys"]),
                "distinct_baskets": int(mongo_stats["baskets_pushed"]),
                "coupon_redemptions": int(redempt_df.height),
            },
            "redis": {
                "active_campaign_ids": sorted(redis_camp_stats["active_campaigns"].keys()),
                "started_campaigns": redis_camp_stats["started_campaigns"],
                "expired_campaigns": redis_camp_stats["expired_campaigns"],
                "campaign_22_ttl": ttl_camp_22,
                "redemptions": redis_camp_stats["redemptions"],
                "profiles_invalidated_del_calls": len(touched_households),
                "profiles_evicted_from_cache": invalidated_profiles,
            },
            "cassandra": cassandra_stats,
            "mongodb": {
                "households_updated": mongo_stats["households_updated"],
                "baskets_pushed": mongo_stats["baskets_pushed"],
            },
            "watched_household": {
                "household_key": watch_household,
                "purchased_today": not watch_tx_df.is_empty(),
                "items_bought_today": int(watch_tx_df.height),
                "spend_today": round(float(watch_tx_df["SALES_VALUE"].sum() or 0.0), 2)
                if not watch_tx_df.is_empty()
                else 0.0,
                "basket_ids_today": sorted(
                    int(b) for b in watch_tx_df["BASKET_ID"].unique().to_list()
                )
                if not watch_tx_df.is_empty()
                else [],
                "redeemed_coupons_today": [
                    str(u) for u in watch_redempt_df["COUPON_UPC"].to_list()
                ]
                if not watch_redempt_df.is_empty()
                else [],
                "cache_existed_before_del": watch_cached_before,
                "cache_del_executed": watch_invalidated,
                "cache_exists_after_del": bool(redis_client.exists(watch_cache_key)),
                "mongo_last_day": watch_doc["behavior_summary"]["last_day"] if watch_doc else None,
                "mongo_total_baskets": watch_doc["behavior_summary"]["total_baskets"]
                if watch_doc
                else None,
                "mongo_total_spend": watch_doc["behavior_summary"]["total_spend"]
                if watch_doc
                else None,
                "mongo_recent_baskets_count": len(watch_doc.get("recent_baskets", []))
                if watch_doc
                else 0,
                "mongo_recent_basket_ids": [
                    int(b["basket_id"]) for b in (watch_doc.get("recent_baskets", []) if watch_doc else [])
                ],
            },
        }
    finally:
        if owns_mongo and mongo_client is not None:
            mongo_client.close()
        if owns_cassandra and cluster is not None:
            cluster.shutdown()
        if owns_redis and redis_client is not None:
            redis_client.close()


def replay_range(
    start_day: int = 650,
    end_day: int = 656,
    seconds_per_day: int = 5,
    sleep_between_days: float = 0.0,
    watch_household: int = 208,
    prime_watched_cache_each_day: bool = False,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Replay a contiguous window of operational days (`start_day..end_day`) with telemetry."""
    if end_day < start_day:
        raise ValueError(f"end_day ({end_day}) must be >= start_day ({start_day})")

    cfg = settings or get_settings()
    mongo_client = get_mongo_client(settings=cfg)
    db = get_mongo_db(settings=cfg, client=mongo_client)
    cluster, session = get_cassandra_cluster_and_session(
        settings=cfg,
        keyspace=cfg.cassandra_keyspace,
    )
    redis_client = get_redis_client(settings=cfg)

    daily_logs: list[dict[str, Any]] = []
    try:
        for current_day in range(start_day, end_day + 1):
            if prime_watched_cache_each_day:
                doc = db[HOUSEHOLDS_COLLECTION].find_one(
                    {"household_key": watch_household},
                    {"_id": 0},
                )
                if doc is not None:
                    import json

                    redis_client.setex(
                        profile_key(watch_household),
                        cfg.profile_ttl_seconds,
                        json.dumps(doc),
                    )

            day_report = replay_day(
                day=current_day,
                seconds_per_day=seconds_per_day,
                watch_household=watch_household,
                db=db,
                session=session,
                redis_client=redis_client,
                settings=cfg,
            )
            daily_logs.append(day_report)

            if sleep_between_days > 0 and current_day < end_day:
                time.sleep(sleep_between_days)

        return daily_logs
    finally:
        mongo_client.close()
        cluster.shutdown()
        redis_client.close()


def restore_full_historical_state(
    cutoff_day: int = 711,
    reference_day: int = 650,
    seconds_per_day: int = 5,
    watch_households: Sequence[int] = (208,),
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Restore full historical state up to `cutoff_day = 711` and Redis `reference_day = 650`."""
    cfg = settings or get_settings()
    mongo_stats = ingest_mongo_households(cutoff_day=cutoff_day, settings=cfg)

    cluster, session = get_cassandra_cluster_and_session(
        settings=cfg,
        keyspace=cfg.cassandra_keyspace,
    )
    try:
        target_households = sorted({int(cfg.case_study_household), *(int(h) for h in watch_households)})
        watch_tx_df = _collect_streaming(
            pl.scan_csv(
                cfg.csv_path("transaction_data.csv"),
                schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
            ).filter(
                (pl.col("DAY") <= cutoff_day)
                & (pl.col("household_key").is_in(target_households))
            )
        )
        if not watch_tx_df.is_empty():
            hh_tuples, hh_prod_tuples = _df_to_tx_tuples(watch_tx_df)
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
    finally:
        cluster.shutdown()

    redis_stats = ingest_redis_state(
        reference_day=reference_day,
        seconds_per_day=seconds_per_day,
        include_weekly_showcases=True,
        settings=cfg,
    )
    return {
        "cutoff_day": cutoff_day,
        "reference_day": reference_day,
        "mongodb": mongo_stats,
        "redis": redis_stats,
    }


__all__ = [
    "COUPON_REDEMPT_SCHEMA_OVERRIDES",
    "prepare_replay_baseline",
    "replay_day",
    "replay_range",
    "restore_full_historical_state",
]
