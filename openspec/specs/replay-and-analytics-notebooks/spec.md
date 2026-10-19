# replay-and-analytics-notebooks Specification

## Purpose
Provide executed Jupyter notebooks (`notebooks/03_event_replay_streaming.ipynb` and `notebooks/04_polyglot_360_analytics.ipynb`) demonstrating day-by-day operational Event Replay (Mode B) and the polyglot Customer 360º analytics & business question answers.

## Requirements
### Requirement: Event Replay Streaming Notebook (`03_event_replay_streaming.ipynb`)
The repository SHALL include `notebooks/03_event_replay_streaming.ipynb` demonstrating Mode B (day-to-day operational simulation) from Day 649 through Day 657.

#### Scenario: Live demonstration of John Smith (#208) checkout, coupon redemption, cache invalidation, and TTL expiry
- **WHEN** `notebooks/03_event_replay_streaming.ipynb` is executed
- **THEN** it MUST demonstrate:
  1. Baseline initialization at Day 649
  2. Day-by-day replay from Day 650 to Day 656 showing active campaign TTL countdown in Redis
  3. John Smith (`household_key = 208`) purchasing on Day 654 and redeeming coupon `51800000050`, triggering `$slice: -5` update on `recent_baskets` in MongoDB, CQL insert in Cassandra, and `DEL profile:208` cache invalidation in Redis
  4. Automatic expiration of Campaign 22 after Day 656

### Requirement: Polyglot 360º Analytics Notebook (`04_polyglot_360_analytics.ipynb`)
The repository SHALL include `notebooks/04_polyglot_360_analytics.ipynb` executing `build_360_view` and answering all three mandatory business questions plus the Trade Marketing bonus queries.

#### Scenario: Notebook outputs structured answers and latency metrics for all rubric questions
- **WHEN** `notebooks/04_polyglot_360_analytics.ipynb` is executed
- **THEN** it MUST display the complete 360º view for `household_key = 208`, benchmark Cache-Miss vs. Cache-Hit latency on `profile:208`, present the results of Business Questions 1, 2, and 3 (by `classification_1` and `classification_3`), and show the Trade Marketing display/mailer lift analysis
