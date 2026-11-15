#!/usr/bin/env python3
"""Claude Code session logs -> metrics.json (numbers only).

Usage:
    python3 extract.py [--days 30 | --since YYYY-MM-DD [--until YYYY-MM-DD]]
                       [--logs-dir DIR] [--out metrics.json]

Reads local files only. No network access. Output holds no text, names or paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aititle.metrics import analyze, build_metrics  # noqa: E402
from aititle.sources import claude_code  # noqa: E402

HISTORY_DAYS = 60  # look-back before the window, for "new tools this period"


def _date(s: str) -> datetime:
    dt = claude_code.parse_ts(s if "T" in s else s + "T00:00:00")
    if dt is None:
        raise argparse.ArgumentTypeError(f"invalid date: {s}")
    return dt


def window(args: argparse.Namespace) -> Tuple[datetime, datetime]:
    until = args.until or datetime.now(timezone.utc)
    since = args.since or (until - timedelta(days=args.days))
    return since, until


def run(logs_dir: Optional[Path], since: datetime, until: datetime) -> dict:
    read = claude_code.read_sessions(logs_dir, since, until,
                                     history_since=since - timedelta(days=HISTORY_DAYS))
    stats = analyze(read.sessions)
    on_disk = claude_code.skill_names_on_disk(logs_dir)
    return build_metrics(stats, read, since, until, on_disk)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--since", type=_date)
    ap.add_argument("--until", type=_date)
    ap.add_argument("--logs-dir", type=Path, default=None,
                    help="default: $CLAUDE_CONFIG_DIR/projects or ~/.claude/projects")
    ap.add_argument("--out", type=Path, default=Path("metrics.json"))
    args = ap.parse_args(argv)
    since, until = window(args)
    metrics = run(args.logs_dir, since, until)
    args.out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    d = metrics["data"]
    print(f"sessions={d['sessions']} tasks={d['tasks']} prompts={d['human_prompts']} "
          f"language={metrics['language']['dominant']} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
