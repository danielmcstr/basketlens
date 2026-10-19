# polyglot-connections-and-schemas Specification

## Purpose
Provide resilient client connection factories and health diagnostics (`basketlens.connections`) alongside declarative, idempotent schema and index provisioning (`basketlens.schemas`) for MongoDB `households` indexes, Apache Cassandra `basketlens` keyspace and 4 query-driven CQL tables, and Redis `object:id` namespace key builders.

## Requirements
### Requirement: Polyglot Database Connection Manager (`basketlens.connections`)
The `basketlens.connections` module SHALL provide factory functions and healthcheck helpers to establish connections to MongoDB (`pymongo.MongoClient`), Apache Cassandra (`cassandra.cluster.Cluster` / `Session`), and Redis (`redis.Redis` with `decode_responses=True`).

#### Scenario: Healthcheck verifies connectivity across all three databases
- **WHEN** `check_all_connections()` is invoked while the Docker Compose stack is healthy
- **THEN** it MUST return a status dictionary reporting `{"mongodb": True, "cassandra": True, "redis": True}` after executing a ping/heartbeat on each engine

### Requirement: Idempotent MongoDB Collection and Index Provisioning
The `basketlens.schemas.mongo_schema` module SHALL create and verify indexes on the `households` collection without failing if they already exist, and expose a helper to inspect query plans via `explain("executionStats")`.

#### Scenario: Creating required indexes on `households`
- **WHEN** `ensure_mongo_indexes(db)` is executed
- **THEN** the `households` collection MUST have:
  1. A unique index on `{"household_key": 1}`
  2. A compound index on `{"demographics.classification_1": 1, "demographics.classification_3": 1}`
  3. A descending index on `{"behavior_summary.avg_weekly_spend": -1}`

### Requirement: Idempotent Cassandra Keyspace and Query-Driven Table Provisioning
The `basketlens.schemas.cassandra_schema` module SHALL create the `basketlens` keyspace (`SimpleStrategy`, `replication_factor = 1` by default) and the four query-driven tables (`transactions_by_household`, `transactions_by_household_product`, `sales_by_product_week`, and `causal_promotions_by_store_week`).

#### Scenario: Creating the four Cassandra CQL tables
- **WHEN** `ensure_cassandra_schema(session)` is executed
- **THEN** the `basketlens` keyspace MUST contain:
  1. `transactions_by_household` with `PRIMARY KEY ((household_key), week_no, day, basket_id, product_id)` and `CLUSTERING ORDER BY (week_no DESC, day DESC)`
  2. `transactions_by_household_product` with `PRIMARY KEY ((household_key, product_id), day, basket_id)`
  3. `sales_by_product_week` with `PRIMARY KEY ((product_id), week_no)`
  4. `causal_promotions_by_store_week` with `PRIMARY KEY ((store_id, week_no), product_id)` and `display_type text`, `mailer_page text`

### Requirement: Redis Key Namespace Helpers
The `basketlens.schemas.redis_schema` module SHALL define canonical key builders matching the course convention `object:id` (`campanha:{campaign}`, `cupom:{coupon_upc}`, `household:{household_key}:campaigns`, `household:{household_key}:coupons`, `profile:{household_key}`, `ranking:week:{week_no}`, `store:{store_id}:week:{week_no}:displays`).

#### Scenario: Generating canonical Redis keys
- **WHEN** the key builder functions are called for `household_key = 208`, `campaign = 22`, and `coupon_upc = "51800000050"`
- **THEN** they MUST return `"profile:208"`, `"household:208:campaigns"`, `"campanha:22"`, and `"cupom:51800000050"`
