---
name: my-ai-title
description: Diagnose how the user works with AI from their local Claude Code session logs, score six axes, and render a shareable trading-card PNG with their "AI title". Use when the user asks for AI肩書き診断, "AI肩書き診断して", "私のAIの使い方を診断して", "My AI Title", or wants a card/title describing their AI working style.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# My AI Title (AI肩書き診断)

Produce one 1200×675 PNG card that describes how the user works with AI. Numbers come from scripts; judgment (the six scores and the conditions marked （判定） in `types.md`) comes from you. Card wording always comes from the fixed text in `types.md` — never write card text from scratch.

## Privacy rules (always)

- Never open or read raw session logs (`~/.claude/projects/**`) yourself. Read only the redacted output of `sample.py` and the numbers in `metrics.json`.
- Send nothing anywhere. No network access is needed.
- The card never shows counts, ratios, durations, times of day, or anything that reveals working hours or time away.
- The card never shows code, company names, file names, or project names.

## Steps

All intermediate files go in a temporary work directory (`$WORK`, e.g. created with `mktemp -d`). Do not write them into the user's project. Run every script from the user's working directory (do not `cd` into `$WORK`): the default scope is decided by the working directory.

1. **Period and scope** — Default is the last 30 days of the **current project**: the scripts use the git root of the working directory (worktrees included) unless told otherwise. Use the user's period if they give one. If the user asks for all projects, add `--all-projects`; for another project, add `--project <dir>`. Pass the same scope option to both `extract.py` and `sample.py`.
2. **Extract** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/extract.py --days 30 --out $WORK/metrics.json`
3. **Check data volume** — If `metrics.json` shows fewer than 5 sessions, tell the user and ask whether to stop, continue with lower accuracy, or (when `scope` is `project`) widen to all projects with `--all-projects`.
4. **Sample** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/sample.py --metrics $WORK/metrics.json --out $WORK/samples.json`
   and read `$WORK/samples.json` (already redacted).
5. **Score** — Following [references/rubric.md](references/rubric.md), score the six axes 1–5 from the samples and metrics (apply the rubric's cap rule). Then decide each judgment listed by
   `python3 ${CLAUDE_SKILL_DIR}/scripts/choose.py --list-judgments`
   as `"no"`, `"yes"` or `"strong"` (when unsure, `"no"`). Write `$WORK/scores.json`:
   ```json
   {"scores": {"context": 3, "delegation": 4, "verification": 4, "autonomy": 3, "efficiency": 3, "systems": 2},
    "judgments": {"precision": "yes", "keeneye": "no"},
    "evidence": {"context": "one or two sentences per axis, no identifying details"}}
   ```
6. **Choose** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/choose.py --scores $WORK/scores.json --metrics $WORK/metrics.json --lang <ja|en> --out $WORK/card.json --save-history`
   This picks the type, ability, quirk and rare status with the rules in [references/types.md](references/types.md) and fills in its fixed wording. `--save-history` keeps only the six scores (in `~/.claude/my-ai-title/history.json`) so the next run can detect growth. For a second language, run it again with the other `--lang`.
7. **Render** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/render.py --card $WORK/card.json --out ./my-ai-title-card.png`
   (English: `--out ./my-ai-title-card-en.png`). If it exits with code 3, the file already exists: ask the user, and only if they agree, rerun with `--force`. It uses a local Chromium-based browser if one is installed, otherwise draws a simpler card with Pillow; tell the user if the message says a fallback was used.
8. **Show** — Show the image and tell the user where it was saved. Offer the other language.

## Output language

Use the language the user asks for. Otherwise use `metrics.json`'s dominant log language: Japanese → `ja`, anything else → `en`.
