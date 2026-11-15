"""Reader for Claude Code session logs (~/.claude/projects/**/*.jsonl).

Layout (Claude Code 2.1.x):
    <root>/<project-dir>/<sessionId>.jsonl                     main transcript
    <root>/<project-dir>/<sessionId>/subagents/agent-*.jsonl   sub-agent transcripts

Every line is a JSON object with a ``type``. Only ``user``, ``assistant``,
``system`` and some ``attachment`` lines matter here. Everything else (request
bodies, file snapshots, account ids, PR links, titles...) is skipped without
being parsed into events. Unknown types and fields are ignored; broken lines
are counted and skipped.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

from .. import events as E

# Line types that are never read. Checked on the raw text before json.loads so
# that the (large) request-body lines cost almost nothing.
_SKIP_PREFIX_RE = re.compile(
    r'^\{\s*"type"\s*:\s*"(api-request|api-request-blob|api-request-shape|file-history-'
    r'|last-prompt|mode|permission-mode|atis-latch|ai-title|session-owner'
    r'|cost-state|tools-used|isolation-latch|frame-link|custom-title'
    r'|artifact-|queue-operation)'
)

_TAG_RE = re.compile(r"^\s*<([a-z][a-z0-9-]*)[\s>]")
_COMMAND_NAME_RE = re.compile(r"<command-name>\s*/?([^<\s]+)\s*</command-name>")
_INTERRUPT_PREFIX = "[Request interrupted by user"
_IMAGE_PREFIX_RE = re.compile(r"^\[Image\b")
# Tags on human-role string messages that are not instructions typed by a human.
_NON_PROMPT_TAGS = {
    "task-notification", "bash-input", "bash-stdout", "bash-stderr",
    "local-command-stdout", "local-command-stderr", "local-command-caveat",
    "system-reminder", "user-memory-input", "teammate-message",
}
_GENERIC_DIRS = {
    "", "users", "home", "user", "projects", "project", "src", "repos", "repo",
    "workspace", "workspaces", "code", "dev", "work", "documents", "desktop",
    "tmp", "private", "var", "github", "git", "worktrees", ".claude", "claude",
    "volumes", "mnt", "c:", "d:", "main", "master", "develop", "feature", "fix",
    "feat", "chore", "bugfix", "hotfix", "release",
}


def default_root() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return Path(base) / "projects"


def parse_ts(value: object) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # Python 3.8/3.9 fromisoformat only accepts 3 or 6 fractional digits.
    s = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], s, count=1)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def project_key(cwd: str) -> str:
    base = re.split(r"[/\\]\.claude[/\\]worktrees[/\\]", cwd)[0]
    return hashlib.sha1(base.encode("utf-8", "replace")).hexdigest()[:10]


def _terms_from_cwd(cwd: str) -> Set[str]:
    out = set()
    for part in re.split(r"[/\\]", cwd):
        for piece in [part] + re.split(r"[-_.\s]+", part):
            if len(piece) >= 3 and piece.lower() not in _GENERIC_DIRS:
                out.add(piece)
    return out


def _terms_from_branch(branch: str) -> Set[str]:
    out = set()
    for piece in re.split(r"[/\-_.\s]+", branch):
        if len(piece) >= 4 and piece.lower() not in _GENERIC_DIRS and not piece.isdigit():
            out.add(piece)
    return out


def _iter_lines(path: Path) -> Iterator[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line
    except OSError:
        return


def _content_blocks(content: object) -> List[dict]:
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


class _SessionBuilder:
    def __init__(self, session_id: str):
        self.session = E.Session(id=session_id, project="")
        self.seen_uuids: Set[str] = set()
        self.first_cwd = ""   # memory only; used for --project filtering

    def note_meta(self, obj: dict) -> None:
        s = self.session
        cwd = obj.get("cwd")
        if isinstance(cwd, str) and cwd:
            if not self.first_cwd:
                self.first_cwd = cwd
            if not s.project:
                s.project = project_key(cwd)
            if re.search(r"[/\\]\.claude[/\\]worktrees[/\\]", cwd):
                s.in_worktree = True
            s.sensitive_terms |= _terms_from_cwd(cwd)
        branch = obj.get("gitBranch")
        if isinstance(branch, str) and branch:
            s.sensitive_terms |= _terms_from_branch(branch)
        version = obj.get("version")
        if isinstance(version, str):
            s.versions.add(version)


def _user_events(obj: dict, ts: datetime, agent: Optional[str]) -> List[E.Event]:
    out: List[E.Event] = []
    if obj.get("isMeta") or obj.get("isVisibleInTranscriptOnly"):
        return out
    if obj.get("isCompactSummary"):
        return [E.Event(ts, E.COMPACT, agent)]
    origin = obj.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return out  # task notifications, messages from other agents, ...
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return out
    flags: Dict[str, object] = {}
    source = obj.get("promptSource")
    if isinstance(source, str):
        flags["source"] = source
        if source in ("system", "sdk"):
            return out
    if obj.get("toolDenialKind") == "user-rejected":
        out.append(E.Event(ts, E.DENIAL, agent))
    tur = obj.get("toolUseResult")
    if isinstance(tur, dict) and tur.get("userModified") is True:
        out.append(E.Event(ts, E.HUMAN_EDIT, agent))

    content = msg.get("content")
    if isinstance(content, str):
        text = content
        if text.lstrip().startswith(_INTERRUPT_PREFIX):
            out.append(E.Event(ts, E.INTERRUPT, agent))
            return out
        m = _TAG_RE.match(text)
        if m:
            tag = m.group(1)
            if tag in ("command-name", "command-message"):
                cm = _COMMAND_NAME_RE.search(text)
                if cm:
                    out.append(E.Event(ts, E.COMMAND, agent, tool=cm.group(1).lower()))
                return out
            if tag in _NON_PROMPT_TAGS:
                return out
        if text.strip():
            out.append(E.Event(ts, E.PROMPT, agent, text=text, flags=flags))
        return out

    blocks = _content_blocks(content)
    if any(b.get("type") == "tool_result" for b in blocks):
        return out  # tool output, not a human instruction
    texts = []
    for b in blocks:
        if b.get("type") == "image":
            flags["image"] = True
        elif b.get("type") == "text":
            t = b.get("text")
            if not isinstance(t, str):
                continue
            if t.lstrip().startswith(_INTERRUPT_PREFIX):
                out.append(E.Event(ts, E.INTERRUPT, agent))
                return out
            if _IMAGE_PREFIX_RE.match(t.strip()):
                flags["image"] = True
                continue
            if _TAG_RE.match(t) and _TAG_RE.match(t).group(1) in _NON_PROMPT_TAGS:
                continue
            texts.append(t)
    if texts and any(t.strip() for t in texts):
        out.append(E.Event(ts, E.PROMPT, agent, text="\n".join(texts), flags=flags))
    return out


def _tool_target(name: str, inp: object) -> Tuple[str, Dict[str, object]]:
    flags: Dict[str, object] = {}
    if not isinstance(inp, dict):
        return "", flags
    if inp.get("run_in_background") is True:
        flags["background"] = True
    for key in ("command", "file_path", "notebook_path", "path", "skill"):
        v = inp.get(key)
        if isinstance(v, str) and v:
            return v, flags
    return "", flags


def _assistant_events(obj: dict, ts: datetime, agent: Optional[str]) -> List[E.Event]:
    msg = obj.get("message")
    if not isinstance(msg, dict) or obj.get("isApiErrorMessage"):
        return []
    out: List[E.Event] = []
    for b in _content_blocks(msg.get("content")):
        bt = b.get("type")
        if bt == "tool_use":
            name = b.get("name") if isinstance(b.get("name"), str) else ""
            target, flags = _tool_target(name, b.get("input"))
            out.append(E.Event(ts, E.TOOL_CALL, agent, tool=name, target=target, flags=flags))
        elif bt == "text":
            t = b.get("text")
            if isinstance(t, str) and t.strip():
                out.append(E.Event(ts, E.ASSISTANT_TEXT, agent, text=t))
    return out


def _system_events(obj: dict, ts: datetime, agent: Optional[str]) -> List[E.Event]:
    sub = obj.get("subtype")
    if sub == "stop_hook_summary":
        n = obj.get("hookCount")
        return [E.Event(ts, E.HOOK, agent, flags={"count": n if isinstance(n, int) else 1})]
    if sub == "compact_boundary":
        return [E.Event(ts, E.COMPACT, agent)]
    # turn_duration, away_summary (reveals time away: never used), etc.
    return []


def _attachment_events(obj: dict, ts: datetime, agent: Optional[str]) -> List[E.Event]:
    a = obj.get("attachment")
    if not isinstance(a, dict):
        return []
    t = a.get("type")
    if t == "hook_additional_context":
        return [E.Event(ts, E.HOOK, agent, flags={"count": 1})]
    if t == "edited_text_file":
        return [E.Event(ts, E.HUMAN_EDIT, agent)]
    return []


_HANDLERS = {
    "user": _user_events,
    "assistant": _assistant_events,
    "system": _system_events,
    "attachment": _attachment_events,
}


def _read_file(path: Path, builder: _SessionBuilder, agent: Optional[str],
               since: Optional[datetime], until: Optional[datetime],
               counters: Dict[str, int], before: Optional[Set[str]] = None,
               history_since: Optional[datetime] = None) -> None:
    for line in _iter_lines(path):
        if not line.strip():
            continue
        if _SKIP_PREFIX_RE.match(line):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            counters["unparseable"] += 1
            continue
        if not isinstance(obj, dict):
            counters["unparseable"] += 1
            continue
        t = obj.get("type")
        if t == "pr-link":
            repo = obj.get("prRepository")
            if isinstance(repo, str):
                builder.session.sensitive_terms |= {p for p in re.split(r"[/\-_.]", repo) if len(p) >= 3}
            continue
        handler = _HANDLERS.get(t) if isinstance(t, str) else None
        if handler is None:
            continue
        uuid = obj.get("uuid")
        if isinstance(uuid, str):
            if uuid in builder.seen_uuids:
                continue
            builder.seen_uuids.add(uuid)
        builder.note_meta(obj)
        ts = parse_ts(obj.get("timestamp"))
        if ts is None:
            continue
        if since and ts < since:
            if before is not None and t == "assistant" and (history_since is None or ts >= history_since):
                before.update(e.tool for e in _assistant_events(obj, ts, None) if e.kind == E.TOOL_CALL)
            continue
        if until and ts >= until:
            continue
        a = agent
        if a is None and obj.get("isSidechain") is True:
            a = str(obj.get("agentId") or "sidechain")
        try:
            evs = handler(obj, ts, a)
            if a is not None:
                # In a sub-agent transcript the "user" is the parent AI, not the human.
                evs = [e for e in evs if e.kind not in (E.PROMPT, E.COMMAND)]
            builder.session.events.extend(evs)
        except Exception:  # never let one odd line stop the run
            counters["unparseable"] += 1


_TOOL_NAME_RE = re.compile(r'"type"\s*:\s*"tool_use"\s*,\s*"id"\s*:\s*"[^"]*"\s*,\s*"name"\s*:\s*"([^"]+)"')


def _scan_tool_names(path: Path) -> Set[str]:
    """Cheap scan of tool names in an older file (regex, no JSON parsing)."""
    out: Set[str] = set()
    for line in _iter_lines(path):
        if "tool_use" in line and not _SKIP_PREFIX_RE.match(line):
            out.update(_TOOL_NAME_RE.findall(line))
    return out


def _session_files(root: Path) -> Iterable[Tuple[Path, List[Path]]]:
    if not root.is_dir():
        return
    for proj in sorted(p for p in root.iterdir() if p.is_dir()):
        for main in sorted(proj.glob("*.jsonl")):
            subs = sorted((proj / main.stem / "subagents").glob("*.jsonl"))
            yield main, subs


def under(path: str, prefix: str) -> bool:
    p, q = os.path.normpath(path), os.path.normpath(prefix)
    return p == q or p.startswith(q.rstrip(os.sep) + os.sep)


def read_sessions(root: Optional[Path] = None, since: Optional[datetime] = None,
                  until: Optional[datetime] = None,
                  history_since: Optional[datetime] = None,
                  project: Optional[str] = None) -> E.ReadResult:
    """Read all sessions with events in [since, until).

    ``project``: if given, only sessions that started in this directory (or
    below it, including its worktrees) are read.
    ``history_since``: if given, tool names used in [history_since, since) are
    collected (used for "new usage in this period"). Files last modified before
    ``since`` are scanned cheaply with a regex instead of being parsed.
    """
    root = root or default_root()
    counters = {"unparseable": 0}
    sessions: List[E.Session] = []
    before: Set[str] = set()
    skipped = 0
    project = os.path.abspath(os.path.expanduser(project)) if project else None
    encoded = re.sub(r"[^A-Za-z0-9]", "-", project) if project else ""
    for main, subs in _session_files(root):
        if project and not main.parent.name.startswith(encoded):
            continue
        try:
            mtime = datetime.fromtimestamp(max(p.stat().st_mtime for p in [main] + subs), timezone.utc)
        except OSError:
            skipped += 1
            continue
        if since and mtime < since:
            if history_since and mtime >= history_since:
                for p in [main] + subs:
                    before |= _scan_tool_names(p)
            skipped += 1
            continue
        b = _SessionBuilder(main.stem)
        _read_file(main, b, None, since, until, counters, before, history_since)
        for sub in subs:
            _read_file(sub, b, sub.stem, since, until, counters, before, history_since)
        if project and not under(b.first_cwd, project):
            continue
        b.session.subagent_logs = len(subs)
        b.session.events.sort(key=lambda e: e.ts)
        if b.session.events:
            sessions.append(b.session)
    sessions.sort(key=lambda s: s.events[0].ts)
    return E.ReadResult(sessions=sessions, unparseable_lines=counters["unparseable"],
                        skipped_files=skipped, tools_before_window=before)


def skill_names_on_disk(root: Optional[Path] = None) -> Set[str]:
    """Names (directory / file names only) of user-level skills and commands."""
    root = root or default_root()
    base = root.parent
    out: Set[str] = set()
    for sub, pattern in (("skills", "*/SKILL.md"), ("commands", "*.md"), ("agents", "*.md")):
        d = base / sub
        if d.is_dir():
            for p in d.glob(pattern):
                out.add(p.parent.name if sub == "skills" else p.stem)
    return out
