"""Unified Customer 360º View (`build_360_view`) with Redis Cache-Aside, MongoDB, and Cassandra."""

from __future__ import annotations

import json
import time
from typing import Any

import redis
from cassandra.cluster import Session
from pymongo.database import Database

from basketlens.config import Settings, get_settings
from basketlens.connections import (
    get_cassandra_cluster_and_session,
    get_mongo_client,
    get_mongo_db,
    get_redis_client,
)
from basketlens.queries.business_questions import get_active_campaigns_for_household
from basketlens.schemas.mongo_schema import HOUSEHOLDS_COLLECTION
from basketlens.schemas.redis_schema import profile_key


def build_360_view(
    household_key: int,
    limit_transactions: int = 50,
    use_cache: bool = True,
    profile_ttl_seconds: int | None = None,
    db: Database[dict[str, Any]] | None = None,
    session: Session | None = None,
    redis_client: redis.Redis | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Assemble the complete Customer 360º view across Redis (Cache-Aside + TTL), MongoDB, and Cassandra.

    Database Interaction:
        build_360_view(household_key=208)
          │
          ├──► 1. [Redis] GET profile:208
          │         ├─► Cache Hit  : Retorna JSON da RAM (< 0.5 ms, source="redis")
          │         └─► Cache Miss : Consulta [MongoDB] find_one({household_key: 208})
          │                          e grava [Redis] SETEX profile:208 60 <json>
          │
          ├──► 2. [Cassandra] SELECT ... FROM transactions_by_household WHERE household_key = 208 LIMIT N
          │                   (leitura O(1) no topo da partição ordenada por week_no DESC, day DESC)
          │
          └──► 3. [Redis]     SMEMBERS household:208:campaigns + TTL/HGETALL campanha:{id} (TTL > 0)
    """
    cfg = settings or get_settings()
    ttl_sec = profile_ttl_seconds if profile_ttl_seconds is not None else cfg.profile_ttl_seconds
    t0 = time.perf_counter()

    owns_mongo = db is None
    owns_cassandra = session is None
    owns_redis = redis_client is None
    mongo_client = None
    cluster = None

    try:
        if redis_client is None:
            redis_client = get_redis_client(settings=cfg)
        if db is None:
            mongo_client = get_mongo_client(settings=cfg)
            db = get_mongo_db(settings=cfg, client=mongo_client)
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(
                settings=cfg,
                keyspace=cfg.cassandra_keyspace,
            )

        # 1. Profile lookup via Cache-Aside (`GET profile:{id}` -> MongoDB fallback -> `SETEX`)
        t_profile = time.perf_counter()
        cache_key = profile_key(household_key)
        cache_hit = False
        profile_doc: dict[str, Any] | None = None

        if use_cache:
            cached_raw = redis_client.get(cache_key)
            if cached_raw:
                profile_doc = json.loads(str(cached_raw))
                cache_hit = True

        if profile_doc is None:
            profile_doc = db[HOUSEHOLDS_COLLECTION].find_one(
                {"household_key": int(household_key)},
                {"_id": 0},
            )
            if profile_doc is not None and use_cache:
                redis_client.setex(cache_key, int(ttl_sec), json.dumps(profile_doc))

        profile_latency_ms = round((time.perf_counter() - t_profile) * 1000, 3)
        profile_ttl_remaining = int(redis_client.ttl(cache_key)) if use_cache else -2

        # 2. Recent item-level transactions from Cassandra (`transactions_by_household`)
        t_cass = time.perf_counter()
        cql = (
            "SELECT household_key, week_no, day, basket_id, product_id, "
            "quantity, sales_value, store_id, trans_time, "
            "retail_disc, coupon_disc, coupon_match_disc "
            f"FROM transactions_by_household WHERE household_key = %s LIMIT {int(limit_transactions)}"
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
        cassandra_latency_ms = round((time.perf_counter() - t_cass) * 1000, 3)

        # 3. Real-time active campaigns and coupons (`TTL > 0`) from Redis
        t_redis = time.perf_counter()
        active_eligibility = get_active_campaigns_for_household(
            household_key=int(household_key),
            redis_client=redis_client,
            settings=cfg,
        )
        redis_campaigns_latency_ms = round((time.perf_counter() - t_redis) * 1000, 3)

        return {
            "household_key": int(household_key),
            "cache": {
                "key": cache_key,
                "cache_hit": cache_hit,
                "source": "redis" if cache_hit else "mongodb",
                "ttl_remaining_seconds": profile_ttl_remaining,
            },
            "profile": profile_doc,
            "demographics": profile_doc.get("demographics") if profile_doc else None,
            "behavior_summary": profile_doc.get("behavior_summary") if profile_doc else None,
            "recent_baskets": profile_doc.get("recent_baskets", []) if profile_doc else [],
            "recent_transactions": recent_transactions,
            "active_campaigns": active_eligibility["active_campaigns"],
            "active_campaign_count": active_eligibility["active_campaign_count"],
            "redeemed_coupons_history": active_eligibility["redeemed_coupons_history"],
            "latency_ms": {
                "profile_lookup_ms": profile_latency_ms,
                "cassandra_transactions_ms": cassandra_latency_ms,
                "redis_campaigns_ms": redis_campaigns_latency_ms,
                "total_ms": round((time.perf_counter() - t0) * 1000, 3),
            },
        }
    finally:
        if owns_mongo and mongo_client is not None:
            mongo_client.close()
        if owns_cassandra and cluster is not None:
            cluster.shutdown()
        if owns_redis and redis_client is not None:
            redis_client.close()


def benchmark_cache_aside_latency(
    household_key: int = 208,
    iterations: int = 15,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Benchmark profile lookup latency comparing Cold Cache Miss (MongoDB) vs. Warm Cache Hit (Redis).

    Database Interaction:
        Iteração 1..N:
          ├── Cold Cache Miss : [Redis] DEL profile:208 ──► [MongoDB] find_one() ──► [Redis] SETEX
          └── Warm Cache Hit  : [Redis] GET profile:208 ──► Retorno direto da RAM (Speedup ~3.2x a 6.8x)
    """
    cfg = settings or get_settings()
    mongo_client = get_mongo_client(settings=cfg)
    db = get_mongo_db(settings=cfg, client=mongo_client)
    cluster, session = get_cassandra_cluster_and_session(
        settings=cfg,
        keyspace=cfg.cassandra_keyspace,
    )
    redis_client = get_redis_client(settings=cfg)

    try:
        cache_key = profile_key(household_key)
        miss_samples_ms: list[float] = []
        hit_samples_ms: list[float] = []

        for _ in range(max(1, iterations)):
            redis_client.delete(cache_key)
            miss_res = build_360_view(
                household_key=household_key,
                limit_transactions=10,
                use_cache=True,
                db=db,
                session=session,
                redis_client=redis_client,
                settings=cfg,
            )
            miss_samples_ms.append(float(miss_res["latency_ms"]["profile_lookup_ms"]))

            hit_res = build_360_view(
                household_key=household_key,
                limit_transactions=10,
                use_cache=True,
                db=db,
                session=session,
                redis_client=redis_client,
                settings=cfg,
            )
            hit_samples_ms.append(float(hit_res["latency_ms"]["profile_lookup_ms"]))

        avg_miss = round(sum(miss_samples_ms) / len(miss_samples_ms), 3)
        avg_hit = round(sum(hit_samples_ms) / len(hit_samples_ms), 3)
        speedup = round(avg_miss / max(0.001, avg_hit), 2)

        return {
            "household_key": household_key,
            "iterations": iterations,
            "avg_cache_miss_ms": avg_miss,
            "avg_cache_hit_ms": avg_hit,
            "speedup_factor": speedup,
            "miss_samples_ms": miss_samples_ms,
            "hit_samples_ms": hit_samples_ms,
        }
    finally:
        mongo_client.close()
        cluster.shutdown()
        redis_client.close()


__all__ = [
    "benchmark_cache_aside_latency",
    "build_360_view",
]
