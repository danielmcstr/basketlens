# architecture-and-critical-analysis-doc Specification

## Purpose
Provide formal documentation of the BasketLens polyglot architecture (`docs/ARCHITECTURE.md`) and empirical business answers (`docs/BUSINESS_ANSWERS.md`) covering modeling justifications, CAP/consistency decisions, graph database critical analysis (Neo4j), and Kubernetes production evolution.

## Requirements
### Requirement: Complete Polyglot Architecture & Critical Analysis Document (`docs/ARCHITECTURE.md`)
The repository SHALL include `docs/ARCHITECTURE.md` covering the Class 6 and Class 8 architecture and critical analysis rubric items.

#### Scenario: Document contains all required architectural justifications and diagrams
- **WHEN** an evaluator reviews `docs/ARCHITECTURE.md`
- **THEN** it MUST contain:
  1. Architecture diagrams for the Polyglot 360º stack and the Dual Operational Modes (**Mode A: Full Historical Load** vs. **Mode B: Daily Event Replay**)
  2. Modeling justification for MongoDB (`households` schema, Subset Pattern, Extended Reference Pattern, Polymorphic Schema across 2,500 households, and index strategy)
  3. Modeling justification for Cassandra (partition keys, clustering keys, clustering order, and `ALLOW FILTERING` anti-pattern avoidance for all 4 CQL tables)
  4. Modeling justification for Redis (key naming convention, Cache-Aside lifecycle with `DEL` invalidation, and dynamic TTL formula aligned with campaign validity)
  5. CAP theorem and tunable consistency decision matrix (`CP` vs. `AP`, `ONE` vs. `QUORUM`)
  6. Critical Analysis answering *"Onde entraria um grafo?"* (Neo4j node/edge schema and why the 3 mandatory questions are aggregation/key-lookup rather than graph traversal) plus production evolution on Kubernetes

### Requirement: Business Questions & Evidence Document (`docs/BUSINESS_ANSWERS.md`)
The repository SHALL include `docs/BUSINESS_ANSWERS.md` presenting the empirical answers, queries, and execution proofs for all mandatory and bonus business questions.

#### Scenario: Document presents verified empirical outputs for the three mandatory questions
- **WHEN** an evaluator reviews `docs/BUSINESS_ANSWERS.md`
- **THEN** it MUST include:
  1. **Question 1**: Profile and recent purchase history for `household_key = 208` (John Smith), MongoDB `explain("executionStats")` output, and Cache-Aside latency comparison
  2. **Question 2**: Active campaigns and coupons in Redis at `REFERENCE_DAY = 650` (and behavior across Days 650–657 during Event Replay)
  3. **Question 3**: Average weekly spend tables across the 801 demographic households grouped by `classification_1` (Age Group) and `classification_3` (Income/Socioeconomic Level)
  4. **Bonus Trade Marketing**: Display and mailer promotional lift analysis on `causal_data` (including product `72717`)
