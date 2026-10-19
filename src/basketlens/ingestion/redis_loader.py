"""Polars-backed Redis speed-layer ingestion for active campaigns, coupons, and weekly showcases."""

from __future__ import annotations

from typing import Any

import polars as pl
import redis

from basketlens.config import Settings, get_settings
from basketlens.connections import get_redis_client
from basketlens.ingestion.cassandra_loader import CAUSAL_SCHEMA_OVERRIDES, resolve_cutoff_week
from basketlens.ingestion.mongo_loader import TRANSACTION_SCHEMA_OVERRIDES, _collect_streaming
from basketlens.schemas.redis_schema import (
    campaign_coupons_key,
    campaign_key,
    clear_redis_namespace,
    compute_campaign_ttl_seconds,
    coupon_key,
    household_campaigns_key,
    household_coupons_key,
    ranking_week_key,
    store_week_displays_key,
)


def load_active_campaigns_to_redis(
    reference_day: int | None = None,
    seconds_per_day: int | None = None,
    clear_existing: bool = True,
    client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Load campaigns active on `reference_day` into Redis hashes with vigency-aligned TTL."""
    cfg = settings or get_settings()
    ref_day = reference_day if reference_day is not None else cfg.reference_day
    sec_per_day = seconds_per_day if seconds_per_day is not None else cfg.seconds_per_day

    owns_client = client is None
    redis_client = client or get_redis_client(settings=cfg)

    try:
        if clear_existing:
            clear_redis_namespace(client=redis_client, pattern="campanha:*")

        campaigns_df = _collect_streaming(
            pl.scan_csv(cfg.csv_path("campaign_desc.csv"))
            .filter((pl.col("START_DAY") <= ref_day) & (pl.col("END_DAY") >= ref_day))
            .sort("CAMPAIGN")
        )

        active_campaigns: dict[int, dict[str, Any]] = {}
        pipe = redis_client.pipeline(transaction=False)

        for row in campaigns_df.iter_rows(named=True):
            campaign_id = int(row["CAMPAIGN"])
            description = str(row["DESCRIPTION"])
            start_day = int(row["START_DAY"])
            end_day = int(row["END_DAY"])
            ttl_seconds = compute_campaign_ttl_seconds(
                end_day=end_day,
                reference_day=ref_day,
                seconds_per_day=sec_per_day,
            )

            key = campaign_key(campaign_id)
            pipe.hset(
                key,
                mapping={
                    "campaign": str(campaign_id),
                    "description": description,
                    "type": description,
                    "start_day": str(start_day),
                    "end_day": str(end_day),
                    "reference_day": str(ref_day),
                },
            )
            pipe.expire(key, ttl_seconds)

            active_campaigns[campaign_id] = {
                "campaign": campaign_id,
                "description": description,
                "start_day": start_day,
                "end_day": end_day,
                "ttl_seconds": ttl_seconds,
            }

        pipe.execute()
        return {
            "reference_day": ref_day,
            "seconds_per_day": sec_per_day,
            "active_campaign_count": len(active_campaigns),
            "active_campaigns": active_campaigns,
        }
    finally:
        if owns_client:
            redis_client.close()


def load_active_coupons_and_eligibility_to_redis(
    active_campaigns: dict[int, dict[str, Any]],
    clear_existing: bool = True,
    client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Load active coupons (`cupom:{upc}`) and household eligibility sets via `redis.pipeline()`."""
    cfg = settings or get_settings()
    owns_client = client is None
    redis_client = client or get_redis_client(settings=cfg)

    try:
        if clear_existing:
            clear_redis_namespace(client=redis_client, pattern="cupom:*")
            clear_redis_namespace(client=redis_client, pattern="household:*")

        if not active_campaigns:
            return {"active_coupons": 0, "eligible_households": 0}

        active_ids = sorted(active_campaigns.keys())

        coupons_df = _collect_streaming(
            pl.scan_csv(
                cfg.csv_path("coupon.csv"),
                schema_overrides={"COUPON_UPC": pl.Utf8, "PRODUCT_ID": pl.Int64, "CAMPAIGN": pl.Int64},
            )
            .filter(pl.col("CAMPAIGN").is_in(active_ids))
            .group_by(["CAMPAIGN", "COUPON_UPC"])
            .agg(
                pl.col("PRODUCT_ID").first().alias("sample_product_id"),
                pl.col("PRODUCT_ID").n_unique().alias("product_count"),
            )
            .sort(["CAMPAIGN", "COUPON_UPC"])
        )

        coupons_by_campaign: dict[int, list[str]] = {cid: [] for cid in active_ids}
        pipe = redis_client.pipeline(transaction=False)
        coupon_count = 0

        for row in coupons_df.iter_rows(named=True):
            cid = int(row["CAMPAIGN"])
            upc = str(row["COUPON_UPC"])
            ttl_sec = int(active_campaigns[cid]["ttl_seconds"])
            coupons_by_campaign.setdefault(cid, []).append(upc)

            c_key = coupon_key(upc)
            pipe.hset(
                c_key,
                mapping={
                    "coupon_upc": upc,
                    "campaign": str(cid),
                    "product_id": str(int(row["sample_product_id"])),
                    "product_count": str(int(row["product_count"])),
                },
            )
            pipe.expire(c_key, ttl_sec)
            coupon_count += 1

        for cid, upcs in coupons_by_campaign.items():
            if upcs:
                pool_key = campaign_coupons_key(cid)
                pipe.sadd(pool_key, *upcs)
                pipe.expire(pool_key, int(active_campaigns[cid]["ttl_seconds"]))

        pipe.execute()

        eligibility_df = _collect_streaming(
            pl.scan_csv(cfg.csv_path("campaign_table.csv"))
            .filter(pl.col("CAMPAIGN").is_in(active_ids))
            .group_by("household_key")
            .agg(pl.col("CAMPAIGN").unique().sort().alias("campaigns"))
            .sort("household_key")
        )

        pipe = redis_client.pipeline(transaction=False)
        household_count = 0

        for row in eligibility_df.iter_rows(named=True):
            hh_key = int(row["household_key"])
            hh_campaigns = [int(c) for c in (row["campaigns"] or []) if int(c) in active_campaigns]
            if not hh_campaigns:
                continue

            max_ttl = max(int(active_campaigns[c]["ttl_seconds"]) for c in hh_campaigns)
            hh_camp_key = household_campaigns_key(hh_key)
            pipe.sadd(hh_camp_key, *(str(c) for c in hh_campaigns))
            pipe.expire(hh_camp_key, max_ttl)

            hh_upcs: list[str] = []
            for c in hh_campaigns:
                hh_upcs.extend(coupons_by_campaign.get(c, []))
            if hh_upcs:
                hh_coup_key = household_coupons_key(hh_key)
                pipe.sadd(hh_coup_key, *set(hh_upcs))
                pipe.expire(hh_coup_key, max_ttl)

            household_count += 1

        pipe.execute()
        return {
            "active_coupons": coupon_count,
            "eligible_households": household_count,
        }
    finally:
        if owns_client:
            redis_client.close()


def load_weekly_rankings_and_displays_to_redis(
    week_no: int = 93,
    top_n_commodities: int = 20,
    max_stores: int = 20,
    max_products_per_store: int = 100,
    ttl_seconds: int = 3600,
    client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Populate `ranking:week:{w}` (ZSET) and `store:{id}:week:{w}:displays` (SET) in Redis."""
    cfg = settings or get_settings()
    owns_client = client is None
    redis_client = client or get_redis_client(settings=cfg)

    try:
        tx_lf = pl.scan_csv(
            cfg.csv_path("transaction_data.csv"),
            schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
        ).filter(pl.col("WEEK_NO") == week_no)
        prod_lf = pl.scan_csv(cfg.csv_path("product.csv")).select(
            "PRODUCT_ID", "COMMODITY_DESC"
        )

        ranking_df = (
            _collect_streaming(
                tx_lf.join(prod_lf, on="PRODUCT_ID", how="left")
                .filter(
                    pl.col("COMMODITY_DESC").is_not_null()
                    & (pl.col("COMMODITY_DESC").str.strip_chars() != "")
                )
                .group_by("COMMODITY_DESC")
                .agg(pl.col("SALES_VALUE").sum().round(2).alias("week_sales"))
            )
            .sort("week_sales", descending=True)
            .head(top_n_commodities)
        )

        r_key = ranking_week_key(week_no)
        pipe = redis_client.pipeline(transaction=False)
        pipe.delete(r_key)
        zset_mapping = {
            str(row["COMMODITY_DESC"]): float(row["week_sales"])
            for row in ranking_df.iter_rows(named=True)
        }
        if zset_mapping:
            pipe.zadd(r_key, zset_mapping)
            pipe.expire(r_key, ttl_seconds)

        displays_df = (
            _collect_streaming(
                pl.scan_csv(
                    cfg.csv_path("causal_data.csv"),
                    schema_overrides=CAUSAL_SCHEMA_OVERRIDES,
                )
                .filter((pl.col("WEEK_NO") == week_no) & (pl.col("display") != "0"))
                .group_by("STORE_ID")
                .agg(
                    pl.col("PRODUCT_ID")
                    .unique()
                    .sort()
                    .head(max_products_per_store)
                    .alias("products")
                )
            )
            .sort("STORE_ID")
            .head(max_stores)
        )

        stores_written = 0
        for row in displays_df.iter_rows(named=True):
            store_id = int(row["STORE_ID"])
            products = [str(int(p)) for p in (row["products"] or [])]
            if not products:
                continue
            s_key = store_week_displays_key(store_id, week_no)
            pipe.delete(s_key)
            pipe.sadd(s_key, *products)
            pipe.expire(s_key, ttl_seconds)
            stores_written += 1

        pipe.execute()
        return {
            "week_no": week_no,
            "ranked_commodities": len(zset_mapping),
            "stores_with_displays": stores_written,
        }
    finally:
        if owns_client:
            redis_client.close()


def ingest_redis_state(
    reference_day: int | None = None,
    seconds_per_day: int | None = None,
    include_weekly_showcases: bool = True,
    client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Ingest active campaigns, coupons, household eligibility, and weekly showcases into Redis.

    Database Interaction:
        [CSVs: campaign_desc, campaign_table, coupon, coupon_redempt, transaction, causal]
           └──► Polars Lazy Filter (vigentes em reference_day)
                  └──► [Redis Pipeline em Memória]
                         ├── HSET + EXPIRE  campanha:{id}               (TTL proporcional à vigência)
                         ├── SADD + EXPIRE  campanha:{id}:coupons       (cupons da campanha ativa)
                         ├── HSET + EXPIRE  cupom:{upc}                 (regras e contagem de SKUs)
                         ├── SADD + EXPIRE  household:{id}:campaigns    (campanhas ativas do domicílio)
                         ├── SADD + EXPIRE  household:{id}:coupons      (cupons disponíveis não resgatados)
                         └── ZADD / SADD    ranking:week:{w} & store:{id}:week:{w}:displays
    """
    cfg = settings or get_settings()
    ref_day = reference_day if reference_day is not None else cfg.reference_day
    sec_per_day = seconds_per_day if seconds_per_day is not None else cfg.seconds_per_day

    owns_client = client is None
    redis_client = client or get_redis_client(settings=cfg)

    try:
        camp_res = load_active_campaigns_to_redis(
            reference_day=ref_day,
            seconds_per_day=sec_per_day,
            clear_existing=True,
            client=redis_client,
            settings=cfg,
        )
        elig_res = load_active_coupons_and_eligibility_to_redis(
            active_campaigns=camp_res["active_campaigns"],
            clear_existing=True,
            client=redis_client,
            settings=cfg,
        )
        showcase_res: dict[str, Any] = {
            "week_no": 0,
            "ranked_commodities": 0,
            "stores_with_displays": 0,
        }
        if include_weekly_showcases:
            week_no = resolve_cutoff_week(cutoff_day=ref_day, settings=cfg)
            showcase_res = load_weekly_rankings_and_displays_to_redis(
                week_no=week_no,
                client=redis_client,
                settings=cfg,
            )

        return {
            "reference_day": ref_day,
            "seconds_per_day": sec_per_day,
            "active_campaign_count": camp_res["active_campaign_count"],
            "active_campaigns": camp_res["active_campaigns"],
            "active_coupons": elig_res["active_coupons"],
            "eligible_households": elig_res["eligible_households"],
            "weekly_showcases": showcase_res,
        }
    finally:
        if owns_client:
            redis_client.close()


__all__ = [
    "ingest_redis_state",
    "load_active_campaigns_to_redis",
    "load_active_coupons_and_eligibility_to_redis",
    "load_weekly_rankings_and_displays_to_redis",
]


