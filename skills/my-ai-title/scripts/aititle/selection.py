"""scores.json + metrics.json -> type, ability, quirk, rare (types.md rules).

Every numeric threshold below is provisional ("仮置き" in types.md). They are
gathered here so they can be tuned against real distributions later.

Condition strength ("倍率" in types.md) is value / threshold, so 1.0 means just
satisfied. Strengths are capped at RATIO_CAP so that conditions Claude judges
（判定） can compete with counts; ties at the cap are broken by the uncapped
value, then by table order.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .typesdb import AXES, Ability, Quirk, TypesDB

RATIO_CAP = 3.0
JUDGED_LEVEL = {"no": 0.0, "yes": 1.5, "strong": 3.0}

# Which axis decides which type (types.md "判定").
AXIS_TYPE = {
    "verification": "appraiser",
    "context": "architect",
    "systems": "alchemist",
    "efficiency": "sniper",
    "delegation": "commander",
    "autonomy": "commander",
}
DECIDING_AXES = {
    "appraiser": ("verification",),
    "architect": ("context",),
    "alchemist": ("systems",),
    "sniper": ("efficiency",),
    "commander": ("delegation", "autonomy"),
    "partner": (),
    "explorer": (),
    "conductor": AXES,
}
TIE_ORDER = ("appraiser", "architect", "alchemist", "sniper", "commander")

PARTNER_PROMPTS_PER_TASK = 6       # "1タスクあたりの往復が多い"
RARE_MIN_SESSIONS = 20             # per 30 days
GROWTH_STEP = 1                    # 急成長: an axis rose by this much
RARE_GROWTH = 2                    # explorer rare: an axis rose by this much


# --- condition primitives ------------------------------------------------------

@dataclass
class Ctx:
    metrics: dict
    scores: Dict[str, int]
    judgments: Dict[str, str]
    growth: Optional[Tuple[str, int]]   # (axis, delta) of the largest rise, if history exists

    @property
    def scale(self) -> float:
        days = self.metrics.get("period", {}).get("days") or 30
        return max(days, 1) / 30.0

    def value(self, key: str) -> Optional[float]:
        section, name = key.split(".")
        v = self.metrics.get(section, {}).get(name)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def at_least(key: str, threshold: float, per_month: bool = False):
    def f(c: Ctx) -> float:
        v = c.value(key)
        t = threshold * (c.scale if per_month else 1.0)
        return 0.0 if v is None or t <= 0 else v / t
    return f


def at_most(key: str, threshold: float):
    def f(c: Ctx) -> float:
        v = c.value(key)
        if v is None:
            return 0.0
        return RATIO_CAP if v <= 0 else threshold / v
    return f


def total(keys: Sequence[str], threshold: float, per_month: bool = True):
    def f(c: Ctx) -> float:
        vals = [c.value(k) for k in keys]
        if all(v is None for v in vals):
            return 0.0
        t = threshold * (c.scale if per_month else 1.0)
        return sum(v or 0.0 for v in vals) / t
    return f


def both(*conds):
    return lambda c: min(cond(c) for cond in conds)


def judged(name: str):
    return lambda c: JUDGED_LEVEL.get(str(c.judgments.get(name, "no")).lower(), 0.0)


def growth(step: int):
    return lambda c: 0.0 if not c.growth else max(c.growth[1], 0) / step


def all_axes_at_least(n: int):
    return lambda c: 1.0 if min(c.scores.values()) >= n else 0.0


# --- ability / quirk conditions (types.md "条件") ------------------------------

ABILITY_RULES = {
    # commander
    "pasture": at_least("autonomy.long_runs_completed", 20, per_month=True),
    "clone": total(["parallel.subagent_calls", "parallel.worktree_sessions"], 20),
    "fullpower": at_least("delegation.files_changed_per_prompt_mean", 1.5),
    "onevoice": at_least("delegation.short_and_wide_turn_share", 0.10),
    # appraiser
    "doubt": at_least("verification.verify_request_share", 0.10),
    "farsight": at_least("verification.visual_checks", 20, per_month=True),
    "ironwall": at_least("verification.test_runs", 30, per_month=True),
    "keeneye": judged("keeneye"),
    "multicheck": at_least("verification.methods_used", 3),
    # architect
    "foresight": at_least("context.plan_task_share", 0.20),
    "sage": at_least("context.memo_updates", 4, per_month=True),
    "lucid": judged("lucid"),
    "inquiry": judged("inquiry"),
    # alchemist
    "sloth": at_least("systems.patterns_gone_after_mechanism", 1),
    "hundredtools": at_least("systems.own_mechanism_calls", 15, per_month=True),
    "perpetual": total(["systems.hook_runs", "systems.automation_tool_calls"], 20),
    "massproduce": at_least("systems.mechanisms_created_used", 3),
    # sniper
    "bullseye": at_least("intervention.tasks_within_2_prompts_share", 0.50),
    "precision": judged("precision"),
    "flash": at_most("intervention.task_minutes_median", 10),
    "silence": at_least("intervention.short_prompt_share", 0.70),
    # partner
    "sparring": at_least("intervention.turns_per_session_median", 20),
    "discerning": judged("discerning"),
    "reverse": judged("reverse"),
    "monologue": judged("monologue"),
    # explorer
    "curious": at_least("breadth.distinct_tools", 12),
    "risingstar": growth(GROWTH_STEP),
    "tireless": at_least("data.active_day_share", 0.60),
    "pioneer": at_least("breadth.new_tools_this_period", 3),
    # conductor
    "legion": both(at_least("parallel.sessions_with_parallel_share", 0.30),
                   at_most("verification.followup_fix_task_share_est", 0.20)),
    "strategist": judged("strategist"),
    "flawless": all_axes_at_least(4),
}

QUIRK_RULES = {
    "afterthought": judged("afterthought"),
    "oral": at_least("systems.repeated_long_prompts", 5, per_month=True),
    "micromanage": at_most("delegation.tool_calls_per_prompt_median", 2),
    "hoarder": at_least("delegation.human_edits", 20, per_month=True),
    "gullible": at_most("verification.verified_task_share", 0.50),
    "lasteye": at_least("verification.followup_fix_task_share_est", 0.15),
    "hover": at_least("autonomy.mid_run_messages", 20, per_month=True),
    "stopper": at_least("autonomy.interrupts", 10, per_month=True),
    "marathon": at_least("intervention.prompts_per_task_median", PARTNER_PROMPTS_PER_TASK),
    "uturn": judged("uturn"),
    "handwritten": at_least("systems.repeated_prompts", 10, per_month=True),
    "sleeping": at_least("systems.own_mechanisms_unused", 3),
}

# Judgments Claude must make (written to scores.json "judgments").
JUDGMENTS = {
    "keeneye": "The human points out AI mistakes and is usually right (appraiser).",
    "lucid": "Tasks keep finishing without rework caused by missing information (architect).",
    "inquiry": "Many tasks hand over the symptom and let the AI investigate instead of assuming a cause (architect).",
    "precision": "Requests usually state completion criteria (sniper).",
    "discerning": "Many sessions compare several options before deciding (partner).",
    "reverse": "Many tasks start by letting the AI ask questions first (partner).",
    "monologue": "The human often finds the answer while explaining to the AI (partner).",
    "strategist": "Delegation style changes with the nature of the task (conductor).",
    "afterthought": "Rework caused by details added after the request (context quirk).",
    "uturn": "Many tasks change direction midway (efficiency quirk).",
    "partner_adopted": "In long back-and-forth sessions, the results end up adopted (partner type).",
    "partner_compare_many": "Comparing several options in brainstorming happens in many sessions, about 10+ a month (partner rare).",
}


def _rare_achievements(c: Ctx) -> Dict[str, bool]:
    s = c.scale
    v = lambda k: c.value(k) or 0.0  # noqa: E731
    return {
        "commander": v("autonomy.long_runs_completed") >= 10 * s,
        "appraiser": c.value("verification.followup_fix_prompts_est") == 0 and v("verification.methods_used") >= 3,
        "architect": v("intervention.max_clean_task_streak") >= 15,
        "alchemist": v("systems.own_mechanism_calls") >= 20 * s,
        "sniper": v("intervention.tasks_within_2_prompts_no_rework") >= 10 * s,
        "partner": judged("partner_compare_many")(c) >= 1.0,
        "explorer": bool(c.growth) and c.growth[1] >= RARE_GROWTH,
    }


# --- selection -------------------------------------------------------------------

def _rank_key(ratio: float, order: int) -> Tuple[float, float, int]:
    return (min(ratio, RATIO_CAP), ratio, -order)


def best_ability(db: TypesDB, type_id: str, c: Ctx) -> Tuple[Ability, float]:
    abilities = db.types[type_id].abilities
    scored = [(a, ABILITY_RULES[a.id](c), i) for i, a in enumerate(abilities)]
    ok = [x for x in scored if x[1] >= 1.0]
    if not ok:
        return abilities[0], 0.0
    a, r, _ = max(ok, key=lambda x: _rank_key(x[1], x[2]))
    return a, r


def choose_type(db: TypesDB, c: Ctx) -> str:
    sc = c.scores
    if min(sc.values()) >= 4:
        return "conductor"
    if sum(sc.values()) / len(sc) < 3:
        return "explorer"
    top = max(sc.values())
    tops = [a for a in AXES if sc[a] == top]
    partner_style = (at_least("intervention.prompts_per_task_median", PARTNER_PROMPTS_PER_TASK)(c) >= 1.0
                     and judged("partner_adopted")(c) >= 1.0)
    if partner_style and (top <= 3 or len(tops) >= 3):
        return "partner"
    candidates = []
    for a in tops:
        t = AXIS_TYPE[a]
        if t not in candidates:
            candidates.append(t)
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda t: _rank_key(best_ability(db, t, c)[1], TIE_ORDER.index(t)))


def choose_quirk(db: TypesDB, type_id: str, c: Ctx) -> Optional[Quirk]:
    """None means: use the type's surplus quirk (余裕のクセ)."""
    sc = c.scores
    if min(sc.values()) >= 4:
        return None
    axes = [a for a in AXES if a not in DECIDING_AXES[type_id]]
    low = min(sc[a] for a in axes)

    def best(axis: str) -> Tuple[Quirk, float]:
        qs = db.quirks_for(axis)
        scored = [(q, QUIRK_RULES[q.id](c), i) for i, q in enumerate(qs)]
        q, r, _ = max(scored, key=lambda x: _rank_key(x[1], x[2]))
        return q, r

    lowest = [a for a in axes if sc[a] == low]
    picks = [(best(a), AXES.index(a)) for a in lowest]
    (q, _r), _ = max(picks, key=lambda x: _rank_key(x[0][1], x[1]))
    return q


def is_rare(type_id: str, c: Ctx) -> bool:
    sessions = c.value("data.sessions") or 0
    if sessions < math.ceil(RARE_MIN_SESSIONS * c.scale):
        return False
    deciding = DECIDING_AXES[type_id]
    if type_id not in ("explorer", "partner", "conductor") and any(c.scores[a] != 5 for a in deciding):
        return False
    ach = _rare_achievements(c)
    if type_id == "conductor":
        return min(c.scores.values()) >= 4 and sum(ach.values()) >= 2
    return ach[type_id]


@dataclass
class Selection:
    type: str
    ability: Ability
    ability_ratio: float
    quirk: Optional[Quirk]
    rare: bool
    growth_axis: Optional[str]


def select(db: TypesDB, c: Ctx) -> Selection:
    t = choose_type(db, c)
    ability, ratio = best_ability(db, t, c)
    return Selection(type=t, ability=ability, ability_ratio=ratio, quirk=choose_quirk(db, t, c),
                     rare=is_rare(t, c), growth_axis=c.growth[0] if c.growth else None)


def validate_scores(scores: dict) -> Dict[str, int]:
    out = {}
    for a in AXES:
        v = scores.get(a)
        if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 5:
            raise ValueError(f"scores.{a} must be an integer from 1 to 5 (got {v!r})")
        out[a] = v
    return out


def largest_growth(now: Dict[str, int], prev: Optional[Dict[str, int]]) -> Optional[Tuple[str, int]]:
    if not prev:
        return None
    deltas = [(now[a] - int(prev.get(a, now[a])), -i, a) for i, a in enumerate(AXES)]
    d, _, a = max(deltas)
    return (a, d)


def list_judgments() -> List[str]:
    return list(JUDGMENTS)
