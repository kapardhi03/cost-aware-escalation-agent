"""
Guards on `tests/reproduction.py`, and on the Python floor it declares.

Two things are tested here, and they fail for different reasons.

The comparator is tested the way the rest of this suite tests a guard: by breaking
one thing at a time and asserting it is caught. A tolerance that forgave more than
float-versus-float would silently retire the exactness claims the artifacts carry —
the `Fraction`s rendered as strings, the counts, the question ids, the key order —
so each of those gets its own negative control. The one thing that must be forgiven,
a float differing by less than the tolerance, gets a positive control.

The floor is tested because a reproducibility claim that depends on the interpreter
without saying so is the same shape of gap as v1's model-id gap (L10): the artifact
was produced under conditions the artifact does not record. `MIN_PYTHON` is the
condition, and the three tests below pin it to the CI matrix, to the README, and to
the interpreter actually running the suite — so it cannot drift in any of the three
directions independently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import reproduction

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

BASE = {
    "ceiling_exact": "-2/13",
    "n_cases": 100,
    "attained": True,
    "grid_max": -0.16666666666666696,
    "readiness": {"hot": 0.1333, "warm": 0.8333},
    "cases": [{"id": "a05-restricted-043", "voi": -2.8}],
    "missing": None,
}


def render(obj) -> str:
    return json.dumps(obj, indent=2) + "\n"


@pytest.fixture
def committed(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text(render(BASE), encoding="utf-8")
    return path


def mutate(**changes) -> dict:
    out = json.loads(json.dumps(BASE))
    out.update(changes)
    return out


# --------------------------------------------------------------------------- #
# What must be forgiven: float noise, and only float noise
# --------------------------------------------------------------------------- #

def test_a_float_within_the_tolerance_is_forgiven(committed):
    """The whole point. 4.4e-16 of drift is a CPython version, not a result."""
    fresh = mutate(grid_max=-0.16666666666666652)
    reproduction.assert_reproduces(render(fresh), committed)


def test_a_float_beyond_the_tolerance_is_caught(committed):
    fresh = mutate(grid_max=-0.16666666)
    with pytest.raises(AssertionError, match="grid_max"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_an_identical_file_is_forgiven(committed):
    reproduction.assert_reproduces(render(BASE), committed)


# --------------------------------------------------------------------------- #
# Negative controls: everything else still has to match exactly
# --------------------------------------------------------------------------- #

def test_a_changed_fraction_string_is_caught(committed):
    """The exactness claims live in these. `-2/13` is not a float leaf."""
    fresh = mutate(ceiling_exact="-3/13")
    with pytest.raises(AssertionError, match="ceiling_exact"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_fraction_string_that_differs_only_numerically_is_caught(committed):
    """`"-2/13"` against `"-2.0000000001/13"` is a string change, not float noise."""
    fresh = mutate(ceiling_exact="-2/14")
    with pytest.raises(AssertionError, match="ceiling_exact"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_changed_int_is_caught(committed):
    fresh = mutate(n_cases=99)
    with pytest.raises(AssertionError, match="n_cases"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_an_int_becoming_a_float_is_caught(committed):
    """The line comparison forgives `100` against `100.0`. The parsed walk does not.

    This is the case that justifies running both comparisons rather than either one.
    """
    fresh = mutate(n_cases=100.0)
    assert not reproduction.line_mismatches(render(BASE), render(fresh))
    with pytest.raises(AssertionError, match="type"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_changed_bool_is_caught(committed):
    fresh = mutate(attained=False)
    with pytest.raises(AssertionError, match="attained"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_bool_becoming_an_int_is_caught(committed):
    """`isinstance(True, int)` is True, so this needs the `type(...) is` comparison."""
    fresh = mutate(attained=1)
    with pytest.raises(AssertionError, match="type|attained"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_null_becoming_a_zero_is_caught(committed):
    fresh = mutate(missing=0.0)
    with pytest.raises(AssertionError, match="missing"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_reordered_keys_are_caught(committed):
    """A reordering changes the file even though no value moved."""
    fresh = {k: BASE[k] for k in reversed(list(BASE))}
    with pytest.raises(AssertionError, match="order"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_renamed_key_is_caught(committed):
    fresh = {("ceiling" if k == "ceiling_exact" else k): v for k, v in BASE.items()}
    with pytest.raises(AssertionError, match="keys"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_an_added_key_is_caught(committed):
    fresh = mutate(extra="new")
    with pytest.raises(AssertionError, match="keys|line count"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_shorter_list_is_caught(committed):
    """A loader that quietly dropped cases is the failure this catches."""
    fresh = mutate(cases=[])
    with pytest.raises(AssertionError, match="length|line count"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_changed_string_is_caught(committed):
    fresh = json.loads(json.dumps(BASE))
    fresh["cases"][0]["id"] = "a05-restricted-044"
    with pytest.raises(AssertionError, match="id"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_nested_float_is_still_only_forgiven_within_tolerance(committed):
    fresh = json.loads(json.dumps(BASE))
    fresh["readiness"]["warm"] = 0.85
    with pytest.raises(AssertionError, match="warm"):
        reproduction.assert_reproduces(render(fresh), committed)


def test_a_changed_indent_is_caught(committed):
    """The parsed walk cannot see this; the line comparison is why it is here."""
    fresh = json.dumps(BASE, indent=4) + "\n"
    assert not reproduction.structural_mismatches(BASE, json.loads(fresh))
    with pytest.raises(AssertionError, match="line"):
        reproduction.assert_reproduces(fresh, committed)


def test_a_missing_trailing_newline_is_caught(committed):
    with pytest.raises(AssertionError, match="line"):
        reproduction.assert_reproduces(render(BASE).rstrip("\n"), committed)


# --------------------------------------------------------------------------- #
# The declared Python floor
# --------------------------------------------------------------------------- #

def test_the_interpreter_meets_the_declared_floor():
    """Fails loudly on an unsupported interpreter instead of failing obscurely.

    Below the floor, two exactness claims break and produce five confusing failures
    elsewhere in the suite. One explicit failure naming the reason is more useful.
    """
    assert sys.version_info[:2] >= reproduction.MIN_PYTHON, (
        f"this suite is run on Python {'.'.join(map(str, sys.version_info[:2]))}, "
        f"below the declared floor "
        f"{'.'.join(map(str, reproduction.MIN_PYTHON))}. "
        f"{reproduction.WHY_MIN_PYTHON}")


def test_every_ci_version_is_at_or_above_the_floor():
    """The gap this closes: CI tested 3.10 while the artifacts required 3.12."""
    versions = reproduction.ci_matrix_versions()
    assert versions, "the CI matrix parsed as empty"
    below = [v for v in versions if v[:2] < reproduction.MIN_PYTHON]
    assert not below, (
        f"CI runs {below} below the declared floor {reproduction.MIN_PYTHON}. "
        f"Those legs cannot pass: {reproduction.WHY_MIN_PYTHON}")


def test_ci_tests_the_floor_itself():
    """A floor no leg runs at is a claim nothing checks."""
    versions = [v[:2] for v in reproduction.ci_matrix_versions()]
    assert reproduction.MIN_PYTHON in versions, (
        f"no CI leg runs the declared floor {reproduction.MIN_PYTHON}, so a "
        f"regression that needed a later interpreter would pass unnoticed")


def test_the_readme_states_the_same_floor():
    floor = ".".join(str(part) for part in reproduction.MIN_PYTHON)
    text = README.read_text(encoding="utf-8")
    assert f"Python {floor}+" in text, (
        f"README.md does not state 'Python {floor}+'. The declared floor and the "
        f"documented floor have to be the same number.")
