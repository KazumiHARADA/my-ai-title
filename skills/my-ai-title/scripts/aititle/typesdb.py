"""Load card wording from references/types.md (the source of truth).

The Markdown tables are parsed at run time so that wording changes only ever
happen in types.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

AXES = ("context", "delegation", "verification", "autonomy", "efficiency", "systems")
TYPES = ("commander", "appraiser", "architect", "alchemist", "sniper", "partner", "explorer", "conductor")


@dataclass
class Ability:
    type: str
    id: str
    no: int
    name: Dict[str, str]
    epithet: Dict[str, str]
    rare_epithet: Dict[str, str]
    quote: Dict[str, str]
    rare_quote: Dict[str, str]
    why: Dict[str, str]


@dataclass
class TypeInfo:
    id: str
    role: Dict[str, str]
    color: str
    surplus_quirk: Dict[str, str]
    abilities: List[Ability] = field(default_factory=list)


@dataclass
class Quirk:
    axis: str
    id: str
    name: Dict[str, str]
    why: Dict[str, str]


@dataclass
class TypesDB:
    types: Dict[str, TypeInfo]
    quirks: List[Quirk]
    axis_names: Dict[str, Dict[str, str]]

    def ability(self, ability_id: str) -> Ability:
        for t in self.types.values():
            for a in t.abilities:
                if a.id == ability_id:
                    return a
        raise KeyError(ability_id)

    def quirks_for(self, axis: str) -> List[Quirk]:
        return [q for q in self.quirks if q.axis == axis]


def _rows(lines: List[str]) -> List[List[str]]:
    out = []
    for line in lines:
        s = line.strip()
        if not s.startswith("|") or re.match(r"^\|[\s:|-]+\|$", s):
            continue
        out.append([c.strip() for c in s.strip("|").split("|")])
    return out


def _table_after(lines: List[str], start: int) -> List[List[str]]:
    """Rows of the first table at or after ``start`` (header row included)."""
    i = start
    while i < len(lines) and not lines[i].strip().startswith("|"):
        i += 1
    j = i
    while j < len(lines) and lines[j].strip().startswith("|"):
        j += 1
    return _rows(lines[i:j])


def _find(lines: List[str], pattern: str, start: int = 0) -> int:
    rx = re.compile(pattern)
    for i in range(start, len(lines)):
        if rx.search(lines[i]):
            return i
    raise ValueError(f"types.md: section not found: {pattern}")


def _no_suffix(s: str) -> str:
    return s[:-1] if s.endswith("の") else s


def _unquote(s: str) -> str:
    return s[1:-1] if s.startswith("「") and s.endswith("」") else s


def load(path: Optional[Path] = None) -> TypesDB:
    path = path or Path(__file__).resolve().parents[2] / "references" / "types.md"
    lines = path.read_text(encoding="utf-8").splitlines()

    # English tables (also define IDs and card order)
    en_types = {r[0]: r for r in _table_after(lines, _find(lines, r"^### タイプ"))[1:]}
    en_abilities = _table_after(lines, _find(lines, r"^### 技名"))[1:]
    en_axes = _table_after(lines, _find(lines, r"^### 軸"))[1:]
    en_quirks = _table_after(lines, _find(lines, r"^### クセ$"))[1:]

    types: Dict[str, TypeInfo] = {}
    for t in TYPES:
        head = _find(lines, rf"^## {t}：")
        nxt = next((i for i in range(head + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        block = lines[head:nxt]
        color = re.search(r"#[0-9A-Fa-f]{6}", next(x for x in block if "テーマカラー" in x)).group(0)
        surplus = next(x for x in block if x.startswith("- 余裕のクセ")).split("：", 1)[1].strip()
        en = en_types[t]
        info = TypeInfo(id=t, role={"ja": en[1], "en": en[2]}, color=color,
                        surplus_quirk={"ja": surplus, "en": en[3]})
        ja_rows = {r[0]: r for r in _table_after(block, 0)[1:]}
        for r in en_abilities:
            if r[0] != t:
                continue
            ja = ja_rows[r[2]]
            # ja: 技名 二つ名 英語 レア二つ名 レア英語 セリフ レアセリフ 条件 根拠の文
            info.abilities.append(Ability(
                type=t, id=r[1], no=0,
                name={"ja": ja[0], "en": r[3]},
                epithet={"ja": _no_suffix(ja[1]), "en": ja[2]},
                rare_epithet={"ja": _no_suffix(ja[3]), "en": ja[4]},
                quote={"ja": _unquote(ja[5]), "en": r[4]},
                rare_quote={"ja": _unquote(ja[6]), "en": r[5]},
                why={"ja": ja[8], "en": r[6]},
            ))
        types[t] = info

    no = 0
    for r in en_abilities:
        no += 1
        for a in types[r[0]].abilities:
            if a.id == r[1]:
                a.no = no

    ja_quirks = {r[1]: r for r in _table_after(lines, _find(lines, r"^## クセのパターン"))[1:]}
    quirks = []
    for r in en_quirks:
        ja = ja_quirks[r[2]]
        quirks.append(Quirk(axis=r[0], id=r[1], name={"ja": r[2], "en": r[3]}, why={"ja": ja[3], "en": r[4]}))

    axis_names = {r[0]: {"ja": r[1], "en": r[2]} for r in en_axes}
    return TypesDB(types=types, quirks=quirks, axis_names=axis_names)
