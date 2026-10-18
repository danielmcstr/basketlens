## 1. Alinhamento do `docs/DRAFT.md` com o Guia Oficial e Decisões Arquiteturais

- [x] 1.1 Atualizar a Seção 3.2 e a Seção 5.1 de `docs/DRAFT.md` com as colunas reais de `hh_demographic.csv` (`classification_1..5`, `HOMEOWNER_DESC`, `KID_CATEGORY_DESC`, `household_key`), seus significados ordinais conforme a página 4 do PDF oficial e a estratégia de 2.500 documentos na coleção `households` (801 com subdocumento `demographics` e 1.699 sem o campo)
- [x] 1.2 Corrigir a Seção 3.4 e a Seção 5.2 de `docs/DRAFT.md` alterando os tipos de `display_type` e `mailer_page` na tabela CQL `causal_promotions_by_store_week` de `int` para `text` (conforme códigos alfanuméricos da página 6 do PDF)
- [x] 1.3 Atualizar as Seções 4, 5.3, 9 e 10 de `docs/DRAFT.md` registrando a infraestrutura 100% Docker Compose local com Web UIs dedicadas, o motor de ingestão via Polars (`scan_csv` / `read_csv_batched`, sem carregar o dataset inteiro em RAM), os dois modos operacionais (**Modo A: Ingestão Completa** e **Modo B: Event Replay Dia a Dia** com `REFERENCE_DAY = 650` para o estudo de caso `household_key = 208`) e a estrutura dos 4 notebooks

## 2. Configuração do Pacote Python e Ambiente `.venv`

- [x] 2.1 Atualizar `.gitignore` garantindo exclusão de `.venv/`, `.env`, `__pycache__/`, `.pytest_cache/`, `.ipynb_checkpoints/` e volumes de dados locais
- [ ] 2.2 Criar `pyproject.toml` com metadados do pacote `basketlens` (`src/` layout) e dependências pinadas (`polars`, `pymongo`, `cassandra-driver`, `redis`, `pydantic`, `pydantic-settings`, `jupyterlab`, `ipykernel`, `pytest`)
- [ ] 2.3 Criar `.env.example` documentando todas as variáveis `BASKETLENS_*` para conexões locais (MongoDB, Cassandra, Redis), diretório `dataset/` e parâmetros de simulação (`REFERENCE_DAY=650`, `SECONDS_PER_DAY=5`, `PROFILE_TTL_SECONDS=60`)
- [ ] 2.4 Criar o ambiente virtual `.venv` e instalar o pacote `basketlens` em modo editável (`pip install -e ".[dev]"`)

## 3. Módulo de Configuração Tipada e Verificação

- [ ] 3.1 Criar a árvore de pacotes `src/basketlens/__init__.py` e implementar `src/basketlens/config.py` com `Settings` (`pydantic-settings`) e helper `get_settings()`
- [ ] 3.2 Criar `tests/test_config.py` validando os valores padrão de `Settings`, resolução de caminhos de `dataset/` e sobrescrita por variáveis de ambiente (`BASKETLENS_REFERENCE_DAY`, `BASKETLENS_SECONDS_PER_DAY`)
- [ ] 3.3 Executar `pytest` dentro do `.venv` para confirmar que o ambiente e a configuração estão 100% funcionais
