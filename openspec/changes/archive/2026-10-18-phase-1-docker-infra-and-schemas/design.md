## Context

A Fase 1 constrói a fundação operacional sobre a qual os dados da base *The Complete Journey* serão ingeridos e consultados. O ambiente precisa rodar 100% localmente via Docker Compose com imagens pinadas para evitar variações entre máquinas dos integrantes do grupo e permitir inspeção visual imediata de cada banco durante o desenvolvimento e na apresentação da Aula 8.

## Goals / Non-Goals

**Goals:**
- Prover um `docker-compose.yml` com versões pinadas do MongoDB, Apache Cassandra e Redis + suas 3 Web UIs pré-conectadas.
- Configurar limites de memória da JVM do Cassandra (`MAX_HEAP_SIZE=1536M`, `HEAP_NEWSIZE=384M`) para que o container conviva bem com Mongo, Redis e Jupyter na mesma máquina local.
- Implementar `src/basketlens/connections.py` e `src/basketlens/schemas/` para conectar nos 3 bancos e criar de forma idempotente os índices do MongoDB e o Keyspace + 4 tabelas CQL do Cassandra.

**Non-Goals:**
- Não ingerir os arquivos CSV nesta fase (Fase 2).
- Não implementar consultas de negócio ou Event Replay nesta fase (Fase 3).

## Decisions

### 1. Imagens Docker Pinadas e Web UIs Dedicadas
- **MongoDB**: `mongo:8.0.4` (`27017`) + `mongo-express:1.0.2-20-alpine3.19` (`8081`).
  - *Racional:* `mongo-express` permite visualizar a estrutura aninhada de `households` (`demographics`, `behavior_summary`, `recent_baskets`) e os índices criados.
- **Apache Cassandra**: `cassandra:5.0.2` (`9042`) + `delermando/cassandra-web:0.4.0` (`3000`).
  - *Racional:* `cassandra-web` se conecta automaticamente via variáveis `CASSANDRA_HOST` e `CASSANDRA_PORT`, permitindo navegar pelo keyspace `basketlens`, inspecionar o schema das 4 tabelas e rodar consultas CQL pelo navegador.
- **Redis**: `redis:7.4.2-alpine` (`6379`) + `rediscommander/redis-commander:latest` (`8082`).
  - *Racional:* `redis-commander` permite visualizar em árvore os namespaces (`campanha:*`, `cupom:*`, `household:*`, `profile:*`) e inspecionar o contador regressivo de **TTL** em tempo real.

### 2. Modelagem das Chaves Primárias no Cassandra (Evitando `ALLOW FILTERING`)
- **`transactions_by_household`**:
  - `PRIMARY KEY ((household_key), week_no, day, basket_id, product_id) WITH CLUSTERING ORDER BY (week_no DESC, day DESC, basket_id DESC, product_id ASC)`
  -Inclui `retail_disc`, `coupon_disc` e `coupon_match_disc` além de `quantity`, `sales_value`, `store_id` e `trans_time`, permitindo reconstruir cestas e calcular tanto receita líquida quanto preço pago pelo cliente.
- **`transactions_by_household_product`**:
  - `PRIMARY KEY ((household_key, product_id), day, basket_id) WITH CLUSTERING ORDER BY (day DESC, basket_id DESC)`
  - Demonstra por que filtrar por produto dentro de um domicílio requer outra tabela com chave de partição composta.
- **`sales_by_product_week`**:
  - `PRIMARY KEY ((product_id), week_no) WITH CLUSTERING ORDER BY (week_no DESC)`
  - Armazena `total_units bigint`, `total_sales decimal`, `total_baskets bigint` pré-agregados por produto e semana para cruzamento rápido com `causal_data` e rankings semanais.
- **`causal_promotions_by_store_week`**:
  - `PRIMARY KEY ((store_id, week_no), product_id)`
  - Colunas `display_type text` e `mailer_page text` para suportar os códigos alfanuméricos (`'0'..'9'`, `'A'`, `'D'`, `'Z'`).

### 3. Índices do MongoDB (`households`)
- `{ "household_key": 1 }` (`unique: True`) — busca direta O(log N) do perfil 360º.
- `{ "demographics.classification_1": 1, "demographics.classification_3": 1 }` — acelera a segmentação demográfica da Pergunta 3 (faixa etária × nível socioeconômico/renda).
- `{ "behavior_summary.avg_weekly_spend": -1 }` — acelera ordenação de clientes por gasto semanal médio.

## Risks / Trade-offs

- **[Risco] Tempo de inicialização do Cassandra (~30–60s)** → **Mitigação:** Configurar `healthcheck` com `cqlsh -e "describe keyspaces"` (`start_period: 45s`) e fazer `cassandra-web` depender de `service_healthy`, além de incluir *retry/backoff* em `connections.py`.
- **[Risco] `coupon_upc` exceder inteiro de 32 bits** (ex.: `10000089061`, `51800000050`) → **Mitigação:** Tratar `coupon_upc` sempre como `str` / `text` (ou `bigint`), nunca `int` de 32 bits, e `basket_id` como `bigint` (`26984851472`).
