"""Reader for Codex session logs (~/.codex/sessions and archived_sessions).

Codex records a tool-independent stream of completed UI items in recent
versions and lower-level response items in older versions.  This reader prefers
the completed items when present and falls back to response items, normalizing
both into ``aititle.events``.  Sub-agent rollout files are skipped: their start
events are already present in the parent thread and forked history would
otherwise be counted twice.

Unknown fields and item types are ignored. Broken lines are counted and skipped.
Raw text is kept in memory only and is redacted by sample.py before being written.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set

from .. import events as E
from .claude_code import parse_ts, under

_GENERIC_DIRS = {
    "", "users", "home", "user", "projects", "project", "src", "repos", "repo",
    "workspace", "workspaces", "code", "dev", "work", "documents", "desktop",
    "tmp", "private", "var", "github", "git", "worktrees", ".codex", "codex",
    "volumes", "mnt", "c:", "d:", "main", "master", "develop", "feature", "fix",
    "feat", "chore", "bugfix", "hotfix", "release",
}
_SKILL_RE = re.compile(r"(?:^|\s)\$([a-z0-9][a-z0-9-]{1,63})\b", re.IGNORECASE)


def default_root() -> Path:
    return Path(os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex"))


def project_key(cwd: str) -> str:
    return hashlib.sha1(os.path.normpath(cwd).encode("utf-8", "replace")).hexdigest()[:10]


def _terms(value: str) -> Set[str]:
    out: Set[str] = set()
    for part in re.split(r"[/\\]", value):
        for piece in [part] + re.split(r"[-_.\s]+", part):
            if len(piece) >= 3 and piece.lower() not in _GENERIC_DIRS:
                out.add(piece)
    return out


def _iter_lines(path: Path) -> Iterator[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line
    except OSError:
        return


def _session_files(root: Path) -> Iterable[Path]:
    roots = []
    if root.name in ("sessions", "archived_sessions"):
        roots.append(root)
    else:
        roots.extend((root / "sessions", root / "archived_sessions"))
    seen: Set[Path] = set()
    for base in roots:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.jsonl")):
            if path not in seen:
                seen.add(path)
                yield path


def _text_blocks(content: object, *types: str) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    texts = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") not in types:
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text)
    return "\n".join(texts)


def _has_image(content: object) -> bool:
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") in ("local_image", "input_image", "image") for b in content
    )


def _json_object(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        obj = json.loads(value)
    except ValueError:
        return {}
    return obj if isinstance(obj, dict) else {}


def _tool_name(server: object, tool: object) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", str(server or "tool"))
    t = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(tool or "call")).replace(".", "__")
    return f"mcp__{s}__{t}"


def _target(args: dict) -> str:
    for key in ("cmd", "command", "file_path", "path", "skill", "code"):
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


class _SessionBuilder:
    def __init__(self, fallback_id: str):
        self.session = E.Session(id=fallback_id, project="")
        self.first_cwd = ""
        self.repo_url = ""
        self.workspace_roots: List[str] = []
        self.is_subagent = False
        self.seen_ids: Set[str] = set()

    def meta(self, payload: dict) -> None:
        sid = payload.get("session_id") or payload.get("id")
        if isinstance(sid, str) and sid:
            self.session.id = sid
        source = payload.get("source")
        self.is_subagent = isinstance(source, dict) and "subagent" in source
        self.is_subagent = self.is_subagent or bool(payload.get("parent_thread_id"))
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd:
            self.note_cwd(cwd)
        roots = payload.get("runtime_workspace_roots")
        if isinstance(roots, list):
            for root in roots:
                if isinstance(root, str) and root:
                    self.workspace_roots.append(root)
                    self.session.sensitive_terms |= _terms(root)
        version = payload.get("cli_version")
        if isinstance(version, str) and version:
            self.session.versions.add(version)
        git = payload.get("git")
        if isinstance(git, dict):
            branch = git.get("branch")
            if isinstance(branch, str):
                self.session.sensitive_terms |= _terms(branch)
            repo = git.get("repository_url")
            if isinstance(repo, str):
                self.repo_url = _normalize_repo_url(repo)
                self.session.sensitive_terms |= _terms(repo)

    def note_cwd(self, cwd: str) -> None:
        if not self.first_cwd:
            self.first_cwd = cwd
        if not self.session.project:
            self.session.project = project_key(cwd)
        if re.search(r"[/\\]\.codex[/\\]worktrees[/\\]", cwd):
            self.session.in_worktree = True
        self.session.sensitive_terms |= _terms(cwd)

    def add(self, event: E.Event, item_id: object = None) -> None:
        if isinstance(item_id, str):
            if item_id in self.seen_ids:
                return
            self.seen_ids.add(item_id)
        self.session.events.append(event)


def _normalize_repo_url(value: str) -> str:
    value = value.strip().lower().rstrip("/")
    value = re.sub(r"\.git$", "", value)
    value = re.sub(r"^[^@]+@([^:]+):", r"https://\1/", value)
    return value


def _repo_url(path: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return _normalize_repo_url(proc.stdout) if proc.returncode == 0 else ""


def _prompt_events(ts: datetime, content: object) -> List[E.Event]:
    text = _text_blocks(content, "text", "Text", "input_text")
    if not text.strip():
        return []
    flags = {"image": True} if _has_image(content) else {}
    out = [E.Event(ts, E.PROMPT, text=text, flags=flags)]
    for name in _SKILL_RE.findall(text):
        out.append(E.Event(ts, E.TOOL_CALL, tool="Skill", target=name))
    return out


def _completed_item(builder: _SessionBuilder, item: dict, ts: datetime) -> None:
    kind = item.get("type")
    item_id = item.get("id")
    if kind == "UserMessage":
        for event in _prompt_events(ts, item.get("content")):
            builder.add(event, item_id if event.kind == E.PROMPT else None)
    elif kind == "AgentMessage":
        text = _text_blocks(item.get("content"), "text", "Text", "output_text")
        if text.strip():
            builder.add(E.Event(ts, E.ASSISTANT_TEXT, text=text), item_id)
    elif kind == "CommandExecution":
        command = item.get("command")
        if isinstance(command, list):
            command = " ".join(str(x) for x in command)
        if not isinstance(command, str):
            command = ""
        cwd = item.get("cwd")
        if isinstance(cwd, str):
            builder.note_cwd(cwd)
        builder.add(E.Event(ts, E.TOOL_CALL, tool="Bash", target=command), item_id)
    elif kind == "FileChange":
        changes = item.get("changes")
        if isinstance(changes, dict):
            for path in changes:
                builder.add(E.Event(ts, E.TOOL_CALL, tool="Write", target=str(path)))
    elif kind == "McpToolCall":
        name = _tool_name(item.get("server"), item.get("tool"))
        args = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
        builder.add(E.Event(ts, E.TOOL_CALL, tool=name, target=_target(args)), item_id)
    elif kind == "SubAgentActivity" and item.get("kind") == "started":
        builder.add(E.Event(ts, E.TOOL_CALL, tool="Agent", target=str(item.get("agent_path") or "")), item_id)
    elif kind == "ImageView":
        builder.add(E.Event(ts, E.TOOL_CALL, tool="Read", target=str(item.get("path") or "")), item_id)
    elif kind == "Extension":
        label = str(item.get("kind") or item.get("action") or "extension")
        builder.add(E.Event(ts, E.TOOL_CALL, tool=label), item_id)
    elif kind == "ContextCompaction":
        builder.add(E.Event(ts, E.COMPACT), item_id)


def _response_item(builder: _SessionBuilder, payload: dict, metadata: dict, ts: datetime) -> None:
    if metadata.get("inherited_user_message"):
        return
    kind = payload.get("type")
    item_id = payload.get("id")
    if kind == "message":
        role = payload.get("role")
        if role == "user":
            for event in _prompt_events(ts, payload.get("content")):
                builder.add(event, item_id if event.kind == E.PROMPT else None)
        elif role == "assistant":
            text = _text_blocks(payload.get("content"), "output_text", "text", "Text")
            if text.strip():
                builder.add(E.Event(ts, E.ASSISTANT_TEXT, text=text), item_id)
    elif kind == "custom_tool_call":
        name = str(payload.get("name") or "tool")
        args = _json_object(payload.get("input"))
        tool = "Bash" if name == "exec" else name
        builder.add(E.Event(ts, E.TOOL_CALL, tool=tool, target=_target(args)), item_id)
    elif kind == "function_call":
        namespace = str(payload.get("namespace") or "")
        name = str(payload.get("name") or "tool")
        args = _json_object(payload.get("arguments"))
        if namespace == "collaboration" and name == "spawn_agent":
            tool = "Agent"
        elif namespace == "collaboration" and name in ("send_message", "followup_task"):
            tool = "SendMessage"
        elif name.startswith("request_user_input"):
            tool = "AskUserQuestion"
        else:
            tool = _tool_name(namespace, name) if namespace else name
        builder.add(E.Event(ts, E.TOOL_CALL, tool=tool, target=_target(args)), item_id)


def _read_file(path: Path, since: Optional[datetime], until: Optional[datetime], counters: Dict[str, int],
               before: Set[str], history_since: Optional[datetime]) -> Optional[_SessionBuilder]:
    # Newer rollouts contain normalized completed items. Prefer them to avoid
    # double-counting their lower-level response_item counterparts.
    high_level = any('"item_completed"' in line for line in _iter_lines(path))
    builder = _SessionBuilder(path.stem)
    for line in _iter_lines(path):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            counters["unparseable"] += 1
            continue
        if not isinstance(obj, dict):
            counters["unparseable"] += 1
            continue
        kind = obj.get("type")
        payload = obj.get("payload")
        if kind == "session_meta" and isinstance(payload, dict):
            builder.meta(payload)
            continue
        if not isinstance(payload, dict):
            continue
        ts = parse_ts(obj.get("timestamp") or payload.get("timestamp"))
        if ts is None:
            continue
        if since and ts < since:
            if history_since is None or ts < history_since:
                continue
            if high_level and kind == "event_msg" and payload.get("type") == "item_completed":
                item = payload.get("item")
                if isinstance(item, dict):
                    before |= _item_tools(item)
            elif not high_level and kind == "response_item":
                before |= _response_tools(payload)
            continue
        if until and ts >= until:
            continue
        try:
            if high_level and kind == "event_msg" and payload.get("type") == "item_completed":
                item = payload.get("item")
                if isinstance(item, dict):
                    _completed_item(builder, item, ts)
            elif not high_level and kind == "response_item":
                metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
                _response_item(builder, payload, metadata, ts)
        except Exception:
            counters["unparseable"] += 1
    return builder


def _item_tools(item: dict) -> Set[str]:
    kind = item.get("type")
    if kind == "CommandExecution":
        return {"Bash"}
    if kind == "FileChange":
        return {"Write"}
    if kind == "McpToolCall":
        return {_tool_name(item.get("server"), item.get("tool"))}
    if kind == "SubAgentActivity" and item.get("kind") == "started":
        return {"Agent"}
    if kind == "ImageView":
        return {"Read"}
    return set()


def _response_tools(payload: dict) -> Set[str]:
    kind = payload.get("type")
    name = str(payload.get("name") or "")
    if kind == "custom_tool_call":
        return {"Bash" if name == "exec" else name}
    if kind == "function_call":
        namespace = str(payload.get("namespace") or "")
        if namespace == "collaboration" and name == "spawn_agent":
            return {"Agent"}
        return {_tool_name(namespace, name) if namespace else name} if name else set()
    return set()


def read_sessions(root: Optional[Path] = None, since: Optional[datetime] = None,
                  until: Optional[datetime] = None, history_since: Optional[datetime] = None,
                  project: Optional[str] = None) -> E.ReadResult:
    root = root or default_root()
    counters = {"unparseable": 0}
    sessions: List[E.Session] = []
    before: Set[str] = set()
    skipped = 0
    project = os.path.abspath(os.path.expanduser(project)) if project else None
    wanted_repo = _repo_url(project) if project else ""
    for path in _session_files(root):
        try:
            builder = _read_file(path, since, until, counters, before, history_since)
        except OSError:
            skipped += 1
            continue
        if builder is None or builder.is_subagent:
            continue
        if project:
            paths = [builder.first_cwd] + builder.workspace_roots
            path_match = any(p and under(p, project) for p in paths)
            repo_match = bool(wanted_repo and builder.repo_url and wanted_repo == builder.repo_url)
            if not path_match and not repo_match:
                continue
        from ..sources.claude_code import _drop_self_runs
        _drop_self_runs(builder.session)
        builder.session.events.sort(key=lambda e: e.ts)
        if builder.session.events:
            sessions.append(builder.session)
    sessions.sort(key=lambda s: s.events[0].ts)
    return E.ReadResult(sessions=sessions, unparseable_lines=counters["unparseable"],
                        skipped_files=skipped, tools_before_window=before)


def skill_names_on_disk(root: Optional[Path] = None) -> Set[str]:
    """Names only of locally installed Codex skills."""
    base = root or default_root()
    dirs = [Path.home() / ".agents" / "skills", base / "skills"]
    out: Set[str] = set()
    for directory in dirs:
        if directory.is_dir():
            out |= {p.parent.name for p in directory.glob("*/SKILL.md")}
    return out
