## Context

A Fase 3 materializa os dois diferenciais centrais pedidos para o projeto:
1. **O Modo Operacional de Event Replay (`basketlens.replay` + Notebook `03`)**: demonstra como a arquitetura funciona em produção no dia a dia à medida que o tempo avança (`DAY = 650, 651, ..., 656`), integrando escrita transacional no Cassandra, atualização incremental do documento 360º no MongoDB (`$inc` + `$push` com `$slice: -5`) e rotação de TTL + invalidação de cache (`DEL profile:{id}`) no Redis.
2. **A Biblioteca de Consulta Poliglota (`basketlens.queries` + Notebook `04`)**: responde às 3 perguntas obrigatórias do enunciado e às consultas bônus de Trade Marketing fazendo *pushdown* aos 3 bancos, trazendo para a memória do Python apenas os dados estritamente necessários à resposta.

## Goals / Non-Goals

**Goals:**
- Implementar `src/basketlens/replay/engine.py` operando dia a dia com leitura *out-of-core* via Polars `scan_csv().filter(pl.col("DAY") == day)`.
- Implementar `src/basketlens/queries/view_360.py` e `src/basketlens/queries/business_questions.py` cumprindo rigorosamente a regra *Zero Full-Dataset In-Memory*.
- Construir os notebooks `03_event_replay_streaming.ipynb` e `04_polyglot_360_analytics.ipynb`.

**Non-Goals:**
- Não alterar os schemas definidos na Fase 1.
- Não depender de brokers externos pesados (Kafka/Spark) para rodar a demonstração local — o motor de Event Replay em Python simula diretamente o consumidor da fila de PDV atualizando os 3 bancos.

## Decisions

### 1. Mecânica de Atualização Incremental no Event Replay (`replay_day`)
Para cada `day` simulado:
- **Extração Seletiva via Polars**:
  - `pl.scan_csv("dataset/transaction_data.csv").filter(pl.col("DAY") == day).collect(streaming=True)` retorna apenas ~3.600 linhas (as compras daquele único dia em todas as lojas).
  - `pl.scan_csv("dataset/coupon_redempt.csv").filter(pl.col("DAY") == day).collect(streaming=True)` retorna os poucos resgates daquele dia.
- **Atualização nos 3 Bancos**:
  1. **Cassandra**: insere as novas linhas do dia nas tabelas `transactions_by_household` e `transactions_by_household_product` e atualiza o acumulado da semana em `sales_by_product_week`.
  2. **MongoDB**: agrupa as compras do dia por `household_key` e `BASKET_ID` (enriquecendo com `product.csv`), executando `UpdateOne` com:
     - `$inc`: `{"behavior_summary.total_spend": day_spend, "behavior_summary.total_baskets": day_baskets}`
     - `$max`: `{"behavior_summary.last_day": day}`
     - `$push`: `{"recent_baskets": {"$each": new_baskets, "$sort": {"day": 1, "basket_id": 1}, "$slice": -5}}`
  3. **Redis**:
     - Para cada `household_key` modificado no dia: `redis.delete(f"profile:{household_key}")` (invalidação do Cache-Aside).
     - Para as campanhas ativas em `day`: recalcula o TTL restante `(END_DAY - day) * seconds_per_day` (ou deixa o TTL nativo correr quando em modo contínuo `run_live_countdown`).

### 2. Execução Pushdown da Pergunta 3 (Gasto Semanal Médio por Faixa Demográfica)
- **Passo 1 (MongoDB Projection Indexada)**:
  - Buscamos no MongoDB apenas os 801 domicílios com demografia:
    `db.households.find({"demographics": {"$exists": True}}, {"_id": 0, "household_key": 1, "demographics": 1, "behavior_summary": 1})`
  - Como são apenas 801 documentos projetados (~100 KB), o uso de memória é ínfimo.
- **Passo 2 (Cassandra Partition Pushdown + Comparação com Resumo Materializado)**:
  - Para cada um dos 801 `household_key`s, consultamos a partição correspondente em `transactions_by_household` usando `execute_concurrent_with_args` (`SELECT household_key, week_no, sales_value FROM transactions_by_household WHERE household_key = ?`), agregando o gasto semanal por domicílio sem jamais usar `ALLOW FILTERING` nem ler os outros 1.699 domicílios.
  - Em seguida agrupamos os 801 domicílios pelas faixas ordinais do PDF (`classification_1` = Faixa Etária `Age Group1..6` e `classification_3` = Nível de Renda `Level1..12`), e também comparamos com `behavior_summary.avg_weekly_spend` pré-calculado no MongoDB para mostrar a diferença de latência entre agregação colunar sob demanda vs. leitura de resumo materializado.

## Risks / Trade-offs

- **[Risco] Ao reexecutar o Notebook 03 (Event Replay) após o Notebook 02 (Full Ingestion), os dados de `DAY > 649` já estariam no Cassandra** → **Mitigação:** `prepare_replay_baseline(cutoff_day=649)` na abertura do Notebook 03 limpa/recarrega apenas o delta (ou reinicializa o estado até o Dia 649 de forma rápida e determinística), e ao final permite restaurar o estado completo até o Dia 711.
