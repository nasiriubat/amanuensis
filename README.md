# Paper Writer

An AI co-author that learns how good papers in a genre are structured, learns how a
specific author writes, interviews you until your work fits a publishable shape, then
drafts the paper section by section with verified references and exports it in a venue
template.

Design and roadmap: [SPEC.md](SPEC.md). This repository is at **phase 1 (skeleton)**:
accounts, providers, model-per-purpose, projects, author profiles, paper kinds, house
style and usage. Ingest, interview, drafting, references and export follow in phases 2
to 7.

## Run with Docker

```bash
cp .env.example .env
# edit .env: set APP_SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
docker compose up -d --build
```

Open http://localhost:8000, sign in with the admin credentials from `.env`, change the
password, then go to **Settings → Providers** to add an API key and **Settings → Models**
to assign a model to each purpose.

All data lives in the `paper_data` volume: SQLite database, projects, profiles,
templates. Back it up by copying that volume.

## Run for development

Backend (FastAPI on port 8000):

```bash
cd backend
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -e ".[dev]"
cp ../.env.example ../.env   # edit values
set -a; source ../.env; set +a
.venv/bin/uvicorn app.main:app --reload
```

Frontend (Vite on port 5173, proxies `/api` to the backend):

```bash
cd frontend
npm install
npm run dev
```

Tests and lint:

```bash
cd backend && .venv/bin/pytest -q && .venv/bin/ruff check app tests
cd frontend && npm run typecheck
```

## Layout

```
backend/app/        FastAPI app: routers, models, storage, LLM adapters
backend/seed/       built-in paper kinds and house style, copied to DATA_DIR on first boot
frontend/src/       React SPA: pages, components, design tokens in index.css
data/               created at runtime (gitignored)
```

## Configuration

Bootstrap settings come from the environment (see `.env.example`). Everything else is
configured in the admin UI and stored in SQLite: providers and keys (encrypted at rest),
model per purpose, paper kinds, house style, users.
