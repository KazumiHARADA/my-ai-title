"""Shared test helpers: put the skill's scripts/ on sys.path."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "my-ai-title" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures" / "claude"
PROJECTS = FIXTURES / "projects"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
