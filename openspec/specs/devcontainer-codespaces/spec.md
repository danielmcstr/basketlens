# devcontainer-codespaces Specification

## Purpose
TBD - created by archiving change add-devcontainer-codespaces. Update Purpose after archive.

## Requirements
### Requirement: Dev Container Configuration for GitHub Codespaces (`devcontainer.json`)
The repository SHALL provide a `.devcontainer/devcontainer.json` file that provisions a Python 3.12 development container with Docker-in-Docker (`ghcr.io/devcontainers/features/docker-in-docker:2`), Git LFS (`ghcr.io/devcontainers/features/git-lfs:1`), minimum host resource requirements (`cpus: 2`, `memory: "8gb"`, `storage: "32gb"`), port forwarding with labeled attributes for all 3 Web UIs (`8081`, `3000`, `8082`) and 3 database services (`27017`, `9042`, `6379`), and VS Code Python/Jupyter settings bound to `.venv/bin/python`.

#### Scenario: Docker-in-Docker and Git LFS features are declared
- **WHEN** a developer or automated test inspects `.devcontainer/devcontainer.json`
- **THEN** it MUST specify `mcr.microsoft.com/devcontainers/python:1-3.12-bookworm` as the base image, include `ghcr.io/devcontainers/features/docker-in-docker:2` (with `dockerDashComposeVersion: "v2"`) and `ghcr.io/devcontainers/features/git-lfs:1` (with `autoPull: true`), and declare `hostRequirements` with at least `2` CPUs, `"8gb"` memory, and `"32gb"` storage

#### Scenario: All 6 polyglot ports are forwarded and labeled for classroom demonstration
- **WHEN** the Codespace is launched from `.devcontainer/devcontainer.json`
- **THEN** `forwardPorts` MUST include `8081`, `3000`, `8082`, `27017`, `9042`, and `6379`, and `portsAttributes` MUST define human-readable labels for `8081` (`Mongo Express`), `3000` (`Cassandra Web`), `8082` (`Redis Commander`), `27017` (`MongoDB`), `9042` (`Apache Cassandra`), and `6379` (`Redis`)

#### Scenario: VS Code extensions and default Python interpreter are pre-configured
- **WHEN** the Codespace opens in VS Code Web or Desktop
- **THEN** `customizations.vscode.extensions` MUST include `ms-python.python`, `ms-python.vscode-pylance`, `ms-toolsai.jupyter`, and `ms-azuretools.vscode-docker`, and `customizations.vscode.settings` MUST set `python.defaultInterpreterPath` to `${containerWorkspaceFolder}/.venv/bin/python`

### Requirement: Idempotent Post-Create Environment Bootstrap (`.devcontainer/post-create.sh`)
The repository SHALL provide an executable `.devcontainer/post-create.sh` script referenced by `postCreateCommand` in `.devcontainer/devcontainer.json` that idempotently pulls Git LFS dataset files, creates `.venv`, installs the project in editable mode (`pip install -e ".[dev]"`), registers the `basketlens` Jupyter kernel, and copies `.env.example` to `.env` without modifying `README.md` or breaking manual re-execution of `README.md` commands.

#### Scenario: Post-create script executes README setup steps idempotently
- **WHEN** `.devcontainer/post-create.sh` runs during Codespace creation or is re-run manually
- **THEN** it MUST ensure Git LFS objects are pulled (`git lfs pull`), create `.venv` (`python3 -m venv .venv`), install `pip install -e ".[dev]"` inside `.venv`, register the Jupyter kernel `basketlens` (`Python (.venv BasketLens)`), and create `.env` from `.env.example` if `.env` does not already exist

#### Scenario: Zero modifications to existing README.md and docker-compose.yml
- **WHEN** the Dev Container configuration is added to the repository
- **THEN** `README.md`, `docker-compose.yml`, and `.env.example` MUST remain unmodified, and all `localhost` endpoints documented in `README.md` (`localhost:27017`, `localhost:9042`, `localhost:6379`, `http://localhost:8081`, `http://localhost:3000`, `http://localhost:8082`) MUST remain valid inside the Codespace via Docker-in-Docker
