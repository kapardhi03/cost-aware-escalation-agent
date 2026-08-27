"""
Guards on `tests/paper_preflight.py`: the checks fire, and they fire only when they
should.

The module they test stands in for a compile that cannot run here, which makes both
halves of its behaviour load-bearing. A check that misses a dangling `\\ref` sends a
`??` into a PDF. A check that reports a failure on source that compiles is worse: it
trains its reader to ignore the output, and this module has already done that once —
four of its first eleven failures were legal inline math spanning two lines, and one
was a `\\multicolumn` row it could not count.

So every defect class gets a negative control that must be caught, and every false
positive from that first run gets a positive control that must stay quiet: math over
two lines, a `\\multicolumn` span, a `p{}` column, an escaped `\\%`, an escaped brace.

The committed `paper/main.tex` is the other positive control, and the strongest one:
it is a real 1400-line document with four tables, a theorem, nineteen labels and five
citations, and it must come back clean. What that does *not* establish is that the
paper compiles — no TeX runs in this environment. It establishes that no defect a
parser can name is present.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import paper_preflight
from paper_preflight import from_text, preflight

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper" / "main.tex"


def failures(source: str, **kwargs) -> tuple[str, ...]:
    """The failures a fragment produces, with the external inputs left absent."""
    return preflight(from_text(source, **kwargs)).failures


def notes(source: str, **kwargs) -> tuple[str, ...]:
    return preflight(from_text(source, **kwargs)).notes


def only_failure(source: str, **kwargs) -> str:
    """The single failure a fragment produces. Fails if it produces none, or several."""
    found = failures(source, **kwargs)
    assert len(found) == 1, f"expected exactly one failure, got {found}"
    return found[0]


# --------------------------------------------------------------------------- #
# The committed paper
# --------------------------------------------------------------------------- #

def test_the_committed_paper_has_no_structural_defect():
    """The check that pays for the module: run before every Overleaf round trip.

    A failure here names the defect and the line. It does not mean the paper fails to
    compile for only that reason — it means a parser can already see this one.
    """
    paper_preflight.assert_clean(PAPER)


def test_the_committed_paper_declares_and_uses_its_theorem_environment():
    """`\\newtheorem{theorem}` is the one preamble line the tracked v1 PDF cannot vouch
    for, so the source is asked directly whether it is declared once and used."""
    report = preflight(PAPER)
    assert not any("newtheorem" in note for note in report.notes), (
        f"the theorem environment is declared but unused: {report.notes}")


def test_the_committed_papers_only_graphic_is_present():
    """The failure this module first caught: `\\includegraphics` naming a file that the
    repository claimed to commit and had not."""
    paper = paper_preflight.load(PAPER)
    found, _ = paper_preflight.check_graphics(paper)
    assert not found, found


def test_every_reference_in_the_committed_paper_resolves():
    paper = paper_preflight.load(PAPER)
    found, _ = paper_preflight.check_labels(paper)
    assert not found, found


# --------------------------------------------------------------------------- #
# Environments
# --------------------------------------------------------------------------- #

def test_an_unclosed_environment_is_caught():
    assert "never closed" in only_failure("\\begin{itemize}\n\\item one\n")


def test_an_end_with_nothing_open_is_caught():
    assert "nothing open" in only_failure("text\n\\end{itemize}\n")


def test_crossed_nesting_is_caught():
    """This is why the check keeps a stack. The counts here balance perfectly."""
    source = ("\\begin{table}\n\\begin{center}\n\\end{table}\n\\end{center}\n")
    found = failures(source)
    assert any("closes" in f for f in found), found


def test_correct_nesting_is_quiet():
    source = ("\\begin{table}\n\\begin{center}\ntext\n\\end{center}\n"
              "\\label{tab:x}\n\\caption{c}\n\\end{table}\n\\ref{tab:x}\n")
    found, _ = paper_preflight.check_environments(from_text(source))
    assert not found, found


# --------------------------------------------------------------------------- #
# Preamble
# --------------------------------------------------------------------------- #

def test_a_double_loaded_package_is_caught():
    source = "\\usepackage{amsmath}\n\\usepackage[utf8]{inputenc}\n\\usepackage{amsmath}\n"
    assert "amsmath" in only_failure(source)


def test_a_package_in_a_comma_list_counts_as_loaded():
    """`\\usepackage{a,b}` then `\\usepackage{b}` is the same clash, spelled shorter."""
    assert "amssymb" in only_failure("\\usepackage{amsmath,amssymb}\n"
                                     "\\usepackage{amssymb}\n")


def test_a_package_the_style_file_already_loaded_is_caught():
    source = "\\usepackage{ijcai26}\n\\usepackage{xcolor}\n"
    assert "xcolor" in only_failure(source, sty="\\RequirePackage{xcolor}\n")


def test_a_package_the_style_file_loads_in_a_comment_is_not_a_clash():
    """The style file is comment-stripped too, or every commented example clashes."""
    source = "\\usepackage{xcolor}\n"
    assert not failures(source, sty="% \\RequirePackage{xcolor}\n")


def test_a_duplicate_newtheorem_is_caught():
    source = ("\\newtheorem{theorem}{Theorem}\n\\newtheorem{theorem}{Thm}\n"
              "\\begin{theorem}\nx\n\\end{theorem}\n")
    assert "theorem" in only_failure(source)


def test_a_newtheorem_the_style_file_already_defines_is_caught():
    """The collision the author feared before the first compile. Statically decidable:
    it fires when, and only when, the style file declares the same name."""
    source = "\\newtheorem{theorem}{Theorem}\n\\begin{theorem}\nx\n\\end{theorem}\n"
    assert "style file" in only_failure(source, sty="\\newtheorem{theorem}{Thm}\n")


def test_a_newtheorem_the_style_file_leaves_alone_is_quiet():
    source = "\\newtheorem{theorem}{Theorem}\n\\begin{theorem}\nx\n\\end{theorem}\n"
    assert not failures(source, sty="\\newcommand{\\ijcaipaperid}[1]{}\n")


def test_a_declared_but_unused_theorem_environment_is_a_note_not_a_failure():
    source = "\\newtheorem{lemma}{Lemma}\n"
    assert not failures(source)
    assert any("never used" in note for note in notes(source))


def test_a_newcommand_shadowing_a_style_file_command_is_caught():
    """`\\newcommand` on a name that already exists is an error, not an override."""
    source = "\\newcommand{\\keywords}[1]{#1}\n"
    assert "keywords" in only_failure(source, sty="\\newcommand{\\keywords}[1]{}\n")


def test_a_renewcommand_over_a_style_file_command_is_allowed():
    """The distinction is real: `\\renewcommand` is how a style command is overridden,
    so flagging it would flag the correct spelling of the intent."""
    source = "\\renewcommand{\\keywords}[1]{#1}\n"
    assert not failures(source, sty="\\newcommand{\\keywords}[1]{}\n")


# --------------------------------------------------------------------------- #
# Labels, references, citations
# --------------------------------------------------------------------------- #

def test_a_duplicate_label_is_caught():
    """Two labels with one name renders the wrong number at one of the two call sites,
    and warns rather than stopping — so it reaches the PDF unless something asks."""
    source = "\\label{sec:x}\ntext\n\\label{sec:x}\n\\ref{sec:x}\n"
    assert "sec:x" in only_failure(source)


def test_a_dangling_reference_is_caught():
    source = "\\label{sec:x}\nsee \\ref{sec:y}\n\\ref{sec:x}\n"
    assert "sec:y" in only_failure(source)


def test_autoref_and_eqref_count_as_references():
    source = "\\label{eq:a}\\label{sec:b}\n\\eqref{eq:a} \\autoref{sec:c}\n"
    assert "sec:c" in only_failure(source)


def test_an_unreferenced_label_is_a_note_not_a_failure():
    """Two of the paper's own labels are like this, on purpose."""
    source = "\\label{sec:intro}\ntext\n"
    assert not failures(source)
    assert any("never referenced" in note for note in notes(source))


def test_a_cited_key_absent_from_the_bibliography_is_caught():
    source = "text \\cite{kaelbling1998}\n"
    assert "kaelbling1998" in only_failure(source, bib_keys=frozenset({"sutton1998"}))


def test_a_multi_key_citation_is_split():
    source = "text \\cite{a,b}\n"
    assert "'b'" in only_failure(source, bib_keys=frozenset({"a"}))


def test_citations_are_unchecked_when_there_is_no_bibliography():
    """Absence of the file says nothing about the keys, so it must not fail."""
    source = "text \\cite{whatever}\n"
    assert not failures(source)
    assert any("no bibliography" in note for note in notes(source))


# --------------------------------------------------------------------------- #
# Graphics
# --------------------------------------------------------------------------- #

def test_a_missing_graphic_is_caught(tmp_path):
    source = "\\includegraphics[width=\\columnwidth]{figures/absent}\n"
    assert "absent" in only_failure(source, graphics_root=tmp_path)


def test_a_graphic_found_through_graphicspath_is_quiet(tmp_path):
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "plot.pdf").write_bytes(b"%PDF-1.4\n")
    source = ("\\graphicspath{{figures/}}\n"
              "\\includegraphics[width=\\columnwidth]{plot}\n")
    assert not failures(source, graphics_root=tmp_path)


def test_an_extensionless_target_resolves_to_pdf_or_png(tmp_path):
    """LaTeX picks the extension, so a bare name must be tried both ways."""
    (tmp_path / "plot.png").write_bytes(b"\x89PNG\r\n")
    assert not failures("\\includegraphics{plot}\n", graphics_root=tmp_path)


def test_a_target_naming_pdf_is_not_satisfied_by_a_png_beside_it(tmp_path):
    """The bug this module shipped for one run: `\\includegraphics{fig.pdf}` loads
    `fig.pdf` and nothing else, so a stale `.png` from an earlier render must not make a
    missing figure look present. It did, and the paper's own target names `.pdf`."""
    (tmp_path / "plot.png").write_bytes(b"\x89PNG\r\n")
    assert "plot.pdf" in only_failure("\\includegraphics{plot.pdf}\n",
                                      graphics_root=tmp_path)


def test_graphics_are_unchecked_when_there_is_no_directory():
    source = "\\includegraphics{plot}\n"
    assert not failures(source)
    assert any("no directory" in note for note in notes(source))


def test_every_graphic_the_paper_needs_is_tracked_by_git():
    """The clean-clone criterion, which the check above cannot ask.

    `check_graphics` resolves against the working tree, so an untracked file satisfies
    it — and because LaTeX picks the extension, a stray `.png` left behind by a render
    satisfies it even when the `.pdf` the repository claims to commit is gone. That is
    the exact state this test was written in. A fresh clone gets only what git tracks,
    so that is what is asked here.
    """
    paper = paper_preflight.load(PAPER)
    targets = paper_preflight.included_graphics(paper)
    assert targets, "the paper includes no graphics; this test has nothing to check"
    tracked = git_tracked_paths()
    if tracked is None:
        pytest.skip("git could not list tracked files")
    missing = []
    for target in targets:
        resolved = paper_preflight.resolve_graphic(paper, target)
        if resolved is None or resolved.resolve() not in tracked:
            missing.append(f"{target} -> {resolved}")
    assert not missing, (
        "a fresh clone cannot compile the paper: these \\includegraphics targets "
        f"resolve to nothing git tracks: {missing}. The rendered figure is committed "
        "on purpose — see README step 5 and the un-ignore in .gitignore — because it "
        "needs matplotlib, which nothing else here depends on.")


def git_tracked_paths() -> frozenset[Path] | None:
    """Absolute paths git tracks under the project, or None if git cannot answer."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return frozenset((ROOT / name).resolve()
                     for name in out.stdout.split("\0") if name)


# --------------------------------------------------------------------------- #
# Braces and math mode
# --------------------------------------------------------------------------- #

def test_a_brace_imbalance_is_caught():
    assert "brace imbalance" in only_failure("\\textbf{unclosed\n")


def test_an_escaped_brace_does_not_count():
    """A literal `\\{` in math is not a group. Counting it as one reports a file that
    compiles."""
    assert not failures("the set $\\{1, 2\\}$ is finite\n")


def test_an_odd_dollar_in_a_block_is_caught():
    source = "the value $b_h is three thirteenths\n\nnext block\n"
    assert "odd number of $" in only_failure(source)


def test_inline_math_spanning_two_lines_is_quiet():
    """Four of this module's first eleven failures were exactly this, and the paper
    compiles. The unit of the parity check is the block, and this test is the reason."""
    source = ("the bound $c_F/\\nu +\n"
              "c_T/\\alpha < 1$ holds\n")
    assert not failures(source)


def test_the_block_boundary_is_the_blank_line_not_the_paragraph_break():
    """Two blocks, each individually balanced, must not be pooled — pooling would let
    one stray `$` in each cancel the other out."""
    source = "first $x$ and $y\n\nsecond $z\n"
    found = failures(source)
    assert len(found) == 2, found


def test_an_escaped_dollar_does_not_count():
    assert not failures("a \\$5 cost\n")


def test_a_display_pair_does_not_read_as_two_openings():
    assert not failures("$$x = 1$$\n")


def test_mismatched_display_math_delimiters_are_caught():
    assert "\\[ appears" in only_failure("\\[ x = 1\n")


def test_a_percent_in_a_caption_is_not_a_comment():
    """`\\%` is a percent sign. Treating it as a comment start deletes the rest of the
    line and every count downstream is then wrong — including the brace balance."""
    source = "\\caption{a 95\\% interval on $x$}\n"
    assert not failures(source)


def test_a_real_comment_is_stripped():
    """A commented-out `\\begin` must not be reported as unclosed."""
    assert not failures("% \\begin{itemize}\ntext\n")


# --------------------------------------------------------------------------- #
# Tabulars
# --------------------------------------------------------------------------- #

def tabular(spec: str, *rows: str) -> str:
    body = "\n".join(rows)
    return f"\\begin{{tabular}}{{{spec}}}\n{body}\n\\end{{tabular}}\n"


def test_a_row_with_one_cell_too_many_is_caught():
    source = tabular("lrr", "a & 1 & 2 \\\\", "b & 3 & 4 & 5 \\\\")
    assert "declares 3 column(s)" in only_failure(source)


def test_a_row_with_one_cell_too_few_is_caught():
    source = tabular("lrr", "a & 1 & 2 \\\\", "b & 3 \\\\")
    assert "row 1 has 2" in only_failure(source)


def test_a_matching_table_is_quiet():
    source = tabular("lrr", "\\toprule", "a & 1 & 2 \\\\", "\\midrule",
                     "b & 3 & 4 \\\\", "\\bottomrule")
    assert not failures(source)


def test_a_multicolumn_span_is_counted():
    """One of the first run's false failures: a `\\multicolumn{3}` row is three cells
    wide and holds one separator."""
    source = tabular("lrrr", "\\multicolumn{4}{c}{heading} \\\\",
                     "a & 1 & 2 & 3 \\\\")
    assert not failures(source)


def test_a_multicolumn_span_of_the_wrong_width_is_still_caught():
    """The span arithmetic must not become a way for any row to pass."""
    source = tabular("lrrr", "\\multicolumn{2}{c}{heading} \\\\",
                     "a & 1 & 2 & 3 \\\\")
    assert "row 0 has 2" in only_failure(source)


def test_a_p_column_is_counted_once():
    """Six of the first run's false failures came from a spec regex that stopped at the
    inner brace of `p{3.2cm}` and read `lr p{3.2cm}` as `lr p`."""
    source = tabular("lr p{3.2cm}", "a & 1 & note \\\\", "b & 2 & other \\\\")
    assert not failures(source)


def test_a_cmidrule_row_carries_no_cells():
    source = tabular("lrr", "a & 1 & 2 \\\\", "\\cmidrule(lr){2-3}",
                     "b & 3 & 4 \\\\")
    assert not failures(source)


def test_an_escaped_ampersand_is_not_a_separator():
    source = tabular("ll", "R\\&D & yes \\\\")
    assert not failures(source)


# --------------------------------------------------------------------------- #
# Floats and the macro scan
# --------------------------------------------------------------------------- #

def test_a_float_without_a_label_is_caught():
    source = "\\begin{table}\n\\caption{c}\ntext\n\\end{table}\n"
    assert "no \\label" in only_failure(source)


def test_a_label_before_the_caption_is_a_note_not_a_failure():
    """It compiles. It numbers the wrong counter, which a human has to judge."""
    source = ("\\begin{figure}\n\\label{fig:x}\n\\caption{c}\n\\end{figure}\n"
              "\\ref{fig:x}\n")
    assert not failures(source)
    assert any("precedes" in note for note in notes(source))


def test_a_well_formed_float_is_quiet():
    source = ("\\begin{table}\n\\caption{c}\n\\label{tab:x}\n\\end{table}\n"
              "\\ref{tab:x}\n")
    assert not failures(source)


def test_an_unrecognised_control_sequence_is_a_note_not_a_failure():
    """The whitelist is a reading aid, not a claim to know every macro LaTeX defines,
    so it may never fail a check — a typo and a package command look the same here."""
    source = "\\definitelynotarealmacro{x}\n"
    assert not failures(source)
    assert any("definitelynotarealmacro" in note for note in notes(source))


def test_a_macro_the_source_defines_is_not_reported():
    source = "\\newcommand{\\vact}{V_{\\mathrm{act}}}\n$\\vact(b)$\n"
    assert not any("vact" in note for note in notes(source))


def test_a_macro_the_style_file_defines_is_not_reported():
    source = "\\affiliations\nx\n"
    assert not any("affiliations" in note for note in notes(
        source, sty="\\newcommand{\\affiliations}{}\n"))


# --------------------------------------------------------------------------- #
# The report itself
# --------------------------------------------------------------------------- #

def test_assert_clean_raises_and_names_every_failure():
    """The message is the whole value of the check when it fires, so it is tested."""
    paper = from_text("\\ref{sec:missing}\n\\textbf{unclosed\n")
    with pytest.raises(AssertionError) as excinfo:
        paper_preflight.assert_clean(paper)
    message = str(excinfo.value)
    assert "sec:missing" in message and "brace imbalance" in message


def test_assert_clean_returns_the_report_when_it_passes():
    report = paper_preflight.assert_clean(from_text("text\n"))
    assert report.ok and report.failures == ()


def test_a_clean_report_describes_itself_as_clean():
    assert preflight(from_text("text\n")).describe() == (
        "no compile-blocking defect found")


def test_notes_never_make_a_report_fail():
    """Every note-only class at once: an unreferenced label, an unknown macro, a label
    before a caption, an unused theorem environment."""
    source = ("\\newtheorem{lemma}{Lemma}\n\\label{sec:unref}\n"
              "\\madeupmacro{x}\n"
              "\\begin{figure}\n\\label{fig:y}\n\\caption{c}\n\\end{figure}\n"
              "\\ref{fig:y}\n")
    report = preflight(from_text(source))
    assert report.ok, report.failures
    assert len(report.notes) >= 4, report.notes


def test_every_check_is_registered():
    """A check written and never added to `CHECKS` runs nowhere. This catches that."""
    written = {name for name in vars(paper_preflight) if name.startswith("check_")}
    registered = {check.__name__ for check in paper_preflight.CHECKS}
    assert written == registered, written ^ registered
