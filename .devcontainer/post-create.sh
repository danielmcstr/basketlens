#!/usr/bin/env bash
set -euo pipefail

# Garantir execução a partir da raiz do repositório
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "[BasketLens DevContainer] 1/4 Garantindo arquivos Git LFS em dataset/..."
if command -v git-lfs >/dev/null 2>&1 || git lfs version >/dev/null 2>&1; then
  git lfs install --local || true
  git lfs pull || true
fi

echo "[BasketLens DevContainer] 2/4 Criando/atualizando ambiente virtual .venv (README Seção 3.1)..."
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo "[BasketLens DevContainer] 3/4 Registrando kernel Jupyter do .venv..."
python -m ipykernel install --user --name basketlens --display-name "Python (.venv BasketLens)"

echo "[BasketLens DevContainer] 4/4 Garantindo arquivo .env (README Seção 3.2)..."
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
fi

echo "[BasketLens DevContainer] Bootstrap concluído! Para iniciar os bancos e Web UIs, execute: docker compose up -d"
