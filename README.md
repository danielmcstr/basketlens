<p align="center">
  <img src="docs/assets/logo.svg" alt="BasketLens 360º — Polyglot Customer Intelligence for Physical Retail" width="100%"/>
</p>

# BasketLens 360º — Inteligência Poliglota do Cliente para Varejo Físico

**BasketLens** é uma solução de **Persistência Poliglota** desenvolvida para o **Case 7 (*Fidelidade dunnhumby — Visão 360º do Cliente com Três Bancos*)** da disciplina **Big Data e NoSQL: Soluções de Armazenamento Inovadoras (BDDB)**, combinando **MongoDB 8.0**, **Apache Cassandra 5.0**, **Redis 7.4** e **Python + Polars** sobre a base oficial **dunnhumby — The Complete Journey** (~847 MB, 6,27 milhões de registros em 8 arquivos CSV).

---

## 1. Sobre o Projeto e Contexto do Problema

No varejo alimentar físico moderno, programas de fidelidade geram simultaneamente **cadastros ricos e heterogêneos de clientes**, **bilhões de eventos imutáveis de passagem de caixa (PDV) e auditoria de gôndola/tabloide**, e **decisões de elegibilidade promocional em tempo real** no momento do checkout. Tentar atender a esses três padrões de acesso concorrentes com um único banco de dados relacional ou monolítico leva a gargalos clássicos: *joins* custosos para montar a tela de CRM, degradação de escrita em séries temporais massivas e *cron jobs* lentos para expirar campanhas e cupons vencidos.

O **BasketLens 360º** resolve esse trilema por meio de uma arquitetura de **Persistência Poliglota**, onde cada família NoSQL assume exatamente a carga de trabalho para a qual foi projetada:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                 RESPONSABILIDADES DE ARMAZENAMENTO DA PERSISTÊNCIA POLIGLOTA                    │
├───────────────────────────────┬───────────────────────────────┬─────────────────────────────────┤
│    MongoDB 8.0 (CP · Docs)    │Apache Cassandra 5.0 (AP · Col)│      Redis 7.4 (AP · RAM)       │
├───────────────────────────────┼───────────────────────────────┼─────────────────────────────────┤
│ • Coleção `households` (2.500)│ • Keyspace `basketlens`       │ • Hashes `campanha:{id}` (TTL)  │
│ • 801 c/ demografia (Polimorf)│ • `transactions_by_household` │ • Hashes `cupom:{upc}` (TTL)    │
│ • 1.699 sem demografia        │ • `transactions_by_household_ │ • Sets `household:{id}:coupons` │
│ • `recent_baskets` ($slice:-5)│    product` (histórico SKU)   │ • String `profile:{id}`         │
│ • `behavior_summary` (RFM $inc│ • `sales_by_product_week`     │   (Cache-Aside SETEX 60s / DEL) │
│ • 3 índices B-Tree (0 ms)     │ • `causal_promotions_by_store`│ • ZSet `ranking:week:{w}`       │
└───────────────────────────────┴───────────────────────────────┴─────────────────────────────────┘
```

1. **Agregado do Perfil 360º (`MongoDB 8.0` · Documentos BSON · `CP`):** armazena os **2.500 domicílios** da base em documentos coesos (`households`), combinando **Esquema Polimórfico** (acomodando naturalmente os **801 domicílios** com demografia mapeada e os **1.699** sem demografia, sem colunas `NULL`), **Subset Pattern** (mantendo apenas as 5 cestas mais recentes em `recent_baskets` via `$slice: -5`), **Extended Reference Pattern** (itens enriquecidos com departamento e categoria) e **Computed Pattern** (`behavior_summary` atualizado incrementalmente via `$inc`).
2. **Séries Temporais de Transações e Promoções Físicas (`Apache Cassandra 5.0` · Colunas Largas · `AP`):** absorve os eventos *append-only* de compras (`2,59 milhões` de linhas) e de exposição em display/tabloide (`36,78 milhões` de linhas) em **4 tabelas CQL modeladas pela consulta (*Query-Driven Modeling*)**, com ordenação física decrescente em disco (`CLUSTERING ORDER BY ... DESC`) e **zero uso de `ALLOW FILTERING`**.
3. **Camada de Velocidade, Elegibilidade e Cache (`Redis 7.4` · Chave-Valor em RAM · `AP`):** governa em sub-milissegundo quais campanhas e cupons estão ativos **agora** através de **TTL nativo** proporcional à janela de vigência (`campanha:{id}`, `cupom:{upc}`, `household:{id}:campaigns`, `household:{id}:coupons`), além de acelerar a leitura do perfil 360º via padrão **Cache-Aside** (`profile:{id}`) com invalidação ativa (`DEL`) a cada nova compra.

### Engenharia *Out-of-Core* com Polars e Estudo de Caso Real (`John Smith #208`)
- **Regra Estrita *Zero Full-Dataset In-Memory*:** Toda a ingestão e simulação utiliza **Polars** em modo *lazy/streaming* (`pl.scan_csv(...).collect(engine="streaming")` e `pl.read_csv_batched`), processando centenas de megabytes e dezenas de milhões de registros com consumo constante de RAM.
- **Fio Condutor Empírico:** Toda a jornada analítica acompanha o cliente do estudo de caso oficial do guia da dunnhumby — **John Smith (`household_key = 208`)** — operando em **dois modos complementares**: **Modo A (Carga Histórica Completa `DAY 1..711`)** para análises globais de 2 anos e **Modo B (Event Replay Dia a Dia `DAY 649..657`)** para demonstrar em tempo real o checkout, o resgate do cupom `51800000050` no Dia 654, a rotação `$slice: -5`, a invalidação `DEL profile:208` e a expiração automática da Campanha 22 após o Dia 656.

---

### Resumo de Mapeamento da Rubrica Avaliativa

| Documento / Artefato | Conteúdo Principal | Critério da Rubrica Atendido |
|:---|:---|:---|
| [**`docs/ARCHITECTURE.md`**](docs/ARCHITECTURE.md) | 4 diagramas Draw.io SVG padronizados (Arquitetura Poliglota + Observabilidade, Modos A/B + Cache-Aside, Grafo Neo4j e Produção Kubernetes), justificativas de modelagem (MongoDB, Cassandra e Redis), matriz **CAP/Consistência** e **Análise Crítica**. | Arquitetura e Modelagem Justificadas (12 pts) + Análise Crítica (8 pts) |
| [**`docs/BUSINESS_ANSWERS.md`**](docs/BUSINESS_ANSWERS.md) | Respostas executivas e técnicas comentadas para as **3 perguntas obrigatórias de negócio** + **consultas bônus de Trade Marketing**, com planos `explain("executionStats")`, tabelas consolidadas das 801 famílias demográficas e benchmark de Cache-Aside. | Implementação Funcional com Dados Reais e Consultas (15 pts) + Apresentação (10 pts) |
| [**`docs/dunnhumby_The-Complete-Journey-User-Guide.pdf`**](docs/dunnhumby_The-Complete-Journey-User-Guide.pdf) | Guia oficial de referência da dunnhumby (dicionário das 8 tabelas, estudo de caso **John Smith `household_key = 208`** e fórmulas de preço/desconto). | Dicionário Oficial de Dados |

---

## 4. Arquitetura e Infraestrutura Local (`docker-compose.yml`)

Toda a infraestrutura roda 100% localmente via Docker Compose com versões fixadas (*pinned versions*), *healthchecks* nativos e **3 interfaces Web pré-configuradas (Zero Config / Sem Login)**:

| Serviço | Imagem Docker | Porta do Banco | Web UI Dedicada | URL da Web UI | Papel no BasketLens |
|:---|:---|:---:|:---|:---|:---|
| **MongoDB** | `mongo:8.0.4` | `localhost:27017` | `mongo-express` | **`http://localhost:8081`** | Coleção `households` (2.500 perfis 360º: 801 com `demographics` + 1.699 sem `demographics`, `behavior_summary` e `recent_baskets` com `$slice: -5`). |
| **Apache Cassandra** | `cassandra:5.0.2` | `localhost:9042` | `cassandra-web` | **`http://localhost:3000`** | Keyspace `basketlens` com 4 tabelas orientadas à consulta (`transactions_by_household`, `transactions_by_household_product`, `sales_by_product_week`, `causal_promotions_by_store_week`). |
| **Redis** | `redis:7.4.2-alpine` | `localhost:6379` | `redis-commander` | **`http://localhost:8082`** | Campanhas e cupons ativos com **TTL** proporcional à vigência (`campanha:{id}`, `cupom:{upc}`), elegibilidade (`household:{id}:campaigns`), Cache-Aside (`profile:{id}`) e vitrines semanais. |

---

## 5. Como Executar o Projeto Passo a Passo

### 5.1 Criar o Ambiente Virtual Python (`.venv`) e Instalar as Dependências
Na raiz do repositório, crie o ambiente virtual isolado `.venv`, ative-o e instale o pacote `basketlens` em modo editável junto com todas as dependências de execução e desenvolvimento (`polars`, `pymongo`, `cassandra-driver`, `redis`, `jupyterlab`, `pytest`, etc.):

```bash
# 1. Criar o ambiente virtual .venv (requer Python 3.11+)
python3 -m venv .venv

# 2. Ativar o ambiente virtual
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows (PowerShell / CMD)

# 3. Atualizar o pip e instalar o projeto + dependências (.[dev])
pip install --upgrade pip
pip install -e ".[dev]"

# 4. (Opcional) Registrar o kernel do .venv para uso no JupyterLab / VS Code
python -m ipykernel install --user --name basketlens --display-name "Python (.venv BasketLens)"
```

### 5.2 Subir a Infraestrutura Docker Compose
```bash
cp .env.example .env
docker compose up -d
docker compose ps
```
> O Cassandra leva cerca de 35–50 segundos para concluir o *bootstrap* inicial até atingir `healthy`. As Web UIs sobem automaticamente em `http://localhost:8081` (Mongo Express), `http://localhost:3000` (Cassandra Web) e `http://localhost:8082` (Redis Commander).

### 5.3 Verificar Conexões e Inicializar Schemas/Índices
```bash
.venv/bin/python -c "from basketlens import check_all_connections, initialize_all_schemas; print(check_all_connections()); print(initialize_all_schemas())"
```
---


## 8. Roteiro dos 4 Notebooks Demonstrativos (`notebooks/`)

Todos os 4 notebooks estão pré-executados e prontos para inspeção ou reexecução ao vivo:

1. [**`notebooks/01_eda_and_data_quality.ipynb`**](notebooks/01_eda_and_data_quality.ipynb) — **EDA Out-of-Core e Qualidade de Dados com Polars**: inventário dos 8 CSVs (39,6M linhas totais / 808 MiB), prova de que apenas 801 de 2.500 domicílios possuem `hh_demographic.csv`, inspeção dos códigos alfanuméricos de `causal_data.csv` e rastreamento do caso de estudo `household_key = 208`.
2. [**`notebooks/02_full_ingestion_setup.ipynb`**](notebooks/02_full_ingestion_setup.ipynb) — **Modo A (Ingestão Poliglota Completa até `DAY = 711`)**: executa `check_all_connections()`, `initialize_all_schemas()`, `run_full_ingestion()` e `explain_query()`, comprovando a carga dos 2.500 documentos no MongoDB, 4 tabelas CQL no Cassandra, estado ativo no Redis e planos `EXPRESS_IXSCAN` / `IXSCAN`.
3. [**`notebooks/03_event_replay_streaming.ipynb`**](notebooks/03_event_replay_streaming.ipynb) — **Modo B (Event Replay Dia a Dia: `DAY = 649 .. 657`)**: executa `prepare_replay_baseline()`, `replay_range()`, `replay_day(654)`, `build_360_view(208)`, `get_household_product_history(208, 1017772)` e `restore_full_historical_state()`, demonstrando o resgate do cupom `51800000050`, a rotação `$slice: -5`, a invalidação `DEL profile:208` e a expiração automática da Campanha 22 no Dia 657.
4. [**`notebooks/04_polyglot_360_analytics.ipynb`**](notebooks/04_polyglot_360_analytics.ipynb) — **Visão 360º e Respostas Executivas às 3 Perguntas + Bônus Trade Marketing**: executa `build_360_view()`, `benchmark_cache_aside_latency()`, `get_household_profile_and_recent_history()`, `get_active_campaigns_for_household()`, `get_avg_weekly_spend_by_demographic()` (`classification_1` e `classification_3`), `get_product_causal_promotion_lift()` e `get_store_weekly_showcase()`.

---

## 9. Testes Automatizados (`pytest`)

Para executar toda a suíte de validação fim a fim (configuração, conexões, schemas/índices, ingestão Polars, Event Replay, consultas 360º e validação dos entregáveis documentais):
```bash
.venv/bin/pytest -v
```

---

## 10. Fonte dos Dados e Citação Oficial de Licença

Este projeto utiliza o dataset público **dunnhumby — The Complete Journey**, disponibilizado gratuitamente pela **dunnhumby** para fins acadêmicos, científicos e educacionais mediante aceite dos termos de uso oficiais:

- **Fonte Oficial:** dunnhumby Source Files — *The Complete Journey* (`https://www.dunnhumby.com/source-files/`)
- **Espelho Público:** Kaggle (`https://www.kaggle.com/datasets/frtgnn/dunnhumby-the-complete-journey`)
- **Citação Obrigatória:**
  > *dunnhumby (2023). "The Complete Journey: Retail Shopping Dataset & User Guide". Disponível em: https://www.dunnhumby.com/source-files/. Utilizado exclusivamente para fins acadêmicos na disciplina Big Data e NoSQL.*
