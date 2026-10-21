<p align="center">
  <img src="docs/assets/logo.svg" alt="BasketLens 360º — Polyglot Customer Intelligence for Physical Retail" width="100%"/>
</p>

# BasketLens 360º — Inteligência Poliglota do Cliente para Varejo Físico

**BasketLens** é uma solução de **Persistência Poliglota** desenvolvida para o **Case 7 (*Fidelidade dunnhumby — Visão 360º do Cliente com Três Bancos*)** da disciplina **Big Data e NoSQL: Soluções de Armazenamento Inovadoras (BDDB)**, combinando **MongoDB 8.0**, **Apache Cassandra 5.0**, **Redis 7.4** e **Python + Polars** sobre a base oficial **dunnhumby — The Complete Journey** (~847 MB, 6,27 milhões de registros em 8 arquivos CSV).

---

## 1. Sobre o Projeto e Contexto do Problema

No varejo alimentar físico moderno, programas de fidelidade geram simultaneamente **cadastros ricos e heterogêneos de clientes**, **bilhões de eventos imutáveis de passagem de caixa (PDV) e auditoria de gôndola/tabloide**, e **decisões de elegibilidade promocional em tempo real** no momento do checkout. Tentar atender a esses três padrões de acesso concorrentes com um único banco de dados relacional ou monolítico leva a gargalos clássicos: *joins* custosos para montar a tela de CRM, degradação de escrita em séries temporais massivas e *cron jobs* lentos para expirar campanhas e cupons vencidos.

O **BasketLens 360º** resolve esse trilema por meio de uma arquitetura de **Persistência Poliglota**, onde cada família NoSQL assume exatamente a carga de trabalho para a qual foi projetada:

1. **Agregado do Perfil 360º (`MongoDB 8.0` · Documentos BSON):** materializa os **2.500 domicílios** da base em documentos coesos (`households`), combinando **Esquema Polimórfico** (acomodando naturalmente os **801 domicílios** com demografia mapeada e os **1.699** sem demografia, sem colunas `NULL`), **Subset Pattern** (mantendo apenas as 5 cestas mais recentes em `recent_baskets` via `$slice: -5`), **Extended Reference Pattern** (itens enriquecidos com departamento e categoria) e **Computed Pattern** (`behavior_summary` atualizado incrementalmente via `$inc`). Essa é uma projeção do histórico, não a fonte canônica dos eventos brutos.
2. **Séries Temporais de Transações e Promoções Físicas (`Apache Cassandra 5.0` · Colunas Largas):** absorve os eventos *append-only* de compras (`2,59 milhões` de linhas) e de exposição em display/tabloide (`36,78 milhões` de linhas) em **4 tabelas CQL modeladas pela consulta (*Query-Driven Modeling*)**, com ordenação de clustering decrescente e **zero uso de `ALLOW FILTERING`**.
3. **Camada de Velocidade, Elegibilidade e Cache (`Redis 7.4` · Chave-Valor em RAM):** mantém estado efêmero de campanhas e cupons através de **TTL nativo** proporcional à janela de vigência (`campanha:{id}`, `cupom:{upc}`, `household:{id}:campaigns`, `household:{id}:coupons`), além de acelerar a leitura do perfil 360º via padrão **Cache-Aside** (`profile:{id}`) com invalidação ativa (`DEL`) a cada nova compra. Latências devem ser demonstradas por benchmark reproduzível.

### Engenharia *Out-of-Core* com Polars e Estudo de Caso Real (`John Smith #208`)
- **Processamento Out-of-Core:** Toda a ingestão e simulação utiliza **Polars** em modo *lazy/streaming* (`pl.scan_csv(...).collect(engine="streaming")` e `pl.read_csv_batched`), evitando carregar intencionalmente os CSVs brutos completos. O consumo de RAM ainda depende de joins, agregações e materialização de intermediários.
- **Fio Condutor Empírico:** Toda a jornada analítica acompanha o cliente do estudo de caso oficial do guia da dunnhumby — **John Smith (`household_key = 208`)** — operando em **dois modos complementares**: **Modo A (Carga Histórica Completa `DAY 1..711`)** para análises globais de 2 anos e **Modo B (Event Replay Dia a Dia `DAY 649..657`)** para demonstrar em tempo real o checkout, o resgate do cupom `51800000050` no Dia 654, a rotação `$slice: -5`, a invalidação `DEL profile:208` e a expiração automática da Campanha 22 após o Dia 656.

---

## 2. Trilha da Documentação: Arquitetura e Respostas de Negócio

Para navegar pelo projeto com todo o contexto conceitual, técnico e empírico, a documentação oficial está organizada em dois documentos centrais:

1. [**`docs/ARCHITECTURE.md`**](docs/ARCHITECTURE.md) — **Arquitetura Poliglota, Modelagem NoSQL e Análise Crítica:**
   - Fundamenta as decisões de engenharia através dos **diagramas em Draw.io SVG** (`arch-polyglot-overview.svg`, `arch-operational-modes.svg`, `arch-neo4j-graph.svg` e `arch-kubernetes-production.svg`).
   - Apresenta as **3 nuances físicas da base *The Complete Journey*** (assimetria de volume com Polars *out-of-core*, cobertura demográfica parcial de 801/2.500 famílias com códigos alfanuméricos e decomposição de preços/descontos no PDV).
   - Detalha a matriz **CAP/Consistência**, a modelagem física em cada motor (**MongoDB**, **Cassandra** e **Redis**), o ciclo **Cache-Aside** e a análise crítica (**Neo4j** como sidecar analítico e evolução corporativa em **Kubernetes**).
2. [**`docs/BUSINESS_ANSWERS.md`**](docs/BUSINESS_ANSWERS.md) — **Respostas Executivas e Evidências Empíricas:**
   - Apresenta as respostas completas e planos de execução reais para as **3 perguntas obrigatórias do professor** + **consultas bônus de Trade Marketing**:
     - **Pergunta 1:** Perfil 360º de John Smith (`#208`), plano indexado observado no ambiente de teste e benchmark de Cache-Aside com condições reproduzíveis.
     - **Pergunta 2:** Elegibilidade em tempo real com TTL dinâmico no Dia 650 e auditoria dia a dia do Event Replay (`DAY 650..657`).
     - **Pergunta 3:** Gasto semanal médio das 801 famílias demográficas agrupadas por faixa etária (`classification_1`) e nível de renda (`classification_3`).
     - **Bônus:** Lift promocional de gôndola/tabloide (+347,56% no SKU 862349 e replicação da Semana 40 do SKU 72717).

### Resumo de Mapeamento da Rubrica Avaliativa

| Documento / Artefato | Conteúdo Principal | Critério da Rubrica Atendido |
|:---|:---|:---|
| [**`docs/ARCHITECTURE.md`**](docs/ARCHITECTURE.md) | Diagramas Draw.io SVG padronizados, nuances físicas do dataset, justificativas de modelagem (MongoDB, Cassandra e Redis), matriz **CAP/Consistência** e **Análise Crítica** (Neo4j + Kubernetes). | Arquitetura e Modelagem Justificadas (12 pts) + Análise Crítica (8 pts) |
| [**`docs/BUSINESS_ANSWERS.md`**](docs/BUSINESS_ANSWERS.md) | Respostas executivas e técnicas comentadas para as **3 perguntas obrigatórias de negócio** + **consultas bônus de Trade Marketing**, com planos `explain("executionStats")`, tabelas consolidadas das 801 famílias demográficas e benchmark de Cache-Aside. | Implementação Funcional com Dados Reais e Consultas (15 pts) + Apresentação (10 pts) |
| [**`docs/dunnhumby_The-Complete-Journey-User-Guide.pdf`**](docs/dunnhumby_The-Complete-Journey-User-Guide.pdf) | Guia oficial de referência da dunnhumby (dicionário das 8 tabelas, estudo de caso **John Smith `household_key = 208`** e fórmulas de preço/desconto). | Dicionário Oficial de Dados |

---

## 3. Infraestrutura Local (`docker-compose.yml`)

Toda a infraestrutura roda 100% localmente via Docker Compose com versões fixadas (*pinned versions*), *healthchecks* nativos e **3 interfaces Web pré-configuradas (Zero Config / Sem Login)**:

| Serviço | Imagem Docker | Porta do Banco | Web UI Dedicada | URL da Web UI | Papel no BasketLens |
|:---|:---|:---:|:---|:---|:---|
| **MongoDB** | `mongo:8.0.4` | `localhost:27017` | `mongo-express` | **`http://localhost:8081`** | Coleção `households` (2.500 perfis 360º: 801 com `demographics` + 1.699 sem `demographics`, `behavior_summary` e `recent_baskets` com `$slice: -5`). |
| **Apache Cassandra** | `cassandra:5.0.2` | `localhost:9042` | `cassandra-web` | **`http://localhost:3000`** | Keyspace `basketlens` com 4 tabelas orientadas à consulta (`transactions_by_household`, `transactions_by_household_product`, `sales_by_product_week`, `causal_promotions_by_store_week`). |
| **Redis** | `redis:7.4.2-alpine` | `localhost:6379` | `redis-commander` | **`http://localhost:8082`** | Campanhas e cupons ativos com **TTL** proporcional à vigência (`campanha:{id}`, `cupom:{upc}`), elegibilidade (`household:{id}:campaigns`), Cache-Aside (`profile:{id}`) e vitrines semanais. |

---

## 4. Como Executar o Projeto Passo a Passo

### 4.1 Criar o Ambiente Virtual Python (`.venv`) e Instalar as Dependências
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

### 4.2 Subir a Infraestrutura Docker Compose
```bash
cp .env.example .env
docker compose up -d
docker compose ps
```
> O Cassandra leva cerca de 35–50 segundos para concluir o *bootstrap* inicial até atingir `healthy`. As Web UIs sobem automaticamente em `http://localhost:8081` (Mongo Express), `http://localhost:3000` (Cassandra Web) e `http://localhost:8082` (Redis Commander).

### 4.3 Verificar Conexões e Inicializar Schemas/Índices
```bash
.venv/bin/python -c "from basketlens import check_all_connections, initialize_all_schemas; print(check_all_connections()); print(initialize_all_schemas())"
```

---

## 5. Roteiro dos 4 Notebooks Demonstrativos (`notebooks/`)

Todos os 4 notebooks estão pré-executados e prontos para inspeção ou reexecução ao vivo durante a apresentação:

1. [**`notebooks/01_eda_and_data_quality.ipynb`**](notebooks/01_eda_and_data_quality.ipynb) — **EDA Out-of-Core e Qualidade de Dados com Polars**: inventário dos 8 CSVs (39,6M linhas totais / 808 MiB), prova de que apenas 801 de 2.500 domicílios possuem `hh_demographic.csv`, inspeção dos códigos alfanuméricos de `causal_data.csv` e rastreamento do caso de estudo `household_key = 208`.
2. [**`notebooks/02_full_ingestion_setup.ipynb`**](notebooks/02_full_ingestion_setup.ipynb) — **Modo A (Ingestão Poliglota Completa até `DAY = 711`)**: executa [`check_all_connections()`](src/basketlens/connections.py), [`initialize_all_schemas()`](src/basketlens/schemas/__init__.py), [`run_full_ingestion()`](src/basketlens/ingestion/pipeline.py) e [`explain_query()`](src/basketlens/schemas/mongo_schema.py), comprovando a carga dos 2.500 documentos no MongoDB, 4 tabelas CQL no Cassandra, estado ativo no Redis e planos `EXPRESS_IXSCAN` / `IXSCAN`.
3. [**`notebooks/03_event_replay_streaming.ipynb`**](notebooks/03_event_replay_streaming.ipynb) — **Modo B (Event Replay Dia a Dia: `DAY = 649 .. 657`)**: executa [`prepare_replay_baseline()`](src/basketlens/replay/engine.py), [`replay_range()`](src/basketlens/replay/engine.py), [`replay_day(654)`](src/basketlens/replay/engine.py), [`build_360_view(208)`](src/basketlens/queries/view_360.py), [`get_household_product_history(208, 1017772)`](src/basketlens/queries/business_questions.py) e [`restore_full_historical_state()`](src/basketlens/replay/engine.py), demonstrando o resgate do cupom `51800000050`, a rotação `$slice: -5`, a invalidação `DEL profile:208` e a expiração automática da Campanha 22 no Dia 657.
4. [**`notebooks/04_polyglot_360_analytics.ipynb`**](notebooks/04_polyglot_360_analytics.ipynb) — **Visão 360º e Respostas Executivas às 3 Perguntas + Bônus Trade Marketing**: executa [`build_360_view()`](src/basketlens/queries/view_360.py), [`benchmark_cache_aside_latency()`](src/basketlens/queries/view_360.py), [`get_household_profile_and_recent_history()`](src/basketlens/queries/business_questions.py), [`get_active_campaigns_for_household()`](src/basketlens/queries/business_questions.py), [`get_avg_weekly_spend_by_demographic()`](src/basketlens/queries/business_questions.py) e [`get_product_causal_promotion_lift()`](src/basketlens/queries/business_questions.py), acompanhados de gráficos visuais interativos.

> **Extensão do Projeto e Testes:** Para executar a suíte de testes automatizados (`.venv/bin/pytest -v`), consultar a arquitetura de pacotes de `src/basketlens/` ou conhecer as 4 invariantes técnicas do projeto, consulte o [**`CONTRIBUTING.md`**](CONTRIBUTING.md).
> **Termos de Uso e Licença:** O código e os dados deste repositório destinam-se exclusivamente para fins didáticos e educacionais (uso comercial não autorizado). Consulte o arquivo [**`LICENSE`**](LICENSE).
