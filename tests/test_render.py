import json
import os
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from helpers import ROOT, SCRIPTS  # noqa: F401  (sets sys.path)

import choose
import render
from aititle import pillow_card, typesdb
from aititle.selection import Selection

DB = typesdb.load()
BROWSER = render.find_browser()
try:
    import PIL  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
SLOW = os.environ.get("MY_AI_TITLE_SLOW") == "1"   # exhaustive browser checks

SCORES = {"context": 4, "delegation": 3, "verification": 3, "autonomy": 2, "efficiency": 5, "systems": 4}


def card_for(ability_id: str, rare: bool, lang: str) -> dict:
    a = DB.ability(ability_id)
    sel = Selection(type=a.type, ability=a, ability_ratio=1.0, quirk=DB.quirks[0], rare=rare, growth_axis="systems")
    return choose.build_card(DB, sel, SCORES, 30, lang)


def all_title_cards(lang: str):
    for t in DB.types.values():
        for a in t.abilities:
            for rare in (False, True):
                yield card_for(a.id, rare, lang)


class TestHtml(unittest.TestCase):
    def test_all_placeholders_filled(self):
        for lang in ("ja", "en"):
            doc = render.build_html(card_for("silence", False, lang))
            self.assertNotIn("{{", doc)
            self.assertIn("data:image/png;base64,", doc)
            self.assertNotIn('class="rare"', doc)

    def test_rare_and_svg_fallback(self):
        card = card_for("legion", True, "ja")
        card["image"] = "assets/characters/fallback/conductor.svg"   # as when the PNG is missing
        doc = render.build_html(card)
        self.assertIn('class="rare"', doc)
        self.assertNotIn('class="badge"', doc)   # no badge: the frame shows it is rare
        self.assertIn("<svg", doc.split('class="art"')[1][:2000])

    def test_text_is_escaped(self):
        card = card_for("silence", False, "en")
        card["quote"] = '<script>alert(1)</script> & "x"'
        doc = render.build_html(card)
        self.assertNotIn("<script>alert(1)", doc)
        self.assertIn("&lt;script&gt;", doc)

    def test_en_title_has_no_leading_the(self):
        doc = render.build_html(card_for("massproduce", True, "en"))
        self.assertIn('<span class="ep">Mass Transmutation</span>', doc)

    def test_tint_is_lighter(self):
        self.assertEqual(render.tint("#000000", 0.5), "#808080")


class TestPngCrop(unittest.TestCase):
    def png(self, w, h, rows):
        raw = b"".join(b"\x02" + bytes(r) * w for r in rows)  # filter 2 (Up) on every row
        def chunk(k, b):
            return struct.pack(">I", len(b)) + k + b + struct.pack(">I", zlib.crc32(k + b) & 0xFFFFFFFF)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

    def test_crop_keeps_top_rows(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            rows = [(i % 7, 0, 0) for i in range(10)]
            (tmp / "a.png").write_bytes(self.png(4, 10, rows))
            render.crop_png_top(tmp / "a.png", tmp / "b.png", 6)
            data = (tmp / "b.png").read_bytes()
            self.assertEqual(struct.unpack(">II", data[16:24]), (4, 6))
            self.assertTrue(data.endswith(render.PNG_END))
            if HAS_PIL:
                from PIL import Image
                with Image.open(tmp / "b.png") as im:
                    self.assertEqual(im.size, (4, 6))
            with self.assertRaises(ValueError):
                render.crop_png_top(tmp / "a.png", tmp / "c.png", 11)
        finally:
            shutil.rmtree(tmp)


class TestCli(unittest.TestCase):
    def test_refuses_to_overwrite(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "card.json").write_text(json.dumps(card_for("silence", False, "ja"), ensure_ascii=False))
            (tmp / "out.png").write_bytes(b"keep")
            rc = render.main(["--card", str(tmp / "card.json"), "--out", str(tmp / "out.png")])
            self.assertEqual(rc, render.EXIT_EXISTS)
            self.assertEqual((tmp / "out.png").read_bytes(), b"keep")
        finally:
            shutil.rmtree(tmp)

    def test_browser_override(self):
        old = os.environ.get("MY_AI_TITLE_BROWSER")
        os.environ["MY_AI_TITLE_BROWSER"] = "/nonexistent/chrome"
        try:
            self.assertIsNone(render.find_browser())
        finally:
            if old is None:
                del os.environ["MY_AI_TITLE_BROWSER"]
            else:
                os.environ["MY_AI_TITLE_BROWSER"] = old


@unittest.skipUnless(BROWSER, "no Chromium-based browser found")
class TestBrowser(unittest.TestCase):
    LONGEST = [("perpetual", True, "ja"), ("massproduce", True, "en")]  # examples from the spec

    def test_longest_titles_fit(self):
        cases = [card_for(a, r, l) for a, r, l in self.LONGEST]
        if SLOW:
            cases = list(all_title_cards("ja")) + list(all_title_cards("en"))
        for card in cases:
            with self.subTest(title=card["title"]["en"], lang=card["lang"]):
                fits, px = render.measure_fit(render.build_html(card), BROWSER)
                self.assertTrue(fits, f"{card['title']} overflows at {px}px")
                self.assertGreaterEqual(px, 30)

    def test_render_png_both_languages(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            for lang in ("ja", "en"):
                out = tmp / f"{lang}.png"
                self.assertEqual(render.render(card_for("silence", True, lang), out, "browser"), "browser")
                data = out.read_bytes()
                self.assertEqual(struct.unpack(">II", data[16:24]), (render.WIDTH, render.HEIGHT))
                if HAS_PIL:
                    from PIL import Image
                    with Image.open(out) as im:
                        # the bottom rows are the dark page background, not an unpainted white strip
                        self.assertLess(sum(im.convert("RGB").getpixel((600, render.HEIGHT - 5))), 200)
        finally:
            shutil.rmtree(tmp)


@unittest.skipUnless(HAS_PIL, "Pillow not installed")
class TestPillow(unittest.TestCase):
    def test_every_title_fits(self):
        for lang in ("ja", "en"):
            paths = pillow_card.find_fonts(cjk=(lang == "ja"))
            if not paths:
                self.skipTest("no font")
            fonts = pillow_card.Fonts(*paths)
            width = pillow_card.TITLE_BOX[1] - pillow_card.TITLE_BOX[0]
            for card in all_title_cards(lang):
                with self.subTest(title=card["title"]["en"], lang=lang):
                    size, w = pillow_card.fit_title(card, fonts)
                    self.assertLessEqual(w, width)
                    self.assertGreaterEqual(size, pillow_card.TITLE_MIN)

    def test_render_both_languages(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            from PIL import Image
            for lang, ability, rare, svg in (("ja", "perpetual", True, False), ("en", "massproduce", True, False),
                                             ("ja", "legion", False, True)):
                out = tmp / f"{lang}-{ability}.png"
                card = card_for(ability, rare, lang)
                if svg:  # Pillow cannot draw SVG; it falls back to an emblem
                    card["image"] = "assets/characters/fallback/conductor.svg"
                used = render.render(card, out, "pillow")
                self.assertTrue(used.startswith("pillow"))
                with Image.open(out) as im:
                    self.assertEqual(im.size, (render.WIDTH, render.HEIGHT))
        finally:
            shutil.rmtree(tmp)

    def test_without_cjk_font_falls_back_to_english(self):
        tmp = Path(tempfile.mkdtemp())
        original = pillow_card.find_fonts
        try:
            pillow_card.find_fonts = lambda cjk: None if cjk else original(False)
            used = pillow_card.render(card_for("silence", False, "ja"), tmp / "x.png")
            self.assertEqual(used, "en")
        finally:
            pillow_card.find_fonts = original
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
