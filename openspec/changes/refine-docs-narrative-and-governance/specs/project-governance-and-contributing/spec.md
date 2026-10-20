## ADDED Requirements

### Requirement: Extension and Testing Guide (`CONTRIBUTING.md`)
The repository SHALL provide a `CONTRIBUTING.md` file documenting how to run the automated test suite (`pytest`), the modular structure of `src/basketlens/`, and the technical invariants required when extending the project.

#### Scenario: Developer inspects `CONTRIBUTING.md` to extend or validate the project
- **WHEN** a contributor or evaluator reads `CONTRIBUTING.md`
- **THEN** it MUST document `.venv/bin/pytest -v`, the responsibilities of `basketlens.connections`, `basketlens.schemas`, `basketlens.ingestion`, `basketlens.replay`, and `basketlens.queries`, and the architectural constraints (*Zero Full-Dataset In-Memory* with Polars, zero `ALLOW FILTERING` in Cassandra, indexed queries in MongoDB, and dynamic TTL / Cache-Aside invalidation in Redis)

### Requirement: Non-Commercial Educational License (`LICENSE` and `pyproject.toml`)
The repository SHALL provide a root `LICENSE` file and matching `pyproject.toml` metadata declaring strictly educational, academic, and scientific use (non-commercial) and including the official *dunnhumby — The Complete Journey* attribution.

#### Scenario: Evaluator checks repository licensing and dataset attribution
- **WHEN** `LICENSE` and `pyproject.toml` are inspected
- **THEN** `LICENSE` MUST state that commercial use is not authorized (strictly didactic/academic use) and include the official dunnhumby source citation (`https://www.dunnhumby.com/source-files/`), and `pyproject.toml` MUST NOT declare a commercial/permissive `MIT` license
