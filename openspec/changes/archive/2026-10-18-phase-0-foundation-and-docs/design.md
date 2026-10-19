## Context

O projeto **BasketLens** implementa o Case 7 da disciplina *Big Data e NoSQL: Soluções de Armazenamento Inovadoras* usando o dataset *dunnhumby — The Complete Journey* (~847 MB em 8 arquivos CSV já baixados em `dataset/`) e seu guia oficial (`docs/dunnhumby_The-Complete-Journey-User-Guide.pdf`).

Durante a revisão inicial, identificamos três pontos de desalinhamento entre o rascunho original (`docs/DRAFT.md`) e os arquivos reais / PDF oficial:
1. O arquivo `hh_demographic.csv` utiliza nomes de colunas anonimizados (`classification_1..5`, `HOMEOWNER_DESC`, `KID_CATEGORY_DESC`, `household_key`) em vez dos nomes legados (`AGE_DESC`, `INCOME_DESC`).
2. O arquivo `causal_data.csv` utiliza códigos alfanuméricos em `display` (`0..9`, `A`) e `mailer` (`0`, `A`, `C`, `D`, `F`, `H`, `J`, `L`, `P`, `X`, `Z`), o que invalida o tipo `int` originalmente previsto na tabela CQL `causal_promotions_by_store_week`.
3. O projeto precisa operar 100% localmente via Docker Compose no Tier 2 (base completa), com processamento estritamente *out-of-core*/em lotes via **Polars** e dois modos operacionais: **Ingestão Completa (Modo A)** e **Event Replay Dia a Dia (Modo B)** centrado no caso de estudo oficial do PDF (`household_key = 208`, John Smith, `REFERENCE_DAY = 650`).

## Goals / Non-Goals

**Goals:**
- Reconciliar `docs/DRAFT.md` com o PDF oficial e com as decisões arquiteturais tomadas na entrevista de planejamento.
- Estabelecer o pacote Python `src/basketlens` com `pyproject.toml`, `.env.example` e ambiente virtual `.venv`.
- Implementar `src/basketlens/config.py` com `pydantic-settings` para centralizar parâmetros de conexão, caminhos da base (`dataset/`), tamanho de lote (`batch_size`) e parâmetros temporais do replay (`reference_day=650`, `seconds_per_day=5`).

**Non-Goals:**
- Não subir containers Docker nem criar conexões de banco nesta fase (escopo da Fase 1).
- Não executar ingestão dos CSVs nem criar notebooks nesta fase (escopo das Fases 2 e 3).

## Decisions

### 1. Mapeamento Semântico + Literal em `demographics` (MongoDB)
- **Decisão:** Preservar os campos originais do CSV/PDF (`classification_1` a `classification_5`, `homeowner_desc`, `kid_category_desc`) dentro do subdocumento `demographics` no MongoDB e documentar claramente a equivalência ordinal descrita na página 4 do PDF (`classification_1` = faixa etária `Age Group1..6`, `classification_2` = código `X/Y/Z`, `classification_3` = faixa socioeconômica/renda `Level1..12`, `classification_4` = tamanho do domicílio `1..5+`, `classification_5` = composição familiar `Group1..6`).
- **Alternativa considerada:** Renomear arbitrariamente os valores para faixas salariais inventadas (`50-74K`). Descartada porque perderia a rastreabilidade direta com o CSV oficial e com o PDF da dunnhumby.

### 2. Polimorfismo na coleção `households` (2.500 documentos, 801 com `demographics`)
- **Decisão:** Inserir todas as 2.500 famílias que transacionam em `transaction_data.csv` na coleção `households`. As 801 famílias presentes em `hh_demographic.csv` contêm o subdocumento `demographics`; as 1.699 famílias restantes não possuem a chave `demographics` (ou têm `demographics: null` omitido).
- **Racional:** Demonstra na prática o esquema flexível do modelo documental (sem `NULL`s espalhados em colunas fixas) e garante que `build_360_view(household_key)` funcione para qualquer cliente do programa de fidelidade.

### 3. Gerenciamento de Configuração com `pydantic-settings`
- **Decisão:** Usar `pydantic-settings` com prefixo `BASKETLENS_` e suporte a arquivo `.env`.
- **Racional:** Evita strings mágicas espalhadas entre módulos e notebooks, permitindo alternar facilmente `reference_day`, `seconds_per_day`, `batch_size` e hosts dos bancos.

## Risks / Trade-offs

- **[Risco] Compatibilidade do driver `cassandra-driver` com Python 3.12+** → **Mitigação:** Fixar versão compatível (`cassandra-driver>=3.29.2`) e garantir dependências de compilação ou modo Cython/pure-python estável no `.venv`.
- **[Risco] Comandos acidentais versionando `.venv/` ou dados temporários** → **Mitigação:** Garantir que `.gitignore` cubra `.venv/`, `.env`, `__pycache__/`, `.pytest_cache/` e `.ipynb_checkpoints/`.
