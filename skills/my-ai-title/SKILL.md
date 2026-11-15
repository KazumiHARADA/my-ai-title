---
name: my-ai-title
description: Diagnose how the user works with AI from their local Claude Code session logs, score six axes, and render a shareable trading-card PNG with their "AI title". Use when the user asks for AI肩書き診断, "AI肩書き診断して", "私のAIの使い方を診断して", "My AI Title", or wants a card/title describing their AI working style.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# My AI Title (AI肩書き診断)

> DRAFT — the scripts referenced below are not implemented yet.

Produce one 1200×675 PNG card that describes how the user works with AI. Numbers come from scripts; judgment (the six scores and the conditions marked （判定） in `types.md`) comes from you. Card wording always comes from the fixed text in `types.md` — never write card text from scratch.

## Privacy rules (always)

- Never open or read raw session logs (`~/.claude/projects/**`) yourself. Read only the redacted output of `sample.py` and the numbers in `metrics.json`.
- Send nothing anywhere. No network access is needed.
- The card never shows counts, ratios, durations, times of day, or anything that reveals working hours or time away.
- The card never shows code, company names, file names, or project names.

## Steps

All intermediate files go in a temporary work directory (`$WORK`, e.g. created with `mktemp -d`). Do not write them into the user's project.

1. **Period** — Default is the last 30 days. Use the user's period if they give one.
2. **Extract** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/extract.py --days 30 --out $WORK/metrics.json`
3. **Check data volume** — If `metrics.json` shows fewer than 5 sessions, tell the user and ask whether to stop or continue with lower accuracy.
4. **Sample** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/sample.py --metrics $WORK/metrics.json --out $WORK/samples.json`
   and read `$WORK/samples.json` (already redacted).
5. **Score** — Following [references/rubric.md](references/rubric.md), score the six axes 1–5 from the samples and metrics. Also decide every condition marked （判定） in [references/types.md](references/types.md). Write `$WORK/scores.json`.
6. **Select** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/select.py --scores $WORK/scores.json --metrics $WORK/metrics.json --lang <ja|en> --out $WORK/card.json`
7. **Render** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/render.py --card $WORK/card.json --out ./my-ai-title-card.png`
   (English: `./my-ai-title-card-en.png`). If the file already exists, ask before overwriting.
8. **Show** — Show the image and tell the user where it was saved. Offer the other language.

## Output language

Use the language the user asks for. Otherwise use `metrics.json`'s dominant log language: Japanese → `ja`, anything else → `en`.
