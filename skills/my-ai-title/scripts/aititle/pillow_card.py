"""Fallback renderer: draw a simplified card with Pillow (no browser needed).

Supports Latin and CJK text. Follows the HTML template's layout roughly and
the same title rule: start at 60px and shrink by 2px down to 30px until it fits.
"""
from __future__ import annotations

import math
import os
import platform
import unicodedata
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

W, H = 1200, 675
SKILL_DIR = Path(__file__).resolve().parents[2]
AXES = ("context", "delegation", "verification", "autonomy", "efficiency", "systems")
RADAR_LABELS = {"ja": ["文脈", "委任", "検証", "自律", "効率", "仕組"],
                "en": ["Context", "Delegate", "Verify", "Autonomy", "Efficiency", "Systems"]}
CTA = {"ja": "あなたのAI肩書きは？", "en": "What's yours?"}
QUIRK_LABEL = {"ja": "クセ", "en": "Quirk"}
TITLE_BOX = (512, 896)        # x range of the title column
TITLE_MAX, TITLE_MIN, TITLE_STEP = 60, 30, 2

_CJK_FONTS = {
    "Darwin": [("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"),
               ("/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc"),
               ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf")],
    "Windows": [(r"C:\Windows\Fonts\YuGothB.ttc", r"C:\Windows\Fonts\YuGothM.ttc"),
                (r"C:\Windows\Fonts\meiryob.ttc", r"C:\Windows\Fonts\meiryo.ttc"),
                (r"C:\Windows\Fonts\msgothic.ttc", r"C:\Windows\Fonts\msgothic.ttc")],
    "Linux": [("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
              ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
              ("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc", "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc"),
              ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
              ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf")],
}
_LATIN_FONTS = {
    "Darwin": [("/System/Library/Fonts/Helvetica.ttc#1", "/System/Library/Fonts/Helvetica.ttc#0"),
               ("/Library/Fonts/Arial Bold.ttf", "/Library/Fonts/Arial.ttf")],
    "Windows": [(r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\segoeui.ttf"),
                (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf")],
    "Linux": [("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
              ("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"),
              ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")],
}


def _existing(path: str) -> Optional[str]:
    """Existing font path; a "#n" suffix selects face n of a .ttc collection."""
    base, _, index = path.partition("#")
    # macOS stores some font file names in decomposed (NFD) form.
    for p in (base, unicodedata.normalize("NFD", base), unicodedata.normalize("NFC", base)):
        if os.path.isfile(p):
            return p + ("#" + index if index else "")
    return None


def find_fonts(cjk: bool) -> Optional[Tuple[str, str]]:
    """(bold, regular) font paths, or None."""
    env = os.environ.get("MY_AI_TITLE_FONT_CJK" if cjk else "MY_AI_TITLE_FONT")
    if env and os.path.isfile(env.partition("#")[0]):
        return env, env
    table = _CJK_FONTS if cjk else _LATIN_FONTS
    for bold, regular in table.get(platform.system(), []):
        b, r = _existing(bold), _existing(regular)
        if b:
            return b, r or b
    if not cjk:
        return find_fonts(True)  # CJK fonts include Latin glyphs
    return None


class Fonts:
    def __init__(self, bold: str, regular: str):
        from PIL import ImageFont
        self._ImageFont = ImageFont
        self.bold_path, self.regular_path = bold, regular
        self._cache = {}

    def get(self, size: int, bold: bool = True):
        key = (size, bold)
        if key not in self._cache:
            path, _, index = (self.bold_path if bold else self.regular_path).partition("#")
            self._cache[key] = self._ImageFont.truetype(path, size, index=int(index or 0))
        return self._cache[key]


# --- colors ------------------------------------------------------------------------

def rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def mix(a: Sequence[int], b: Sequence[int], t: float) -> Tuple[int, int, int]:
    """t of a, (1 - t) of b."""
    return tuple(round(x * t + y * (1 - t)) for x, y in zip(a, b))  # type: ignore


WHITE, BLACK = (255, 255, 255), (0, 0, 0)
GOLD, GOLD_LIGHT = (212, 175, 55), (243, 220, 138)


# --- text helpers --------------------------------------------------------------------

_NO_LINE_START = set("、。，．・：；？！ー」』）】〉》…‥,.;:!?)]}")


def _tokens(text: str) -> List[str]:
    out: List[str] = []
    buf = ""
    for ch in text:
        if ord(ch) > 0x2E7F:   # CJK and full-width: break anywhere
            if buf:
                out.append(buf)
                buf = ""
            out.append(ch)
        elif ch == " ":
            buf += ch
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf:
        out.append(buf)
    return out


def wrap(text: str, font, width: int) -> List[str]:
    lines: List[str] = []
    line = ""
    for tok in _tokens(text):
        trial = line + tok
        if line and font.getlength(trial.rstrip()) > width and tok.strip() and tok[0] not in _NO_LINE_START:
            lines.append(line.rstrip())
            line = tok.lstrip()
        else:
            line = trial
    if line.strip():
        lines.append(line.rstrip())
    return lines


def title_runs(card: dict, size: int, fonts: Fonts) -> List[Tuple[str, object, Tuple[int, int, int]]]:
    color = rgb(card["color"])
    ep_color = GOLD_LIGHT if card["rare"] else mix(color, WHITE, 0.28)
    t = card["title"]
    if card["lang"] == "ja":
        return [(t["epithet"], fonts.get(size), ep_color),
                ("の", fonts.get(max(1, round(size * 0.62))), mix(WHITE, BLACK, 0.85)),
                (t["role"], fonts.get(size), WHITE)]
    # English: small epithet line above the role, like the HTML template.
    return [(t["epithet"], fonts.get(max(1, round(size * 0.58))), ep_color), (t["role"], fonts.get(size), WHITE)]


def fit_title(card: dict, fonts: Fonts) -> Tuple[int, float]:
    """(font size, width) using the template's rule."""
    width = TITLE_BOX[1] - TITLE_BOX[0]
    size = TITLE_MAX
    while True:
        runs = title_runs(card, size, fonts)
        if card["lang"] == "ja":
            w = sum(f.getlength(s) for s, f, _ in runs)
        else:
            w = max(f.getlength(s) for s, f, _ in runs)   # one run per line
        if w <= width or size <= TITLE_MIN:
            return size, w
        size -= TITLE_STEP


# --- drawing --------------------------------------------------------------------------

def _paste_character(img, card: dict, box: Tuple[int, int, int, int], fonts: Fonts) -> None:
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = box
    path = SKILL_DIR / card["image"]
    if path.suffix.lower() in (".png", ".webp"):
        with Image.open(path) as src:
            ch = src.convert("RGBA")
        max_w, max_h = int((x1 - x0) * 0.92), int((y1 - y0) * 0.86)
        scale = min(max_w / ch.width, max_h / ch.height)
        ch = ch.resize((max(1, int(ch.width * scale)), max(1, int(ch.height * scale))), Image.LANCZOS)
        px = x0 + ((x1 - x0) - ch.width) // 2
        py = y0 + ((y1 - y0) - ch.height) // 2 + 10
        img.alpha_composite(ch, (px, py))
        return
    # SVG cannot be drawn by Pillow: draw a simple emblem in the theme color.
    d = ImageDraw.Draw(img)
    cx, cy, r = (x0 + x1) // 2, (y0 + y1) // 2 + 10, 130
    color = rgb(card["color"])
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (255,), outline=WHITE + (255,), width=6)
    letter = card["title"]["role"][:1]
    f = fonts.get(150)
    d.text((cx, cy), letter, font=f, fill=WHITE + (255,), anchor="mm")


def _radar(img, card: dict, origin: Tuple[int, int], size: int, fonts: Fonts) -> None:
    from PIL import Image, ImageDraw
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    k = size / 268
    cx, cy, R = origin[0] + 134 * k, origin[1] + 136 * k, 80 * k
    pt = lambda i, r: (cx + r * math.sin(math.pi * 2 * i / 6), cy - r * math.cos(math.pi * 2 * i / 6))  # noqa: E731
    grid = (255, 255, 255, 46)
    for lv in range(1, 6):
        d.polygon([pt(i, R * lv / 5) for i in range(6)], outline=grid)
    for i in range(6):
        d.line([pt(i, 0), pt(i, R)], fill=grid)
    color = rgb(card["color"])
    vals = [int(card["scores"][a]) for a in AXES]
    poly = [pt(i, R * v / 5) for i, v in enumerate(vals)]
    d.polygon(poly, fill=color + (115,))
    d.line(poly + [poly[0]], fill=color + (255,), width=3)
    for x, y in poly:
        d.ellipse((x - 4.5, y - 4.5, x + 4.5, y + 4.5), fill=WHITE + (255,), outline=color + (255,), width=2)
    labels = RADAR_LABELS[card["lang"]]
    lf = fonts.get(13 if card["lang"] == "en" else 17)
    vf = fonts.get(20)
    for i, (lab, v) in enumerate(zip(labels, vals)):
        x, y = pt(i, R + 30 * k)
        d.text((x, y - 9 * k), lab, font=lf, fill=(233, 237, 245, 205), anchor="mm")
        d.text((x, y + 13 * k), str(v), font=vf, fill=WHITE + (255,), anchor="mm")
    img.alpha_composite(layer)


def draw(card: dict, fonts: Fonts):
    from PIL import Image, ImageDraw
    lang = card["lang"]
    color = rgb(card["color"])
    rare = bool(card["rare"])
    img = Image.new("RGBA", (W, H), mix(color, (13, 18, 32), 0.30) + (255,))
    d = ImageDraw.Draw(img)

    # frame and face
    frame = GOLD if rare else color
    d.rounded_rectangle((30, 30, 1170, 645), radius=34, fill=frame + (255,))
    d.rounded_rectangle((46, 46, 1154, 629), radius=22, fill=mix(color, (18, 24, 38), 0.22) + (255,))

    # art panel
    art = (68, 68, 488, 607)
    art_bg = mix(color, (26, 20, 8), 0.55) if rare else mix(color, WHITE, 0.22)
    d.rounded_rectangle(art, radius=18, fill=art_bg + (255,),
                        outline=(GOLD_LIGHT if rare else mix(color, WHITE, 0.45)) + (255,), width=3)
    _paste_character(img, card, art, fonts)
    d = ImageDraw.Draw(img)
    no_color = GOLD_LIGHT if rare else mix(color, BLACK, 0.70)
    d.text((84, 80), card["no"], font=fonts.get(19), fill=no_color + (190,))

    # title block (vertically centred next to the radar)
    size, _w = fit_title(card, fonts)
    runs = title_runs(card, size, fonts)
    sub = [] if lang == "en" else [(card["title"]["en"], fonts.get(22), mix(color, WHITE, 0.35), 8)]
    open_q, close_q = ("「", "」") if lang == "ja" else ("\u201c", "\u201d")
    quote_lines = wrap(open_q + card["quote"] + close_q, fonts.get(21), TITLE_BOX[1] - TITLE_BOX[0])
    title_h = size if lang == "ja" else round(size * 0.58) + 4 + size
    block_h = title_h + sum(f.size + gap for _, f, _, gap in sub) + len(quote_lines) * 30 + 8
    y = 68 + (216 - block_h) / 2
    if lang == "ja":
        x, base = TITLE_BOX[0], y + size
        for s, f, c in runs:
            d.text((x, base), s, font=f, fill=c + (255,), anchor="ls")
            x += f.getlength(s)
    else:
        (ep, ef, ec), (role, rf, rc) = runs
        d.text((TITLE_BOX[0], y + ef.size), ep, font=ef, fill=ec + (255,), anchor="ls")
        base = y + ef.size + 4 + size
        d.text((TITLE_BOX[0], base), role, font=rf, fill=rc + (255,), anchor="ls")
    y = base + 12
    for s, f, c, gap in sub:
        d.text((TITLE_BOX[0], y), s, font=f, fill=c + (255,))
        y += f.size + gap
    for line in quote_lines:
        d.text((TITLE_BOX[0], y + 8), line, font=fonts.get(21), fill=mix(WHITE, (15, 20, 32), 0.85) + (255,))
        y += 30

    _radar(img, card, (906, 62), 216, fonts)
    d = ImageDraw.Draw(img)

    # ability + quirk box (shrink text until it fits)
    box = (512, 296, 1124, 578)
    d.rounded_rectangle(box, radius=16, fill=(244, 246, 250, 255))
    inner_w = box[2] - box[0] - 48
    for scale in (1.0, 0.94, 0.88, 0.82, 0.76, 0.7):
        fa, fw = fonts.get(round(30 * scale)), fonts.get(round(23 * scale), bold=False)
        fq, fqw = fonts.get(round(21 * scale)), fonts.get(round(19 * scale), bold=False)
        why_lines = wrap(card["ability"]["why"], fw, inner_w)
        qlabel = QUIRK_LABEL[lang]
        label_w = fonts.get(15).getlength(qlabel) + 16
        qname_lines = wrap(card["quirk"]["name"], fq, inner_w - label_w - 10)
        qwhy_lines = wrap(card["quirk"]["why"], fqw, inner_w) if card["quirk"]["why"] else []
        total = (fa.size + 6 + len(why_lines) * fw.size * 1.55 + 26
                 + len(qname_lines) * fq.size * 1.35 + len(qwhy_lines) * fqw.size * 1.5)
        if total <= box[3] - box[1] - 40:
            break
    y = box[1] + (box[3] - box[1] - total) / 2
    bx = box[0] + 24
    d.text((bx, y), card["ability"]["name"] if lang == "en" else f"【{card['ability']['name']}】",
           font=fa, fill=mix(color, BLACK, 0.75) + (255,))
    y += fa.size + 6
    for line in why_lines:
        d.text((bx, y), line, font=fw, fill=(27, 34, 48, 255))
        y += fw.size * 1.55
    y += 6
    for xx in range(bx, box[2] - 24, 12):
        d.line([(xx, y), (xx + 6, y)], fill=(213, 218, 228, 255), width=2)
    y += 14
    lf = fonts.get(15)
    d.rounded_rectangle((bx, y + 2, bx + label_w, y + 26), radius=6, fill=mix(color, BLACK, 0.75) + (255,))
    d.text((bx + label_w / 2, y + 14), qlabel, font=lf, fill=WHITE + (255,), anchor="mm")
    for i, line in enumerate(qname_lines):
        d.text((bx + label_w + 10, y), line, font=fq, fill=(42, 49, 64, 255))
        y += fq.size * 1.35
    for line in qwhy_lines:
        d.text((bx, y + 2), line, font=fqw, fill=(74, 82, 99, 255))
        y += fqw.size * 1.5

    # footer
    fy = 596
    d.text((512, fy), card["period"], font=fonts.get(15, bold=False), fill=(150, 155, 165, 255), anchor="lm")
    tag_f, cta_f = fonts.get(17), fonts.get(17)
    tag_w = tag_f.getlength(card["hashtag"])
    d.text((1124, fy), card["hashtag"], font=tag_f,
           fill=(GOLD_LIGHT if rare else mix(color, WHITE, 0.4)) + (255,), anchor="rm")
    d.text((1124 - tag_w - 10, fy), CTA[lang], font=cta_f, fill=(222, 224, 228, 255), anchor="rm")
    return img.convert("RGB")


def render(card: dict, out: Path) -> str:
    """Draw the card. Returns the language actually used."""
    lang = card["lang"]
    fonts_paths = find_fonts(cjk=lang in ("ja", "zh", "ko"))
    if fonts_paths is None and lang != "en":
        import choose  # rebuild the wording in English
        card = choose.localize(card, "en")
        lang = "en"
        fonts_paths = find_fonts(cjk=False)
    if fonts_paths is None:
        raise RuntimeError("no usable font found for the Pillow renderer; install a browser or set MY_AI_TITLE_FONT")
    img = draw(card, Fonts(*fonts_paths))
    tmp = out.with_name(out.name + ".tmp.png")
    img.save(tmp, "PNG", optimize=True)
    tmp.replace(out)
    return lang
