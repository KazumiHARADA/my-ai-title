"""Language-agnostic text helpers."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List, Sequence, Set

_KANA_RE = re.compile(r"[぀-ヿ]")
_HANGUL_RE = re.compile(r"[가-힯]")
_HAN_RE = re.compile(r"[一-鿿]")
_CJK_CHAR_RE = re.compile(r"[぀-ヿ一-鿿가-힯]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_CODE_BLOCK_RE = re.compile(r"```.*?(```|$)", re.DOTALL)


def language_of(text: str) -> str:
    if _KANA_RE.search(text):
        return "ja"
    if _HANGUL_RE.search(text):
        return "ko"
    if _HAN_RE.search(text):
        return "zh"
    if _LATIN_WORD_RE.search(text):
        return "en"  # Latin-script; treated as English for output purposes
    return "other"


def dominant_language(texts: Sequence[str]) -> Dict[str, object]:
    counts = Counter(language_of(t) for t in texts if t.strip())
    total = sum(counts.values())
    if not total:
        return {"dominant": "en", "shares": {}}
    shares = {k: round(v / total, 2) for k, v in counts.most_common()}
    return {"dominant": counts.most_common(1)[0][0], "shares": shares}


def size_units(text: str) -> float:
    """Rough, language-neutral instruction size.

    One Latin word ~ one unit; CJK characters count 0.5 each (two characters
    carry roughly one English word of meaning). Code blocks are excluded.
    """
    t = _CODE_BLOCK_RE.sub(" ", text)
    return len(_LATIN_WORD_RE.findall(t)) + 0.5 * len(_CJK_CHAR_RE.findall(t))


def normalize(text: str) -> str:
    t = _CODE_BLOCK_RE.sub(" ", text.lower())
    t = re.sub(r"\d+", "0", t)
    return re.sub(r"[\W_]+", "", t)


def trigrams(text: str) -> Set[str]:
    n = normalize(text)
    return {n[i:i + 3] for i in range(len(n) - 2)}


def similar_clusters(texts: Sequence[str], threshold: float = 0.5, min_len: int = 15) -> List[List[int]]:
    """Cluster near-duplicate texts (Jaccard on character trigrams).

    Returns clusters (lists of indices into ``texts``) with 2+ members.
    """
    grams = [trigrams(t) if len(normalize(t)) >= min_len else set() for t in texts]
    index: Dict[str, List[int]] = defaultdict(list)
    parent = list(range(len(texts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, g in enumerate(grams):
        if not g:
            continue
        shared: Counter = Counter()
        for gram in g:
            for j in index[gram]:
                shared[j] += 1
        for j, inter in shared.items():
            union = len(g) + len(grams[j]) - inter
            if union and inter / union >= threshold:
                parent[find(i)] = find(j)
        for gram in g:
            index[gram].append(i)

    groups: Dict[int, List[int]] = defaultdict(list)
    for i, g in enumerate(grams):
        if g:
            groups[find(i)].append(i)
    return [sorted(v) for v in groups.values() if len(v) >= 2]
