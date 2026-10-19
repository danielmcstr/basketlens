## 1. Motor de Event Replay Operacional (`src/basketlens/replay/`)

- [x] 1.1 Implementar `prepare_replay_baseline(cutoff_day=649)` em `src/basketlens/replay/engine.py` preparando o estado inicial dos 3 bancos até a véspera do replay
- [x] 1.2 Implementar `replay_day(day, seconds_per_day=5)` extraindo apenas os eventos de `DAY == day` via Polars `scan_csv()` e aplicando: (a) rotação de campanhas/cupons e TTL no Redis, (b) inserção CQL no Cassandra, (c) atualização incremental `$inc` e `$push` com `$slice: -5` em `recent_baskets` no MongoDB e (d) invalidação de cache `DEL profile:{id}` no Redis
- [x] 1.3 Implementar `replay_range(start_day, end_day, seconds_per_day, sleep_between_days)` gerando telemetria detalhada dia a dia (incluindo rastreamento explícito de `household_key = 208`)

## 2. Biblioteca de Consulta Poliglota (`src/basketlens/queries/`)

- [x] 2.1 Implementar `build_360_view(household_key, limit_transactions=50, use_cache=True)` em `src/basketlens/queries/view_360.py` com Cache-Aside no Redis (`GET profile:{id}` -> MongoDB fallback -> `SETEX`), consulta de histórico recente no Cassandra e campanhas ativas com `TTL > 0`
- [x] 2.2 Implementar em `src/basketlens/queries/business_questions.py` as funções para a **Pergunta 1** (`get_household_profile_and_recent_history` + `get_household_product_history`) e para a **Pergunta 2** (`get_active_campaigns_for_household`)
- [x] 2.3 Implementar em `src/basketlens/queries/business_questions.py` a **Pergunta 3** (`get_avg_weekly_spend_by_demographic`) cruzando os 801 perfis demográficos do MongoDB (`classification_1` e `classification_3`) com consultas por chave de partição no Cassandra (sem `ALLOW FILTERING`)
- [x] 2.4 Implementar em `src/basketlens/queries/business_questions.py` as consultas bônus de Trade Marketing (`get_product_causal_promotion_lift` para o produto `72717` do PDF e `get_store_weekly_showcase`)

## 3. Notebooks de Event Replay (`03`) e Análises 360º (`04`) + Testes

- [x] 3.1 Construir `notebooks/03_event_replay_streaming.ipynb` demonstrando a operação dia a dia (Dias 650 a 657), a compra e resgate do cupom `51800000050` por John Smith (`208`) no Dia 654, a invalidação do cache `profile:208` e a expiração da Campanha 22
- [x] 3.2 Construir `notebooks/04_polyglot_360_analytics.ipynb` apresentando o `build_360_view(208)`, o benchmark de latência Cache-Miss vs. Cache-Hit e as respostas completas às 3 perguntas de negócio + bônus de Trade Marketing
- [x] 3.3 Criar `tests/test_replay_and_queries.py` validando o ciclo de Event Replay, o comportamento de Cache-Aside e as 3 perguntas de negócio
