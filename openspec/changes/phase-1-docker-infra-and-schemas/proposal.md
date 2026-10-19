## Why

Para executar os pipelines de ingestão e consulta poliglota de forma 100% reprodutível sem esbarrar nos limites de armazenamento das camadas gratuitas em nuvem (512 MB no Atlas M0 e 30 MB no Redis Cloud), precisamos de uma infraestrutura local em Docker Compose com versões pinadas do MongoDB, Apache Cassandra e Redis, acompanhada de interfaces gráficas dedicadas (Web UIs) pré-configuradas e de um módulo Python de conexão e provisionamento de schemas/índices.

## What Changes

- **Infraestrutura Docker Compose (`docker-compose.yml`)**:
  - **MongoDB (`mongo:8.0.4`)** na porta `27017` com *healthcheck* e volume persistente + **UI (`mongo-express:1.0.2-20-alpine3.19`)** na porta `8081` pré-conectada.
  - **Apache Cassandra (`cassandra:5.0.2`)** na porta `9042` com *heap* ajustado para ambiente local, *healthcheck* via `cqlsh` e volume persistente + **UI (`delermando/cassandra-web:0.4.0`)** na porta `3000` pré-conectada ao cluster e keyspace.
  - **Redis (`redis:7.4.2-alpine`)** na porta `6379` com persistência leve e *healthcheck* via `redis-cli ping` + **UI (`rediscommander/redis-commander:latest`)** na porta `8082` pré-conectada.
- **Gerenciador de Conexões Poliglota (`src/basketlens/connections.py`)**:
  - Fábricas e gerenciadores de contexto para `MongoClient`, `cassandra.cluster.Session` e `redis.Redis` (com `decode_responses=True`), além de função `check_all_connections()` para diagnóstico imediato dos 3 bancos.
- **Provisionamento Declarativo de Schemas e Índices (`src/basketlens/schemas/`)**:
  - `src/basketlens/schemas/mongo_schema.py`: criação idempotente dos índices da coleção `households` (`household_key` único, índice composto em `demographics.classification_1` e `demographics.classification_3`, e índice decrescente em `behavior_summary.avg_weekly_spend`).
  - `src/basketlens/schemas/cassandra_schema.py`: criação idempotente do keyspace `basketlens` (`SimpleStrategy`, `replication_factor = 1` no ambiente local) e das 4 tabelas orientadas à consulta:
    1. `transactions_by_household` (`PRIMARY KEY ((household_key), week_no, day, basket_id, product_id)` com `CLUSTERING ORDER BY (week_no DESC, day DESC)`);
    2. `transactions_by_household_product` (`PRIMARY KEY ((household_key, product_id), day, basket_id)`);
    3. `sales_by_product_week` (`PRIMARY KEY ((product_id), week_no)`);
    4. `causal_promotions_by_store_week` (`PRIMARY KEY ((store_id, week_no), product_id)`, com `display_type text` e `mailer_page text`).
  - `src/basketlens/schemas/redis_schema.py`: constantes de prefixos de chaves (`campanha:{id}`, `cupom:{upc}`, `household:{id}:campaigns`, `household:{id}:coupons`, `profile:{id}`, `ranking:week:{w}`, `store:{id}:week:{w}:displays`) e utilitários de limpeza seletiva por namespace.
- **Fora de escopo nesta fase (Out of Scope)**:
  - Leitura e carga dos arquivos CSV via Polars (Fase 2);
  - Motor de Event Replay e biblioteca de consultas de negócio (Fase 3).

## Capabilities

### New Capabilities
- `docker-polyglot-infra`: Orquestração local via `docker-compose.yml` com versões pinadas do MongoDB, Cassandra e Redis, *healthchecks* e 3 Web UIs pré-conectadas.
- `polyglot-connections-and-schemas`: Clientes de conexão resilientes (`connections.py`) e provisionamento idempotente de índices no MongoDB, Keyspace/Tabelas CQL no Cassandra e convenções de chaves no Redis (`schemas/`).

### Modified Capabilities
<!-- Nenhuma capability existente modificada. -->

## Impact

- Infraestrutura: `docker-compose.yml`.
- Código-fonte: `src/basketlens/connections.py`, `src/basketlens/schemas/__init__.py`, `src/basketlens/schemas/mongo_schema.py`, `src/basketlens/schemas/cassandra_schema.py`, `src/basketlens/schemas/redis_schema.py`.
- Testes: `tests/test_connections_and_schemas.py`.
