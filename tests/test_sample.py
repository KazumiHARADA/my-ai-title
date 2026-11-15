import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from helpers import PROJECTS  # noqa: F401  (sets sys.path)

import extract
import sample
from aititle.metrics import analyze
from aititle.redact import redact
from aititle.sources import claude_code

SINCE = datetime(2026, 9, 25, tzinfo=timezone.utc)
UNTIL = datetime(2026, 10, 10, tzinfo=timezone.utc)

# Strings in the fixtures that must never reach Claude.
MUST_NOT_APPEAR = [
    "sk-ant", "AbCdEfGh", "ghp_", "Tr0ub4dor", "sk-live", "ops@", "yamada", "globex", "Globex",
    "Initech", "INV-2041", "/Users", "secrets.yml", "wiki.", "db01", "internal", "acme", "zeta",
    "demo", "cart.ts", "IGNORE ME", "Secret Project Title", "deploy-check", "API_KEY", "endpoint_",
    "feat-x", "rm -rf", "npm test", "rspec",
]


class TestRedact(unittest.TestCase):
    def check(self, text, gone, kept=(), terms=()):
        out = redact(text, terms)
        for g in gone:
            self.assertNotIn(g, out, f"{g!r} leaked in {out!r}")
        for k in kept:
            self.assertIn(k, out, f"{k!r} missing in {out!r}")
        return out

    def test_secrets(self):
        self.check("key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWx and ghp_ABCDEFGHIJKLMNOPQRSTUV1234",
                   ["sk-ant", "ghp_", "AbCdEf"], ["[SECRET]"])
        self.check("AKIAIOSFODNN7EXAMPLE xoxb-123456789012-abcdefghij", ["AKIA", "xoxb"])
        self.check("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
                   ["eyJ", "dozjg"])
        self.check("-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", ["MIIEow"])
        self.check("password: hunter2pass, パスワード：ひみつのあいことば123", ["hunter2", "ひみつ"])
        self.check("hash 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", ["9f86d0"])

    def test_contact_and_locations(self):
        self.check("mail a.b+c@example.co.jp now", ["example", "a.b"], ["[EMAIL]"])
        self.check("see https://foo.example.com/a?b=c and www.example.org", ["foo.", "example"], ["[URL]"])
        self.check("edit /Users/taro/work/app/main.go and ~/notes/todo.txt", ["taro", "main.go", "notes"], ["[PATH]"])
        self.check("C:\\Users\\taro\\proj\\a.cs", ["taro"], ["[PATH]"])
        self.check("change src/components/Button.tsx and utils.py", ["Button", "utils"], ["[PATH]"])
        self.check("ssh to 10.0.0.12:22 or api.internal.example.io", ["10.0", "internal"], ["[HOST]"])

    def test_names_and_identifiers(self):
        self.check("Ask Initech about the FooBarService in PROJ-123 and #45, ping @alice",
                   ["Initech", "FooBar", "PROJ", "#45", "alice"], ["Ask", "about the"])
        self.check("HogetechのSlack連携とfoobarが壊れた", ["Hogetech", "Slack", "foobar"], ["連携", "壊れた"])
        self.check("work on secret-repo for taro", ["secret-repo", "taro"], terms={"secret-repo", "taro"})
        self.check("株式会社ほげの件", ["ほげ"], terms={"株式会社ほげ"})
        self.check("order 1234567 shipped", ["1234567"], ["[NUM]"])
        # everyday words collected from branch names are not masked
        self.check("run the test again", [], ["run the test again"], terms={"test", "acme"})

    def test_japanese_proper_nouns(self):
        self.check("大和田製薬のフローを確認して", ["大和田"], ["のフローを確認して"])
        self.check("株式会社フガの件", ["フガ"], ["の件"])
        self.check("Zed さんの基準で見て", ["Zed"], ["さんの基準で見て"])
        self.check("田中さんに確認して、お客様と担当者様にも連絡", ["田中"], ["さんに確認", "お客様", "担当者様"])
        self.check("ホゲモア受注の復唱ナシ版", ["ホゲモア"], ["受注", "ナシ"])
        self.check("東京都目黒区三田の番地", ["目黒", "三田"], ["の番地"])
        self.check("続いて、北海道函館市 末広町の住所", ["函館", "末広"], ["の住所"])
        self.check("続いて、北海道函館市 **末広町**の住所", ["函館", "末広"], ["の住所"])
        self.check("トウキョウトメグロクミタ の番地", ["トウキョウ"], ["の番地"])
        self.check("コールフローとダイヤルパッドのテスト", [], ["コールフローとダイヤルパッドのテスト"])

    def test_code_is_omitted(self):
        out = self.check("look:\n```python\nAPI_KEY='x'\nprint(1)\n```\nand `rm -rf /` please",
                         ["API_KEY", "print", "rm -rf"], ["[CODE]", "please"])
        self.assertNotIn("[CODE] [CODE]", out)

    def test_pasted_logs_are_omitted(self):
        out = self.check("it failed:\nTraceback (most recent call last):\n  File \"/x/y.py\", line 3\nValueError: bad\nhelp",
                         ["Traceback", "ValueError"], ["help"])
        self.assertIn("[LOG]", out)

    def test_plain_text_is_kept(self):
        self.assertEqual(redact("Please fix the login bug and run the tests."),
                         "Please fix the login bug and run the tests.")
        self.assertEqual(redact("カート画面の合計がずれるので直して"), "カート画面の合計がずれるので直して")

    def test_placeholders_are_not_double_wrapped(self):
        out = redact("Initech at https://x.example.com with sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWx")
        self.assertNotIn("[[", out)
        self.assertNotIn("]]", out)

    def test_limit(self):
        self.assertTrue(redact("word " * 500, limit=50).endswith("…"))


class TestSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read = claude_code.read_sessions(PROJECTS, SINCE, UNTIL)
        cls.data = sample.build(analyze(read.sessions))
        cls.blob = json.dumps(cls.data, ensure_ascii=False)

    def test_nothing_sensitive_leaks(self):
        for bad in MUST_NOT_APPEAR:
            self.assertNotIn(bad, self.blob, bad)

    def test_shape(self):
        sessions = self.data["sessions"]
        self.assertTrue(1 <= len(sessions) <= sample.MAX_SESSIONS)
        labels = [s["why_selected"] for s in sessions]
        self.assertEqual(len(labels), len(set(labels)))
        for s in sessions:
            for t in s["turns"]:
                if "n" in t:
                    self.assertTrue({"human", "ai_actions", "ai_report"} <= set(t))

    def test_flags_present(self):
        turns = [t for s in self.data["sessions"] for t in s["turns"]]
        for flag in ("interrupted_by_human", "sent_while_ai_was_working", "possible_correction"):
            self.assertTrue(any(t.get(flag) for t in turns), flag)

    def test_pick_turns_caps_long_sessions(self):
        from aititle.metrics import Turn
        t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
        turns = [Turn(start=t0, end=t0, text=str(i)) for i in range(40)]
        turns[20].followup_fix = True
        idx = sample.pick_turns(turns)
        self.assertEqual(len(idx), sample.MAX_TURNS)
        self.assertIn(20, idx)
        self.assertEqual(idx[:3], [0, 1, 2])
        self.assertEqual(idx[-3:], [37, 38, 39])

    def test_cli(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            extract.main(["--logs-dir", str(PROJECTS), "--since", "2026-09-25", "--until", "2026-10-10",
                          "--out", str(tmp / "m.json")])
            rc = sample.main(["--metrics", str(tmp / "m.json"), "--logs-dir", str(PROJECTS),
                              "--out", str(tmp / "s.json")])
            self.assertEqual(rc, 0)
            text = (tmp / "s.json").read_text(encoding="utf-8")
            for bad in MUST_NOT_APPEAR:
                self.assertNotIn(bad, text, bad)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
