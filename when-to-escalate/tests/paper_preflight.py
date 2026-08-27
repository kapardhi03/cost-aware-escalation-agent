"""
Structural checks on the LaTeX source, for the failures a compile catches.

There is no TeX toolchain in this project's environment and no network to fetch
one, so `it compiles` cannot be asserted here — that check belongs to whoever
runs Overleaf. What *can* be checked offline is the class of defect that makes a
compile fail for a reason a parser can see: an environment closed by the wrong
`\\end`, a `\\ref` to a label nobody declared, a `tabular` row with one column too
many, an `\\includegraphics` naming a file that is not there. Those are the
failures that cost a round trip to find, and every one of them is decidable from
the text.

The line between this module and a compile is worth stating, because a check that
is mistaken for a stronger one is worse than no check. This module cannot see an
overfull box, a font substitution, a float that lands three pages from its
reference, a bibliography style error, or anything else that only exists once TeX
has run. A pass here means the source is structurally sound, not that the PDF is
right.

Two design choices follow from the paper's own history of false positives:

1. Inline math legally spans lines, so `$` parity is checked per blank-line
   separated block and never per line. Checking per line reports four failures on
   a file that compiles.
2. A column spec is read with brace matching and `\\multicolumn` spans are added
   back, because `p{3.2cm}` and `\\multicolumn{3}{c}{...}` each break the naive
   count in opposite directions.

Findings are split into failures and notes. A failure is something that stops a
compile or silently renders wrong. A note is something worth a human's eye that
is not by itself an error — a label nothing references, a macro this module does
not recognise.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple

#: Control sequences this module knows about. Anything outside it is reported as a
#: note, not a failure: the list is a reading aid for the author, not a claim to
#: know every macro LaTeX defines. Commands defined in main.tex or in the style
#: file are resolved from those files instead of from here.
KNOWN_MACROS = frozenset("""
documentclass usepackage newcommand renewcommand def newtheorem begin end
section subsection subsubsection paragraph label ref eqref autoref pageref cite
shortcite citeauthor citeyear item textbf textit emph texttt textsc text
footnote caption centering includegraphics graphicspath toprule midrule
bottomrule cmidrule multicolumn multirow frac tfrac dfrac sum prod min max log
exp mathbb mathcal mathrm mathbf mathit mathsf operatorname arg star colon
leq geq neq approx equiv times cdot cdots ldots dots big bigl bigr Big Bigl
Bigr le ge ll gg in notin subset subseteq cup cap emptyset forall exists
alpha beta gamma delta epsilon varepsilon zeta eta theta iota kappa lambda mu
nu xi pi rho sigma tau upsilon phi varphi chi psi omega Gamma Delta Theta
Lambda Xi Pi Sigma Upsilon Phi Psi Omega infty partial nabla
left right quad qquad hspace vspace medskip smallskip bigskip noindent par
title author maketitle abstract bibliographystyle bibliography pdfinfo
pdfpagewidth pdfpageheight urlstyle linenumbers url href hidelinks appendix
and thanks affiliations setlength tabcolsep arraystretch
scriptsize footnotesize small normalsize large Large LARGE huge Huge
today linewidth textwidth columnwidth hfill vfill proof qedhere theoremstyle
protect relax newline
""".split())

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper" / "main.tex"


class Report(NamedTuple):
    """Everything the check found, split by whether it blocks a compile."""

    failures: tuple[str, ...]
    notes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures

    def describe(self) -> str:
        if self.ok:
            return "no compile-blocking defect found"
        return "; ".join(self.failures)


def strip_comments(text: str) -> str:
    """Drop LaTeX comments, respecting `\\%`.

    Done by hand rather than with a regex because the escape matters: a `\\%` in a
    caption is a percent sign, and treating it as a comment start would silently
    delete the rest of the line and change every count downstream.
    """
    out = []
    for line in text.split("\n"):
        buf, i = [], 0
        while i < len(line):
            if line[i] == "\\" and i + 1 < len(line):
                buf.append(line[i:i + 2])
                i += 2
                continue
            if line[i] == "%":
                break
            buf.append(line[i])
            i += 1
        out.append("".join(buf))
    return "\n".join(out)


def brace_group(text: str, start: int) -> tuple[str, int]:
    """Contents of the balanced brace group at `text[start]`, and the index past it."""
    if start >= len(text) or text[start] != "{":
        raise ValueError(f"no brace group at index {start}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ValueError("unclosed brace group")


def line_of(text: str, index: int) -> int:
    """1-indexed line number of `index` in `text`."""
    return text.count("\n", 0, index) + 1


def repeated(items) -> list[str]:
    """The values appearing more than once, sorted. Empty when every value is unique."""
    counts = Counter(items)
    return sorted(value for value, n in counts.items() if n > 1)


def blocks(text: str) -> list[tuple[int, str]]:
    """Blank-line separated blocks, each with the line it starts on.

    The unit for math-mode balance. Inline math may wrap across lines, and does in
    this paper, so a per-line `$` parity check reports failures on source that
    compiles.
    """
    found, current, start = [], [], 1
    for i, line in enumerate(text.split("\n"), 1):
        if line.strip():
            if not current:
                start = i
            current.append(line)
        elif current:
            found.append((start, "\n".join(current)))
            current = []
    if current:
        found.append((start, "\n".join(current)))
    return found

class Paper(NamedTuple):
    """A source to check, with the three things outside it that checks resolve against.

    Built from disk by `load` for the real paper, and directly by `from_text` for a
    test that wants one defect and nothing else. Both the style file and the
    bibliography are optional: a check whose external input is absent reports that as
    a note and asserts nothing, because a missing `references.bib` is not evidence
    that a `\\cite` key is wrong.
    """

    body: str                       # comment-stripped LaTeX
    sty: str = ""                   # comment-stripped style file, "" if absent
    bib_keys: frozenset[str] | None = None   # None when there is no bibliography
    graphics_root: Path | None = None        # None disables the graphics check
    name: str = "<text>"


def load(paper: Path = PAPER) -> Paper:
    """The committed paper, with `ijcai26.sty` and `references.bib` alongside it."""
    src = strip_comments(paper.read_text(encoding="utf-8"))
    sty_path = paper.parent / "ijcai26.sty"
    sty = (strip_comments(sty_path.read_text(encoding="utf-8"))
           if sty_path.exists() else "")
    bib_path = paper.parent / "references.bib"
    keys: frozenset[str] | None = None
    if bib_path.exists():
        keys = frozenset(re.findall(r"@\w+\s*\{\s*([^,\s]+)",
                                    bib_path.read_text(encoding="utf-8")))
    return Paper(body=src, sty=sty, bib_keys=keys, graphics_root=paper.parent,
                 name=paper.name)


def from_text(body: str, *, sty: str = "", bib_keys: frozenset[str] | None = None,
              graphics_root: Path | None = None, name: str = "<text>") -> Paper:
    """A `Paper` from a fragment, comments stripped the same way `load` strips them."""
    return Paper(body=strip_comments(body), sty=strip_comments(sty),
                 bib_keys=bib_keys, graphics_root=graphics_root, name=name)


def defined_macros(paper: Paper) -> tuple[frozenset[str], frozenset[str]]:
    """Command names defined in the source, and those defined in the style file."""
    own = re.findall(r"\\(?:newcommand|renewcommand|def)\s*\{?\\([A-Za-z@]+)",
                     paper.body)
    sty = re.findall(r"\\(?:newcommand|renewcommand|def|let)\s*\{?\\([A-Za-z@]+)",
                     paper.sty)
    return frozenset(own), frozenset(sty)

def check_environments(paper: Paper) -> tuple[list[str], list[str]]:
    """Every `\\begin` closed by the matching `\\end`, in order.

    A stack rather than a count, because the count is right in the two cases that
    break a compile: `\\begin{table} \\begin{tabular} \\end{table} \\end{tabular}`
    balances and does not compile.
    """
    failures: list[str] = []
    stack: list[tuple[str, int]] = []
    for i, line in enumerate(paper.body.split("\n"), 1):
        for kind, name in re.findall(r"\\(begin|end)\{([^}]+)\}", line):
            if kind == "begin":
                stack.append((name, i))
            elif not stack:
                failures.append(f"L{i}: \\end{{{name}}} with nothing open")
            elif stack[-1][0] != name:
                opened, at = stack.pop()
                failures.append(f"L{i}: \\end{{{name}}} closes "
                                f"\\begin{{{opened}}} opened at L{at}")
            else:
                stack.pop()
    if stack:
        failures.append("never closed: "
                        + ", ".join(f"{n} at L{i}" for n, i in stack))
    return failures, []


def check_preamble(paper: Paper) -> tuple[list[str], list[str]]:
    """Packages, theorem environments and command definitions, against the style file.

    The three failures here are the ones that make TeX stop on line 1 of the log and
    are invisible to a reader of the source: a package loaded twice, a package the
    style file already loaded, and a `\\newcommand` for a name the style file has
    already taken — `\\newcommand` errors rather than overwriting.
    """
    failures: list[str] = []
    notes: list[str] = []

    groups = re.findall(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}", paper.body)
    packages = [p.strip() for group in groups for p in group.split(",")]
    twice = repeated(packages)
    if twice:
        failures.append(f"double-loaded packages: {twice}")

    sty_groups = re.findall(
        r"\\(?:RequirePackage|usepackage)(?:\[[^\]]*\])?\{([^}]+)\}", paper.sty)
    sty_packages = {p.strip() for group in sty_groups for p in group.split(",")}
    clash = sorted(set(packages) & sty_packages)
    if clash:
        failures.append(f"loaded by both the source and the style file: {clash}")
    notes.append(f"packages the style file loads: {sorted(sty_packages) or 'none'}")

    theorems = re.findall(r"\\newtheorem\{([^}]+)\}", paper.body)
    twice = repeated(theorems)
    if twice:
        failures.append(f"duplicate \\newtheorem: {twice}")
    for name in dict.fromkeys(theorems):
        if re.search(r"\\newtheorem\{" + re.escape(name) + r"\}", paper.sty):
            failures.append(
                f"\\newtheorem{{{name}}} is also defined in the style file")
        if not re.search(r"\\begin\{" + re.escape(name) + r"\}", paper.body):
            notes.append(f"\\newtheorem{{{name}}} declared but never used")

    own, sty_defined = defined_macros(paper)
    shadowed = sorted({n for n in re.findall(
        r"\\newcommand\s*\{?\\([A-Za-z@]+)", paper.body) if n in sty_defined})
    if shadowed:
        failures.append(
            f"\\newcommand redefines a style-file command: {shadowed}")
    notes.append(f"{len(own)} command(s) defined in the source")
    return failures, notes

def check_labels(paper: Paper) -> tuple[list[str], list[str]]:
    """Labels declared once each, and every reference pointing at one of them.

    A dangling `\\ref` does not stop a compile — it renders `??` and warns — but it
    is the defect this whole module was written to catch, because the warning scrolls
    past and the `??` reaches a reader. It is reported as a failure for that reason.
    A label nothing references is a note: harmless, and often the author's intent.
    """
    labels = re.findall(r"\\label\{([^}]+)\}", paper.body)
    failures, notes = [], []
    twice = repeated(labels)
    if twice:
        failures.append(f"duplicate labels: {twice}")
    refs = set(re.findall(r"\\(?:ref|autoref|eqref|pageref)\{([^}]+)\}", paper.body))
    dangling = sorted(refs - set(labels))
    if dangling:
        failures.append(f"references to labels that are never declared: {dangling}")
    unreferenced = sorted(set(labels) - refs)
    if unreferenced:
        notes.append(f"labels never referenced: {unreferenced}")
    notes.append(f"{len(set(labels))} label(s), {len(refs)} distinct reference(s)")
    return failures, notes


def check_citations(paper: Paper) -> tuple[list[str], list[str]]:
    """Every cited key present in the bibliography.

    Skipped, with a note, when there is no bibliography to check against: absence of
    the file is not evidence about the keys.
    """
    cited: set[str] = set()
    for group in re.findall(
            r"\\(?:cite|shortcite|citeauthor|citeyear)\{([^}]+)\}", paper.body):
        cited |= {key.strip() for key in group.split(",")}
    if paper.bib_keys is None:
        return [], [f"no bibliography alongside {paper.name}; "
                    f"{len(cited)} cited key(s) unchecked"]
    missing = sorted(cited - paper.bib_keys)
    failures = ([f"cited keys absent from the bibliography: {missing}"]
                if missing else [])
    notes = [f"{len(cited)} key(s) cited, {len(paper.bib_keys)} in the bibliography, "
             f"{len(paper.bib_keys - cited)} uncited"]
    return failures, notes


#: Extensions LaTeX will supply itself when the target names none. A target that
#: already carries one of these is loaded as written — `\\includegraphics{fig.pdf}` is
#: not satisfied by `fig.png` sitting beside it, which is a distinction this module got
#: wrong once and reported a missing figure as present because a stale `.png` was there.
GRAPHICS_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps")


def resolve_graphic(paper: Paper, target: str) -> Path | None:
    """The file an `\\includegraphics{target}` would load, or None if there is none.

    The extension is optional in LaTeX, so a target without one is tried with each of
    `GRAPHICS_EXTENSIONS`, under each `\\graphicspath` prefix and then unprefixed. A
    target that names its own extension is only ever tried as written.
    """
    if paper.graphics_root is None:
        return None
    named = Path(target).suffix.lower() in GRAPHICS_EXTENSIONS
    for prefix in [*re.findall(r"\\graphicspath\{\{([^}]*)\}\}", paper.body), ""]:
        base = paper.graphics_root / prefix / target
        candidates = ((base,) if named
                      else (base, *(base.with_suffix(ext)
                                    for ext in GRAPHICS_EXTENSIONS)))
        for candidate in candidates:
            if candidate.exists():
                return candidate
    return None


def included_graphics(paper: Paper) -> list[str]:
    """Every `\\includegraphics` target, in source order."""
    return re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", paper.body)


def check_graphics(paper: Paper) -> tuple[list[str], list[str]]:
    """Every `\\includegraphics` target resolvable, through `\\graphicspath`.

    A compile fails outright on a missing graphic, and nothing else here notices the
    absence of a file. This is the check that caught the figure the repository claimed
    to commit and had not.

    What it checks is the working tree, which is not the same question as whether a
    fresh clone can compile — an untracked file satisfies it. That second question
    needs git, which this module deliberately does not know about; it is asked by
    `test_paper_preflight.test_every_graphic_the_paper_needs_is_tracked_by_git`.
    """
    if paper.graphics_root is None:
        return [], ["graphics targets unchecked: no directory to resolve against"]
    search = re.findall(r"\\graphicspath\{\{([^}]*)\}\}", paper.body)
    failures = []
    included = included_graphics(paper)
    for target in included:
        if resolve_graphic(paper, target) is None:
            failures.append(f"\\includegraphics{{{target}}}: no such file "
                            f"(graphicspath {search or 'unset'})")
    return failures, [f"{len(included)} graphic(s) included"]

def check_math(paper: Paper) -> tuple[list[str], list[str]]:
    """Brace balance file-wide, `$` parity per block, and `\\[` against `\\]`.

    The unit for `$` is a blank-line separated block, not a line. Inline math may
    wrap, and does in this paper — a per-line parity check reported four failures on
    a source that compiles, which is how this rule came to be written down. `$$` is
    removed before counting so that a display pair does not read as two openings, and
    an escaped `\\$` is removed because it is a dollar sign.
    """
    failures = []
    depth = 0
    for line in paper.body.split("\n"):
        plain = re.sub(r"\\[{}$]", "", line)
        depth += plain.count("{") - plain.count("}")
    if depth:
        failures.append(f"brace imbalance over the whole file: {depth:+d}")

    for start, block in blocks(paper.body):
        plain = re.sub(r"\\\$", "", block).replace("$$", "")
        if plain.count("$") % 2:
            failures.append(f"L{start}: odd number of $ in the block starting here")

    opens, closes = paper.body.count("\\["), paper.body.count("\\]")
    if opens != closes:
        failures.append(f"\\[ appears {opens} time(s) and \\] {closes}")
    return failures, []


def check_tabulars(paper: Paper) -> tuple[list[str], list[str]]:
    """Every `tabular` row holding as many cells as the column spec declares.

    The spec is read with `brace_group` rather than a regex, because `p{3.2cm}` ends
    the naive `\\{([^}]*)\\}` match at the inner brace and truncates the spec — six
    false failures on one table, historically. Column letters are counted after inner
    groups are removed, `p{` is added back, and each `\\multicolumn{n}` in a row
    contributes `n - 1` beyond its own separator. Rule rows carry no cells and are
    dropped before counting.
    """
    failures = []
    counted = 0
    for match in re.finditer(r"\\begin\{tabular\}", paper.body):
        try:
            spec, after = brace_group(paper.body, match.end())
        except ValueError as exc:
            failures.append(f"L{line_of(paper.body, match.end())}: "
                            f"unreadable column spec ({exc})")
            continue
        columns = (len(re.findall(r"[lcr]", re.sub(r"\{[^{}]*\}", "", spec)))
                   + len(re.findall(r"p\{", spec)))
        end = paper.body.find("\\end{tabular}", after)
        if end < 0:
            continue        # check_environments owns the unclosed case
        at = line_of(paper.body, match.start())
        counted += 1
        for i, row in enumerate(paper.body[after:end].split("\\\\")):
            bare = re.sub(r"\\(?:top|mid|bottom)rule", "", row)
            bare = re.sub(r"\\cmidrule(?:\([lr]+\))?\{[^}]*\}", "", bare).strip()
            if not bare:
                continue
            cells = len(re.findall(r"(?<!\\)&", bare)) + 1
            for span in re.findall(r"\\multicolumn\{(\d+)\}", bare):
                cells += int(span) - 1
            if cells != columns:
                failures.append(
                    f"tabular at L{at}: spec '{spec}' declares {columns} column(s), "
                    f"row {i} has {cells}: {bare[:60]}")
    return failures, [f"{counted} tabular(s) checked"]

def check_macros(paper: Paper) -> tuple[list[str], list[str]]:
    """Control sequences that are neither whitelisted nor defined anywhere visible.

    Notes only, never failures. This module does not know what LaTeX defines, so an
    unrecognised name is a request for a human's eye and not a verdict. It earns its
    place because the one thing it does catch — a typo in a command name — is
    otherwise a compile error with an unhelpful message.
    """
    own, sty_defined = defined_macros(paper)
    used = Counter(re.findall(r"\\([A-Za-z@]+)", paper.body))
    environments = set(re.findall(r"\\(?:begin|end)\{([^}]+)\}", paper.body))
    unknown = sorted(name for name in used
                     if name not in KNOWN_MACROS and name not in own
                     and name not in sty_defined and name not in environments)
    if not unknown:
        return [], []
    return [], ["control sequences not in the whitelist (eyeball these): "
                + ", ".join(f"\\{name} x{used[name]}" for name in unknown)]


def check_floats(paper: Paper) -> tuple[list[str], list[str]]:
    """Every `table` and `figure` carrying a `\\label`, declared after its `\\caption`.

    A float without a label cannot be referenced, which in a paper that references all
    of its floats means the reference was meant to exist. A label *before* the caption
    is a note rather than a failure: it compiles, and it numbers whatever counter was
    current at the time, which is usually not the float.
    """
    failures, notes = [], []
    for match in re.finditer(r"\\begin\{(table|figure)\}", paper.body):
        kind = match.group(1)
        end = paper.body.find("\\end{" + kind + "}", match.end())
        if end < 0:
            continue        # check_environments owns the unclosed case
        segment = paper.body[match.end():end]
        at = line_of(paper.body, match.start())
        if "\\label" not in segment:
            failures.append(f"{kind} float at L{at} has no \\label")
        elif ("\\caption" in segment
              and segment.index("\\label") < segment.index("\\caption")):
            notes.append(f"{kind} float at L{at}: \\label precedes \\caption, "
                         "so the number it captures can be the wrong one")
    return failures, notes


#: Run in this order, so that the report reads outward from the structure of the file
#: to its contents. `check_environments` is first because several later checks say
#: "that case belongs to check_environments" and rely on it having spoken.
CHECKS = (
    check_environments,
    check_preamble,
    check_labels,
    check_citations,
    check_graphics,
    check_math,
    check_tabulars,
    check_macros,
    check_floats,
)


def preflight(paper: Paper | Path | None = None) -> Report:
    """Every check, over one source. A `Path` or nothing is loaded from disk first."""
    if paper is None:
        paper = load()
    elif isinstance(paper, Path):
        paper = load(paper)
    failures: list[str] = []
    notes: list[str] = []
    for check in CHECKS:
        found, said = check(paper)
        failures += found
        notes += said
    return Report(tuple(failures), tuple(notes))


def assert_clean(paper: Paper | Path | None = None) -> Report:
    """`preflight` with no failures. Raises AssertionError naming every one it found."""
    report = preflight(paper)
    if not report.ok:
        raise AssertionError(
            f"{len(report.failures)} compile-blocking defect(s) in the LaTeX source:\n"
            + "\n".join(f"  - {f}" for f in report.failures))
    return report


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else PAPER
    result = preflight(target)
    print(f"{target}: {'PASS' if result.ok else 'FAIL'}")
    for failure in result.failures:
        print("  fail:", failure)
    for note in result.notes:
        print("  note:", note)
    raise SystemExit(0 if result.ok else 1)
