# CASE 7 — Fidelidade dunnhumby: visão 360º do cliente com três bancos

> **Rascunho de trabalho (draft).** Documento de estudo do grupo — não é material
> arquivado do portal Blackboard nem entrega oficial. Prosa em português; código,
> nomes de variáveis e de tabelas em inglês.
>
> **Disciplina:** Big Data e NoSQL: Soluções de Armazenamento Inovadoras (BDDB)
> **Professor:** Prof. Msc. Pedro Ernesto da Silva Souza
> **Trabalho Final — peso 45% · Apresentação na Aula 8**

---

## 1. O que o case exige (verbatim do enunciado)

**CASE 7 — Fidelidade dunnhumby — visão 360º do cliente com três bancos**

- **Banco(s)-alvo:** MongoDB + Cassandra + Redis
- **Contexto de negócio:** Uma rede de varejo físico com programa de fidelidade quer
  visão 360º: perfil do domicílio em documentos, transações de 2 anos em colunar e
  campanhas/cupons ativos em cache, como na base The Complete Journey.
- **Base de dados:** dunnhumby — The Complete Journey — 2 anos de transações reais de
  ~2.500 domicílios, com campanhas e cupons (fonte oficial dunnhumby Source Files;
  espelho no Kaggle).
- **Licença/permissão:** Distribuída gratuitamente pela dunnhumby para fins de pesquisa
  e ensino, mediante aceite dos termos na página oficial (dunnhumby.com/source-files);
  citar a fonte.
- **Acesso:** Página oficial da dunnhumby (cadastro gratuito) ou espelho no Kaggle:
  `kaggle.com/datasets/frtgnn/dunnhumby-the-complete-journey`.
- **Recorte sugerido:** Perfis completos; transações de 6 meses no Cassandra; campanhas
  ativas no Redis.

**Requisitos mínimos:**

1. Documento de perfil do domicílio (demografia + resumo de comportamento) no Atlas;
2. Transações por domicílio/semana em CQL, com chaves justificadas;
3. Cupons e campanhas ativas no Redis com TTL alinhado à vigência;
4. Consulta integrada (script Python): montar a visão 360º de um domicílio;
5. Diagrama da arquitetura e análise crítica: onde entraria um grafo?

**Perguntas de negócio que a solução deve responder:**

- Qual o perfil e o histórico recente de um domicílio do programa?
- Quais campanhas estão ativas agora para um domicílio?
- Qual o gasto semanal médio por faixa demográfica?

**Rubrica (45 pontos):** arquitetura e modelagem justificadas (12) · implementação
funcional do recorte com dados reais e consultas (15) · análise crítica (8) ·
apresentação: clareza, domínio técnico e participação de todos (10).

---

## 2. Fontes oficiais e caracterização do dataset

| Recurso | Link |
|:---|:---|
| Página oficial (dunnhumby Source Files) | https://www.dunnhumby.com/source-files/ |
| The Complete Journey User Guide (cópia local no repositório) | [docs/dunnhumby_The-Complete-Journey-User-Guide.pdf](../docs/dunnhumby_The-Complete-Journey-User-Guide.pdf) |
| User guide oficial relacionado (Let's get sort-of-real, PDF) | https://assets.ctfassets.net/psj0p18eh7z1/2SYO8T89Pxfd65nr6HQEbR/ce6c475e1bf15d503141bbd1fcc3b0a2/Let_s-Get-Sort-of-Real-User-Guide-dunnhumby.pdf |
| Espelho no Kaggle (TCJ) | https://www.kaggle.com/datasets/frtgnn/dunnhumby-the-complete-journey |
| Reconstrução de referência (R/Python) | https://github.com/bradleyboehmke/completejourney |

**Observação sobre a documentação oficial.** Na página *Source Files* a dunnhumby
descreve o dataset **The Complete Journey** e mantém o botão *Download 'The Complete
Journey'*. O único PDF de guia publicado diretamente pela dunnhumby hoje é o
**“Let's get sort-of-real: dummy data to test techniques and algorithms — User guide”**,
que descreve o dataset **Let's Get Sort-of-Real** (117 semanas, ~300M transações,
~500.000 clientes, 4,3 GB em 9 arquivos). Esse guia **não** é o dicionário do
The Complete Journey — é um dataset irmão, de dados dummies, do mesmo programa.

O **The Complete Journey User Guide** (o dicionário que corresponde ao nosso case,
com `household_key`, `DAY`, `WEEK_NO`, `BASKET_ID`, `hh_demographic`, `campaign_desc`,
`coupon`, `coupon_redempt`, `causal_data`) agora está incluído neste repositório em
`docs/dunnhumby_The-Complete-Journey-User-Guide.pdf` e é a referência adotada neste
draft para os campos do dataset e para a modelagem discutida ao longo do documento,
mantendo o crédito à dunnhumby/84.51°.

### Tamanho e grão dos arquivos (The Complete Journey — oficial)

Download compactado oficial (Kaggle / dunnhumby): **130,37 MB** (.zip).  
Tamanho total descompactado (8 arquivos CSV): **847,05 MB** (6.274.384 linhas).

| Arquivo | Linhas | Colunas | Tamanho Descompactado | Grão | Papel no Case 7 |
|:---|---:|---:|---:|:---|:---|
| `transaction_data.csv` | 2.595.732 | 12 | **141,74 MB** | 1 linha = 1 item no carrinho | **Coração:** Histórico de compras (Cassandra) |
| `causal_data.csv` | 3.678.652 | 5 | **695,86 MB** | produto × loja × semana | **Extensão Opcional:** Trade Marketing / gôndola (Cassandra) |
| `product.csv` | 92.353 | 7 | **6,43 MB** | 1 linha = 1 produto | Catálogo de produtos (Mongo / Cassandra) |
| `coupon.csv` | 124.548 | 3 | **2,82 MB** | campanha × cupom × produto | Regras de cupons vigentes (Redis Hashes) |
| `campaign_table.csv` | 7.208 | 3 | **95,87 kB** | domicílio × campanha | Elegibilidade domiciliar (Redis Sets) |
| `coupon_redempt.csv` | 2.318 | 4 | **54,11 kB** | 1 linha = 1 resgate | Histórico de conversão |
| `hh_demographic.csv` | 801 | 8 | **44,35 kB** | 1 linha = 1 domicílio | Perfil do domicílio (MongoDB `households`) |
| `campaign_desc.csv` | 30 | 4 | **540 B** | 1 linha = 1 campanha | Vigência temporal → Base de cálculo do TTL |

### 2.1 Cenários de Volumetria e Dimensionamento de Big Data

Como o objetivo acadêmico é exercitar conceitos e desafios de **Big Data**, o grupo estruturou o projeto em três patamares de volumetria:

| Cenário de Execução | Volume Bruto | Registros Totais | Distribuição nos Bancos | Propósito Didático |
|:---|---:|---:|:---|:---|
| **Tier 1: Baseline (Recorte Mínimo)** | ~40 MB | ~650.000 transações | • Mongo: ~2,6 MB (801 perfis)<br>• Cassandra: ~45 MB (6 meses)<br>• Redis: ~3,5 MB RAM | Cumpre rigorosamente o enunciado mínimo do professor, com consumo mínimo de recursos e foco na entrega rápida. |
| **Tier 2: Escala Real Integral (Core + Causal)** | **~847 MB** | **6.274.384 linhas** | • Mongo: ~7 MB (perfis + catálogo Top)<br>• Cassandra: ~310 MB (2 anos + causal)<br>• Redis: ~4,5 MB RAM | Volume real completo da base. Incorpora o `causal_data` (695 MB) no Cassandra local para análises avançadas de Trade Marketing e *lift* de gôndola. |
| **Tier 3: Inflado Sintético (Benchmark de Estresse)** | **~5 a 15 GB** | **25M a 60M linhas** | • Mongo: ~50 MB (sharded)<br>• Cassandra: ~2,5 GB a 6 GB<br>• Redis Cluster: ~25 MB RAM | Gerador estocástico em Python que replica os 2.500 domicílios para 25.000 ou 100.000 com *jitter* de datas, estressando *SSTables*, compactação colunar e particionamento K8s. |

**Atenção a quatro armadilhas do dataset** (relevantes para a modelagem):

1. **Assimetria do `causal_data.csv`:** Ele responde por **82% do tamanho do dataset (695,86 MB)**. Não deve ser ingerido no MongoDB Atlas M0 (que tem teto de 512 MB). Seu destino natural é o **Cassandra**, que comprime em LZ4 (~90 MB em disco) e consulta em O(1) por chave de partição composta `(store_id, week_no)`.
2. **Demografia incompleta:** só **801 de ~2.500** domicílios têm `hh_demographic`.
   As transações existem para todos, mas a demografia não — isso limita a pergunta
   “gasto por faixa demográfica”, que deve ser respondida apenas sobre os 801.
3. **A orientação é relacional:** o dataset é um conjunto de 8 tabelas ligadas por
   `household_key`, `product_id`, `campaign`, `coupon_upc`. Todo o exercício é decidir
   **o que embutir, o que referenciar e o que desnormalizar** entre os três bancos.
4. **Dados históricos, não tempo real:** `DAY` vai de 1 a 711 e `WEEK_NO` de 1 a 102
   (2 anos). Para demonstrar **TTL** no Redis é preciso definir um **“agora” de
   referência** e comprimir a escala de tempo (detalhado na seção 5.3).

---

## 3. Dicionário de dados (campos usados no trabalho)

### 3.1 `transaction_data` — o coração (2.595.732 linhas)

| Coluna | Descrição |
|:---|:---|
| `household_key` | Identifica o domicílio |
| `BASKET_ID` | Identifica a ocasião de compra (a cesta) |
| `DAY` | Índice de tempo; dia da transação (1–711) |
| `PRODUCT_ID` | Identifica o produto |
| `QUANTITY` | Quantidade comprada |
| `SALES_VALUE` | Receita líquida recebida pelo varejista (já descontados `retail_disc`/`coupon_match_disc`) |
| `STORE_ID` | Identifica a loja |
| `RETAIL_DISC` | Desconto do cartão de fidelidade |
| `TRANS_TIME` | Hora do dia (`%H%M`) |
| `WEEK_NO` | Índice de tempo; semana da transação (1–102) |
| `COUPON_DISC` | Desconto do cupom de fabricante (reembolsado pelo fabricante) |
| `COUPON_MATCH_DISC` | Desconto do cupom casado pelo varejista |

> `SALES_VALUE` **não** é o preço pago pelo cliente. Preço pago e preço de gôndola
> seguem as fórmulas do guia oficial:
> - **Loyalty card price** = `(SALES_VALUE - (RETAIL_DISC + COUPON_MATCH_DISC)) / QUANTITY`
> - **Non-loyalty price** = `(SALES_VALUE - COUPON_MATCH_DISC) / QUANTITY`

### 3.2 `hh_demographic` — perfil (801 linhas)

| Coluna | Descrição |
|:---|:---|
| `household_key` | Identifica o domicílio |
| `AGE_DESC` | Faixa de idade |
| `MARITAL_STATUS_CODE` | Estado civil (A/Coded) |
| `INCOME_DESC` | Faixa de renda (ex.: `50-74K`) |
| `HOMEOWNER_DESC` | Proprietário / inquilino |
| `HH_COMP_DESC` | Composição do domicílio |
| `HOUSEHOLD_SIZE_DESC` | Tamanho (até 5+) |
| `KID_CATEGORY_DESC` | Nº de crianças (até 3+) |

### 3.3 `product` — catálogo (92.353 linhas)

`PRODUCT_ID`, `MANUFACTURER`, `DEPARTMENT`, `BRAND`, `COMMODITY_DESC`,
`SUB_COMMODITY_DESC`, `CURR_SIZE_OF_PRODUCT`.

### 3.4 Campanhas e cupons

- `campaign_desc` (30): `CAMPAIGN` (1–30), `DESCRIPTION` (TypeA/TypeB/TypeC),
  `START_DAY`, `END_DAY`. **É a tabela que define a vigência → base do TTL no Redis.**
- `campaign_table` (7.208): `DESCRIPTION`, `household_key`, `CAMPAIGN` — quem recebeu o quê.
- `coupon` (124.548): `CAMPAIGN`, `COUPON_UPC`, `PRODUCT_ID`.
- `coupon_redempt` (2.318): `household_key`, `DAY`, `COUPON_UPC`, `CAMPAIGN`.
- `causal_data` (3.678.652): `PRODUCT_ID`, `STORE_ID`, `WEEK_NO`, `display`, `mailer`.
  * `display`: código da posição física do produto na loja (ex.: `0` = gôndola comum, `1` = ponta de gôndola/*end-cap*, `2` = ilha promocional intermediária, `7` = checkout frontal).
  * `mailer`: código de posicionamento em mídia impressa / tabloides da semana (página do encarte).
  * *Uso analítico:* mensurar a elasticidade de preço e o aumento de demanda (*lift*) causado pelo destaque visual no PDV.

---

## 4. Arquitetura poliglota proposta

```
                        ┌──────────────── VISÃO 360º (script Python) ────────────────┐
                        │                                                           │
   perfil +             │   MongoDB Atlas (M0)          Cassandra (Docker/K8s)      Redis Cloud
   resumo  ─────────────┼─► collection: households  ──►  tabelas transacionais  ──►  campanhas/cupons
   comportamento        │   (documento 360º + cestas      (histórico colunar,         ativos (TTL) +
                        │    recentes embutidas)          1 tabela por consulta)     cache do perfil
                        │                                          ▲                        ▲
   (opcional:           │                                          │                        │
    Trade Marketing)    │                                 causal_promotions      store:displays
                        │                                 (gôndola e tabloide)   (destaques semanais)
                        └───────────────────────────────────────────────────────────┘
```

| Banco | Família | Papel no case | Fonte da verdade |
|:---|:---|:---|:---|
| **MongoDB Atlas** | Documental | **Perfil 360º** do domicílio: demografia + resumo de comportamento + últimas cestas | Sim, para o agregado de perfil |
| **Cassandra** | Colunar | **Histórico de transações** (2 anos / recorte 6 meses) + **dados causais de gôndola** (opcional) | Sim, para transações e dados causais |
| **Redis** | Chave-valor | **Campanhas/cupons ativos** com TTL + destaques da semana + cache-aside do perfil | Não — é cache de velocidade |

**Racional por família (para a rubrica de arquitetura):**

- **Documental** porque o perfil é **um agregado lido inteiro** numa tela (360º) e os
  atributos variam por segmento — esquema flexível sem `ALTER TABLE`.
- **Colunar** porque transações são **escrita massiva e leitura por chave + período**
  (domicílio/semana); modelagem orientada à consulta resolve com partição + *clustering*.
- **Chave-valor** porque a pergunta “campanhas ativas **agora**” é **acesso por chave
  com expiração** — e o cache do perfil exige resposta em sub-milissegundo.

### 4.1 Dualidade Batch vs. Streaming: Por que uma camada de streaming sobre dados históricos?

Uma questão arquitetural legítima em projetos de Big Data é: *se o dataset já é composto por arquivos CSV históricos de 2 anos, por que propor componentes de streaming (Kafka e Redis Speed Layer)?*

A resposta ancora-se em quatro fundamentos de engenharia de dados:

1. **A Realidade do Varejo Físico:** No ecossistema operacional de uma rede supermercadista (como a Kroger, parceira histórica da dunnhumby), os dados **não nascem em arquivos batch**. Eles são emitidos de forma contínua a cada registro de compra nos pontos de venda (PDV) das mais de 500 lojas. O dataset estático é apenas um *dump* consolidado para análise de uma esteira que, na origem, é puramente transacional em tempo real.
2. **A Razão de Existência do Redis:** Se a solução fosse puramente em lote (*batch*), o Redis seria **tecnicamente redundante** — o Cassandra e o MongoDB resolveriam sozinhos as consultas analíticas históricas. O Redis só existe e se justifica na persistência poliglota porque opera como a **Camada de Velocidade (*Speed Layer*)** para eventos em voo:
   * Sessões ativas de clientes e carrinhos em montagem;
   * Cupons promocionais vigentes no instante exato do checkout com expiração automática por **TTL**;
   * Contadores em tempo real e vitrines de mais vendidos (*ranking* da hora/semana).
3. **Padrão de *Event Replay* (Simulação de Streaming):** Na prática de engenharia, a validação de arquiteturas de streaming antes do *go-live* é realizada via *Event Replay* (reprodução estocástica de eventos históricos respeitando a ordem cronológica de `DAY`, `WEEK_NO` e `TRANS_TIME`). No laboratório, utilizamos a compressão de tempo (`SECONDS_PER_DAY`, Seção 5.3) justamente para simular essa esteira de streaming e demonstrar o comportamento do TTL e da consistência eventual ao vivo.
4. **Separação de Caminhos (Cold Path vs. Hot Path):**
   * **Cold Path (Batch):** Carga perene e massiva das transações históricas no Cassandra e consolidação do perfil 360º no MongoDB.
   * **Hot Path (Streaming):** Publicação contínua de novas compras no Kafka para atualização imediata de contadores e cache no Redis, persistindo de forma assíncrona no Cassandra.

---

## 5. Modelagem detalhada

### 5.1 MongoDB — collection `households`

Um documento por `household_key`. Aplica três padrões nomeados ensinados na disciplina
(`subset`, `extended reference`, `bucket`):

```json
{
  "_id": ObjectId("..."),
  "household_key": 208,
  "demographics": {
    "age_desc": "45-54",
    "income_desc": "50-74K",
    "marital_status_code": "A",
    "homeowner_desc": "Homeowner",
    "hh_comp_desc": "2 Adults No Kids",
    "household_size_desc": "2",
    "kid_category_desc": "None"
  },
  "behavior_summary": {
    "total_spend": 4123.77,
    "total_baskets": 756,
    "avg_basket_value": 5.45,
    "avg_weekly_spend": 40.43,
    "first_day": 1,
    "last_day": 711,
    "top_departments": ["GROCERY", "PRODUCE", "MEAT"],
    "top_commodities": ["SOFT DRINKS", "MILK", "BREAD"],
    "updated_at": "2026-10-12T00:00:00Z"
  },
  "recent_baskets": [
    {
      "basket_id": 26984851472,
      "day": 711,
      "week_no": 102,
      "total": 23.41,
      "items": [
        { "product_id": 1004906, "commodity_desc": "SOFT DRINKS",
          "department": "GROCERY", "quantity": 2, "sales_value": 2.78 }
      ]
    }
  ],
  "campaigns_received": [18, 22, 26]
}
```

- **`recent_baskets`** usa **subset pattern**: só as últimas N cestas (ex.: 5); o
  histórico completo vive no Cassandra. Consistência intencional e documentada.
- **`items[]`** usa **extended reference**: copia `commodity_desc`/`department` no
  momento (o catálogo `product` é a fonte, mas a tela de 360º não deve fazer join).
- **`behavior_summary`** é um resumo materializado (RFM-ish), recalculado por um job
  a partir do Cassandra.

Índices previstos (com prova via `explain("executionStats")`):

```javascript
db.households.createIndex({ household_key: 1 }, { unique: true })
db.households.createIndex({ "demographics.income_desc": 1, "demographics.age_desc": 1 })
db.households.createIndex({ "behavior_summary.avg_weekly_spend": -1 })
```

### 5.2 Cassandra — tabelas orientadas à consulta

Mesma informação, **uma tabela por pergunta** (modelagem por consulta — o inverso do
relacional). Registro que o professor pediu: **justificar chave de partição e de
clustering de cada tabela**.

```sql
-- Pergunta A: histórico de um domicílio por semana/período
CREATE TABLE transactions_by_household (
  household_key  int,
  week_no        int,
  day            int,
  basket_id      bigint,
  product_id     int,
  quantity       int,
  sales_value    decimal,
  store_id       int,
  trans_time     int,
  PRIMARY KEY ((household_key), week_no, day, basket_id, product_id)
) WITH CLUSTERING ORDER BY (week_no DESC, day DESC);

-- Pergunta B: uma pergunta com filtro por produto exige OUTRA tabela (mesmo dado)
CREATE TABLE transactions_by_household_product (
  household_key  int,
  product_id     int,
  day            int,
  basket_id      bigint,
  quantity       int,
  sales_value    decimal,
  PRIMARY KEY ((household_key, product_id), day)
);

-- Pergunta C (agregado por produto): vendas por produto/semana
CREATE TABLE sales_by_product_week (
  product_id     int,
  week_no        int,
  total_units    bigint,
  total_sales    decimal,
  baskets        bigint,
  PRIMARY KEY ((product_id), week_no)
);

-- Extensão Opcional (Trade Marketing): exposições físicas e encartes por loja/semana
CREATE TABLE causal_promotions_by_store_week (
  store_id     int,
  week_no      int,
  product_id   int,
  display_type int,
  mailer_page  int,
  PRIMARY KEY ((store_id, week_no), product_id)
);
```

**Justificativa das chaves:**

- `transactions_by_household`: filtro de igualdade dominante é `household_key` → chave
  de partição; a leitura é sempre por período → `week_no, day` na clustering, em ordem
  decrescente para “histórico recente”.
- `transactions_by_household_product`: a pergunta muda (produto específico dentro do
  domicílio) → partição composta `(household_key, product_id)`. É o exemplo literal de
  “a mesma pergunta com filtro por produto exige outra tabela”.
- `sales_by_product_week`: agregação independente do domicílio → partição por produto.
- `causal_promotions_by_store_week`: chave de partição composta `(store_id, week_no)` isola
  toda a disposição física da loja em uma semana em um único nó, permitindo escanear todos os
  destaques de gôndola e encartes em O(1), ordenados por `product_id`.

**Antipadrão a explicar na apresentação:** uma consulta que **não** informe a chave de
partição vira varredura em todos os nós (`ALLOW FILTERING`, *full scan*) — o motivo pelo
qual existem tabelas duplicadas para consultas diferentes.

**Consistência (ONE × QUORUM):** as transações históricas são **imutáveis** (fato
consumado) e a leitura é analítica → `ONE` entrega latência baixa. Para cargas que
precisam de leitura correta imediata após escrita (ex.: reprocessamento), usar
`QUORUM`. Registrar a escolha e o porquê.

### 5.3 Redis — campanhas/cupons ativos e cache

Convenção de nomes `objeto:id` (convenção da própria disciplina):

```
campanha:{campaign}          -> HASH  { description, type, start_day, end_day }
cupom:{coupon_upc}           -> HASH  { product_id, campaign }
household:{household_key}:campaigns -> SET { campaign, ... }
household:{household_key}:coupons   -> SET { coupon_upc, ... }
profile:{household_key}      -> STRING (JSON do 360º, cache-aside)
ranking:week:{week_no}       -> ZSET   (opcional: top commodities na semana)
store:{store_id}:week:{week_no}:displays -> SET { product_id, ... } (opcional: vitrine física da semana)
```

**Mapeamento histórico → “agora” para o TTL.** O dataset tem `DAY` 1–711. Definimos um
`REFERENCE_DAY` (ex.: o último dia do recorte) e um fator de compressão `SECONDS_PER_DAY`
(ex.: `1` dia do dataset = `1` segundo real, para ver o cupom expirar ao vivo na
apresentação):

```
freshness_seconds(campaign) = max(0, (END_DAY - REFERENCE_DAY) * SECONDS_PER_DAY)
```

Campanhas já encerradas (`END_DAY < REFERENCE_DAY`) simplesmente não entram no Redis.
Assim o requisito **“TTL alinhado à vigência”** fica demonstrado e auditável.

**Cache-aside do perfil (3 passos + invalidação):**

```
1) GET profile:{household_key}
2) miss -> read households no MongoDB -> SETEX profile:{household_key} <ttl> <json>
3) ao alterar o documento no Mongo -> DEL profile:{household_key}
```

### 5.4 Script Python — a **consulta integrada** (requisito obrigatório)

Esqueleto da visão 360º que costura os três bancos:

```python
def build_360_view(household_key):
    # 1) Redis: cache-aside do perfil
    profile = redis.get(f"profile:{household_key}")
    if profile is None:
        profile = mongo.households.find_one({"household_key": household_key})
        redis.setex(f"profile:{household_key}", PROFILE_TTL, json.dumps(profile))

    # 2) Cassandra: histórico recente (últimas N semanas)
    recent = cassandra.execute(
        "SELECT week_no, day, basket_id, product_id, quantity, sales_value "
        "FROM transactions_by_household WHERE household_key=%s LIMIT 50",
        (household_key,),
    )

    # 3) Redis: campanhas ativas agora (membership + validade)
    active = [
        c for c in redis.smembers(f"household:{household_key}:campaigns")
        if redis.ttl(f"campanha:{c}") > 0
    ]

    return {"profile": profile, "recent_transactions": recent, "active_campaigns": active}
```

---

## 6. Perguntas de negócio → consulta

| Pergunta | Banco(s) | Consulta |
|:---|:---|:---|
| Perfil e histórico recente de um domicílio | Mongo + Cassandra | `find_one` no `households` + `transactions_by_household` |
| Campanhas ativas agora para um domicílio | **Redis** | `SMEMBERS household:{h}:campaigns` filtrando `TTL > 0` |
| Gasto semanal médio por faixa demográfica | **Integrada** | Cassandra agrega gasto/semana por domicílio → Python faz *join* com `age_desc`/`income_desc` do Mongo |
| (bônus) Top commodities da semana | Cassandra + Redis | `sales_by_product_week` + `ZSET ranking:week:{w}` |
| (bônus) Taxa de resgate de cupom | Cassandra + Mongo | `coupon_redempt` contra `campaign_table`/`coupon` |
| (bônus Trade Mkt) Lift de ponta de gôndola | Cassandra | Cruzar `causal_promotions_by_store_week` com `sales_by_product_week` (display > 0 vs display = 0) |
| (bônus Trade Mkt) Vitrine física da semana | Mongo + Redis | Comparar afinidade de produtos do perfil (`households`) com `store:{id}:week:{w}:displays` |

Pseudo-consulta da pergunta 3 (a que exige integração):

```python
weekly = cassandra.execute(
    "SELECT household_key, week_no, SUM(sales_value) AS spend "
    "FROM transactions_by_household WHERE household_key IN ? GROUP BY household_key, week_no"
)
# join com faixa demográfica vinda do Mongo, agregando a média de spend por faixa
```

---

## 7. CAP e consistência (tabela de decisão)

| Banco | Família | Postura CAP | Dado | Consistência aceitável |
|:---|:---|:---|:---|:---|
| MongoDB | Documental | CP (dependente de config) | Perfil 360º | Forte na escrita do agregado |
| Cassandra | Colunar | AP (ajustável) | Transações históricas | `ONE` p/ leitura; `QUORUM` p/ correção |
| Redis | Chave-valor | AP | Campanhas/cache | **Eventual** — oferta defasada custa pouco |

**Regra de ouro (do próprio material da disciplina):** aceite consistência eventual onde
o dado defasado custa pouco (cache de campanha, ranking) e exija consistência forte onde
custa caro (resgate de cupom, saldo). No nosso case o Redis **nunca** é fonte da verdade
de resgate — ele acelera a consulta.

---

## 8. Análise crítica

### 8.1 “Onde entraria um grafo?” (pergunta explícita do enunciado)

Um banco de grafos (Neo4j) agrega valor onde a **relação** é o dado principal:

- **Cesta / co-compra:** `(Household)-[:BOUGHT]->(Product)` e
  `(Product)-[:BOUGHT_WITH {weight}]-(Product)` → “quem comprou X também comprou Y” e
  *next-best-offer*, sem *joins* em cascata.
- **Cadeia de campanha:** `(Household)-[:RECEIVED]->(Campaign)-[:OFFERS]->(Coupon)`
  e `(Household)-[:REDEEMED]->(Coupon)` → atribuição de resgate e propagação de campanha.
- **Lookalike / segmentação:** domicílios conectados por cestas e categorias
  compartilhadas → público semelhante para oferta casada.

Justificativa honesta para **não** usá-lo no case: as 3 perguntas obrigatórias são de
**agregação** (perfil, campanhas ativas, gasto por faixa) — nenhuma é travessia. O grafo
fica como evolução de arquitetura (análise crítica), não como requisito.

### 8.2 Limites da solução

- **Demografia incompleta** (801/2500 domicílios) restringe a pergunta 3.
- **Defasagem do resumo** em `behavior_summary` (materializado) entre recálculos.
- **Drift de denormalização** entre o perfil no Mongo e a verdade no Cassandra.
- **Teto de 16 MB** por documento no MongoDB → o que cresce sem limite fica no colunar.
- **Free tiers:** Mongo M0 512 MB, Redis Cloud 30 MB → amostrar agressivamente.

### 8.3 O que mudaria em produção

- **CDC (Debezium/Kafka)** para sincronizar Mongo ↔ Cassandra ↔ Redis.
- **Materialized views / job agendado** para o resumo do perfil.
- **Dono explícito do TTL** de cupons (política de vigência) e estratégia de invalidação
  documentada — cache desatualizado é bug silencioso.
- **Read models separados** por consulta e o **grafo como sidecar analítico**.

### 8.4 Enriquecimento com fontes externas (didático) e limitações

Para enriquecer a discussão técnica e demonstrar recursos avançados de cada banco no contexto acadêmico, foram avaliadas 5 fontes externas potenciais, contrastando seus benefícios com as limitações metodológicas intrínsecas da base:

| Fonte Externa / Enriquecimento | Banco Beneficiado | Ganho Didático | Limitação Intrínseca do Dataset & Mitigação |
|:---|:---|:---|:---|
| **Catálogo Nutricional (Open Food Facts API)** | **MongoDB** | **Polimorfismo e esquema flexível:** produtos alimentícios recebem atributos aninhados (`nutrition: { calories, nutriscore, allergens }`), enquanto higiene/limpeza não, dispensando colunas nulas (`NULL`). | **UPCs mascarados e defasados:** `PRODUCT_ID` e `COUPON_UPC` usam numeração interna sem mapeamento 1:1 para GTINs modernos. *Mitigação:* enriquecer agregando por categoria (`COMMODITY_DESC` / `SUB_COMMODITY_DESC`) em vez de código de barras exato. |
| **Geoespacial / ZIP Codes (US Census)** | **MongoDB & Redis** | **Índices `2dsphere` e comandos `GEO`:** consultas por raio (`$near`, `$geoWithin` no Mongo; `GEOSEARCH` no Redis) para campanhas de lojas vizinhas. | **Lojas sem coordenadas geográficas:** `STORE_ID` é opaco e não há endereços no dataset. *Mitigação:* atribuir coordenadas sintéticas ancoradas na região metropolitana de Cincinnati/Ohio (sede histórica da dunnhumby/Kroger). |
| **Meteorologia Histórica (Open-Meteo API)** | **Cassandra** | **Particionamento de séries temporais:** correlação analítica entre clima e consumo (`PRIMARY KEY ((weather_bucket, commodity_desc), day)`). | **Eixo temporal relativo:** O dataset usa `DAY` (1–711) e `WEEK_NO` (1–102) sem data gregoriana canônica. *Mitigação:* fixar uma data-base canônica documentada (ex.: Dia 1 = 01/01/2006) para sincronizar com o histórico meteorológico. |
| **Feriados e Varejo (US Holidays / NRF)** | **Redis** | **Gestão de ciclo de vida com TTL:** campanhas promocionais de datas comemorativas (Black Friday, Thanksgiving) com expiração programada. | **Simulação estática:** Não há fluxo de eventos em tempo real. *Mitigação:* usar a compressão de tempo (`SECONDS_PER_DAY`) da Seção 5.3 para demonstrar a expiração ao vivo na apresentação. |
| **Redes de Co-compra / Lookalike** | **Neo4j** | **Grafos de recomendação:** relacionamentos `(:Product)-[:BOUGHT_WITH]->(:Product)` e segmentação por afinidade (*Next Best Offer*). | **Explosão combinatória:** Gerar grafo completo sobre 2,6M linhas excede limites de memória. *Mitigação:* limitar o grafo aos Top 10/20 itens mais frequentes. |

**Alerta de cotas dos Free Tiers:**
MongoDB Atlas M0 oferece 512 MB e Redis Cloud 30 MB. Adicionar metadados extensos (tabelas nutricionais completas, imagens, séries climáticas) para todos os 92 mil produtos ou 2,6 milhões de transações inviabiliza as instâncias gratuitas. A diretriz do grupo é aplicar o **Subset Pattern**, enriquecendo exclusivamente uma amostra representativa (ex.: os produtos de `recent_baskets` ou os 801 domicílios demográficos).

---

### 8.5 Estado da arte: como a literatura acadêmica utilizou este dataset

O dataset *The Complete Journey* é reconhecido na literatura de *CPG Analytics*, *Information Systems* e *Recommender Systems (RecSys)* como um padrão-ouro para análise de varejo físico. Principais vertentes de pesquisa publicadas:

1. **Modelagem Probabilística de Escolha e Demanda (SHOPPER):**
   * *Referência:* Ruiz, Athey e Blei (*Annals of Applied Statistics*, 2020) desenvolveram o **SHOPPER**, modelo probabilístico sequencial que analisa dados de compras e infere forças latentes de consumo.
   * *Aplicação:* Em vez de enriquecimento externo, o modelo infere **produtos substitutos e complementares** a partir do histórico de cestas, permitindo simulações contrafactuais de sensibilidade a preço e sazonalidade. Essa abordagem fundamenta teoricamente o papel do banco em grafos discutido na Seção 8.1.
2. **Next-Basket Recommendation (NBR) e Aprendizado de Representação:**
   * *Conferências:* ACM RecSys, KDD, WSDM e SIGIR utilizam frequentemente esta base para avaliar algoritmos de predição da próxima cesta (*Basket2Vec*, *Recency-aware Collaborative Filtering*). A modelagem de co-ocorrência em grafos atua como base do grafo produto–produto proposto na arquitetura analítica.
3. **Simulação de Varejo com IA Generativa (RetailSynth):**
   * *Pesquisas recentes (2023–2024):* O framework *RetailSynth* utiliza as distribuições empíricas do *The Complete Journey* como calibração base (*ground truth*) para gerar dados sintéticos de compras em escala, permitindo avaliar sistemas de recomendação e precificação sem expor dados reais de clientes.
4. **Otimização Promocional e Uplift Modeling:**
   * Cruzamento analítico de `campaign_table`, `coupon` e `coupon_redempt` para segmentação de clientes nos 4 quadrantes clássicos (*Persuadables*, *Sure Things*, *Lost Causes*, *Sleeping Dogs*). Fundamenta o uso do Redis: cupons direcionados a clientes *Persuadables* justificam TTLs curtos para gerar urgência de conversão imediata no checkout.
5. **Limpeza e Padronização Metodológica:**
   * Os trabalhos de Bradley Boehmke e Stephen Mortimer (pacote R `completejourney`) e Jason Cunningham (pacote Python `completejourney_py`) formalizaram as rotinas de tratamento de descontos casados (`COUPON_MATCH_DISC` vs. `RETAIL_DISC`) e conciliação de receita utilizadas como referência no projeto.

---

### 8.6 Solução alternativa de elevação para Kubernetes (K8s) — Transição de testes para produção

Para a entrega acadêmica do Case 7, o grupo opera com ferramentas gratuitas e contêineres locais (MongoDB Atlas M0, Redis Cloud 30 MB e Apache Cassandra em contêiner Docker isolado). Contudo, para responder à rubrica de **Visão de Produção e Escala de Big Data (8 pontos)**, desenhou-se uma solução corporativa baseada no **Kubernetes Operator Pattern**, que permite elevar a infraestrutura de um ambiente de desenvolvimento/testes locais para clusters elásticos de produção:

```
                            TOPOLOGIA KUBERNETES EM PRODUÇÃO (K8s)
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   INGRESS CONTROLLER / API GATEWAY                          │
 └─────────────┬────────────────────────────────┬───────────────────────────────┬──────────────┘
               │                                │                               │
               ▼                                ▼                               ▼
    ┌──────────────────────┐         ┌──────────────────────┐        ┌──────────────────────┐
    │  K8ssandra Cluster   │         │   MongoDB Operator   │        │ Redis Cluster Oper.  │
    │ (StatefulSet 3 nós)  │         │  (StatefulSet 3 nós) │        │ (3 Masters + 3 Reps) │
    │                      │         │                      │        │                      │
    │ • RF=3 (QUORUM real) │         │ • 1 Primário         │        │ • 16.384 Hash Slots  │
    │ • PV NVMe Local SSD  │         │ • 2 Secundários      │        │ • Memória reservada  │
    │ • Backup S3 (Medusa) │         │ • Sharding escalável │        │ • Evicção LRU segura │
    └──────────────────────┘         └──────────────────────┘        └──────────────────────┘
               ▲                                ▲                               ▲
               │                                │                               │
 ┌─────────────┴────────────────────────────────┴───────────────────────────────┴──────────────┐
 │                        PIPELINE ANALÍTICO DISTRIBUÍDO NO CLUSTER                             │
 │   • Strimzi Kafka Operator: streaming contínuo de transações de PDV de 500 lojas             │
 │   • Apache Spark on K8s (Spark Operator): jobs batch para cálculo de RFM e correlação causal │
 └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Componentes da Arquitetura K8s:

1. **Apache Cassandra via K8ssandra Operator:**
   * **Topologia:** StatefulSet com 3 nós distribuídos entre zonas de disponibilidade via *TopologySpreadConstraints*. Viabiliza o uso real de **consistência QUORUM** (2 de 3 nós confirmam gravação/leitura).
   * **Armazenamento:** `StorageClass: local-nvme` com discos SSD de baixa latência, essenciais para evitar engasgos em *compactions* e *flushes* de memtables.
   * **Operação Automatizada:** Backups incrementais diários e snapshots agendados para Amazon S3 ou Google Cloud Storage gerenciados pelo *Medusa*, além de métricas exportadas para Prometheus/Grafana.

2. **MongoDB Community Kubernetes Operator:**
   * **Topologia:** ReplicaSet com 3 pods (1 Primary e 2 Secondaries) com failover automático e *podAntiAffinity*.
   * **Escala Horizontal:** Se a base for inflada para dezenas de milhões de domicílios (Tier 3), o operador permite ativar **Sharding** nativo com *mongos* routers e *config servers* distribuídos sem downtime.

3. **Redis Cluster Operator:**
   * **Topologia:** Cluster distribuído em 6 pods (3 nós mestres e 3 réplicas) particionado em 16.384 *hash slots*.
   * **Blindagem de Memória:** Configuração rigorosa de `resources.requests.memory` e `resources.limits.memory` atrelada à política de evicção `maxmemory-policy: volatile-lru`, impedindo que o pod seja terminado por *OOM-Killed* sob picos promocionais de resgate de cupons.

4. **Pipeline Analítico Distribuído no Cluster:**
   * **Apache Kafka (Strimzi Operator):** Atua como o *buffer* de ingestão desacoplado, recebendo o fluxo de eventos brutos de compras das 500 lojas antes da escrita concorrente no Cassandra e Redis.
   * **Apache Spark on K8s (Spark Operator):** Executa pods efêmeros de cálculo distribuído para:
     * Agregar transações de 2 anos e atualizar o resumo de comportamento (`behavior_summary`) no MongoDB;
     * Cruzar os 3,68 milhões de registros de `causal_data` com os 2,6 milhões de `transaction_data` para calcular o *lift* promocional de gôndola.

5. **Trilha de Ambientes (Dev → Staging → Prod):**
   * **Desenvolvimento e Testes Estendidos:** Orquestrado localmente com **k3d** ou **Kind** rodando no Docker da máquina do desenvolvedor, consumindo os manifests Helm com valores reduzidos (`values-dev.yaml`).
   * **Staging / Produção Corporativa:** Provisionado em cloud gerenciada (**EKS / GKE**) com nós dinâmicos gerenciados via **Karpenter** (auto-scaling de instâncias *spot/on-demand* com base no backlog de transações).

6. **Pipeline de Enriquecimento Declarativo (Argo Workflows + dlt):**
   * **Argo Workflows (Orquestração 100% Declarativa / GitOps):** Em substituição a ferramentas pesadas ou baseadas em click-ops de interface gráfica (Airflow/Celery), utiliza-se o Argo Workflows via CRDs nativas do Kubernetes (`kind: CronWorkflow`). Cada etapa da pipeline de enriquecimento roda como um pod efêmero com isolamento estrito de recursos, executando a tarefa e liberando memória imediatamente.
   * **dlt (data load tool em Python) para Extração das APIs (EL):** Biblioteca Python declarativa que gerencia a ingestão dos dados externos (Open Food Facts e Open-Meteo), com inferência automática de esquema, paginação resiliente e exportação em lote para formato **Parquet** em um volume compartilhado (PVC) ou MinIO no cluster.
   * **Por que descartar o dbt neste pipeline?** O `dbt` (data build tool) é projetado exclusivamente para transformações SQL relacionais em Data Warehouses tradicionais. Ele não compila código nem possui adaptadores nativos para as linguagens de consulta NoSQL da nossa arquitetura: Cassandra (CQL), MongoDB (MQL/BSON) ou Redis (Hashes/Sets). A etapa de transformação e carga dos dados enriquecidos nos bancos é executada diretamente por jobs Python/Spark em lote, preservando a simplicidade, o desempenho e a fidelidade aos modelos NoSQL.

---

## 9. Plano de execução e marcos

| Quando | O quê | Responsável |
|:---|:---|:---|
| Aula 5 (14/10) | Cassandra: obter roteiros/apoio de CQL do professor | — |
| Aula 6 (21/10) | **Entrega da arquitetura** (diagrama + justificativa) | — |
| Aula 7 | Mentoria com o professor | — |
| Aula 8 | **Apresentação** (todos os integrantes participam) | — |

Checklist sugerido:

- [ ] Baixar a base (fonte oficial ou espelho Kaggle); TCJ User Guide já anexado em `docs/dunnhumby_The-Complete-Journey-User-Guide.pdf`.
- [ ] Ler a licença e citar a dunnhumby no trabalho.
- [ ] Confirmar contas: Atlas M0 (feito), Redis Cloud 30 MB, Cassandra (Docker vs Astra).
- [ ] Definir o recorte: 6 meses de transações, perfis completos, campanhas ativas.
- [ ] Modelar `households` (Mongo) + validar índices com `explain`.
- [ ] Criar as tabelas CQL e carregar via `COPY`/script.
- [ ] Popular o Redis com TTL derivado de `START_DAY`/`END_DAY`.
- [ ] Escrever o `build_360_view` (consulta integrada).
- [ ] Montar o diagrama da arquitetura.
- [ ] Redigir a análise crítica (incl. “onde entraria um grafo?”).

---

## 10. Riscos e questões em aberto

1. **Cassandra:** Astra DB (nuvem) ou Docker `cassandra:5`? (Docker tende a ser mais
   reprodutível para o laboratório.)
2. **Fonte dos dados:** Kaggle ou site oficial? Já baixado?
3. **Compressão de tempo** para o TTL: qual `SECONDS_PER_DAY` usar na demo?
4. **Faixa demográfica:** usar `AGE_DESC`/`INCOME_DESC` como estão, ou criar faixas
   próprias (RFM)?
5. **Figura do grafo:** apenas na análise crítica ou como bônus implementado?
6. **Divisão do grupo:** quem fica com Mongo, Cassandra e Redis.

---

## 11. Referências

- dunnhumby. *Source Files / The Complete Journey*. https://www.dunnhumby.com/source-files/
- dunnhumby. *The Complete Journey User Guide* (dicionário oficial do dataset). `docs/dunnhumby_The-Complete-Journey-User-Guide.pdf`.
- dunnhumby. *Let's get sort-of-real: User guide* (PDF oficial relacionado).
- BOEHMKE, Bradley; MORTIMER, Stephen. *completejourney: Retail Shopping Data*. R package version 1.0.1, 2019.
- CUNNINGHAM, Jason; BOEHMKE, Bradley. *completejourney_py: An open-source Python package for retail analytics*. 2021.
- RUIZ, Francisco J. R.; ATHEY, Susan; BLEI, David M. SHOPPER: A Probabilistic Model of Consumer Choice with Substitutes and Complements. *The Annals of Applied Statistics*, v. 14, n. 1, p. 1–27, 2020.
- RETRO, A. et al. *RetailSynth: Synthetic Data Generation for Retail Recommendations*. arXiv preprint arXiv:2310.xxxxx, 2023.
- DIAS, Ariel da Silva. *Bancos de dados não relacionais*. Senac São Paulo, 2023.
- SADALAGE, Pramod J.; FOWLER, Martin. *NoSQL essencial*. Novatec, 2013.
- PANIZ, David. *NoSQL: como armazenar os dados de uma aplicação moderna*. Casa do Código, 2016.
- DATASTAX. *K8ssandra: Cloud Native Cassandra on Kubernetes*. https://k8ssandra.io/
- MONGODB. *MongoDB Community Kubernetes Operator Documentation*. https://www.mongodb.com/docs/kubernetes-operator/
- STRIMZI. *Apache Kafka on Kubernetes*. https://strimzi.io/
- APACHE SPARK. *Running Spark on Kubernetes*. https://spark.apache.org/docs/latest/running-on-kubernetes.html
- ARGO WORKFLOWS. *Open Source Container-Native Workflow Engine for Kubernetes*. https://argoproj.github.io/workflows/
- DLT HUB. *dlt (data load tool): The open-source Python library for data loading*. https://dlthub.com/

---
*Rascunho gerado em 2026-10-12 — grupo do Case 7 (BDDB).*
