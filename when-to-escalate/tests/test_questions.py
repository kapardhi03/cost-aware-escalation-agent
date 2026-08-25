"""
The Gate 3 question set, the answer model, and the OQ1 adapter.

Two load-bearing tests here.

`test_preregistration_prose_matches_the_constants` is the link that stops
`decisions/v2-gate3-preregistration.md` from going stale silently. The document
names the questions, the answer sets, the sweep grid and the parameter counts; if
someone edits a constant without editing the document, or the reverse, this fails.
Gate 2 used the same mechanism against `src/calibrate.PREREGISTRATION`.

`test_narrow_raises_on_a_coupled_posterior` is the one that makes OQ1 real. A test
that only checked the round trip would pass on an adapter that always projects onto
the marginals, which is exactly the silent flattening OQ1 was opened to prevent.
"""

from __future__ import annotations

import importlib.util
import sys
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "decisions" / "v2-gate3-preregistration.md"


@pytest.fixture
def q():
    import questions as questions_mod
    return questions_mod


@pytest.fixture
def am():
    """`experiments/answer_model.py`, loaded by path.

    It is a script rather than a package module, and it puts the repo root on
    sys.path itself so its `from src...` imports resolve.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "answer_model", ROOT / "experiments" / "answer_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Shape, and agreement with the rest of the codebase
# --------------------------------------------------------------------------- #

def test_readiness_order_matches_costs(q):
    import costs
    assert q.READINESS == tuple(costs.READINESS_LABELS)


def test_six_states_in_the_order_costs_assumes(q):
    assert q.STATES == (("hot", False), ("hot", True),
                        ("warm", False), ("warm", True),
                        ("cold", False), ("cold", True))


def test_the_set_is_three_questions_plus_one_control(q):
    assert [x.id for x in q.QUESTIONS] == [
        "q_timeline", "q_authority", "q_specifics", "q_null"]
    assert sum(1 for x in q.QUESTIONS if x.target == "none") == 1


def test_every_row_sums_to_exactly_one(q):
    for question in q.QUESTIONS:
        assert q.rows_sum_to_one(question), question.id
        for s in q.STATES:
            # Exact, not approximate: entries are integers out of 100.
            assert sum(question.row(s)) == Fraction(1)


def test_every_entry_is_inside_the_sweep_clip_range(q):
    lo, hi = q.SWEEP_CLIP
    for question in q.QUESTIONS:
        for s in q.STATES:
            for v in question.table[s]:
                assert lo <= v / 100.0 <= hi, (question.id, s, v)


def test_no_answer_has_positive_probability_everywhere(q):
    """Assumption A2. It is what keeps every P_b(u) > 0."""
    for question in q.QUESTIONS:
        if "no_answer" not in question.answers:
            continue
        for s in q.STATES:
            assert question.likelihood(s, "no_answer") > 0, (question.id, s)


def test_likelihood_is_exact_rational(q):
    v = q.Q_TIMELINE.likelihood(("hot", False), "soon")
    assert isinstance(v, Fraction)
    assert v == Fraction(70, 100)


# --------------------------------------------------------------------------- #
# Separability — the structural claim the pre-registration makes
# --------------------------------------------------------------------------- #

def test_single_axis_questions_separate_and_the_both_axis_one_does_not(q):
    assert q.separates(q.Q_TIMELINE) is True
    assert q.separates(q.Q_AUTHORITY) is True
    assert q.separates(q.Q_NULL) is True
    assert q.separates(q.Q_SPECIFICS) is False


def test_axis_only_tables_repeat_across_the_other_axis(q):
    """The reason they separate, asserted directly rather than inferred."""
    for r in q.READINESS:
        assert q.Q_TIMELINE.table[(r, False)] == q.Q_TIMELINE.table[(r, True)]
    for h in q.NEEDS_HUMAN:
        rows = {q.Q_AUTHORITY.table[(r, h)] for r in q.READINESS}
        assert len(rows) == 1


def test_separates_catches_a_table_that_only_just_couples(q):
    """A one-unit perturbation to a separable table must be detected.

    Exact arithmetic is the point: a float rank-1 test with a loose tolerance
    would call this separable.
    """
    table = dict(q.Q_TIMELINE.table)
    row = list(table[("hot", True)])
    row[0] += 1
    row[2] -= 1
    table[("hot", True)] = tuple(row)
    perturbed = q.Question(id="x", text="", target="readiness",
                           answers=q.Q_TIMELINE.answers, table=table)
    assert q.rows_sum_to_one(perturbed)
    assert q.separates(perturbed) is False


# --------------------------------------------------------------------------- #
# The OQ1 adapter, both directions
# --------------------------------------------------------------------------- #

def test_widen_produces_a_distribution_over_six_states(q):
    joint = q.widen({"hot": 0.5, "warm": 0.3, "cold": 0.2}, 0.4)
    assert set(joint) == set(q.STATES)
    assert abs(sum(joint.values()) - 1.0) < 1e-15
    assert abs(joint[("hot", True)] - 0.5 * 0.4) < 1e-15


def test_round_trip_is_exact_for_a_factorising_belief(q):
    readiness = {"hot": 0.5, "warm": 0.3, "cold": 0.2}
    joint = q.widen(readiness, 0.4)
    back_r, back_h = q.narrow(joint)
    assert max(abs(back_r[k] - readiness[k]) for k in readiness) < 1e-12
    assert abs(back_h - 0.4) < 1e-12


def test_round_trip_survives_a_degenerate_belief(q):
    """b_h = 0 and a pure readiness state — the shape four real cases have."""
    joint = q.widen({"hot": 0.0, "warm": 0.0, "cold": 1.0}, 0.0)
    back_r, back_h = q.narrow(joint)
    assert back_r == {"hot": 0.0, "warm": 0.0, "cold": 1.0}
    assert back_h == 0.0


def test_narrow_raises_on_a_coupled_posterior(q):
    """The test that makes OQ1 real. Same marginals, not a product."""
    coupled = {("hot", False): 0.30, ("hot", True): 0.20,
               ("warm", False): 0.10, ("warm", True): 0.20,
               ("cold", False): 0.20, ("cold", True): 0.00}
    assert abs(sum(coupled.values()) - 1.0) < 1e-15
    assert q.factorises(coupled) is False
    with pytest.raises(q.NonFactorisingError):
        q.narrow(coupled)


def test_narrow_does_not_project(q):
    """An adapter that projected would return the marginals and not raise.

    Pinned separately from the raise, because `marginals` is public and returning
    it from `narrow` would be the easy wrong implementation.
    """
    coupled = {("hot", False): 0.30, ("hot", True): 0.20,
               ("warm", False): 0.10, ("warm", True): 0.20,
               ("cold", False): 0.20, ("cold", True): 0.00}
    readiness, needs_human = q.marginals(coupled)
    assert abs(sum(readiness.values()) - 1.0) < 1e-15
    assert abs(needs_human - 0.40) < 1e-15
    with pytest.raises(q.NonFactorisingError):
        q.narrow(coupled)


def test_a_real_posterior_from_the_both_axis_question_couples(q, am):
    """Not a hand-built example: the posterior a middling belief actually produces."""
    joint = q.widen({"hot": 0.2, "warm": 0.5, "cold": 0.3}, 0.4)
    j = q.Q_SPECIFICS.answers.index("concrete")
    weights = {s: joint[s] * q.Q_SPECIFICS.table[s][j] / 100.0 for s in q.STATES}
    total = sum(weights.values())
    posterior = {s: weights[s] / total for s in q.STATES}
    assert q.factorises(posterior) is False
    with pytest.raises(q.NonFactorisingError):
        q.narrow(posterior)


# --------------------------------------------------------------------------- #
# Information gain — the Gate 1 §2 definitions, on synthetic beliefs
# --------------------------------------------------------------------------- #

UNIFORM = ({"hot": 1 / 3, "warm": 1 / 3, "cold": 1 / 3}, 0.5)
MIDDLING = ({"hot": 0.2, "warm": 0.5, "cold": 0.3}, 0.4)
DEGENERATE = ({"hot": 0.0, "warm": 0.0, "cold": 1.0}, 0.0)


@pytest.mark.parametrize("readiness,needs_human", [UNIFORM, MIDDLING, DEGENERATE])
def test_ig_is_non_negative_and_bounded_by_the_prior_entropy(q, am, readiness,
                                                             needs_human):
    joint = q.widen(readiness, needs_human)
    for question in q.QUESTIONS:
        r = am.evaluate(question, joint)
        assert r["ig"] >= -1e-12, (question.id, r["ig"])
        assert r["ig"] <= r["h_prior_joint"] + 1e-12


@pytest.mark.parametrize("readiness,needs_human", [UNIFORM, MIDDLING, DEGENERATE])
def test_the_control_question_gains_exactly_nothing(q, am, readiness, needs_human):
    """The equality case: IG = 0 iff P(u | s) does not depend on s."""
    joint = q.widen(readiness, needs_human)
    assert abs(am.evaluate(q.Q_NULL, joint)["ig"]) < 1e-12


@pytest.mark.parametrize("readiness,needs_human", [UNIFORM, MIDDLING, DEGENERATE])
def test_predictive_distribution_sums_to_one(q, am, readiness, needs_human):
    joint = q.widen(readiness, needs_human)
    for question in q.QUESTIONS:
        r = am.evaluate(question, joint)
        assert r["predictive_sums_to_1_residual"] < 1e-12
        assert all(p > 0.0 for p in r["predictive"].values()), question.id


def test_a_degenerate_belief_gains_nothing_from_any_question(q, am):
    """H(b) = 0 on both axes, so IG must be 0 — invariant 5 at its boundary.

    This is the shape `a11-repeated-097` has, and it fails loudly on a sign or
    normalisation error in the entropy code.
    """
    joint = q.widen(*DEGENERATE)
    for question in q.QUESTIONS:
        r = am.evaluate(question, joint)
        assert r["h_prior_joint"] == 0.0
        assert abs(r["ig"]) < 1e-12, question.id


def test_prior_entropy_is_additive_but_posterior_entropy_need_not_be(q, am):
    """The trap `answer_model` is built around.

    H(b) = H_r + H_h holds for the prior because the two parts are independent by
    design. For a coupled posterior H_r + H_h exceeds the joint entropy, so using
    the sum would understate IG. Both halves asserted.
    """
    joint = q.widen(*MIDDLING)
    r = am.evaluate(q.Q_SPECIFICS, joint)
    assert r["additivity_residual"] < 1e-12

    j = q.Q_SPECIFICS.answers.index("concrete")
    weights = {s: joint[s] * q.Q_SPECIFICS.table[s][j] / 100.0 for s in q.STATES}
    total = sum(weights.values())
    posterior = {s: weights[s] / total for s in q.STATES}
    h_joint = am.joint_entropy(posterior)
    h_r, h_h = am.axis_entropies(posterior)
    assert h_r + h_h > h_joint + 1e-9


def test_ig_decomposes_into_axis_gains_plus_coupling(q, am):
    """IG = IG_r + IG_h + I(R ; Hh | U), exactly, and the coupling is >= 0."""
    joint = q.widen(*MIDDLING)
    for question in q.QUESTIONS:
        r = am.evaluate(question, joint)
        assert r["decomposition_residual"] < 1e-12, question.id
        assert r["coupling_term"] >= -1e-12, question.id


def test_a_separable_table_induces_no_coupling(q, am):
    """The independent cross-check on `separates`.

    `separates` is a rank-1 test on the table; the coupling term is an entropy
    computed from the posteriors. They are different computations, so agreement is
    evidence rather than tautology.
    """
    joint = q.widen(*MIDDLING)
    for question in q.QUESTIONS:
        if q.separates(question):
            assert abs(am.evaluate(question, joint)["coupling_term"]) < 1e-12, \
                question.id
    assert am.evaluate(q.Q_SPECIFICS, joint)["coupling_term"] > 1e-9


def test_a_state_independent_table_is_the_only_way_to_get_zero(q, am):
    """Constructed from the definition, not from the committed tables.

    Any table whose rows are all identical must give IG = 0; perturbing one row
    must make IG positive. This pins the equality case in both directions.
    """
    joint = q.widen(*MIDDLING)
    flat = q.Question(id="flat", text="", target="none", answers=("a", "b"),
                      table={s: (30, 70) for s in q.STATES})
    assert abs(am.evaluate(flat, joint)["ig"]) < 1e-12

    table = dict(flat.table)
    table[("hot", False)] = (31, 69)
    tilted = q.Question(id="tilted", text="", target="none", answers=("a", "b"),
                        table=table)
    assert am.evaluate(tilted, joint)["ig"] > 0.0


# --------------------------------------------------------------------------- #
# The pre-registration link
# --------------------------------------------------------------------------- #

def test_preregistration_prose_matches_the_constants(q):
    doc = PREREG.read_text()

    for question in q.QUESTIONS:
        assert f"`{question.id}`" in doc, question.id
        for answer in question.answers:
            assert f"`{answer}`" in doc, (question.id, answer)

    assert "±0.05" in doc and "±0.10" in doc
    assert "`[0.01, 0.99]`" in doc
    assert [abs(d) for d in q.SWEEP_DELTAS] == [0.10, 0.05, 0.05, 0.10]
    assert q.SWEEP_CLIP == (0.01, 0.99)

    # The parameter-count table in §3.
    assert q.PREREGISTRATION["n_judgment_entries"] == 54
    assert "| total | 54 | — | 22 |" in doc
    for name, entries, rows_, free in (("q_timeline", 18, 3, 6),
                                       ("q_authority", 18, 2, 4),
                                       ("q_specifics", 18, 6, 12)):
        assert f"| `{name}` | {entries} | {rows_} | {free} |" in doc


def test_preregistration_free_parameter_counts_are_the_real_ones(q):
    """The 22 in the document, recomputed from the tables rather than trusted."""
    total = 0
    for question in q.QUESTIONS:
        if question.id == "q_null":
            continue
        distinct = {question.table[s] for s in q.STATES}
        total += len(distinct) * (len(question.answers) - 1)
    assert total == 22


def test_expected_separability_is_declared_and_true(q):
    declared = q.PREREGISTRATION["expected_separable"]
    assert declared == {x.id: q.separates(x) for x in q.QUESTIONS}
    assert declared["q_specifics"] is False


def test_the_provenance_tag_is_the_honest_one(q):
    """The entries are AI-drafted and Kaps-reviewed, and never called otherwise.

    Mislabelling them practitioner-set would fabricate the provenance the design
    record runs on, so it is pinned rather than left to review.
    """
    assert q.PREREGISTRATION["entry_provenance"] == "AI-proposed, Kaps-reviewed"
    assert q.PREREGISTRATION["not_practitioner_set"] is True

    doc = PREREG.read_text()
    assert "(AI-proposed, Kaps-reviewed)" in doc
    assert "**not** practitioner-set" in doc
    # No positive claim anywhere, in either file.
    for text in (doc, (ROOT / "src" / "questions.py").read_text()):
        assert "entries set by practitioner judgment" not in text
        assert "practitioner-set entries" not in text


def test_the_five_invariants_are_stated_in_both_places(q):
    doc = PREREG.read_text()
    assert len(q.PREREGISTRATION["invariants"]) == 5
    for fragment in ("IG(q | b) ≥ 0", "IG(q_null | b) = 0", "Σ_u P_b(u) = 1",
                     "IG(q | b) ≤ H(b)"):
        assert fragment in doc, fragment


def test_the_gate_makes_no_api_calls(am):
    """Asserted structurally: the script imports nothing that can reach a provider."""
    source = (ROOT / "experiments" / "answer_model.py").read_text()
    for forbidden in ("get_belief", "llm_chain", "openai", "genai",
                      "get_provider", "requests"):
        assert forbidden not in source, forbidden
