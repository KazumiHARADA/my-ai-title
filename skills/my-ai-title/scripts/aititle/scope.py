"""Which sessions to diagnose: the current project by default.

Shared by extract.py and sample.py so both always read the same sessions.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from typing import Optional

_WORKTREE_RE = re.compile(r"[/\\]\.claude[/\\]worktrees[/\\].*$")


def project_root(cwd: Optional[str] = None) -> str:
    """The project for ``cwd``: its git top level (main checkout, not a
    worktree) when it is inside a git repository, otherwise ``cwd`` itself."""
    cwd = os.path.abspath(cwd or os.getcwd())
    root = cwd
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            root = out.stdout.strip()
        common = subprocess.run(["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, timeout=5)
        if common.returncode == 0 and os.path.basename(common.stdout.strip()) == ".git":
            root = os.path.dirname(common.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return _WORKTREE_RE.sub("", root)


def add_arguments(ap: argparse.ArgumentParser) -> None:
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--project", default=None,
                   help="diagnose sessions started in this directory or below it "
                        "(default: the current project, i.e. the git root of the working directory)")
    g.add_argument("--all-projects", action="store_true", help="diagnose sessions from every project")


def resolve(args: argparse.Namespace) -> Optional[str]:
    """Project directory to filter on, or None for all projects."""
    if args.all_projects:
        return None
    if args.project:
        return os.path.abspath(os.path.expanduser(args.project))
    return project_root()
