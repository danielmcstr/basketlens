## Why

Com os 6,27 milhões de registros brutos da base *The Complete Journey* (~847 MB em disco), precisamos de um motor de ingestão e análise exploratória baseado em **Polars (`LazyFrame` / `scan_csv` / batches)** que processe os dados sem nunca carregar o dataset inteiro em memória RAM, populando MongoDB, Cassandra e Redis com suporte tanto ao **Modo A (Ingestão Completa até o Dia 711)** quanto ao **Checkpoint Base para o Modo B (corte parametrizável em `cutoff_day`, ex.: Dia 649)**.

## What Changes

- **Módulo de Ingestão Polars Out-of-Core (`src/basketlens/ingestion/`)**:
  - `src/basketlens/ingestion/mongo_loader.py`:
    - Agrega métricas comportamentais (`total_spend`, `total_baskets`, `avg_basket_value`, `avg_weekly_spend`, `first_day`, `last_day`, `top_departments`, `top_commodities`) usando `pl.scan_csv()` com filtro opcional `DAY <= cutoff_day` e `.collect(streaming=True)`.
    - Constrói o array `recent_baskets` contendo apenas as **últimas 5 cestas** por domicílio (*Subset Pattern*), enriquecendo cada item com `department` e `commodity_desc` de `product.csv` (*Extended Reference Pattern*).
    - Mescla com `hh_demographic.csv` (para os 801 domicílios com demografia) e `campaign_table.csv` (`campaigns_received`), gerando os **2.500 documentos** na coleção `households` via `bulk_write` em lotes (`ReplaceOne(..., upsert=True)`).
  - `src/basketlens/ingestion/cassandra_loader.py`:
    - Itera sobre `transaction_data.csv` (2,6M linhas) e `causal_data.csv` (3,68M linhas) em lotes controlados (`pl.read_csv_batched` / fatias por `WEEK_NO`) filtrando `DAY <= cutoff_day`.
    - Grava concorrentemente no Cassandra usando `PreparedStatement` + `execute_concurrent_with_args` nas 4 tabelas (`transactions_by_household`, `transactions_by_household_product`, `sales_by_product_week` e `causal_promotions_by_store_week`).
  - `src/basketlens/ingestion/redis_loader.py`:
    - Popula no Redis as campanhas ativas em `reference_day` (`START_DAY <= reference_day <= END_DAY`), seus cupons e os conjuntos de elegibilidade por domicílio (`household:{id}:campaigns` e `household:{id}:coupons`), aplicando **TTL** proporcional à vigência restante `max(1, (END_DAY - reference_day) * seconds_per_day)`.
    - Popula o ranking semanal (`ranking:week:{w}`) e vitrines físicas (`store:{id}:week:{w}:displays`) da semana correspondente ao `reference_day`.
  - `src/basketlens/ingestion/pipeline.py`:
    - Orquestrador `run_full_ingestion(cutoff_day=711, reference_day=650, include_causal=True)` que permite carregar a base completa (Modo A) ou preparar o estado inicial até `cutoff_day=649` para o Event Replay (Modo B).
- **Notebooks Jupyter de EDA e Ingestão Completa**:
  - `notebooks/01_eda_and_data_quality.ipynb`: Análise exploratória 100% *out-of-core* com Polars `scan_csv`, provando as 4 armadilhas do dataset, as fórmulas de preço do PDF (pág. 3) e a jornada do cliente `household_key = 208` (John Smith).
  - `notebooks/02_full_ingestion_setup.ipynb`: Execução guiada do Modo A (Ingestão Completa Tier 2), monitoramento de tempo/memória, verificação de contagens nos 3 bancos e prova de uso de índices no MongoDB via `explain("executionStats")`.
- **Fora de escopo nesta fase (Out of Scope)**:
  - Motor de Event Replay incremental dia-a-dia e biblioteca de consultas analíticas 360º (Fase 3).

## Capabilities

### New Capabilities
- `polars-streaming-ingestion`: Pipelines de ingestão *out-of-core* e em lotes com Polars para MongoDB (`households` com 2.500 documentos), Cassandra (4 tabelas CQL sem full-scan) e Redis (campanhas/cupons com TTL baseado em `reference_day`), suportando `cutoff_day` configurável.
- `eda-and-ingestion-notebooks`: Notebooks interativos `01_eda_and_data_quality.ipynb` e `02_full_ingestion_setup.ipynb` demonstrando a análise exploratória lazy e a carga completa Tier 2.

### Modified Capabilities
<!-- Nenhuma capability existente modificada. -->

## Impact

- Código-fonte: `src/basketlens/ingestion/__init__.py`, `src/basketlens/ingestion/mongo_loader.py`, `src/basketlens/ingestion/cassandra_loader.py`, `src/basketlens/ingestion/redis_loader.py`, `src/basketlens/ingestion/pipeline.py`.
- Notebooks: `notebooks/01_eda_and_data_quality.ipynb`, `notebooks/02_full_ingestion_setup.ipynb`.
- Testes: `tests/test_ingestion.py`.
