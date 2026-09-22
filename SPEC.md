# Paper Writer — System Specification (v0.1, 2026-09-21)

An AI co-author that learns how good papers in a genre are structured, learns how a
specific author writes, interviews the user until their work fits a publishable
shape, then drafts the paper section by section with verified references and
exports it in a venue template.

## 1. Goals and non-goals

**Goals**

- Lightweight, self-hosted, Dockerized. Runs on a laptop or a small VPS.
- Multi-user with a secure admin. Admin credentials come from a seed (env vars) and
  can be changed later from the profile menu.
- Any LLM provider, selected by the admin. When a key is saved the app fetches that
  provider's model list so the admin picks from real names. A model is mapped per
  purpose, and can be overridden per project and per section when one model writes
  a given section better.
- Two layers of learned material. **Author profiles** capture one person's tone and
  way of writing, are built once from their papers, and can be reused in any project.
  **Playbooks** capture structure, argument, evidence and venue and belong to one
  project.
- Structured interview that turns "I built X" into a framed contribution.
- Section-by-section drafting. User edits are never overwritten.
- References are always verified records, never free text.
- Export to LaTeX, PDF and DOCX using built-in or user-uploaded venue templates.
- Card-based, typographically clean UI in the spirit of NotebookLM and Stripe.

**Non-goals**

- Not an Overleaf clone. No in-browser LaTeX compiler, no collaborative editing.
- No fabricated results, data, figures or citations. The tool asks for what is
  missing. When it cannot find a needed reference itself, it gives the user search
  keywords for Google Scholar and asks them to upload the papers they find.
- Not designed to evade AI-detection, but the prose must read as human. No stock AI
  phrases, no long chained sentences, no em dashes, and the author profile's tone is
  followed. See section 4.11. Goal is the author's voice, ideas and evidence; the tool
  structures and drafts. It reminds the user of venue disclosure policies.

## 2. Core concepts

| Concept | Owner | Stored as | Purpose |
|---|---|---|---|
| Author profile | a user, shareable | `data/profiles/<slug>/` | Voice: sentence rhythm, hedging, transitions, vocabulary |
| Paper kind | global, admin-editable | `data/kinds/<slug>/` | Prior knowledge for a genre: default sections, interview rounds, checklist, evidence expectations |
| Project | a user | `data/projects/<slug>/` | One paper; picks one kind, one author profile, one venue |
| Exemplars | project | `exemplars/` | 5–10 papers the playbook is learned from |
| Playbook | project | `playbook/*.md` | How this genre/venue frames contribution, structures sections, presents evidence |
| Inputs | project | `inputs/` | System spec, interview answers, user data and figures |
| Reference record | project | `references/<key>.json` + `refs.bib` | Verified metadata plus the snippet supporting each use |
| Section | project | `sections/NN-<name>.md` | Drafts, versioned by git |
| Checklist | project | `checklist.json` | Missing evidence per section |
| Venue template | global or user | `data/templates/<slug>/` | Class files plus a wrapper with placeholders |

## 3. Architecture

```
┌──────────────────────┐        ┌──────────────────────────────────────┐
│  React SPA (Vite)    │  HTTP  │  FastAPI                             │
│  Tailwind + shadcn   │ ◀────▶ │  auth · projects · jobs · llm · export│
│  CodeMirror, KaTeX,  │  SSE   │                                      │
│  Mermaid             │        │  SQLite (metadata)   data/ (files)   │
└──────────────────────┘        │  Pandoc · Tectonic · git             │
                                └──────────────────────────────────────┘
```

**Backend**: Python 3.12, FastAPI, SQLAlchemy 2 + SQLite, Pydantic v2.
**Frontend**: React 18, Vite, TypeScript, Tailwind, shadcn/ui, CodeMirror 6,
react-markdown + remark-math + KaTeX, mermaid.js, TanStack Query.
**Tooling in the container**: Pandoc, Tectonic (single-binary LaTeX), git,
Docling with its layout and table models (CPU build of PyTorch), pypdfium2.
**LLM calls**: official OpenAI and Anthropic SDKs behind two adapters, Pydantic for
structured output, Jinja prompt templates stored as files. No LangChain or LangGraph
(see section 9).

Everything runs in Docker via `docker compose` (section 6).

### 3.1 Storage

SQLite holds users, sessions, provider settings, model-per-purpose settings, token count per project, job
status, project and profile metadata, reference index. Everything that is a document
lives as files under `data/`. Copying `data/` plus the SQLite file is a full backup.

```
data/
  app.db
  profiles/<slug>/
    sources/                # uploaded papers of this author
    style.md                # learned voice profile (editable)
  projects/<slug>/
    exemplars/<id>/         # source.tex or source.pdf, extracted.md, meta.json
    playbook/
      structure.md          # section order, purpose and length of each section
      argumentation.md      # how gap and contribution are stated, with quotes
      evaluation.md         # what counts as evidence in these papers
      related-work.md       # how prior work is grouped and positioned
      venue.md              # target venue, page limit, template, AI policy
    inputs/
      system-spec.md
      interview.md
      uploads/
    references/
      refs.bib
      <key>.json            # metadata, source API, snippet, verified_at
    sections/
      00-abstract.md ... 07-conclusion.md
    figures/<name>.mmd + <name>.svg
    outline.md
    checklist.json
    .git/
  templates/
    lncs/ acm/ <user-slug>/
      class files, wrapper.tex.j2, meta.json
  kinds/
    tool-paper/ literature-review/ benchmark/ empirical-study/ position-paper/ other/
      kind.md               # what this genre is, what reviewers expect, common rejections
      sections.md           # default section skeleton with purpose and rough length
      interview.md          # question rounds for this genre
      checklist.md          # evidence a paper of this kind must have
  house-style.md
```

### 3.1.1 Paper kinds

At project creation the user picks a **kind**: tool paper, literature review,
benchmark, empirical study, position paper, or other. The kind is a prior, not a
cage. It gives the tool a sensible starting point before any exemplar is ingested:

- `sections.md` seeds the outline when no exemplars exist, and is merged with
  `playbook/structure.md` when they do. Exemplars win on conflicts, because they are
  real evidence of what the venue accepts.
- `interview.md` supplies the question rounds. A tool paper asks about users,
  evaluation and limitations. A literature review asks about search strategy,
  inclusion criteria and screening. A benchmark asks about tasks, metrics, baselines
  and reproducibility.
- `checklist.md` seeds the evidence checklist. A review without a PRISMA-style
  search description, or a benchmark without baseline numbers, is flagged from the
  first draft.

Kinds are plain Markdown folders, so the admin can edit the built-in ones or add a
new one (for example "experience report" or "dataset paper") without code changes.
"Other" ships empty and relies entirely on exemplars. The kind can be changed later
in project settings; doing so re-seeds unanswered interview rounds and open checklist
items, and never touches written sections.

Every project folder is a git repository. Each save and each generation is a commit.
The user sees "versions" and diffs; git is never exposed.

### 3.2 LLM layer

Two adapters cover nearly every provider:

- **OpenAI-compatible**: OpenAI, OpenRouter, Ollama, Groq, Together, Mistral,
  DeepSeek, Gemini (OpenAI endpoint), any custom base URL.
- **Anthropic**: native Messages API.

Admin adds providers (name, adapter, base URL, API key). Keys are encrypted at rest
with Fernet using `APP_SECRET_KEY` from the environment. On save the app calls the
provider's model-list endpoint and caches the result, with a refresh button and a
manual entry field for providers that do not expose a list. Admin then maps a model
to each **purpose**:

| Purpose | Typical need |
|---|---|
| `learn` | long context, careful reading of 5–10 papers |
| `interview` | good questions, tool calling |
| `draft` | strongest writing model |
| `critique` | strong reasoning, acts as reviewer |
| `utility` | cheap and fast: summaries, ranking search hits, extraction |

Model resolution for any call is a lookup chain: section override → project override
→ purpose default. Overrides are optional and most users never touch them.

Every call is logged (purpose, model, tokens, duration, project) so the admin usage
view can show cost per provider and token count per project. Structured outputs use
JSON mode where supported and a schema-validating retry otherwise, so weaker
providers still work.

### 3.3 Background jobs

Ingest, learn, search and export can take minutes. They run as in-process background
tasks with a job row in SQLite and progress streamed to the UI over Server-Sent
Events. No external queue in v1. If the app ever needs to scale, the job interface
stays the same and a worker can be added.

### 3.4 Context assembly

Context efficiency is a property of how prompts are built, not of any framework.
One module, the **context builder**, assembles every prompt from named parts. Each
part has a token budget and a priority; when the total exceeds the model's budget the
lowest priorities are excerpted or summarized first. Final sizes are logged per call.

Rules that keep calls small and good:

- **Stable prefix first, for caching.** Author profile, house style, playbook and
  paper facts are placed first and byte-identical across calls in a project, so
  provider prompt caching (Anthropic, OpenAI) makes repeated section calls cheap.
- **Map then reduce for learning.** Playbook and profile learning run one
  extraction call per paper into a structured summary, then one synthesis call
  across summaries. Never all papers in a single prompt.
- **Section-aligned excerpts.** When drafting a section, include only the matching
  section from two or three exemplars, looked up by heading in `extracted.md`. Full
  exemplars are never in a drafting prompt.
- **Neighbors as summaries.** A section call sees one-paragraph summaries of the
  other sections, not their full text, plus the full text of the immediately
  preceding section for flow.
- **Paper facts file.** `inputs/facts.md` holds defined terms, component names, key
  claims and every number in the paper, seeded from the interview and updated when
  the user resolves a checklist item. It is in every drafting and critique prompt and
  is the mechanism for cross-section coherence. Critique flags any section that
  contradicts it.

Typical budgets (tokens): drafting one section 15–25k; interview round 8–12k;
critique 15–20k; learning per paper 10–20k, synthesis 15–30k.

## 4. Pipeline

### 4.1 Ingest

- **arXiv**: paste ID or URL. Fetch metadata, try LaTeX source first (exact
  structure, figures as original files, tables as text, bib), fall back to PDF.
  Flatten `\input`s, extract sections, tables and figure captions directly.
- **PDF upload**: **Docling** (MIT) is the extractor. It handles reading order,
  two-column layouts, tables to Markdown and CSV, and detects figures with their
  captions and a coarse type (diagram, chart, photo). Runs on CPU, roughly 5–20 s
  per page, always as a background job. **pypdfium2** (BSD/Apache) is used for
  page thumbnails and for fast text-only passes where layout does not matter, such
  as pulling full text of a related-work paper for the model to read.
- **Figures**: every extracted or LaTeX-sourced figure is stored as an image with its
  caption. A vision-capable `utility` model writes a one-paragraph description at
  ingest (figure kind, what it shows, axes and series for charts). Descriptions feed
  playbook learning ("these papers all include an architecture diagram and a results
  table with baselines") and the checklist. Charts are never reconstructed.
- **Tables**: stored as Markdown for the model and CSV for the user.
- **References in PDFs**: the reference section is split into entries and each entry
  is resolved against Crossref and OpenAlex into a verified record. No GROBID.
- **Bib import**: `.bib` upload becomes verified-by-user reference records.
- All extraction dependencies are permissively licensed (MIT, BSD, Apache). No AGPL
  or GPL components, so the project can be released or sold under any license.
- Output per exemplar: `extracted.md` with heading hierarchy, inline tables and
  figure placeholders; `figures/` with images, captions and descriptions;
  `tables/` as CSV; `meta.json` (title, authors, venue, year, section list, word
  counts, figure and table inventory).

### 4.2 Learn

**Author profile** (from the author's own papers): one pass producing `style.md` —
sentence length distribution, paragraph openers, hedging patterns, transition
vocabulary, first-person usage, favorite constructions, things the author never does.
Quotes are included as evidence and the user can edit the file.

**Project playbook** (from exemplars): one pass per playbook file with a fixed
question set, for example "Across these papers, how is the contribution stated in
the introduction? Quote the sentences." Each file is Markdown, readable and editable.

### 4.3 Interview

Structured rounds rendered as cards. The rounds come from the paper kind's
`interview.md`; the model reads the system spec, the playbook and those rounds, and
generates the concrete questions that close the gap between them. Each card shows the
question, one line on why the paper needs it, an answer box, "not applicable", and a
suggested answer drafted from the system spec. The suggestion is visibly marked as a
guess, because the model does not know the user's system beyond the spec; the user
must confirm or rewrite it before it counts as an answer.
Answers append to `interview.md`. A side chat allows free thinking; anything useful
from chat can be pinned into `interview.md`. Typical rounds for a tool paper:
users and problem, existing approaches and their failures, design decisions,
evaluation performed, limitations and threats to validity.

### 4.4 Related work and references

Search through Semantic Scholar, OpenAlex and arXiv APIs (free, structured, DOIs).
Web search only as fallback for grey literature such as tool documentation. Results
are ranked by the `utility` model and shown as cards to accept or reject. For the
top accepted papers, full text is fetched from arXiv or open-access PDFs so related
work states what those papers did, not what their abstracts claim.

**Reference requests.** When drafting or critique needs a citation that search did
not find, the tool creates a request card: what claim needs support, suggested
Google Scholar keywords, and an upload slot. Uploaded PDFs become verified records.

Rules:
- Prose contains only citation keys, e.g. `[@smith2023tender]`.
- A key must resolve to a record with `verified_at` set (from an API, a bib import or
  an explicit user confirmation).
- Unverified keys render red in the preview and block export.
- Each use of a citation stores the snippet it supports, shown on hover.

### 4.5 Outline

Section-by-section plan, one line per paragraph, checked against
`playbook/structure.md` and the venue page limit. User approves or edits before any
prose is written.

### 4.6 Draft

One section per call, with author profile, playbook, outline, interview answers and
accepted references in context. The section card shows: draft, diff against previous
version, evidence checklist, and actions: *regenerate*, *regenerate with
instructions*, *mark as mine*. A section marked as mine cannot be regenerated without
explicit confirmation. Every change is a commit.

### 4.7 Checklist

`checklist.json` holds items per section such as "Evaluation: no participant count"
or "Introduction: claims faster than baseline, no number". Items are generated during
drafting and critique, shown in a persistent panel, and resolved by the user by
providing the evidence or marking it as a stated limitation.

### 4.8 Figures

Mermaid for architecture, flow, block and sequence diagrams. Rendered in the browser, saved
as SVG in `figures/`, converted to PDF for LaTeX at export. Result figures are never
generated from invented data; the checklist requests data or an image from the user.
If the user supplies a CSV, the tool can draw a chart from it.

### 4.9 Critique

A separate pass acting as a reviewer for the target venue: contribution clarity,
evidence gaps, missing related work, overclaiming, page budget. Findings become
checklist items or suggested edits, never silent changes.

### 4.10 Venue and export

- Model suggests up to three venues with a one-paragraph reason each. User can
  disagree and pick another or upload a custom template.
- Built-in templates: **Springer LNCS** and **ACM (acmart)** in v1, IEEE later.
- Custom template: user uploads class files and a sample document. The tool helps
  produce `wrapper.tex.j2` with placeholders for title, authors, abstract, body,
  bibliography, and records which bibliography style the venue expects.
- Export chain: sections → concatenated Markdown → Pandoc → LaTeX body → wrapper →
  Tectonic → PDF. DOCX via Pandoc with a CSL style. A LaTeX zip for Overleaf upload.
- Venue AI-disclosure policy is shown before export when known.

### 4.11 House style and prose lint

Two mechanisms keep the prose human.

- **House style file** (`data/house-style.md`, admin-editable): banned phrases and
  patterns ("delve", "it is worth noting", "in today's fast-paced", "not only ... but
  also", em dashes, triadic lists by reflex), sentence length target, one idea per
  sentence, preference for concrete nouns and active voice. It is injected into every
  drafting and critique prompt after the author profile, so the profile wins on tone
  and the house style wins on hygiene.
- **Deterministic lint** after every generation and on save: regex and simple stats,
  no LLM. Flags banned phrases, em dashes, sentences over a threshold, paragraphs
  with the same opener, and citation keys that do not resolve. Findings show inline
  in the editor like a spell checker. Cheap, instant, and it also catches the user's
  own habits.

## 5. Security

- Passwords hashed with argon2. Sessions in HttpOnly, SameSite=Lax cookies.
  CSRF token on state-changing requests.
- Roles: `admin`, `user`. First admin seeded from `ADMIN_EMAIL` and
  `ADMIN_PASSWORD` env vars on first boot; must be changed from the profile menu.
- Provider API keys encrypted at rest; never sent to the browser.
- Uploads validated by type and size; PDFs and LaTeX processed in the app container
  only, never shell-interpolated. Tectonic runs with shell escape disabled.
- Per-user isolation of projects. Author profiles can be marked shareable.
- Rate limits on auth and on LLM-triggering endpoints.

## 6. Deployment

Single Docker image, multi-stage: Node builds the SPA, Python image installs Pandoc,
Tectonic and git and serves both API and static bundle. `docker compose up` with an
`.env` file. A single volume for `data/`. Docling's models are baked into the image
so first use is offline and fast; the image is around 2–3 GB. Needs 2 vCPU and
3–4 GB RAM to extract a paper in a couple of minutes; 1 vCPU works but ingest is
slow. Tectonic downloads LaTeX packages on first compile and caches them in the
volume.

Configuration is env-first for bootstrap (secret key, admin seed, data path) and
UI-first for everything else (providers, models, templates, users).

## 7. UI

**Design language**: card surfaces on a soft neutral background, 12px radii,
1px borders instead of shadows, a single accent color, Inter or Geist for text and
JetBrains Mono for code and keys. Generous whitespace, strong type hierarchy, calm
motion. Dark mode from day one.

**Screens**

1. **Library**: cards for projects and author profiles, with progress rings. New
   project dialog: title, paper kind, author profile, optional venue.
2. **Project home**: cards for Sources, Playbook, Interview, Outline, References,
   Figures, Export, each showing status and the next action.
3. **Sources**: exemplar cards (title, venue, year, ingest status), add by arXiv ID or
   upload.
4. **Playbook and Profile**: editable Markdown files with quoted evidence.
5. **Interview**: question cards in rounds, side chat, progress.
6. **Studio**: left rail of sections with status chips; centre CodeMirror editor;
   right rendered preview with math, figures and hoverable citations; a collapsible
   checklist panel; version history drawer with diffs.
7. **References**: search, result cards, accepted list, verification status.
8. **Export**: template picker, compile log, download PDF, LaTeX zip, DOCX.
9. **Admin**: Providers, Models per purpose, Templates, Paper kinds, House style,
   Users, Usage.
10. **Profile menu**: change password, personal defaults.

## 8. Build phases

Each phase leaves a usable product.

1. **Skeleton**: repo layout, Docker, FastAPI + SQLite, auth with seeded admin,
   provider adapters, admin settings UI, project and profile CRUD, built-in paper
   kinds, design system.
2. **Ingest and learn**: arXiv and PDF ingest, exemplar cards, playbook and author
   profile generation, editable Markdown views.
3. **Interview and outline**: question rounds, side chat, outline approval.
4. **Studio**: section drafting, editor, preview, checklist, git versioning,
   mark-as-mine.
5. **References**: academic search, verification, bib import, red-key blocking,
   snippets on hover.
6. **Figures and export**: Mermaid, LNCS and ACM templates, Pandoc and Tectonic
   chain, DOCX, LaTeX zip.
7. **Polish**: critique pass, venue suggestion, custom template upload, usage
   dashboard, dark mode audit.

## 9. Decisions taken

- SQLite for metadata instead of pure files: an admin dashboard needs relational data.
- Two LLM adapters instead of a meta-library: smaller, fewer surprises.
- Markdown as the single source of truth; LaTeX and DOCX are exports.
- Structured interview over pure chat: produces citable input and visible progress.
- Tectonic over TeX Live: single binary, fits a small VPS.
- Docling as the one PDF extractor, always included, with permissive licenses only.
  Chosen over pymupdf4llm (AGPL) and over a split light/heavy design, because one
  good backend is simpler than two and the user accepted the larger image.
- Figures are understood through a vision model description at ingest, not
  reconstructed. References inside PDFs are resolved via Crossref and OpenAlex
  rather than parsed with GROBID.
- Author profiles are global and reusable; playbooks are per project.
- No LangChain or LangGraph. The pipeline is a fixed sequence of steps with user
  approval gates, which is plain Python. Memory is files and SQLite, already
  readable, editable and versioned. The only loop-shaped part (reference search:
  query, rank, fetch, refine) is a short function with tool calls. The framework
  would add a large dependency tree, abstractions that conflict with the two-adapter
  design, and harder debugging, for nothing the app needs. Revisit only if a truly
  open-ended agent is ever required.

## 10. Open items

- Whether to allow a project to blend two author profiles (co-authored papers).
- Does playbook learning produce advice the model would not give anyway? Phase 2
  must include a small test: learn a playbook from five real papers and compare
  drafts with and without it. If the gain is small, the learning prompts need work,
  not the architecture.
- Plagiarism guard: flag long n-gram overlap between drafts and exemplars. Cheap to
  add in phase 4.
