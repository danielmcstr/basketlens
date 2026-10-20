## Context

O projeto **BasketLens 360º** já possui toda a implementação funcional em `src/basketlens/`, os 4 Jupyter Notebooks executados em `notebooks/` e os 4 diagramas SVG em `docs/assets/`. Contudo, após edições iterativas:
1. O `README.md` ficou com numeração descontínua (`1`, `4`, `5`, `8`, `9`, `10`), manteve um quadro ASCII redundante na Seção 1 e ainda inclui seções de testes e licença que pertencem a `CONTRIBUTING.md` e `LICENSE`.
2. O `docs/ARCHITECTURE.md` repete a descrição dos três bancos em quatro pontos distintos (lista da Seção 1, tabela da Seção 1.1, Seção 3 e tabela CAP da Seção 4), mantém um bloco `mermaid` duplicado na Seção 5.1 e ainda não incorpora explicitamente as 3 nuances físicas do dataset (*assimetria de volume*, *cobertura demográfica 801/2.500 + códigos alfanuméricos* e *fórmulas de preço/desconto do PDV*) que antes estavam no `README.md`.

## Goals / Non-Goals

**Goals:**
- Tornar o `README.md` uma porta de entrada enxuta, de alto nível e com numeração sequencial (`1` a `5`), guiando o leitor para `docs/ARCHITECTURE.md`, depois para `docs/BUSINESS_ANSWERS.md`, para o setup reproduzível e para o roteiro dos 4 notebooks.
- Reescrever `docs/ARCHITECTURE.md` aplicando *grounding* progressivo (`writing-beats` / `writing-shape`) em **6 seções encadeadas**, sem repetição de tabelas, sem jargão solto (*slop*) e sem blocos `mermaid` redundantes, mantendo os 4 diagramas SVG existentes em `docs/ARCHITECTURE.md`.
- Extrair diretrizes de testes (`pytest`) e regras de extensão da biblioteca para `CONTRIBUTING.md`.
- Formalizar a licença estritamente didática/acadêmica (uso comercial não autorizado) no arquivo `LICENSE` e em `pyproject.toml`.

**Non-Goals:**
- Não alterar código de negócio em `src/basketlens/` nem reexecutar os notebooks `01` a `04`.
- Não alterar os números ou evidências empíricas já consolidados em `docs/BUSINESS_ANSWERS.md`.

## Decisions

### 1. Estrutura Enxuta do `README.md` (5 Seções Sequenciais)
- **Seção 1 (`## 1. Sobre o Projeto e Contexto do Problema`)**: Apresenta o problema de negócio no varejo alimentar físico, a abordagem de Persistência Poliglota nos 3 motores (**MongoDB 8.0 `CP`**, **Apache Cassandra 5.0 `AP`** e **Redis 7.4 `AP`**), a engenharia *out-of-core* com **Polars** e o estudo de caso **John Smith (`household_key = 208`)**, removendo o quadro ASCII redundante.
- **Seção 2 (`## 2. Trilha da Documentação: Arquitetura e Respostas de Negócio`)**: Ponte narrativa em dois passos claros — (1) apontando para [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) para todos os detalhes técnicos, nuances das bases e diagramas; e (2) apontando para [`docs/BUSINESS_ANSWERS.md`](docs/BUSINESS_ANSWERS.md) para os resultados reais das 3 perguntas do professor + bônus de Trade Marketing — seguida da tabela enxuta de mapeamento da rubrica.
- **Seção 3 (`## 3. Infraestrutura Local (docker-compose.yml)`)**: Tabela dos 3 containers de banco e suas 3 Web UIs Zero-Config (`:8081`, `:3000`, `:8082`).
- **Seção 4 (`## 4. Como Executar o Projeto Passo a Passo`)**: Comandos reproduzíveis para `.venv`, `docker compose up -d` e inicialização de schemas/índices.
- **Seção 5 (`## 5. Roteiro dos 4 Notebooks Demonstrativos (notebooks/)`)**: Inventário dos 4 notebooks e dos métodos-chave de `src/basketlens/` demonstrados em cada um, encerrando com uma nota direcionando para [`CONTRIBUTING.md`](CONTRIBUTING.md) para execução da suíte `pytest` e extensão de módulos.

### 2. Narrativa Didática em 6 Beats para `docs/ARCHITECTURE.md`
Aplicando os princípios de *Grounding* (`writing-beats`) e escolha deliberada de formato (`writing-shape`):
- **Seção 1 — Visão Geral da Arquitetura e as 3 Realidades Físicas do Dataset**:
  - Exibe `assets/arch-polyglot-overview.svg`.
  - Aterra as **3 nuances de domínio da base *The Complete Journey*** que motivam cada decisão subsequente:
    1. *Assimetria de Volumetria (98,88% concentrados em `causal_data.csv` e `transaction_data.csv`)* $\rightarrow$ fundamenta a regra estrita **Zero Full-Dataset In-Memory** via `pl.scan_csv(..., streaming=True)` e `pl.read_csv_batched`.
    2. *Heterogeneidade Demográfica (`801` de `2.500` famílias em `hh_demographic.csv`) e Códigos Alfanuméricos Promocionais (`display` e `mailer` em `causal_data.csv`)* $\rightarrow$ fundamenta o esquema polimórfico no MongoDB e a tipagem `text` no Cassandra.
    3. *Decomposição Financeira de Preços e Descontos no PDV (`SALES_VALUE`, `RETAIL_DISC`, `COUPON_DISC`, `COUPON_MATCH_DISC`)* $\rightarrow$ fundamenta as métricas de receita líquida, desconto de fidelidade e resgate de cupom para a persona **John Smith (`household_key = 208`)**.
- **Seção 2 — Por Que Três Motores? Do Padrão de Acesso ao Teorema CAP**:
  - Unifica a antiga tabela 1.1 e a antiga Seção 4 em **uma única Matriz Arquitetural e CAP/Consistência**, contrastando papel (*System of Record* vs. *Speed Layer*), classificação CAP (`CP` vs. `AP`), configuração de consistência (`w: 1`/`"majority"` no MongoDB; `ONE` analítico vs. `LOCAL_QUORUM` `R + W > N` no Cassandra; `TTL` + `DEL` no Redis) e o *trade-off* de negócio no PDV.
- **Seção 3 — Modelagem Física em Disco e Memória**:
  - **3.1 MongoDB (`households`)**: explica de forma direta os 4 padrões (*Polymorphic Schema*, *Subset Pattern* com `$slice: -5`, *Extended Reference Pattern* e *Computed Pattern*) e os 3 índices B-Tree (`idx_household_key_unique`, `idx_demographics_class1_class3`, `idx_behavior_avg_weekly_spend_desc`).
  - **3.2 Apache Cassandra (`basketlens`)**: tabela das 4 tabelas CQL (`transactions_by_household`, `transactions_by_household_product`, `sales_by_product_week`, `causal_promotions_by_store_week`), chaves de partição/clustering e por que `ALLOW FILTERING` é proibido.
  - **3.3 Redis (`objeto:id`)**: tabela dos 7 padrões de chave e fórmula de `TTL = max(1, (END_DAY - ref_day) * SECONDS_PER_DAY)`.
- **Seção 4 — O Sistema em Movimento: Modo A (Batch) vs. Modo B (Event Replay) e Ciclo Cache-Aside**:
  - Exibe `assets/arch-operational-modes.svg`.
  - Narra como os schemas da Seção 3 operam em conjunto nos dois modos (**Modo A** em `cutoff_day = 711` / `REFERENCE_DAY = 650` vs. **Modo B** avançando `DAY 649 -> 650..657`), detalhando os 4 passos diários e o ciclo **Cache-Aside** (`GET profile:208` $\rightarrow$ *Cache Miss* no MongoDB $\rightarrow$ `SETEX 60s` $\rightarrow$ invalidação `DEL profile:208` na compra do Dia 654 e expiração da Campanha 22 no Dia 657).
- **Seção 5 — Análise Crítica: Fronteira de Grafos (Neo4j) e Escala Corporativa (Kubernetes)**:
  - **5.1 Onde Entraria um Banco de Grafos (`Neo4j`)?**: exibe apenas `assets/arch-neo4j-graph.svg` (sem o bloco `mermaid` duplicado), detalha os 3 casos de travessia multi-salto (`BOUGHT_WITH`, atribuição/*halo effect* e *Lookalike* via GDS) e explica por que as Perguntas 1, 2 e 3 são resolvidas em `O(1)` / `O(log N)` sem grafo.
  - **5.2 Limitações Locais e Evolução para Produção em Kubernetes (`K8s`)**: conecta cada limitação do setup local (*amostra demográfica de 32%*, *dual-write coordenado pela aplicação* e *instâncias single-node*) diretamente à arquitetura em `assets/arch-kubernetes-production.svg` (*Strimzi Kafka + Outbox/CDC*, *K8ssandra Operator RF=3 LOCAL_QUORUM*, *MongoDB Operator ReplicaSet*, *Redis Cluster* e *Argo Workflows* + `dlt`).

### 3. Separação de `CONTRIBUTING.md` e `LICENSE`
- **`CONTRIBUTING.md`**: concentra comandos de verificação (`.venv/bin/pytest -v`), mapa de módulos em `src/basketlens/` e checklist de invariantes para novos recursos.
- **`LICENSE` e `pyproject.toml`**: formalizam que o código e os artefatos têm finalidade exclusivamente didática/acadêmica (uso comercial proibido) e preservam os créditos e termos do dataset *dunnhumby — The Complete Journey*.

## Risks / Trade-offs

- **[Risco] Quebra de testes documentais em `tests/test_e2e_deliverables.py` após enxugamento do `README.md`** → **Mitigação**: Atualizar `test_readme_documents_setup_web_uis_notebooks_and_citation` para validar as seções enxutas do `README.md` e adicionar verificações explícitas para `CONTRIBUTING.md` e `LICENSE`, mantendo 100% das palavras-chave obrigatórias em `docs/ARCHITECTURE.md` e `docs/BUSINESS_ANSWERS.md`.
