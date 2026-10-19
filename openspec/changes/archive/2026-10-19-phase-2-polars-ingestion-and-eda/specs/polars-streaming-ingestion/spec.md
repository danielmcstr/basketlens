## ADDED Requirements

### Requirement: Out-of-Core Polars Streaming Rule for Large CSVs
The ingestion pipeline SHALL process `transaction_data.csv` (2.59M rows) and `causal_data.csv` (3.68M rows) exclusively via Polars lazy frames (`pl.scan_csv`) with streaming collection (`.collect(streaming=True)`) or batched iteration (`pl.read_csv_batched` / partitioned week batches), and MUST NOT call `pl.read_csv()` on the full `transaction_data.csv` or `causal_data.csv` files at once.

#### Scenario: Ingesting transactions and causal data in bounded memory batches
- **WHEN** the Cassandra loader ingests `transaction_data.csv` and `causal_data.csv`
- **THEN** it MUST iterate over bounded batches (e.g., `batch_size = 50_000` rows or week-by-week slices) and write them via prepared CQL statements without materializing the entire CSV DataFrame in memory

### Requirement: MongoDB `households` 2,500-Document Aggregation with Cutoff Support
The `basketlens.ingestion.mongo_loader` module SHALL populate the `households` collection with all 2,500 households active up to `cutoff_day` (default `711` for Mode A Full Ingestion, or `649` for Mode B Replay Checkpoint).

#### Scenario: Populating 2,500 household documents with polymorphic demographics and 5 recent baskets
- **WHEN** `ingest_mongo_households(cutoff_day=711)` is executed
- **THEN** the `households` collection MUST contain 2,500 documents where:
  1. Exactly 801 documents contain the nested `demographics` subdocument mapped from `hh_demographic.csv` (`classification_1..5`, `homeowner_desc`, `kid_category_desc`), while the remaining 1,699 documents omit the `demographics` field
  2. Each document contains `behavior_summary` (`total_spend`, `total_baskets`, `avg_basket_value`, `avg_weekly_spend`, `first_day`, `last_day`, `top_departments`, `top_commodities`, `updated_at`) computed from transactions with `DAY <= cutoff_day`
  3. Each document contains `recent_baskets` with at most the 5 most recent baskets (`DAY <= cutoff_day`), and each item inside `recent_baskets` embeds `department` and `commodity_desc` (*Extended Reference Pattern*)

### Requirement: Cassandra Four-Table Batched Ingestion with Cutoff Support
The `basketlens.ingestion.cassandra_loader` module SHALL populate `transactions_by_household`, `transactions_by_household_product`, `sales_by_product_week`, and `causal_promotions_by_store_week` for all records up to `cutoff_day` (and corresponding `cutoff_week`).

#### Scenario: Querying household #208 (John Smith) after Cassandra ingestion
- **WHEN** `ingest_cassandra_data(cutoff_day=711)` completes and `SELECT * FROM transactions_by_household WHERE household_key = 208 LIMIT 10` is executed
- **THEN** Cassandra MUST return John Smith's most recent transactions ordered by `week_no DESC, day DESC` without requiring `ALLOW FILTERING`

### Requirement: Redis Active Campaign & Coupon Ingestion with Vigency-Aligned TTL
The `basketlens.ingestion.redis_loader` module SHALL load campaigns active on `reference_day` (`START_DAY <= reference_day <= END_DAY`), their associated coupons, and household eligibility sets into Redis with TTL calculated as `max(1, (END_DAY - reference_day) * seconds_per_day)`.

#### Scenario: Loading active campaigns for `reference_day = 650` (John Smith Case Study)
- **WHEN** `ingest_redis_state(reference_day=650, seconds_per_day=5)` is executed
- **THEN** Campaign 22 (`START_DAY = 624`, `END_DAY = 656`) MUST exist in Redis at `campanha:22` with a positive TTL (`<= 30` seconds), `"22"` MUST be a member of `household:208:campaigns`, and expired campaigns (`END_DAY < 650`, such as Campaign 18 with `END_DAY = 642`) MUST NOT be loaded as active in Redis
