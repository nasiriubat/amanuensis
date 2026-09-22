"""Everything that is a document lives on disk under DATA_DIR.

This module owns the folder layout and the git-based version history. Nothing else
in the app should build data paths by hand.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from slugify import slugify as _slugify

from .config import get_settings

PLAYBOOK_FILES = ["structure.md", "argumentation.md", "evaluation.md", "related-work.md", "venue.md"]
KIND_FILES = ["kind.md", "sections.md", "interview.md", "checklist.md"]


def data_dir() -> Path:
    return get_settings().data_dir


def slugify(text: str, max_length: int = 60) -> str:
    s = _slugify(text, max_length=max_length) or "untitled"
    return s


def unique_slug(base: str, exists) -> str:
    """Append -2, -3 ... until `exists(slug)` is False."""
    slug = base
    n = 2
    while exists(slug):
        slug = f"{base}-{n}"
        n += 1
    return slug


# ---------------------------------------------------------------- projects


def project_dir(slug: str) -> Path:
    return data_dir() / "projects" / slug


def create_project_tree(slug: str, meta: dict) -> Path:
    root = project_dir(slug)
    if root.exists():
        raise FileExistsError(root)
    for sub in ["exemplars", "playbook", "inputs/uploads", "references", "sections", "figures"]:
        (root / sub).mkdir(parents=True, exist_ok=True)
    for name in PLAYBOOK_FILES:
        (root / "playbook" / name).write_text("", encoding="utf-8")
    (root / "inputs" / "system-spec.md").write_text("", encoding="utf-8")
    (root / "inputs" / "interview.md").write_text("", encoding="utf-8")
    (root / "inputs" / "facts.md").write_text("", encoding="utf-8")
    (root / "inputs" / "idea.md").write_text("", encoding="utf-8")
    (root / "inputs" / "research-plan.md").write_text("", encoding="utf-8")
    (root / "references" / "refs.bib").write_text("", encoding="utf-8")
    (root / "outline.md").write_text("", encoding="utf-8")
    (root / "checklist.json").write_text("[]\n", encoding="utf-8")
    (root / "project.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    git_init(root)
    git_commit(root, "Create project")
    return root


def delete_project_tree(slug: str) -> None:
    root = project_dir(slug)
    if root.exists():
        shutil.rmtree(root)


# ---------------------------------------------------------------- profiles


def profile_dir(slug: str) -> Path:
    return data_dir() / "profiles" / slug


def create_profile_tree(slug: str, meta: dict) -> Path:
    root = profile_dir(slug)
    if root.exists():
        raise FileExistsError(root)
    (root / "sources").mkdir(parents=True, exist_ok=True)
    (root / "style.md").write_text("", encoding="utf-8")
    (root / "profile.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    git_init(root)
    git_commit(root, "Create author profile")
    return root


def delete_profile_tree(slug: str) -> None:
    root = profile_dir(slug)
    if root.exists():
        shutil.rmtree(root)


# ---------------------------------------------------------------- kinds and house style


def kinds_dir() -> Path:
    return data_dir() / "kinds"


def kind_dir(slug: str) -> Path:
    return kinds_dir() / slug


def house_style_path() -> Path:
    return data_dir() / "house-style.md"


def seed_defaults() -> None:
    """Copy built-in kinds and house style into DATA_DIR on first boot.

    Existing files are never overwritten, so admin edits survive upgrades.
    """
    seed = get_settings().seed_dir
    kinds_dir().mkdir(parents=True, exist_ok=True)
    for src in sorted((seed / "kinds").iterdir()):
        if not src.is_dir():
            continue
        dst = kind_dir(src.name)
        dst.mkdir(exist_ok=True)
        for f in src.iterdir():
            target = dst / f.name
            if not target.exists():
                shutil.copy2(f, target)
    if not house_style_path().exists():
        shutil.copy2(seed / "house-style.md", house_style_path())
    (data_dir() / "templates").mkdir(exist_ok=True)


# ---------------------------------------------------------------- safe file access


def safe_child(root: Path, name: str) -> Path:
    """Resolve `name` under `root` and refuse anything that escapes it."""
    candidate = (root / name).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        raise ValueError("Path escapes its root")
    return candidate


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------- git (invisible versioning)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={
            "GIT_AUTHOR_NAME": "Paper Writer",
            "GIT_AUTHOR_EMAIL": "app@paper-writer.local",
            "GIT_COMMITTER_NAME": "Paper Writer",
            "GIT_COMMITTER_EMAIL": "app@paper-writer.local",
            "HOME": str(root),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        },
    )


def git_init(root: Path) -> None:
    if not (root / ".git").exists():
        _git(root, "init", "-q", "-b", "main")


def git_commit(root: Path, message: str) -> bool:
    """Stage everything and commit. Returns False when there was nothing to commit."""
    _git(root, "add", "-A")
    r = _git(root, "commit", "-q", "-m", message)
    return r.returncode == 0


def git_log(root: Path, path: str | None = None, limit: int = 50) -> list[dict]:
    args = ["log", f"-n{limit}", "--pretty=format:%H%x1f%ct%x1f%s"]
    if path:
        args += ["--", path]
    r = _git(root, *args)
    entries = []
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        sha, ts, subject = line.split("\x1f", 2)
        entries.append({"sha": sha, "timestamp": int(ts), "message": subject})
    return entries


def git_show(root: Path, sha: str, path: str) -> str:
    r = _git(root, "show", f"{sha}:{path}")
    return r.stdout if r.returncode == 0 else ""
