"""Default landing copy and the two seeded public pages. Long lines are prose, not code."""

# ruff: noqa: E501

LANDING_DEFAULTS = {
    "eyebrow": "Self-hosted · your own API keys · every step is a file",
    "headline": "Write the paper your work deserves.",
    "subheadline": (
        "Amanuensis learns how papers in your field are built, learns how you write, "
        "interviews you until the work fits a publishable shape, then drafts one section at a time "
        "with verified references and exports a venue-ready PDF."
    ),
    "cta_primary": "Sign in",
    "cta_secondary": "See how it works",
    "why_chat": [
        "Context is rebuilt by hand every session and drifts.",
        "References are recalled from memory and often do not exist.",
        "Structure comes from the model's average paper, not your venue's.",
        "Voice is generic; reviewers spot it in a paragraph.",
        "Regeneration overwrites your edits.",
    ],
    "why_us": [
        "Playbook, facts, outline and drafts persist as Markdown under version control.",
        "Every citation key maps to a record fetched from Semantic Scholar, OpenAlex or arXiv.",
        "Section order, lengths and argumentative moves are learned from your exemplars.",
        "A voice profile is learned from an author's own papers and enforced by lint.",
        "Edited sections are yours; gaps become visible placeholders, not invented facts.",
    ],
    "principles": [
        {
            "title": "No invented facts",
            "text": "Drafts use only your specification, your answers and the facts sheet. Anything missing becomes a red [NEEDS] placeholder.",
        },
        {
            "title": "No invented references",
            "text": "A citation key exists only if a record was fetched from an academic API or imported from your .bib file.",
        },
        {
            "title": "Planned is not done",
            "text": "Facts extraction separates what was built and measured from what is still planned, and the drafts keep that distinction.",
        },
        {
            "title": "Your edits win",
            "text": "Sections you edit or write are protected. Regeneration asks first, and every version is recoverable.",
        },
        {
            "title": "Human prose",
            "text": "House style bans stock AI phrasing and enforces sentence rhythm; the voice profile sets the rest.",
        },
        {
            "title": "Your keys, your box",
            "text": "One container, one data volume. Prompts leave the server only to the provider you configured.",
        },
    ],
    "closing": "Accounts are created by the workspace administrator. Sign in to open your library.",
}


ABOUT_PAGE = """# About {name}

{name} is a self-hosted co-author for people who build things and want to publish them. It is not a chat window: every step of the work lives as a file you can open, diff and back up.

## What it does

1. **Learns the genre.** You add five to ten exemplar papers from arXiv or PDF. The tool measures how they are structured and learns how they argue, evaluate and position themselves.
2. **Learns the author.** An author profile is built from someone's own papers, so drafts sound like a person, not like a model.
3. **Interviews you.** Rounds of pointed questions with suggested answers, until the paper has everything the venue expects.
4. **Drafts one section at a time.** From an approved outline, with house-style lint, a checklist of open items and full version history.
5. **Verifies every reference.** Citations resolve to records fetched from Semantic Scholar, OpenAlex or arXiv. Nothing is cited from memory.
6. **Reviews and exports.** A reviewer-style critique pass, venue suggestions, then LNCS or ACM PDF, DOCX and a LaTeX archive.

## Who runs it

This instance is operated by its administrator. Model calls go to the provider they configured, with their own API keys. See the [contact page](/p/contact) to reach them.
"""

CONTACT_PAGE = """# Contact

Questions about this workspace, accounts or the tool itself go to the administrator.

- **Email:** {admin_email}

Accounts are created by the administrator. If you were invited, sign in with the temporary password you received and change it on your first visit.

## About the software

{name} is open source. Bug reports and feature requests belong in the project repository; ask the administrator for the link if it is not listed here.
"""
