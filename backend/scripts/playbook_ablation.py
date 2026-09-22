"""Playbook value test (SPEC 10): draft one section with and without the learned playbook and exemplar
excerpts, then compare deterministically. The "with" run is saved as the real draft; the ablated run is
discarded after the comparison, so the test costs one extra model call.

Usage: cd backend && .venv/bin/python -m scripts.playbook_ablation <project-slug> <section-slug> [out-dir]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app import storage
from app.db import SessionLocal
from app.jobs import JobContext
from app.learn.stats import text_stats
from app.models import Project, User
from app.studio import lint as lint_mod
from app.studio import service as studio


def _report(label: str, text: str, target: int, house: str, keys: set[str], exemplars: dict[str, str]) -> dict:
    findings = lint_mod.lint(text, house, keys, exemplars)
    st = text_stats(text)
    return {
        "label": label,
        "words": studio._word_count(text),
        "target": target,
        "needs": text.count("[NEEDS:"),
        "cites": text.count("[@"),
        "lint": lint_mod.summarize(findings),
        "overlap_hits": sum(1 for f in findings if f["kind"] == "overlap"),
        "avg_sentence_words": st.get("avg_sentence_words"),
        "share_over_30_words": st.get("share_over_30_words"),
        "avg_paragraph_words": st.get("avg_paragraph_words"),
        "passive_per_100_sentences": st.get("passive_per_100_sentences"),
    }


async def main(slug: str, section_slug: str, out_dir: Path) -> None:
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.slug == slug))
        admin = db.scalar(select(User).where(User.role == "admin"))
        if not project or not admin:
            sys.exit("project or admin not found")
        pid, uid = project.id, admin.id
    root = storage.project_dir(slug)
    index = studio.load_index(root)
    sec = next((s for s in index["sections"] if s["slug"] == section_slug), None)
    if not sec:
        sys.exit(f"section {section_slug} not found; have {[s['slug'] for s in index['sections']]}")
    ctx = JobContext(job_id="ablation", user_id=uid)
    house = storage.read_text(storage.house_style_path())
    keys = studio.known_ref_keys(root)
    exemplars = studio.exemplar_texts(root)

    without = await studio.draft_section(pid, sec["id"], ctx, ablate=frozenset({"playbook", "exemplars"}), dry_run=True)
    withpb = await studio.draft_section(pid, sec["id"], ctx, force=True)
    saved = studio.read_section(root, sec)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{section_slug}-without-playbook.md").write_text(without["text"], encoding="utf-8")
    (out_dir / f"{section_slug}-with-playbook.md").write_text(saved, encoding="utf-8")
    rows = [
        _report("without playbook + exemplars", without["text"], sec["target_words"], house, keys, exemplars),
        _report("with playbook + exemplars", saved, sec["target_words"], house, keys, exemplars),
    ]
    tokens = {
        "without": (without["tokens_in"], without["tokens_out"]),
        "with": (withpb["tokens_in"], withpb["tokens_out"]),
    }
    print(json.dumps({"section": sec["title"], "rows": rows, "tokens": tokens}, indent=2))


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    asyncio.run(main(args[0], args[1], Path(args[2] if len(args) > 2 else "ablation-out")))
