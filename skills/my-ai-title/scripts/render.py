#!/usr/bin/env python3
"""card.json -> 1200x675 PNG.

Usage:
    python3 render.py --card card.json [--out PATH] [--force] [--no-open]
                      [--renderer auto|browser|playwright|pillow]

Renderers, in order (auto):
  1. A Chromium-based browser (Chrome, Edge, Brave, Chromium) in headless mode.
     Set MY_AI_TITLE_BROWSER to a browser executable to override the search.
  2. Playwright's Chromium, if the playwright package and its browser exist.
  3. Pillow, drawing a simplified card (Latin and CJK). If no CJK font is
     found, the card is rendered in English instead.

Without --out the card goes to the first writable folder of ~/Desktop,
the selected host's local config directory and the current directory, named with today's date
(my-ai-title-card-2026-11-16.png, then -2, -3, ...), so it never overwrites.
With --out, an existing file is not overwritten unless --force is given
(exit code 3 means "file exists").

The finished card is opened in the system's image viewer unless --no-open.
Nothing is fetched from the network.
"""
from __future__ import annotations

import argparse
import datetime
import base64
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import struct
import tempfile
import time
import zlib
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aititle.pillow_card import char_zoom  # noqa: E402  (no Pillow needed for this)
from radar import radar  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS = SKILL_DIR / "assets"
TEMPLATES = {"ja": ASSETS / "card_h.html", "en": ASSETS / "card_h_en.html"}
AXES = ("context", "delegation", "verification", "autonomy", "efficiency", "systems")
RADAR_LABELS = {"ja": None, "en": ["Context", "Delegate", "Verify", "Autonomy", "Efficiency", "Systems"]}
RADAR_FONT = {"ja": 19, "en": 13}
CTA = {"ja": "あなたのAI肩書きは？", "en": "What's yours?"}
WIDTH, HEIGHT = 1200, 675
# Headless Chrome's viewport is shorter than its window (by ~90px on macOS), so
# the window is opened taller and the screenshot is cropped back to HEIGHT.
WINDOW_EXTRA = 300
EXIT_EXISTS = 3
PNG_END = b"\x00\x00\x00\x00IEND\xaeB`\x82"

# Runs after the template's own fit script (listeners fire in order) and
# records whether the title fits, so tests can check it with --dump-dom: no
# horizontal overflow, and the epithet stays on one line (English layout).
_FIT_PROBE = """<script>window.addEventListener('load',()=>{const n=document.querySelector('.name'),
b=n.parentElement,ep=n.querySelector('.ep'),st=getComputedStyle(ep),
lines=Math.round(ep.getBoundingClientRect().height/(parseFloat(st.fontSize)*1.02)),
ok=n.scrollWidth<=b.clientWidth&&(st.display!=='block'||lines<=1);
document.documentElement.dataset.fit=ok+':'+parseInt(n.style.fontSize||60)});</script>"""


# --- HTML ------------------------------------------------------------------------

def tint(hex_color: str, white: float = 0.78) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    mix = lambda c: round(c + (255 - c) * white)  # noqa: E731
    return "#{:02X}{:02X}{:02X}".format(mix(r), mix(g), mix(b))


def character_html(image: str) -> str:
    path = SKILL_DIR / image
    if path.suffix.lower() == ".svg":
        svg = path.read_text(encoding="utf-8")
        return re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
    mime = "image/webp" if path.suffix.lower() == ".webp" else "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:{mime};base64,{data}" alt="">'


def build_html(card: dict) -> str:
    lang = card["lang"]
    e = html.escape
    t = card["title"]
    stem = t["epithet"]
    scores = [int(card["scores"][a]) for a in AXES]
    values = {
        "RARE": "rare" if card["rare"] else "",
        "COLOR": card["color"],
        "TINT": tint(card["color"]),
        "ZOOM": f"{char_zoom(card.get('type', '')):g}",
        "NO": e(card["no"]),
        "BADGE": "",  # rare cards are shown by the frame and glow only, no badge
        "CHAR": character_html(card["image"]),
        "EPITHET_STEM": e(stem),
        "NAME": e(t["role"]),
        "EN": e(t["en"]),
        "QUOTE": e(card["quote"]),
        "RADAR": radar(scores, card["color"], axes=RADAR_LABELS[lang], fs=RADAR_FONT[lang]),
        "ABILITY": e(card["ability"]["name"]),
        "ABILITY_WHY": e(card["ability"]["why"]),
        "WEAK": e(card["quirk"]["name"]),
        "WEAK_WHY": e(card["quirk"]["why"]),
        "PERIOD": e(card["period"]),
        "CTA": e(CTA[lang]),
        "TAG": e(card["hashtag"]),
    }
    doc = TEMPLATES[lang].read_text(encoding="utf-8")
    doc = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values[m.group(1)], doc)
    return doc.replace("</body>", _FIT_PROBE + "</body>")


# --- browsers ----------------------------------------------------------------------

def browser_candidates() -> List[str]:
    system = platform.system()
    out: List[str] = []
    if system == "Darwin":
        apps = ["Google Chrome", "Chromium", "Microsoft Edge", "Brave Browser", "Google Chrome Canary"]
        for base in ("/Applications", os.path.expanduser("~/Applications")):
            out += [f"{base}/{a}.app/Contents/MacOS/{a}" for a in apps]
    elif system == "Windows":
        rel = [r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe",
               r"BraveSoftware\Brave-Browser\Application\brave.exe", r"Chromium\Application\chrome.exe"]
        for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                out += [os.path.join(base, r) for r in rel]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "microsoft-edge", "microsoft-edge-stable", "brave-browser", "chrome"):
        found = shutil.which(name)
        if found:
            out.append(found)
    return out


def find_browser() -> Optional[str]:
    override = os.environ.get("MY_AI_TITLE_BROWSER")
    if override:
        return override if os.path.isfile(override) else None
    return next((c for c in browser_candidates() if os.path.isfile(c)), None)


def _browser_args(browser: str, profile: str) -> List[str]:
    return [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
            "--disable-sync", "--disable-component-update", "--no-pings", "--mute-audio",
            f"--user-data-dir={profile}", f"--window-size={WIDTH},{HEIGHT + WINDOW_EXTRA}",
            "--force-device-scale-factor=1", "--virtual-time-budget=5000"]


def _wait_and_stop(proc: subprocess.Popen, done, timeout: float) -> bool:
    """Wait until done() is true, then stop the browser.

    Headless Chrome on macOS sometimes keeps running after it has written its
    output, so we watch for the output instead of waiting for the process.
    """
    deadline = time.monotonic() + timeout
    ok = False
    while time.monotonic() < deadline:
        if done():
            ok = True
            break
        if proc.poll() is not None:
            ok = done()
            break
        time.sleep(0.1)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    return ok


def _launch(browser: str, html_doc: str, extra: List[str], tmp: Path, stdout=subprocess.DEVNULL) -> subprocess.Popen:
    page = tmp / "card.html"
    page.write_text(html_doc, encoding="utf-8")
    args = _browser_args(browser, str(tmp / "profile")) + extra + [page.as_uri()]
    return subprocess.Popen(args, stdout=stdout, stderr=subprocess.DEVNULL)


def render_browser(html_doc: str, out: Path, browser: str, timeout: float = 60) -> bool:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        shot = tmp / "shot.png"

        def done() -> bool:
            # A complete PNG ends with the IEND chunk; until then Chrome is still writing.
            try:
                with shot.open("rb") as fh:
                    fh.seek(-12, os.SEEK_END)
                    return fh.read() == PNG_END
            except OSError:
                return False

        try:
            proc = _launch(browser, html_doc, [f"--screenshot={shot}"], tmp)
        except OSError:
            return False
        if not _wait_and_stop(proc, done, timeout):
            return False
        try:
            crop_png_top(shot, out, HEIGHT)
        except ValueError:
            return False
        return True


def measure_fit(html_doc: str, browser: str, timeout: float = 60) -> Optional[tuple]:
    """(fits, font_px) of the title after the template's fit script ran."""
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        dom = tmp / "dom.html"
        with dom.open("wb") as fh:
            proc = _launch(browser, html_doc, ["--dump-dom"], tmp, stdout=fh)
            _wait_and_stop(proc, lambda: b"</html>" in dom.read_bytes(), timeout)
        m = re.search(r'data-fit="(true|false):(\d+)"', dom.read_text(encoding="utf-8", errors="replace"))
    return (m.group(1) == "true", int(m.group(2))) if m else None


def _chunks(data: bytes):
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        yield kind, data[pos + 8:pos + 8 + length]
        pos += 12 + length


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def crop_png_top(src: Path, dst: Path, height: int) -> None:
    """Keep the top ``height`` rows of a non-interlaced 8-bit PNG (stdlib only).

    PNG row filters only refer to the row above, so dropping rows at the
    bottom needs no un-filtering: decompress, truncate, recompress.
    """
    data = src.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    chunks = list(_chunks(data))
    ihdr = chunks[0][1]
    w, h, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if depth != 8 or interlace or channels is None or h < height:
        raise ValueError("unsupported PNG layout")
    raw = zlib.decompress(b"".join(body for kind, body in chunks if kind == b"IDAT"))
    stride = 1 + w * channels
    new_ihdr = struct.pack(">IIBBBBB", w, height, depth, ctype, _comp, _filt, interlace)
    extra = b"".join(_chunk(k, b) for k, b in chunks[1:] if k not in (b"IDAT", b"IEND"))
    out = (data[:8] + _chunk(b"IHDR", new_ihdr) + extra
           + _chunk(b"IDAT", zlib.compress(raw[:stride * height], 9)) + _chunk(b"IEND", b""))
    dst.write_bytes(out)


def render_playwright(html_doc: str, out: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            page.set_content(html_doc, wait_until="load")
            page.wait_for_function("document.documentElement.dataset.fit !== undefined", timeout=5000)
            page.screenshot(path=str(out))
            b.close()
        return True
    except Exception:
        return False


# --- output ----------------------------------------------------------------------------

def output_dirs(source: str = "claude") -> List[Tuple[Path, bool]]:
    """Candidate folders in order, each with whether it may be created."""
    home = Path.home()
    if source == "codex":
        config = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    else:
        config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude")
    return [(home / "Desktop", False), (config / "my-ai-title", True), (Path.cwd(), False)]


def writable(folder: Path, create: bool = False) -> bool:
    """True if a file can actually be created there.

    os.access is not enough: macOS privacy controls and sandboxes can refuse
    a write that the permission bits allow, so try one.
    """
    try:
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".my-ai-title-", suffix=".tmp"):
            pass
        return True
    except OSError:
        return False


def default_out(lang: str, dirs: Optional[List[Tuple[Path, bool]]] = None,
                today: Optional[datetime.date] = None, source: str = "claude") -> Path:
    folder = next((d for d, create in (dirs or output_dirs(source)) if writable(d, create)), Path.cwd())
    stem = "my-ai-title-card" + ("-en" if lang == "en" else "") + "-" + (today or datetime.date.today()).isoformat()
    out = folder / f"{stem}.png"
    n = 2
    while out.exists():
        out = folder / f"{stem}-{n}.png"
        n += 1
    return out


def open_file(path: Path) -> bool:
    """Open the image in the system viewer. False if that was not possible."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True
        cmd = "open" if system == "Darwin" else shutil.which("xdg-open")
        if not cmd:
            return False
        return subprocess.run([cmd, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# --- main ------------------------------------------------------------------------------

def render(card: dict, out: Path, renderer: str = "auto") -> str:
    """Render and return the name of the renderer used."""
    if renderer in ("auto", "browser"):
        browser = find_browser()
        if browser and render_browser(build_html(card), out, browser):
            return "browser"
        if renderer == "browser":
            raise RuntimeError("no Chromium-based browser could render the card")
    if renderer in ("auto", "playwright"):
        if render_playwright(build_html(card), out):
            return "playwright"
        if renderer == "playwright":
            raise RuntimeError("playwright is not available")
    from aititle import pillow_card
    used_lang = pillow_card.render(card, out)
    return "pillow" if used_lang == card["lang"] else f"pillow ({used_lang} fallback)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--card", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None,
                    help="default: ~/Desktop/my-ai-title-card-<date>.png (see above)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing --out file")
    ap.add_argument("--no-open", action="store_true", help="do not open the card after rendering")
    ap.add_argument("--renderer", choices=("auto", "browser", "playwright", "pillow"), default="auto")
    args = ap.parse_args(argv)
    card = json.loads(args.card.read_text(encoding="utf-8"))
    if args.out:
        out = args.out
        if out.exists() and not args.force:
            print(f"{out} already exists. Ask the user, then rerun with --force to overwrite.", file=sys.stderr)
            return EXIT_EXISTS
    else:
        out = default_out(card.get("lang", "ja"), source=card.get("source", "claude"))
    used = render(card, out, args.renderer)
    print(f"rendered with {used} -> {out.resolve()}", file=sys.stderr)
    if not args.no_open:
        print("opened" if open_file(out) else "could not open it automatically", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
