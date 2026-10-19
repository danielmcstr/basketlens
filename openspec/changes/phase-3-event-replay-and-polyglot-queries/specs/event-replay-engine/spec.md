## ADDED Requirements

### Requirement: Daily Operational Event Replay (`basketlens.replay`)
The `basketlens.replay` module SHALL provide a day-by-day simulation engine (`replay_day(day, seconds_per_day)`) that extracts only the events of `DAY == day` via Polars `scan_csv()` without loading the full dataset into memory, and applies coordinated updates across Cassandra, MongoDB, and Redis.

#### Scenario: Replaying Day 654 for John Smith (`household_key = 208`)
- **WHEN** the baseline is loaded up to Day 649 and `replay_range(start_day=650, end_day=654, seconds_per_day=5)` is executed
- **THEN** on Day 654 (`household_key = 208` purchasing `product_id = 1017772` and redeeming `coupon_upc = "51800000050"` in Campaign 22):
  1. Cassandra `transactions_by_household` and `transactions_by_household_product` MUST contain the new Day 654 items for `household_key = 208`
  2. MongoDB `households` document for `household_key = 208` MUST have `behavior_summary.last_day == 654`, updated `total_spend` and `total_baskets`, and `recent_baskets` capped at a maximum of 5 baskets (`len(recent_baskets) <= 5`) including basket `41531980403` from Day 654
  3. Redis `DEL profile:208` MUST be executed upon the purchase update so any cached profile is invalidated

### Requirement: Dynamic Campaign Lifecycle and TTL Expiration During Replay
The `basketlens.replay` engine SHALL update campaign TTLs in Redis at each simulated day step and allow campaigns whose `END_DAY` has passed (or whose compressed TTL has elapsed) to expire automatically.

#### Scenario: Campaign 22 expires after Day 656
- **WHEN** `replay_day(day=656, seconds_per_day=2)` is executed and the compressed TTL window elapses (or `replay_day(day=657)` runs)
- **THEN** `campanha:22` MUST no longer appear as an active campaign (`redis.ttl("campanha:22") <= 0`) when querying active campaigns for `household_key = 208`
