"""Polyglot pushdown queries answering the 3 mandatory business questions + Trade Marketing bonus."""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from typing import Any

import redis
from cassandra.cluster import Session
from cassandra.concurrent import execute_concurrent_with_args
from pymongo.database import Database

from basketlens.config import Settings, get_settings
from basketlens.connections import (
    get_cassandra_cluster_and_session,
    get_mongo_client,
    get_mongo_db,
    get_redis_client,
)
from basketlens.schemas.mongo_schema import HOUSEHOLDS_COLLECTION
from basketlens.schemas.redis_schema import (
    campaign_coupons_key,
    campaign_key,
    coupon_key,
    household_campaigns_key,
    household_coupons_key,
    ranking_week_key,
    store_week_displays_key,
)

DEFAULT_CAUSAL_STORES: tuple[int, ...] = (
    286,
    288,
    317,
    339,
    369,
    370,
    375,
    396,
    406,
    420,
    432,
    450,
    3182,
    3274,
)


def _natural_sort_key(val: str) -> tuple[int, str]:
    """Extract numeric suffix from ordinal labels like `Age Group1` or `Level10` for sorting."""
    match = re.search(r"(\d+)", str(val))
    return (int(match.group(1)) if match else 999, str(val))


def get_household_profile_and_recent_history(
    household_key: int,
    limit: int = 50,
    db: Database[dict[str, Any]] | None = None,
    session: Session | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Answer Business Question 1: MongoDB 360º profile + Cassandra ordered recent transactions.

    Database Interaction:
        get_household_profile_and_recent_history(208)
          ├──► [MongoDB]   db.households.find_one({household_key: 208})
          │                (demographics + behavior_summary + recent_baskets)
          └──► [Cassandra] SELECT * FROM transactions_by_household
                           WHERE household_key = 208 LIMIT N (partição já ordenada)
    """
    cfg = settings or get_settings()
    t0 = time.perf_counter()

    owns_mongo = db is None
    owns_cassandra = session is None
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

        t_mongo = time.perf_counter()
        profile_doc = db[HOUSEHOLDS_COLLECTION].find_one(
            {"household_key": int(household_key)},
            {"_id": 0},
        )
        mongo_ms = round((time.perf_counter() - t_mongo) * 1000, 3)

        t_cass = time.perf_counter()
        cql = (
            "SELECT household_key, week_no, day, basket_id, product_id, "
            "quantity, sales_value, store_id, trans_time, "
            "retail_disc, coupon_disc, coupon_match_disc "
            f"FROM transactions_by_household WHERE household_key = %s LIMIT {int(limit)}"
        )
        rows = session.execute(cql, (int(household_key),))
        recent_transactions = [
            {
                "household_key": int(r.household_key),
                "week_no": int(r.week_no),
                "day": int(r.day),
                "basket_id": int(r.basket_id),
                "product_id": int(r.product_id),
                "quantity": int(r.quantity),
                "sales_value": round(float(r.sales_value or 0.0), 2),
                "store_id": int(r.store_id),
                "trans_time": int(r.trans_time),
                "retail_disc": round(float(r.retail_disc or 0.0), 2),
                "coupon_disc": round(float(r.coupon_disc or 0.0), 2),
                "coupon_match_disc": round(float(r.coupon_match_disc or 0.0), 2),
            }
            for r in rows
        ]
        cassandra_ms = round((time.perf_counter() - t_cass) * 1000, 3)

        return {
            "household_key": int(household_key),
            "profile": profile_doc,
            "demographics": profile_doc.get("demographics") if profile_doc else None,
            "behavior_summary": profile_doc.get("behavior_summary") if profile_doc else None,
            "recent_baskets": profile_doc.get("recent_baskets", []) if profile_doc else [],
            "recent_transactions": recent_transactions,
            "transactions_returned": len(recent_transactions),
            "latency_ms": {
                "mongodb_ms": mongo_ms,
                "cassandra_ms": cassandra_ms,
                "total_ms": round((time.perf_counter() - t0) * 1000, 3),
            },
        }
    finally:
        if owns_mongo and mongo_client is not None:
            mongo_client.close()
        if owns_cassandra and cluster is not None:
            cluster.shutdown()


def get_household_product_history(
    household_key: int,
    product_id: int,
    limit: int = 50,
    session: Session | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Query `transactions_by_household_product` by composite partition key `(household_key, product_id)`.

    Database Interaction:
        get_household_product_history(208, 1017772)
          └──► [Cassandra] SELECT * FROM transactions_by_household_product
                           WHERE household_key = 208 AND product_id = 1017772
                           (chave composta ((household_key, product_id)) em O(1))
    """
    cfg = settings or get_settings()
    t0 = time.perf_counter()
    owns_cassandra = session is None
    cluster = None

    try:
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(
                settings=cfg,
                keyspace=cfg.cassandra_keyspace,
            )

        cql = (
            "SELECT household_key, product_id, day, basket_id, week_no, "
            "quantity, sales_value, store_id, retail_disc, coupon_disc, coupon_match_disc "
            "FROM transactions_by_household_product "
            f"WHERE household_key = %s AND product_id = %s LIMIT {int(limit)}"
        )
        rows = session.execute(cql, (int(household_key), int(product_id)))
        purchases = [
            {
                "household_key": int(r.household_key),
                "product_id": int(r.product_id),
                "day": int(r.day),
                "basket_id": int(r.basket_id),
                "week_no": int(r.week_no),
                "quantity": int(r.quantity),
                "sales_value": round(float(r.sales_value or 0.0), 2),
                "store_id": int(r.store_id),
                "retail_disc": round(float(r.retail_disc or 0.0), 2),
                "coupon_disc": round(float(r.coupon_disc or 0.0), 2),
                "coupon_match_disc": round(float(r.coupon_match_disc or 0.0), 2),
            }
            for r in rows
        ]

        return {
            "household_key": int(household_key),
            "product_id": int(product_id),
            "purchase_count": len(purchases),
            "total_units": sum(p["quantity"] for p in purchases),
            "total_spend": round(sum(p["sales_value"] for p in purchases), 2),
            "purchases": purchases,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    finally:
        if owns_cassandra and cluster is not None:
            cluster.shutdown()


def get_active_campaigns_for_household(
    household_key: int,
    redis_client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Answer Business Question 2: Active campaigns and coupons with `TTL > 0` in Redis.

    Database Interaction:
        get_active_campaigns_for_household(208)
          └──► [Redis em Memória]
                 ├── SMEMBERS household:208:campaigns ──► ids candidatos
                 ├── TTL/HGETALL campanha:{id} (filtra campanhas com TTL > 0)
                 └── Intersecta household:208:coupons ∩ campanha:{id}:coupons
                     ──► HGETALL cupom:{upc} (retorna os 21 cupons ativos, ex: 51800000050)
    """
    cfg = settings or get_settings()
    t0 = time.perf_counter()
    owns_redis = redis_client is None
    client = redis_client or get_redis_client(settings=cfg)

    try:
        hh_camp_ids = sorted(
            int(cid) for cid in client.smembers(household_campaigns_key(household_key))
        )
        hh_coupon_upcs = sorted(
            str(upc) for upc in client.smembers(household_coupons_key(household_key))
        )
        redeemed_entries = sorted(
            str(item) for item in client.smembers(f"household:{household_key}:redeemed_coupons")
        )

        active_campaigns: list[dict[str, Any]] = []
        expired_or_missing_campaigns: list[int] = []

        for cid in hh_camp_ids:
            c_key = campaign_key(cid)
            ttl_sec = int(client.ttl(c_key))
            if ttl_sec <= 0:
                expired_or_missing_campaigns.append(cid)
                continue

            meta = client.hgetall(c_key)
            if not meta:
                expired_or_missing_campaigns.append(cid)
                continue

            camp_pool_upcs = set(client.smembers(campaign_coupons_key(cid)))
            eligible_upcs = sorted(camp_pool_upcs.intersection(hh_coupon_upcs))
            coupons_detail: list[dict[str, Any]] = []
            for upc in eligible_upcs:
                c_meta = client.hgetall(coupon_key(upc))
                coupons_detail.append(
                    {
                        "coupon_upc": upc,
                        "campaign": cid,
                        "product_id": int(c_meta["product_id"]) if "product_id" in c_meta else None,
                        "product_count": int(c_meta["product_count"])
                        if "product_count" in c_meta
                        else 0,
                        "ttl_seconds": int(client.ttl(coupon_key(upc))),
                    }
                )

            description = str(meta.get("description", meta.get("type", "Unknown")))
            active_campaigns.append(
                {
                    "campaign": cid,
                    "description": description,
                    "type": description,
                    "targeting_mechanism": (
                        "Personalized by customer history"
                        if description == "TypeA"
                        else "Triggered/segmented campaign pool"
                    ),
                    "start_day": int(meta.get("start_day", 0)),
                    "end_day": int(meta.get("end_day", 0)),
                    "reference_day": int(meta.get("reference_day", 0)),
                    "ttl_seconds": ttl_sec,
                    "coupons": coupons_detail,
                    "coupon_count": len(coupons_detail),
                }
            )

        return {
            "household_key": int(household_key),
            "active_campaign_count": len(active_campaigns),
            "active_campaigns": active_campaigns,
            "expired_or_inactive_campaigns": expired_or_missing_campaigns,
            "redeemed_coupons_history": redeemed_entries,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    finally:
        if owns_redis:
            client.close()


def get_avg_weekly_spend_by_demographic(
    group_by_field: str = "classification_1",
    db: Database[dict[str, Any]] | None = None,
    session: Session | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Answer Business Question 3: Average weekly spend by demographic group across the 801 profiles.

    Database Interaction:
        get_avg_weekly_spend_by_demographic("classification_1" | "classification_3")
          │
          ├──► 1. [MongoDB]   db.households.find({demographics.<field>: {$exists: true}})
          │                   via índice idx_demographics_class1_class3 (801 chaves, zero COLLSCAN)
          │
          ├──► 2. [Cassandra] execute_concurrent_with_args em transactions_by_household
          │                   para as 801 partições (allow_filtering_used = False!)
          │
          └──► 3. [Agregação] Consolida gasto total, semanas ativas e gasto semanal médio ($)
    """
    cfg = settings or get_settings()
    t0 = time.perf_counter()

    owns_mongo = db is None
    owns_cassandra = session is None
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

        # Step 1: Indexed projection in MongoDB for the 801 households with demographics
        t_mongo = time.perf_counter()
        cursor = db[HOUSEHOLDS_COLLECTION].find(
            {f"demographics.{group_by_field}": {"$exists": True}},
            {
                "_id": 0,
                "household_key": 1,
                f"demographics.{group_by_field}": 1,
                "behavior_summary.total_spend": 1,
                "behavior_summary.active_weeks": 1,
                "behavior_summary.avg_weekly_spend": 1,
            },
        )
        demographic_docs = list(cursor)
        mongo_ms = round((time.perf_counter() - t_mongo) * 1000, 3)

        # Step 2: Concurrent partition-key queries in Cassandra (`WHERE household_key = ?`)
        # Zero `ALLOW FILTERING` and zero full-table scans
        t_cass = time.perf_counter()
        stmt = session.prepare(
            "SELECT household_key, week_no, sales_value "
            "FROM transactions_by_household WHERE household_key = ?"
        )
        hh_keys = [(int(doc["household_key"]),) for doc in demographic_docs]
        concurrent_results = execute_concurrent_with_args(
            session,
            stmt,
            hh_keys,
            concurrency=cfg.cassandra_concurrency,
        )

        cassandra_metrics_by_hh: dict[int, tuple[float, int]] = {}
        for (hh_tuple), (success, rows) in zip(hh_keys, concurrent_results):
            hh_id = hh_tuple[0]
            if not success:
                cassandra_metrics_by_hh[hh_id] = (0.0, 0)
                continue
            spend = 0.0
            weeks: set[int] = set()
            for r in rows:
                spend += float(r.sales_value or 0.0)
                weeks.add(int(r.week_no))
            cassandra_metrics_by_hh[hh_id] = (round(spend, 2), len(weeks))

        cassandra_ms = round((time.perf_counter() - t_cass) * 1000, 3)

        # Step 3: Aggregate in Python across the 801 demographic households
        groups_acc: dict[str, dict[str, Any]] = {}
        for doc in demographic_docs:
            hh_id = int(doc["household_key"])
            group_val = str(doc.get("demographics", {}).get(group_by_field, "UNKNOWN"))
            summary = doc.get("behavior_summary", {})
            mongo_spend = float(summary.get("total_spend", 0.0))
            mongo_weeks = max(1, int(summary.get("active_weeks", 1)))
            mongo_avg_weekly = float(summary.get("avg_weekly_spend", 0.0))

            cass_spend, cass_weeks = cassandra_metrics_by_hh.get(hh_id, (0.0, 0))

            bucket = groups_acc.setdefault(
                group_val,
                {
                    "group_value": group_val,
                    "household_count": 0,
                    "mongo_total_spend": 0.0,
                    "mongo_total_active_weeks": 0,
                    "mongo_sum_household_avg_weekly": 0.0,
                    "cassandra_sampled_spend": 0.0,
                    "cassandra_sampled_active_weeks": 0,
                },
            )
            bucket["household_count"] += 1
            bucket["mongo_total_spend"] += mongo_spend
            bucket["mongo_total_active_weeks"] += mongo_weeks
            bucket["mongo_sum_household_avg_weekly"] += mongo_avg_weekly
            bucket["cassandra_sampled_spend"] += cass_spend
            bucket["cassandra_sampled_active_weeks"] += max(1, cass_weeks)

        results: list[dict[str, Any]] = []
        for group_val in sorted(groups_acc.keys(), key=_natural_sort_key):
            b = groups_acc[group_val]
            hh_count = max(1, int(b["household_count"]))
            total_spend = round(float(b["mongo_total_spend"]), 2)
            total_active_weeks = max(1, int(b["mongo_total_active_weeks"]))
            cass_spend = round(float(b["cassandra_sampled_spend"]), 2)
            cass_weeks = max(1, int(b["cassandra_sampled_active_weeks"]))

            results.append(
                {
                    "group_field": group_by_field,
                    "group_value": group_val,
                    "household_count": int(b["household_count"]),
                    "total_spend": total_spend,
                    "total_active_weeks": total_active_weeks,
                    "avg_weekly_spend": round(total_spend / total_active_weeks, 2),
                    "avg_household_weekly_spend": round(
                        float(b["mongo_sum_household_avg_weekly"]) / hh_count, 2
                    ),
                    "cassandra_partition_spend": cass_spend,
                    "cassandra_partition_active_weeks": cass_weeks,
                    "cassandra_partition_avg_weekly_spend": round(cass_spend / cass_weeks, 2),
                }
            )

        return {
            "group_by_field": group_by_field,
            "total_demographic_households": len(demographic_docs),
            "allow_filtering_used": False,
            "groups": results,
            "latency_ms": {
                "mongodb_projection_ms": mongo_ms,
                "cassandra_801_partitions_ms": cassandra_ms,
                "total_ms": round((time.perf_counter() - t0) * 1000, 3),
            },
        }
    finally:
        if owns_mongo and mongo_client is not None:
            mongo_client.close()
        if owns_cassandra and cluster is not None:
            cluster.shutdown()


def get_product_causal_promotion_lift(
    product_id: int = 72717,
    store_ids: Sequence[int] | None = None,
    session: Session | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Bonus Trade Marketing query: combine `sales_by_product_week` and `causal_promotions_by_store_week`.

    Database Interaction:
        get_product_causal_promotion_lift(product_id)
          ├──► [Cassandra] SELECT * FROM sales_by_product_week WHERE product_id = ?
          ├──► [Cassandra] execute_concurrent_with_args em causal_promotions_by_store_week
          │                (detecta semanas COM vs. SEM display/mailer na gôndola/tabloide)
          └──► Compara médias de venda semanal (ex: SKU 862349 -> Lift = +347,56%)
    """
    cfg = settings or get_settings()
    t0 = time.perf_counter()
    owns_cassandra = session is None
    cluster = None

    try:
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(
                settings=cfg,
                keyspace=cfg.cassandra_keyspace,
            )

        # 1. Fetch weekly sales for `product_id` from `sales_by_product_week`
        sales_rows = list(
            session.execute(
                "SELECT product_id, week_no, total_units, total_sales, total_baskets "
                "FROM sales_by_product_week WHERE product_id = %s",
                (int(product_id),),
            )
        )
        sales_by_week: dict[int, dict[str, Any]] = {
            int(r.week_no): {
                "week_no": int(r.week_no),
                "total_units": int(r.total_units or 0),
                "total_sales": round(float(r.total_sales or 0.0), 2),
                "total_baskets": int(r.total_baskets or 0),
            }
            for r in sales_rows
        }

        # 2. Query `causal_promotions_by_store_week` by partition key `(store_id, week_no)` and clustering `product_id`
        target_stores = [int(s) for s in (store_ids or DEFAULT_CAUSAL_STORES)]
        target_weeks = sorted(
            {
                *sales_by_week.keys(),
                12,
                24,
                25,
                29,
                30,
                35,
                36,
                38,
                39,
                40,
                47,
                51,
                56,
                63,
                64,
                87,
                88,
                91,
                92,
                93,
                94,
                101,
            }
        )

        causal_stmt = session.prepare(
            "SELECT store_id, week_no, product_id, display_type, mailer_page "
            "FROM causal_promotions_by_store_week "
            "WHERE store_id = ? AND week_no = ? AND product_id = ?"
        )
        params = [(s, w, int(product_id)) for s in target_stores for w in target_weeks]
        causal_res = execute_concurrent_with_args(
            session,
            causal_stmt,
            params,
            concurrency=cfg.cassandra_concurrency,
        )

        causal_by_week: dict[int, list[dict[str, Any]]] = {}
        for ok, rows in causal_res:
            if not ok:
                continue
            for r in rows:
                causal_by_week.setdefault(int(r.week_no), []).append(
                    {
                        "store_id": int(r.store_id),
                        "week_no": int(r.week_no),
                        "display_type": str(r.display_type),
                        "mailer_page": str(r.mailer_page),
                    }
                )

        all_weeks = sorted({*sales_by_week.keys(), *causal_by_week.keys()})
        weekly_comparison: list[dict[str, Any]] = []
        promoted_weeks_sales: list[float] = []
        baseline_weeks_sales: list[float] = []

        for w in all_weeks:
            s_info = sales_by_week.get(
                w,
                {
                    "week_no": w,
                    "total_units": 0,
                    "total_sales": 0.0,
                    "total_baskets": 0,
                },
            )
            c_list = causal_by_week.get(w, [])
            displays = sorted({c["display_type"] for c in c_list if c["display_type"] != "0"})
            mailers = sorted({c["mailer_page"] for c in c_list if c["mailer_page"] != "0"})
            is_promoted = bool(displays or mailers)

            if s_info["total_sales"] > 0:
                if is_promoted:
                    promoted_weeks_sales.append(float(s_info["total_sales"]))
                else:
                    baseline_weeks_sales.append(float(s_info["total_sales"]))

            weekly_comparison.append(
                {
                    "week_no": w,
                    "total_units": s_info["total_units"],
                    "total_sales": s_info["total_sales"],
                    "total_baskets": s_info["total_baskets"],
                    "is_promoted": is_promoted,
                    "promoted_stores_count": len(c_list),
                    "active_display_codes": displays,
                    "active_mailer_codes": mailers,
                    "store_promotions": c_list,
                }
            )

        avg_promoted = (
            round(sum(promoted_weeks_sales) / len(promoted_weeks_sales), 2)
            if promoted_weeks_sales
            else 0.0
        )
        avg_baseline = (
            round(sum(baseline_weeks_sales) / len(baseline_weeks_sales), 2)
            if baseline_weeks_sales
            else 0.0
        )
        lift_pct = (
            round(((avg_promoted - avg_baseline) / avg_baseline) * 100.0, 2)
            if avg_baseline > 0 and avg_promoted > 0
            else None
        )

        return {
            "product_id": int(product_id),
            "weeks_analyzed": len(weekly_comparison),
            "weeks_with_sales": len(sales_by_week),
            "weeks_with_causal_promotions": len(causal_by_week),
            "avg_weekly_sales_promoted": avg_promoted,
            "avg_weekly_sales_baseline": avg_baseline,
            "promotional_lift_pct": lift_pct,
            "weekly_breakdown": weekly_comparison,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    finally:
        if owns_cassandra and cluster is not None:
            cluster.shutdown()


# Alias for compatibility with proposal/documentation naming
get_display_and_mailer_lift = get_product_causal_promotion_lift


def get_store_weekly_showcase(
    store_id: int = 3274,
    week_no: int = 94,
    top_n: int = 10,
    redis_client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Bonus Trade Marketing query: read weekly commodity ranking ZSET and store display SET from Redis.

    Database Interaction:
        get_store_weekly_showcase(store_id=288, week_no=94)
          ├──► [Redis] ZREVRANGE ranking:week:94 0 9 WITHSCORES ──► Top categorias ($)
          └──► [Redis] SMEMBERS store:288:week:94:displays      ──► 100 SKUs em gôndola na loja
    """
    cfg = settings or get_settings()
    t0 = time.perf_counter()
    owns_redis = redis_client is None
    client = redis_client or get_redis_client(settings=cfg)

    try:
        r_key = ranking_week_key(week_no)
        s_key = store_week_displays_key(store_id, week_no)

        top_commodities_raw = client.zrevrange(r_key, 0, max(0, top_n - 1), withscores=True)
        top_commodities = [
            {
                "rank": idx + 1,
                "commodity_desc": str(member),
                "week_sales": round(float(score), 2),
            }
            for idx, (member, score) in enumerate(top_commodities_raw)
        ]

        display_products = sorted(int(p) for p in client.smembers(s_key))

        return {
            "store_id": int(store_id),
            "week_no": int(week_no),
            "ranking_key": r_key,
            "ranking_ttl_seconds": int(client.ttl(r_key)),
            "top_commodities": top_commodities,
            "store_displays_key": s_key,
            "store_displays_ttl_seconds": int(client.ttl(s_key)),
            "displayed_product_ids": display_products,
            "displayed_products_count": len(display_products),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        }
    finally:
        if owns_redis:
            client.close()


__all__ = [
    "DEFAULT_CAUSAL_STORES",
    "get_active_campaigns_for_household",
    "get_avg_weekly_spend_by_demographic",
    "get_display_and_mailer_lift",
    "get_household_product_history",
    "get_household_profile_and_recent_history",
    "get_product_causal_promotion_lift",
    "get_store_weekly_showcase",
]
