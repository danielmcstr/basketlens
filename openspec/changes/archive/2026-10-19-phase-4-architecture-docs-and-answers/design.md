## Context

A Fase 4 consolida toda a engenharia construída nas Fases 0 a 3 em documentação técnica e executiva pronta para avaliação nas Aulas 6 e 8:
- `docs/ARCHITECTURE.md`: entrega formal da Arquitetura Poliglota e da Análise Crítica (valendo 12 + 8 = 20 dos 45 pontos da rubrica).
- `docs/BUSINESS_ANSWERS.md`: caderno de respostas comentadas com os números, tabelas e planos de execução reais extraídos dos 3 bancos (valendo os 15 pontos de implementação e consultas com dados reais e apoiando os 10 pontos de apresentação).
- `README.md`: porta de entrada do repositório com instruções claras de operação dos dois modos (**Modo A: Full Historical Ingestion** e **Modo B: Daily Event Replay**) e das 3 Web UIs.

## Goals / Non-Goals

**Goals:**
- Redigir `docs/ARCHITECTURE.md` com diagramas Mermaid/ASCII claros, justificativas de modelagem de cada banco, CAP/consistência e análise crítica (Neo4j + Kubernetes).
- Redigir `docs/BUSINESS_ANSWERS.md` com os resultados reais das consultas executadas na Fase 3 (incluindo o estudo de caso `household_key = 208`, John Smith).
- Atualizar `README.md` e adicionar testes de verificação final (`tests/test_e2e_deliverables.py`).

**Non-Goals:**
- Não alterar schemas de banco ou lógica de ingestão já validados nas fases anteriores.

## Decisions

### 1. Separação Clara entre `docs/ARCHITECTURE.md` e `docs/BUSINESS_ANSWERS.md`
- **Decisão:** Manter `docs/DRAFT.md` como documento vivo de estudo do grupo e criar dois documentos focados nas rubricas do professor:
  - `docs/ARCHITECTURE.md` focado em **como e por que** os 3 bancos foram modelados, como os dois modos (Batch vs. Event Replay) operam sem estourar memória com Polars, teorema CAP e onde entraria o banco de grafos Neo4j.
  - `docs/BUSINESS_ANSWERS.md` focado nas **respostas de negócio, evidências numéricas, queries executadas e tempos de resposta** obtidos nos bancos reais.
- **Racional:** Facilita tanto a correção da entrega intermediária da Aula 6 (Arquitetura) quanto a arguição final da Aula 8.

## Risks / Trade-offs

- **[Risco] Divergência entre números documentados em `docs/BUSINESS_ANSWERS.md` e saídas dos notebooks** → **Mitigação:** Extrair as tabelas e métricas diretamente das funções de `basketlens.queries` contra os bancos populados e validar com `tests/test_e2e_deliverables.py`.
