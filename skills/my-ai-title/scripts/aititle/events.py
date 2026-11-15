"""Tool-independent intermediate format.

A log reader (see ``aititle.sources``) turns one tool's raw logs into a list of
``Session`` objects, each holding an ordered list of ``Event``s. The metrics
code only ever sees this format, so supporting another tool means writing a new
reader, not touching the metrics.

Free text (``Event.text``, ``Event.target``) is kept in memory only. It is used
to compute numbers and, after redaction, by sample.py. It is never written to
metrics.json.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

# Event kinds
PROMPT = "prompt"                  # an instruction typed by the human
ASSISTANT_TEXT = "assistant_text"  # text the AI showed to the human
TOOL_CALL = "tool_call"            # the AI called a tool
INTERRUPT = "interrupt"            # the human stopped the AI mid-run
DENIAL = "denial"                  # the human rejected a tool call
HOOK = "hook"                      # an automation (hook) ran
COMMAND = "command"                # the human ran a slash command
HUMAN_EDIT = "human_edit"          # the human edited a file / an AI edit by hand
COMPACT = "compact"                # context was compacted


@dataclass
class Event:
    ts: datetime
    kind: str
    agent: Optional[str] = None   # sub-agent id; None for the main thread
    tool: str = ""                # tool name, slash-command name, or skill name
    text: str = ""                # prompt / assistant text (memory only)
    target: str = ""              # shell command or file path (memory only)
    flags: Dict[str, object] = field(default_factory=dict)


@dataclass
class Session:
    id: str
    project: str                  # opaque, hashed project key
    events: List[Event] = field(default_factory=list)
    in_worktree: bool = False
    subagent_logs: int = 0        # number of separate sub-agent transcripts
    versions: Set[str] = field(default_factory=set)
    # Words that identify the user's environment (directory names, branch
    # names, repository names). sample.py redacts them. Never output.
    sensitive_terms: Set[str] = field(default_factory=set)

    @property
    def main_events(self) -> List[Event]:
        return [e for e in self.events if e.agent is None]


@dataclass
class ReadResult:
    sessions: List[Session]
    unparseable_lines: int = 0
    skipped_files: int = 0
    # Tool names seen in logs older than the analysis window (for "new usage").
    tools_before_window: Set[str] = field(default_factory=set)
