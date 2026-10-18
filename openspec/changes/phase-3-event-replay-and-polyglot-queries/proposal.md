## Why

Além da carga histórica completa (Modo A), precisamos demonstrar como um time de engenharia de dados e operações mantém a arquitetura poliglota viva no dia a dia (**Modo B: Event Replay**) — com compras chegando dos PDVs, o Cassandra anexando os eventos colunares, o MongoDB atualizando o resumo e rotacionando as 5 últimas cestas (`$slice: -5`), e o Redis gerenciando TTLs de campanhas/cupons e invalidando o cache do perfil (`DEL profile:{id}`) — além de fornecer a **Biblioteca de Consulta Poliglota** que responde às 3 perguntas obrigatórias de negócio sem carregar o dataset em memória.

## What Changes

- **Motor de Operação Dia a Dia — Event Replay (`src/basketlens/replay/`)**:
  - `src/basketlens/replay/engine.py`:
    - `prepare_replay_baseline(cutoff_day=649)`: prepara o estado inicial dos 3 bancos até a véspera da janela de simulação.
    - `replay_day(day, seconds_per_day=5)`: simula um dia operacional completo lendo do disco apenas os eventos daquele `DAY` via Polars `pl.scan_csv().filter(pl.col("DAY") == day).collect(streaming=True)`:
      1. **Redis (Ciclo de Vida e TTL)**: atualiza o TTL das campanhas vigentes (`campanha:{id}`), ativa novas campanhas cujo `START_DAY == day`, expira campanhas encerradas (`END_DAY < day`) e processa os resgates de cupons do dia (`coupon_redempt.csv`, incluindo o resgate do cupom `51800000050` pelo cliente `208` no Dia 654).
      2. **Cassandra (Append Transacional)**: insere os itens comprados no `day` em `transactions_by_household` e `transactions_by_household_product` e atualiza o agregado da semana em `sales_by_product_week`.
      3. **MongoDB (Atualização Incremental de Documento)**: para cada domicílio que comprou no `day`, incrementa `behavior_summary.total_spend` e `total_baskets` (`$inc`), atualiza `last_day` / `avg_basket_value` e empurra as novas cestas em `recent_baskets` mantendo estritamente as 5 últimas (`$push` com `$each` e `$slice: -5`).
      4. **Redis (Invalidação de Cache-Aside)**: executa `DEL profile:{household_key}` para todos os domicílios que tiveram compras ou resgates no `day`, garantindo que a próxima chamada a `build_360_view` reflita o novo estado.
- **Biblioteca de Consulta Poliglota (`src/basketlens/queries/`)**:
  - Todas as consultas fazem *pushdown* aos bancos, trazendo para a memória apenas o resultado da consulta:
    - `src/basketlens/queries/view_360.py`: implementa `build_360_view(household_key, limit_transactions=50, use_cache=True)` costurando Redis (cache-aside `profile:{id}` + campanhas e cupons ativos com `TTL > 0`), MongoDB (`households` em caso de *cache miss*) e Cassandra (`transactions_by_household`).
    - `src/basketlens/queries/business_questions.py`:
      - **Pergunta 1 (`get_household_profile_and_recent_history`)**: perfil demográfico/comportamental (MongoDB) + histórico recente ordenado por `week_no DESC, day DESC` (Cassandra) + comparação de latência *Cache Miss vs. Cache Hit* (Redis).
      - **Pergunta 2 (`get_active_campaigns_for_household`)**: campanhas e cupons ativos agora para um domicílio no Redis (`SMEMBERS` + `TTL > 0` + metadados `HGETALL`), distinguindo campanhas `TypeA` vs `TypeB/C`.
      - **Pergunta 3 (`get_avg_weekly_spend_by_demographic`)**: gasto semanal médio por faixa demográfica (`classification_1` e `classification_3`), buscando os 801 perfis demográficos indexados no MongoDB e consultando por chave de partição no Cassandra sem `ALLOW FILTERING`.
      - **Consultas Bônus de Trade Marketing (`get_display_and_mailer_lift`, `get_store_weekly_showcase`)**: cruzamento de `causal_promotions_by_store_week` com `sales_by_product_week` (ex.: produto `72717` do estudo de caso do PDF) e vitrines ativas no Redis.
- **Notebooks Jupyter de Event Replay (`03`) e Análises 360º (`04`)**:
  - `notebooks/03_event_replay_streaming.ipynb`: demonstração passo a passo do Modo B (Dias 650 a 656), exibindo a jornada de John Smith (`household_key = 208`), o TTL caindo em tempo real, o resgate de cupom no Dia 654 e a invalidação automática do cache `profile:208`.
  - `notebooks/04_polyglot_360_analytics.ipynb`: demonstração executiva da Visão 360º e respostas completas às 3 perguntas obrigatórias + bônus de Trade Marketing.

## Capabilities

### New Capabilities
- `event-replay-engine`: Simulador operacional dia-a-dia (`basketlens.replay`) que reproduz compras, resgates de cupons, rotação de `$slice: -5` no MongoDB, append no Cassandra e gestão dinâmica de TTL e invalidação de cache (`DEL profile:{id}`) no Redis.
- `polyglot-query-library`: Biblioteca enxuta de consultas poliglotas (`basketlens.queries`) que executa `build_360_view` e responde às 3 perguntas de negócio + bônus de Trade Marketing fazendo *pushdown* aos 3 bancos sem carregar o dataset em memória.
- `replay-and-analytics-notebooks`: Notebooks interativos `03_event_replay_streaming.ipynb` e `04_polyglot_360_analytics.ipynb` para demonstração ao vivo dos dois modos operacionais.

### Modified Capabilities
<!-- Nenhuma capability existente modificada. -->

## Impact

- Código-fonte: `src/basketlens/replay/__init__.py`, `src/basketlens/replay/engine.py`, `src/basketlens/queries/__init__.py`, `src/basketlens/queries/view_360.py`, `src/basketlens/queries/business_questions.py`.
- Notebooks: `notebooks/03_event_replay_streaming.ipynb`, `notebooks/04_polyglot_360_analytics.ipynb`.
- Testes: `tests/test_replay_and_queries.py`.
