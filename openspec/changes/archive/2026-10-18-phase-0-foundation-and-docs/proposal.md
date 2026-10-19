## Why

Antes de levantar a infraestrutura e iniciar a ingestão dos 6,27 milhões de registros da base *The Complete Journey*, o projeto precisa alinhar a documentação de referência (`docs/DRAFT.md`) com o dicionário oficial da dunnhumby (`docs/dunnhumby_The-Complete-Journey-User-Guide.pdf`) e estruturar o ambiente Python (`.venv` e `pyproject.toml`) com dependências pinadas e configuração centralizada. Sem essa fundação, divergências como nomes de colunas demográficas anonimizadas (`classification_1..5`) e tipos alfanuméricos em `causal_data.csv` causariam falhas de schema nas fases seguintes.

## What Changes

- **Atualização e reconciliação de `docs/DRAFT.md`**:
  - Alinhar a Seção 3.2 e a Seção 5.1 com as colunas reais do `hh_demographic.csv` documentadas no PDF oficial (`classification_1` a `classification_5`, `HOMEOWNER_DESC`, `KID_CATEGORY_DESC`, `household_key`) e com a decisão de armazenar todas as 2.500 famílias no MongoDB (801 com subdocumento `demographics` e 1.699 sem o campo, demonstrando esquema flexível).
  - Corrigir a modelagem CQL da tabela `causal_promotions_by_store_week` na Seção 5.2, alterando `display_type` e `mailer_page` de `int` para `text` (conforme códigos alfanuméricos da página 6 do PDF).
  - Documentar a infraestrutura 100% local via Docker Compose com Web UIs pré-configuradas, o uso de Polars em modo *streaming/out-of-core* (sem carregar o dataset completo em memória) e os dois modos operacionais (**Modo A: Ingestão Completa** e **Modo B: Event Replay Dia a Dia** ancorado no estudo de caso `household_key = 208` no Dia 650).
- **Configuração do pacote Python e ambiente virtual (`.venv`)**:
  - Criar `pyproject.toml` definindo o pacote instalável `basketlens` (em `src/basketlens/`) com dependências pinadas (`polars`, `pymongo`, `cassandra-driver`, `redis`, `pydantic`, `pydantic-settings`, `jupyterlab`, `ipykernel`, `pytest`).
  - Criar `.env.example` com todas as variáveis de conexão local e parâmetros de simulação (`REFERENCE_DAY=650`, `SECONDS_PER_DAY=5`, `PROFILE_TTL_SECONDS=60`).
  - Criar a estrutura inicial de pacotes em `src/basketlens/` e `src/basketlens/config.py`.
- **Fora de escopo nesta fase (Out of Scope)**:
  - Subida dos containers Docker (`docker-compose.yml` pertence à Fase 1);
  - Criação de índices/tabelas nos bancos (Fase 1);
  - Pipelines de ingestão, Event Replay, queries e notebooks (Fases 2, 3 e 4).

## Capabilities

### New Capabilities
- `project-foundation`: Estrutura do pacote Python `basketlens`, gerenciamento de configuração tipada via variáveis de ambiente (`.env.example` / `config.py`), ambiente `.venv` reprodutível e alinhamento do documento base `docs/DRAFT.md` com o guia oficial do dataset.

### Modified Capabilities
<!-- Nenhuma capability existente está sendo modificada nesta fase inicial. -->

## Impact

- Documentação: `docs/DRAFT.md` e `.gitignore`.
- Configuração e Build: `pyproject.toml`, `.env.example`, `.venv/`.
- Código-fonte inicial: `src/basketlens/__init__.py` e `src/basketlens/config.py`.
- Testes iniciais: `tests/test_config.py`.
