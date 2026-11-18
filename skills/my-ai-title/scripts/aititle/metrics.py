"""Events -> numbers.

Everything here is deterministic: the same events give the same metrics.
Thresholds and heuristics are named constants at the top so they can be tuned
in one place. Output contains numbers only (no text, names, or paths).
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Set

from . import evidence as V
from . import events as E
from .textutil import dominant_language, similar_clusters, size_units

TASK_GAP = timedelta(minutes=30)   # idle gap that starts a new task
LONG_RUN_TOOL_CALLS = 10           # a turn with this many tool calls = autonomous run
WIDE_TURN_FILES = 5                # files changed in one turn = wide delegation
SHORT_PROMPT_UNITS = 15            # size_units at or below = short instruction
REPEAT_MIN_CLUSTER = 3             # near-duplicate prompts that form a "pattern"
PATTERN_FOLLOWUP = timedelta(days=3)  # mechanism made this soon after a pattern's last use
PATTERN_QUIET = timedelta(days=7)     # ...and the pattern stayed gone at least this long

# Cues that a follow-up prompt is a correction. Judged again by the AI host from the
# samples; this is only an estimate.
FIX_CUE_RE = re.compile(
    r"違う|ちがう|動かない|動いてない|うまくいかない|上手くいかない|おかしい|エラー|失敗"
    r"|戻して|ダメ|だめ|できてない|出来てない|なってない|されない|崩れ|ずれ|ズレ"
    r"|効いてない|反映されて(ない|いない)|直ってない|治ってない"
    r"|\b(wrong|doesn'?t work|not working|still (fails|failing|broken|wrong|not)|broken|revert"
    r"|incorrect|regress\w*|didn'?t work|isn'?t working|not fixed)\b",
    re.IGNORECASE,
)
PLAN_CUE_RE = re.compile(
    r"計画|プラン|方針|段取り|設計して|まず.{0,10}(調べ|調査|整理)|実装(する)?前に"
    r"|\b(plan|planning|approach|design doc|before (you )?(start|implement))\b",
    re.IGNORECASE,
)
# Cues that a follow-up prompt asks the AI to check its work.
VERIFY_CUE_RE = re.compile(
    r"確認して|確かめて|テストして|テストを(書|回|実行|追加)|見せて|スクショ|スクリーンショット|動作確認"
    r"|検証して|レビューして|本当に|ちゃんと動|画面(を)?(見|確認)"
    r"|\b(check|verify|test it|run the tests?|screenshot|show me|are you sure|double-?check|review it)\b",
    re.IGNORECASE,
)
LONG_PROMPT_UNITS = 40             # size_units at or above = a long (background) explanation
_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


@dataclass
class Turn:
    start: datetime
    end: datetime
    text: str = ""
    kind: str = "prompt"                 # "prompt" or "command"
    queued: bool = False
    image: bool = False                  # the human attached an image
    tool_calls: int = 0
    behaviors: Counter = field(default_factory=Counter)
    files: Set[str] = field(default_factory=set)
    agents: int = 0                      # sub-agents started in this turn
    interrupted: bool = False
    denied: bool = False
    human_edits: int = 0
    last_ai_text: str = ""
    tools: List[str] = field(default_factory=list)
    task_end: bool = False
    boundary_before: bool = False        # a /clear-like command came right before
    followup_fix: bool = False

    @property
    def verified(self) -> bool:
        return any(self.behaviors[m] for m in V.VERIFICATION_METHODS)


@dataclass
class Task:
    turns: List[Turn]

    @property
    def prompts(self) -> int:
        return sum(1 for t in self.turns if t.kind == "prompt")

    @property
    def tool_calls(self) -> int:
        return sum(t.tool_calls for t in self.turns)

    @property
    def files(self) -> Set[str]:
        out: Set[str] = set()
        for t in self.turns:
            out |= t.files
        return out

    @property
    def fixes(self) -> int:
        return sum(1 for t in self.turns if t.followup_fix)

    @property
    def minutes(self) -> float:
        return (self.turns[-1].end - self.turns[0].start).total_seconds() / 60


@dataclass
class SessionStats:
    session: E.Session
    turns: List[Turn]
    tasks: List[Task]
    hooks: int = 0
    commands: List[str] = field(default_factory=list)


def _new_turn(ev: E.Event, kind: str, boundary: bool) -> Turn:
    return Turn(start=ev.ts, end=ev.ts, text=ev.text if kind == "prompt" else "",
                kind=kind, queued=ev.flags.get("source") == "queued",
                image=bool(ev.flags.get("image")),
                boundary_before=boundary)


def _apply(turn: Turn, ev: E.Event) -> None:
    turn.end = max(turn.end, ev.ts)
    if ev.kind == E.TOOL_CALL:
        turn.tool_calls += 1
        turn.tools.append(ev.tool)
        for b in V.tool_behaviors(ev.tool, ev.target):
            turn.behaviors[b] += 1
        if V.TASK_END in V.tool_behaviors(ev.tool, ev.target):
            turn.task_end = True
        if ev.tool in _EDIT_TOOLS and ev.target:
            turn.files.add(ev.target)
        if ev.tool in ("Agent", "Task"):
            turn.agents += 1
        if ev.flags.get("background"):
            turn.behaviors["background"] += 1
    elif ev.kind == E.ASSISTANT_TEXT and ev.agent is None:
        turn.last_ai_text = ev.text
    elif ev.kind == E.INTERRUPT:
        turn.interrupted = True
    elif ev.kind == E.DENIAL:
        turn.denied = True
    elif ev.kind == E.HUMAN_EDIT:
        turn.human_edits += 1


def build_turns(session: E.Session) -> SessionStats:
    turns: List[Turn] = []
    hooks = 0
    commands: List[str] = []
    boundary = False
    pending_sub: List[E.Event] = []
    for ev in session.events:
        if ev.kind == E.HOOK:
            hooks += int(ev.flags.get("count", 1) or 1)
            continue
        if ev.agent is not None:
            if turns:
                _apply(turns[-1], ev)
            else:
                pending_sub.append(ev)
            continue
        if ev.kind == E.COMMAND:
            commands.append(ev.tool)
            if ev.tool in V.NEW_TASK_COMMANDS:
                boundary = True
            if ev.tool not in V.BUILTIN_COMMANDS:
                turns.append(_new_turn(ev, "command", boundary))
                boundary = False
            continue
        if ev.kind == E.PROMPT:
            turns.append(_new_turn(ev, "prompt", boundary))
            boundary = False
            continue
        if turns:
            _apply(turns[-1], ev)
    return SessionStats(session=session, turns=turns, tasks=split_tasks(turns),
                        hooks=hooks, commands=commands)


def split_tasks(turns: Sequence[Turn]) -> List[Task]:
    tasks: List[Task] = []
    for i, t in enumerate(turns):
        prev = turns[i - 1] if i else None
        new = (prev is None or t.boundary_before or prev.task_end
               or t.start - prev.end >= TASK_GAP)
        if new:
            tasks.append(Task(turns=[t]))
        else:
            tasks[-1].turns.append(t)
            earlier_edits = any(x.files or x.tool_calls for x in tasks[-1].turns[:-1])
            if t.kind == "prompt" and earlier_edits and FIX_CUE_RE.search(t.text):
                t.followup_fix = True
    return tasks


def analyze(sessions: Sequence[E.Session]) -> List[SessionStats]:
    return [s for s in (build_turns(x) for x in sessions) if s.turns]


# ---------------------------------------------------------------------------

def _median(xs: Sequence[float]) -> Optional[float]:
    return round(statistics.median(xs), 2) if xs else None


def _mean(xs: Sequence[float]) -> Optional[float]:
    return round(sum(xs) / len(xs), 2) if xs else None


def _share(n: int, d: int) -> Optional[float]:
    return round(n / d, 3) if d else None


def _max_streak(flags: Sequence[bool]) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def own_names(created: Dict[str, datetime], on_disk: Set[str]) -> Set[str]:
    return (set(created) | set(on_disk)) - V.BUNDLED_SKILLS


def _tool_family(name: str) -> str:
    m = re.match(r"(mcp__[^_]+(?:_[^_]+)*?)__", name)
    return m.group(1) if m else name


def mechanism_activity(stats: Sequence[SessionStats], on_disk: Set[str]):
    """Return (created: {name: first ts}, uses: [(ts, name, self_made)])."""
    created: Dict[str, datetime] = {}
    for st in stats:
        for ev in st.session.events:
            if ev.kind == E.TOOL_CALL and ev.tool == "Write":
                name = V.mechanism_name(ev.target)
                if name and name not in created:
                    created[name] = ev.ts
    own = own_names(created, on_disk)
    uses = []
    for st in stats:
        for ev in st.session.events:
            name = None
            if ev.kind == E.TOOL_CALL and ev.tool == "Skill" and ev.target:
                name = ev.target
            elif ev.kind == E.COMMAND and ev.tool not in V.BUILTIN_COMMANDS:
                name = ev.tool
            if name:
                base = name.split(":")[-1]
                uses.append((ev.ts, base, base in own and ":" not in name))
    return created, uses


def build_metrics(stats: Sequence[SessionStats], read: E.ReadResult,
                  since: datetime, until: datetime,
                  on_disk_mechanisms: Optional[Set[str]] = None) -> dict:
    on_disk_mechanisms = on_disk_mechanisms or set()
    turns = [t for st in stats for t in st.turns]
    prompt_turns = [t for t in turns if t.kind == "prompt"]
    tasks = [k for st in stats for k in st.tasks]
    work_tasks = [k for k in tasks if k.tool_calls > 0]
    prompts_text = [t.text for t in prompt_turns]
    sizes = [size_units(t.text) for t in prompt_turns]
    beh = Counter()
    for t in turns:
        beh.update(t.behaviors)

    # verification
    followups = [t for k in work_tasks for t in k.turns[1:] if t.kind == "prompt"]
    methods_used = [m for m in V.VERIFICATION_METHODS if beh[m] > 0]
    fix_turns = [t for t in turns if t.followup_fix]

    # autonomy
    long_runs = [t for t in turns if t.tool_calls >= LONG_RUN_TOOL_CALLS]
    queued = [t for t in prompt_turns if t.queued]

    # parallel
    worktree_sessions = sum(1 for st in stats if st.session.in_worktree)
    parallel_sessions = sum(
        1 for st in stats
        if st.session.in_worktree or st.session.subagent_logs
        or any(t.behaviors[V.PARALLEL] or t.agents for t in st.turns))

    # systematization
    created, uses = mechanism_activity(stats, on_disk_mechanisms)
    used_after = {n for (ts, n, _own) in uses if n in created and ts >= created[n]}
    clusters = [c for c in similar_clusters(prompts_text) if len(c) >= REPEAT_MIN_CLUSTER]
    prompt_ts = [t.start for t in prompt_turns]
    resolved = 0
    for c in clusters:
        times = sorted(prompt_ts[i] for i in c)
        for ts in sorted(set(created.values())):
            # A mechanism made soon after the pattern's last occurrence, with
            # enough time left in the window to see the pattern stay gone.
            if (times[-1] <= ts <= times[-1] + PATTERN_FOLLOWUP
                    and until - ts >= PATTERN_QUIET
                    and sum(1 for x in times if x < ts) >= REPEAT_MIN_CLUSTER):
                resolved += 1
                break

    # context
    memo_events = [ev for st in stats for ev in st.session.events
                   if ev.kind == E.TOOL_CALL and ev.tool in _EDIT_TOOLS and V.is_memo_file(ev.target)]
    memo_sessions = len({id(st) for st in stats for ev in st.session.events
                         if ev.kind == E.TOOL_CALL and ev.tool in _EDIT_TOOLS and V.is_memo_file(ev.target)})
    plan_tasks = sum(
        1 for k in work_tasks
        if any(t.behaviors[V.PLAN] for t in k.turns)
        or (PLAN_CUE_RE.search(k.turns[0].text) and not k.turns[0].files))

    # explorer
    tools_in = {_tool_family(t) for x in turns for t in x.tools}
    before = {_tool_family(t) for t in read.tools_before_window}
    active_days = len({t.start.astimezone().date() for t in prompt_turns})
    days = max(1, round((until - since).total_seconds() / 86400))

    versions = sorted({v for st in stats for v in st.session.versions},
                      key=lambda v: [int(x) if x.isdigit() else 0 for x in v.split(".")])
    clean_short = [k for k in work_tasks if k.prompts <= 2 and k.fixes == 0
                   and not any(t.interrupted for t in k.turns)]

    return {
        "schema": 1,
        "source": "claude-code",
        "period": {"since": since.isoformat(), "until": until.isoformat(), "days": days},
        "data": {
            "sessions": len(stats),
            "tasks": len(tasks),
            "work_tasks": len(work_tasks),
            "human_prompts": len(prompt_turns),
            "active_days": active_days,
            "active_day_share": _share(active_days, days),
            "projects": len({st.session.project for st in stats}),
            "log_versions": [versions[0], versions[-1]] if versions else [],
            "unparseable_lines": read.unparseable_lines,
        },
        "language": dominant_language(prompts_text),
        "intervention": {
            "prompts_per_task_mean": _mean([k.prompts for k in work_tasks]),
            "prompts_per_task_median": _median([k.prompts for k in work_tasks]),
            "tasks_within_2_prompts_share": _share(sum(1 for k in work_tasks if k.prompts <= 2), len(work_tasks)),
            "tasks_within_2_prompts_no_rework": len(clean_short),
            "max_clean_task_streak": _max_streak([k.fixes == 0 for k in work_tasks]),
            "turns_per_session_mean": _mean([len(st.turns) for st in stats]),
            "turns_per_session_median": _median([len(st.turns) for st in stats]),
            "prompt_size_median": _median(sizes),
            "short_prompt_share": _share(sum(1 for s in sizes if s <= SHORT_PROMPT_UNITS), len(sizes)),
            "task_minutes_median": _median([k.minutes for k in work_tasks]),
        },
        "delegation": {
            "tool_calls_per_prompt_mean": _mean([t.tool_calls for t in prompt_turns]),
            "tool_calls_per_prompt_median": _median([t.tool_calls for t in prompt_turns]),
            "files_changed_per_prompt_mean": _mean([len(t.files) for t in prompt_turns]),
            "files_changed_per_task_mean": _mean([len(k.files) for k in work_tasks]),
            "wide_turn_share": _share(sum(1 for t in prompt_turns if len(t.files) >= WIDE_TURN_FILES), len(prompt_turns)),
            "short_and_wide_turn_share": _share(
                sum(1 for t in prompt_turns if len(t.files) >= 3 and size_units(t.text) <= SHORT_PROMPT_UNITS),
                len(prompt_turns)),
            "human_edits": sum(t.human_edits for t in turns),
        },
        "verification": {
            "test_runs": beh[V.V_TEST],
            "build_runs": beh[V.V_BUILD],
            "typecheck_runs": beh[V.V_TYPECHECK],
            "lint_runs": beh[V.V_LINT],
            "visual_checks": beh[V.V_VISUAL],
            "review_runs": beh[V.V_REVIEW],
            "methods_used": len(methods_used),
            "verified_task_share": _share(sum(1 for k in work_tasks if any(t.verified for t in k.turns)), len(work_tasks)),
            "followup_fix_prompts_est": len(fix_turns),
            "followup_fix_task_share_est": _share(sum(1 for k in work_tasks if k.fixes), len(work_tasks)),
            "image_prompts": sum(1 for t in prompt_turns if t.image),
            "verify_request_share": _share(sum(1 for t in followups if VERIFY_CUE_RE.search(t.text)), len(followups)),
        },
        "parallel": {
            "subagent_calls": sum(t.agents for t in turns),
            "subagent_logs": sum(st.session.subagent_logs for st in stats),
            "max_agents_in_one_turn": max([t.agents for t in turns], default=0),
            "worktree_sessions": worktree_sessions,
            "background_tasks": beh["background"],
            "sessions_with_parallel_share": _share(parallel_sessions, len(stats)),
        },
        "autonomy": {
            "long_runs": len(long_runs),
            "long_runs_completed": sum(1 for t in long_runs if not t.interrupted and not t.denied),
            "long_runs_interrupted": sum(1 for t in long_runs if t.interrupted),
            "interrupts": sum(1 for t in turns if t.interrupted),
            "mid_run_messages": len(queued),
            "user_denials": sum(1 for t in turns if t.denied),
            "autonomy_tool_calls": beh[V.AUTONOMY],
        },
        "systems": {
            "mechanism_calls": len(uses),
            "own_mechanism_calls": sum(1 for u in uses if u[2]),
            "hook_runs": sum(st.hooks for st in stats),
            "automation_tool_calls": beh[V.AUTOMATION],
            "mechanisms_created": len(created),
            "mechanisms_created_used": len(used_after),
            "mechanisms_created_unused": len(set(created) - used_after),
            "own_mechanisms_unused": len((own_names(created, on_disk_mechanisms)) - {u[1] for u in uses}),
            "repeated_prompt_patterns": len(clusters),
            "repeated_prompts": sum(len(c) - 1 for c in clusters),
            "repeated_long_prompts": sum(1 for c in clusters for i in c[1:]
                                         if size_units(prompts_text[i]) >= LONG_PROMPT_UNITS),
            "patterns_gone_after_mechanism": resolved,
        },
        "context": {
            "memo_updates": len(memo_events),
            "memo_update_sessions": memo_sessions,
            "plan_task_share": _share(plan_tasks, len(work_tasks)),
            "plan_tool_calls": beh[V.PLAN],
            "compactions": sum(1 for st in stats for ev in st.session.events if ev.kind == E.COMPACT),
        },
        "breadth": {
            "distinct_tools": len(tools_in),
            "new_tools_this_period": len(tools_in - before) if before else None,
        },
    }
