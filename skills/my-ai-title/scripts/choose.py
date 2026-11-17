#!/usr/bin/env python3
"""scores.json + metrics.json -> card.json (type, ability, quirk, rare, wording).

Usage:
    python3 choose.py --scores scores.json --metrics metrics.json --lang ja|en
                      [--out card.json] [--save-history] [--history PATH]

scores.json (written by Claude):
    {"scores": {"context": 1-5, "delegation": ..., "verification": ..,
                "autonomy": .., "efficiency": .., "systems": ..},
     "judgments": {"<name>": "no" | "yes" | "strong", ...}}
Run with --list-judgments to see the judgment names.

All card wording comes from references/types.md. The only state kept is the
previous six scores (for "growth"), in ~/.claude/my-ai-title/history.json, and
only when --save-history is given.

This file is not called select.py on purpose: that name would shadow Python's
standard "select" module for every script in this directory.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aititle import typesdb  # noqa: E402
from aititle.selection import (JUDGMENTS, Ctx, Selection, largest_growth, select,  # noqa: E402
                               validate_scores)

SKILL_DIR = Path(__file__).resolve().parents[1]
CHAR_DIR = SKILL_DIR / "assets" / "characters"
HASHTAG = "#MyAITitle"  # one tag for both languages, so all cards gather in one place
HISTORY_KEEP = 20
HISTORY_MIN_AGE = timedelta(hours=24)  # runs within a day replace each other


def default_history() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return Path(base) / "my-ai-title" / "history.json"


def load_history(path: Path) -> List[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data if isinstance(e, dict) and isinstance(e.get("scores"), dict)] if isinstance(data, list) else []


def previous_scores(history: List[dict], now: datetime) -> Optional[Dict[str, int]]:
    older = [e for e in history if _ts(e) and _ts(e) <= now - HISTORY_MIN_AGE]
    return max(older, key=_ts)["scores"] if older else None


def save_history(path: Path, history: List[dict], scores: Dict[str, int], now: datetime) -> None:
    kept = [e for e in history if _ts(e) and _ts(e) <= now - HISTORY_MIN_AGE]
    kept.append({"date": now.isoformat(), "scores": scores})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kept[-HISTORY_KEEP:], indent=2) + "\n", encoding="utf-8")


def _ts(entry: dict) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(entry.get("date")))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def pick_image(db: typesdb.TypesDB, sel: Selection, char_dir: Path = CHAR_DIR) -> str:
    """Character image with the fallbacks from the spec (section 7)."""
    t = sel.type
    others = [a.id for a in db.types[t].abilities if a.id != sel.ability.id]
    names: List[str] = []
    if sel.rare:
        names.append(f"{t}_{sel.ability.id}_rare")
    names.append(f"{t}_{sel.ability.id}")
    if sel.rare:
        names += [f"{t}_{o}_rare" for o in others]
    names += [f"{t}_{o}" for o in others]
    for n in names:
        for ext in (".png", ".webp"):
            if (char_dir / (n + ext)).is_file():
                return f"assets/characters/{n}{ext}"
    return f"assets/characters/fallback/{t}.svg"


def period_text(days: int, lang: str) -> str:
    if lang == "ja":
        return f"直近{days}日のClaude Codeログより"
    return f"Last {days} days of Claude Code logs"


def build_card(db: typesdb.TypesDB, sel: Selection, scores: Dict[str, int], days: int, lang: str,
               char_dir: Path = CHAR_DIR) -> dict:
    t = db.types[sel.type]
    a = sel.ability
    epithet = a.rare_epithet if sel.rare else a.epithet
    quote = a.rare_quote if sel.rare else a.quote
    why = a.why[lang]
    if "{axis}" in why:
        why = why.replace("{axis}", db.axis_names[sel.growth_axis][lang] if sel.growth_axis else "")
    if sel.quirk is None:
        quirk = {"id": "surplus", "name": t.surplus_quirk[lang], "why": ""}
    else:
        quirk = {"id": sel.quirk.id, "name": sel.quirk.name[lang], "why": sel.quirk.why[lang]}
    return {
        "lang": lang,
        "type": sel.type,
        "ability_id": a.id,
        "rare": sel.rare,
        "no": f"No.{a.no:02d}",
        "color": t.color,
        "title": {"epithet": epithet[lang] if lang == "ja" else epithet["en"],
                  "role": t.role[lang],
                  "en": f"The {epithet['en']} {t.role['en']}"},
        "quote": quote[lang],
        "ability": {"name": a.name[lang], "why": why},
        "quirk": quirk,
        "scores": scores,
        "days": days,
        "growth_axis": sel.growth_axis,
        "period": period_text(days, lang),
        "hashtag": HASHTAG,
        "image": pick_image(db, sel, char_dir),
    }


def localize(card: dict, lang: str, db: Optional[typesdb.TypesDB] = None,
             char_dir: Path = CHAR_DIR) -> dict:
    """Rebuild a card's wording in another language from its ids."""
    db = db or typesdb.load()
    quirk = None if card["quirk"]["id"] == "surplus" else next(q for q in db.quirks if q.id == card["quirk"]["id"])
    sel = Selection(type=card["type"], ability=db.ability(card["ability_id"]), ability_ratio=0.0,
                    quirk=quirk, rare=bool(card["rare"]), growth_axis=card.get("growth_axis"))
    return build_card(db, sel, card["scores"], int(card.get("days") or 30), lang, char_dir)


def run(scores_doc: dict, metrics: dict, lang: str, prev: Optional[Dict[str, int]],
        db: Optional[typesdb.TypesDB] = None, char_dir: Path = CHAR_DIR) -> dict:
    db = db or typesdb.load()
    lang = lang if lang in ("ja", "en") else "en"
    scores = validate_scores(scores_doc.get("scores", {}))
    judgments = {k: str(v) for k, v in (scores_doc.get("judgments") or {}).items()}
    ctx = Ctx(metrics=metrics, scores=scores, judgments=judgments, growth=largest_growth(scores, prev))
    sel = select(db, ctx)
    days = int(metrics.get("period", {}).get("days") or 30)
    return build_card(db, sel, scores, days, lang, char_dir)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scores", type=Path)
    ap.add_argument("--metrics", type=Path)
    ap.add_argument("--lang", default="ja")
    ap.add_argument("--out", type=Path, default=Path("card.json"))
    ap.add_argument("--history", type=Path, default=None)
    ap.add_argument("--save-history", action="store_true")
    ap.add_argument("--list-judgments", action="store_true")
    args = ap.parse_args(argv)
    if args.list_judgments:
        for k, v in JUDGMENTS.items():
            print(f"{k}: {v}")
        return 0
    if not args.scores or not args.metrics:
        ap.error("--scores and --metrics are required")
    scores_doc = json.loads(args.scores.read_text(encoding="utf-8"))
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    hist_path = args.history or default_history()
    history = load_history(hist_path)
    now = datetime.now(timezone.utc)
    gaps = scores_doc.get("gaps") or {}
    for axis, value in (scores_doc.get("scores") or {}).items():
        if value in (2, 4) and not str(gaps.get(axis, "")).strip():
            print(f"warning: {axis} is {value} but scores.json has no gaps.{axis} "
                  f"(name the unmet part of the level-{value + 1} description, or use {value + 1})", file=sys.stderr)
    card = run(scores_doc, metrics, args.lang, previous_scores(history, now))
    if args.save_history:
        save_history(hist_path, history, card["scores"], now)
    args.out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{card['type']} / {card['ability_id']}{' (rare)' if card['rare'] else ''} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
