## ADDED Requirements

### Requirement: Integrated 360º View with Cache-Aside (`build_360_view`)
The `basketlens.queries.view_360` module SHALL provide `build_360_view(household_key, limit_transactions=50, use_cache=True)` combining Redis (Cache-Aside for the MongoDB profile + active campaigns/coupons with `TTL > 0`), MongoDB (`households` fallback on cache miss), and Cassandra (`transactions_by_household`).

#### Scenario: Cache miss followed by cache hit and invalidation
- **WHEN** `build_360_view(208)` is called for the first time after cache clear
- **THEN** it MUST read the profile from MongoDB (`cache_hit = False`), store the serialized profile at `profile:208` in Redis with `SETEX`, fetch the latest transactions from Cassandra `transactions_by_household`, and return active campaigns whose `TTL > 0`; a subsequent call before TTL expiry MUST return `cache_hit = True` from Redis

### Requirement: Business Question 1 — Household Profile and Recent History
The `basketlens.queries.business_questions` module SHALL provide `get_household_profile_and_recent_history(household_key, limit=50)` returning the household's demographic/behavioral profile from MongoDB and recent item-level transactions from Cassandra without loading any CSV or full table into memory.

#### Scenario: Querying John Smith (`household_key = 208`)
- **WHEN** `get_household_profile_and_recent_history(208, limit=20)` is called
- **THEN** it MUST return the `households` document for `208` (including `behavior_summary` and `recent_baskets`) and up to 20 rows from Cassandra `transactions_by_household` ordered by `week_no DESC, day DESC`

### Requirement: Business Question 2 — Active Campaigns and Coupons Now
The `basketlens.queries.business_questions` module SHALL provide `get_active_campaigns_for_household(household_key)` querying Redis sets (`household:{id}:campaigns` and `household:{id}:coupons`) and filtering by `TTL > 0` on `campanha:{id}`.

#### Scenario: Returning active campaigns with live TTL metadata
- **WHEN** `get_active_campaigns_for_household(208)` is called while `reference_day = 650` state is loaded in Redis
- **THEN** it MUST return Campaign 22 (`DESCRIPTION = "TypeB"`, `START_DAY = 624`, `END_DAY = 656`), its remaining `ttl_seconds > 0`, and the list of redeemable coupons for that campaign

### Requirement: Business Question 3 — Average Weekly Spend by Demographic Segment
The `basketlens.queries.business_questions` module SHALL provide `get_avg_weekly_spend_by_demographic(group_by_field="classification_1")` computing average weekly spend across the 801 households with demographic records by querying Cassandra per partition (`WHERE household_key = ?`) and joining in Python memory only the aggregated household metrics with MongoDB's indexed `demographics` projection.

#### Scenario: Aggregating weekly spend by `classification_1` (Age Group) and `classification_3` (Income/Socioeconomic Level)
- **WHEN** `get_avg_weekly_spend_by_demographic("classification_1")` and `get_avg_weekly_spend_by_demographic("classification_3")` are executed
- **THEN** they MUST return an ordered table of demographic groups with `household_count`, `total_spend`, `total_active_weeks`, and `avg_weekly_spend` covering only the 801 demographic households and executing zero `ALLOW FILTERING` queries in Cassandra

### Requirement: Bonus Trade Marketing Display & Mailer Lift Query
The `basketlens.queries.business_questions` module SHALL provide `get_product_causal_promotion_lift(product_id)` combining `sales_by_product_week` and `causal_promotions_by_store_week` in Cassandra to compare weekly sales in weeks with display/mailer promotions versus baseline weeks.

#### Scenario: Analyzing promotional lift for product `72717` (from the PDF Case Study)
- **WHEN** `get_product_causal_promotion_lift(72717)` is executed
- **THEN** it MUST return weekly sales metrics juxtaposed with store display and mailer codes from Cassandra
