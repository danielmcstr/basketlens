## 1. Configuração do Dev Container e GitHub Codespaces (`.devcontainer/`)

- [x] 1.1 Criar `.devcontainer/devcontainer.json` com imagem `mcr.microsoft.com/devcontainers/python:1-3.12-bookworm`, features `ghcr.io/devcontainers/features/docker-in-docker:2` (`moby: true`, `dockerDashComposeVersion: "v2"`) e `ghcr.io/devcontainers/features/git-lfs:1` (`autoPull: true`), `hostRequirements` (`cpus: 2`, `memory: "8gb"`, `storage: "32gb"`), `forwardPorts`, `portsAttributes` para as 6 portas (`8081`, `3000`, `8082`, `27017`, `9042`, `6379`) e `customizations.vscode` (extensões Python/Jupyter/Docker e interpretador `.venv/bin/python`)
- [x] 1.2 Criar `.devcontainer/post-create.sh` (com permissão de execução `chmod +x`) implementando de forma idempotente o `git lfs pull`, criação do `.venv`, instalação `pip install -e ".[dev]"`, registro do kernel Jupyter `basketlens` (`Python (.venv BasketLens)`) e cópia condicional de `.env.example` para `.env`

## 2. Testes Automatizados e Verificação de Integridade

- [x] 2.1 Criar `tests/test_devcontainer.py` validando o JSON do `.devcontainer/devcontainer.json` (imagem, features Docker-in-Docker e Git LFS, `hostRequirements`, `forwardPorts`, `portsAttributes` e configurações do VS Code) e a sintaxe/comandos do `.devcontainer/post-create.sh`
- [x] 2.2 Executar `.venv/bin/pytest -v` e `git diff README.md docker-compose.yml .env.example` garantindo que 100% da suíte passe e que `README.md`, `docker-compose.yml` e `.env.example` permaneçam inalterados
