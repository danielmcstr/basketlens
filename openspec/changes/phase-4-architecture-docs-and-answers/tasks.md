## 1. Documento de Arquitetura e Análise Crítica (`docs/ARCHITECTURE.md`)

- [x] 1.1 Redigir os diagramas e a visão geral da Arquitetura Poliglota e dos dois modos operacionais (**Modo A: Full Historical Load** vs. **Modo B: Daily Event Replay**) em `docs/ARCHITECTURE.md`
- [x] 1.2 Documentar a justificativa detalhada de modelagem dos 3 bancos (padrões Subset/Extended Reference/Polimorfismo no MongoDB, chaves de partição e clustering das 4 tabelas CQL no Cassandra e estrutura de chaves/TTL e Cache-Aside no Redis) + tabela CAP/consistência
- [x] 1.3 Documentar a Análise Crítica completa em `docs/ARCHITECTURE.md`, incluindo *"Onde entraria um grafo (Neo4j)?"*, limitações da base e evolução para Kubernetes em produção

## 2. Documento de Respostas às Perguntas de Negócio (`docs/BUSINESS_ANSWERS.md`)

- [x] 2.1 Documentar em `docs/BUSINESS_ANSWERS.md` a resposta e as evidências empíricas da **Pergunta 1** (Visão 360º e histórico recente do cliente `household_key = 208`, saída do `explain("executionStats")` no MongoDB e ganho de latência do Cache-Aside no Redis)
- [x] 2.2 Documentar em `docs/BUSINESS_ANSWERS.md` a resposta e as evidências empíricas da **Pergunta 2** (campanhas e cupons ativos no Redis no `REFERENCE_DAY = 650`, evolução até o Dia 657 no Event Replay e resgate no Dia 654)
- [x] 2.3 Documentar em `docs/BUSINESS_ANSWERS.md` a resposta e as tabelas consolidadas da **Pergunta 3** (gasto semanal médio das 801 famílias por `classification_1` e `classification_3`) e das **Consultas Bônus de Trade Marketing** (lift de gôndola e tabloide sobre o produto `72717`)

## 3. Guia Principal (`README.md`) e Validação E2E

- [x] 3.1 Atualizar `README.md` com instruções completas de setup, `docker compose up -d`, URLs das 3 Web UIs (`:8081`, `:3000`, `:8082`), execução dos dois modos operacionais, roteiro dos 4 notebooks (`01` a `04`) e citação oficial da licença dunnhumby
- [x] 3.2 Criar `tests/test_e2e_deliverables.py` validando a existência e integridade de todos os documentos, notebooks e entregas da rubrica
- [x] 3.3 Executar a suíte completa `pytest` garantindo que todas as fases passem sem erros
