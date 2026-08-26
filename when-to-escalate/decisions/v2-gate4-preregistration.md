# Gate 4 pre-registration — recalibrated beliefs against the ceiling, and abstention

**Status: locked before any Gate 4 number is computed.** This file lands in a commit
made while `experiments/abstention.py`, `results/voi-ceiling-arms.json` and
`results/abstention.json` do not exist, so the arm set, the option set, the
threshold grid and the stratification rule are fixed before the artifacts that
consume them, and the ordering is checkable in the git history.

Provenance for everything here: (AI-proposed), **confirmed** by Kaps in the Gate 4
opening exchange, except where marked otherwise.

---

## 1. What Gate 4 is for, and what this document can and cannot claim

Gate 4 owes four things, all deferred to it explicitly by earlier gates:

1. The `V_act(b) − EC(ask | b)` ceiling re-evaluated on the beliefs Gate 2
   produced, with the belief source named rather than assumed.
2. OQ2's abstention wiring, built and **measured**, with the (a)/(b)/(c) call made
   on the measured numbers at this gate's close.
3. The first application of the S4 forward check installed after Gate 3: any
   threshold or grid stated as a fraction of the scale it resolves, or justified as
   absolute.
4. Q5's reliability diagram data path, which consumes the Gate 2 belief
   distributions.

**This document is not written blind, and saying otherwise would be the dishonest
part.** Gate 3's pre-registration could claim no information gain had been computed
when its tables were fixed. That is not available here: the ceiling's inputs are
already committed, so three facts were read from committed artifacts during the
Gate 4 opening exchange, before this file was written. They are recorded here so no
later reader mistakes them for discoveries of the run:

- **The isotonic map's floor is exactly `6/23 = 0.260870`**, read from
  `results/logprob-elicitation.json` → `analysis.calibration.map.knots[0][1]`.
- **All eight `no_direct_answer` cases have `b_h ≥ 0.400`** in every score set
  (cached 0.400, raw 0.4042, calibrated 0.4259), read from
  `results/run.json` → `rows[].belief.needs_human` and
  `analysis.recalibrated_scores`.
- **`order_preserved_on_test: false` is ties, not inversions** — 0 inversions and
  16 merged pairs at full precision (31 at the pre-registered 3dp) on the test
  split, computed from the committed scores and the committed map.
- **The `calibrated` arm already chooses `answer` zero times**, read from
  `results/rebaseline.json` → `arms.fresh_calibrated.action_counts`
  (`escalate_notify` 41, `hold` 9), against 12 for `fresh_raw` and 15 for
  `rebaselined_written`. This is §3's mechanism already visible in Gate 2's
  committed output, so §3.4's first falsifier is a regression guard, not a test
  whose result is unknown.

So the pre-commitment at this gate does **not** bind an unknown ceiling verdict.
What it binds is what is done with these facts and what is not: the arm set, the
option set, the grid, the stratification, and the requirement that whichever
abstention variant wins on the measured numbers is the one reported. The genuinely
unknown quantities at this gate are the **abstention costs** and the **per-arm
ceiling differences**. Those are where tuning could hide, and those are what §5 and
§6 lock.

**What Gate 4 does not do.** It does not touch `costs.COST` (locked by OQ4's
resolution), does not re-run or retune the Gate 3 sweep, does not retune the §5
collapse thresholds, does not overwrite `results/run.json`,
`results/voi-ceiling.json` or any Gate 2 or Gate 3 artifact, does not add a
production `ask` feature, and makes zero API calls.

---

## 2. The four belief arms — locked

`experiments/rebaseline.py` already established the one-variable-at-a-time arm
design at Gate 2. Gate 4 reuses the same four arms so that a contrast means the
same thing in both artifacts.

| arm | readiness from | `needs_human` from | contrast against the row above isolates |
| --- | --- | --- | --- |
| `published` | v1 cache (`data/belief_cache.json`) | written digit | — this is Gate 1's input, `results/run.json` |
| `rebaselined` | fresh logprob cache | written digit | cache **drift** (11 of 100 written values moved) |
| `raw` | fresh | `digit_expectation` logprob expectation | **continuity** — 43 distinct values on test against one decimal place |
| `calibrated` | fresh | `isotonic(raw)` | the **map** |

Four arms rather than two, because `published` against `calibrated` mixes three
effects, and the ceiling reads readiness through `hold` and `escalate_pause` — so
fresh-versus-cached readiness is a live confound, not a formality. (Kaps-decided.)

Locked with the arms: the `published` arm must reproduce the committed
`results/voi-ceiling.json` exactly. That file carries no `generated_at`, so the
comparison is byte-level on the JSON, and a test asserts it. This is what makes
"the arms are a superset, not a revision" checkable rather than asserted.

---

## 3. The calibration floor — the structural claim, locked with its falsifiers

This is Gate 4's headline finding and it is featured, not footnoted. (Kaps-decided.)

### 3.1 The claim

`src/calibrate.py`'s `IsotonicMap.predict` is **flat outside its knots** by design,
documented there as deliberate: an isotonic fit carries no information about a
region it never saw, and inventing a slope would be fabrication. The knot `y`
values are non-decreasing. Therefore

    min over x in [0,1] of predict(x) = knots[0].y = 6/23 = 0.260870

is a hard floor on every calibrated `b_h`, for every input score, not a property of
the observed scores.

Line that up against the two rationals the cost matrix already fixed:

```
1/5  = 0.200000   constrained-menu positive-VoI bound, binding action escalate_notify
3/13 = 0.230769   t*, the answer-vs-escalate_notify crossover
6/23 = 0.260870   the isotonic map's floor
```

`1/5 < 3/13 < 6/23`, exactly, in rational arithmetic. Two consequences follow from
one cause:

- **No calibrated belief can enter the constrained-menu positive-VoI region.** Not
  because these cases happen to score high — because the map's reachable range
  excludes the region entirely.
- **Every calibrated belief sits above `t*`**, so `EC(answer | b) = 10·b_h` exceeds
  `EC(escalate_notify | b) = 3·(1 − b_h)` on every case and `answer` is never the
  argmin. This is the mechanism behind the escalation count already measured and
  committed in `results/rebaseline.md`: the calibrated arm's 50 test decisions are
  41 `escalate_notify` and 9 `hold`, with **zero** `answer`, against 12 `answer`
  for `raw` and 15 for `rebaselined`. Gate 4 **explains** those numbers; it does
  not produce them.

### 3.2 Where the floor comes from

The floor is not a designed quantity and nobody chose it. PAVA sets each block's
level to that block's positive rate, and the lowest block pooled **23 of the 50 dev
cases with 6 positives**, so the level is `6/23`. Every knot `y` in the committed
map is `pos/n` of its block, and the block sizes sum to 50.

### 3.3 The transferable form

Stated so it does not depend on this dataset, in the same register as
`c_F/ν + c_T/α < 1`:

> For an isotonic map fitted by PAVA and evaluated flat outside its knots, the
> reachable range of calibrated probabilities is bounded below by the positive rate
> of the lowest pooled block. A decision rule with a fixed threshold strictly below
> that rate cannot fire after calibration, however much cross-entropy the map buys.

A calibration map has a **reachable range**; a fixed-threshold decision rule has
**thresholds**. Merging is harmless for the decision rule only if the thresholds
sit inside the range. Cross-entropy does not check that, because it never looks at
the thresholds. This is the concrete reason R7's bit-priced merge does not license
assuming the merge is harmless for the ceiling: R7 bought 0.0747 bits and paid with
a change to the range, and the ceiling reads the range.

### 3.4 What would falsify the mechanism

Pre-registered, so the claim is checkable rather than decorative. Each becomes an
assertion in code:

- Any test-split case under the `calibrated` arm whose chosen action is `answer`.
  Under §3.1 this is impossible, so a single occurrence falsifies the mechanism.
  Already satisfied by committed Gate 2 data (§1), so in code this is a regression
  guard on the mechanism rather than an open test.
- Any calibrated `b_h` below `6/23`.
- `min over the calibrated arm of b_h` not equal to a value the committed map can
  produce.
- The 41-notify / 9-hold / 0-answer test-split breakdown not reproducing from the
  committed caches.

The nine `hold` cases hold because `hold` is cheaper than `escalate_notify` on
their readiness vectors, not because `answer` won. That is asserted as measured,
and the per-case reason is reported rather than inferred here.

---

## 4. What recalibration can and cannot change

Stated plainly in both directions, because one half is a tautology and presenting
it as a discovery would be the easiest available overclaim. (Kaps-decided.)

`experiments/voi_ceiling.py` has two halves.

**Belief-independent, in exact `Fraction` arithmetic over the entire simplex:**
`global_ceiling`, `witness_crosscheck`, `grid_crosscheck`, `check_feasibility`,
`lambda_crosscheck`, and `constrained_regime`'s `max_ceiling` and
`positive_region_on_the_argmax_ray`. So `−2/13`, `30/13`, `min EC(ask) = 2`,
`λ = 15/16`, `t* = 3/13`, the constrained maximum `+1.000` and its bound `b_h < 1/5`
are properties of `costs.COST`. No belief set moves them.

**Belief-dependent:** `check_per_case` — the 100 per-case ceilings with each case's
constraints applied — and `constrained_regime`'s `min_b_h_among_those_cases` and
`any_such_case_inside_the_region`.

Therefore:

- **On the unconstrained menu, the impossibility surviving recalibration is
  ANALYTIC.** The maximum over all beliefs is already negative, and any
  recalibrated belief is still a belief. This is a tautology and the artifact says
  so. It is not written up as an empirical result and it is not presented as
  evidence that the recalibration was tested against the theorem.
- **On the constrained menu, the emptiness is EMPIRICAL.** The positive region
  exists and is reachable in principle; whether any case with `no_direct_answer`
  lands inside it is a fact about this dataset. Under the `calibrated` arm the
  region is additionally excluded by §3.1's floor, which is structural — so the
  reason differs by arm, and the artifact reports the reason alongside the verdict
  rather than merging them.

The binding wording rule (G7) holds throughout every Gate 4 artifact: the claim is
**"asking is never rational on the unconstrained action menu,"** with the
constrained-menu positive region (`b_h < 1/5` on the all-hot ray) and its emptiness
in this dataset stated explicitly. Never the unqualified "asking never helps."

One precision point the artifact must carry: `b_h < 1/5` is the bound **on the
all-hot ray**, where the constrained region's maximum sits. A case off that ray has
a tighter bound. So failing `b_h < 1/5` rules a case out cleanly, but passing it
would not by itself place a case inside the region. `check_per_case` with
constraints applied is the sufficient test, and it is the one reported.

---

## 5. The abstention option set — locked

OQ2 (`decisions/v2-definitions.md` §7) left three options and deferred the call to
this gate specifically so the cost would be visible rather than predicted. All
three are built and measured. No fourth is added after the numbers are seen.

**Abstention resolves to `escalate_pause`** — the agent stops and hands over — not
`escalate_notify`. (Kaps-decided.)

| variant | rule | 
| --- | --- |
| **(c) diagnostic** | myopic argmin, policy unchanged. Abstention reported, never acted on |
| **(b) fallback ordering** | when `ask` loses only because `VoI ≤ 0`, resolve toward `escalate_pause` instead of `escalate_notify` |
| **(a) threshold override** | `H(b) ≥ τ` implies `escalate_pause`, overriding the matrix, τ over §6's grid |

### 5.1 What is measured

Realised cost, missed escalations and action counts, on the **test** split, with
v1's cost matrix and v1's miss definition, reusing `rebaseline.realised_cost` so
the numbers sit in the same table as the published / rebaselined / raw / calibrated
arms rather than in a private scale.

On three arms — `published`, `raw`, `calibrated` — not four. `rebaselined` would add
a column about cache drift, which abstention has nothing to do with.
(Kaps-decided.)

Additionally, and this is the part OQ2 was held to this gate for: for every case
where abstention would fire, the realised cost of resolving it to **`escalate_pause`**
against **`escalate_notify`** and against **`answer`**. That makes "abstention
should be pause" a measured claim about this cost matrix and these labels rather
than a definition.

### 5.2 (b) is measured as the blanket rewrite it is

OQ2 already noted the problem and Gate 1 confirmed its premise: if `VoI ≤ 0` on
every case, then "`ask` lost only because `VoI ≤ 0`" is true everywhere, so (b)
stops being a narrow tie-break and becomes a blanket rewrite of the fallback. Gate
4 puts a number on the size of that rewrite — action-change count and cost delta on
the test split — so the "large change wearing a small change's costume" reading is
demonstrated rather than asserted.

### 5.3 The call, and the pre-commitment on it

OQ4 resolved to (C)-primary, which by OQ2's own reasoning points at (c). **The call
is made at this gate's close, on the measured numbers, by Kaps.** (Kaps-decided.)

Pre-committed now: τ is not tuned to make any variant look good, and if (a) or (b)
beats (c) on realised cost that is reported plainly, even though it cuts against
the no-free-parameters claim. The recommendation is stated separately from the
measurement so the two are not confusable.

---

## 6. The `H(b)` threshold grid, and the full S4 inventory

This is the first gate under the S4 forward check, so the inventory is complete
rather than limited to the awkward case.

### 6.1 The one genuinely new tunable: τ

The scale τ has to resolve, from `results/answer-model.json` →
`per_case.cases[].h_joint`, the 100 committed beliefs:

| | bits |
| --- | ---: |
| theoretical range of `H(b)` | 0 – 2.585 |
| observed min / max | 0.0000 / 2.4564 |
| observed median | 2.0174 |
| deciles, 0% to 100% | 0, 1.626, 1.626, 1.879, 2.017, 2.017, 2.017, 2.038, 2.083, 2.252, 2.456 |
| cases at `H(b) = 0` | 1 (`a11-repeated-097`) |

The distribution is **bunched**: one case at zero, then 90% of the mass inside
1.626–2.456 — a 0.83-bit band, a third of the theoretical range. An absolute grid
such as τ ∈ {0.5, 1.0, 1.5, 2.0} would spend three of its four points in a region
containing one case. That is Gate 3's sweep failure in a new costume, and S4 exists
to stop the third occurrence.

**Locked: τ is defined as the deciles of the observed `H(b)` distribution on the arm
being scored**, so the step is commensurate with the quantity by construction. The
artifact reports both the quantile and the absolute bit value each quantile lands
on, per arm.

Declared trade-off: quantile grids are not comparable across arms in absolute bits,
because `H(b)` shifts when `b_h` shifts. Reporting both readings is the mitigation,
and it is stated rather than left for a reader to notice.

### 6.2 Numbers that are absolute, and why S4 does not apply

| number | why it is absolute |
| --- | --- |
| `1/5`, `3/13`, `15/16`, `−2/13`, `30/13` | exact rationals *derived* from `costs.COST` by closed-form maximisation. Consequences of the matrix, not knobs. There is no scale to state them as a fraction of |
| `6/23` | the fitted map's lowest block level, `pos/n` on dev. A measured property of a committed artifact, not a setting |
| `n_bins = 10` | pre-registered at Gate 2, carried unchanged. Not new at this gate |
| arm-comparison tolerance `1e-9` | resolves float noise, not signal, on a quantity spanning ≈3.1 (ceilings from −3.500 to −0.400). Absolute by intent |
| Wilson `z = 1.96` | existing in `paper/figures/make_figures.py`, unchanged |

Exactly one new tunable at this gate, and it gets the quantile treatment.

---

## 7. Split stratification — locked

The isotonic map was fitted on dev and evaluated on test (`fitted_on: 'dev'`,
`evaluated_on: 'test'`, 50/50). So calibrated `b_h` on the 50 dev cases is
**in-sample**, and five of the eight `no_direct_answer` cases are dev.

Locked: every arm is computed on all 100 cases, results are reported
split-stratified, and **any held-out claim is test-only**, with the dev half shown
and labelled in-sample. (Kaps-decided.) Without this, a 5-of-8 in-sample majority
would quietly carry a claim about held-out behaviour.

---

## 8. What is computed, and where it lands

| artifact | status | contents |
| --- | --- | --- |
| `experiments/voi_ceiling.py` | extended | arm selector; belief-independent sections computed once and shared; default path unchanged |
| `results/voi-ceiling-arms.json` / `.md` | new | the four arms, split-stratified, with §3's floor section and §4's analytic/empirical split stated in the artifact itself |
| `experiments/abstention.py` | new | three variants × three arms × the τ decile grid, on test, v1's matrix and miss definition |
| `results/abstention.json` / `.md` | new | the measured costs, the pause/notify/answer comparison, the size of (b)'s rewrite |
| `paper/figures/make_figures.py` | extended | `figure_data()` gains the Gate 2 test-split panels from `test_reliability_raw` and `test_reliability_calibrated`; `--check` re-derives every plotted number from the committed JSON and exits non-zero on mismatch |
| `results/voi-ceiling.json` | **untouched** | Gate 1's artifact; the `published` arm must reproduce it byte-for-byte |

Q5's rendering path is deferred. matplotlib is absent from the test environment and
the repo holds a pure-stdlib discipline, so shipping a render path now would ship
something untested; the data path and `--check` land here and rendering lands at
the paper gate. (Kaps-decided.)

Two bin schemes must not be drawn on one axis: v1's panel bins the elicited
one-decimal values (8 occupied bins, 4–35 cases each), Gate 2's are the
pre-registered 10 equal-width bins. Both shaded-unresolvable regions are also
distinct and are labelled separately — v1's `(0.2, 0.3)` because the elicited
marginal only took one-decimal values, the calibrated panel's `[0, 6/23)` because
the map cannot produce a value there at all.

The test suite is **510 passing** at this gate's open. New tests cover the arm
loader, the `published`-arm reproduction assertion, §3.4's four falsifiers, the
three abstention variants, τ's quantile definition, and `--check`'s mismatch exit.

---

## 9. What would make this document false

Stated in advance, so the failure is recognisable rather than absorbable:

- An arm added or dropped after the numbers are seen.
- An abstention variant added, or one of the three dropped, after the numbers are
  seen.
- τ defined in absolute bits anywhere, or a τ grid whose step was not checked
  against the observed `H(b)` spread.
- A dev-split calibrated number carrying a held-out claim, or a split-stratified
  table collapsed to a single column in any write-up.
- The unconstrained-menu impossibility described as empirically confirmed by the
  recalibration, or the analytic half of §4 written up as a finding.
- The constrained-menu emptiness described as logical rather than empirical, or the
  `calibrated` arm's structural exclusion conflated with the other arms' empirical
  one.
- Any Gate 4 claim stated without "on the unconstrained action menu" where G7
  requires it.
- `results/voi-ceiling.json`, `results/run.json`, or any Gate 2 or Gate 3 artifact
  modified by this gate.
- Any assignment into `costs.COST`.
- The abstention call made on anything other than the measured numbers, or the
  recommendation presented as the measurement.
- Any API call made during Gate 4.

---

## Provenance index, Gate 4 pre-registration

| # | Item | Provenance | Status |
| --- | --- | --- | --- |
| T1 | This document is not blind; the four facts already read from committed artifacts are listed, and the pre-commitment binds the abstention call and the arm differences rather than a ceiling verdict already legible from committed data | (AI-proposed) | **noted** |
| T2 | Four belief arms, mirroring `rebaseline.py`, so every contrast is one-variable; the `published` arm must reproduce `results/voi-ceiling.json` byte-for-byte | (Kaps-decided) | **confirmed** |
| T3 | The calibration floor `6/23` sitting above both `t* = 3/13` and the `1/5` bound is Gate 4's headline, featured with its mechanism and its transferable form, not footnoted to the ceiling table | (Kaps-decided) | **confirmed** |
| T4 | The floor's mechanism is falsifiable and gets four assertions in code; the first is already satisfied by committed Gate 2 data and is recorded as a regression guard rather than an open test | (AI-proposed) | **confirmed** |
| T5 | On the unconstrained menu the impossibility surviving recalibration is analytic and is written up as a tautology; only the constrained-menu emptiness is empirical, and under the `calibrated` arm it is structural. All three statements appear in the artifact | (Kaps-decided) | **confirmed** |
| T6 | OQ2's three options all built and measured; abstention resolves to `escalate_pause`; the pause/notify/answer comparison is measured, not defined | (Kaps-decided) | **confirmed** |
| T7 | (b) is measured as the blanket fallback rewrite the ceiling result makes it, with the action-change count and cost delta reported | (AI-proposed) | **confirmed** |
| T8 | The OQ2 (a)/(b)/(c) call is made at the Gate 4 close on the measured numbers; τ is not tuned toward any variant, and a variant beating (c) is reported | (Kaps-decided) | **confirmed** |
| T9 | τ is the deciles of the observed `H(b)` distribution on the arm being scored, reported in both quantiles and bits. First application of the S4 forward check; the cross-arm incomparability is declared | (Kaps-decided) | **confirmed** |
| T10 | The full absolute/tunable inventory is carried in the artifact, including why S4 does not apply to the matrix-derived rationals | (Kaps-decided) | **confirmed** |
| T11 | All 100 cases computed, headline test-only, dev shown and labelled in-sample | (Kaps-decided) | **confirmed** |
| T12 | Q5 lands the `--check`-verified data path; rendering deferred to the paper gate because matplotlib is absent and an untested render path would ship unverified | (Kaps-decided) | **confirmed** |
| T13 | Gate 4 makes zero API calls and modifies no committed Gate 1, 2 or 3 artifact | (AI-proposed) | **noted** |
