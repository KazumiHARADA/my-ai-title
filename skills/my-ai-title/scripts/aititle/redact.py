"""Redaction applied to every excerpt before Claude reads it.

When unsure, redact. Order matters: whole structures (code, secrets, URLs,
paths) go first, then word-level rules.

Placeholders: [CODE] [LOG] [SECRET] [EMAIL] [URL] [PATH] [HOST] [NAME] [ID] [NUM]
"""
from __future__ import annotations

import re
from typing import Iterable, Optional


# Placeholders are held as private-use characters while redacting so that later
# word-level rules do not touch them, then rendered as [NAME] etc. at the end.
_NAMES = ("CODE", "LOG", "SECRET", "EMAIL", "URL", "PATH", "HOST", "NAME", "ID", "NUM")
_PH = {n: chr(0xE000 + i) for i, n in enumerate(_NAMES)}
_PH_BACK = {v: "[" + k + "]" for k, v in _PH.items()}
CODE, LOG, SECRET, EMAIL, URL, PATH, HOST, NAME, ID, NUM = (_PH[n] for n in _NAMES)

_CODE_BLOCK_RE = re.compile(r"```.*?(?:```|$)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_XMLISH_BLOCK_RE = re.compile(r"<(pasted_content|file|document|code)[^>]*>.*?(?:</\1>|$)", re.DOTALL | re.IGNORECASE)

_SECRET_RES = [
    re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_\-]{12,}"),                 # OpenAI/Anthropic/Stripe style
    re.compile(r"\b(gh[pousr]|github_pat)_[A-Za-z0-9_]{16,}"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.DOTALL),
    re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|auth|bearer|パスワード|トークン)"
               r"(\s*[:=：]\s*|\s+)[\"']?[^\s\"'、。]{4,}"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),                              # long hex
    re.compile(r"\b(?=[A-Za-z0-9+/_\-]*\d)(?=[A-Za-z0-9+/_\-]*[A-Za-z])[A-Za-z0-9+/_\-]{32,}={0,2}"),  # long base64-ish
]
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"\b(?:https?|ftp|ssh|git|wss?|file)://[^\s<>\"'）)」]+|\bwww\.[^\s<>\"'）)」]+", re.IGNORECASE)
_PATH_RES = [
    re.compile(r"(?:~|[\w.\-]+)?(?:/[^\s/:*?\"<>|、。「」（）()]+){2,}/?"),   # unix paths (2+ segments)
    re.compile(r"[A-Za-z]:\\[^\s:*?\"<>|、。]+"),                        # windows paths
    re.compile(r"\b[\w.\-]+/[\w.\-/]+\.\w{1,6}\b"),                    # relative path with extension
    re.compile(r"\b[\w\-]+\.(?:py|rb|js|jsx|ts|tsx|go|rs|java|kt|swift|c|cc|cpp|h|hpp|cs|php|vue|svelte"
               r"|css|scss|html|json|ya?ml|toml|ini|env|md|sql|sh|lock|xml|csv|txt|log)\b", re.IGNORECASE),
]
_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
_HOST_RE = re.compile(r"\b(?:[A-Za-z0-9\-]+\.)+(?:com|net|org|io|ai|dev|app|co|jp|cloud|local|internal|so|me|us|uk|de|xyz|tech|info|biz)\b(?::\d+)?", re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<![\w])@[A-Za-z0-9_\-]{2,}")
_TICKET_RE = re.compile(r"(?<![\w])(#\d+|[A-Z][A-Z0-9]+-\d+)\b")
_NUM_RE = re.compile(r"\d{4,}")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[_\-.'][A-Za-z0-9]+)*")
_CJK_RE = re.compile(r"[぀-ヿ一-鿿가-힯]")

# Common English and everyday software words that are never names. Everything
# capitalized that is not here is treated as a possible proper noun.
_COMMON = set("""
a about above after again against all almost also always am an and any anything are around as ask at away back
bad be because been before being below best better between both but by can cannot change check clear could
data day did do does doing done down during each else end enough even every everything example fast few file
files find first fix for from full get give go going good got great had has have having he her here him his
how i if in instead into is it its just keep kind know last later least left less let like little look lot
make many maybe me might more most much must my need needs never new next no not nothing now of off ok okay
old on once one only open or other our out over own part please put quite rather read really right run same
say see seem set she should show side simple since small so some something still stop such sure take than
thank thanks that the their them then there these they thing things think this those though through time to
too try turn two under until up us use used using very want was way we well were what when where which while
who why will with without work would write yes yet you your yeah hi hello sorry also again first second third
add added adding api app apply bug bugs build branch call case cache ci cli click code command commit component
config console copy create css database debug default delete deploy design diff doc docs edit error errors
feature field fixed form function handle header html image import input install issue item json key layout
line link list load log logic login logout merge message method mode model module name page param path plan
plugin pr prod production pull push query readme refactor release remove rename request response result
return review route rule save schema screen script search server service session setting settings setup skill
spec sql staging state status step style table task test tests text title token tool type ui update url user
users value version view web window yaml review reviewed tested passing failing works working broken lint
agent agents prompt prompts output inputs outputs note notes card cards chart image images png svg markdown
readme local remote main master dev development frontend backend endpoint client token tokens auth parallel
python ruby javascript typescript react node rails go rust java swift kotlin docker git github npm yarn pip
rate limit limits limiting bump docs doc migration migrate rollback retry timeout queue job jobs worker event
events hook hooks cron schedule report summary done finished complete completed implement implemented
investigate investigated found looks look checked created updated fixed bumped added removed moved
""".split())


def _sentence_start(text: str, pos: int) -> bool:
    before = text[:pos].rstrip(" \t\"'(")
    return not before or before[-1] in ".!?\n:。！？"


def _tokenwise(text: str, cjk_context: bool, terms_lower: set) -> str:
    out = []
    last = 0
    for m in _WORD_RE.finditer(text):
        word = m.group(0)
        start = m.start()
        out.append(text[last:start])
        last = m.end()
        low = word.lower()
        if low in terms_lower:
            out.append(NAME)
        elif re.search(r"[_\-.]", word) or (re.search(r"\d", word) and re.search(r"[A-Za-z]", word)):
            out.append(ID)
        elif re.search(r"[a-z][A-Z]", word) or (len(word) > 1 and word.isupper() and low not in _COMMON):
            out.append(ID if re.search(r"[a-z][A-Z]", word) else NAME)
        elif word[0].isupper() and low not in _COMMON and word != "I" \
                and not (_sentence_start(text, start) and re.fullmatch(r"[A-Z][a-z]+(ed|ing|ly)", word)):
            out.append(NAME)
        elif cjk_context and len(word) >= 3 and low not in _COMMON:
            out.append(NAME)
        else:
            out.append(word)
    out.append(text[last:])
    return "".join(out)


def _logish(line: str) -> bool:
    s = line.strip()
    if len(s) < 25:
        return False
    sym = sum(1 for c in s if not c.isalnum() and not c.isspace() and not _CJK_RE.match(c))
    return sym / len(s) > 0.25 or bool(re.match(r"^\s*(at |File \"|Traceback|\w+Error:|\[\d{2}:\d{2}|\d{4}-\d{2}-\d{2}[ T]\d{2}:)", line))


def redact(text: str, terms: Optional[Iterable[str]] = None, limit: Optional[int] = None) -> str:
    t = text
    t = _CODE_BLOCK_RE.sub(" " + CODE + " ", t)
    t = _XMLISH_BLOCK_RE.sub(" " + CODE + " ", t)
    for rx in _SECRET_RES:
        t = rx.sub(SECRET, t)
    t = _EMAIL_RE.sub(EMAIL, t)
    t = _URL_RE.sub(URL, t)
    for rx in _PATH_RES:
        t = rx.sub(PATH, t)
    t = _IP_RE.sub(HOST, t)
    t = _HOST_RE.sub(HOST, t)
    t = _INLINE_CODE_RE.sub(CODE, t)
    t = "\n".join(LOG if _logish(line) else line for line in t.split("\n"))
    t = _MENTION_RE.sub(NAME, t)
    t = _TICKET_RE.sub(ID, t)
    # Everyday words (e.g. "test" from a branch name) are not identifying.
    terms_lower = {x.lower() for x in (terms or ()) if x} - _COMMON
    # Multi-word / non-Latin terms (e.g. Japanese project names) first.
    for term in sorted(terms_lower, key=len, reverse=True):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", term):
            t = re.sub(re.escape(term), NAME, t, flags=re.IGNORECASE)
    t = _tokenwise(t, bool(_CJK_RE.search(t)), terms_lower)
    t = _NUM_RE.sub(NUM, t)
    t = re.sub("([" + CODE + LOG + r"])(\s*[" + CODE + LOG + r"])+", r"\1", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if limit and len(t) > limit:
        t = t[:limit].rstrip() + "…"
    return "".join(_PH_BACK.get(c, c) for c in t)
