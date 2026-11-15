#!/usr/bin/env python3
"""Pick characteristic sessions and write redacted excerpts for scoring.

Usage:
    python3 sample.py --metrics metrics.json [--project DIR | --all-projects] [--logs-dir DIR] [--out samples.json]

Use the same scope options as extract.py (default: the current project).

Only redacted text leaves this script: human instructions, the AI's final
report of each turn, and per-turn action counts. Code blocks, secrets,
e-mail addresses, URLs, paths, host names and likely proper nouns are masked.
Tool commands and file names are never included.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aititle import evidence as V  # noqa: E402
from aititle import scope  # noqa: E402
from aititle.metrics import SessionStats, Turn, analyze  # noqa: E402
from aititle.redact import redact  # noqa: E402
from aititle.sources import claude_code  # noqa: E402

MAX_SESSIONS = 10
MAX_TURNS = 7
HUMAN_LIMIT = 500
AI_LIMIT = 300

_CATEGORY = {
    "Edit": "edit", "Write": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
    "Read": "read", "Grep": "search", "Glob": "search", "WebSearch": "web", "WebFetch": "web",
    "Bash": "shell", "PowerShell": "shell", "Agent": "subagent", "Task": "subagent",
    "Skill": "skill", "AskUserQuestion": "question",
}


def actions(turn: Turn) -> Dict[str, int]:
    c: Counter = Counter()
    for tool in turn.tools:
        c[_CATEGORY.get(tool, "mcp" if tool.startswith("mcp__") else "other")] += 1
    for m in V.VERIFICATION_METHODS + (V.PLAN,):
        if turn.behaviors[m]:
            c[m] = turn.behaviors[m]
    return dict(sorted(c.items()))


def pick_sessions(stats: Sequence[SessionStats], limit: int = MAX_SESSIONS) -> List[tuple]:
    candidates = [s for s in stats if len(s.turns) >= 2]
    criteria = [
        ("long_dialogue", lambda s: len(s.turns)),
        ("corrections", lambda s: sum(t.followup_fix for t in s.turns)),
        ("longest_autonomous_run", lambda s: max(t.tool_calls for t in s.turns)),
        ("verification", lambda s: sum(t.verified for t in s.turns)),
        ("reuse", lambda s: sum(1 for t in s.turns if t.kind == "command" or t.behaviors[V.REUSE])),
        ("interruptions", lambda s: sum(t.interrupted for t in s.turns)),
    ]
    chosen: List[tuple] = []
    used: Set[str] = set()
    for label, key in criteria:
        if len(chosen) >= limit:
            break
        ranked = sorted(candidates, key=lambda s: (-key(s), s.session.id))
        for s in ranked:
            if key(s) <= 0:
                break
            if s.session.id not in used:
                chosen.append((label, s))
                used.add(s.session.id)
                break
    # Fill the rest with sessions spread evenly over the period (not just the longest).
    rest = sorted((s for s in candidates if s.session.id not in used), key=lambda s: (s.turns[0].start, s.session.id))
    slots = limit - len(chosen)
    if rest and slots > 0:
        step = len(rest) / slots
        picked = sorted({min(len(rest) - 1, int(i * step + step / 2)) for i in range(slots)})
        chosen += [("typical", rest[i]) for i in picked]
    return chosen


def pick_turns(turns: Sequence[Turn], limit: int = MAX_TURNS) -> List[int]:
    n = len(turns)
    if n <= limit:
        return list(range(n))
    edge = max(1, (limit - 1) // 3)          # turns kept from the start and from the end
    keep = set(range(edge)) | set(range(n - edge, n))
    for i, t in enumerate(turns):
        if len(keep) >= limit:
            break
        if t.followup_fix or t.interrupted or t.queued:
            keep.add(i)
    step = max(1, n // limit)
    i = edge
    while len(keep) < limit and i < n:
        keep.add(i)
        i += step
    return sorted(keep)[:limit]


def excerpt(label: str, st: SessionStats, terms: Set[str]) -> dict:
    idx = pick_turns(st.turns)
    out_turns = []
    prev = -1
    for i in idx:
        if i - prev > 1:
            out_turns.append({"omitted_turns": i - prev - 1})
        t = st.turns[i]
        item = {
            "n": i + 1,
            "human": redact(t.text, terms, HUMAN_LIMIT) if t.kind == "prompt" else "(ran a reusable command)",
            "ai_actions": actions(t),
            "ai_report": redact(t.last_ai_text, terms, AI_LIMIT),
        }
        for flag, val in (("interrupted_by_human", t.interrupted), ("sent_while_ai_was_working", t.queued),
                          ("possible_correction", t.followup_fix), ("human_attached_image", t.image),
                          ("new_task_starts", any(k.turns[0] is t for k in st.tasks))):
            if val:
                item[flag] = True
        out_turns.append(item)
        prev = i
    if prev < len(st.turns) - 1:
        out_turns.append({"omitted_turns": len(st.turns) - 1 - prev})
    return {
        "why_selected": label,
        "turns_total": len(st.turns),
        "tasks": len(st.tasks),
        "used_subagents": st.session.subagent_logs > 0 or any(t.agents for t in st.turns),
        "in_worktree": st.session.in_worktree,
        "turns": out_turns,
    }


def all_terms(stats: Sequence[SessionStats]) -> Set[str]:
    terms: Set[str] = set()
    for st in stats:
        terms |= st.session.sensitive_terms
    user = os.path.basename(os.path.expanduser("~"))
    if len(user) >= 3:
        terms.add(user)
    return terms


def build(stats: Sequence[SessionStats], limit: int = MAX_SESSIONS) -> dict:
    terms = all_terms(stats)
    return {
        "note": ("Redacted excerpts. Placeholders: [CODE] code, [LOG] pasted logs, [SECRET], [EMAIL], "
                 "[URL], [PATH], [HOST], [NAME] likely proper noun, [ID] identifier, [NUM] long number. "
                 "ai_actions are counts per turn. possible_correction is a keyword-based guess."),
        "sessions": [excerpt(label, st, terms) for label, st in pick_sessions(stats, limit)],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metrics", type=Path, required=True, help="metrics.json from extract.py (for the period)")
    ap.add_argument("--logs-dir", type=Path, default=None)
    scope.add_arguments(ap)
    ap.add_argument("--out", type=Path, default=Path("samples.json"))
    ap.add_argument("--max-sessions", type=int, default=MAX_SESSIONS)
    args = ap.parse_args(argv)
    period = json.loads(args.metrics.read_text(encoding="utf-8"))["period"]
    since = claude_code.parse_ts(period["since"])
    until = claude_code.parse_ts(period["until"])
    read = claude_code.read_sessions(args.logs_dir, since, until, project=scope.resolve(args))
    data = build(analyze(read.sessions), args.max_sessions)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sessions sampled={len(data['sessions'])} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
