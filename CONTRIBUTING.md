# Contributing to Coscribe

Thank you for considering a contribution. This file tells you how the project is laid out, how to
run it, and what a good change looks like. Questions go in a GitHub issue.

## What we are building

A self-hosted co-author for research papers that never invents content: every number, name and
citation in a draft must come from something the author gave it, and gaps are marked instead of
filled. Contributions that weaken that rule will not be merged, however clever. Contributions that
make the rule easier to live with, more paper kinds, better prompts, better exports, are very welcome.

## Ways to contribute without writing code

- **Try it and report where you got stuck.** Open an issue with what you expected and what happened.
  Usability reports from real writing sessions are the most valuable thing we receive.
- **Paper kinds.** Each kind is a folder of four Markdown files under `backend/seed/kinds/<slug>/`:
  `kind.md` (what the kind is), `sections.md` (default sections and lengths), `interview.md`
  (rounds and example questions), `checklist.md` (what reviewers expect). A new kind is a pull
  request with four files and no code.
- **House style.** `backend/seed/house-style.md` is the prose hygiene rulebook. Propose changes
  with a reason; the lint reads its "Banned words and phrases" section.
- **Venue templates.** A template is `meta.json` plus `wrapper.tex.j2` under
  `backend/seed/templates/<slug>/`. Wrappers use `<< >>`, `<% %>` and `<# #>` delimiters. Do not
  add class files whose licence forbids redistribution (Springer's `llncs.cls` is one).
- **Prompts.** Everything the model is told lives in `backend/app/learn/prompts/*.j2`. Improvements
  should come with a before-and-after example from a real project.

## Running it locally

Backend (Python 3.12, [uv](https://github.com/astral-sh/uv)):

```bash
cd backend
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -e ".[dev]"
cp ../.env.example ../.env          # set APP_SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
set -a; source ../.env; set +a
.venv/bin/uvicorn app.main:app --reload
```

Frontend (Node 20 or newer):

```bash
cd frontend
npm install
npm run dev                          # proxies /api to the backend
```

PDF export needs `pandoc` and `tectonic` on the PATH (the Docker image ships both). Everything
else works without them.

## Before you open a pull request

```bash
cd backend && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

- One change per pull request, with a test when behaviour changes. The backend tests run against
  a temporary data directory and a stubbed model, so a test never needs an API key.
- Model calls in tests are faked by monkeypatching `complete` in the module under test; see
  `backend/tests/test_readings.py` for the pattern.
- Anything that starts a background job must be an `async def` endpoint.
- Keep the flow rule: one `nextStep()` in `frontend/src/lib/flow.ts` decides what the user does
  next, and every screen reads it. Do not add a second source of guidance.
- Prose in the UI: plain sentences, no jargon the user did not introduce, one action per button.
  Say what happens, not how it is implemented.
- Commits: a short imperative subject, a body that says why.

## Where things live

```
backend/app/
  routers/      HTTP endpoints, one file per area
  learn/        playbook and voice learning, prompt templates in learn/prompts/
  interview/    research design, interview rounds, facts, outline, side chat
  studio/       sections, drafting, lint, hygiene pass, fix issues, critique
  refs/         reference search, literature scan, background readings, citation evidence
  figures/      Mermaid and uploaded figures, results tables
  export/       Pandoc + Tectonic export, templates
  mail.py       SMTP for invitations and password resets
  storage.py    the per-project file layout and git commits
backend/seed/   built-in kinds, house style, templates, study kit
frontend/src/
  pages/        one file per screen
  components/   shared pieces; layout/ holds the shell and top bar
  lib/          api client, flow rules, jobs, events, types
```

Each project is a folder of Markdown and JSON under the data directory with its own git history,
so anything the model produced can be read, diffed and reverted with ordinary tools.

## Reporting a security problem

Please do not open a public issue. See [SECURITY.md](SECURITY.md).

## Licence

By contributing you agree that your contribution is licensed under the MIT licence in
[LICENSE](LICENSE).
