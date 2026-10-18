## Context

A Fase 2 implementa o coração de engenharia de dados do **BasketLens**: o módulo `src/basketlens/ingestion/` baseado em **Polars** e os dois primeiros notebooks (`01_eda_and_data_quality.ipynb` e `02_full_ingestion_setup.ipynb`).

A restrição central desta fase é processar os ~6,27 milhões de registros (~847 MB) **sem nunca carregar `transaction_data.csv` ou `causal_data.csv` inteiros na memória RAM**, além de suportar um parâmetro `cutoff_day` para servir tanto ao **Modo A (Ingestão Completa: `cutoff_day = 711`)** quanto à preparação do **Modo B (Checkpoint antes do Event Replay: `cutoff_day = 649`)**.

## Goals / Non-Goals

**Goals:**
- Implementar pipelines Polars *lazy/streaming* e em lotes (`read_csv_batched`) para popular MongoDB, Cassandra e Redis.
- Suportar `cutoff_day` em todos os carregadores para permitir fotografias temporais exatas da base.
- Construir `notebooks/01_eda_and_data_quality.ipynb` (EDA) e `notebooks/02_full_ingestion_setup.ipynb` (Ingestão Completa + validação `explain`).

**Non-Goals:**
- Não implementar o loop incremental de Event Replay dia a dia nem a biblioteca de consultas 360º nesta fase (ambos pertencem à Fase 3).

## Decisions

### 1. Estratégia Polars Out-of-Core para o MongoDB (`mongo_loader.py`)
- **Agregação de `behavior_summary`**:
  - Usamos `pl.scan_csv("dataset/transaction_data.csv").filter(pl.col("DAY") <= cutoff_day)` combinado via *lazy join* com `pl.scan_csv("dataset/product.csv")` (apenas 92k linhas, ~6 MB).
  - Executamos agregações por `household_key` com `.collect(streaming=True)` para obter `total_spend`, `total_baskets` (`n_unique("BASKET_ID")`), `first_day`, `last_day`, `active_weeks` e `avg_weekly_spend` (`total_spend / active_weeks_or_span`), além do Top 3 de `DEPARTMENT` e `COMMODITY_DESC`.
  - O resultado agregado final tem apenas **2.500 linhas** (1 por domicílio), ocupando menos de 2 MB em memória.
- **Extração das 5 últimas cestas (`recent_baskets` — *Subset Pattern* + *Extended Reference*)**:
  - Primeiro identificamos via `scan_csv` os `BASKET_ID`s correspondentes às 5 cestas mais recentes (`sort_by(["DAY", "TRANS_TIME", "BASKET_ID"], descending=True).head(5)` por `household_key`). São no máximo `2.500 × 5 = 12.500` cestas.
  - Em seguida filtramos no `scan_csv("dataset/transaction_data.csv")` apenas os itens pertencentes a esses 12.500 `BASKET_ID`s, juntamos com `product.csv` para embutir `department` e `commodity_desc`, e montamos o array `recent_baskets` de cada documento.
- **Escrita em Lote (`bulk_write`)**:
  - Os 2.500 documentos são enviados ao MongoDB em lotes de 500 via `ReplaceOne({"household_key": doc["household_key"]}, doc, upsert=True)`.

### 2. Estratégia Polars Batched + Concorrência CQL para o Cassandra (`cassandra_loader.py`)
- **Leitura em Lotes (`pl.read_csv_batched`)**:
  - Lemos `transaction_data.csv` e `causal_data.csv` em lotes de `50.000` linhas via `pl.read_csv_batched()`.
  - Para cada lote, filtramos `DAY <= cutoff_day` (ou `WEEK_NO <= cutoff_week` no `causal_data`) e convertemos apenas o lote atual em tuplas para envio via `execute_concurrent_with_args(session, prepared_stmt, batch_params, concurrency=64)`.
- **Tabela `sales_by_product_week`**:
  - Pré-agregada via `pl.scan_csv("dataset/transaction_data.csv").filter(pl.col("DAY") <= cutoff_day).group_by(["PRODUCT_ID", "WEEK_NO"]).agg(...).collect(streaming=True)` e inserida em lotes de `10.000` linhas com `execute_concurrent_with_args`.

### 3. Estratégia de Vigência e TTL no Redis (`redis_loader.py`)
- Com base em `reference_day` (ex.: `650`) e `seconds_per_day` (ex.: `5` ou `60`):
  - Filtramos `campaign_desc.csv` onde `START_DAY <= reference_day <= END_DAY`.
  - Para cada campanha ativa, calculamos `ttl_seconds = max(1, (END_DAY - reference_day) * seconds_per_day)`.
  - Usamos `redis.pipeline()` para gravar `HSET campanha:{id}` + `EXPIRE campanha:{id} {ttl}`, os cupons da campanha (`HSET cupom:{upc}` + `EXPIRE`) e os conjuntos de elegibilidade dos domicílios (`SADD household:{h}:campaigns {id}`).
  - Aplicamos a regra da página 5 do PDF oficial: para campanhas `TypeB` e `TypeC`, todos os domicílios participantes recebem os cupons da campanha em `household:{h}:coupons`; para `TypeA`, os cupons ficam indexados no pool da campanha `campanha:{id}:coupons` e no domicílio elegível.

## Risks / Trade-offs

- **[Risco] Tempo de ingestão de 3,68M linhas de `causal_data.csv` no Cassandra local** → **Mitigação:** Usar `PreparedStatement` + `execute_concurrent_with_args(concurrency=64)` e permitir nos testes automatizados ou reexecuções rápidas parametrizar `include_causal: bool = True` ou filtrar janelas de semanas quando desejado, mantendo o Tier 2 completo no `02_full_ingestion_setup.ipynb`.
