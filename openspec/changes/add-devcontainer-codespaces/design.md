## Context

O projeto **BasketLens** foi desenvolvido para rodar 100% localmente via Docker Compose (`mongo:8.0.4`, `cassandra:5.0.2`, `redis:7.4.2-alpine` + 3 Web UIs: `mongo-express`, `cassandra-web` e `redis-commander`) e um ambiente virtual Python `.venv` gerenciado por `pyproject.toml`. Para a apresentação final em sala de aula (Aula 8), o objetivo é executar e demonstrar todo o projeto a partir do zero dentro do **GitHub Codespaces**, seguindo fielmente as instruções já documentadas em `README.md` e mantendo `README.md`, `docker-compose.yml` e `.env.example` **intocados**.

## Goals / Non-Goals

**Goals:**
- Fornecer `.devcontainer/devcontainer.json` e `.devcontainer/post-create.sh` prontos para **GitHub Codespaces** e **VS Code Dev Containers**.
- Garantir que `docker compose up -d` executado dentro do terminal do Codespace suba os 6 containers (`basketlens-mongo`, `basketlens-cassandra`, `basketlens-redis`, `basketlens-mongo-express`, `basketlens-cassandra-web`, `basketlens-redis-commander`) acessíveis em `localhost` nas exatas portas do `README.md` (`27017`, `9042`, `6379`, `8081`, `3000`, `8082`).
- Automatizar no `postCreateCommand` a hidratação do Git LFS (`dataset/*.csv`) e a criação idempotente do `.venv` + kernel Jupyter `basketlens`, preservando a possibilidade de reexecutar qualquer comando da Seção 3 do `README.md` ao vivo durante a aula.
- Validar a configuração via testes automatizados (`tests/test_devcontainer.py`).

**Non-Goals:**
- Não alterar nenhuma linha de `README.md`, `docker-compose.yml`, `.env.example` ou `src/basketlens/`.
- Não converter o `devcontainer.json` para o modo multi-container acoplado (`dockerComposeFile`), pois isso alteraria os hostnames de `localhost` para nomes de serviço Docker e impediria demonstrar o comando `docker compose up -d` exatamente como está no `README.md`.

## Decisions

### 1. Docker-in-Docker (`docker-in-docker:2`) em vez de `docker-outside-of-docker` ou `dockerComposeFile`
- **Decisão:** Utilizar a feature oficial `ghcr.io/devcontainers/features/docker-in-docker:2` (`moby: true`, `dockerDashComposeVersion: "v2"`) sobre a imagem `mcr.microsoft.com/devcontainers/python:1-3.12-bookworm`.
- **Racional:**
  - Com `docker-in-docker:2`, o daemon Docker roda isolado **dentro** do próprio container do Codespace. Quando o apresentador executa `docker compose up -d` no terminal do Codespace (Seção 3.2 do `README.md`), as portas publicadas pelos 6 serviços (`27017`, `9042`, `6379`, `8081`, `3000`, `8082`) ficam vinculadas diretamente à interface `localhost` do Codespace.
  - Isso garante compatibilidade 100% transparente com `.env.example` (`localhost`), com os 4 notebooks e com o teste `test_web_uis_respond_http_200` em `tests/test_connections_and_schemas.py` (`http://localhost:8081`, `http://localhost:3000`, `http://localhost:8082`).
  - Simultaneamente, o GitHub Codespaces detecta as portas listadas em `forwardPorts` e gera URLs HTTPS públicas/autenticadas na aba **PORTS** para abrir o `mongo-express`, `cassandra-web` e `redis-commander` no navegador da sala de aula.
- **Alternativas descartadas:**
  - `docker-outside-of-docker`: em ambientes locais com Docker Desktop, containers irmãos fazem bind no host e não no `localhost` interno do dev container, quebrando `http://localhost:8081` dentro do container.
  - `dockerComposeFile`: exigiria modificar `docker-compose.yml` ou criar overrides de rede e descaracterizaria o passo `docker compose up -d` do `README.md`.

### 2. Dimensionamento `hostRequirements` para GitHub Codespaces (`2 cpus`, `8gb RAM`, `32gb storage`)
- **Decisão:** Configurar `"hostRequirements": { "cpus": 2, "memory": "8gb", "storage": "32gb" }`.
- **Racional:**
  - Medições reais da stack mostram consumo em repouso de ~2,25 GiB de RAM (`basketlens-cassandra` com `MAX_HEAP_SIZE="1536M"` consome ~1,88 GiB, `basketlens-mongo` ~205 MiB, `basketlens-redis` ~5 MiB, 3 Web UIs ~90 MiB) e pico de ~3,2 GiB durante a ingestão streaming em Polars (`batch_size = 50_000`).
  - No GitHub Codespaces, a máquina padrão de **2 cores já possui 8 GB de RAM e 32 GB de SSD** (e a de 4 cores possui 16 GB de RAM). Exigir `cpus: 2` e `memory: "8gb"` garante memória suficiente para o Cassandra + Polars sem bloquear contas estudantis/educacionais cujo limite de Codespaces seja de 2 cores.

### 3. Bootstrap Idempotente via `.devcontainer/post-create.sh`
- **Decisão:** Centralizar o `postCreateCommand` em um script `.devcontainer/post-create.sh` com `set -euo pipefail`.
- **Racional:**
  - Os 8 arquivos CSV em `dataset/` (~808 MB) são rastreados via Git LFS (`.gitattributes`). O script executa `git lfs install --local` e `git lfs pull` para garantir que os CSVs reais estejam presentes antes de qualquer execução dos notebooks ou testes.
  - Em seguida, executa os comandos da Seção 3.1 do `README.md` (`python3 -m venv .venv`, `pip install --upgrade pip`, `pip install -e ".[dev]"`, `python -m ipykernel install --user --name basketlens --display-name "Python (.venv BasketLens)"`) e cria `.env` caso não exista (`if [ ! -f .env ]; then cp .env.example .env; fi`).
  - Todos esses comandos são **idempotentes**: durante a apresentação em sala de aula, o grupo pode tanto abrir diretamente os notebooks com o kernel já pronto quanto colar os comandos do `README.md` no terminal para demonstrar o passo a passo do zero.

## Risks / Trade-offs

- **[Risco] Cota de banda do Git LFS no GitHub ao criar múltiplos Codespaces** → **Mitigação:** A feature `git-lfs:1` e o `post-create.sh` verificam se os arquivos em `dataset/*.csv` já estão hidratados antes de forçar novo download, e o Codespace pode ser pré-criado (ou usar *Prebuilds*) antes da apresentação.
- **[Risco] Tempo de bootstrap do Apache Cassandra (~35–50s) após `docker compose up -d`** → **Mitigação:** O `docker-compose.yml` já possui `healthcheck` com `start_period: 45s` e `depends_on: condition: service_healthy` nas Web UIs, permitindo acompanhar a transição para `healthy` ao vivo com `docker compose ps`.
