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
LaTeX zip; site settings, logo, SEO and public Markdown pages; a reviewer-style critique pass
whose major findings land on the checklist, and venue suggestions you can adopt as the target
venue. All seven build phases from SPEC.md are done; what remains is feedback-driven polish.

Three starting points are offered when a project is created. "I built something" opens with
the specification. "I have an idea" opens with research design and the specification grows out
of the plan. "I have a draft" makes exemplars optional and opens the Studio, where you paste the whole
draft once: every heading becomes a section marked as yours and its paragraphs become the
outline, so lint, references, the reviewer and export work on your text from the first minute. A literature scan on the Sources and References pages turns the idea, plan
and specification into search queries, asks Semantic Scholar, OpenAlex and arXiv, ranks what comes
back, and lets you adopt papers as verified references or as exemplars in one click. Any exemplar
can be made citable with one click as well. Papers you read for the work go in as *background
reading*: read in full once, summarised into a reading card (question, method, result,
limitation, relation to your work), and citable at once; drafts may attribute to them what the
card says, and Related Work is written from the cards. Twenty to forty readings per project is
normal; they never touch the playbook. Author profiles stay optional: without one, drafts
follow the house style.

Around the pipeline: a public landing page whose copy the admin edits (steps and entry points
come from the product itself), seeded About and Contact pages, server-rendered SEO tags and a
sitemap, a top bar with breadcrumbs, live background-job indicator and account menu, and an
admin Storage page that shows disk use per project and runs explicit cleanups (old exports,
raw paper sources, git history compaction, finished jobs, old call logs, expired sessions,
database vacuum). Uploads are checked by their bytes, SVGs are sanitised, and user files are
served with a sandboxing content-security policy.

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

The image is large (about 8 GB) because it bakes in CPU PyTorch and the Docling layout
models so PDF extraction works offline. The first build downloads a few gigabytes; pip runs
with a long timeout and retries so a slow connection does not fail the build.

## Deploying for a team

Paper Writer is one container with one data volume. That is the right shape for a research
group of up to a few dozen people. What to do before you hand the URL to colleagues:

1. **Put it behind HTTPS.** Run the container on a private port and terminate TLS in a reverse
   proxy. With Caddy, the whole configuration is two lines:
   ```
   papers.example.org {
       reverse_proxy localhost:8000
   }
   ```
   Then set `APP_URL=https://papers.example.org` and `SECURE_COOKIES=true` in `.env`. The app
   trusts `X-Forwarded-*` headers from the proxy.
2. **Generate a real secret.** `APP_SECRET_KEY` encrypts every provider API key at rest. Losing
   it means re-entering the keys; changing it after the fact makes stored keys unreadable.
3. **Sign in once as the seeded admin and change the password**, then add providers, assign a
   model to each purpose, and invite members from Settings → Users. The Library shows a
   set-up checklist until those are done. Members get a temporary password and must change
   it on first sign-in.
4. **Add an SMTP server (optional) under Settings → Site → Email.** With it, invitations and
   admin resets are emailed and members get "Forgot your password?" on the sign-in page (one-hour
   links). Without it, you share temporary passwords yourself. The SMTP password is stored
   encrypted with `APP_SECRET_KEY`; "Send a test to me" confirms the connection.
5. **Set `SEMANTIC_SCHOLAR_API_KEY`.** Without it, reference search and the literature scan
   share the public quota and are throttled within seconds. The key is free.
6. **Back up the volume.** Settings → Storage → Download backup produces one zip with a
   consistent database snapshot and every file. For unattended backups, call
   `GET /api/admin/storage/backup` with an admin session from a cron job, or snapshot the
   `paper_data` volume. Restore by unzipping into an empty volume.
7. **Watch disk and tokens.** Settings → Storage shows disk use per project and runs cleanups;
   Settings → Usage shows tokens per user, purpose and model. Every model call is logged.
8. **Size the host.** Two vCPUs and 4 GB of RAM are enough for a group. PDF extraction with
   Docling is the only CPU-heavy step and runs as a background job. The image is about 8 GB.

Known limits: the app runs as a single process, so run exactly one replica. Background jobs
live inside that process and are marked failed if the container restarts mid-job; the user
simply starts them again. SQLite is the database; it is not the bottleneck at this scale.

**Updating.** `git pull && docker compose up -d --build`. Schema additions are applied
automatically at start-up; built-in paper kinds, house style and templates are refreshed
without touching files an admin has edited.

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

LaTeX templates live in `data/templates/<slug>/` as `meta.json` plus `wrapper.tex.j2`. Wrappers
use LaTeX-safe Jinja delimiters (`<< title >>`, `<% for a in authors %>`, `<# comment #>`) and
receive `title`, `subtitle`, `authors`, `institutes`, `abstract`, `keywords_lncs`,
`keywords_csv`, `body`, `has_bib` and `venue` (the project's target venue, used for running headers).

Figures are inserted in a section as `![Caption](figures/name.svg){#fig:name}` and referred to
in the text as `Figure @fig:name`. Export turns the reference into `\ref{fig:name}` for LaTeX and
into the figure's number for DOCX. The reference list is included only when a section actually
cites a verified key with `[@key]`. acmart is fetched by Tectonic automatically. Springer's `llncs.cls` and
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
