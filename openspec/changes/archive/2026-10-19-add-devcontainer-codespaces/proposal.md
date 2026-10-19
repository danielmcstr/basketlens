## Why

Para realizar a demonstração ao vivo do projeto **BasketLens** em sala de aula (Aula 8) a partir de qualquer máquina usando **GitHub Codespaces** (ou VS Code Dev Containers), precisamos de uma configuração `.devcontainer/` reprodutível que provisione automaticamente Python 3.12, o ambiente virtual `.venv`, Git LFS (`dataset/*.csv`), Docker-in-Docker e o redirecionamento das 6 portas locais, permitindo executar todos os passos do `README.md` do zero **sem alterar nenhuma linha do `README.md` ou do código existente**.

## What Changes

- **Configuração Oficial de Dev Container (`.devcontainer/devcontainer.json`)**:
  - Imagem base oficial `mcr.microsoft.com/devcontainers/python:1-3.12-bookworm`.
  - Feature `ghcr.io/devcontainers/features/docker-in-docker:2` (`moby: true`, `dockerDashComposeVersion: "v2"`) para que o comando `docker compose up -d` do `README.md` rode um daemon Docker isolado dentro do próprio Codespace e exponha os 3 bancos (`27017`, `9042`, `6379`) e as 3 Web UIs (`8081`, `3000`, `8082`) diretamente em `localhost`.
  - Feature `ghcr.io/devcontainers/features/git-lfs:1` (`autoPull: true`) para baixar automaticamente os 8 arquivos CSV reais da pasta `dataset/` (~808 MB).
  - Declaração de `hostRequirements` (`cpus: 2`, `memory: "8gb"`, `storage: "32gb"`) compatível com as máquinas de 2-core (8 GB RAM) e 4-core (16 GB RAM) do GitHub Codespaces.
  - Configuração de `forwardPorts` e `portsAttributes` nomeando claramente as 3 interfaces Web (`Mongo Express (MongoDB UI)` em `8081`, `Cassandra Web (Cassandra UI)` em `3000` e `Redis Commander (Redis UI)` em `8082`) e as portas dos bancos (`27017`, `9042`, `6379`) na aba **PORTS** do Codespaces.
  - Customizações do VS Code (`customizations.vscode`) com extensões pré-instaladas (`ms-python.python`, `ms-python.vscode-pylance`, `ms-toolsai.jupyter`, `ms-azuretools.vscode-docker`) e interpretador padrão apontando para `${containerWorkspaceFolder}/.venv/bin/python`.
- **Script Idempotente de Inicialização (`.devcontainer/post-create.sh`)**:
  - Acionado via `postCreateCommand` na criação do Codespace.
  - Executa `git lfs install --local` e `git lfs pull` para garantir que os arquivos em `dataset/*.csv` estejam materializados (e não apenas ponteiros LFS).
  - Executa de forma idempotente os exatos comandos da Seção 3.1 e 3.2 do `README.md`: cria `.venv`, atualiza `pip`, instala `pip install -e ".[dev]"`, registra o kernel Jupyter `basketlens` (`Python (.venv BasketLens)`) e cria `.env` a partir de `.env.example` (`cp -n .env.example .env`).
- **Suíte de Testes de Validação do Dev Container (`tests/test_devcontainer.py`)**:
  - Valida a estrutura e o conteúdo do `.devcontainer/devcontainer.json` (features, `hostRequirements`, `forwardPorts`, `portsAttributes`, extensões VS Code) e a sintaxe/idempotência do `.devcontainer/post-create.sh`.

### Escopo (In Scope vs. Out of Scope)
- **In Scope**:
  - Criação de `.devcontainer/devcontainer.json` e `.devcontainer/post-create.sh`.
  - Criação de testes automatizados em `tests/test_devcontainer.py` para garantir a integridade da configuração de Codespaces.
- **Out of Scope**:
  - **Zero alterações** em `README.md`, `docker-compose.yml`, `.env.example`, `pyproject.toml`, notebooks (`notebooks/*.ipynb`) ou módulos Python em `src/basketlens/`.
  - Inicialização automática do `docker compose up -d` no `postStartCommand` (mantido manual conforme o fluxo de demonstração da Seção 3.2 do `README.md`).

## Capabilities

### New Capabilities
- `devcontainer-codespaces`: Configuração de Dev Container e GitHub Codespaces (`.devcontainer/devcontainer.json` e `.devcontainer/post-create.sh`) com suporte a Docker-in-Docker, Git LFS, pré-configuração idempotente do `.venv` + kernel Jupyter e redirecionamento rotulado das 3 Web UIs e 3 bancos NoSQL.

### Modified Capabilities
<!-- Nenhuma capability existente tem seus requisitos alterados. -->

## Impact

- Novos arquivos de infraestrutura de desenvolvimento: `.devcontainer/devcontainer.json`, `.devcontainer/post-create.sh`.
- Novos testes automatizados: `tests/test_devcontainer.py`.
- Nenhum impacto ou modificação em `README.md`, `docker-compose.yml` ou `src/basketlens/`.
