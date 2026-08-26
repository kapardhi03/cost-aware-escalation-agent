"""
Reproduction checks for the artifacts that carry float columns.

A byte-for-byte comparison is the right guard for an artifact whose every value is
exact. It is the wrong guard for one that carries a float sum, because CPython 3.12
changed `sum()` over floats to Neumaier compensated summation. The same expression
on the same inputs therefore ends in different last bits on 3.11 and on 3.12, and a
byte test reads that as a changed result. Measured on `results/entropy-baseline.json`:
826 leaves differ between 3.11.12 and 3.14.3, 818 of them float-typed with a maximum
absolute delta of 1.11e-15.

What this module must not do is soften anything else. The exactness claims in this
repo live in strings and ints — `"-2/13"`, `"15/16"`, `"30/13"` are `Fraction`s
rendered with `str`, and every count is an `int` — so the rule is: **only a
float-versus-float leaf is forgiven, and only within `FLOAT_TOL`.** A changed key, a
reordered key, a changed list length, a changed string, a changed int, a changed
bool, and a leaf whose *type* changed all still fail.

Two independent comparisons run, because each catches what the other cannot:

1. `structural_mismatches` walks the parsed objects. It sees types, key sets, key
   order and list lengths, which a text diff cannot name.
2. `float_only_line_mismatches` walks the rendered text line by line. It sees
   indentation, separators and the trailing newline, which a parsed walk discards,
   and it forgives a line only when the two differ in a numeric literal alone.

Together they leave no gap: (1) would pass `2` against `2.0` under a naive numeric
rule, and (2) would pass a file whose indent changed if the parse were all that was
checked. Neither is permitted here.

The floor in `MIN_PYTHON` is not about this tolerance. It is about the two claims
that compensated summation is what makes true — see `WHY_MIN_PYTHON`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT.parent / ".github" / "workflows" / "tests.yml"

#: Forgiveness for a float-versus-float leaf. Seven orders of magnitude above the
#: largest interpreter-to-interpreter delta measured (1.11e-15), and far below any
#: quantity this repo reports: costs are counted in whole points, beliefs are
#: quantized to 4 decimals, entropies to 12.
FLOAT_TOL = 1e-9

#: The lowest interpreter the reported artifacts are claimed to reproduce on. Below
#: it the tolerance checks in this module still pass; two exactness claims do not.
MIN_PYTHON = (3, 12)

WHY_MIN_PYTHON = (
    "CPython 3.12 made `sum()` over floats use Neumaier compensated summation. Two "
    "committed claims depend on it. `ceiling_agreement.max_ceiling_delta` is 0.0 "
    "exactly on all four arms, asserted in "
    "test_entropy_baseline.test_ceiling_agreement_is_exact_on_every_arm and recorded "
    "as X2; on 3.11 the same recomputation lands at 1.11e-15, which passes every "
    "tolerance but is not zero. And `results/entropy-baseline.md` prints an exact "
    "zero as `0` and a nonzero residual as `< 1e-12`, so that same delta changes the "
    "rendered table. Neither is a defect below 3.12 — the arithmetic is simply less "
    "exact there, and the repo declares the range in which its exactness claims hold "
    "rather than quietly depending on the interpreter that happened to write them.")


class Mismatch(NamedTuple):
    """One difference the comparison would not forgive."""

    path: str
    kind: str          # keys | order | length | type | value
    committed: object
    fresh: object

    def __str__(self) -> str:
        return (f"{self.path or '<root>'}: {self.kind}: "
                f"{self.committed!r} -> {self.fresh!r}")


def structural_mismatches(committed, fresh, tol: float = FLOAT_TOL,
                          path: str = "") -> list[Mismatch]:
    """Every difference between two parsed JSON values, floats aside.

    Key *order* is compared as well as key membership, because the artifacts are
    rendered with `json.dumps` and their key order is the order the report is built
    in. A reordering is a change to the file even when no value moved.

    Leaf types are compared with `type(...) is type(...)` rather than `isinstance`,
    so `2` against `2.0` and `True` against `1` are both reported. Under a numeric
    rule alone they would pass, and an int silently becoming a float is exactly the
    kind of drift this file exists to notice.
    """
    if isinstance(committed, dict) or isinstance(fresh, dict):
        if type(committed) is not type(fresh):
            return [Mismatch(path, "type", type(committed).__name__,
                             type(fresh).__name__)]
        if list(committed) != list(fresh):
            return [Mismatch(path, "keys" if set(committed) != set(fresh) else "order",
                             list(committed), list(fresh))]
        out = []
        for key in committed:
            out += structural_mismatches(committed[key], fresh[key], tol,
                                         f"{path}.{key}")
        return out

    if isinstance(committed, list) or isinstance(fresh, list):
        if type(committed) is not type(fresh):
            return [Mismatch(path, "type", type(committed).__name__,
                             type(fresh).__name__)]
        if len(committed) != len(fresh):
            return [Mismatch(path, "length", len(committed), len(fresh))]
        out = []
        for i, (c, f) in enumerate(zip(committed, fresh)):
            out += structural_mismatches(c, f, tol, f"{path}[{i}]")
        return out

    if type(committed) is not type(fresh):
        return [Mismatch(path, "type", committed, fresh)]
    if type(committed) is float:
        return ([] if abs(committed - fresh) <= tol
                else [Mismatch(path, "value", committed, fresh)])
    return [] if committed == fresh else [Mismatch(path, "value", committed, fresh)]


#: One rendered line of `json.dumps(..., indent=2)` whose value is a bare number:
#: indentation, an optional quoted key and colon, the number, an optional comma and
#: newline. A string value cannot match, because it is quoted where `num` requires a
#: digit or a sign — so `"ceiling_exact": "-2/13"` is never treated as numeric.
NUMERIC_LINE = re.compile(
    r'^(?P<head>[ ]*(?:"(?:[^"\\]|\\.)*"[ ]*:[ ]*)?)'
    r'(?P<num>-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)'
    r'(?P<tail>,?\n?)$')


def line_mismatches(committed_text: str, fresh_text: str,
                    tol: float = FLOAT_TOL) -> list[str]:
    """Differing rendered lines, excusing only a numeric value in the same slot.

    This is the byte test with one hole drilled in it, deliberately the smallest hole
    that admits summation noise: the two lines must agree on indentation, on the key,
    and on the separator, and differ only in a number that differs by at most `tol`.
    Anything else — a moved line, a changed string, an added or removed line, a
    changed trailing newline — is returned.
    """
    old = committed_text.splitlines(keepends=True)
    new = fresh_text.splitlines(keepends=True)
    if len(old) != len(new):
        return [f"line count: {len(old)} committed, {len(new)} fresh"]

    out = []
    for i, (a, b) in enumerate(zip(old, new), start=1):
        if a == b:
            continue
        ma, mb = NUMERIC_LINE.match(a), NUMERIC_LINE.match(b)
        forgiven = (
            ma is not None and mb is not None
            and ma["head"] == mb["head"] and ma["tail"] == mb["tail"]
            and abs(float(ma["num"]) - float(mb["num"])) <= tol)
        if not forgiven:
            out.append(f"line {i}: {a.rstrip()!r} -> {b.rstrip()!r}")
    return out


def assert_reproduces(fresh_text: str, committed: Path,
                      tol: float = FLOAT_TOL) -> None:
    """`fresh_text` must be `committed`, up to float noise. Raises AssertionError.

    `fresh_text` is the string the byte test used to compare, so the call site keeps
    its own `json.dumps` conventions — indent, `default=str`, trailing newline — and
    those conventions are still checked, by `line_mismatches`.
    """
    committed_text = committed.read_text(encoding="utf-8")
    lines = line_mismatches(committed_text, fresh_text, tol)
    struct = structural_mismatches(json.loads(committed_text),
                                   json.loads(fresh_text), tol)
    if not lines and not struct:
        return

    report = [f"{committed.name} no longer reproduces (tolerance {tol:g} on "
              f"float-vs-float leaves only)."]
    if struct:
        report.append(f"  {len(struct)} structural mismatch(es), first 10:")
        report += [f"    {m}" for m in struct[:10]]
    if lines:
        report.append(f"  {len(lines)} unforgiven line(s), first 10:")
        report += [f"    {ln}" for ln in lines[:10]]
    raise AssertionError("\n".join(report))


def ci_matrix_versions() -> list[tuple[int, ...]]:
    """The Python versions the CI workflow runs, parsed without a YAML dependency.

    `src/` is stdlib-only and the test venv installs pytest and matplotlib, so there
    is no yaml module to lean on. The matrix is a single flow-sequence line.
    """
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"^\s*python-version:\s*\[(?P<items>[^\]]*)\]\s*$",
                      text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"no python-version matrix line in {CI_WORKFLOW}")
    return [tuple(int(part) for part in item.strip().strip('"\'').split("."))
            for item in match["items"].split(",") if item.strip()]
