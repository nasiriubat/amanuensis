"""Robust JSON parsing for structured LLM output, with one bounded repair retry.

Weaker providers occasionally wrap the object in prose or a code fence, or truncate it
at max_tokens. `extract_json` tolerates the first two; `complete_json` re-asks once when
the reply still will not parse, so a single hiccup does not fail a whole (already paid-for)
job. Replaces the identical `_parse_json` helpers that used to live in learn/, interview/
and refs/.
"""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from .base import Completion, Message
from .registry import complete

_FENCE = re.compile(r"^```[a-zA-Z]*\n(.*?)\n```$", re.DOTALL)


def extract_json(text: str) -> dict:
    """Parse the first JSON object in `text`, ignoring surrounding prose or a code fence."""
    t = text.strip()
    fence = _FENCE.fullmatch(t)
    if fence:
        t = fence.group(1).strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    return json.loads(m.group(0) if m else t)


async def complete_json(
    db: Session,
    purpose: str,
    messages: list[Message],
    **kwargs,
) -> tuple[dict, Completion]:
    """Run a JSON-mode completion and parse it, retrying once on a malformed reply.

    Returns (parsed_object, final_completion). Forwards every keyword (project, section,
    user_id, max_tokens, temperature) to `complete`. Both attempts are logged and billed,
    since both are real provider calls.
    """
    kwargs.setdefault("json_mode", True)
    result = await complete(db, purpose, messages, **kwargs)
    try:
        return extract_json(result.text), result
    except (json.JSONDecodeError, ValueError):
        repair = [
            *messages,
            Message("assistant", result.text[:4000]),
            Message("user", "Your previous reply was not valid JSON. Reply with only the JSON object, nothing else."),
        ]
        result = await complete(db, purpose, repair, **kwargs)
        return extract_json(result.text), result
