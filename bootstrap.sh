#!/usr/bin/env bash
# Bootstrap do projeto Storyteller. Roda uma vez pra criar estrutura.
# Uso: bash bootstrap.sh

set -euo pipefail

echo "==> Setting up Storyteller project structure"

# Criar pastas
mkdir -p core/memory core/prompts
mkdir -p eval/scenarios/full eval/prompts
mkdir -p api ui tests scripts configs deploy
mkdir -p docs

# Placeholders __init__
touch core/__init__.py core/memory/__init__.py
touch eval/__init__.py
touch api/__init__.py ui/__init__.py tests/__init__.py

# pyproject.toml se não existe
if [ ! -f pyproject.toml ]; then
cat > pyproject.toml <<'EOF'
[tool.poetry]
name = "storyteller"
version = "0.1.0"
description = "LLM storyteller with long-term memory + eval harness"
authors = ["marco <marcooinotna13@outlook.com>"]
readme = "README.md"
packages = [{include = "core"}, {include = "eval"}, {include = "api"}, {include = "ui"}]

[tool.poetry.dependencies]
python = "^3.11"
anthropic = "^0.40.0"
mem0ai = "^0.1.0"
fastapi = "^0.115.0"
uvicorn = "^0.32.0"
streamlit = "^1.40.0"
sqlalchemy = "^2.0.0"
alembic = "^1.13.0"
pydantic = "^2.9.0"
pydantic-settings = "^2.5.0"
python-dotenv = "^1.0.0"
tenacity = "^9.0.0"
tiktoken = "^0.8.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-cov = "^5.0.0"
pytest-mock = "^3.14.0"
ruff = "^0.7.0"
mypy = "^1.13.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
EOF
echo "==> pyproject.toml created"
fi

# .env.example — SQLite pro dev; migração pra Postgres no Sprint 5 (deploy)
if [ ! -f .env.example ]; then
cat > .env.example <<'EOF'
ANTHROPIC_API_KEY=sk-ant-...
# SQLite local pro dev. Prod migra pra Postgres via Fly (Sprint 5).
DATABASE_URL=sqlite:///./storyteller.db
MEM0_STORAGE_PATH=./.mem0_data
LOG_LEVEL=INFO
EOF
echo "==> .env.example created"
fi

# .gitignore
if [ ! -f .gitignore ]; then
cat > .gitignore <<'EOF'
# --- Python ---
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
.venv/
.env
.mem0_data/
*.db
storyteller.db
*.egg-info/
.mypy_cache/
.ruff_cache/
.DS_Store

# --- Secrets / credentials (never commit) ---
docker/.env
**/.credentials.json
*.pem
id_ed25519*
id_rsa*

# --- Workspace clutter, not part of the Storyteller project ---
.claude/
.claude.json
node_modules/
package.json
package-lock.json
dev-marco/
docker/
portfolio-brief-para-outra-claude.md
CLAUDE.csharp-legacy.md
EOF
echo "==> .gitignore created"
fi

# README stub
if [ ! -f README.md ]; then
cat > README.md <<'EOF'
# Storyteller

LLM-powered storyteller with verifiable long-term memory. Portfolio project.

Status: in progress. See `docs/tasks.md`.
EOF
fi

# Git init se ainda não é repo
if [ ! -d .git ]; then
  git init
  git branch -M main
  git add .
  git config user.name "NFAsylum"
  git config user.email "marcooinotna13@outlook.com"
  git commit -m "chore: bootstrap Storyteller project structure"
  echo "==> Git initialized with first commit"
fi

echo ""
echo "==> Done. Next steps:"
echo "    1. Copy .env.example to .env and fill ANTHROPIC_API_KEY"
echo "    2. poetry install"
echo "    3. Start Sprint 1: read docs/tasks.md"
