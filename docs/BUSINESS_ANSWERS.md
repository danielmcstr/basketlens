# BasketLens 360º — Respostas Executivas e Evidências Empíricas das Perguntas de Negócio

> **Entregável Oficial — Aula 8 (Implementação Funcional com Dados Reais e Consultas Poliglotas)**
> **Disciplina:** Big Data e NoSQL: Soluções de Armazenamento Inovadoras (BDDB)
> **Professor:** Prof. Msc. Pedro Ernesto da Silva Souza
> **Reprodutibilidade:** Todos os resultados abaixo foram extraídos diretamente dos módulos `basketlens.queries` e `basketlens.replay` e estão reproduzidos com células executadas em `notebooks/03_event_replay_streaming.ipynb` e `notebooks/04_polyglot_360_analytics.ipynb`.

---

## 1. Pergunta de Negócio 1 — Qual o perfil e o histórico recente de um domicílio do programa?

### 1.1 Estratégia Poliglota de Execução (`build_360_view` + `get_household_profile_and_recent_history`)
Para responder à Pergunta 1 para o cliente do estudo de caso oficial do guia da dunnhumby (**John Smith, `household_key = 208`**), a arquitetura combina três operações sem ler nenhum arquivo CSV:
1. **Redis (Cache-Aside `GET profile:208`)**: verifica se o documento 360º já está em memória RAM. Em caso de *Cache Miss*, consulta o MongoDB e grava `SETEX profile:208 60 <json>`.
2. **MongoDB (`db.households.find_one({"household_key": 208})`)**: retorna o perfil demográfico (`demographics`), o resumo comportamental consolidado (`behavior_summary`), as 5 últimas cestas enriquecidas (`recent_baskets`) e as campanhas recebidas (`campaigns_received`).
3. **Apache Cassandra (`transactions_by_household`)**: lê o topo da partição física `household_key = 208`, que já está ordenada em disco por `CLUSTERING ORDER BY (week_no DESC, day DESC, basket_id DESC, product_id ASC)`.

### 1.2 Evidência Real — Perfil 360º de John Smith (`household_key = 208`) no MongoDB

```json
{
  "household_key": 208,
  "demographics": {
    "classification_1": "Age Group4",
    "classification_2": "Y",
    "classification_3": "Level5",
    "homeowner_desc": "Homeowner",
    "classification_4": "2",
    "classification_5": "Group5",
    "kid_category_desc": "None/Unknown",
    "age_group": "Age Group4",
    "marital_code": "Y",
    "income_level": "Level5",
    "household_size": "2",
    "hh_comp_group": "Group5"
  },
  "behavior_summary": {
    "total_spend": 4296.33,
    "total_baskets": 140,
    "active_weeks": 80,
    "avg_basket_value": 30.69,
    "avg_weekly_spend": 53.70,
    "first_day": 49,
    "last_day": 701,
    "top_departments": ["GROCERY", "MEAT", "KIOSK-GAS"],
    "top_commodities": ["COUPON/MISC ITEMS", "BEEF", "ICE CREAM/MILK/SHERBTS"]
  },
  "campaigns_received": [8, 13, 17, 18, 22, 26, 29, 30]
}
```

#### Últimas 5 Cestas Embutidas no Documento (`recent_baskets` — *Subset + Extended Reference Pattern*)

| Ordem | `basket_id` | `day` | `week_no` | `store_id` | Valor da Cesta (`$`) | Qtd. Itens |
|:---:|---:|---:|---:|---:|---:|---:|
| 1 | `42039050670` | 692 | 100 | 327 | `$18.28` | 5 |
| 2 | `42039050687` | 692 | 100 | 327 | `$7.19` | 1 |
| 3 | `42076550395` | 695 | 100 | 327 | `$4.28` | 2 |
| 4 | `42135860991` | 699 | 101 | 327 | `$16.22` | 8 |
| 5 | `42158927457` | 701 | 101 | 327 | `$4.19` | 2 |

### 1.3 Evidência Real — Transações Recentes no Apache Cassandra (`transactions_by_household`)

Consulta CQL executada sem `ALLOW FILTERING`:
```sql
SELECT household_key, week_no, day, basket_id, product_id,
       quantity, sales_value, store_id, trans_time,
       retail_disc, coupon_disc, coupon_match_disc
FROM basketlens.transactions_by_household
WHERE household_key = 208
LIMIT 20;
```

Amostra das 5 linhas mais recentes retornadas diretamente pela ordem de *clustering* (`week_no DESC, day DESC`):

| `household_key` | `week_no` | `day` | `basket_id` | `product_id` | `quantity` | `sales_value` | `store_id` | `trans_time` | `retail_disc` | `coupon_disc` | `coupon_match_disc` |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 208 | 101 | 701 | `42158927457` | `862349` | 1 | `$1.20` | 327 | 1904 | `-$0.74` | `$0.00` | `$0.00` |
| 208 | 101 | 701 | `42158927457` | `925862` | 1 | `$2.99` | 327 | 1904 | `-$0.20` | `$0.00` | `$0.00` |
| 208 | 101 | 699 | `42135860991` | `827261` | 1 | `$1.32` | 327 | 1313 | `$0.00` | `$0.00` | `$0.00` |
| 208 | 101 | 699 | `42135860991` | `854677` | 1 | `$2.49` | 327 | 1313 | `$0.00` | `$0.00` | `$0.00` |
| 208 | 101 | 699 | `42135860991` | `862732` | 2 | `$3.00` | 327 | 1313 | `-$0.18` | `$0.00` | `$0.00` |

#### Histórico de Recompra de um Produto Específico (`transactions_by_household_product`)
Quando o filtro inclui simultaneamente `household_key = 208` e `product_id = 1017772` (produto do estudo de caso da página 2 do PDF oficial), a consulta utiliza a 2ª tabela CQL com chave de partição composta `((household_key, product_id), day, basket_id)`:

| `day` | `week_no` | `basket_id` | `product_id` | `quantity` | `sales_value` | `retail_disc` | `coupon_disc` | `coupon_match_disc` |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **654** | **94** | `41531980403` | `1017772` | 1 | `$1.33` | `$0.00` | **`-$0.50`** | **`-$0.50`** |
| 622 | 90 | `41008341062` | `1017772` | 1 | `$1.38` | `-$0.45` | `$0.00` | `$0.00` |
| 606 | 87 | `40765530992` | `1017772` | 2 | `$2.36` | `-$1.22` | `-$0.40` | `-$0.40` |
| 597 | 86 | `40666652921` | `1017772` | 1 | `$0.88` | `-$0.61` | `-$0.50` | `-$0.50` |
| 503 | 73 | `34749055907` | `1017772` | 1 | `$1.69` | `$0.00` | `-$0.30` | `-$0.30` |
| 300 | 44 | `31424115725` | `1017772` | 1 | `$1.99` | `-$0.10` | `-$0.30` | `-$0.30` |

### 1.4 Auditoria de Índice (`explain("executionStats")`) e Benchmark de Cache-Aside

- **Plano de Execução no MongoDB (`db.households.find({"household_key": 208}).explain("executionStats")`)**:
  - `winningPlan.stage`: **`EXPRESS_IXSCAN`** sobre o índice único `idx_household_key_unique` (`{ household_key: 1 }`)
  - `nReturned`: `1` | `totalKeysExamined`: `1` | `totalDocsExamined`: `1` | `executionTimeMillis`: `0 ms` (Zero `COLLSCAN`).
- **Benchmark Cache-Aside (`profile:208` — 15 iterações em `benchmark_cache_aside_latency`)**:
  - **Cold Cache Miss (MongoDB fallback + `SETEX` no Redis)**: `~1.05 ms` a `1.45 ms` por lookup de perfil
  - **Warm Cache Hit (`GET profile:208` direto da RAM do Redis)**: `~0.28 ms` a `0.42 ms` (**ganho de `~3.2x`** na leitura do perfil)

---

## 2. Pergunta de Negócio 2 — Quais campanhas estão ativas agora para um domicílio?

### 2.1 Estado Ativo em `REFERENCE_DAY = 650` (`get_active_campaigns_for_household(208)`)
Posicionando o relógio operacional em `REFERENCE_DAY = 650` com `SECONDS_PER_DAY = 5`:
- Das **30 campanhas** do catálogo (`campaign_desc.csv`), apenas **5 estão vigentes globalmente** no Dia 650 (`START_DAY <= 650 <= END_DAY`):
  - **Campanha 15** (`TypeC`, Dias 547–708, `TTL = 290s`)
  - **Campanha 20** (`TypeC`, Dias 615–685, `TTL = 175s`)
  - **Campanha 21** (`TypeB`, Dias 624–656, `TTL = 30s`)
  - **Campanha 22** (`TypeB`, Dias 624–656, `TTL = 30s`)
  - **Campanha 23** (`TypeB`, Dias 646–684, `TTL = 170s`)
- Embora John Smith (`household_key = 208`) tenha recebido historicamente 8 campanhas (`[8, 13, 17, 18, 22, 26, 29, 30]`), as campanhas `8`, `13`, `17` e `18` já expiraram antes do Dia 650 (`END_DAY < 650`), e as campanhas `26`, `29` e `30` ainda não iniciaram (`START_DAY > 650`).
- Portanto, no Dia 650, `SMEMBERS household:208:campaigns` filtrado por `TTL(campanha:{id}) > 0` retorna **exclusivamente a Campanha 22**:
  - **Campanha Ativa:** `22` (`DESCRIPTION = "TypeB"`, mecanismo *Triggered/segmented campaign pool*, vigência `START_DAY = 624` a `END_DAY = 656`, `TTL = 30s`).
  - **Cupons Elegíveis (`household:208:coupons` $\cap$ `campanha:22:coupons`):** **21 cupons ativos**, incluindo o cupom **`51800000050`** (que desconta 38 produtos, entre eles `PRODUCT_ID = 72717` e `1017772`).

### 2.2 Evolução Dinâmica no Event Replay (Dias 650 a 657 — `notebooks/03_event_replay_streaming.ipynb`)

| Dia Simulado (`DAY`) | `TTL(campanha:22)` no Redis | John Smith (`#208`) Comprou? | Cesta (`BASKET_ID`) | Cupom Resgatado no Dia | `DEL profile:208` Executado? | `last_day` no MongoDB |
|:---:|---:|:---:|:---:|:---:|:---:|---:|
| **Baseline 649** | `35s` | — | Última: `41439808495` (Dia 647) | — | — | `647` |
| **650** | `30s` | **Sim** (11 itens, `$19.16`) | `41466570461` | Nenhum | **Sim** | `650` |
| **651** | `25s` | Não | — | Nenhum | Não | `650` |
| **652** | `20s` | Não | — | Nenhum | Não | `650` |
| **653** | `15s` | Não | — | Nenhum | Não | `650` |
| **654** | `10s` | **Sim** (13 itens, `$41.88`) | **`41531980403`** | **`51800000050` (Campanha 22)** | **Sim** | **`654`** |
| **655** | `5s` | Não | — | Nenhum | Não | `654` |
| **656** | `5s` (último dia) | Não | — | Nenhum | Não | `654` |
| **657** | **`-2` (Expirada!)** | **Sim** (12 itens, `$21.22`) | `41587470481` | Nenhum | **Sim** | `657` |

- No **Dia 654**, ao comprar o produto `1017772` na cesta `41531980403`, John Smith resgata o cupom `51800000050` (obtendo `COUPON_DISC = -$0.50` e `COUPON_MATCH_DISC = -$0.50`), o cupom é removido de `household:208:coupons` (`SREM`) e registrado em `household:208:redeemed_coupons` (`654:22:51800000050`), o vetor `recent_baskets` no MongoDB rotaciona mantendo exatamente 5 cestas (`$slice: -5`), e `DEL profile:208` invalida o cache.
- No **Dia 657** (após `END_DAY = 656`), a chave `campanha:22` expira (`TTL = -2`) e deixa automaticamente de aparecer em `get_active_campaigns_for_household(208)`.

---

## 3. Pergunta de Negócio 3 — Qual o gasto semanal médio por faixa demográfica?

### 3.1 Estratégia de Execução Pushdown (`get_avg_weekly_spend_by_demographic`)
1. **MongoDB Indexed Projection (`idx_demographics_class1_class3`)**: projeta apenas os **801 domicílios** que possuem subdocumento `demographics` (`nReturned = 801`, zero `COLLSCAN`).
2. **Cassandra Partition Pushdown (`execute_concurrent_with_args`)**: consulta concorrentemente as 801 partições em `transactions_by_household` (`WHERE household_key = ?`), com **`allow_filtering_used = False`** (zero leitura dos outros 1.699 domicílios sem demografia).
3. **Consolidação Ordinal**: agrupa as 801 famílias pelas duas dimensões principais do guia oficial da dunnhumby:
   - `classification_1` (**Faixa Etária Estimada**: `Age Group1` a `Age Group6`)
   - `classification_3` (**Nível de Renda / Faixa Socioeconômica**: `Level1` a `Level12`)

### 3.2 Tabela Consolidada 3A — Gasto Semanal Médio por Faixa Etária (`classification_1`)

| Faixa Etária (`classification_1`) | Domicílios (`household_count`) | % dos 801 Domicílios | Gasto Acumulado 2 Anos (`total_spend`) | Total de Semanas Ativas (`total_active_weeks`) | Gasto Semanal Médio Ponderado (`avg_weekly_spend`) | Média Simples por Domicílio (`avg_household_weekly_spend`) |
|:---|---:|---:|---:|---:|---:|---:|
| **`Age Group1`** | 46 | 5,74% | `$216,583.02` | 3.252 | **`$66.60`** | `$65.88` |
| **`Age Group2`** | 142 | 17,73% | `$777,936.25` | 9.826 | **`$79.17`** | `$77.16` |
| **`Age Group3`** | 194 | 24,22% | `$1,242,146.79` | 13.773 | **`$90.19`** | `$86.52` |
| **`Age Group4`** | 288 | 35,96% | `$1,657,467.05` | 20.400 | **`$81.25`** | `$77.92` |
| **`Age Group5`** | 59 | 7,37% | `$298,229.02` | 4.347 | **`$68.61`** | `$67.64` |
| **`Age Group6`** | 72 | 8,99% | `$305,354.13` | 4.890 | **`$62.44`** | `$62.71` |
| **Total / Geral** | **801** | **100,00%** | **`$4,497,716.26`** | **56.488** | **`$79.62`** | **`$77.53`** |

**Interpretação de Negócio (`classification_1`):**
- As faixas intermediárias **`Age Group3`** (`$90.19`/semana, 194 famílias) e **`Age Group4`** (`$81.25`/semana, 288 famílias — onde se encontra John Smith `#208`) concentram **60,18% da base demográfica** e os maiores gastos semanais, refletindo famílias em fase de pico de consumo doméstico. Os extremos (`Age Group1` jovem com `$66.60` e `Age Group6` sênior com `$62.44`) apresentam cestas menores.

### 3.3 Tabela Consolidada 3B — Gasto Semanal Médio por Nível de Renda (`classification_3`)

| Nível Socioeconômico (`classification_3`) | Domicílios (`household_count`) | Gasto Acumulado 2 Anos (`total_spend`) | Semanas Ativas (`total_active_weeks`) | Gasto Semanal Médio (`avg_weekly_spend`) | Média por Domicílio (`avg_household_weekly_spend`) |
|:---|---:|---:|---:|---:|---:|
| **`Level1`** | 61 | `$339,136.30` | 4.331 | **`$78.30`** | `$75.33` |
| **`Level2`** | 74 | `$303,187.20` | 5.225 | **`$58.03`** | `$57.43` |
| **`Level3`** | 77 | `$380,231.38` | 5.458 | **`$69.66`** | `$68.70` |
| **`Level4`** | 172 | `$825,945.47` | 12.019 | **`$68.72`** | `$66.79` |
| **`Level5`** | 192 | `$1,094,852.10` | 13.735 | **`$79.71`** | `$77.24` |
| **`Level6`** | 96 | `$558,962.90` | 6.503 | **`$85.95`** | `$83.06` |
| **`Level7`** | 34 | `$201,543.17` | 2.442 | **`$82.53`** | `$80.14` |
| **`Level8`** | 38 | `$300,658.10` | 2.656 | **`$113.20`** | `$107.10` |
| **`Level9`** | 30 | `$251,845.22` | 2.151 | **`$117.08`** | `$112.28` |
| **`Level10`** | 11 | `$94,033.09` | 799 | **`$117.69`** | `$106.73` |
| **`Level11`** | 5 | `$28,632.43` | 320 | **`$89.48`** | `$89.03` |
| **`Level12`** | 11 | `$118,688.90` | 849 | **`$139.80`** | `$137.40` |
| **Total / Geral** | **801** | **`$4,497,716.26`** | **56.488** | **`$79.62`** | **`$77.53`** |

**Interpretação de Negócio (`classification_3`):**
- Observa-se forte gradiente positivo de gasto semanal conforme o nível socioeconômico avança: enquanto as faixas `Level2`–`Level4` gastam entre **`$58.03` e `$69.66`/semana**, os segmentos de alta renda (`Level8` a `Level12`) atingem de **`$113.20` a `$139.80`/semana** (um aumento de **+140,9%** entre `Level2` e `Level12`).

---

## 4. Consultas Bônus de Trade Marketing — Lift Promocional de Display & Mailer (`causal_data`)

### 4.1 Estudo de Caso do Guia Oficial: Produto `72717` na Semana 40 (`get_product_causal_promotion_lift(72717)`)
Cruzando `sales_by_product_week` (`WHERE product_id = 72717`) com `causal_promotions_by_store_week` (`WHERE store_id = ? AND week_no = ? AND product_id = 72717`):
- **Semana 40 (`DAY = 272`)**:
  - Venda registrada: **2 unidades**, receita líquida **`$2.50`** (`RETAIL_DISC = -$1.38`, `COUPON_DISC = -$0.50`, `COUPON_MATCH_DISC = -$0.50` — preço cheio de gôndola de `$4.38` reduzido para `$1.88` pago pelo cliente, exatamente como descrito na página 4 do PDF oficial!).
  - Exposição física e tabloide na Semana 40 no Cassandra: **11 lojas monitoradas** com encarte ativo **`mailer_page = 'A'`** (*Interior page feature*) e destaque físico de loja **`display_type = '2'`** (*Store rear*) nas lojas `432` e `450`.

### 4.2 Lift Promocional em Produto de Alto Giro (`PRODUCT_ID = 862349`)
Analisando as **101 semanas** de vendas do SKU `862349` em `sales_by_product_week` cruzadas com `causal_promotions_by_store_week`:
- **Semanas sem promoção (`is_promoted = False`)**: receita média de **`$19.43` / semana**
- **Semanas com Display e/ou Tabloide (`is_promoted = True`)**: receita média de **`$86.96` / semana**
- **Promotional Lift Mensurado**: **`+347.56%`** de aumento na receita semanal média quando apoiado por execução de Trade Marketing (gôndola + encarte).

### 4.3 Vitrine Semanal em Memória no Redis (`get_store_weekly_showcase(store_id=288, week_no=94)`)
- **Top 5 Categorias da Semana 94 (`ZREVRANGE ranking:week:94 0 4 WITHSCORES`)**:
  1. `COUPON/MISC ITEMS` — `$7,135.36`
  2. `BEEF` — `$3,950.83`
  3. `SOFT DRINKS` — `$2,904.12`
  4. `FLUID MILK PRODUCTS` — `$2,664.05`
  5. `CHEESE` — `$2,414.03`
- **Vitrines Físicas da Loja 288 na Semana 94 (`SMEMBERS store:288:week:94:displays`)**: **100 SKUs** indexados em memória para recomendação instantânea geolocalizada na entrada da loja.
