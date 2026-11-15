import copy
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from helpers import ROOT, SCRIPTS  # noqa: F401  (sets sys.path)

import choose
import extract
from aititle import typesdb
from aititle.selection import ABILITY_RULES, QUIRK_RULES, Ctx, choose_type, is_rare, select

TYPES_DIR = ROOT / "tests" / "fixtures" / "types"
DB = typesdb.load()

NEUTRAL = {
    "period": {"days": 30},
    "data": {"sessions": 30, "active_day_share": 0.3},
    "intervention": {"prompts_per_task_median": 3, "tasks_within_2_prompts_share": 0.2,
                     "tasks_within_2_prompts_no_rework": 0, "turns_per_session_median": 8,
                     "short_prompt_share": 0.3, "task_minutes_median": 40, "max_clean_task_streak": 0},
    "delegation": {"files_changed_per_prompt_mean": 0.5, "short_and_wide_turn_share": 0.0,
                   "tool_calls_per_prompt_median": 5, "human_edits": 0},
    "verification": {"test_runs": 0, "visual_checks": 0, "methods_used": 1, "verify_request_share": 0.0,
                     "verified_task_share": 0.8, "followup_fix_task_share_est": 0.05, "followup_fix_prompts_est": 1},
    "parallel": {"subagent_calls": 0, "worktree_sessions": 0, "sessions_with_parallel_share": 0.0},
    "autonomy": {"long_runs_completed": 0, "mid_run_messages": 0, "interrupts": 0},
    "systems": {"own_mechanism_calls": 0, "hook_runs": 0, "automation_tool_calls": 0, "mechanisms_created_used": 0,
                "patterns_gone_after_mechanism": 0, "repeated_prompts": 0, "repeated_long_prompts": 0,
                "own_mechanisms_unused": 0},
    "context": {"plan_task_share": 0.0, "memo_updates": 0},
    "breadth": {"distinct_tools": 5, "new_tools_this_period": 0},
}


def metrics(**overrides):
    m = copy.deepcopy(NEUTRAL)
    for key, value in overrides.items():
        section, name = key.split("__")
        m[section][name] = value
    return m


def S(c=3, d=3, v=3, a=3, e=3, s=3):
    return {"context": c, "delegation": d, "verification": v, "autonomy": a, "efficiency": e, "systems": s}


def ctx(scores, m=None, judgments=None, growth=None):
    return Ctx(metrics=m or metrics(), scores=scores, judgments=judgments or {}, growth=growth)


class TestTypeScenarios(unittest.TestCase):
    """One synthetic log set per type -> expected type and ability."""

    def test_all_types_covered(self):
        self.assertEqual(sorted(p.name for p in TYPES_DIR.iterdir() if p.is_dir()), sorted(typesdb.TYPES))

    def test_scenarios(self):
        since = datetime(2026, 10, 1, tzinfo=timezone.utc)
        until = datetime(2026, 10, 31, tzinfo=timezone.utc)
        for d in sorted(p for p in TYPES_DIR.iterdir() if p.is_dir()):
            with self.subTest(type=d.name):
                m = extract.run(d / "projects", since, until)
                doc = json.loads((d / "scores.json").read_text(encoding="utf-8"))
                want = json.loads((d / "expected.json").read_text())
                card = choose.run(doc, m, "ja", None)
                got = {"type": card["type"], "ability_id": card["ability_id"], "rare": card["rare"],
                       "quirk_id": card["quirk"]["id"]}
                self.assertEqual(got, want)


class TestTypeRules(unittest.TestCase):
    def test_all_four_or_more_is_conductor(self):
        self.assertEqual(choose_type(DB, ctx(S(4, 4, 4, 4, 4, 4))), "conductor")
        self.assertNotEqual(choose_type(DB, ctx(S(4, 4, 4, 4, 4, 3))), "conductor")

    def test_average_below_three_is_explorer(self):
        self.assertEqual(choose_type(DB, ctx(S(3, 3, 3, 3, 3, 2))), "explorer")      # 2.83
        self.assertNotEqual(choose_type(DB, ctx(S(3, 3, 3, 3, 4, 2))), "explorer")   # 3.0

    def test_top_axis(self):
        self.assertEqual(choose_type(DB, ctx(S(v=5))), "appraiser")
        self.assertEqual(choose_type(DB, ctx(S(c=5))), "architect")
        self.assertEqual(choose_type(DB, ctx(S(s=5))), "alchemist")
        self.assertEqual(choose_type(DB, ctx(S(e=5))), "sniper")

    def test_commander_with_either_axis_on_top(self):
        self.assertEqual(choose_type(DB, ctx(S(d=5, a=4))), "commander")
        self.assertEqual(choose_type(DB, ctx(S(d=5, a=2, c=4))), "commander")
        self.assertEqual(choose_type(DB, ctx(S(a=5, d=2, c=4))), "commander")

    def test_tie_goes_to_stronger_ability(self):
        tie = S(c=5, v=5)
        strong_memo = metrics(context__memo_updates=12)          # sage x3
        strong_tests = metrics(verification__test_runs=90)       # ironwall x3 > ...
        self.assertEqual(choose_type(DB, ctx(tie, strong_memo)), "architect")
        self.assertEqual(choose_type(DB, ctx(tie, strong_tests)), "appraiser")

    def test_tie_with_no_signal_uses_fixed_order(self):
        self.assertEqual(choose_type(DB, ctx(S(c=5, v=5))), "appraiser")
        self.assertEqual(choose_type(DB, ctx(S(e=5, d=5))), "sniper")

    def test_partner(self):
        chatty = metrics(intervention__prompts_per_task_median=8)
        adopted = {"partner_adopted": "yes"}
        self.assertEqual(choose_type(DB, ctx(S(), chatty, adopted)), "partner")                     # top 3
        self.assertEqual(choose_type(DB, ctx(S(c=4, d=4, v=4), chatty, adopted)), "partner")        # 3-way tie
        self.assertEqual(choose_type(DB, ctx(S(v=4), chatty, adopted)), "appraiser")                # clear top
        self.assertEqual(choose_type(DB, ctx(S(), chatty)), "appraiser")                            # not adopted
        self.assertEqual(choose_type(DB, ctx(S(), metrics(), adopted)), "appraiser")                # not chatty


class TestAbilityAndQuirk(unittest.TestCase):
    def test_every_ability_and_quirk_has_a_rule(self):
        ids = {a.id for t in DB.types.values() for a in t.abilities}
        self.assertEqual(ids, set(ABILITY_RULES))
        self.assertEqual({q.id for q in DB.quirks}, set(QUIRK_RULES))
        self.assertEqual(len(ids), 32)

    def test_image_files_use_known_ids(self):
        ids = {f"{a.type}_{a.id}" for t in DB.types.values() for a in t.abilities}
        for p in (ROOT / "skills" / "my-ai-title" / "assets" / "characters").glob("*.png"):
            self.assertIn(p.stem.replace("_rare", ""), ids, p.name)

    def test_no_condition_met_uses_first_ability(self):
        sel = select(DB, ctx(S(e=5)))
        self.assertEqual(sel.ability.id, "bullseye")

    def test_strongest_condition_wins(self):
        m = metrics(intervention__short_prompt_share=0.9, intervention__tasks_within_2_prompts_share=0.6)
        self.assertEqual(select(DB, ctx(S(e=5), m)).ability.id, "silence")    # 1.29 > 1.2
        self.assertEqual(select(DB, ctx(S(e=5), m, {"precision": "strong"})).ability.id, "precision")

    def test_quirk_skips_deciding_axis(self):
        sel = select(DB, ctx(S(e=5, a=2, c=2), metrics(autonomy__interrupts=30)))
        self.assertEqual(sel.quirk.id, "stopper")
        # the deciding axis is never the quirk axis, even if lowest-looking rules fire
        sel = select(DB, ctx(S(c=5, d=4, v=4, a=4, e=4, s=3)))
        self.assertEqual(sel.quirk.axis, "systems")

    def test_quirk_tie_goes_to_stronger_pattern(self):
        m = metrics(delegation__human_edits=60)
        sel = select(DB, ctx(S(v=5, d=2, s=2), m))
        self.assertEqual(sel.quirk.id, "hoarder")

    def test_quirk_without_signal_uses_first_pattern(self):
        sel = select(DB, ctx(S(v=5, a=2)))
        self.assertEqual(sel.quirk.id, "hover")

    def test_surplus_quirk_when_all_four_or_more(self):
        card = choose.run({"scores": S(4, 4, 4, 4, 4, 4)}, metrics(), "ja", None)
        self.assertEqual(card["quirk"]["id"], "surplus")
        self.assertEqual(card["quirk"]["name"], DB.types["conductor"].surplus_quirk["ja"])


class TestRare(unittest.TestCase):
    def rare_sniper(self, **over):
        base = {"intervention__tasks_within_2_prompts_no_rework": 12, "data__sessions": 20}
        base.update(over)
        return metrics(**base)

    def test_sniper_rare_boundaries(self):
        self.assertTrue(is_rare("sniper", ctx(S(e=5), self.rare_sniper())))
        self.assertFalse(is_rare("sniper", ctx(S(e=5), self.rare_sniper(data__sessions=19))))
        self.assertFalse(is_rare("sniper", ctx(S(e=4), self.rare_sniper())))
        self.assertFalse(is_rare("sniper", ctx(S(e=5), self.rare_sniper(intervention__tasks_within_2_prompts_no_rework=9))))

    def test_period_scaling(self):
        m = self.rare_sniper(data__sessions=10, intervention__tasks_within_2_prompts_no_rework=5)
        m["period"]["days"] = 15
        self.assertTrue(is_rare("sniper", ctx(S(e=5), m)))

    def test_commander_needs_both_axes_at_five(self):
        m = metrics(autonomy__long_runs_completed=15)
        self.assertTrue(is_rare("commander", ctx(S(d=5, a=5), m)))
        self.assertFalse(is_rare("commander", ctx(S(d=5, a=4), m)))

    def test_partner_needs_no_axis(self):
        self.assertTrue(is_rare("partner", ctx(S(), metrics(), {"partner_compare_many": "yes"})))
        self.assertFalse(is_rare("partner", ctx(S(), metrics())))

    def test_explorer_needs_growth_of_two(self):
        self.assertTrue(is_rare("explorer", ctx(S(2, 2, 2, 2, 2, 4), growth=("systems", 2))))
        self.assertFalse(is_rare("explorer", ctx(S(2, 2, 2, 2, 2, 4), growth=("systems", 1))))
        self.assertFalse(is_rare("explorer", ctx(S(2, 2, 2, 2, 2, 4))))

    def test_conductor_needs_two_other_achievements(self):
        one = metrics(autonomy__long_runs_completed=15)
        two = metrics(autonomy__long_runs_completed=15, systems__own_mechanism_calls=25)
        self.assertFalse(is_rare("conductor", ctx(S(4, 4, 4, 4, 4, 4), one)))
        self.assertTrue(is_rare("conductor", ctx(S(4, 4, 4, 4, 4, 4), two)))

    def test_insufficient_data_never_crashes_or_rares(self):
        empty = {"period": {"days": 30}, "data": {"sessions": 0}}
        for sc in (S(), S(4, 4, 4, 4, 4, 4), S(1, 1, 1, 1, 1, 1), S(e=5)):
            card = choose.run({"scores": sc}, empty, "ja", None)
            self.assertFalse(card["rare"])


class TestCard(unittest.TestCase):
    def test_ja_card_matches_spec_shape(self):
        m = metrics(intervention__short_prompt_share=0.9)
        card = choose.run({"scores": S(c=4, d=4, v=3, a=2, e=5, s=4)}, m, "ja", None)
        self.assertEqual(card["type"], "sniper")
        self.assertEqual(card["ability_id"], "silence")
        self.assertEqual(card["title"], {"epithet": "沈黙", "role": "狙撃手", "en": "The Silent Sniper"})
        self.assertEqual(card["quote"], "…指示は一度しか言わない")
        self.assertEqual(card["ability"]["name"], "無言の圧")
        self.assertEqual(card["quirk"]["id"], "hover")
        self.assertEqual(card["period"], "直近30日のClaude Codeログより")
        self.assertEqual(card["image"], "assets/characters/sniper_silence.png")
        self.assertEqual(card["no"], "No.21")
        self.assertEqual(card["hashtag"], "#AI肩書き診断")

    def test_rare_swaps_epithet_quote_and_image(self):
        m = metrics(intervention__short_prompt_share=0.9, intervention__tasks_within_2_prompts_no_rework=12)
        card = choose.run({"scores": S(c=4, d=4, v=3, a=2, e=5, s=4)}, m, "ja", None)
        self.assertTrue(card["rare"])
        self.assertEqual(card["title"]["epithet"], "絶対沈黙")
        self.assertEqual(card["quote"], "……")
        self.assertEqual(card["image"], "assets/characters/sniper_silence_rare.png")

    def test_en_card(self):
        m = metrics(intervention__short_prompt_share=0.9)
        card = choose.run({"scores": S(e=5)}, m, "en", None)
        self.assertEqual(card["title"]["epithet"], "Silent")
        self.assertEqual(card["title"]["role"], "Sniper")
        self.assertEqual(card["ability"]["name"], "Silent Pressure")
        self.assertEqual(card["period"], "Last 30 days of Claude Code logs")
        self.assertEqual(card["hashtag"], "#MyAITitle")
        self.assertNotRegex(json.dumps(card, ensure_ascii=False), r"[぀-ヿ一-鿿]")

    def test_unsupported_language_falls_back_to_english(self):
        self.assertEqual(choose.run({"scores": S(e=5)}, metrics(), "fr", None)["lang"], "en")

    def test_growth_fills_axis_name(self):
        card = choose.run({"scores": S(2, 2, 2, 2, 2, 4)}, metrics(), "ja", S(2, 2, 2, 2, 2, 2))
        self.assertEqual(card["ability_id"], "risingstar")
        self.assertIn("仕組み化", card["ability"]["why"])
        self.assertTrue(card["rare"])  # +2

    def test_image_fallbacks(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            def pick(type_id, ability_id, rare):
                sel = select(DB, ctx(S(e=5)))
                sel.type, sel.ability, sel.rare = type_id, DB.ability(ability_id), rare
                return choose.pick_image(DB, sel, tmp)
            self.assertEqual(pick("architect", "sage", False), "assets/characters/fallback/architect.svg")
            (tmp / "sniper_flash.png").write_bytes(b"x")
            self.assertEqual(pick("sniper", "silence", False), "assets/characters/sniper_flash.png")
            self.assertEqual(pick("sniper", "flash", True), "assets/characters/sniper_flash.png")
            (tmp / "sniper_silence.webp").write_bytes(b"x")
            self.assertEqual(pick("sniper", "silence", True), "assets/characters/sniper_silence.webp")
        finally:
            shutil.rmtree(tmp)

    def test_invalid_scores_are_rejected(self):
        for bad in ({"context": 6}, {**S(), "context": "4"}, {**S(), "systems": 0}, {**S(), "autonomy": True}):
            with self.assertRaises(ValueError):
                choose.run({"scores": bad}, metrics(), "ja", None)


class TestHistory(unittest.TestCase):
    def test_previous_ignores_runs_from_the_same_day(self):
        now = datetime(2026, 11, 1, tzinfo=timezone.utc)
        hist = [{"date": (now - timedelta(days=30)).isoformat(), "scores": S(2, 2, 2, 2, 2, 2)},
                {"date": (now - timedelta(hours=2)).isoformat(), "scores": S()}]
        self.assertEqual(choose.previous_scores(hist, now), S(2, 2, 2, 2, 2, 2))
        self.assertIsNone(choose.previous_scores(hist[1:], now))

    def test_save_replaces_same_day_runs(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            path = tmp / "sub" / "history.json"
            now = datetime(2026, 11, 1, tzinfo=timezone.utc)
            choose.save_history(path, [], S(), now)
            choose.save_history(path, choose.load_history(path), S(4, 4, 4, 4, 4, 4), now + timedelta(hours=1))
            data = choose.load_history(path)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["scores"], S(4, 4, 4, 4, 4, 4))
            self.assertEqual(set(data[0]), {"date", "scores"})  # nothing else is stored
            (tmp / "broken.json").write_text("{nope")
            self.assertEqual(choose.load_history(tmp / "broken.json"), [])
        finally:
            shutil.rmtree(tmp)

    def test_cli(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "scores.json").write_text(json.dumps({"scores": S(e=5)}))
            (tmp / "metrics.json").write_text(json.dumps(metrics()))
            rc = choose.main(["--scores", str(tmp / "scores.json"), "--metrics", str(tmp / "metrics.json"),
                              "--lang", "en", "--out", str(tmp / "card.json"),
                              "--history", str(tmp / "h.json"), "--save-history"])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads((tmp / "card.json").read_text())["type"], "sniper")
            self.assertTrue((tmp / "h.json").exists())
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
