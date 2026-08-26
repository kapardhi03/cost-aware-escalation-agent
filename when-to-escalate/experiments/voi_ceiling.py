"""
voi_ceiling.py — can `ask` ever be worth its price under this cost matrix?

Gate 1 of v2 defines the value of information of a question as

    V_act(b) = min over the feasible NON-ask actions of EC(a | b)
    V_q(b)   = sum_u P_b(u) * V_act(b^u)          one-question lookahead
    VoI(q|b) = V_act(b) - [ EC(ask | b) + V_q(b) ]

Every cost in the matrix is non-negative, so V_q(b) >= 0, so

    VoI(q | b) <= V_act(b) - EC(ask | b)                             (*)

The right-hand side mentions no question and no answer model. It is what VoI
would be if an oracle answered perfectly and for free. So (*) is a CEILING on the
value of asking that can be evaluated without building an answer model at all,
and if it is negative then no answer model can rescue `ask`.

This script evaluates (*) and writes the result to results/. It is offline and
deterministic: it reads results/run.json and src/costs.py and touches no provider.
It never writes to costs.COST — the lambda re-pricing below is computed on a local
copy, because changing the matrix would reopen a locked v1 decision.

  per_case              (*) on the 100 committed beliefs, respecting each case's
                        hard constraints, since `no_direct_answer` removes
                        `answer` from the non-ask menu and therefore RAISES V_act.
  global_ceiling        the maximum of (*) over EVERY belief, not just these 100,
                        in closed form with exact rational arithmetic.
  witness_crosscheck    the same maximum re-evaluated through src/costs.py's own
                        expected_cost, so the derivation is checked against the
                        code the paper's numbers come from.
  grid_crosscheck       a deliberately dumb numeric search over the same domain,
                        which must never exceed the closed form.
  constrained_regime    the maximum on the menu `no_direct_answer` leaves, where
                        the ceiling CAN be positive — so the impossibility is
                        unconditional only on the unconstrained menu.
  feasibility           the condition on `ask`'s two cost values under which (*)
                        can be positive at all, and the uniform scaling factor
                        lambda that would flip this matrix.
  lambda_crosscheck     that lambda again, by bisection instead of algebra.
  invariants            the algebraic identities Gate 1 asserts, on real data.

The closed form rests on one structural fact about this matrix: `answer`,
`escalate_notify` and `ask` are all FLAT in readiness, so on the unconstrained
menu V_act(b) is capped by two functions of b_h alone and the readiness
distribution cannot help. That is why an exact answer is available here and the
grid search is only a cross-check. The flatness and the two monotonicity side
conditions are asserted, not assumed, so a future matrix edit fails loudly rather
than returning a quietly wrong optimum.

Belief arms (Gate 4). `--arm` selects which beliefs the belief-dependent halves
read. The four arms mirror experiments/rebaseline.py exactly, so a contrast means
the same thing in both artifacts and each one varies a single thing:

  published     v1's cache, i.e. results/run.json. The default, and the only arm
                whose output is pinned: it must reproduce results/voi-ceiling.json
                byte for byte, which tests/test_voi_ceiling_arms.py asserts.
  rebaselined   fresh readiness and the fresh WRITTEN digit. Against `published`
                this isolates cache drift.
  raw           fresh readiness, continuous logprob expectation for needs_human.
                Against `rebaselined` this isolates continuity.
  calibrated    the same, through the committed isotonic map. Against `raw` this
                isolates the map.

Only `per_case` and `constrained_regime`'s two case-level fields are
belief-dependent. `global_ceiling`, `witness_crosscheck`, `grid_crosscheck`,
`feasibility`, `lambda_crosscheck` and `constrained_regime`'s maximum are maxima
over the whole simplex in exact rational arithmetic, so no arm can move them —
see decisions/v2-gate4-preregistration.md section 4, which also says why that makes
the unconstrained-menu result analytic rather than empirical.

Usage
    python experiments/voi_ceiling.py
    python experiments/voi_ceiling.py --json results/voi-ceiling.json
    python experiments/voi_ceiling.py --arm calibrated
"""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.belief import Belief, to_belief                          # noqa: E402
from src.costs import (ACTIONS, COST, READINESS_LABELS,            # noqa: E402
                       expected_cost, feasible_actions)
import src.calibrate as calib                                     # noqa: E402
import src.elicit as elicit_mod                                   # noqa: E402

RUN_JSON = ROOT / "results" / "run.json"
CASES_JSON = ROOT / "data" / "cases.json"
ELICIT_JSON = ROOT / "results" / "logprob-elicitation.json"

#: Actions that compete with `ask`. `ask` is excluded from its own baseline: the
#: myopic V(b) already prices `ask` as a terminal action, so measuring the ask
#: branch against V(b) double-counts and makes VoI <= 0 for ANY matrix. That
#: mistake was made and caught while drafting the definitions; the exclusion here
#: is the fix, and check_invariants() pins it.
NONASK = tuple(a for a in ACTIONS if a != "ask")


def load_rows() -> tuple[list[dict], dict]:
    payload = json.loads(RUN_JSON.read_text())
    return payload["rows"], payload


def belief_of(row: dict) -> Belief:
    return Belief.from_dict(row["belief"])


# --------------------------------------------------------------------------- #
# 0. Belief arms
# --------------------------------------------------------------------------- #

#: The four belief sources, in the order experiments/rebaseline.py established.
#: `published` is first because it is the default and the only arm pinned to a
#: committed file.
ARMS = ("published", "rebaselined", "raw", "calibrated")

#: What each arm reads, recorded in the artifact's `source` field so a findings
#: file always names the beliefs it was computed on. `published` deliberately keeps
#: Gate 1's exact string, because changing it would break byte-reproduction.
ARM_SOURCES = {
    "published": "results/run.json",
    "rebaselined": "data/logprob_cache.json written digit + fresh readiness",
    "raw": "results/logprob-elicitation.json raw + fresh readiness",
    "calibrated": "results/logprob-elicitation.json calibrated + fresh readiness",
}


class ArmError(RuntimeError):
    """An arm could not be built. Never downgraded to a warning, because a
    silently short arm would compare 97 cases against 100 and look fine."""


def _load_elicitation() -> dict:
    """The committed Gate 2 results, with Gate 2's own provenance guards.

    Same two refusals as experiments/rebaseline.py: a not-reportable file or one
    with stub rows would produce numbers that look like measurements and are not.
    """
    if not ELICIT_JSON.exists():
        raise ArmError(
            f"{ELICIT_JSON.name} is absent. It is a committed Gate 2 artifact; "
            "this script never calls a provider to rebuild it.")
    payload = json.loads(ELICIT_JSON.read_text(encoding="utf-8"))
    if not payload.get("reportable"):
        raise ArmError(f"{ELICIT_JSON.name} is marked not reportable "
                       f"({payload.get('stub_rows')} stub rows).")
    if payload.get("stub_rows"):
        raise ArmError(f"{ELICIT_JSON.name} contains "
                       f"{payload['stub_rows']} stub rows.")
    return payload


def _fresh_beliefs() -> dict:
    """Fresh readiness and the fresh written digit, per case.

    Parses each elicitor-A payload back through `belief.to_belief` — v1's own
    parser on v1's own JSON shape — so the readiness vector here is what v1 would
    have recorded had it run today, not a reimplementation of its parsing.
    """
    cache_path = elicit_mod.logprob_cache_path()
    if not cache_path.exists():
        raise ArmError(f"{cache_path} is absent; this script reads the cache and "
                       "never calls a provider.")
    cache = elicit_mod.load_cache(cache_path)
    out = {}
    for entry in cache["entries"].values():
        if entry["elicitor"] != elicit_mod.ELICITOR_A:
            continue
        b = to_belief(json.loads(entry["payload"]["text"]))
        out[entry["case_id"]] = {"readiness": b.readiness,
                                 "written": b.needs_human}
    return out


def _committed_scores(payload: dict) -> dict:
    """The raw and calibrated scores Gate 2 committed, verified against the map.

    The scores are read rather than recomputed — refitting would be a second fit
    and a second chance to land elsewhere. But the stored knots and the stored
    scores are two records of one thing, so they are checked against each other,
    and the map's floor is checked to be what the knots say it is. Those are two
    of the four falsifiers in the Gate 4 pre-registration section 3.4.
    """
    cal = payload["analysis"]["calibration"]
    spec = cal["map"]
    if spec["name"] != "isotonic":
        raise ArmError(f"the committed map is {spec['name']!r}, not isotonic; the "
                       "floor argument in the pre-registration assumes isotonic")
    mapping = calib.IsotonicMap(knots=tuple(tuple(k) for k in spec["knots"]))
    floor = spec["knots"][0][1]

    scores = payload["analysis"]["recalibrated_scores"]
    worst, worst_case = 0.0, None
    for case_id, rec in scores.items():
        delta = abs(calib.apply_map(mapping, [rec["raw"]])[0] - rec["calibrated"])
        if delta > worst:
            worst, worst_case = delta, case_id
        if rec["calibrated"] < floor:
            raise ArmError(
                f"{case_id} has a calibrated score {rec['calibrated']!r} below the "
                f"map's floor {floor!r}. The map cannot produce that, so one of the "
                "two records is stale.")
    if worst > 1e-12:
        raise ArmError(
            f"the committed knots do not reproduce the committed calibrated scores "
            f"(worst delta {worst:.3e} at {worst_case}); one of them is stale.")
    return scores


def load_arm(name: str) -> tuple[list[dict], str]:
    """Rows in run.json's shape for one arm, plus the source string.

    Every arm carries all 100 cases and both splits. Stratification happens at
    reporting time, not here, so an arm can never be quietly narrowed to the split
    that suits it.
    """
    if name not in ARMS:
        raise ArmError(f"unknown arm {name!r}; expected one of {ARMS}")
    if name == "published":
        rows, _ = load_rows()
        return rows, ARM_SOURCES["published"]

    payload = _load_elicitation()
    fresh = _fresh_beliefs()
    scores = _committed_scores(payload)
    cases = json.loads(CASES_JSON.read_text(encoding="utf-8"))["cases"]

    rows = []
    for case in cases:
        case_id = case["case_id"]
        if case_id not in fresh:
            raise ArmError(f"{case_id} has no {elicit_mod.ELICITOR_A} payload in "
                           "the logprob cache")
        if name != "rebaselined" and case_id not in scores:
            raise ArmError(f"{case_id} has no recalibrated score in "
                           f"{ELICIT_JSON.name}")
        needs_human = (fresh[case_id]["written"] if name == "rebaselined"
                       else scores[case_id]["raw"] if name == "raw"
                       else scores[case_id]["calibrated"])
        rows.append({
            "case_id": case_id,
            "split": case["split"],
            "constraints": list(case.get("constraints") or ()),
            "labels": case["labels"],
            "belief": {"readiness": dict(fresh[case_id]["readiness"]),
                       "needs_human": needs_human},
        })

    if len(rows) != len(cases):
        raise ArmError(f"arm {name!r} built {len(rows)} rows from {len(cases)} cases")
    return rows, ARM_SOURCES[name]


# --------------------------------------------------------------------------- #
# Exact matrix reading
# --------------------------------------------------------------------------- #

def _flat_in_readiness(action: str, needs_human: bool) -> Fraction:
    """The cost of `action` in the given needs_human half, asserting it is the
    same for all three readiness states.

    Three of the five actions are readiness-flat and the closed form below
    depends on it, so this raises rather than silently averaging.
    """
    values = {Fraction(COST[action][(r, needs_human)]).limit_denominator()
              for r in READINESS_LABELS}
    if len(values) != 1:
        raise ValueError(
            f"{action} at needs_human={needs_human} is not flat in readiness: "
            f"{sorted(values)}; the closed form in global_ceiling() assumes it is")
    return values.pop()


def matrix_constants() -> dict:
    """The four numbers the closed form needs, read out of COST rather than typed.

    alpha  cost of `answer` when a human WAS needed        (the false assertion)
    nu     cost of `escalate_notify` when one was NOT      (the needless escalation)
    ask_F  cost of `ask` when no human is needed
    ask_T  cost of `ask` when one is
    """
    return {
        "alpha": _flat_in_readiness("answer", True),
        "answer_when_fine": _flat_in_readiness("answer", False),
        "nu": _flat_in_readiness("escalate_notify", False),
        "notify_when_needed": _flat_in_readiness("escalate_notify", True),
        "ask_F": _flat_in_readiness("ask", False),
        "ask_T": _flat_in_readiness("ask", True),
    }


# --------------------------------------------------------------------------- #
# 1. The ceiling on the 100 committed beliefs
# --------------------------------------------------------------------------- #

def check_per_case(rows: list[dict]) -> dict:
    """(*) evaluated on each committed belief, with that case's constraints applied.

    Constraints matter and are easy to miss. `no_direct_answer` removes `answer`
    from the non-ask menu, which can only RAISE V_act and therefore raise the
    ceiling. Ignoring them would understate the value of asking on exactly the
    cases where asking is most plausible.
    """
    out = []
    for row in rows:
        b = belief_of(row)
        constraints = tuple(row.get("constraints") or ())
        feasible = feasible_actions(constraints)
        nonask = [a for a in feasible if a != "ask"]

        ec = {a: expected_cost(a, b) for a in ACTIONS}
        v_act = min(ec[a] for a in nonask)
        v_all = min(ec[a] for a in feasible)
        out.append({
            "case_id": row["case_id"],
            "split": row["split"],
            "constraints": list(constraints),
            "b_h": b.needs_human,
            "v_act": v_act,
            "ec_ask": ec["ask"],
            "ceiling": v_act - ec["ask"],
            "v_act_argmin": min(nonask, key=lambda a: ec[a]),
            "ask_is_myopic_argmin": v_all < v_act - 1e-12,
        })

    ceilings = [c["ceiling"] for c in out]
    positive = [c for c in out if c["ceiling"] > 0]
    best = max(ceilings)
    tied = sorted(c["case_id"] for c in out if abs(c["ceiling"] - best) < 1e-12)
    constrained = [c for c in out if c["constraints"]]
    return {
        "n": len(out),
        "n_positive_ceiling": len(positive),
        "max_ceiling": best,
        "min_ceiling": min(ceilings),
        "n_at_max_ceiling": len(tied),
        "cases_at_max_ceiling": tied,
        "n_constrained_cases": len(constrained),
        "constrained_case_ids": [c["case_id"] for c in constrained],
        "max_ceiling_among_constrained": (max(c["ceiling"] for c in constrained)
                                          if constrained else None),
        "min_b_h_among_constrained": (min(c["b_h"] for c in constrained)
                                      if constrained else None),
        "anchor_case": next(({k: c[k] for k in ("case_id", "ceiling", "v_act",
                                                "ec_ask", "b_h", "v_act_argmin")}
                             for c in out if c["case_id"] == "a02-deep-018"), None),
        "per_case": out,
    }


# --------------------------------------------------------------------------- #
# 2. The maximum of (*) over every belief there is
# --------------------------------------------------------------------------- #

def _ec_ask_at(t: Fraction, ask_F: Fraction, ask_T: Fraction) -> Fraction:
    """EC(ask | b) as a function of b_h alone — `ask` is readiness-flat."""
    return ask_F + (ask_T - ask_F) * t


def _cost_at(action: str, readiness: str, t: Fraction) -> Fraction:
    lo = Fraction(COST[action][(readiness, False)]).limit_denominator()
    hi = Fraction(COST[action][(readiness, True)]).limit_denominator()
    return lo + (hi - lo) * t


def check_global_ceiling(k: dict) -> dict:
    """max over ALL beliefs of V_act(b) - EC(ask | b), exactly.

    The argument, on the unconstrained menu:

    1. `answer` and `escalate_notify` are both in the non-ask menu and both flat
       in readiness, so for every belief
           V_act(b) <= min( alpha*t , nu*(1-t) )        where t = b_h
       and the readiness distribution cannot raise that cap at all.
    2. `ask` is also flat in readiness, so
           V_act(b) - EC(ask|b) <= u(t) = min(alpha*t, nu*(1-t)) - EC(ask|t)
       a function of t alone. u rises on t <= t* and falls on t >= t*, where
       t* = nu/(alpha+nu) is the answer/notify crossover, so
           max_t u(t) = u(t*) = alpha*nu/(alpha+nu) - EC(ask|t*)
       The two monotonicity conditions are -nu < ask_T - ask_F < alpha; both are
       asserted below rather than assumed.
    3. The bound is ATTAINED, so it is the maximum and not merely a bound: at
       t = t* pick the pure readiness state whose `hold` and `escalate_pause`
       costs both exceed the cap, and V_act equals the cap exactly.
    """
    alpha, nu = k["alpha"], k["nu"]
    ask_F, ask_T = k["ask_F"], k["ask_T"]

    slope = ask_T - ask_F
    monotone_rising = slope < alpha            # left branch of u increases
    monotone_falling = slope > -nu             # right branch decreases

    t_star = nu / (alpha + nu)
    cap = alpha * nu / (alpha + nu)            # = alpha*t* = nu*(1-t*)
    ec_ask_star = _ec_ask_at(t_star, ask_F, ask_T)
    ceiling = cap - ec_ask_star

    # A witness belief attaining it: a pure readiness state where the two
    # readiness-dependent actions are both more expensive than the cap.
    witness = None
    for r in READINESS_LABELS:
        hold = _cost_at("hold", r, t_star)
        pause = _cost_at("escalate_pause", r, t_star)
        if min(hold, pause) >= cap:
            witness = {"readiness": {rr: (1 if rr == r else 0)
                                     for rr in READINESS_LABELS},
                       "b_h": str(t_star),
                       "hold_cost": str(hold), "pause_cost": str(pause),
                       "v_act": str(cap), "ec_ask": str(ec_ask_star)}
            break

    return {
        "alpha_false_assertion": str(alpha),
        "nu_needless_escalation": str(nu),
        "ask_F": str(ask_F), "ask_T": str(ask_T),
        "t_star_exact": str(t_star), "t_star_float": float(t_star),
        "max_v_act_exact": str(cap), "max_v_act_float": float(cap),
        "ec_ask_at_t_star_exact": str(ec_ask_star),
        "ec_ask_range": [str(ask_F), str(ask_T)],
        "ceiling_exact": str(ceiling),
        "ceiling_float": float(ceiling),
        "ask_can_ever_be_rational": ceiling > 0,
        "monotonicity_left_branch_rises": monotone_rising,
        "monotonicity_right_branch_falls": monotone_falling,
        "closed_form_valid": monotone_rising and monotone_falling,
        "witness_belief": witness,
        "bound_is_attained": witness is not None,
    }


#: Decimals the grid's argmax is decided at, and the width of the plateau it reports.
#: The maximum is attained on a large flat region, not at a point, so a bit-exact `>`
#: comparison picks whichever member of it float noise happened to put first — and
#: CPython 3.12's compensated `sum()` changes that. Rounding first makes the plateau
#: interpreter-independent; the tie-break below picks from it deterministically.
GRID_DECIMALS = 12

GRID_TIE_BREAK = ("lowest (hot, warm, b_h) among the maximisers at "
                  f"{GRID_DECIMALS} decimals")


def grid_crosscheck(k: dict, n: int = 60) -> dict:
    """An independent numeric search, to catch an error in the closed form.

    Deliberately dumb: a uniform grid over the readiness simplex and b_h, in
    floats, with no reference to the derivation above. It should never EXCEED the
    closed-form value, and should come close to it.

    It does not have a unique argmax, and an earlier version of this function
    implied one. The maximum is attained along a flat region — 1185 of the grid's
    points at `n = 60` — because `min_a EC(a | b) - EC(ask | b)` is linear in the
    belief and the same pair of actions is active across a whole face. Reporting one
    point as *the* argmax was slightly false even before it became unstable: the
    plateau size is reported alongside it now, and the point is the lexicographically
    lowest member rather than whichever one the interpreter reached first.
    """
    step = 1.0 / n
    best_rounded = -float("inf")
    best: tuple[float, dict] | None = None
    n_at_max = 0
    n_points = 0
    for i in range(n + 1):
        for j in range(n + 1 - i):
            hot, warm = i * step, j * step
            cold = max(0.0, 1.0 - hot - warm)
            for m in range(n + 1):
                t = m * step
                p = {"hot": hot, "warm": warm, "cold": cold}
                ec = {}
                for a in ACTIONS:
                    ec[a] = sum(p[r] * ((1 - t) * COST[a][(r, False)]
                                        + t * COST[a][(r, True)])
                                for r in READINESS_LABELS)
                value = min(ec[a] for a in NONASK) - ec["ask"]
                n_points += 1
                rounded = round(value, GRID_DECIMALS)
                if rounded > best_rounded:
                    # The loops ascend in (hot, warm, b_h), so the first member of a
                    # plateau reached is its lexicographically lowest point.
                    best_rounded = rounded
                    best = (value, {"readiness": {kk: round(vv, 4)
                                                  for kk, vv in p.items()},
                                    "b_h": round(t, 4)})
                    n_at_max = 1
                elif rounded == best_rounded:
                    n_at_max += 1
    exact = float(Fraction(k["ceiling_exact"]))
    return {
        "grid_steps_per_axis": n,
        "grid_points_searched": n_points,
        "grid_max": best[0],
        "grid_argmax": best[1],
        "grid_argmax_tie_break": GRID_TIE_BREAK,
        "n_grid_points_attaining_the_max": n_at_max,
        "grid_argmax_is_unique": n_at_max == 1,
        "closed_form_max": exact,
        "grid_exceeds_closed_form": best[0] > exact + 1e-9,
        "gap_to_closed_form": exact - best[0],
    }


def witness_crosscheck(glob: dict) -> dict:
    """Re-evaluate the witness belief through src/costs.py itself.

    The closed form and the grid both reimplement the expected-cost arithmetic
    inside this file. This one does not: it builds a real `Belief` and calls the
    same `expected_cost` the policy uses, so it catches a disagreement between the
    derivation and the code the paper's numbers actually come from.
    """
    w = glob.get("witness_belief")
    if not w:
        return {"ran": False, "reason": "no witness belief was found"}
    t = float(Fraction(w["b_h"]))
    b = Belief(readiness={r: float(w["readiness"][r]) for r in READINESS_LABELS},
               needs_human=t)
    ec = {a: expected_cost(a, b) for a in ACTIONS}
    v_act = min(ec[a] for a in NONASK)
    ceiling = v_act - ec["ask"]
    expected = float(Fraction(glob["ceiling_exact"]))
    return {
        "ran": True,
        "belief": b.to_dict(),
        "expected_cost_per_action": ec,
        "v_act_via_src_costs": v_act,
        "ec_ask_via_src_costs": ec["ask"],
        "ceiling_via_src_costs": ceiling,
        "closed_form_ceiling": expected,
        "agree_to_1e_9": abs(ceiling - expected) < 1e-9,
    }


def check_constrained_regime(k: dict, rows: list[dict]) -> dict:
    """The same maximum, but on the menu `no_direct_answer` leaves behind.

    Worth separating, because removing `answer` removes the alpha*t half of the cap
    on V_act. The ceiling is then governed by `escalate_notify` against `hold` and
    `escalate_pause`, and it CAN be positive: asking beats a needless escalation
    when the lead is hot and a human probably is not needed. So the impossibility
    is unconditional only on the unconstrained menu.

    Whether that positive region is ever reached is a separate, empirical question,
    so the minimum b_h among the cases that actually carry the constraint is
    reported next to the region's own b_h bound.
    """
    forbidden = {"answer"}
    menu = [a for a in NONASK if a not in forbidden]
    n = 200
    best = (-float("inf"), None)
    for m in range(n + 1):
        t = m / n
        # For fixed t every EC is linear in the readiness distribution, and we are
        # maximising a min of linear forms, so the optimum over the simplex sits at
        # a vertex or on a tie between two of them. Both families are enumerated, so
        # the value is exact at each grid point in t.
        rows_at_t = {a: {r: (1 - t) * COST[a][(r, False)] + t * COST[a][(r, True)]
                         for r in READINESS_LABELS} for a in ACTIONS}
        cands = [{r: 1.0 if r == rr else 0.0 for r in READINESS_LABELS}
                 for rr in READINESS_LABELS]
        for a1 in menu:
            for a2 in menu:
                if a1 >= a2:
                    continue
                for r1 in READINESS_LABELS:
                    for r2 in READINESS_LABELS:
                        if r1 == r2:
                            continue
                        d1 = rows_at_t[a1][r1] - rows_at_t[a2][r1]
                        d2 = rows_at_t[a1][r2] - rows_at_t[a2][r2]
                        if abs(d1 - d2) < 1e-12:
                            continue
                        w = d2 / (d2 - d1)          # mix of r1,r2 where a1 ties a2
                        if 0.0 <= w <= 1.0:
                            cands.append({r: (w if r == r1 else
                                              (1 - w) if r == r2 else 0.0)
                                          for r in READINESS_LABELS})
        for p in cands:
            ec = {a: sum(p[r] * rows_at_t[a][r] for r in READINESS_LABELS)
                  for a in ACTIONS}
            value = min(ec[a] for a in menu) - ec["ask"]
            if value > best[0]:
                best = (value, {"readiness": {kk: round(vv, 4) for kk, vv in p.items()},
                                "b_h": round(t, 4)})

    # The region exactly, along the ray the maximum sits on: a pure readiness state.
    # On that ray every cost is affine in t, so the boundary is a single rational.
    ray = best[1]["readiness"] if best[1] else None
    ray_label = (next((r for r, v in ray.items() if v > 0.999), None)
                 if ray else None)
    bound = None
    if ray_label is not None:
        lo = {a: Fraction(COST[a][(ray_label, False)]).limit_denominator()
              for a in ACTIONS}
        hi = {a: Fraction(COST[a][(ray_label, True)]).limit_denominator()
              for a in ACTIONS}
        # ceiling(t) = min_a in menu [lo_a + (hi_a - lo_a) t] - [lo_ask + (hi_ask-lo_ask) t]
        # Positive iff every menu action beats ask; the binding one gives the bound.
        crossings = []
        for a in menu:
            num = lo[a] - lo["ask"]
            den = (hi["ask"] - lo["ask"]) - (hi[a] - lo[a])
            if den == 0:
                crossings.append((a, None, num > 0))
                continue
            crossings.append((a, num / den, None))
        finite = [c for c in crossings if c[1] is not None and 0 <= c[1] <= 1]
        binding = min(finite, key=lambda c: c[1]) if finite else None
        bound = {
            "ray": ray_label,
            "per_action_crossing": {a: (str(x) if x is not None else "never")
                                    for a, x, _ in crossings},
            "binding_action": binding[0] if binding else None,
            "b_h_upper_bound_exact": str(binding[1]) if binding else None,
            "b_h_upper_bound_float": float(binding[1]) if binding else None,
        }

    real = [r for r in rows if r.get("constraints")]
    min_b_h = min((r["belief"]["needs_human"] for r in real), default=None)
    return {
        "menu": menu,
        "constraint": "no_direct_answer",
        "max_ceiling": best[0],
        "argmax": best[1],
        "ask_can_be_rational_under_this_constraint": best[0] > 0,
        "positive_region_on_the_argmax_ray": bound,
        "n_cases_carrying_the_constraint": len(real),
        "min_b_h_among_those_cases": min_b_h,
        "any_such_case_inside_the_region": (
            bound is not None and bound["b_h_upper_bound_float"] is not None
            and min_b_h is not None
            and min_b_h < bound["b_h_upper_bound_float"]),
        "grid_steps_b_h": n,
        "note": ("readiness optimum enumerated exactly at each b_h (vertices plus "
                 "pairwise ties); b_h itself on a grid, so max_ceiling is exact at "
                 "the grid points and a lower bound on the true supremum"),
    }


# --------------------------------------------------------------------------- #
# 3. What `ask` would have to cost
# --------------------------------------------------------------------------- #

def check_feasibility(k: dict) -> dict:
    """The condition on ask's price under which (*) can be positive, exactly.

    From check_global_ceiling, the ceiling is positive iff EC(ask|t*) < cap, i.e.

        ask_F + (ask_T - ask_F) * nu/(alpha+nu)  <  alpha*nu/(alpha+nu)

    Multiplying through by (alpha+nu):

        alpha*ask_F + nu*ask_T  <  alpha*nu

    and dividing by alpha*nu gives the readable form

        ask_F/nu + ask_T/alpha  <  1

    The price of a question, measured against a needless escalation when no human
    is needed and against a false assertion when one is, must sum to under one.
    Scaling ask's row uniformly by lambda, the break-even is
    lambda* = alpha*nu / (alpha*ask_F + nu*ask_T), the reciprocal of that sum.
    """
    alpha, nu = k["alpha"], k["nu"]
    ask_F, ask_T = k["ask_F"], k["ask_T"]

    lhs = alpha * ask_F + nu * ask_T
    rhs = alpha * nu
    ratio = ask_F / nu + ask_T / alpha
    lam = rhs / lhs if lhs != 0 else None

    return {
        "condition": "alpha*ask_F + nu*ask_T < alpha*nu",
        "readable_condition": "ask_F/nu + ask_T/alpha < 1",
        "lhs_exact": str(lhs), "rhs_exact": str(rhs),
        "satisfied": lhs < rhs,
        "ratio_exact": str(ratio), "ratio_float": float(ratio),
        "break_even_lambda_exact": str(lam),
        "break_even_lambda_float": float(lam),
        "repriced_ask_row": [str(ask_F * lam), str(ask_T * lam)],
        "repriced_ask_row_float": [float(ask_F * lam), float(ask_T * lam)],
        "required_reduction_exact": str(1 - lam),
        "required_reduction_pct": float((1 - lam) * 100),
    }


def lambda_crosscheck(k: dict, feas: dict, iterations: int = 60) -> dict:
    """Bisect for the break-even lambda numerically, ignoring the algebra above."""
    alpha, nu = float(k["alpha"]), float(k["nu"])
    ask_F, ask_T = float(k["ask_F"]), float(k["ask_T"])

    def ceiling(lam: float) -> float:
        t = nu / (alpha + nu)
        return min(alpha * t, nu * (1 - t)) - lam * (ask_F + (ask_T - ask_F) * t)

    lo, hi = 0.0, 2.0
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if ceiling(mid) > 0:
            lo = mid
        else:
            hi = mid
    exact = float(Fraction(feas["break_even_lambda_exact"]))
    return {
        "bisected_lambda": hi,
        "closed_form_lambda": exact,
        "agree_to_1e_9": abs(hi - exact) < 1e-9,
        "ceiling_at_lambda_1": ceiling(1.0),
    }


# --------------------------------------------------------------------------- #
# 4. The identities Gate 1 asserts
# --------------------------------------------------------------------------- #

def check_invariants(rows: list[dict], k: dict) -> dict:
    """Every algebraic claim the definitions make, checked against real beliefs."""
    ask_F, ask_T = float(k["ask_F"]), float(k["ask_T"])
    ec_ask_violations, v_act_violations, ask_argmin = [], [], []

    for row in rows:
        b = belief_of(row)
        constraints = tuple(row.get("constraints") or ())
        feasible = feasible_actions(constraints)
        ec = {a: expected_cost(a, b) for a in ACTIONS}

        predicted = ask_F + (ask_T - ask_F) * b.needs_human
        if abs(ec["ask"] - predicted) > 1e-12:
            ec_ask_violations.append(row["case_id"])

        nonask = [a for a in feasible if a != "ask"]
        v_act = min(ec[a] for a in nonask)
        v_all = min(ec[a] for a in feasible)
        if v_act < v_all - 1e-12:
            v_act_violations.append(row["case_id"])
        if v_all < v_act - 1e-12:
            ask_argmin.append(row["case_id"])

    return {
        "ec_ask_is_affine_in_b_h": {
            "claim": f"EC(ask|b) = {ask_F:g} + {ask_T - ask_F:g}*b_h, "
                     "independent of readiness",
            "violations": ec_ask_violations,
            "holds_on": f"{len(rows) - len(ec_ask_violations)}/{len(rows)}",
        },
        "v_act_at_least_v": {
            "claim": "V_act(b) >= V(b), since V_act minimises over a subset",
            "violations": v_act_violations,
            "holds_on": f"{len(rows) - len(v_act_violations)}/{len(rows)}",
        },
        "ask_never_myopic_argmin": {
            "claim": "V_act(b) == V(b) on every case, i.e. `ask` is never chosen "
                     "— the cross-check on run.json's action census",
            "cases_where_ask_would_be_chosen": ask_argmin,
            "holds_on": f"{len(rows) - len(ask_argmin)}/{len(rows)}",
        },
    }


# --------------------------------------------------------------------------- #

def build_findings(rows: list[dict], source: str, grid: int = 60) -> dict:
    """Every check, on one arm's beliefs. The key order is load-bearing.

    `results/voi-ceiling.json` was written by json.dumps on this dict, and the
    `published` arm has to reproduce that file byte for byte, so reordering these
    keys or renaming one would break the guard in tests/test_voi_ceiling_arms.py.
    That is deliberate: it is what makes "the arms are a superset of Gate 1, not a
    revision of it" a checkable claim rather than a promise.
    """
    k = matrix_constants()
    glob = check_global_ceiling(k)
    feas = check_feasibility(k)
    return {
        "n_cases": len(rows),
        "source": source,
        "cost_matrix_constants": {kk: str(vv) for kk, vv in k.items()},
        "per_case": check_per_case(rows),
        "global_ceiling": glob,
        "witness_crosscheck": witness_crosscheck(glob),
        "grid_crosscheck": grid_crosscheck(glob, n=grid),
        "constrained_regime": check_constrained_regime(k, rows),
        "feasibility": feas,
        "lambda_crosscheck": lambda_crosscheck(k, feas),
        "invariants": check_invariants(rows, k),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="also write the raw findings here")
    ap.add_argument("--grid", type=int, default=60,
                    help="steps per axis for the cross-check grid (default 60)")
    ap.add_argument("--arm", choices=ARMS, default="published",
                    help="which beliefs the belief-dependent checks read "
                         "(default published, i.e. Gate 1's results/run.json)")
    args = ap.parse_args()

    try:
        rows, source = load_arm(args.arm)
    except ArmError as exc:
        print(f"Cannot build the {args.arm!r} arm:\n\n  {exc}\n", file=sys.stderr)
        return 2

    findings = build_findings(rows, source, grid=args.grid)
    if args.arm != "published":
        print(f"\n### arm: {args.arm}   beliefs: {source}")

    p = findings["per_case"]
    print(f"\n=== 1. Ceiling on the {p['n']} committed beliefs "
          f"(constraints applied) ===")
    print("VoI(q|b) <= V_act(b) - EC(ask|b), for every question and answer model")
    print(f"  cases where that ceiling is positive: "
          f"{p['n_positive_ceiling']} / {p['n']}")
    print(f"  least negative {p['max_ceiling']:+.3f} (attained by "
          f"{p['n_at_max_ceiling']} cases)   "
          f"most negative {p['min_ceiling']:+.3f}")
    print(f"  cases at the least-negative value: "
          f"{', '.join(p['cases_at_max_ceiling'])}")
    a = p["anchor_case"]
    print(f"  anchor {a['case_id']}: ceiling {a['ceiling']:+.3f} "
          f"(V_act {a['v_act']:.3f} via {a['v_act_argmin']}, "
          f"EC(ask) {a['ec_ask']:.3f})")
    print(f"  {p['n_constrained_cases']} cases carry a hard constraint; best "
          f"ceiling among them {p['max_ceiling_among_constrained']:+.3f}, "
          f"lowest b_h {p['min_b_h_among_constrained']:.2f}")

    g = findings["global_ceiling"]
    print("\n=== 2. Maximum over EVERY belief, in closed form ===")
    print(f"alpha (false assertion) = {g['alpha_false_assertion']}   "
          f"nu (needless escalation) = {g['nu_needless_escalation']}   "
          f"ask row = ({g['ask_F']}, {g['ask_T']})")
    print(f"closed form valid (both monotonicity conditions): "
          f"{g['closed_form_valid']}")
    print(f"  t* = nu/(alpha+nu) = {g['t_star_exact']} = {g['t_star_float']:.6f}")
    print(f"  max_b V_act(b) = alpha*nu/(alpha+nu) = {g['max_v_act_exact']} "
          f"= {g['max_v_act_float']:.6f}")
    print(f"  EC(ask) at t* = {g['ec_ask_at_t_star_exact']}, "
          f"and EC(ask) ranges over [{g['ec_ask_range'][0]}, {g['ec_ask_range'][1]}]")
    print(f"  => max ceiling = {g['ceiling_exact']} = {g['ceiling_float']:+.6f}")
    print(f"  bound attained (so it is the max, not just a bound): "
          f"{g['bound_is_attained']}")
    if g["witness_belief"]:
        w = g["witness_belief"]
        print(f"    witness: readiness {w['readiness']}, b_h = {w['b_h']}; "
              f"hold {w['hold_cost']}, pause {w['pause_cost']} both above the cap")
    print(f"  ask can EVER be rational on the unconstrained menu: "
          f"{g['ask_can_ever_be_rational']}")

    wc = findings["witness_crosscheck"]
    if wc["ran"]:
        print(f"\n  cross-check through src/costs.py at that witness: "
              f"ceiling {wc['ceiling_via_src_costs']:+.9f} vs closed form "
              f"{wc['closed_form_ceiling']:+.9f}  "
              f"agree: {wc['agree_to_1e_9']}")
    x = findings["grid_crosscheck"]
    print(f"  independent grid cross-check ({x['grid_steps_per_axis']}/axis): "
          f"max {x['grid_max']:+.6f} vs closed form {x['closed_form_max']:+.6f}")
    print(f"    grid exceeds closed form (would be a bug): "
          f"{x['grid_exceeds_closed_form']}   "
          f"shortfall {x['gap_to_closed_form']:.6f} (t* = "
          f"{g['t_star_exact']} is not on a 1/{x['grid_steps_per_axis']} grid)")

    c = findings["constrained_regime"]
    print(f"\n=== 2b. The same maximum on the menu `{c['constraint']}` leaves ===")
    print(f"  menu {c['menu']}")
    print(f"  max ceiling {c['max_ceiling']:+.6f} at {c['argmax']}")
    print(f"  ask CAN be rational when answering is forbidden: "
          f"{c['ask_can_be_rational_under_this_constraint']}")
    b = c["positive_region_on_the_argmax_ray"]
    if b and b["b_h_upper_bound_exact"]:
        print(f"  on the {b['ray']} ray the region is b_h < "
              f"{b['b_h_upper_bound_exact']} = {b['b_h_upper_bound_float']:.4f}, "
              f"bound by {b['binding_action']}")
    print(f"  but the {c['n_cases_carrying_the_constraint']} cases that carry the "
          f"constraint have b_h >= {c['min_b_h_among_those_cases']:.2f}, so any "
          f"inside the region: {c['any_such_case_inside_the_region']}")

    f = findings["feasibility"]
    print("\n=== 3. What `ask` would have to cost ===")
    print(f"  condition: {f['condition']}   ->   {f['readable_condition']}")
    print(f"  this matrix: {f['lhs_exact']} < {f['rhs_exact']} is {f['satisfied']}; "
          f"ratio = {f['ratio_exact']} = {f['ratio_float']:.6f}")
    print(f"  break-even lambda = {f['break_even_lambda_exact']} "
          f"= {f['break_even_lambda_float']:.6f}")
    print(f"  ask would have to be priced at "
          f"({f['repriced_ask_row'][0]}, {f['repriced_ask_row'][1]}) "
          f"= ({f['repriced_ask_row_float'][0]:.4f}, "
          f"{f['repriced_ask_row_float'][1]:.4f})")
    print(f"  i.e. a reduction of {f['required_reduction_exact']} "
          f"= {f['required_reduction_pct']:.4f}% in the price of a question")
    lx = findings["lambda_crosscheck"]
    print(f"  bisection cross-check: {lx['bisected_lambda']:.9f}  "
          f"agrees to 1e-9: {lx['agree_to_1e_9']}")

    print("\n=== 4. Invariants from the Gate 1 definitions ===")
    for name, inv in findings["invariants"].items():
        bad = inv.get("violations", inv.get("cases_where_ask_would_be_chosen"))
        print(f"  {name}: holds on {inv['holds_on']}"
              + (f"  VIOLATIONS: {bad}" if bad else ""))
        print(f"    {inv['claim']}")

    if args.json:
        args.json.write_text(json.dumps(findings, indent=2, default=str))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
