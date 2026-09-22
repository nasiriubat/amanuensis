"""Shared checks for user-uploaded files.

Browsers report whatever content type they like, so every upload is sniffed by its first
bytes. SVG is XML and can carry scripts, so it is sanitised before storage and every
user-provided file is served with headers that stop it from running as a page.
"""

from __future__ import annotations

import re

# Headers for any response that returns a user-uploaded or user-generated file.
# `sandbox` without tokens means an SVG opened directly cannot run scripts or reach cookies.
FILE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-cache",
}

_SNIFFERS: list[tuple[str, str, callable]] = [
    ("image/png", ".png", lambda b: b[:8] == b"\x89PNG\r\n\x1a\n"),
    ("image/jpeg", ".jpg", lambda b: b[:3] == b"\xff\xd8\xff"),
    ("image/webp", ".webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
    ("application/pdf", ".pdf", lambda b: b[:5] == b"%PDF-"),
    ("image/svg+xml", ".svg", lambda b: _looks_like_svg(b)),
]


def _looks_like_svg(b: bytes) -> bool:
    head = b[:2048].lstrip()
    if head[:3] == b"\xef\xbb\xbf":
        head = head[3:]
    if not head.startswith(b"<"):
        return False
    lowered = head.lower()
    return b"<svg" in lowered and b"<html" not in lowered


def sniff(data: bytes, allowed: set[str]) -> tuple[str, str] | None:
    """Return (content_type, extension) when the bytes match one of `allowed` types."""
    for ctype, ext, test in _SNIFFERS:
        if ctype in allowed and test(data):
            return ctype, ext
    return None


_SCRIPT_RE = re.compile(rb"<\s*script\b.*?(?:<\s*/\s*script\s*>|/>)", re.IGNORECASE | re.DOTALL)
_HANDLER_RE = re.compile(rb"""\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""", re.IGNORECASE)
_JS_URL_RE = re.compile(rb"""(\s(?:xlink:)?href\s*=\s*["'])\s*javascript:[^"']*(["'])""", re.IGNORECASE)
_FOREIGN_RE = re.compile(rb"<\s*foreignObject\b.*?<\s*/\s*foreignObject\s*>", re.IGNORECASE | re.DOTALL)
_DOCTYPE_ENTITY_RE = re.compile(rb"<!DOCTYPE[^>]*\[.*?\]\s*>", re.IGNORECASE | re.DOTALL)


def sanitize_svg(data: bytes) -> bytes:
    """Strip scripts, event handlers, javascript: links, embedded HTML and entity expansions."""
    out = _DOCTYPE_ENTITY_RE.sub(b"", data)
    out = _SCRIPT_RE.sub(b"", out)
    out = _FOREIGN_RE.sub(b"", out)
    out = _HANDLER_RE.sub(b"", out)
    out = _JS_URL_RE.sub(rb"\1#\2", out)
    return out


def safe_filename(name: str, fallback: str = "file") -> str:
    """Keep only the final path component and plain characters."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-")
    return base[:120] or fallback
