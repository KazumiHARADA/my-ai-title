#!/usr/bin/env python3
"""Generate synthetic Claude Code session logs for tests.

Everything here is made up. The line shapes mirror Claude Code 2.1.x logs
(type/uuid/parentUuid/timestamp/cwd/sessionId/message...). Run this script to
regenerate tests/fixtures/claude/ after changing it:

    python3 tests/fixtures/make_fixtures.py
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Sequence

HERE = Path(__file__).resolve().parent
OUT = HERE / "claude"
BASE = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


class Log:
    """Builds one transcript file line by line."""

    def __init__(self, session_id: str, cwd: str, start: datetime, branch: str = "main",
                 agent_id: Optional[str] = None):
        self.sid, self.cwd, self.t, self.branch, self.agent = session_id, cwd, start, branch, agent_id
        self.lines: List[str] = []
        self.n = 0
        self.parent: Optional[str] = None

    def _uuid(self) -> str:
        self.n += 1
        tag = (self.agent or "main")[:4]
        return f"{self.sid[:8]}-{tag}-{self.n:04d}-0000-000000000000"

    def tick(self, seconds: float = 20) -> "Log":
        self.t += timedelta(seconds=seconds)
        return self

    def _base(self, typ: str, **extra) -> dict:
        u = self._uuid()
        d = {"parentUuid": self.parent, "isSidechain": self.agent is not None, "type": typ,
             "uuid": u, "timestamp": iso(self.t), "userType": "external", "entrypoint": "cli",
             "cwd": self.cwd, "sessionId": self.sid, "version": "2.1.300", "gitBranch": self.branch}
        if self.agent:
            d["agentId"] = self.agent
        d.update(extra)
        self.parent = u
        return d

    def emit(self, d: dict) -> "Log":
        self.lines.append(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
        return self

    def raw(self, line: str) -> "Log":
        self.lines.append(line)
        return self

    # --- message helpers ---
    def prompt(self, text: str, source: str = "typed", **extra) -> "Log":
        self.tick(60)
        d = self._base("user", message={"role": "user", "content": text},
                       promptSource=source, origin={"kind": "human"}, **extra)
        return self.emit(d)

    def legacy_prompt(self, text: str) -> "Log":
        """Older log lines: no promptSource / origin fields."""
        self.tick(60)
        return self.emit(self._base("user", message={"role": "user", "content": text}))

    def user_raw(self, content, **extra) -> "Log":
        self.tick(5)
        return self.emit(self._base("user", message={"role": "user", "content": content}, **extra))

    def tool(self, name: str, **inp) -> "Log":
        self.tick(10)
        tid = f"toolu_{self.n:06d}"
        d = self._base("assistant", requestId="req_x", message={
            "id": f"msg_{self.n}", "type": "message", "role": "assistant", "model": "claude-x",
            "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}],
            "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1}})
        self.emit(d)
        self.tick(5)
        res = self._base("user", message={"role": "user", "content": [
            {"tool_use_id": tid, "type": "tool_result", "content": "ok", "is_error": False}]},
            toolUseResult={"stdout": "ok", "stderr": "", "interrupted": False},
            sourceToolAssistantUUID=d["uuid"])
        return self.emit(res)

    def say(self, text: str) -> "Log":
        self.tick(10)
        return self.emit(self._base("assistant", message={
            "id": f"msg_{self.n}", "type": "message", "role": "assistant", "model": "claude-x",
            "content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}))

    def think(self) -> "Log":
        self.tick(2)
        return self.emit(self._base("assistant", message={
            "role": "assistant", "content": [{"type": "thinking", "thinking": "(synthetic)", "signature": "x"}]}))

    def interrupt(self) -> "Log":
        return self.user_raw([{"type": "text", "text": "[Request interrupted by user]"}])

    def command(self, name: str) -> "Log":
        self.tick(30)
        return self.emit(self._base("user", message={"role": "user", "content":
            f"<command-message>{name}</command-message>\n<command-name>/{name}</command-name>"}))

    def system(self, subtype: str, **extra) -> "Log":
        self.tick(1)
        return self.emit(self._base("system", subtype=subtype, isMeta=False, **extra))

    def attachment(self, atype: str) -> "Log":
        self.tick(1)
        return self.emit(self._base("attachment", attachment={"type": atype}))

    def noise(self) -> "Log":
        """Lines that the reader must skip without crashing."""
        dump = lambda o: json.dumps(o, separators=(",", ":"))  # noqa: E731
        self.raw(dump({"type": "api-request", "sessionId": self.sid, "id": "r1",
                             "timestamp": iso(self.t), "params": {"system": "IGNORE ME"}}))
        self.raw(dump({"type": "ai-title", "aiTitle": "Secret Project Title", "sessionId": self.sid}))
        self.raw(dump({"type": "session-owner", "accountUuid": "acct-1", "sessionId": self.sid}))
        self.raw(dump({"type": "brand-new-type", "whatever": [1, 2, 3], "sessionId": self.sid}))
        self.raw('{"type": "user", "message": ')          # broken line
        self.raw("[1, 2, 3]")                              # valid JSON, not an object
        self.raw("")
        return self

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def projdir(cwd: str) -> Path:
    return OUT / "projects" / cwd.replace("/", "-")


def session_basic() -> None:
    """Japanese user; tests and a correction; commit ends the task; a later task after a gap."""
    cwd = "/Users/demo/Projects/acme-shop"
    sid = "11111111-1111-4111-8111-111111111111"
    lg = Log(sid, cwd, BASE, branch="feature/acme-checkout")
    lg.noise()
    lg.prompt("カート画面の合計金額がずれるので直して。完了条件はテストが通ること。")
    lg.think().tool("Read", file_path=f"{cwd}/src/cart.ts")
    lg.tool("Edit", file_path=f"{cwd}/src/cart.ts", old_string="a", new_string="b")
    lg.tool("Edit", file_path=f"{cwd}/src/total.ts", old_string="a", new_string="b")
    lg.tool("Bash", command="npm test")
    lg.say("修正しました。テストはすべて通っています。")
    lg.prompt("まだ表示がずれてる。直して")
    lg.tool("Edit", file_path=f"{cwd}/src/cart.ts", old_string="b", new_string="c")
    lg.tool("Bash", command="npx tsc --noEmit && npm run lint")
    lg.say("表示のずれを修正しました。型チェックとリントも通ります。")
    lg.prompt("コミットして", unknownFieldFromTheFuture={"x": 1})
    lg.tool("Bash", command="git add -A && git commit -m 'fix cart total'")
    lg.say("コミットしました。")
    lg.raw(json.dumps({"type": "pr-link", "sessionId": sid, "prNumber": 1,
                       "prUrl": "https://github.com/acme-inc/acme-shop/pull/1",
                       "prRepository": "acme-inc/acme-shop", "timestamp": iso(lg.t)}))
    lg.tick(3 * 3600)  # long gap -> new task
    lg.legacy_prompt("READMEのセットアップ手順を最新にして")
    lg.tool("Edit", file_path=f"{cwd}/README.md", old_string="a", new_string="b")
    lg.say("更新しました。")
    lg.system("turn_duration", durationMs=1000, messageCount=3)
    lg.system("away_summary", content="(synthetic away summary: must be ignored)")
    lg.write(projdir(cwd) / f"{sid}.jsonl")


def session_power() -> None:
    """English user in a worktree: sub-agents, a long run, an interrupt, skills, hooks, memo edits."""
    cwd = "/Users/demo/Projects/zeta-api/.claude/worktrees/feat-x"
    sid = "22222222-2222-4222-8222-222222222222"
    lg = Log(sid, cwd, BASE + timedelta(days=1), branch="feat-x")
    lg.prompt("Add rate limiting to the public endpoints. Plan first, then implement.")
    lg.tool("EnterPlanMode")
    lg.tool("ExitPlanMode")
    lg.tool("Agent", description="explore", prompt="find endpoints", subagent_type="Explore")
    lg.tool("Agent", description="tests", prompt="write tests", run_in_background=True)
    for i in range(12):
        lg.tool("Edit", file_path=f"{cwd}/app/endpoint_{i % 6}.rb", old_string="a", new_string="b")
    lg.tool("Bash", command="bundle exec rspec")
    lg.tool("mcp__playwright__browser_take_screenshot")
    lg.say("Rate limiting is in place for all public endpoints; specs pass and a screenshot confirms the 429 page.")
    lg.prompt("Now run the full migration on staging")
    for i in range(10):
        lg.tool("Bash", command=f"echo step {i}")
    lg.interrupt()
    lg.prompt("actually wait, also update the docs", source="queued")
    lg.tool("Edit", file_path=f"{cwd}/CLAUDE.md", old_string="a", new_string="b")
    lg.say("Docs and CLAUDE.md updated.")
    lg.prompt("Make a skill that checks deploy readiness")
    lg.tool("Write", file_path="/Users/demo/.claude/skills/deploy-check/SKILL.md", content="---\nname: deploy-check\n---")
    lg.say("Created the deploy-check skill.")
    lg.command("deploy-check")
    lg.tool("Skill", skill="deploy-check")
    lg.tool("Bash", command="rm -rf /tmp/x")
    lg.user_raw([{"type": "tool_result", "tool_use_id": "t", "content": "denied", "is_error": True}],
                toolDenialKind="user-rejected")
    lg.say("Deploy check finished.")
    lg.system("stop_hook_summary", hookCount=2, hookInfos=[], hookErrors=[], preventedContinuation=False)
    lg.attachment("hook_additional_context")
    lg.attachment("edited_text_file")
    lg.command("clear")
    lg.prompt("ok next thing: bump the version")
    lg.tool("Edit", file_path=f"{cwd}/VERSION", old_string="1", new_string="2")
    lg.say("Bumped.")
    lg.user_raw("<task-notification>agent finished</task-notification>", origin={"kind": "task-notification"})
    lg.user_raw("Caveat: meta", isMeta=True)
    lg.write(projdir(cwd) / f"{sid}.jsonl")

    sub = Log(sid, cwd, BASE + timedelta(days=1, minutes=3), branch="feat-x", agent_id="a1b2c3")
    sub.user_raw("find endpoints")
    sub.tool("Grep", pattern="def index")
    sub.tool("Bash", command="pytest -q")
    sub.say("Found 6 endpoints.")
    sub.write(projdir(cwd) / sid / "subagents" / "agent-a1b2c3.jsonl")


def session_secrets() -> None:
    """Prompts full of things that must be redacted."""
    cwd = "/Users/demo/Projects/globex-billing"
    sid = "33333333-3333-4333-8333-333333333333"
    lg = Log(sid, cwd, BASE + timedelta(days=2), branch="hotfix/globex-invoice")
    lg.prompt("Use key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789 and mail ops@globex.example.com. "
              "Config is in /Users/demo/Projects/globex-billing/config/secrets.yml, "
              "see https://wiki.globex.example.com/billing and db at db01.internal.globex.io. "
              "password: Tr0ub4dor&3 token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234 "
              "Initech asked about it in INV-2041.")
    lg.tool("Read", file_path=f"{cwd}/config/secrets.yml")
    lg.say("I checked /Users/demo/Projects/globex-billing/config/secrets.yml and globex-billing looks fine.\n"
           "```ruby\nAPI_KEY = 'sk-live-should-not-appear'\n```")
    lg.prompt("ありがとう。Globexの請求書のバグをglobex-billingで直して。担当は yamada@globex.example.com")
    lg.tool("Edit", file_path=f"{cwd}/app/invoice.rb", old_string="a", new_string="b")
    lg.say("Fixed.")
    lg.write(projdir(cwd) / f"{sid}.jsonl")


def session_old() -> None:
    """Outside the analysis window."""
    cwd = "/Users/demo/Projects/acme-shop"
    sid = "44444444-4444-4444-8444-444444444444"
    lg = Log(sid, cwd, BASE - timedelta(days=45))
    lg.prompt("old session")
    lg.tool("WebSearch", query="x")
    lg.say("done")
    lg.write(projdir(cwd) / f"{sid}.jsonl")


def skills_on_disk() -> None:
    p = OUT / "skills" / "deploy-check" / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nname: deploy-check\ndescription: synthetic\n---\n", encoding="utf-8")


# --- one scenario per type (tests/fixtures/types/<type>/) -----------------------
# Each scenario = synthetic logs + the scores Claude would plausibly give +
# the type/ability choose.py is expected to pick. Window: 2026-10-01 .. 10-31.

TYPES_OUT = HERE / "types"
TBASE = datetime(2026, 10, 2, 1, 0, tzinfo=timezone.utc)


def _sid(kind: int, i: int) -> str:
    return f"{kind:02d}{i:06d}-0000-4000-8000-000000000000"


def _write_scenario(name: str, logs: List[Log], scores: dict, expected: dict,
                    judgments: Optional[dict] = None, skills: Sequence[str] = ()) -> None:
    root = TYPES_OUT / name
    for lg in logs:
        lg.write(root / "projects" / lg.cwd.replace("/", "-") / f"{lg.sid}.jsonl")
    for sk in skills:
        p = root / "skills" / sk / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\nname: {sk}\n---\n", encoding="utf-8")
    doc = {"scores": scores, "judgments": judgments or {}}
    (root / "scores.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")


def _session(kind: int, i: int, cwd: str = "/Users/demo/Projects/app") -> Log:
    return Log(_sid(kind, i), cwd, TBASE + timedelta(days=i % 28, hours=i // 28))


def scenario_sniper() -> None:
    """Many tasks finished in one or two instructions, no rework."""
    logs = []
    for i in range(24):
        lg = _session(1, i)
        lg.prompt("ヘッダーの余白を詰めて。完了条件は既存テストが通ること。")
        lg.tool("Edit", file_path="/Users/demo/Projects/app/src/header.css", old_string="a", new_string="b")
        lg.tick(600).tool("Bash", command="npm test")
        lg.say("余白を詰めました。テストは通っています。")
        if i % 2:
            lg.prompt("ありがとう、コミットして")
            lg.tick(300).tool("Bash", command="git commit -am header")
            lg.say("コミットしました。")
        logs.append(lg)
    _write_scenario("sniper", logs,
                    {"context": 4, "delegation": 3, "verification": 4, "autonomy": 2, "efficiency": 5, "systems": 3},
                    {"type": "sniper", "ability_id": "bullseye", "rare": True, "quirk_id": "hover"})


def scenario_appraiser() -> None:
    """Has the AI check the screen again and again."""
    logs = []
    for i in range(6):
        lg = _session(2, i)
        lg.prompt("ログイン画面のボタン配置を直して、ブラウザで表示を確認して")
        lg.tool("Edit", file_path="/Users/demo/Projects/app/src/login.tsx", old_string="a", new_string="b")
        for _ in range(5):
            lg.tool("mcp__playwright__browser_take_screenshot")
        lg.say("配置を修正し、スクリーンショットで確認しました。")
        logs.append(lg)
    _write_scenario("appraiser", logs,
                    {"context": 3, "delegation": 3, "verification": 5, "autonomy": 3, "efficiency": 3, "systems": 2},
                    {"type": "appraiser", "ability_id": "farsight", "rare": False, "quirk_id": "handwritten"})


def scenario_alchemist() -> None:
    """Calls home-made skills every day."""
    logs = []
    for i in range(8):
        lg = _session(3, i)
        lg.command("release-notes")
        lg.tool("Skill", skill="release-notes")
        lg.say("リリースノートを作りました。")
        lg.prompt("次は週報も")
        lg.tool("Skill", skill="weekly-report")
        lg.say("週報を作りました。")
        logs.append(lg)
    _write_scenario("alchemist", logs,
                    {"context": 3, "delegation": 3, "verification": 2, "autonomy": 3, "efficiency": 4, "systems": 5},
                    {"type": "alchemist", "ability_id": "hundredtools", "rare": False, "quirk_id": "gullible"},
                    skills=["release-notes", "weekly-report"])


def scenario_commander() -> None:
    """Runs several sub-agents in parallel."""
    logs = []
    for i in range(5):
        lg = _session(4, i)
        lg.prompt("Split this refactor across agents: API, UI and docs. Run them in parallel.")
        for part in ("api", "ui", "docs", "tests", "review"):
            lg.tool("Agent", description=part, prompt=f"handle {part}", run_in_background=True)
        lg.say("All five agents finished their parts.")
        logs.append(lg)
    _write_scenario("commander", logs,
                    {"context": 3, "delegation": 5, "verification": 3, "autonomy": 4, "efficiency": 3, "systems": 2},
                    {"type": "commander", "ability_id": "clone", "rare": False, "quirk_id": "handwritten"})


def scenario_architect() -> None:
    """Keeps the project notes (CLAUDE.md) up to date."""
    logs = []
    for i in range(8):
        lg = _session(5, i)
        lg.prompt("今日決めた命名ルールをCLAUDE.mdに追記して")
        lg.tool("Edit", file_path="/Users/demo/Projects/app/CLAUDE.md", old_string="a", new_string="b")
        lg.say("追記しました。")
        logs.append(lg)
    _write_scenario("architect", logs,
                    {"context": 5, "delegation": 3, "verification": 3, "autonomy": 2, "efficiency": 4, "systems": 3},
                    {"type": "architect", "ability_id": "wisdom", "rare": False, "quirk_id": "hover"})


def scenario_partner() -> None:
    """Long back-and-forth conversations; no axis stands out."""
    logs = []
    for i in range(5):
        lg = _session(6, i)
        lg.prompt("新しい料金プランの案を一緒に考えたい")
        lg.tool("Read", file_path="/Users/demo/Projects/app/docs/pricing.md")
        lg.say("いくつか方向性があります。")
        topics = ["学生向け", "法人向け", "年払い", "無料枠", "競合比較", "解約率", "値上げ", "地域差",
                  "サポート", "上限設定", "紹介制度", "季節要因", "広告", "API利用", "請求書払い",
                  "ストレージ", "チーム機能", "移行期間", "告知方法", "返金", "まとめ"]
        for j, topic in enumerate(topics):
            lg.prompt(f"{topic}の観点{'も気になる' if j % 2 else 'だとどうなる？'}")
            lg.say("その観点だと、こう考えられます。")
        logs.append(lg)
    _write_scenario("partner", logs,
                    {"context": 3, "delegation": 3, "verification": 3, "autonomy": 3, "efficiency": 3, "systems": 3},
                    {"type": "partner", "ability_id": "endless", "rare": False, "quirk_id": "marathon"},
                    judgments={"partner_adopted": "yes"})


def scenario_explorer() -> None:
    """Early days: tries many different tools."""
    tools = ["Read", "Grep", "Glob", "WebSearch", "WebFetch", "Bash", "Edit", "Write",
             "mcp__notion__search", "mcp__figma__get_screenshot", "mcp__slack__post", "TodoWrite", "NotebookEdit"]
    logs = []
    for i in range(3):
        lg = _session(7, i)
        lg.prompt("これもAIでできるか試してみたい")
        for t in tools:
            lg.tool(t, file_path="/Users/demo/Projects/app/notes.txt") if t in ("Read", "Edit", "Write") else lg.tool(t)
        lg.say("試してみました。")
        logs.append(lg)
    _write_scenario("explorer", logs,
                    {"context": 2, "delegation": 3, "verification": 2, "autonomy": 2, "efficiency": 3, "systems": 2},
                    {"type": "explorer", "ability_id": "curious", "rare": False, "quirk_id": "gullible"})


def scenario_conductor() -> None:
    """Strong everywhere; parallel work with almost no rework."""
    logs = []
    for i in range(6):
        lg = _session(8, i, cwd=f"/Users/demo/Projects/app/.claude/worktrees/w{i}")
        lg.prompt("Implement the export feature end to end and verify it.")
        lg.tool("Agent", description="tests", prompt="write tests")
        lg.tool("Edit", file_path="/Users/demo/Projects/app/src/export.ts", old_string="a", new_string="b")
        lg.tool("Bash", command="npm test")
        lg.say("Export implemented; tests pass.")
        logs.append(lg)
    _write_scenario("conductor", logs,
                    {"context": 4, "delegation": 5, "verification": 4, "autonomy": 4, "efficiency": 5, "systems": 4},
                    {"type": "conductor", "ability_id": "legion", "rare": False, "quirk_id": "surplus"})


def main() -> None:
    for d in (OUT, TYPES_OUT):
        if d.exists():
            shutil.rmtree(d)
    session_basic()
    session_power()
    session_secrets()
    session_old()
    skills_on_disk()
    for f in (scenario_sniper, scenario_appraiser, scenario_alchemist, scenario_commander,
              scenario_architect, scenario_partner, scenario_explorer, scenario_conductor):
        f()
    print(f"wrote {OUT} and {TYPES_OUT}")


if __name__ == "__main__":
    main()
