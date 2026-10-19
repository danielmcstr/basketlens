"""Canonical Redis key builders (`object:id`) and namespace cleanup helpers."""

from __future__ import annotations

import redis

from basketlens.connections import get_redis_client

PREFIX_CAMPAIGN = "campanha"
PREFIX_COUPON = "cupom"
PREFIX_HOUSEHOLD = "household"
PREFIX_PROFILE = "profile"
PREFIX_RANKING = "ranking"
PREFIX_STORE = "store"

REDIS_NAMESPACE_PATTERNS: tuple[str, ...] = (
    f"{PREFIX_CAMPAIGN}:*",
    f"{PREFIX_COUPON}:*",
    f"{PREFIX_HOUSEHOLD}:*",
    f"{PREFIX_PROFILE}:*",
    f"{PREFIX_RANKING}:*",
    f"{PREFIX_STORE}:*",
)


def campaign_key(campaign: int | str) -> str:
    """Return canonical Redis HASH key for a campaign (`campanha:{campaign}`)."""
    return f"{PREFIX_CAMPAIGN}:{campaign}"


def campaign_coupons_key(campaign: int | str) -> str:
    """Return canonical Redis SET key for coupons belonging to a campaign (`campanha:{campaign}:coupons`)."""
    return f"{PREFIX_CAMPAIGN}:{campaign}:coupons"


def coupon_key(coupon_upc: int | str) -> str:
    """Return canonical Redis HASH key for a coupon (`cupom:{coupon_upc}`)."""
    return f"{PREFIX_COUPON}:{coupon_upc}"


def household_campaigns_key(household_key: int | str) -> str:
    """Return canonical Redis SET key for a household's active campaigns (`household:{id}:campaigns`)."""
    return f"{PREFIX_HOUSEHOLD}:{household_key}:campaigns"


def household_coupons_key(household_key: int | str) -> str:
    """Return canonical Redis SET key for a household's active coupons (`household:{id}:coupons`)."""
    return f"{PREFIX_HOUSEHOLD}:{household_key}:coupons"


def profile_key(household_key: int | str) -> str:
    """Return canonical Redis STRING key for a household's cached 360º profile (`profile:{id}`)."""
    return f"{PREFIX_PROFILE}:{household_key}"


def ranking_week_key(week_no: int | str) -> str:
    """Return canonical Redis ZSET key for weekly top commodities (`ranking:week:{w}`)."""
    return f"{PREFIX_RANKING}:week:{week_no}"


def store_week_displays_key(store_id: int | str, week_no: int | str) -> str:
    """Return canonical Redis SET key for store weekly physical displays (`store:{id}:week:{w}:displays`)."""
    return f"{PREFIX_STORE}:{store_id}:week:{week_no}:displays"


def compute_campaign_ttl_seconds(
    end_day: int,
    reference_day: int = 650,
    seconds_per_day: int = 5,
) -> int:
    """Compute campaign/coupon TTL in seconds aligned with vigency relative to reference_day."""
    return max(1, (int(end_day) - int(reference_day)) * int(seconds_per_day))


def clear_redis_namespace(
    client: redis.Redis | None = None,
    pattern: str = "*",
    batch_size: int = 500,
) -> int:
    """Delete all Redis keys matching `pattern` using `SCAN` and return the count deleted."""
    owns_client = client is None
    redis_client = client or get_redis_client()
    deleted_total = 0

    try:
        batch: list[str] = []
        for key in redis_client.scan_iter(match=pattern, count=batch_size):
            batch.append(str(key))
            if len(batch) >= batch_size:
                deleted_total += int(redis_client.delete(*batch))
                batch.clear()
        if batch:
            deleted_total += int(redis_client.delete(*batch))
        return deleted_total
    finally:
        if owns_client:
            redis_client.close()


def clear_all_basketlens_keys(client: redis.Redis | None = None) -> int:
    """Delete all keys across all BasketLens Redis namespaces and return total deleted."""
    owns_client = client is None
    redis_client = client or get_redis_client()
    try:
        total = 0
        for pattern in REDIS_NAMESPACE_PATTERNS:
            total += clear_redis_namespace(client=redis_client, pattern=pattern)
        return total
    finally:
        if owns_client:
            redis_client.close()


__all__ = [
    "PREFIX_CAMPAIGN",
    "PREFIX_COUPON",
    "PREFIX_HOUSEHOLD",
    "PREFIX_PROFILE",
    "PREFIX_RANKING",
    "PREFIX_STORE",
    "REDIS_NAMESPACE_PATTERNS",
    "campaign_coupons_key",
    "campaign_key",
    "clear_all_basketlens_keys",
    "clear_redis_namespace",
    "compute_campaign_ttl_seconds",
    "coupon_key",
    "household_campaigns_key",
    "household_coupons_key",
    "profile_key",
    "ranking_week_key",
    "store_week_displays_key",
]
