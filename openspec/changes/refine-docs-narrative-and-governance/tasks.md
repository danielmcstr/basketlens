## 1. Licenciamento Didático Não-Comercial (`LICENSE` e `pyproject.toml`)

- [x] 1.1 Criar o arquivo `LICENSE` na raiz do repositório estipulando uso estritamente didático, acadêmico e científico (uso comercial não autorizado) para o código e artefatos do projeto.
- [x] 1.2 Incluir em `LICENSE` os termos de uso e a citação oficial obrigatória do dataset *dunnhumby — The Complete Journey* (`https://www.dunnhumby.com/source-files/`).
- [x] 1.3 Atualizar o campo `license` em `pyproject.toml` removendo `MIT` e declarando uso exclusivamente educacional/acadêmico (não-comercial).

## 2. Guia de Extensão e Testes Automatizados (`CONTRIBUTING.md`)

- [x] 2.1 Criar `CONTRIBUTING.md` documentando como executar a suíte de validação automatizada (`.venv/bin/pytest -v`) e os testes individuais de entregáveis, configuração, conexões, ingestão e replay.
- [x] 2.2 Documentar em `CONTRIBUTING.md` o mapa de pacotes em `src/basketlens/` (`connections`, `schemas`, `ingestion`, `replay` e `queries`) e onde adicionar novas consultas ou transformações.
- [x] 2.3 Documentar em `CONTRIBUTING.md` as 4 invariantes técnicas obrigatórias ao estender o projeto: (1) *Zero Full-Dataset In-Memory* com Polars (`scan_csv` / `read_csv_batched`), (2) proibição de `ALLOW FILTERING` no Cassandra, (3) cobertura por índices B-Tree (`IXSCAN` / `EXPRESS_IXSCAN`) no MongoDB e (4) alinhamento de `TTL` e invalidação `DEL profile:{id}` no Redis.

## 3. Refinamento e Enxugamento do `README.md`

- [x] 3.1 Reestruturar a **Seção 1 (`## 1. Sobre o Projeto e Contexto do Problema`)** mantendo apenas a introdução de alto nível sobre o problema no varejo físico, a abordagem poliglota nos 3 motores, o processamento *out-of-core* com Polars e o estudo de caso `household_key = 208` (removendo o quadro ASCII redundante).
- [x] 3.2 Estruturar a **Seção 2 (`## 2. Documentação Técnica e Respostas de Negócio`)** como ponte narrativa contextualizada: apontando primeiro para `docs/ARCHITECTURE.md` (detalhes técnicos, nuances das bases e diagramas) e depois para `docs/BUSINESS_ANSWERS.md` (respostas empíricas às perguntas do professor), seguida da tabela da rubrica corrigida (sem menção a observabilidade).
- [x] 3.3 Renumerar e revisar as seções **Seção 3 (`## 3. Infraestrutura Local (docker-compose.yml)`)** e **Seção 4 (`## 4. Como Executar o Projeto Passo a Passo`)** mantendo os comandos reproduzíveis de `.venv`, `docker compose up -d` e inicialização de schemas.
- [x] 3.4 Renumerar a **Seção 5 (`## 5. Roteiro dos 4 Notebooks Demonstrativos (notebooks/)`)**, adicionar referência a `CONTRIBUTING.md` para execução de testes/extensão e remover as antigas Seções 9 (Testes) e 10 (Licença) do `README.md`.

## 4. Reescrita Narrativa e Didática de `docs/ARCHITECTURE.md` (6 Beats sem Repetição)

- [x] 4.1 Reescrever o **Beat 1 (`## 1. Visão Geral da Arquitetura e as 3 Realidades Físicas do Dataset`)** mantendo `assets/arch-polyglot-overview.svg` e aterrando as 3 nuances físicas da base *The Complete Journey* (assimetria de volume + regra *Zero Full-Dataset In-Memory* com Polars; cobertura demográfica parcial de `801`/`2.500` + códigos alfanuméricos `display`/`mailer` como `text`; e decomposição de preço/desconto no PDV para `household_key = 208`), sem repetir em lista o que já está no diagrama.
- [x] 4.2 Reescrever o **Beat 2 (`## 2. Por Que Três Motores? Do Padrão de Acesso ao Teorema CAP`)** unificando a antiga tabela 1.1 e a antiga Seção 4 em uma única Matriz Consolidada de Papel Arquitetural, *System of Record* vs. *Speed Layer*, Teorema CAP (`CP` vs. `AP`) e Consistência Ajustável (`w: 1`/`"majority"`, `ONE` vs. `LOCAL_QUORUM` / `QUORUM`, `TTL` + `DEL`).
- [x] 4.3 Reescrever o **Beat 3 (`## 3. Modelagem Física em Disco e Memória`)** apresentando de forma direta e não-repetitiva: (3.1) os 4 padrões de modelagem (*Polymorphic*, *Subset Pattern* com `$slice: -5`, *Extended Reference Pattern* e *Computed Pattern*) + 3 índices B-Tree no MongoDB (`households`); (3.2) as 4 tabelas CQL orientadas à consulta e a proibição de `ALLOW FILTERING` no Cassandra; e (3.3) os 7 padrões de chave e fórmula de `TTL` no Redis.
- [x] 4.4 Reescrever o **Beat 4 (`## 4. O Sistema em Movimento: Modo A (Batch) vs. Modo B (Event Replay) e Ciclo Cache-Aside`)** mantendo `assets/arch-operational-modes.svg` e narrando a transição `cutoff_day = 711` vs. `prepare_replay_baseline(649)` $\rightarrow$ `DAY 650..657`, os 4 passos diários, o ciclo **Cache-Aside** (`GET` / `SETEX` / `DEL profile:208`), o resgate do cupom `51800000050` no Dia 654 e a expiração da Campanha 22 no Dia 657.
- [x] 4.5 Reescrever o **Beat 5 (`### 5.1 Onde Entraria um Banco de Grafos (Neo4j)?`)** mantendo apenas `assets/arch-neo4j-graph.svg` (removendo o bloco `mermaid` duplicado), detalhando os 3 casos de travessia multi-salto (`BOUGHT_WITH`, atribuição/*halo effect* e *Lookalike* via GDS) e justificando por que as 3 perguntas obrigatórias não exigem grafo.
- [x] 4.6 Reescrever o **Beat 6 (`### 5.2 Das Limitações Locais à Produção Corporativa em Kubernetes (K8s)`)** conectando diretamente as limitações do ambiente local (cobertura demográfica de 32%, *dual-write* na aplicação e *single-node*) à arquitetura em `assets/arch-kubernetes-production.svg` (*Strimzi Kafka + Outbox/CDC*, *K8ssandra RF=3 LOCAL_QUORUM*, *MongoDB Operator*, *Redis Cluster* e *Argo Workflows* + `dlt`).

## 5. Atualização e Verificação da Suíte de Testes (`tests/test_e2e_deliverables.py`)

- [x] 5.1 Atualizar `tests/test_e2e_deliverables.py` para validar o novo `README.md` enxuto, a presença e o conteúdo de `CONTRIBUTING.md` e `LICENSE`, o metadado não-comercial em `pyproject.toml`, e todos os tópicos obrigatórios e diagramas SVG em `docs/ARCHITECTURE.md` (garantindo ausência de blocos `mermaid` duplicados).
- [x] 5.2 Executar `.venv/bin/pytest tests/test_e2e_deliverables.py tests/test_devcontainer.py tests/test_config.py -v` confirmando 100% de aprovação.
