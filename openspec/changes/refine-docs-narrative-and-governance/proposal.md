## Why

O `README.md` e o `docs/ARCHITECTURE.md` acumularam redundâncias entre si (repetindo explicações sobre os 3 bancos em múltiplas tabelas e seções), enquanto diretrizes de contribuição/extensão (`pytest` e invariantes de código) e os termos de licença estritamente didática/não-comercial precisavam ser desacoplados em arquivos próprios (`CONTRIBUTING.md` e `LICENSE`). Esta mudança reorganiza a documentação em uma trilha clara, didática e sem repetição para a apresentação final do projeto.

## What Changes

- **Refinamento e enxugamento do `README.md`**:
  - Organizar o documento em 5 seções numeradas sequencialmente (`1` a `5`): (1) Introdução, Contexto do Problema e Abordagem Poliglota de alto nível; (2) Ponte Narrativa contextualizada apontando primeiro para `docs/ARCHITECTURE.md` e depois para `docs/BUSINESS_ANSWERS.md` + tabela da rubrica; (3) Infraestrutura Local (`docker-compose.yml` e 3 Web UIs); (4) Passo a Passo Reprodutível de Setup (`.venv`, Docker Compose e schemas); e (5) Roteiro dos 4 Notebooks Demonstrativos (`notebooks/01` a `04`) com referência a `CONTRIBUTING.md`.
  - Remover do `README.md` a seção de licença (que passa a ser papel exclusivo do arquivo `LICENSE`) e mover os detalhes de execução de testes/extensão para `CONTRIBUTING.md`.
- **Reescrita narrativa e didática de `docs/ARCHITECTURE.md` (6 Beats sem repetição)**:
  - Estruturar o documento em uma progressão lógica (*grounding* progressivo):
    1. **Visão Geral e Nuances de Domínio das Bases (*The Complete Journey*)**: diagrama `assets/arch-polyglot-overview.svg` acompanhado das 3 nuances físicas do dataset que justificam a arquitetura (assimetria de volume e regra *Zero Full-Dataset In-Memory* com Polars; cobertura demográfica parcial de `801`/`2.500` e códigos alfanuméricos `display`/`mailer` como `text`; e decomposição financeira de preços e descontos no PDV para a persona `household_key = 208`).
    2. **Do Padrão de Acesso ao Teorema CAP (Matriz Consolidada)**: fusão das tabelas de racional por família NoSQL e de decisão CAP/Consistência (`CP` com `w: 1`/`"majority"` no MongoDB, `AP` com `ONE` vs. `LOCAL_QUORUM` no Cassandra, e `AP` em RAM com `TTL` no Redis) em uma narrativa única e sem duplicação.
    3. **Modelagem Física em Disco e Memória**: justificativa direta dos 4 *design patterns* e 3 índices B-Tree no MongoDB (`households`), das 4 tabelas CQL sem `ALLOW FILTERING` no Cassandra (`basketlens`) e dos 7 padrões de chave com `TTL` dinâmico no Redis.
    4. **O Sistema em Movimento (Modo A Batch vs. Modo B Event Replay e Ciclo Cache-Aside)**: diagrama `assets/arch-operational-modes.svg`, máquina de estados diária em 4 passos (`DAY 649..657`), ciclo `GET`/`SETEX`/`DEL profile:208` e linha do tempo de John Smith (`#208`).
    5. **Análise Crítica I — Onde Entraria um Banco de Grafos (Neo4j)?**: diagrama `assets/arch-neo4j-graph.svg` (removendo o bloco `mermaid` redundante), os 3 casos de uso de travessia multi-salto (`BOUGHT_WITH`, atribuição/*halo effect* e *Lookalike* via GDS) e por que as 3 perguntas obrigatórias não exigem grafo.
    6. **Análise Crítica II — Das Limitações Locais à Produção Corporativa em Kubernetes**: conexão direta entre os limites do ambiente local (amostra de 32%, *dual-write* na aplicação e *single-node*) e sua resolução cloud-native em `assets/arch-kubernetes-production.svg` (*Strimzi Kafka + Outbox/CDC*, *K8ssandra RF=3 LOCAL_QUORUM*, *MongoDB Operator*, *Redis Cluster* e *Argo Workflows*).
- **Criação de `CONTRIBUTING.md`**:
  - Documentar a execução da suíte de testes automatizados (`.venv/bin/pytest -v`), a arquitetura de pacotes em `src/basketlens/` e as diretrizes técnicas obrigatórias para quem desejar estender o projeto.
- **Criação de `LICENSE` e atualização de `pyproject.toml` (Fim Didático / Não-Comercial)**:
  - Criar `LICENSE` estipulando uso estritamente didático, acadêmico e científico (vedado o uso comercial), incluindo os termos e a citação oficial do dataset *dunnhumby — The Complete Journey*.
  - Atualizar `pyproject.toml` removendo `MIT` e declarando licença de uso exclusivamente educacional/acadêmico (não-comercial).
- **Atualização da suíte de verificação (`tests/test_e2e_deliverables.py`)**:
  - Alinhar os testes documentais com a nova divisão entre `README.md`, `docs/ARCHITECTURE.md`, `docs/BUSINESS_ANSWERS.md`, `CONTRIBUTING.md` e `LICENSE`.
- **Fora de escopo (Out of Scope)**:
  - Alterações na lógica de ingestão, replay ou queries em `src/basketlens/`;
  - Alterações em `docker-compose.yml` ou nos dados de `docs/BUSINESS_ANSWERS.md`.

## Capabilities

### New Capabilities
- `project-governance-and-contributing`: Guia de contribuição, extensão e testes (`CONTRIBUTING.md`) e licenciamento estritamente didático/não-comercial (`LICENSE` e `pyproject.toml`).

### Modified Capabilities
- `business-answers-and-readme-doc`: Refinamento do `README.md` para foco em contexto de alto nível, ponte narrativa para `docs/ARCHITECTURE.md` e `docs/BUSINESS_ANSWERS.md`, setup reproduzível e inventário dos 4 notebooks, delegando diretrizes de extensão/testes a `CONTRIBUTING.md` e licença a `LICENSE`.
- `architecture-and-critical-analysis-doc`: Reestruturação narrativa de `docs/ARCHITECTURE.md` em 6 *beats* didáticos sem repetição, incorporando as nuances de domínio das 8 bases de dados, unificando a matriz de racional/CAP e removendo diagramas `mermaid` duplicados em favor dos diagramas SVG padronizados.

## Impact

- Documentação principal: `README.md` e `docs/ARCHITECTURE.md`.
- Novos arquivos de governança: `CONTRIBUTING.md` e `LICENSE`.
- Metadados do pacote Python: `pyproject.toml`.
- Testes de verificação documental: `tests/test_e2e_deliverables.py`.
