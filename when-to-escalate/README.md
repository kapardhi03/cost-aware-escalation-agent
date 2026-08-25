# When to Escalate - Project

## Paper

**When to Escalate: A Cost-Aware Belief Policy for Conversational Agents Under
Hidden Intent**

## Problem

The agent observes an inbound message from a sales lead. It must select one action
from {`answer`, `ask`, `hold`, `escalate_notify`, `escalate_pause`} because the
lead's true intent and buying-readiness are not known. `ask` is a qualifying
question rather than an answer; `escalate_notify` tells a human while the
conversation continues; `escalate_pause` stops the agent and hands over. The two
escalations are separate actions because they carry different costs (build
decision 25, superseding the original four-action set).

The agent holds a belief over the lead's hidden intent and readiness and chooses
the action with the lowest expected cost, then is compared against a baseline. The
problem is framed as a POMDP but solved with a myopic (one-step) expected-cost
policy over the belief, not full belief-state planning.

## Repository layout

Primary artifacts:

- `research-file.md` — technical terms, search queries, verified communities and
  accounts, five read sources, open questions, the AI prompts used verbatim, and
  the AI errors caught.
- `discussion-record.md` — public-discussion log and the design change (if any)
  each useful reply produced. 14 rows, every one carrying my reply as posted. It
  opens with a `## Corrections` section: one thread was first logged from memory,
  which credited two replies to the wrong commenter and missed two others, and the
  original attributions are recorded rather than quietly swapped.
- `review-record.md` — AI review comments with accept/reject and reason for each,
  over three reviews (practitioner, probability/decision-theory, conference referee):
  23 comments, each with the section it points at as evidence, plus a per-review
  summary.
- `decisions/probability-decision-record.md` — one worked belief-update-to-action
  record for a single case (`a02-deep-018`), including the six-step update.
- `paper/` — LaTeX source (`main.tex`), the IJCAI style files, `references.bib`,
  and `figures/make_figures.py`. The rendered figure is an input to the compile and
  is deliberately not committed; see step 5.
- `src/` — belief update (`belief.py`), configuration (`config.py`), cost model and
  policy (`costs.py`), and the belief providers (`providers/`).
- `data/` — the case generator (`build_cases.py`), the synthetic conversation set
  (`cases.json`), and the committed belief cache (`belief_cache.json`).
- `experiments/` — the test harness (`run_policies.py`) and the robustness and
  sensitivity checks (`robustness.py`).
- `results/` — `run.json` (per-case beliefs, decisions, realised costs), `run.md`
  (the summary tables), `robustness.json` (the sensitivity output), and
  `wrong-decisions.md` (the five-failure analysis). `wrong-decisions.md` carries a
  `## Corrections` section: four claims in it were corrected after the run was
  analysed, and the original wording is struck rather than deleted.
- `social/` — the LinkedIn post and the X thread, both as published. Each file
  opens with the live URL to the posted version.

Supporting working files:

- `build-log.md` — every design decision with its verdict and reason, the open
  questions, the limitations carried into the paper (L1–L9), and the findings
  (F1–F8). Rows are never edited after the fact; a reversal is added as a new row
  that supersedes the old one.
- `PLAN.md` — the day-by-day working plan.
- `tests/` — 337 tests; see step 6.

## How to reproduce the test

No API key is needed and no network call is made. The belief cache in
`data/belief_cache.json` covers all 100 cases, and `BELIEF_CACHE_ONLY=true` serves
every belief from it and **errors on a miss** rather than quietly generating a fresh
one.

Steps 2–5 run from this directory (`when-to-escalate`). Steps 1
and 6 run from the repository root, because the virtualenv and `requirements.txt`
live there; each step says which.

### 1. Environment (from the repository root)

Python 3.11+ (developed on 3.14).

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

Only `pytest` is needed for the tests and `matplotlib` for the figure. The
`openai` / `google-genai` packages are needed only to regenerate beliefs from
scratch, which is not part of reproducing the reported numbers.

### 2. Regenerate the case set (optional — it is committed)

`data/cases.json` is deterministic: seed `20260818`, stratified by archetype and
sub-variant. Writing it to a scratch path and diffing should show no change.

```bash
python3 data/build_cases.py /tmp/cases_check.json && diff /tmp/cases_check.json data/cases.json && echo "IDENTICAL"
```

Verified: prints `IDENTICAL`.

### 3. Run the policies

This is the command behind `results/run.json` and the paper's Table 2. The
`--legacy-tie-break` flag matters: see the note below.

```bash
BELIEF_CACHE_ONLY=true python3 experiments/run_policies.py --legacy-tie-break
```

Writes `results/run.json` (per-case beliefs, decisions, and realised costs) and
`results/run.md` (the summary tables). This reproduces the committed artifacts
exactly, with one expected difference: the `generated_at` timestamp. Every belief,
decision, realised cost, and summary figure is identical. Verified by structural
diff — the only differing key is `.generated_at`.

Expected, on all 100 cases:

| policy | mean cost | missed esc. | precision | recall | violations |
| --- | ---: | ---: | ---: | ---: | ---: |
| cost_aware | 1.72 | 16 | 0.605 | 0.619 | 0 |
| uniform_baseline | 2.58 | 24 | 0.750 | 0.429 | 0 |
| always_notify | 1.74 | 0 | 0.420 | 1.000 | 0 |
| always_ask | 2.84 | 42 | — | 0.000 | 0 |
| always_answer | 3.40 | 34 | 1.000 | 0.190 | 0 |

ECE on the `needs_human` marginal: 0.142 (all), 0.168 (dev), 0.184 (test).

**On `--legacy-tie-break`.** Exact ties in expected cost were originally resolved
in `ACTIONS` order, which resolves toward `answer` — the action with the worst
downside. That is now fixed to resolve safest-first, by worst-case cost. The flag
restores the old behaviour and exists so the committed artifact stays verifiable.
Dropping the flag changes exactly one case (`a11-repeated-097`, `answer` → `hold`)
and gives mean cost **1.65** instead of 1.72; misses and escalations are unchanged
at 16 and 43. Both are correct outputs of the code — the paper reports 1.72 and
says why in its failure analysis. It is also the only decision the flag *could*
change: it is the one case in the 100 where two feasible actions come out at
exactly equal expected cost.

The five worst decisions from this run, with the belief that produced each one, are
written up in `results/wrong-decisions.md`. Read its `## Corrections` section first:
four claims in that file were corrected after the fact, including the framing of
`a11-repeated-097`.

### 4. Robustness and sensitivity checks

Offline, deterministic, reads only `results/run.json`. This is what backs the
sensitivity and calibration-interval claims in the paper.

```bash
python3 experiments/robustness.py --json results/robustness.json
```

The check to read first is `legacy path reproduces results/run.json exactly:
True` — it confirms the committed artifact and the current code agree, which is
what licenses every other number. The script also reports the cost-matrix sweeps,
the bootstrap CI on ECE, the in-sample recalibration result, the action census,
and the reweighting to the design's own readiness prior.

### 5. Regenerate the figure

```bash
python3 paper/figures/make_figures.py
```

Reads `results/run.json`; nothing is transcribed by hand. Writes
`reliability-needs-human.pdf` and `.png` next to the script.

**This has to be run before the paper will compile.** `main.tex` includes the PDF
via `\includegraphics`, and the PDF is not in the repository by choice: it is listed
in `.gitignore` because it is a build product of `results/run.json`, not a source
file, and it needs `matplotlib`, which nothing else here depends on. So a fresh
clone regenerates the figure rather than receiving it — this step is a prerequisite
of the compile, not a repair. `results/run.json` is committed, so the figure it
produces is fixed.

Add `--check` to print every plotted value — bin counts, predicted and observed
rates, gaps, and Wilson intervals — without needing matplotlib. That path is
verified; the render is not, on a machine without matplotlib.

### 6. Tests (from the repository root)

```bash
./.venv/bin/python -m pytest when-to-escalate -q
```

337 tests, all passing. They cover the cost matrix and the hard constraint
(including that no belief can buy past it), the tie-break, the cache's staleness
and provenance behaviour, and configuration validation.

### What a reproduction cannot check

The beliefs themselves are not reproducible from scratch. They were generated once
by `gpt-4o-mini` — an unpinned, non-deterministic, externally-hosted model with no
dated snapshot recorded — and cached. Regenerating them would move every number in
the paper. The cache is committed for exactly this reason, and it is the boundary
of what these commands verify: everything downstream of the beliefs is
deterministic and checkable, and the beliefs are a fixed input, not a reproducible
one.

## AI-use statement

AI was used as a tool under my direction, not as an author. I chose the problem,
made and locked every design decision, set the cost values and their ordering,
wrote every public discussion contribution myself, and checked every reported
number against the committed run artifacts.

| Used for | Tool |
| --- | --- |
| Preparing the research file — technical terms at my level, grouped search queries, and candidate communities and accounts to verify myself. The prompt is in `research-file.md` verbatim, including the instruction to flag its own uncertainty rather than guess. | Claude, ChatGPT, Gemini |
| Reading the five sources in depth — symbol-by-symbol explanation of the formulas, a usefulness verdict, and multiple-choice quizzing to test my own grasp before deciding whether a paper fitted the project. | NotebookLM |
| Scaffolding, writing and repairing the code in `src/`, `data/`, `experiments/` and `tests/`; running the harness; LaTeX work on the preprint; and the record-keeping in this repository, including the visible corrections in `results/wrong-decisions.md`. | Claude / Claude Code |
| Three adversarial review passes over the draft — a practitioner pass, a probability and decision-theory pass, and a conference-referee pass. All 23 comments are in `review-record.md` with accept or reject, the reason, and the section each one points at. | ChatGPT (GPT), Gemini Spark |
| Finding candidate X posts to reply to each day, with an explicit instruction not to invent URLs and to return fewer if it could not find good ones. Which ones I actually replied to, and what came back, is in `discussion-record.md`. | Boardy |
| Not an authoring tool: generating the 100 beliefs that are the experiment's *input*. See "What a reproduction cannot check" above. | `gpt-4o-mini` |

Every AI output was checked before it was used. The five cases where a tool was
confidently wrong are logged in the "Important AI errors" table in
`research-file.md`, with how each was caught — including a synthesis that
recommended an architecture directly contradicting the locked design, and an
unverified bound attributed to a mis-cited source. Neither was carried into the
paper. AI drafts of public-facing replies were dropped once it was clear they read
as AI-written; AI is used to pressure-test my public writing, not to ghostwrite it.
Per-decision provenance — what I set versus what a tool proposed — is recorded in
`build-log.md` at the point each decision was made.

I affirm that no conversation in `discussion-record.md` is fabricated: every row
links to a real public thread, quotes a real person's reply, and records my own
reply as posted. Every number in the paper and in `results/` comes from a real run
of the committed code over the committed data, reproducible with the commands
above. No reference is cited that I did not read; where a tool asserted something
about a source that I have not confirmed at source, it is marked unconfirmed in the
AI-error table rather than stated as fact.

The paper carries the same statement in its `AI-use statement` section.
