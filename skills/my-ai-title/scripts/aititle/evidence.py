"""Feature -> behavior evidence table.

The rubric scores behavior, not features. This module is the single place that
says "using feature X is evidence of behavior Y". When Claude Code (or another
tool) adds or renames a feature, update only this file.
"""
from __future__ import annotations

import re
from typing import Optional, Set

# --- Behaviors ---------------------------------------------------------------
PARALLEL = "parallel"        # several work streams at once
REUSE = "reuse"              # invoking a reusable asset (skill, command)
PLAN = "plan"                # planning before implementing
AUTONOMY = "autonomy"        # unattended / long-running execution
AUTOMATION = "automation"    # something that runs by itself (hooks, schedules)

# Verification methods (each counts as one "kind" of verification)
V_TEST = "test"
V_BUILD = "build"
V_TYPECHECK = "typecheck"
V_LINT = "lint"
V_VISUAL = "visual"
V_REVIEW = "review"
VERIFICATION_METHODS = (V_TEST, V_BUILD, V_TYPECHECK, V_LINT, V_VISUAL, V_REVIEW)

TASK_END = "task_end"        # a natural end of a task (commit, PR)

# --- Tool name -> behaviors ---------------------------------------------------
TOOL_BEHAVIOR = {
    "Agent": {PARALLEL},
    "Task": {PARALLEL},           # older name of the sub-agent tool
    "SendMessage": {PARALLEL},
    "EnterWorktree": {PARALLEL},
    "Workflow": {PARALLEL, AUTONOMY},
    "Skill": {REUSE},
    "EnterPlanMode": {PLAN},
    "ExitPlanMode": {PLAN},
    "TodoWrite": {PLAN},
    "TaskCreate": {PLAN},
    "Monitor": {AUTONOMY},
    "ScheduleWakeup": {AUTONOMY},
    "CronCreate": {AUTONOMY, AUTOMATION},
    "RemoteTrigger": {AUTOMATION},
}

# Tool names (often MCP tools) whose use is a visual / behavioral check.
VISUAL_TOOL_RE = re.compile(
    r"screenshot|browser|playwright|puppeteer|chrome|preview|computer_use|take_snapshot",
    re.IGNORECASE,
)
IMAGE_FILE_RE = re.compile(r"\.(png|jpe?g|gif|webp|bmp)$", re.IGNORECASE)
# Images Claude Code itself produced (e.g. PDF pages) are not visual checks.
INTERNAL_PATH_RE = re.compile(r"[/\\](tool-results|\.claude[/\\]projects)[/\\]")

# --- Shell command -> verification method / behavior -------------------------
_W = r"(?:^|[\s;&|(/])"  # start of a command word
BASH_RULES = [
    (V_TEST, re.compile(
        _W + r"(pytest|rspec|jest|vitest|mocha|ava|phpunit|ctest|tox|nox"
        r"|go test|cargo test|swift test|dotnet test|mix test|deno test|bun test"
        r"|rails test|rake test|rake spec|mvn test|gradle test|gradlew test"
        r"|playwright test|cypress run|python3? -m (pytest|unittest)"
        r"|(npm|pnpm|yarn)( run)? test)\b")),
    (V_TYPECHECK, re.compile(
        _W + r"(tsc|mypy|pyright|vue-tsc|srb tc|flow check|go vet)\b|type-?check")),
    (V_LINT, re.compile(
        _W + r"(eslint|rubocop|ruff|flake8|pylint|golangci-lint|biome|stylelint"
        r"|shellcheck|cargo clippy|swiftlint|(npm|pnpm|yarn)( run)? lint)\b")),
    (V_BUILD, re.compile(
        _W + r"((npm|pnpm|yarn)( run)? build|vite build|next build|webpack|cargo build"
        r"|go build|make|cmake --build|gradle build|gradlew assemble|mvn package"
        r"|xcodebuild|docker build|docker compose build)\b")),
    (V_VISUAL, re.compile(
        _W + r"(screencapture|webkit2png|agent-browser|playwright screenshot)\b"
        r"|--screenshot")),
    (PARALLEL, re.compile(r"\bgit worktree add\b")),
    (TASK_END, re.compile(r"\bgit commit\b|\bgh pr create\b")),
]

# --- Skills / slash commands ---------------------------------------------------
REVIEW_NAME_RE = re.compile(r"review", re.IGNORECASE)

# Slash commands that come with Claude Code. Anything else the human types as a
# slash command is a reusable asset (their own or a plugin's).
BUILTIN_COMMANDS = {
    "add-dir", "agents", "artifacts", "bug", "clear", "compact", "config", "context",
    "cost", "doctor", "effort", "exit", "export", "fast", "feedback", "help", "hooks",
    "ide", "init", "keybindings", "login", "logout", "mcp", "memory", "model",
    "output-style", "permissions", "plugin", "plugins", "pr-comments", "quit",
    "release-notes", "reload-plugins", "remote-control", "resume", "rewind",
    "sandbox", "status", "statusline", "terminal-setup", "theme", "todos",
    "upgrade", "usage", "vim", "workflows", "btw",
}
# Commands that start a fresh task.
NEW_TASK_COMMANDS = {"clear", "new", "reset"}

# Skills bundled with Claude Code (not built by the user).
BUNDLED_SKILLS = {
    "simplify", "code-review", "security-review", "init", "loop", "schedule",
    "claude-api", "update-config", "keybindings-help", "fewer-permission-prompts",
    "run", "find-skills", "workflow-authoring", "artifact-design",
    "artifact-capabilities", "artifact-diagramming", "dataviz", "plugin-authoring",
}

# --- Files ---------------------------------------------------------------------
# Persistent project notes (context the human keeps for the AI).
MEMO_FILE_RE = re.compile(
    r"(^|[/\\])(CLAUDE|AGENTS|GEMINI)(\.local)?\.md$|[/\\]\.claude[/\\]rules[/\\]",
    re.IGNORECASE,
)
# Files that define a reusable asset. Group 1/2 capture the asset's name.
MECHANISM_FILE_RE = re.compile(
    r"[/\\](?:skills[/\\]([^/\\]+)[/\\]SKILL\.md"
    r"|\.claude[/\\](?:commands|agents)[/\\]([^/\\]+?)\.md)$"
)
SETTINGS_FILE_RE = re.compile(r"[/\\]\.claude[/\\]settings(\.local)?\.json$")


# This skill's own runs: the part of a session from the request that started a
# diagnosis onward is left out, so diagnosing does not change the next result.
SELF_SKILL_RE = re.compile(r"(^|:)my-ai-title$")
SELF_SCRIPT_RE = re.compile(r"skills[/\\]my-ai-title[/\\]scripts[/\\](extract|sample|choose|render)\.py")


def is_self_run(tool: str, target: str) -> bool:
    if tool in ("Skill", "command") and SELF_SKILL_RE.search(target or ""):
        return True
    return tool in ("Bash", "PowerShell") and bool(SELF_SCRIPT_RE.search(target or ""))


def tool_behaviors(tool: str, target: str = "") -> Set[str]:
    """Behaviors evidenced by one tool call."""
    out = set(TOOL_BEHAVIOR.get(tool, ()))
    if VISUAL_TOOL_RE.search(tool):
        out.add(V_VISUAL)
    if tool == "Read" and IMAGE_FILE_RE.search(target) and not INTERNAL_PATH_RE.search(target):
        out.add(V_VISUAL)
    if tool == "Skill" and REVIEW_NAME_RE.search(target):
        out.add(V_REVIEW)
    if tool in ("Bash", "PowerShell") and target:
        out |= bash_behaviors(target)
    return out


def bash_behaviors(command: str) -> Set[str]:
    return {name for name, rx in BASH_RULES if rx.search(command)}


def mechanism_name(path: str) -> Optional[str]:
    """Name of the reusable asset defined by ``path``, if it defines one."""
    m = MECHANISM_FILE_RE.search(path)
    if not m:
        return None
    return m.group(1) or m.group(2)


def is_memo_file(path: str) -> bool:
    return bool(MEMO_FILE_RE.search(path))
