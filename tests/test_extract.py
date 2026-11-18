import json
import os
import random
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from helpers import PROJECTS, ROOT, SCRIPTS  # noqa: F401  (sets sys.path)

import extract
from aititle import events as E
from aititle import evidence as V
from aititle.metrics import TASK_GAP, Turn, analyze, split_tasks
from aititle.sources import claude_code, codex
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

    def test_project_filter(self):
        res = claude_code.read_sessions(PROJECTS, SINCE, UNTIL, project="/Users/demo/Projects/zeta-api")
        self.assertEqual([s.id[:4] for s in res.sessions], ["2222"])     # worktree session included
        res = claude_code.read_sessions(PROJECTS, SINCE, UNTIL, project="/Users/demo/Projects/acme")
        self.assertEqual(res.sessions, [])                               # prefix must be a whole directory
        self.assertTrue(claude_code.under("/a/b/c", "/a/b"))
        self.assertFalse(claude_code.under("/a/bc", "/a/b"))
        m = extract.run(PROJECTS, SINCE, UNTIL, "/Users/demo/Projects/acme-shop")
        self.assertEqual(m["data"]["sessions"], 1)
        self.assertEqual(m["scope"], "project")
        self.assertNotIn("acme", json.dumps(m))

    def test_default_scope_is_current_project(self):
        import argparse
        from aititle import scope
        ap = argparse.ArgumentParser()
        scope.add_arguments(ap)
        here = scope.project_root()
        self.assertEqual(scope.resolve(ap.parse_args([])), here)
        self.assertIsNone(scope.resolve(ap.parse_args(["--all-projects"])))
        self.assertEqual(scope.resolve(ap.parse_args(["--project", "/tmp/x"])), "/tmp/x")
        with self.assertRaises(SystemExit):
            ap.parse_args(["--project", "/tmp/x", "--all-projects"])

    def test_project_root(self):
        from aititle import scope
        tmp = Path(tempfile.mkdtemp())
        try:
            self.assertEqual(scope.project_root(str(tmp)), str(tmp))   # not a git repo: cwd itself
            sub = ROOT / "skills" / "my-ai-title"
            self.assertEqual(os.path.realpath(scope.project_root(str(sub))), os.path.realpath(str(ROOT)))
            self.assertEqual(scope._WORKTREE_RE.sub("", "/p/app/.claude/worktrees/feat-x"), "/p/app")
        finally:
            shutil.rmtree(tmp)

    def test_diagnosis_runs_are_left_out(self):
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
        from make_fixtures import Log
        tmp = Path(tempfile.mkdtemp())
        try:
            cwd = "/Users/demo/Projects/app"
            work = Log("aaaaaaaa-0000-4000-8000-000000000001", cwd, SINCE + timedelta(days=1))
            work.prompt("fix the header spacing")
            work.tool("Edit", file_path=cwd + "/a.css", old_string="a", new_string="b")
            work.say("done")
            work.prompt("AI肩書き診断して")
            work.tool("Skill", skill="my-ai-title:my-ai-title")
            work.tool("Bash", command="python3 /x/plugins/cache/kharada/my-ai-title/0.4.0/skills/my-ai-title/scripts/extract.py --out m.json")
            work.say("card saved")
            only = Log("aaaaaaaa-0000-4000-8000-000000000002", cwd, SINCE + timedelta(days=2))
            only.command("my-ai-title:my-ai-title")
            only.tool("Bash", command="python3 /p/skills/my-ai-title/scripts/sample.py --metrics m.json")
            only.say("card saved")
            d = tmp / "projects" / "-Users-demo-Projects-app"
            work.write(d / (work.sid + ".jsonl"))
            only.write(d / (only.sid + ".jsonl"))
            res = claude_code.read_sessions(tmp / "projects", SINCE, UNTIL)
            self.assertEqual([s.id[-1] for s in res.sessions], ["1"])          # diagnosis-only session dropped
            prompts = [e.text for e in res.sessions[0].events if e.kind == E.PROMPT]
            self.assertEqual(prompts, ["fix the header spacing"])             # work before the request kept
            self.assertFalse(any(e.tool == "Skill" for e in res.sessions[0].events))
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


class TestCodexReader(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        d = self.tmp / "sessions" / "2026" / "10" / "01"
        d.mkdir(parents=True)
        cwd = "/Users/demo/Projects/acme-shop"
        rows = [
            {"timestamp": "2026-10-01T00:00:00Z", "type": "session_meta", "payload": {
                "id": "codex-main", "cwd": cwd, "cli_version": "1.2.3", "source": "vscode",
                "runtime_workspace_roots": [cwd],
                "git": {"branch": "feature/checkout", "repository_url": "https://example.invalid/acme/shop.git"}}},
            {"timestamp": "2026-10-01T00:00:01Z", "type": "event_msg", "payload": {
                "type": "item_completed", "item": {"type": "UserMessage", "id": "u1",
                "content": [{"type": "text", "text": "Implement checkout and verify it"}]}}},
            {"timestamp": "2026-10-01T00:00:02Z", "type": "response_item", "payload": {
                "type": "custom_tool_call", "id": "raw1", "name": "exec", "input": "{\"cmd\":\"duplicate\"}"}},
            {"timestamp": "2026-10-01T00:00:03Z", "type": "event_msg", "payload": {
                "type": "item_completed", "item": {"type": "CommandExecution", "id": "c1",
                "command": "python3 -m pytest -q", "cwd": cwd}}},
            {"timestamp": "2026-10-01T00:00:04Z", "type": "event_msg", "payload": {
                "type": "item_completed", "item": {"type": "FileChange", "id": "f1",
                "changes": {cwd + "/src/cart.py": {"type": "update", "unified_diff": "secret"}}}}},
            {"timestamp": "2026-10-01T00:00:05Z", "type": "event_msg", "payload": {
                "type": "item_completed", "item": {"type": "SubAgentActivity", "id": "a1",
                "kind": "started", "agent_path": "tests"}}},
            {"timestamp": "2026-10-01T00:00:06Z", "type": "event_msg", "payload": {
                "type": "item_completed", "item": {"type": "AgentMessage", "id": "m1",
                "content": [{"type": "Text", "text": "Implemented and verified."}]}}},
            {"timestamp": "2026-10-01T00:00:07Z", "type": "event_msg", "payload": {
                "type": "item_completed", "item": {"type": "UserMessage", "id": "u2",
                "content": [{"type": "text", "text": "Use $my-ai-title now"}]}}},
            {"timestamp": "2026-10-01T00:00:08Z", "type": "event_msg", "payload": {
                "type": "item_completed", "item": {"type": "CommandExecution", "id": "c2",
                "command": "python3 /x/skills/my-ai-title/scripts/extract.py --source codex", "cwd": cwd}}},
        ]
        (d / "rollout-main.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
        sub = [
            {"timestamp": "2026-10-01T00:00:00Z", "type": "session_meta", "payload": {
                "id": "codex-sub", "cwd": cwd, "source": {"subagent": "tests"}, "parent_thread_id": "codex-main"}},
            {"timestamp": "2026-10-01T00:00:02Z", "type": "event_msg", "payload": {
                "type": "item_completed", "item": {"type": "UserMessage", "id": "su1",
                "content": [{"type": "text", "text": "parent agent instruction"}]}}},
        ]
        (d / "rollout-sub.jsonl").write_text("\n".join(json.dumps(x) for x in sub) + "\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_completed_items_are_normalized_without_raw_duplicates(self):
        read = codex.read_sessions(self.tmp, SINCE, UNTIL)
        self.assertEqual(len(read.sessions), 1)
        session = read.sessions[0]
        prompts = [e.text for e in session.events if e.kind == E.PROMPT]
        self.assertEqual(prompts, ["Implement checkout and verify it"])
        tools = [e.tool for e in session.events if e.kind == E.TOOL_CALL]
        self.assertEqual(tools, ["Bash", "Write", "Agent"])
        self.assertNotIn("duplicate", [e.target for e in session.events])
        self.assertEqual(session.versions, {"1.2.3"})
        self.assertTrue({"acme-shop", "checkout", "demo"} <= {x.lower() for x in session.sensitive_terms})

    def test_codex_metrics_and_project_filter(self):
        metrics = extract.run(self.tmp, SINCE, UNTIL, "/Users/demo/Projects/acme-shop", "codex")
        self.assertEqual(metrics["source"], "codex")
        self.assertEqual(metrics["scope"], "project")
        self.assertEqual(metrics["data"]["sessions"], 1)
        self.assertEqual(metrics["verification"]["test_runs"], 1)
        self.assertEqual(metrics["parallel"]["subagent_calls"], 1)
        self.assertNotIn("acme", json.dumps(metrics).lower())

    def test_legacy_response_items_fallback(self):
        d = self.tmp / "archived_sessions"
        d.mkdir()
        rows = [
            {"timestamp": "2026-10-02T00:00:00Z", "type": "session_meta", "payload": {
                "id": "legacy", "cwd": "/Users/demo/Projects/legacy", "source": "vscode"}},
            {"timestamp": "2026-10-02T00:00:01Z", "type": "response_item", "payload": {
                "type": "message", "id": "u", "role": "user",
                "content": [{"type": "input_text", "text": "Build it"}]}},
            {"timestamp": "2026-10-02T00:00:02Z", "type": "response_item", "payload": {
                "type": "custom_tool_call", "id": "t", "name": "exec",
                "input": "{\"cmd\":\"npm run build\"}"}},
            {"timestamp": "2026-10-02T00:00:03Z", "type": "response_item", "payload": {
                "type": "message", "id": "a", "role": "assistant",
                "content": [{"type": "output_text", "text": "Built."}]}},
        ]
        (d / "rollout-legacy.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
        read = codex.read_sessions(self.tmp, SINCE, UNTIL, project="/Users/demo/Projects/legacy")
        self.assertEqual(len(read.sessions), 1)
        stats = analyze(read.sessions)[0]
        self.assertEqual(stats.turns[0].text, "Build it")
        self.assertEqual(stats.turns[0].behaviors[V.V_BUILD], 1)


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
                               "--all-projects", "--out", str(out)])
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
