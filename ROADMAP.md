# Roadmap: fixation round after the field test (September 2026)

Source: the field test of 23–24 September 2026 (five personas through every entry point).
Decisions taken on 24 September: full scope including email and a user study; "Fix issues"
shows a diff the author accepts; the house style always wins over an author voice on hygiene;
interview answers about prior work cite the scan's candidates by title.

Guiding rule for every item: smooth usability without compromising quality. Fewer decisions
for the user, no silent changes to their text, nothing invented.

## Milestones

| Day | Milestone | Items |
|---|---|---|
| 1 | Studio quality | Fix issues (diff and accept) |
| 2 | Prose and interview | Hygiene post-pass; voice vs style enforcement; interview reads the scan |
| 3 | Beginner path | Search this claim; draft-first follow-through; pinned notes as claims |
| 4 | Fewer decisions | Budget wording and defaults; creation dialog trimmed; admin first-run checklist; exemplar nudge |
| 5 | Team features | SMTP settings; invitation mail; password reset |
| 6 | Deploy and re-test | VPS with Semantic Scholar key; Docker rebuild; newcomer persona re-run; regression |
| 7 | Study kit | Consent, questionnaire, participant guide page, step-timing instrumentation |
| 8 | Buffer and paper | Slack for what days 1–7 surface; Paper Writer paper gets the study design |
| +2 weeks | User study | Five colleagues, one paper each; then one day of analysis |

## Items

### 1. Fix issues (Studio)
- `POST /api/projects/{slug}/sections/{id}/fix` sends the section text and its lint findings to the
  utility model with the instruction "smallest edits that resolve these findings; change nothing
  else; keep every [NEEDS] and [@key]". Returns the revised text; nothing is saved.
- Studio shows a side-by-side diff (`lib/diff.ts` already exists) with Accept and Discard. Accept
  saves as a user edit, so the section becomes "edited" and is protected.
- Deterministic pre-pass runs first and is free: em dash to comma or full stop by context,
  semicolon to full stop with capitalisation, double spaces. The model only sees what remains.
- Acceptance: on the newcomer's Related Work (10 findings) one click leaves at most 2, the
  citations and placeholders are untouched, the diff is readable on a phone.
- Cost: about 1.5k tokens per section.

### 2. Hygiene post-pass and voice vs style
- Every draft and redraft runs the deterministic pre-pass from item 1 before saving. The lint
  summary after drafting is stored in the job result so the Studio can say "drafted, 3 issues".
- The drafting system prompt states the precedence once more and lists the hygiene rules as
  hard constraints separately from the voice section; the voice profile's "instructions for
  drafting" are filtered against banned constructions (semicolons, dashes) when rendered.
- Acceptance: the voice-profile abstract redraft that produced 6 hygiene findings produces at
  most 2 after the pass; the voice remains audible (sentence length and openers change).

### 3. Interview reads the scan
- `generate_round` receives the top 8 scan candidates (title, year, one-line reason, abstract
  excerpt) when a scan exists. Questions tagged prior-work or gap get suggested answers that
  cite candidates by title, marked "a guess from the scan; confirm".
- The side chat's system prompt names the scan and the Sources page instead of Google Scholar.
- Acceptance: the newcomer's "what is the gap" question comes with a suggested answer naming at
  least two candidates; nothing is added to references without a click.
- Cost: about 1k tokens more per round.

### 4. Search this claim
- Every `[CITE: …]` request on the References page and every citation finding in the Studio's
  Issues tab gets a "Search" button that runs the existing search with the claim as query and
  scrolls to the results.
- Acceptance: from a placeholder to an accepted reference in two clicks.

### 5. Draft-first follow-through
- After import, compare the draft's section titles to the kind's section pattern using the
  existing `SECTION_HINTS` buckets; list missing buckets ("No Related Work, no Evaluation")
  with "Add section" buttons that append an outline heading and an empty section.
- `stepAfter` for draft-first projects points at Review after the Studio; the Studio header
  says "4 sections, 2 the kind expects are missing" instead of "4 of 4 drafted".

### 6. Pinned notes as claims
- Pins carry `unverified: true`. The outline prompt marks claims sourced from notes with a
  `[CITE: …]` placeholder; facts extraction already files them under Unverified.

### 7. Fewer decisions
- Playbook budgets renamed Quick look / Standard / Thorough, with tokens and minutes shown as
  a secondary line; Standard preselected.
- Creation dialog keeps starting point, title and kind. Author voice and target venue move to
  project settings; the Studio offers "Draft in a learned voice?" once when a profile exists;
  the Review page already suggests venues.
- Admin first-run checklist on the Library until a provider, a model per purpose and one
  member exist; each line links to its page.
- Sources page, under five exemplars: one banner with the ablation result and the scan's
  arXiv or open-PDF candidates as one-click exemplars.

### 8. Email
- SMTP settings in Settings → Site (host, port, user, password encrypted with the existing
  Fernet key, from address, "send test mail"). Invitations send the temporary password and a
  link; "Forgot password" issues a one-hour token; both fall back to the current on-screen
  behaviour when SMTP is unset.
- Tests with an in-process fake SMTP server.

### 9. Deploy and re-test
- VPS behind Caddy, `SECURE_COOKIES=true`, `SEMANTIC_SCHOLAR_API_KEY` set. Rebuild the image
  from main. Re-run the newcomer persona on the server: the scan must return candidates from
  at least two indexes with arXiv ids.

### 10. Study kit and user study
- Participants: five colleagues, each writing one paper about their own tool or idea, two weeks.
- Instrumentation (opt-in per workspace): step timings from job timestamps plus a light page
  event log (step entered, section saved, export downloaded), stored per user.
- Instruments: a public participant guide page (Pages), a consent text, a questionnaire
  (SUS plus five questions on trust, control and where they got stuck), a 20-minute interview.
- Data out: tokens per paper and step, time per step, reviewer verdicts over time, number of
  sections edited by hand, exports produced, questionnaire scores, interview themes.
- Use: the Evaluation section of the Paper Writer paper, which currently holds a placeholder.

## Needed from the workspace owner
- VPS or server with a domain, and who administers it.
- Semantic Scholar API key (free) and an SMTP account for the app's mail.
- Names of five colleagues willing to write one paper each in the two study weeks.
- The university's consent template, if one must be used.

## Not in this round
- Multi-process deployment, Postgres, strict app-page CSP, blended author voices.
