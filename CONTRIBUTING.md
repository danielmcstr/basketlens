# Guia de Contribuição, Testes e Extensão — BasketLens 360º

Este documento reúne as diretrizes para execução da suíte de testes automatizados, organização interna do código em `src/basketlens/` e as **quatro invariantes técnicas inegociáveis** que devem ser preservadas ao estender ou adicionar novas funcionalidades ao projeto.

---

## 1. Execução dos Testes Automatizados (`pytest`)

Toda a validação de regras de negócio, conformidade de esquemas NoSQL, simulação diária e integridade documental é executada via **pytest** dentro do ambiente virtual isolado `.venv`:

```bash
# Executar a suíte completa de testes
.venv/bin/pytest -v

# Executar apenas testes de entregáveis documentais, Dev Container e configuração
.venv/bin/pytest tests/test_e2e_deliverables.py tests/test_devcontainer.py tests/test_config.py -v

# Executar testes funcionais que exigem containers NoSQL ativos
.venv/bin/pytest tests/test_connections_and_schemas.py tests/test_ingestion.py tests/test_replay_and_queries.py -v
```

### Estrutura da Suíte de Testes (`tests/`)

| Arquivo de Teste | Escopo e Critérios Validados | Depende de Docker Ativo? |
|:---|:---|:---:|
| `test_e2e_deliverables.py` | Valida a existência e coerência de `docs/ARCHITECTURE.md`, `docs/BUSINESS_ANSWERS.md`, `README.md`, `CONTRIBUTING.md`, `LICENSE`, diagramas SVG e execução dos 4 notebooks. | Não |
| `test_devcontainer.py` | Valida a configuração do Dev Container (`.devcontainer/devcontainer.json`) e a idempotência do script `post-create.sh`. | Não |
| `test_config.py` | Valida a resolução de caminhos dos 8 CSVs, valores padrão e sobrescritas de ambiente via `Settings`. | Não |
| `test_connections_and_schemas.py` | Valida conectividade, HTTP 200 nas 3 Web UIs, criação idempotente de índices Mongo e tabelas CQL no Cassandra. | **Sim** |
| `test_ingestion.py` | Valida a carga documental no MongoDB (2.500 docs), 4 tabelas CQL no Cassandra e estado de referência no Redis. | **Sim** |
| `test_replay_and_queries.py` | Valida o checkout do Dia 654, resgate de cupom, rotação `$slice: -5`, expiração de TTL no Dia 657 e benchmark Cache-Aside. | **Sim** |

---

## 2. Organização Modular do Código (`src/basketlens/`)

O pacote `basketlens` segue arquitetura modular e desacoplada, organizada em 5 submódulos de responsabilidade única:

```text
src/basketlens/
├── config.py         # Configuração tipada com Pydantic Settings e resolução de paths
├── connections.py    # Fábricas de conexão com retry e healthcheck (MongoDB, Cassandra, Redis)
├── schemas/          # DDL idempotente, criação de índices B-Tree e namespaces canônicos
│   ├── mongo_schema.py       # 3 índices B-Tree e helper explain_query()
│   ├── cassandra_schema.py   # Keyspace basketlens e 4 tabelas orientadas à consulta
│   └── redis_schema.py       # Convenção canônica objeto:id e cálculo dinâmico de TTL
├── ingestion/        # Pipelines out-of-core de carga histórica completa (Modo A)
│   ├── pipeline.py           # Orquestrador run_full_ingestion()
│   ├── mongo_loader.py       # Agregação RFM e bulk_write de 2.500 domicílios
│   ├── cassandra_loader.py   # Ingestão em UNLOGGED BATCH de transações e dados causais
│   └── redis_loader.py       # Pipeline de campanhas/cupons ativos e vitrines semanais
├── replay/           # Motor de simulação operacional dia a dia (Modo B)
│   └── engine.py             # prepare_replay_baseline(), replay_day() e replay_range()
└── queries/          # Biblioteca de consulta com pushdown total aos bancos NoSQL
    ├── view_360.py           # build_360_view() unificada e benchmark_cache_aside_latency()
    └── business_questions.py # Perguntas 1, 2, 3 e consultas bônus de Trade Marketing
```

### Onde Adicionar Novas Funcionalidades?
- **Novas Consultas de Negócio:** Adicionar em `src/basketlens/queries/business_questions.py`, exportando a assinatura em `src/basketlens/queries/__init__.py`.
- **Novas Tabelas Cassandra:** Declarar o DDL em `src/basketlens/schemas/cassandra_schema.py` com sua chave de partição e ordenação física correspondente.
- **Novos Campos no Perfil:** Atualizar os agregadores em `src/basketlens/ingestion/mongo_loader.py` e os modelos Pydantic/índices em `src/basketlens/schemas/mongo_schema.py`.

---

## 3. As Quatro Invariantes Técnicas Obrigatórias

Ao estender ou modificar qualquer parte do projeto, as seguintes quatro regras de engenharia **devem ser estritamente mantidas**:

1. **Regra Estrita *Zero Full-Dataset In-Memory* (Polars):**
   - **Nunca** utilize `pl.read_csv()` diretamente sobre os arquivos grandes (`causal_data.csv` de 663 MiB ou `transaction_data.csv` de 135 MiB).
   - Use sempre `pl.scan_csv(...).collect(engine="streaming")` ou iteração em lotes `pl.read_csv_batched(..., batch_size=50_000)`. Toda filtragem temporal deve ser empurrada para a origem com `.filter(pl.col("DAY") == day)`.
2. **Proibição Estrita de `ALLOW FILTERING` no Apache Cassandra:**
   - Toda consulta CQL deve fornecer a `PARTITION KEY` completa ou ser atendida por uma tabela desnormalizada dedicada.
   - O uso de `ALLOW FILTERING` é proibido por violar as boas práticas de clusters distribuídos de alta vazão.
3. **Cobertura por Índices B-Tree no MongoDB (`EXPRESS_IXSCAN`):**
   - Toda busca pontual ou filtro analítico executado na coleção `households` deve ser coberto por um dos 3 índices B-Tree existentes (`idx_household_key_unique`, `idx_demographics_class1_class3` ou `idx_behavior_avg_weekly_spend_desc`).
   - Consultas com estágio `COLLSCAN` são consideradas falhas de engenharia e rejeitadas pela auditoria de planos `explain_query()`.
4. **Alinhamento de `TTL` Dinâmico e Invalidação Ativa no Redis:**
   - Toda chave efêmera de campanha ou cupom deve ter seu tempo de vida atrelado à fórmula oficial de vigência:
     $$\text{TTL} = \max(1, (\text{END\_DAY} - \text{reference\_day}) \times \text{SECONDS\_PER\_DAY})$$
   - Toda operação de compra ou resgate de cupom no replay diário deve disparar a invalidação imediata `DEL profile:{household_key}`, garantindo a coerência do padrão **Cache-Aside**.
