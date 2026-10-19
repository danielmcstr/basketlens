## ADDED Requirements

### Requirement: Out-of-Core Exploratory Data Analysis Notebook (`01_eda_and_data_quality.ipynb`)
The repository SHALL include `notebooks/01_eda_and_data_quality.ipynb` performing exploratory data analysis on `dataset/*.csv` using Polars `scan_csv()` lazy queries.

#### Scenario: Notebook demonstrates the 4 dataset traps and John Smith (#208) case study
- **WHEN** `notebooks/01_eda_and_data_quality.ipynb` is executed
- **THEN** it MUST display:
  1. File sizes and row counts confirming `causal_data.csv` represents ~82% of uncompressed volume
  2. Coverage comparison showing 2,500 distinct `household_key` values in `transaction_data.csv` vs. 801 in `hh_demographic.csv`
  3. Price calculation examples applying the official PDF formulas (`Loyalty card price` vs. `Non-loyalty price`)
  4. The complete campaign and coupon redemption timeline of `household_key = 208` (John Smith) matching pages 7–9 of the official PDF

### Requirement: Full Ingestion Setup & Index Verification Notebook (`02_full_ingestion_setup.ipynb`)
The repository SHALL include `notebooks/02_full_ingestion_setup.ipynb` executing the Mode A Full Historical Load (Tier 2) and verifying database state and index usage.

#### Scenario: Notebook executes full ingestion and validates MongoDB `explain("executionStats")`
- **WHEN** `notebooks/02_full_ingestion_setup.ipynb` is executed against the running Docker Compose stack
- **THEN** it MUST provision schemas, run the Polars ingestion pipeline for MongoDB, Cassandra, and Redis, report row/document counts across all three engines, and display the `explain("executionStats")` output proving `IXSCAN` (and zero `COLLSCAN`) on `households`
