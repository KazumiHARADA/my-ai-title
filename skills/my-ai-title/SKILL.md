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
5. **Score** — Following [references/rubric.md](references/rubric.md), score the six axes 1–5 from the samples and metrics (apply the rubric's cap rule). Match the evidence to the level 1/3/5 descriptions: when it matches level 5, give 5. A 4 (or a 2) needs a named gap — the specific part of the level-5 (or level-3) description that is not met — written in `gaps`. Never lower a score just to be cautious. Then decide each judgment listed by
   `python3 ${CLAUDE_SKILL_DIR}/scripts/choose.py --list-judgments`
   as `"no"`, `"yes"` or `"strong"` (when unsure, `"no"`). Write `$WORK/scores.json`:
   ```json
   {"scores": {"context": 3, "delegation": 4, "verification": 4, "autonomy": 3, "efficiency": 3, "systems": 2},
    "judgments": {"precision": "yes", "keeneye": "no"},
    "evidence": {"context": "one or two sentences per axis, no identifying details"},
    "gaps": {"delegation": "which part of the level-5 description is not met (for every 4 or 2)"}}
   ```
6. **Choose** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/choose.py --scores $WORK/scores.json --metrics $WORK/metrics.json --lang <ja|en> --out $WORK/card.json --save-history`
   This picks the type, ability, quirk and rare status with the rules in [references/types.md](references/types.md) and fills in its fixed wording. `--save-history` keeps only the six scores (in `~/.claude/my-ai-title/history.json`) so the next run can detect growth. For a second language, run it again with the other `--lang`.
7. **Render** — Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/render.py --card $WORK/card.json`
   with no `--out` unless the user named a path. The card goes to `~/Desktop` (or, if that cannot be written, `~/.claude/my-ai-title`, then the working directory), named with today's date and never overwriting an earlier card, and is opened in the image viewer. If the user named a path and the script exits with code 3, the file already exists: ask the user, and only if they agree, rerun with `--force`. It uses a local Chromium-based browser if one is installed, otherwise draws a simpler card with Pillow; tell the user if the message says a fallback was used. If the message says the card could not be opened, say so.
8. **Report** — If the card was opened, do not read the PNG back; otherwise show it. Reply with this report every time, in the output language (an English example is in parentheses):

   - 能力【ability name】: ability why (Ability [name]: why)
     - クセ【quirk name】: quirk why (Quirk [name]: why) — leave out the why when it is empty
   - One sentence on what was read: the scope (this repository / all projects / the named project), the period, the number of sessions from `metrics.json`, and that only redacted excerpts and totals were used.
   - A table with one row per axis, in the order 文脈・委任・検証・自律・効率・仕組み (Context, Delegation, Verification, Autonomy, Efficiency, Systems), and the columns 軸 / 点 / 根拠 (Axis / Score / Evidence). Evidence is two or three plain sentences from `evidence` and, for a 4 or 2, `gaps`: what the user does, then what is still missing.
   - 伸びしろ（axis）(Room to grow (axis)): for the lowest-scoring axis (on a tie, the one with the most concrete gap), the main cause seen in the samples and one or two concrete things to try next time. Leave this out when every axis is 5.
   - The saved path of the card. Offer the other language.

   The report stays free of code, company names, file names, project names and people's names, like the card.

## Output language

Use the language the user asks for. Otherwise use `metrics.json`'s dominant log language: Japanese → `ja`, anything else → `en`.
