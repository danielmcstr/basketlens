## 1. Módulo de Ingestão Polars para o MongoDB (`src/basketlens/ingestion/mongo_loader.py`)

- [x] 1.1 Implementar o cálculo *out-of-core* de `behavior_summary` (`total_spend`, `total_baskets`, `avg_basket_value`, `avg_weekly_spend`, `first_day`, `last_day`, `top_departments`, `top_commodities`) com `pl.scan_csv` e `.collect(streaming=True)` suportando `cutoff_day`
- [x] 1.2 Implementar a extração das 5 últimas cestas por domicílio (`recent_baskets` — *Subset Pattern*) com enriquecimento de `department` e `commodity_desc` via `product.csv` (*Extended Reference Pattern*)
- [x] 1.3 Implementar a fusão com `hh_demographic.csv` (adicionando `demographics` nos 801 domicílios cadastrados e omitindo nos 1.699 demais) e `campaign_table.csv` (`campaigns_received`), gravando os 2.500 documentos em lotes via `bulk_write`

## 2. Módulo de Ingestão Polars em Lotes para o Cassandra (`src/basketlens/ingestion/cassandra_loader.py`)

- [x] 2.1 Implementar a ingestão paginada (`pl.read_csv_batched`) de `transaction_data.csv` (filtrando `DAY <= cutoff_day`) com `PreparedStatement` + `execute_concurrent_with_args` para `transactions_by_household` e `transactions_by_household_product`
- [x] 2.2 Implementar a agregação streaming por `(product_id, week_no)` e carga em lotes na tabela `sales_by_product_week`
- [x] 2.3 Implementar a ingestão paginada (`pl.read_csv_batched`) de `causal_data.csv` (filtrando `WEEK_NO <= cutoff_week`) na tabela `causal_promotions_by_store_week` com `display_type` e `mailer_page` como `text`

## 3. Módulo de Ingestão de Vigência e TTL para o Redis (`src/basketlens/ingestion/redis_loader.py`)

- [x] 3.1 Implementar a carga de campanhas vigentes em `reference_day` (`START_DAY <= reference_day <= END_DAY`) com `HSET campanha:{id}` e `EXPIRE` proporcional a `(END_DAY - reference_day) * seconds_per_day`
- [x] 3.2 Implementar a carga de cupons ativos (`cupom:{upc}`) e dos conjuntos de elegibilidade por domicílio (`household:{id}:campaigns` e `household:{id}:coupons`) via `redis.pipeline()`
- [x] 3.3 Implementar a carga de destaques semanais (`ranking:week:{w}` e `store:{id}:week:{w}:displays`) e criar o orquestrador `src/basketlens/ingestion/pipeline.py`

## 4. Notebooks de EDA (`01`) e Ingestão Completa (`02`) + Testes

- [x] 4.1 Construir `notebooks/01_eda_and_data_quality.ipynb` com Polars `scan_csv`, demonstrando as 4 armadilhas da base, as fórmulas de preço do PDF oficial e o estudo de caso `household_key = 208` (John Smith)
- [x] 4.2 Construir `notebooks/02_full_ingestion_setup.ipynb` executando a carga completa Tier 2 (Modo A), exibindo contagens nos 3 bancos e validando os índices do MongoDB com `explain("executionStats")`
- [x] 4.3 Criar `tests/test_ingestion.py` validando a integridade dos documentos `households` (incluindo `household_key = 208`), registros no Cassandra e TTLs no Redis
