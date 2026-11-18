"""Log readers. Each reader turns one tool's logs into aititle.events.Session objects."""
from __future__ import annotations

from . import claude_code, codex

READERS = {"claude": claude_code, "codex": codex}


def get(name: str):
    try:
        return READERS[name]
    except KeyError:
        raise ValueError("source must be 'claude' or 'codex'")
