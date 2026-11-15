import json
import os
import random
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from helpers import PROJECTS, SCRIPTS  # noqa: F401  (sets sys.path)

import extract
from aititle import events as E
from aititle import evidence as V
from aititle.metrics import TASK_GAP, Turn, analyze, split_tasks
from aititle.sources import claude_code
from aititle.textutil import dominant_language, similar_clusters, size_units

SINCE = datetime(2026, 9, 25, tzinfo=timezone.utc)
UNTIL = datetime(2026, 10, 10, tzinfo=timezone.utc)


def fixture_metrics():
    return extract.run(PROJECTS, SINCE, UNTIL)


class TestReader(unittest.TestCase):
    def setUp(self):
        self.read = claude_code.read_sessions(PROJECTS, SINCE, UNTIL)
        self.by_id = {s.id[:4]: s for s in self.read.sessions}

    def test_window_excludes_old_session(self):
        self.assertEqual(sorted(self.by_id), ["1111", "2222", "3333"])

    def test_broken_and_non_object_lines_are_counted_not_fatal(self):
        self.assertEqual(self.read.unparseable_lines, 2)

    def test_non_prompts_are_not_prompts(self):
        prompts = [e.text for s in self.read.sessions for e in s.events if e.kind == E.PROMPT]
        joined = "\n".join(prompts)
        for bad in ("task-notification", "Caveat: meta", "Request interrupted", "command-name",
                    "find endpoints", "IGNORE ME", "away summary"):
            self.assertNotIn(bad, joined)
        self.assertTrue(all(e.agent is None for s in self.read.sessions for e in s.events if e.kind == E.PROMPT))

    def test_legacy_lines_without_origin_fields_still_count(self):
        texts = [e.text for e in self.by_id["1111"].events if e.kind == E.PROMPT]
        self.assertIn("READMEのセットアップ手順を最新にして", texts)

    def test_session_flags(self):
        power = self.by_id["2222"]
        self.assertTrue(power.in_worktree)
        self.assertEqual(power.subagent_logs, 1)
        self.assertTrue(any(e.agent == "agent-a1b2c3" for e in power.events))
        # worktree and main checkout map to the same project key
        self.assertEqual(power.project, claude_code.project_key("/Users/demo/Projects/zeta-api"))

    def test_sensitive_terms_collected(self):
        terms = {t.lower() for t in self.by_id["1111"].sensitive_terms}
        self.assertTrue({"acme-shop", "acme", "demo", "checkout"} <= terms)
        self.assertNotIn("users", terms)

    def test_garbage_never_crashes(self):
        rnd = random.Random(0)
        tmp = Path(tempfile.mkdtemp())
        try:
            d = tmp / "p"
            d.mkdir()
            lines = []
            samples = [None, 1, "x", [], {}, {"type": 3}, {"type": "user"}, {"type": "user", "message": "s"},
                       {"type": "user", "message": {"content": 5}}, {"type": "assistant", "message": {"content": [1, None, {}]}},
                       {"type": "user", "timestamp": "not-a-date", "message": {"content": "hi"}},
                       {"type": "user", "timestamp": "2026-10-01T00:00:00Z", "message": {"content": [{"type": "text", "text": None}]}},
                       {"type": "assistant", "timestamp": "2026-10-01T00:00:00.1Z",
                        "message": {"content": [{"type": "tool_use", "name": None, "input": "str"}]}},
                       {"type": "system", "timestamp": "2026-10-01T00:00:00Z", "subtype": "stop_hook_summary", "hookCount": "x"}]
            for _ in range(300):
                obj = rnd.choice(samples)
                lines.append(json.dumps(obj) if rnd.random() < 0.8 else json.dumps(obj)[: rnd.randint(0, 20)])
            (d / "s.jsonl").write_text("\n".join(lines), encoding="utf-8")
            res = claude_code.read_sessions(tmp, SINCE, UNTIL)
            analyze(res.sessions)
        finally:
            shutil.rmtree(tmp)

    def test_parse_ts_variants(self):
        for s in ("2026-10-01T00:00:00Z", "2026-10-01T00:00:00.1Z", "2026-10-01T00:00:00.123456789Z",
                  "2026-10-01T09:00:00+09:00", "2026-10-01T00:00:00"):
            self.assertEqual(claude_code.parse_ts(s).date().isoformat(), "2026-10-01")
        self.assertIsNone(claude_code.parse_ts("yesterday"))
        self.assertIsNone(claude_code.parse_ts(None))

    def test_history_scan_uses_file_mtime(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(PROJECTS, tmp / "projects")
            old = next((tmp / "projects").glob("*/4444*.jsonl"))
            t = (SINCE - timedelta(days=40)).timestamp()
            os.utime(old, (t, t))
            res = claude_code.read_sessions(tmp / "projects", SINCE, UNTIL, history_since=SINCE - timedelta(days=60))
            self.assertIn("WebSearch", res.tools_before_window)
            self.assertEqual(len(res.sessions), 3)
        finally:
            shutil.rmtree(tmp)


class TestMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = fixture_metrics()

    def test_counts(self):
        m = self.m
        self.assertEqual(m["data"]["sessions"], 3)
        self.assertEqual(m["data"]["tasks"], 5)
        self.assertEqual(m["data"]["human_prompts"], 11)
        self.assertEqual(m["data"]["unparseable_lines"], 2)

    def test_verification(self):
        v = self.m["verification"]
        self.assertEqual(v["test_runs"], 3)       # npm test, rspec, pytest (sub-agent)
        self.assertEqual(v["typecheck_runs"], 1)
        self.assertEqual(v["lint_runs"], 1)
        self.assertEqual(v["visual_checks"], 1)
        self.assertEqual(v["methods_used"], 4)
        self.assertEqual(v["followup_fix_prompts_est"], 1)

    def test_autonomy_and_parallel(self):
        a, p = self.m["autonomy"], self.m["parallel"]
        self.assertEqual(a["long_runs"], 2)
        self.assertEqual(a["long_runs_interrupted"], 1)
        self.assertEqual(a["interrupts"], 1)
        self.assertEqual(a["mid_run_messages"], 1)
        self.assertEqual(a["user_denials"], 1)
        self.assertEqual(p["subagent_calls"], 2)
        self.assertEqual(p["worktree_sessions"], 1)
        self.assertEqual(p["background_tasks"], 1)

    def test_systems_and_context(self):
        s, c = self.m["systems"], self.m["context"]
        self.assertEqual(s["hook_runs"], 3)
        self.assertEqual(s["mechanisms_created"], 1)
        self.assertEqual(s["mechanisms_created_used"], 1)
        self.assertEqual(s["own_mechanism_calls"], 2)
        self.assertEqual(c["memo_updates"], 1)
        self.assertEqual(c["plan_tool_calls"], 2)
        self.assertEqual(self.m["delegation"]["human_edits"], 1)

    def test_no_text_leaks_into_metrics(self):
        blob = json.dumps(self.m, ensure_ascii=False).lower()
        for bad in ("acme", "globex", "zeta", "demo", "/users", "deploy-check", "sk-ant", "カート", "readme"):
            self.assertNotIn(bad, blob)

    def test_deterministic(self):
        self.assertEqual(json.dumps(self.m, sort_keys=True), json.dumps(fixture_metrics(), sort_keys=True))

    def test_cli_writes_file(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "metrics.json"
            rc = extract.main(["--logs-dir", str(PROJECTS), "--since", "2026-09-25", "--until", "2026-10-10",
                               "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out.read_text())["data"]["sessions"], 3)
        finally:
            shutil.rmtree(tmp)

    def test_empty_logs_dir(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            m = extract.run(tmp / "missing", SINCE, UNTIL)
            self.assertEqual(m["data"]["sessions"], 0)
            self.assertIsNone(m["intervention"]["prompts_per_task_mean"])
        finally:
            shutil.rmtree(tmp)


class TestHelpers(unittest.TestCase):
    def test_bash_classification(self):
        cases = {
            "npm test": {V.V_TEST}, "pnpm run test -- --watch=false": {V.V_TEST},
            "bundle exec rspec spec/a_spec.rb": {V.V_TEST}, "python3 -m pytest -q": {V.V_TEST},
            "cd web && npx tsc --noEmit": {V.V_TYPECHECK}, "yarn lint": {V.V_LINT},
            "npm run build": {V.V_BUILD}, "git worktree add ../x": {V.PARALLEL},
            "git commit -m x": {V.TASK_END}, "gh pr create --fill": {V.TASK_END},
            "ls -la": set(), "echo contest": set(), "cat makefile": set(),
        }
        for cmd, want in cases.items():
            self.assertEqual(V.bash_behaviors(cmd), want, cmd)

    def test_files(self):
        self.assertEqual(V.mechanism_name("/h/.claude/skills/deploy-check/SKILL.md"), "deploy-check")
        self.assertEqual(V.mechanism_name("/p/.claude/commands/ship.md"), "ship")
        self.assertIsNone(V.mechanism_name("/p/docs/skills.md"))
        self.assertTrue(V.is_memo_file("/p/CLAUDE.md"))
        self.assertTrue(V.is_memo_file("/p/sub/AGENTS.md"))
        self.assertTrue(V.is_memo_file("/p/.claude/rules/style.md"))
        self.assertFalse(V.is_memo_file("/p/README.md"))

    def test_tool_behaviors(self):
        self.assertIn(V.V_VISUAL, V.tool_behaviors("mcp__chrome__take_screenshot"))
        self.assertIn(V.V_VISUAL, V.tool_behaviors("Read", "/x/shot.PNG"))
        self.assertIn(V.V_REVIEW, V.tool_behaviors("Skill", "code-review"))
        self.assertIn(V.PARALLEL, V.tool_behaviors("Agent"))

    def test_language(self):
        self.assertEqual(dominant_language(["これを直して", "fix it", "テスト"])["dominant"], "ja")
        self.assertEqual(dominant_language([])["dominant"], "en")

    def test_size_units(self):
        self.assertEqual(size_units("fix the bug"), 3)
        self.assertEqual(size_units("直して"), 1.5)
        self.assertEqual(size_units("look ```\nlots of code here\n```"), 1)

    def test_similar_clusters(self):
        texts = ["PRのレビューコメントに全部対応して、終わったらpushして",
                 "PRのレビューコメントに全部対応して、終わったらプッシュして",
                 "全然関係のない依頼です。READMEを英訳して",
                 "PRのレビューコメントに全て対応して、終わったらpushしてね"]
        clusters = similar_clusters(texts)
        self.assertEqual(clusters, [[0, 1, 3]])

    def test_task_split_by_gap(self):
        t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
        a = Turn(start=t0, end=t0 + timedelta(minutes=5), text="a", tool_calls=1)
        b = Turn(start=a.end + TASK_GAP - timedelta(seconds=1), end=a.end + TASK_GAP, text="still wrong")
        c = Turn(start=b.end + TASK_GAP, end=b.end + TASK_GAP, text="c")
        tasks = split_tasks([a, b, c])
        self.assertEqual([len(k.turns) for k in tasks], [2, 1])
        self.assertTrue(b.followup_fix)


if __name__ == "__main__":
    unittest.main()
