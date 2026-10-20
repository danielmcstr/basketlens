## MODIFIED Requirements

### Requirement: Complete Polyglot Architecture & Critical Analysis Document (`docs/ARCHITECTURE.md`)
The repository SHALL include `docs/ARCHITECTURE.md` structured as a clear, didactic, non-repetitive narrative covering the Class 6 and Class 8 architecture, domain nuances, modeling justifications, CAP/consistency decisions, and critical analysis rubric items.

#### Scenario: Document contains all required architectural justifications, domain nuances, and SVG diagrams without repetition
- **WHEN** an evaluator reviews `docs/ARCHITECTURE.md`
- **THEN** it MUST contain:
  1. The 4 standardized SVG architecture diagrams (`assets/arch-polyglot-overview.svg`, `assets/arch-operational-modes.svg`, `assets/arch-neo4j-graph.svg`, and `assets/arch-kubernetes-production.svg`) without duplicate `mermaid` blocks
  2. The 3 physical domain nuances of *dunnhumby — The Complete Journey* (volume asymmetry & *Zero Full-Dataset In-Memory* rule with Polars; partial demographic coverage of `801` out of `2,500` households plus alphanumeric `display`/`mailer` codes typed as `text`; and POS price/discount decomposition for `household_key = 208`)
  3. A unified polyglot rationale and CAP/tunable consistency decision matrix (`CP` vs. `AP`, `ONE` vs. `LOCAL_QUORUM` / `QUORUM`) eliminating duplicate tables
  4. Modeling justification for MongoDB (`households` schema, Subset Pattern with `$slice: -5`, Extended Reference Pattern, Polymorphic Schema across 2,500 households, Computed Pattern, and 3 B-Tree indexes)
  5. Modeling justification for Cassandra (partition keys, clustering keys, descending clustering order, and `ALLOW FILTERING` anti-pattern avoidance across all 4 CQL tables)
  6. Modeling justification for Redis (canonical key naming convention, Cache-Aside lifecycle with `DEL` invalidation, and dynamic `TTL` formula aligned with campaign validity)
  7. Operational duality between **Modo A (Batch)** and **Modo B (Event Replay)** across `DAY 649..657`
  8. Critical Analysis answering *"Onde entraria um grafo?"* (Neo4j property graph `BOUGHT_WITH` and why the 3 mandatory questions do not require graph traversal) and connecting local limitations directly to the Kubernetes production evolution (`K8ssandra`, `Strimzi Kafka`, `MongoDB Operator`, `Redis Cluster`, and `Argo Workflows`)
