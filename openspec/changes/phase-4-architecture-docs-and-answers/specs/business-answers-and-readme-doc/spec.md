## ADDED Requirements

### Requirement: Comprehensive Repository Guide (`README.md`)
The repository SHALL provide a complete `README.md` with setup instructions, architecture overview, Web UI URLs, dual operational mode workflows, notebook descriptions, and official dunnhumby dataset citation.

#### Scenario: Developer follows `README.md` to run the project end-to-end
- **WHEN** a user reads `README.md`
- **THEN** it MUST document the exact commands to start the Docker Compose stack, access `mongo-express` (`:8081`), `cassandra-web` (`:3000`), and `redis-commander` (`:8082`), activate `.venv`, run the 4 Jupyter notebooks (`01` through `04`), and execute `pytest`
