# Scoring Rubric

## Principles

- **Score behavior, not features.** Never award or deduct points for using (or not using) a specific tool, command, or feature. Feature usage found in the logs is only *evidence* of a behavior. Different routes to the same behavior earn the same score (e.g. parallel work via manual worktrees, subagents, or orchestrated workflows are equivalent).
- **Score judgment, not volume.** Higher counts are not better by themselves. What matters is whether the user adapts their approach to the situation.
- Each axis is scored 1–5. Levels 1, 3 and 5 are anchors. Decide by matching the evidence to the anchor descriptions: if the evidence matches level 5, give 5. Give 4 only when you can name which part of the level-5 description is not met, and state it in the evidence note. Likewise, give 2 only when you can name which part of the level-3 description is not met. Do not lower a score out of general caution.
- Numeric signals from `extract.py` are reference material. Decide the final score together with the session excerpts.
- For each axis, record 1–2 sentences describing the evidence behind the score. Never include code, company names, file paths, or other identifying details.

## Language

- Session logs may be in any language, often mixed with code and English. Score them identically regardless of language.
- Write evidence notes and advice in the output language specified by the skill.
- Do not judge clarity or quality of instructions by grammar, fluency, or language choice.

## 1. Context Design

Signals: persistent project instructions and how often they are updated, use of a planning step before implementation, rework caused by missing information

- **1**: Frequent rework caused by missing information; the agent often proceeds on wrong assumptions.
- **3**: Generally well communicated, but constraints or completion criteria are occasionally forgotten and added later, causing rework.
- **5**: Chooses between giving everything up front and working in stages (investigate → plan → implement) depending on the task, and rarely causes rework through missing information. Recurring project knowledge is kept in persistent files rather than repeated by hand.

Notes: Do not deduct for intentional staging, or for describing a symptom and letting the agent investigate. Deduct only for information that was *forgotten* and supplied afterward. Prompt length is not a score by itself.

## 2. Delegation

Signals: actions and files changed per instruction, parallel work streams, splitting work across agents

- **1**: Directs every task in small steps of a few lines at a time, regardless of the task.
- **3**: Delegates larger scopes, but the granularity sometimes does not fit the nature of the task.
- **5**: Adjusts granularity to risk and task type. Routine work is delegated in large units and parallelized; core design decisions and security-sensitive parts are kept in smaller, closely controlled steps.

Notes: Delegating a larger scope is not a merit by itself.

## 3. Verification

Signals: how often tests, builds and type checks run, visual or behavioral checks (screenshots, browser interaction), automated reviews, number of distinct verification methods, how often the human reports a problem after the agent declared the work done

- **1**: Accepts output as-is, or cannot proceed without the human manually checking every result.
- **3**: Runs tests or builds, but relies on the human for visual and behavioral checks.
- **5**: Has the agent verify its own work through multiple methods suited to the task (tests, types, visual checks, reviews). The human only spot-checks key points, and rarely needs to point out issues the agent missed.

Notes: Do not deduct for human spot-checking.

## 4. Autonomy Design

Signals: long-running or repeated unattended runs, rate of runs that finish successfully, turns or cost per successful run, how often the human stops a run midway

- **1**: Moves step by step through conversation even on tasks that could run autonomously.
- **3**: Runs autonomous loops, but completion criteria are vague and runs are often stopped midway.
- **5**: Sets explicit completion and stop conditions for autonomous runs, and their results are adopted with little change.

Notes: Not running autonomous loops is not a deduction by itself. Score low only when tasks suited to autonomy are consistently handled step by step.

## 5. Intervention Efficiency

Signals: instructions needed to complete a task, share of corrective instructions, rate of rework after completion

- **1**: Reaches the goal only after many course corrections.
- **3**: Reaches the goal with a few adjustments.
- **5**: Reaches the goal with few instructions; the result passes verification and is not reworked afterward.

**Cap rule:** If Verification is 2 or lower, Intervention Efficiency is capped at 3. Few interventions without verification usually means unchecked acceptance, not skill.

## 6. Systematization

Signals: reusable instructions, commands or automations and how often they are actually used, updates to persistent project instructions, repeated similar instructions and how their frequency changes over time

- **1**: Writes similar instructions by hand every time.
- **3**: Has created reusable assets, but many go unused, or repeated patterns remain.
- **5**: Notices repeated work, turns it into reusable assets, and uses them routinely.

Notes: Judge by usage, not by how many assets exist. A strong positive signal is a pattern of similar instructions that disappears after a reusable asset is created.

## Advice

Give 1–3 concrete next steps for the lowest-scoring axis or the axis with the most room to grow. Describe the behavior to adopt; a specific feature may be mentioned only as one example of how to achieve it.

- If repeated instructions have not been made reusable, show the pattern and how often it occurred (e.g. "Instructions like this appeared 8 times recently. This could be made reusable.").
- If the human often finds problems after the agent's own verification, suggest ways to strengthen self-verification, such as stating what to check or providing a reference image to compare against.

## Recorded only (not scored in the public version)

- Change size and number of files changed per task (for future difficulty adjustment).
