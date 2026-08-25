"""
questions.py — the question set, the answer model, and the six-vector adapter.

Locked by `decisions/v2-gate3-preregistration.md`. This module is committed in the
same commit as that file and **before** `experiments/answer_model.py` exists, so
"the tables were fixed before any information gain was seen" is a property of the
git history rather than a claim. Nothing here computes an information gain — by
design, this commit cannot produce a number.

Provenance of the numbers. The 54 non-null table entries are **(AI-proposed,
Kaps-reviewed)**: drafted by Claude to express the ambiguity each archetype
actually leaves (pre-registration §2), then reviewed by Kaps, who overwrites any
that read wrong. They are **not** practitioner-set and must never be described
that way — the answer model is illustrative, the impossibility result is
answer-model-free (pre-registration §1), and mislabelling an AI draft as
practitioner judgment would fabricate the provenance the rest of this record runs
on.

Two structural assumptions, both contestable, both stated in pre-registration §3:

  A1  P(u | s) depends on the hidden state only, not on which case is asked
      about, so one table serves all 100 cases. False in detail — a hot lead in
      archetype 4 does not answer like a hot lead in archetype 9 — and accepted
      because the alternative is 11 tables with 11x the free parameters and no
      data to constrain any of them.
  A2  `no_answer` is a real answer, not missing data. Every question carries it
      with non-zero probability in every state, so every P_b(u) > 0 and the
      posterior of Gate 1 §2 is defined for every answer.

Entries are stored as integers out of 100 and exposed as `Fraction`s, so every row
sums to exactly 1 and the separability checks below are exact rather than
tolerance-bound. `experiments/voi_ceiling.py` uses the same exact-arithmetic
convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Mapping, Sequence, Tuple

#: Readiness levels, in the order `costs.READINESS_LABELS` uses. Duplicated as a
#: literal rather than imported so this module stays importable on its own; the
#: test asserts the two agree.
READINESS: Tuple[str, ...] = ("hot", "warm", "cold")

#: needs_human levels, in the order `costs.state_probability` assumes.
NEEDS_HUMAN: Tuple[bool, ...] = (False, True)

#: The six joint states, `readiness x needs_human`, in canonical order. The
#: six-vector of OQ1(b) is indexed by this tuple.
STATES: Tuple[Tuple[str, bool], ...] = tuple(
    (r, h) for r in READINESS for h in NEEDS_HUMAN
)

DENOMINATOR = 100

#: Tolerance for float factorisation checks. Table arithmetic is exact; only the
#: belief-derived joint is float.
FACTORISATION_TOL = 1e-12


class NonFactorisingError(ValueError):
    """A coupled six-vector cannot be reduced to a `Belief`.

    Raised rather than projected. OQ1 exists to stop a coupled posterior being
    silently flattened into (readiness dict, scalar); a projection would make the
    coupling invisible at exactly the point it matters.
    """


@dataclass(frozen=True)
class Question:
    """One question, its answer set, and its likelihood table.

    `table` maps each of the six states to a tuple of integers out of
    `DENOMINATOR`, positionally aligned with `answers`.
    """

    id: str
    text: str
    target: str
    answers: Tuple[str, ...]
    table: Mapping[Tuple[str, bool], Tuple[int, ...]]

    def likelihood(self, state: Tuple[str, bool], answer: str) -> Fraction:
        """P(answer | state), exact."""
        return Fraction(self.table[state][self.answers.index(answer)], DENOMINATOR)

    def row(self, state: Tuple[str, bool]) -> Tuple[Fraction, ...]:
        """P(. | state) over `answers`, exact."""
        return tuple(Fraction(v, DENOMINATOR) for v in self.table[state])


# --------------------------------------------------------------------------
# The four questions. Selection rule, pre-registration §2: drawn from what the
# 11 archetypes in data/cases.json actually leave ambiguous, tabulated before any
# IG was computed. Nothing chosen to make `ask` fire.
# --------------------------------------------------------------------------

#: Readiness-only. Archetypes 8 (media, no text) and 9 (over-sharer) split on
#: readiness while every case in them is needs_human=False, so readiness is the
#: axis a question can still move there. Rows are identical across h by
#: construction, which is what makes the posterior factorise.
_TIMELINE_BY_READINESS: Dict[str, Tuple[int, int, int]] = {
    # soon, later, no_answer
    "hot": (70, 18, 12),    # a hot lead volunteers a timeline
    "warm": (35, 45, 20),   # still comparing; "later" is the honest answer
    "cold": (10, 52, 38),   # mostly not engaging with the question at all
}

Q_TIMELINE = Question(
    id="q_timeline",
    text="When are you looking to make a decision on this?",
    target="readiness",
    answers=("soon", "later", "no_answer"),
    table={(r, h): _TIMELINE_BY_READINESS[r] for r in READINESS for h in NEEDS_HUMAN},
)

#: needs_human-only. Archetypes 2, 4, 7 and 11 hold readiness fixed and split on
#: needs_human, so that is the axis in play. Rows are identical across r by
#: construction.
_AUTHORITY_BY_NEEDS_HUMAN: Dict[bool, Tuple[int, int, int]] = {
    # self, others, no_answer
    False: (70, 16, 14),   # decides alone; nothing a human handler is needed for
    True: (20, 60, 20),    # a third party, a lawyer, or a complaint escalation
}

Q_AUTHORITY = Question(
    id="q_authority",
    text="Is this your decision alone, or does someone else sign off with you?",
    target="needs_human",
    answers=("self", "others", "no_answer"),
    table={(r, h): _AUTHORITY_BY_NEEDS_HUMAN[h] for r in READINESS for h in NEEDS_HUMAN},
)

#: Both axes. Archetypes 3, 5, 6 and 10 split on readiness *and* needs_human, so
#: the question that fits them touches both — and its likelihood does not
#: factorise. This is the case that makes the six-vector adapter necessary rather
#: than decorative: `separates()` returns False for it, verified exactly.
_SPECIFICS: Dict[Tuple[str, bool], Tuple[int, int, int]] = {
    # concrete, vague, no_answer
    ("hot", False): (78, 12, 10),   # serious and self-serving: names the detail
    ("hot", True): (50, 30, 20),    # serious but the ask is one we cannot answer
    ("warm", False): (52, 30, 18),
    ("warm", True): (34, 42, 24),
    ("cold", False): (20, 50, 30),  # time-waster: vague by disposition
    ("cold", True): (14, 44, 42),   # off-topic or hostile: mostly no answer
}

Q_SPECIFICS = Question(
    id="q_specifics",
    text="Which specific detail do you need before you can move forward?",
    target="both",
    answers=("concrete", "vague", "no_answer"),
    table=dict(_SPECIFICS),
)

#: The control. Gate 1 §2 states IG = 0 exactly when P(u | s) is the same for
#: every s. This is that case, in the question set so the equality is an
#: executed assertion rather than a sentence.
Q_NULL = Question(
    id="q_null",
    text="(control) a question whose answer cannot depend on the hidden state",
    target="none",
    answers=("a", "b"),
    table={(r, h): (50, 50) for r in READINESS for h in NEEDS_HUMAN},
)

#: The whole set. Not extended after results — a question added later is a free
#: parameter added after the fact, and goes in a new pre-registration.
QUESTIONS: Tuple[Question, ...] = (Q_TIMELINE, Q_AUTHORITY, Q_SPECIFICS, Q_NULL)

QUESTIONS_BY_ID: Mapping[str, Question] = {q.id: q for q in QUESTIONS}


# --------------------------------------------------------------------------
# Sweep grid, pre-registration §5
# --------------------------------------------------------------------------

#: One-at-a-time perturbations applied to each non-`no_answer` entry, with the
#: row renormalised afterwards. A local sensitivity, not a joint sweep.
SWEEP_DELTAS: Tuple[float, ...] = (-0.10, -0.05, 0.05, 0.10)

#: Perturbed entries are clipped to this interval, and the clipping is reported
#: alongside the result rather than hidden.
SWEEP_CLIP: Tuple[float, float] = (0.01, 0.99)


# --------------------------------------------------------------------------
# Structure of the tables
# --------------------------------------------------------------------------


def rows_sum_to_one(question: Question) -> bool:
    """Every state's row is a distribution. Exact, no tolerance."""
    return all(sum(question.row(s)) == 1 for s in STATES)


def separates(question: Question) -> bool:
    """Does P(u | r, h) factor as a(u, r) * b(u, h) for every answer u?

    This is the condition under which a factorised prior yields a factorised
    posterior, so it decides whether `narrow` can succeed. Tested as a rank-1
    condition on each answer's 3x2 matrix, in exact arithmetic:

        M[r1, F] * M[r2, T] == M[r1, T] * M[r2, F]

    True for the single-axis questions by construction, False for `q_specifics`.
    """
    for j in range(len(question.answers)):
        m = {s: Fraction(question.table[s][j], DENOMINATOR) for s in STATES}
        for i in range(len(READINESS)):
            for k in range(i + 1, len(READINESS)):
                r1, r2 = READINESS[i], READINESS[k]
                if m[(r1, False)] * m[(r2, True)] != m[(r1, True)] * m[(r2, False)]:
                    return False
    return True


# --------------------------------------------------------------------------
# The OQ1 adapter. `Belief` is untouched; the six-vector is used only inside the
# VoI computation.
# --------------------------------------------------------------------------


def widen(readiness: Mapping[str, float], needs_human: float) -> Dict[Tuple[str, bool], float]:
    """`Belief` -> six-vector. Always exact in structure: P(s) = b_r(r) * b_h-part.

    Mirrors `costs.state_probability`, which is why STATES uses that order.
    """
    return {
        (r, h): float(readiness[r]) * (needs_human if h else 1.0 - needs_human)
        for r in READINESS
        for h in NEEDS_HUMAN
    }


def marginals(joint: Mapping[Tuple[str, bool], float]) -> Tuple[Dict[str, float], float]:
    """Six-vector -> (readiness marginal, P(needs_human=True))."""
    readiness = {r: sum(joint[(r, h)] for h in NEEDS_HUMAN) for r in READINESS}
    needs_human = sum(joint[(r, True)] for r in READINESS)
    return readiness, needs_human


def factorises(joint: Mapping[Tuple[str, bool], float], tol: float = FACTORISATION_TOL) -> bool:
    """Is this six-vector the product of its own marginals?"""
    readiness, needs_human = marginals(joint)
    for r in READINESS:
        for h in NEEDS_HUMAN:
            expected = readiness[r] * (needs_human if h else 1.0 - needs_human)
            if abs(joint[(r, h)] - expected) > tol:
                return False
    return True


def narrow(
    joint: Mapping[Tuple[str, bool], float], tol: float = FACTORISATION_TOL
) -> Tuple[Dict[str, float], float]:
    """Six-vector -> `Belief` parts, **only** when the joint factorises.

    Raises `NonFactorisingError` otherwise. It does not project onto the
    marginals: a coupled posterior that silently became a `Belief` would hide
    exactly the coupling OQ1 was opened to keep visible.
    """
    if not factorises(joint, tol=tol):
        readiness, needs_human = marginals(joint)
        worst = max(
            abs(joint[(r, h)] - readiness[r] * (needs_human if h else 1.0 - needs_human))
            for r in READINESS
            for h in NEEDS_HUMAN
        )
        raise NonFactorisingError(
            f"joint does not factorise (max deviation {worst:.3e} > tol {tol:.1e}); "
            "refusing to project onto marginals"
        )
    return marginals(joint)


# --------------------------------------------------------------------------
# What was locked, in a form the test can compare against the prose
# --------------------------------------------------------------------------

PREREGISTRATION = {
    "question_ids": [q.id for q in QUESTIONS],
    "answer_sets": {q.id: list(q.answers) for q in QUESTIONS},
    "targets": {q.id: q.target for q in QUESTIONS},
    "control_question": Q_NULL.id,
    "n_states": len(STATES),
    "n_judgment_entries": sum(
        len(q.answers) * len(STATES) for q in QUESTIONS if q.id != Q_NULL.id
    ),
    "entry_provenance": "AI-proposed, Kaps-reviewed",
    "not_practitioner_set": True,
    "sweep_deltas": list(SWEEP_DELTAS),
    "sweep_clip": list(SWEEP_CLIP),
    "factorisation_tol": FACTORISATION_TOL,
    "expected_separable": {q.id: q.target != "both" for q in QUESTIONS},
    "invariants": [
        "IG(q | b) >= 0 for every question and every belief",
        "IG(q_null | b) == 0 to within 1e-12 for every belief",
        "sum_u P_b(u) == 1 for every question and belief",
        "every table row sums to exactly 1",
        "IG(q | b) <= H(b)",
    ],
    "set_is_closed": (
        "Q is three questions plus the q_null control and is not extended after "
        "results. A question added later is a free parameter added after the fact "
        "and goes in a new pre-registration."
    ),
    "assumptions": {
        "A1": "P(u | s) depends on the state only, not on which case is asked about.",
        "A2": "no_answer is a real answer with non-zero probability in every state.",
    },
}
