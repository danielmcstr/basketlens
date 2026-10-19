"""Out-of-core Polars ingestion for MongoDB `households` (2,500 360º profiles)."""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any

import polars as pl
from pymongo import ReplaceOne
from pymongo.database import Database

from basketlens.config import Settings, get_settings
from basketlens.connections import get_mongo_client, get_mongo_db
from basketlens.schemas.mongo_schema import HOUSEHOLDS_COLLECTION, ensure_mongo_indexes

TRANSACTION_SCHEMA_OVERRIDES: dict[str, pl.DataType] = {
    "household_key": pl.Int64,
    "BASKET_ID": pl.Int64,
    "DAY": pl.Int64,
    "PRODUCT_ID": pl.Int64,
    "QUANTITY": pl.Int64,
    "SALES_VALUE": pl.Float64,
    "STORE_ID": pl.Int64,
    "RETAIL_DISC": pl.Float64,
    "TRANS_TIME": pl.Int64,
    "WEEK_NO": pl.Int64,
    "COUPON_DISC": pl.Float64,
    "COUPON_MATCH_DISC": pl.Float64,
}


def _collect_streaming(lf: pl.LazyFrame) -> pl.DataFrame:
    """Collect a Polars LazyFrame using streaming execution."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return lf.collect(streaming=True)


def compute_behavior_summaries(
    cutoff_day: int = 711,
    settings: Settings | None = None,
) -> dict[int, dict[str, Any]]:
    """Compute `behavior_summary` out-of-core per household up to `cutoff_day`."""
    cfg = settings or get_settings()
    tx_path = cfg.csv_path("transaction_data.csv")
    prod_path = cfg.csv_path("product.csv")

    tx_lf = pl.scan_csv(
        tx_path,
        schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
    ).filter(pl.col("DAY") <= cutoff_day)

    base_metrics_df = _collect_streaming(
        tx_lf.group_by("household_key").agg(
            pl.col("SALES_VALUE").sum().alias("total_spend"),
            pl.col("BASKET_ID").n_unique().alias("total_baskets"),
            pl.col("WEEK_NO").n_unique().alias("active_weeks"),
            pl.col("DAY").min().alias("first_day"),
            pl.col("DAY").max().alias("last_day"),
        )
    )

    prod_lf = pl.scan_csv(prod_path).select("PRODUCT_ID", "DEPARTMENT", "COMMODITY_DESC")
    joined_lf = tx_lf.join(prod_lf, on="PRODUCT_ID", how="left")

    dept_df = (
        _collect_streaming(
            joined_lf.filter(
                pl.col("DEPARTMENT").is_not_null()
                & (pl.col("DEPARTMENT").str.strip_chars() != "")
            )
            .group_by(["household_key", "DEPARTMENT"])
            .agg(pl.col("SALES_VALUE").sum().alias("dept_spend"))
        )
        .sort(["household_key", "dept_spend", "DEPARTMENT"], descending=[False, True, False])
        .group_by("household_key", maintain_order=True)
        .agg(pl.col("DEPARTMENT").head(3).alias("top_departments"))
    )

    comm_df = (
        _collect_streaming(
            joined_lf.filter(
                pl.col("COMMODITY_DESC").is_not_null()
                & (pl.col("COMMODITY_DESC").str.strip_chars() != "")
            )
            .group_by(["household_key", "COMMODITY_DESC"])
            .agg(pl.col("SALES_VALUE").sum().alias("comm_spend"))
        )
        .sort(
            ["household_key", "comm_spend", "COMMODITY_DESC"],
            descending=[False, True, False],
        )
        .group_by("household_key", maintain_order=True)
        .agg(pl.col("COMMODITY_DESC").head(3).alias("top_commodities"))
    )

    merged_df = (
        base_metrics_df.join(dept_df, on="household_key", how="left")
        .join(comm_df, on="household_key", how="left")
        .sort("household_key")
    )

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summaries: dict[int, dict[str, Any]] = {}

    for row in merged_df.iter_rows(named=True):
        hh_key = int(row["household_key"])
        total_spend = round(float(row["total_spend"] or 0.0), 2)
        total_baskets = int(row["total_baskets"] or 0)
        active_weeks = max(1, int(row["active_weeks"] or 1))
        avg_basket_value = round(total_spend / max(1, total_baskets), 2)
        avg_weekly_spend = round(total_spend / active_weeks, 2)

        summaries[hh_key] = {
            "total_spend": total_spend,
            "total_baskets": total_baskets,
            "active_weeks": active_weeks,
            "avg_basket_value": avg_basket_value,
            "avg_weekly_spend": avg_weekly_spend,
            "first_day": int(row["first_day"]),
            "last_day": int(row["last_day"]),
            "top_departments": list(row["top_departments"] or []),
            "top_commodities": list(row["top_commodities"] or []),
            "updated_at": now_iso,
        }

    return summaries


def extract_recent_baskets(
    cutoff_day: int = 711,
    limit_baskets: int | None = None,
    settings: Settings | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """Extract the most recent N baskets per household (Subset + Extended Reference patterns)."""
    cfg = settings or get_settings()
    max_baskets = limit_baskets or cfg.recent_baskets_limit
    tx_path = cfg.csv_path("transaction_data.csv")
    prod_path = cfg.csv_path("product.csv")

    tx_lf = pl.scan_csv(
        tx_path,
        schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
    ).filter(pl.col("DAY") <= cutoff_day)

    baskets_df = (
        _collect_streaming(
            tx_lf.group_by(["household_key", "BASKET_ID"]).agg(
                pl.col("DAY").max().alias("day"),
                pl.col("WEEK_NO").max().alias("week_no"),
                pl.col("STORE_ID").first().alias("store_id"),
                pl.col("TRANS_TIME").max().alias("trans_time"),
                pl.col("SALES_VALUE").sum().alias("total"),
            )
        )
        .sort(
            ["household_key", "day", "trans_time", "BASKET_ID"],
            descending=[False, False, False, False],
        )
        .group_by("household_key", maintain_order=True)
        .tail(max_baskets)
    )

    selected_baskets_lf = baskets_df.select(["household_key", "BASKET_ID"]).lazy()
    prod_lf = pl.scan_csv(prod_path).select("PRODUCT_ID", "DEPARTMENT", "COMMODITY_DESC")

    items_df = _collect_streaming(
        tx_lf.join(selected_baskets_lf, on=["household_key", "BASKET_ID"], how="inner")
        .join(prod_lf, on="PRODUCT_ID", how="left")
        .select(
            "household_key",
            "BASKET_ID",
            "PRODUCT_ID",
            "QUANTITY",
            "SALES_VALUE",
            "DEPARTMENT",
            "COMMODITY_DESC",
        )
    ).sort(["household_key", "BASKET_ID", "PRODUCT_ID"])

    items_by_basket: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in items_df.iter_rows(named=True):
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

    recent_by_hh: dict[int, list[dict[str, Any]]] = {}
    for row in baskets_df.iter_rows(named=True):
        hh_key = int(row["household_key"])
        basket_id = int(row["BASKET_ID"])
        recent_by_hh.setdefault(hh_key, []).append(
            {
                "basket_id": basket_id,
                "day": int(row["day"]),
                "week_no": int(row["week_no"]),
                "store_id": int(row["store_id"]),
                "total": round(float(row["total"] or 0.0), 2),
                "items": items_by_basket.get((hh_key, basket_id), []),
            }
        )

    return recent_by_hh


def load_demographics_map(
    settings: Settings | None = None,
) -> dict[int, dict[str, str]]:
    """Read `hh_demographic.csv` (801 rows) and return normalized subdocuments by `household_key`."""
    cfg = settings or get_settings()
    demo_df = _collect_streaming(pl.scan_csv(cfg.csv_path("hh_demographic.csv")))

    demographics_by_hh: dict[int, dict[str, str]] = {}
    for row in demo_df.iter_rows(named=True):
        hh_key = int(row["household_key"])
        c1 = str(row["classification_1"])
        c2 = str(row["classification_2"])
        c3 = str(row["classification_3"])
        homeowner = str(row["HOMEOWNER_DESC"])
        c4 = str(row["classification_4"])
        c5 = str(row["classification_5"])
        kid_cat = str(row["KID_CATEGORY_DESC"])

        demographics_by_hh[hh_key] = {
            "classification_1": c1,
            "classification_2": c2,
            "classification_3": c3,
            "homeowner_desc": homeowner,
            "classification_4": c4,
            "classification_5": c5,
            "kid_category_desc": kid_cat,
            "age_group": c1,
            "marital_code": c2,
            "income_level": c3,
            "household_size": c4,
            "hh_comp_group": c5,
        }

    return demographics_by_hh


def load_campaigns_received_map(
    cutoff_day: int = 711,
    settings: Settings | None = None,
) -> dict[int, list[int]]:
    """Read `campaign_table.csv` joined with `campaign_desc.csv` (`START_DAY <= cutoff_day`)."""
    cfg = settings or get_settings()
    ct_lf = pl.scan_csv(cfg.csv_path("campaign_table.csv"))
    cd_lf = pl.scan_csv(cfg.csv_path("campaign_desc.csv")).filter(
        pl.col("START_DAY") <= cutoff_day
    )

    campaigns_df = _collect_streaming(
        ct_lf.join(cd_lf, on=["CAMPAIGN", "DESCRIPTION"], how="inner")
        .group_by("household_key")
        .agg(pl.col("CAMPAIGN").unique().sort().alias("campaigns"))
    )

    return {
        int(row["household_key"]): [int(c) for c in (row["campaigns"] or [])]
        for row in campaigns_df.iter_rows(named=True)
    }


def build_household_documents(
    cutoff_day: int = 711,
    limit_baskets: int | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Build all 2,500 `households` documents (801 with `demographics`, 1,699 without)."""
    cfg = settings or get_settings()
    all_hh_df = _collect_streaming(
        pl.scan_csv(
            cfg.csv_path("transaction_data.csv"),
            schema_overrides=TRANSACTION_SCHEMA_OVERRIDES,
        )
        .select(pl.col("household_key").unique().sort())
    )
    all_household_keys = [int(r["household_key"]) for r in all_hh_df.iter_rows(named=True)]

    summaries = compute_behavior_summaries(cutoff_day=cutoff_day, settings=cfg)
    recent_baskets = extract_recent_baskets(
        cutoff_day=cutoff_day,
        limit_baskets=limit_baskets,
        settings=cfg,
    )
    demographics_map = load_demographics_map(settings=cfg)
    campaigns_map = load_campaigns_received_map(cutoff_day=cutoff_day, settings=cfg)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documents: list[dict[str, Any]] = []

    for hh_key in all_household_keys:
        summary = summaries.get(
            hh_key,
            {
                "total_spend": 0.0,
                "total_baskets": 0,
                "active_weeks": 0,
                "avg_basket_value": 0.0,
                "avg_weekly_spend": 0.0,
                "first_day": 0,
                "last_day": 0,
                "top_departments": [],
                "top_commodities": [],
                "updated_at": now_iso,
            },
        )
        doc: dict[str, Any] = {
            "household_key": hh_key,
            "behavior_summary": summary,
            "recent_baskets": recent_baskets.get(hh_key, []),
            "campaigns_received": campaigns_map.get(hh_key, []),
        }
        if hh_key in demographics_map:
            doc["demographics"] = demographics_map[hh_key]

        documents.append(doc)

    return documents


def ingest_mongo_households(
    cutoff_day: int = 711,
    limit_baskets: int | None = None,
    batch_size: int = 500,
    db: Database[dict[str, Any]] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Ingest all 2,500 household 360º profiles into MongoDB in batches via `bulk_write`."""
    cfg = settings or get_settings()
    owns_client = db is None
    client = None

    try:
        if db is None:
            client = get_mongo_client(settings=cfg)
            db = get_mongo_db(settings=cfg, client=client)

        ensure_mongo_indexes(db)
        collection = db[HOUSEHOLDS_COLLECTION]
        documents = build_household_documents(
            cutoff_day=cutoff_day,
            limit_baskets=limit_baskets,
            settings=cfg,
        )

        upserted_or_modified = 0
        for start in range(0, len(documents), batch_size):
            batch_docs = documents[start : start + batch_size]
            operations = [
                ReplaceOne({"household_key": doc["household_key"]}, doc, upsert=True)
                for doc in batch_docs
            ]
            result = collection.bulk_write(operations, ordered=False)
            upserted_or_modified += (
                int(result.upserted_count)
                + int(result.modified_count)
                + int(result.matched_count)
            )

        total_docs = int(collection.count_documents({}))
        with_demographics = int(
            collection.count_documents({"demographics": {"$exists": True}})
        )
        without_demographics = int(
            collection.count_documents({"demographics": {"$exists": False}})
        )

        return {
            "cutoff_day": cutoff_day,
            "total_documents": total_docs,
            "with_demographics": with_demographics,
            "without_demographics": without_demographics,
            "batches_written": (len(documents) + batch_size - 1) // batch_size,
        }
    finally:
        if owns_client and client is not None:
            client.close()


__all__ = [
    "TRANSACTION_SCHEMA_OVERRIDES",
    "build_household_documents",
    "compute_behavior_summaries",
    "extract_recent_baskets",
    "ingest_mongo_households",
    "load_campaigns_received_map",
    "load_demographics_map",
]


