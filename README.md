# Paper Writer

An AI co-author that learns how good papers in a genre are structured, learns how a
specific author writes, interviews you until your work fits a publishable shape, then
drafts the paper section by section with verified references and exports it in a venue
template.

Design and roadmap: [SPEC.md](SPEC.md). Phases 1 to 6 are done: accounts, providers,
model-per-purpose, projects, author profiles, paper kinds, house style, usage; arXiv and
PDF ingest, background jobs with live progress, playbook and voice learning with a
per-paper context budget; research design from an idea, interview rounds with suggested
answers, a side chat with pinning, facts extraction and an approvable outline; the Studio
with section-by-section drafting, a checklist of open items, house-style lint and version
history; verified references from Semantic Scholar, OpenAlex, arXiv, .bib import or manual
entry, with a Cite picker in the Studio; Mermaid figures rendered in the browser and uploaded
result images; export to LNCS, ACM or a custom template as PDF (Tectonic), DOCX (Pandoc) and a
LaTeX zip; site settings, logo, SEO and public Markdown pages. Phase 7 is polish: the critique
pass, venue suggestion and a dark-mode audit.

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

LaTeX templates: acmart is fetched by Tectonic automatically. Springer's `llncs.cls` and
`splncs04.bst` are not on CTAN; download the LNCS author package from Springer and upload the
two files under Export → Template (admin), or place them in `data/templates/lncs/`.

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

## Learning budget and cost

Every learning run is map-reduce: one call per paper, one synthesis call. The budget
picker caps how many characters of each paper the model reads (15k, 40k or 90k) while
keeping every section represented. Measured section lengths are passed separately, so
structure advice stays accurate even at the small budget. A three-paper playbook at the
small budget used about 20k tokens; a two-paper voice profile about 9k. Token usage per
run is shown on the Playbook page and under Settings → Usage.

## Configuration

Bootstrap settings come from the environment (see `.env.example`). Everything else is
configured in the admin UI and stored in SQLite: providers and keys (encrypted at rest),
model per purpose, paper kinds, house style, users.
