# docker-polyglot-infra Specification

## Purpose
Provide a reproducible, 100% local Docker Compose infrastructure with pinned container versions for MongoDB (`mongo:8.0.4`), Apache Cassandra (`cassandra:5.0.2`), and Redis (`redis:7.4.2-alpine`), alongside pre-configured dedicated Web UIs (`mongo-express`, `cassandra-web`, and `redis-commander`) and explicit service healthchecks.

## Requirements
### Requirement: Pinned Local Docker Compose for MongoDB, Cassandra, and Redis
The repository SHALL provide a `docker-compose.yml` file at the project root that launches pinned container images for MongoDB (`mongo:8.0.4`), Apache Cassandra (`cassandra:5.0.2`), and Redis (`redis:7.4.2-alpine`), each configured with persistent named volumes and explicit healthchecks.

#### Scenario: All three database containers become healthy
- **WHEN** `docker compose up -d` is executed from the repository root
- **THEN** the `basketlens-mongo`, `basketlens-cassandra`, and `basketlens-redis` containers MUST transition to `healthy` status and listen on local ports `27017`, `9042`, and `6379` respectively

### Requirement: Dedicated Pre-Configured Web UIs for Each Database
The `docker-compose.yml` file SHALL include three dedicated Web UI services (`mongo-express`, `cassandra-web`, and `redis-commander`) pre-configured to connect automatically to their respective database containers once healthy.

#### Scenario: Web UIs are accessible on local HTTP ports
- **WHEN** the Docker Compose stack is up and healthy
- **THEN** `mongo-express` MUST respond on `http://localhost:8081`, `cassandra-web` MUST respond on `http://localhost:3000`, and `redis-commander` MUST respond on `http://localhost:8082` without requiring manual host/port setup in the browser
