"""Polyglot query library for BasketLens (Customer 360º + Business Questions 1, 2, 3 & Bonus)."""

from basketlens.queries.business_questions import (
    DEFAULT_CAUSAL_STORES,
    get_active_campaigns_for_household,
    get_avg_weekly_spend_by_demographic,
    get_display_and_mailer_lift,
    get_household_product_history,
    get_household_profile_and_recent_history,
    get_product_causal_promotion_lift,
    get_store_weekly_showcase,
)
from basketlens.queries.view_360 import benchmark_cache_aside_latency, build_360_view

__all__ = [
    "DEFAULT_CAUSAL_STORES",
    "benchmark_cache_aside_latency",
    "build_360_view",
    "get_active_campaigns_for_household",
    "get_avg_weekly_spend_by_demographic",
    "get_display_and_mailer_lift",
    "get_household_product_history",
    "get_household_profile_and_recent_history",
    "get_product_causal_promotion_lift",
    "get_store_weekly_showcase",
]
