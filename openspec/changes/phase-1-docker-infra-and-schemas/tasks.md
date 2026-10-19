## 1. Infraestrutura Docker Compose com Versões Pinadas e Web UIs

- [x] 1.1 Criar `docker-compose.yml` com os serviços `mongo:8.0.4` (`27017`), `cassandra:5.0.2` (`9042`, com heap ajustado e healthcheck CQL) e `redis:7.4.2-alpine` (`6379`), volumes nomeados e rede dedicada
- [x] 1.2 Adicionar ao `docker-compose.yml` as 3 interfaces gráficas pré-configuradas: `mongo-express:1.0.2-20-alpine3.19` (`8081`), `delermando/cassandra-web:0.4.0` (`3000`) e `rediscommander/redis-commander:latest` (`8082`) dependentes do healthcheck de seus respectivos bancos
- [x] 1.3 Subir os containers (`docker compose up -d`) e verificar que os 3 bancos ficam `healthy` e as 3 Web UIs respondem via HTTP

## 2. Gerenciador de Conexões Poliglota (`src/basketlens/connections.py`)

- [x] 2.1 Implementar `get_mongo_client()`, `get_mongo_db()`, `get_cassandra_cluster_and_session()` (com retry/backoff) e `get_redis_client()` em `src/basketlens/connections.py`
- [x] 2.2 Implementar `check_all_connections()` para testar conectividade dos 3 bancos e retornar diagnóstico estruturado

## 3. Schemas, Índices e Keyspace (`src/basketlens/schemas/`)

- [x] 3.1 Implementar `src/basketlens/schemas/mongo_schema.py` com `ensure_mongo_indexes(db)` (criando índices em `household_key`, `demographics.classification_1` + `demographics.classification_3` e `behavior_summary.avg_weekly_spend`) e helper `explain_query(collection, filter_doc)`
- [x] 3.2 Implementar `src/basketlens/schemas/cassandra_schema.py` com `ensure_cassandra_schema(session)` criando o keyspace `basketlens` e as 4 tabelas CQL (`transactions_by_household`, `transactions_by_household_product`, `sales_by_product_week`, `causal_promotions_by_store_week` com `display_type text` e `mailer_page text`)
- [x] 3.3 Implementar `src/basketlens/schemas/redis_schema.py` com construtores padronizados de chaves (`campanha:{id}`, `cupom:{upc}`, `household:{id}:campaigns`, `household:{id}:coupons`, `profile:{id}`, `ranking:week:{w}`, `store:{id}:week:{w}:displays`) e helper de limpeza por namespace
- [x] 3.4 Criar `src/basketlens/schemas/__init__.py` expondo `initialize_all_schemas()` para provisionar MongoDB e Cassandra em uma única chamada

## 4. Verificação Automatizada da Infraestrutura e Schemas

- [x] 4.1 Criar `tests/test_connections_and_schemas.py` validando conexões aos 3 containers, existência dos 3 índices no MongoDB, existência das 4 tabelas CQL no keyspace `basketlens` do Cassandra e geração/operação de chaves no Redis
- [ ] 4.2 Executar `pytest tests/test_connections_and_schemas.py` contra a stack Docker Compose ativa
