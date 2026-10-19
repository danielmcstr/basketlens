## ADDED Requirements

### Requirement: Official Dataset Schema Alignment in Draft Documentation
The system documentation (`docs/DRAFT.md`) SHALL accurately reflect the official schema from `docs/dunnhumby_The-Complete-Journey-User-Guide.pdf` and the local CSV files in `dataset/`, including anonymized demographic classifications, alphanumeric causal promotion codes, the 2,500-household MongoDB collection strategy, and the dual operational modes (Full Ingestion vs. Event Replay).

#### Scenario: Demographic columns match official PDF and CSV
- **WHEN** a developer or evaluator inspects Section 3.2 and Section 5.1 of `docs/DRAFT.md`
- **THEN** the documented `hh_demographic` attributes MUST list `classification_1`, `classification_2`, `classification_3`, `HOMEOWNER_DESC`, `classification_4`, `classification_5`, `KID_CATEGORY_DESC`, and `household_key`, along with their semantic meanings (`age_group`, `marital_code`, `income_level`, `homeowner_desc`, `household_size`, `hh_comp_group`, `kid_category_desc`) and the explanation that all 2,500 households are stored in MongoDB while only 801 include the `demographics` subdocument

#### Scenario: Causal promotion CQL types support alphanumeric codes
- **WHEN** a developer inspects Section 5.2 of `docs/DRAFT.md` for `causal_promotions_by_store_week`
- **THEN** `display_type` and `mailer_page` MUST be defined as CQL `text` (instead of `int`) so alphanumeric values such as `'A'`, `'D'`, and `'Z'` are valid

#### Scenario: Dual operational modes and local Docker + Polars streaming are documented
- **WHEN** a developer inspects Sections 4, 5, and 10 of `docs/DRAFT.md`
- **THEN** the document MUST describe the 100% local Docker Compose setup with dedicated Web UIs, the Polars streaming/batched ingestion rule (zero full-dataset in memory), and the two execution modes (Mode A: Full Historical Load up to Day 711; Mode B: Event Replay starting from `REFERENCE_DAY = 650` for case study `household_key = 208`)

### Requirement: Reproducible Python Package and Virtual Environment
The repository SHALL provide a PEP 621 `pyproject.toml` and a local `.venv` virtual environment containing pinned dependencies for Polars streaming, MongoDB, Cassandra, Redis, configuration management, Jupyter notebooks, and testing.

#### Scenario: Installing package in editable mode inside `.venv`
- **WHEN** the environment is initialized and `pip install -e ".[dev]"` is executed inside `.venv`
- **THEN** `import basketlens`, `import polars`, `import pymongo`, `import cassandra`, `import redis`, and `import pytest` MUST succeed without import errors

### Requirement: Typed Environment Configuration (`basketlens.config`)
The `basketlens.config` module SHALL expose a typed settings object (`Settings`) loaded from environment variables or a `.env` file, with sensible defaults matching the local Docker Compose services and the PDF case study (`REFERENCE_DAY = 650`).

#### Scenario: Default settings load without requiring a `.env` file
- **WHEN** `get_settings()` is called in an environment without overrides
- **THEN** it MUST return default connection parameters for local MongoDB (`localhost:27017`, database `basketlens`), local Cassandra (`localhost:9042`, keyspace `basketlens`), local Redis (`localhost:6379`), dataset directory (`dataset/`), `reference_day = 650`, `seconds_per_day = 5`, and `profile_ttl_seconds = 60`

#### Scenario: Environment variable override
- **WHEN** `BASKETLENS_REFERENCE_DAY=654` and `BASKETLENS_SECONDS_PER_DAY=10` are set in the environment
- **THEN** `get_settings()` MUST reflect `reference_day == 654` and `seconds_per_day == 10`
