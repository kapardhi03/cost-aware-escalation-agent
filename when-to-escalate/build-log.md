# Build Log

## How to read this

One row per decision. Never edit a row after the fact — if a decision is
reversed, add a new row that supersedes it and say so in the reason. The point of
the log is that it shows what was believed at the time, including the parts that
turned out wrong.

**Verdict** is one of:

| Verdict | Meaning |
| --- | --- |
| `Locked at outset` | Decided before the build started. Not up for reopening. |
| `Approved` | Proposed during the build, accepted. |
| `Rejected` | Proposed during the build, turned down. Reason records why. |
| `Superseded` | Was live, later replaced. Names the row that replaced it. |

`Reason` is the human's reason, in the human's words. Where a reason has not been
given yet, the cell says so explicitly rather than being filled with a guess.

---

## Decisions

| # | Date | Decision | Verdict | Reason | Affected |
| --- | --- | --- | --- | --- | --- |
| 0a | pre-build | Belief = readiness distribution over {hot, warm, cold} summing to 1, **plus** a separate independent `needs_human` probability | Locked at outset | Two separate judgments, not one score. A hot lead can have low `needs_human`; a cold lead can have high `needs_human`. | `src/belief.py` |
| 0b | pre-build | Decision rule = myopic one-step minimum-expected-cost over {answer, ask, hold, escalate} | **Superseded by 25** | Full belief-state planning is intractable, so a one-step rule is the defensible approximation (Kaelbling, Littman & Cassandra — Source 5 in `research-file.md`). | policy (not yet built) |
| 0c | pre-build | Wrong assertion is a **hard constraint**, not a priced term in the cost matrix | Locked at outset | Concretely: the AI has no right to send legal or land documents. No cost number should ever make sending land papers acceptable, so it cannot be a term that a large enough benefit outweighs. Archetype 5 is the worked example. | policy (not yet built) |
| 0d | pre-build | Belief comes from a real LLM call, cached to JSON per case id | Locked at outset | Both policies must run over identical beliefs, so the non-deterministic call happens exactly once per case and is then frozen. | `src/belief.py` |
| 0e | pre-build | Baseline = same decision logic with a uniform cost matrix | Locked at outset | Isolates exactly what cost-awareness buys. Holding the belief, the feasible set and the expected-cost machinery fixed and flattening only the costs means any difference between the two policies comes from the asymmetry and nothing else. | baseline (not yet built) |
| 0f | pre-build | Public boundary: no product name, no client data, no real prompts | Locked at outset | Everything stays at the general problem level. The prompt in `belief.py` is synthetic and written for this experiment. | all files |
| 1 | 2026-08-18 | `build-log.md` lives at `week1/when-to-escalate/build-log.md`, **committed**, not gitignored | Approved | Sits alongside the other record files. Initially asked for it gitignored; reversed once it was clear the build runs in an ephemeral container, where a gitignored file dies with the container and the decision record would be lost entirely. | this file |
| 2 | 2026-08-18 | Log includes the pre-build locked design as rows `0a`–`0f` (Option B), not just decisions made during the build | Approved | "Clean and more readable, i.e. provides wider information." The log should stand alone for a reader who was not present for the locked design. | this file |
| 3 | 2026-08-18 | Belief must come from a real LLM call. API key supplied via `.env`, which is gitignored | Approved | A keyword or rule-based belief is not what the paper is about, and a run scored on rule-based beliefs would report a calibration figure that says nothing about the model. The reported cache has to be genuine model output or the whole calibration argument is hollow. Consequence: the rule-based keyword fallback must not silently satisfy an experiment run. | `src/belief.py`, `.env` |
| 4 | 2026-08-18 | "Modular" means the **wider `src/` structure**, not the log's layout | Approved | Future integrations should be easy to drop in. Clarified after ambiguity in the original instruction. | `src/` |
| 5 | 2026-08-18 | Work proceeds one step at a time; no file is created or changed until that specific step is approved | Approved | Keeps every change traceable to an explicit decision instead of arriving in a batch. | process |
| 6 | 2026-08-18 | *(fallback default later reversed by decision 21)* Rule-based fallback **kept**, but gated: `BELIEF_ALLOW_RULE_FALLBACK` in `.env`, and the provider that produced a belief is surfaced to callers | Approved | "Offline smoke tests keep working; a real run can't silently degrade." Deleting it would break offline runs; leaving it silent would void decision 3, since a run where both APIs fail would produce keyword beliefs that look identical to LLM beliefs in the cache. | `src/config.py`, `src/belief.py` |
| 7 | 2026-08-18 | `python-dotenv` adopted as a real dependency; `requirements.txt` created at the repo root | Approved | Chosen over a hand-rolled parser. Consequence: the repo now needs dependency management, which it had none of. `requirements.txt` added in the same step since a dependency undeclared anywhere is worse than the parser would have been. | `requirements.txt` |
| 8 | 2026-08-18 | Cache path read from `.env` as `BELIEF_CACHE_PATH`; relative values resolve against the **repo root**, never the working directory | Approved | Closes Q3. Verified: the same relative path now resolves to one absolute path whether run from the repo root or from `when-to-escalate/`. | `src/config.py` |
| 9 | 2026-08-18 | The restructure proceeds one sub-step at a time, committing at coherent points rather than after every file | Approved | Same reasoning as decision 5, applied to a multi-file change. | process |
| 10 | 2026-08-18 | Config is loaded once per process and memoised; secrets are masked in `__repr__` and in `describe()` | Approved | *Claude's proposal, ratified.* A run must not see configuration change halfway through, and this repo is public, so a settings object that prints an API key into a traceback or a run log is a live leak risk. | `src/config.py` |
| 11 | 2026-08-18 | `Belief` stays the pure mathematical object; provenance moves to a separate `BeliefMeta`. `get_belief()` returns the pair | Approved | "Put it separate." Keeps the code's `Belief` identical to the paper's belief, so bookkeeping never contaminates the object the policy reasons over. Cost: callers unpack a tuple. | `src/belief.py` |
| 12 | 2026-08-18 | `belief.py` rewired onto `config.py`: no module constants, no ambient env reads, keys passed explicitly into each provider | Approved | Closes Q5. Makes the Q3 cache-path fix actually take effect, and makes `config.py` the only place configuration resolves. | `src/belief.py` |
| 13 | 2026-08-18 | Cache writes are atomic (temp file + `os.replace`) | Approved | *Claude's proposal, ratified.* Each belief costs a real API call, so the cache is expensive to rebuild. The previous version truncated the real cache before writing, so a crash or interrupt mid-write destroyed every belief already collected. Atomic writes make a run safe to interrupt. | `src/belief.py` |
| 14 | 2026-08-18 | `cache_provenance()` added: counts cache entries by provider | Approved | *Claude's proposal, ratified.* Makes Q6 — is this cache LLM-only — checkable in one call before any calibration number is quoted, instead of relying on remembering how a run went. | `src/belief.py` |
| 15 | 2026-08-18 | The reported belief cache must be **LLM-only**; a mixed cache is not a valid basis for calibration | Approved | "It should be LLM Belief." Generate the reported cache with `BELIEF_ALLOW_RULE_FALLBACK=false`. Closes the intent behind Q6. | `src/belief.py`, `.env` |
| 16 | 2026-08-18 | Providers extracted to `src/providers/`: one file per source, a registry, a shared prompt, and a shared JSON extractor | Approved | Closes Q7. Adding a provider is now a new file plus one `register()` call, with no edit to `belief.py`. `belief.py` keeps the belief, the provider *policy*, and the cache; it no longer knows how any provider works. | `src/providers/`, `src/belief.py` |
| 17 | 2026-08-18 | `config.VALID_PROVIDERS` replaced by a lookup against the live registry | Approved | *Claude's proposal, ratified.* Found by a test: registering a provider did not make it selectable, because config validated against a hardcoded tuple. The registry was decorative until this was fixed. | `src/config.py` |
| 18 | 2026-08-18 | `extract_json` rejects any JSON that is not an object | Approved | *Claude's proposal, ratified.* Found by a test: a model replying `null` or `[]` parsed cleanly, then every `.get()` missed and produced a confident uniform belief instead of a visible failure. | `src/providers/json_utils.py` |
| 19 | 2026-08-18 | Full pytest suite added under `tests/`, with stubbed SDKs; no test may make a network call | Approved | "Build the test files. Include every edge case and consider all the cases." Stubs exercise the real provider code path, including the SDK import, so the tests cover production behaviour rather than a parallel implementation. | `tests/`, `pytest.ini` |
| 20 | 2026-08-18 | `assert_llm_only()` added: raises unless every cached belief came from a real model | Approved | *Claude's proposal, ratified.* Turns decision 15 into a check that runs, rather than a rule someone has to remember before quoting an ECE figure. | `src/belief.py` |
| 21 | 2026-08-18 | `BELIEF_ALLOW_RULE_FALLBACK` now defaults to **false**. Keyword scoring must be opted into | Approved | Closes Q9. Follows from decision 15: silence should give the safe answer. Previously an unconfigured run produced a mixed cache and you had to remember the flag; now a keyless run stops at load with an explanation. Supersedes the permissive default set in decision 6. | `src/config.py` |
| 22 | 2026-08-18 | Pinning `BELIEF_PROVIDER=rule` while `BELIEF_ALLOW_RULE_FALLBACK=false` stays a hard error rather than being auto-resolved | Approved | *Claude's proposal, ratified.* It is a genuine contradiction, and auto-resolving it either way would be a guess about intent — better to stop and make the person state what they meant. Cost: an offline run sets two variables instead of one. | `src/config.py` |
| 23 | 2026-08-18 | GitHub Actions workflow added: runs the suite and the offline smoke test on every push and PR, on Python 3.10 and 3.12 | Approved | Makes the tests load-bearing instead of advisory. The strict gate protecting the calibration claim was only verified when someone remembered to run pytest. No secrets are configured for the job, so a test that started making real network calls fails there rather than silently billing someone. | `.github/workflows/tests.yml` |
| 24 | 2026-08-18 | `.env.example` committed with placeholder values only | Approved | *Claude's proposal, ratified.* Gives the variable names and the strict-mode guidance a real place to live, so someone cloning the repo knows what to set without ever seeing a real `.env`; `.gitignore` whitelists it while still ignoring `.env`. | `.env.example` |
| 25 | 2026-08-18 | **Action set expanded to five**: {answer, ask, hold, escalate-notify, escalate-pause}. Supersedes locked design 0b | Approved | Design change forced by case construction. My own production archetypes showed notify and pause carry different costs — pause risks a live lead going cold; notify spends human attention but keeps the conversation alive. Collapsing them would throw away the core cost asymmetry the project is about. | policy, cost matrix (not yet built) |
| 26 | 2026-08-18 | Optional `context` (turn index, repeat count) added to `get_belief`, fed into the prompt | Approved | Keeps the context-dependent archetypes intact and gives evidence to answer research-file question 8: single-message belief is insufficient for ~1/3 of archetypes. Belief stays a pure function of (message + context) so caching is still honest. | `src/belief.py`, `src/providers/` |
| 27 | 2026-08-18 | Readiness stays **three states**. Non-leads (competitor, abuse, spam blast) are labelled `cold` as a known approximation | Approved | Not adding a `not_a_lead` state — too many locked pieces moving at once for Week 1, and every calibration bin would shift. The approximation is recorded explicitly so it surfaces in the paper as a limitation. | `data/`, paper |
| 28 | 2026-08-18 | Case set is **100 cases**, split by a fixed seed into 50 dev / 50 test, committed | Approved | Same 50 to develop on, same 50 to report on, frozen. No random per-run draw — reproducibility comes first. Rejects the earlier "random 50 each run" idea, which would have made published numbers irreproducible and confounded the policy comparison with the draw. | `data/` |
| 29 | 2026-08-18 | Cache fingerprint renamed `msg_hash` → `input_hash`, computed over message **and** context | Approved | *Claude's proposal, ratified.* Hashing the message alone would let context drift silently while the cache still reported a match, which would break the "identical beliefs" guarantee in a way nothing would detect. | `src/belief.py` |
| 30 | 2026-08-18 | Providers receive `message` and `context` **separately**; only text-to-model providers render them together | Approved | *Claude's proposal, ratified.* Found by a test after I initially rendered context for every provider: the phrase "already received" contains "ready", a hot keyword, so the keyword provider read a no-signal opener as a hot lead. A substring matcher must only ever see what the lead actually wrote. | `src/providers/`, `src/belief.py` |
| 31 | 2026-08-18 | Case-set distribution approved: 4=16, 5=12, 1=10, 10=10, 2/3/6/7/8=8, 9=6, 11=6 | Approved | Weighted toward the archetypes where the cost asymmetry bites, thinning the over-sharer, while protecting a block of clean answer-only cases (sub-variant 4a) so the set is not so escalation-heavy that an always-escalate policy scores well by default. | `data/cases.json` |
| 32 | 2026-08-18 | 100 cases written to `data/cases.json`, generated by `data/build_cases.py` | Approved | Labels reviewed and confirmed before writing. The generator is committed alongside the data so the seeded split can be re-derived, but `cases.json` is the source of truth — the messages are hand-authored, not generated. | `data/` |
| 33 | 2026-08-18 | **Cost: wrong answer / false assertion = 10** | Approved | Hard constraint (false legal/land claims, tail risk). Sits at the top, nearly forbidden. My earlier 6 contradicted the paper's own thesis and under-priced the one thing no revenue should ever justify. | cost matrix |
| 34 | 2026-08-18 | **Cost: hold a hot lead = 6** | Approved | A hot, ready-to-buy lead left waiting is the worst outcome short of the hard constraint. Recoverable but the most damaging non-forbidden mistake in my market. | cost matrix |
| 35 | 2026-08-18 | **Cost: needless escalate-pause = 5** | Approved | An active stop is bad, but I judge losing a hot lead to a wait as worse than a needless freeze. | cost matrix |
| 36 | 2026-08-18 | **Cost: needless escalate-notify = 3** | Approved | Spent a human glance, cheap. | cost matrix |
| 37 | 2026-08-18 | **Cost: needless ask = 2** | Approved | Cheapest. One question, mild friction, keeps the lead alive and improves the belief for the next turn. My earlier 7 would have made "ask" a dead action and pre-answered research-file Q2 in the wrong direction. | cost matrix |
| 38 | 2026-08-18 | **Cost: correct actions = 0; correct escalate-pause = 1 residual** | Approved | Human time plus a brief wait, so the policy does not treat correct pausing as free and over-escalate. | cost matrix |
| 39 | 2026-08-18 | `tests/test_cases.py` added: validates the committed case set | Approved | `data/cases.json` is what the reported numbers are computed over. A hand-edited label, a lost case, or a split that stopped being balanced would change published results with nothing to notice. | `tests/test_cases.py` |
| 40 | 2026-08-18 | Full 30-cell cost matrix approved as proposed | Approved | The additivity reasoning is right — hold on hot+needs-human is 8, not 16. The harms overlap, they don't stack; anything above 10 would break the false-assertion-is-top framing. No hotness premium on a false answer. | `src/costs.py` |
| 41 | 2026-08-18 | `escalate-pause` stays constraint-driven and is never the minimum-expected-cost action | Approved | Correct by design, not a repeat of the "ask" bug. Pause is an emergency stop, not a routine cost choice — you pause because continuing is unacceptable, not because it's cheapest. Unlike "ask", it is not supposed to win on price. To be stated in the paper as finding F1 so it does not read as an accident. | `src/costs.py`, paper |
| 42 | 2026-08-18 | `"constraints": ["no_direct_answer"]` added to the 8 restricted cases; regenerated with the same seed and split | Approved | The constraint rides on the case because the belief cannot encode it. Verified: case ids, labels and split are byte-identical to the previous generation; only the new field differs. | `data/cases.json` |
| 43 | 2026-08-18 | `src/costs.py` written; the hard constraint is enforced as **infeasibility**, never as a price | Approved | A constraint expressed as a large number can be outbid by a sufficiently confident belief, which is exactly what a hard constraint must forbid. Confirmed by a test that sets `answer` to cost 0 in every state and shows a constrained case still refuses it. | `src/costs.py` |
| 44 | 2026-08-18 | Baseline `UNIFORM_COST` is **derived** from `COST` (0 stays 0, every non-zero becomes 1) rather than hand-written | Approved | *Claude's proposal, ratified.* Keeps the two policies agreeing on which action is correct in each state, so the only difference is the magnitude of the asymmetry. A hand-written baseline could disagree about correctness, and the comparison would then measure two different notions of "right" instead of the value of pricing errors differently. | `src/costs.py` |
| 45 | 2026-08-22 | Deliverable moved from `week1/deliverables/when-to-escalate/` to `week1/when-to-escalate/`; **supersedes the path in decision 1** | Approved | `week1/deliverables/` held exactly one directory, so the segment carried no information. Row 1 is left as written rather than edited, per the no-retroactive-edits rule, and its path is the old one. Verified after the move: 337 tests pass and `robustness.py` still reports `legacy path reproduces results/run.json exactly: True`. `src/config.py`'s `.git`-less fallback went from `parents[4]` to `parents[3]` — the only depth-sensitive line in the tree; every other `parents[1]` resolves against the deliverable root and is unaffected. | `src/config.py`, `.github/workflows/tests.yml`, both `README.md`s, `.env.example`, `tests/` |
| 46 | 2026-08-22 | `paper/main.pdf` force-added despite the `*.pdf` ignore | Approved | The rendered paper is the submitted artifact, so it ships even though it is a build output. `.gitignore`'s "never source" comment describes the default, not this exception; the exception is force-added rather than un-ignored so no *other* build PDF can arrive by accident. | `paper/main.pdf` |
| 47 | 2026-08-22 | `week1/` removed; the deliverable now sits at the repository root as `when-to-escalate/`. **Supersedes the paths in decisions 1 and 45.** | Approved | `week1/` held exactly one directory and the repository holds exactly one project, so the segment named a course structure this repo does not have. Rows 1 and 45 are left as written per the no-retroactive-edits rule; both record superseded paths. Two things a path sweep misses were fixed by hand: `test_repo_root_contains_this_project` asserted `week1/` existed as a directory, and `config.py`'s `.git`-less fallback went `parents[3]` to `parents[2]`. Verified: 337 tests pass, `robustness.py` still reports `legacy path reproduces results/run.json exactly: True`, mean cost unchanged at 1.720. **Known cost:** the published X thread links to `.../tree/main/week1/when-to-escalate`, and GitHub does not redirect renamed directories, so that link now 404s. The post is left as posted rather than the record being rewritten. | `src/config.py`, `tests/test_config.py`, `.github/workflows/tests.yml`, both `README.md`s, `.env.example`, `.gitignore` |
---

## Open questions carried into the build

Not decisions yet. Listed so they are not lost between steps. All 15 are now
closed; the `Outcome` column records what closed each one, and where a question's
own wording turned out to be wrong the outcome says so rather than restating it.

| # | Question | Status | Outcome |
| --- | --- | --- | --- |
| Q1 | Should the rule-based fallback be deleted, or kept behind a flag? | **Closed** | Kept, gated by `BELIEF_ALLOW_RULE_FALLBACK`. See decision 6. |
| Q2 | `.env` is inert — where does config loading live? | **Closed** | `src/config.py`, via `python-dotenv`. See decisions 7 and 10. |
| Q3 | `DEFAULT_CACHE_PATH` is relative to the working directory. | **Closed** | Read from `.env`, resolved against the repo root. See decision 8. |
| Q4 | Reasons for rows `0e`, `3`, `10`, `13`, `14`, `17`, `18`, `20`, `22`, `24`, `29`, `30`, `39` and `44` were blank. `0c` is filled. This list originally omitted `44`, which was blank too. | **Closed** | All filled 2026-08-22. Rows proposed by Claude and ratified are marked as such in the cell, so the provenance survives the fill. |
| Q5 | `belief.py` does not yet use `config.py`. | **Closed** | Rewired. See decision 12. |
| Q6 | Is the belief calibrated enough to threshold on (research-file Q1)? Cannot be answered while any cached belief may be keyword-derived — ECE over a mixed cache is not LLM calibration. | **Closed** | Answered, and the answer is no. The strict run happened on Kaps's machine: `provider_summary` in `results/run.json` records `openai=100`, so the precondition this row set is met — the reported cache is LLM-only and its ECE is a real calibration number, not an average over two different belief sources. It is **0.142** on the `needs_human` marginal (95% bootstrap CI `[0.100, 0.249]`; 0.168 dev, 0.184 test), and the 0.2–0.3 bin that contains the threshold is over-confident, so the belief is **not** well calibrated. The decision is nevertheless insensitive to that on this case set: every elicited `b_h` sits at one decimal place, so `3/13 ≈ 0.2308` falls in the empty gap `(0.2, 0.3]` and every threshold in that interval decides identically. Thresholding survives here by an accident of the quantization, not because the belief is calibrated — which is why recalibration is reported as an in-sample ceiling rather than a fix. §6.6 and Figure 1; `ece_interval` and `recalibration` in `results/robustness.json`. |
| Q7 | Providers still live inside `belief.py`. | **Closed** | Extracted to `src/providers/`. See decision 16. |
| Q8 | No test file exists. | **Closed** | 208 tests under `tests/`. See decision 19. |
| Q9 | `BELIEF_ALLOW_RULE_FALLBACK` defaults to true, so an unconfigured run can produce a mixed cache. | **Closed** | Default flipped to false. See decision 21. |
| Q10 | No synthetic case set exists in `data/`. | **Closed** | 100 cases written and validated. See decisions 31–32. |
| Q12 | Cost numbers for the five actions are unset. | **Closed** | Set by Kaps with per-cost reasoning. See decisions 33–38. |
| Q13 | The cost matrix is a **ranking**, not a full (action × state) table. Costs for correct actions are 0 and correct pause is 1, but the mapping from these five error costs onto all 5 actions × 6 states is not yet written down. | **Closed** | Written down in full. `COST` in `src/costs.py` gives all 5 actions × 6 states as 30 explicit cells and decision 40 approved them; the same 30 cells are printed as Table 2 in the paper and are re-read from the `cost_matrix` block of `results/run.json` by every downstream check, so the ranking is no longer the only record of the pricing. |
| Q14 | The 42% `needs_human` rate is far above a real inbound base rate, so precision and recall on this set will not transfer to production. Deliberate — needed for measurability — but must be stated as a limitation. | **Closed, with this row's own claim narrowed — see L9.** | Carried into the paper's limitations section (§8.1) and recorded as L1, which is what this row asked for. The transfer warning survives: the 42% rate was set for measurability rather than sampled, so precision and recall are properties of this case set. The *comparison* in the question — that 42% is "far above a real inbound base rate" — is withdrawn, because no measured base rate for this channel exists to compare against. The paper states the withdrawal rather than quietly dropping the phrase. |
| Q11 | Nothing downstream of the belief exists yet: no cost matrix, no policy, no baseline. The decision rule (now 25) and hard constraint (0c) are unimplemented. | **Closed** | All of it exists. `src/costs.py` holds the 30-cell matrix, the expected-cost computation and the myopic argmin decision rule (25), plus `CONSTRAINT_FORBIDS` for the hard constraint (0c); `experiments/run_policies.py` runs the cost-aware policy against four fixed-action baselines over the 100 cases and writes `results/run.json` and `results/run.md`. Hard-constraint behaviour, including that no belief can buy past it, is covered under `tests/`. |
| Q15 | The five-action set (25) means the cost matrix gains a column, and `escalate-notify` vs `escalate-pause` need relative costs. Those numbers are unset. | **Closed** | Numbered `Q12` until 2026-08-22, colliding with the row above; renumbered, not rewritten. It is the same gap as Q12 entered twice, and it closes on the same decisions: 36 prices needless `escalate-notify` at 3 and 35 prices needless `escalate-pause` at 5, 38 gives correct pause a residual of 1, and 40 approved the full 30-cell matrix. |

---

## Limitations to carry into the paper

Recorded here as they surface, so the limitations section is written from a list
rather than from memory.

| # | Limitation | Where it came from |
| --- | --- | --- |
| L1 | The `needs_human` base rate in `data/cases.json` is 42%, far above a real inbound stream. Inflated deliberately so the asymmetry is measurable, but it means **precision and recall on this set will not transfer to production base rates**. | Decision 31, Q14 |
| L2 | Non-leads — competitor fishing, abuse, spam blasts — are labelled `cold` rather than given their own state. A known approximation; readiness calibration is slightly distorted by it. | Decision 27 |
| L3 | Readiness labels are *authored intent*, not observed outcomes. Calibration on readiness measures agreement with my labelling, not with what the lead actually did. `needs_human` labels are stronger, being true by construction. | Two-label decision |
| L4 | The synthetic set makes missed escalation measurable precisely because it is not real. In production there is no follow-up signal, so recall would be unmeasurable — this is the trade the set makes. | research-file Q6 |
| L5 | The state space is **too coarse to separate competitor-fishing from abuse**: both are `(cold, needs_human=True)`, yet the archetypes want different actions — answer-price-only versus stop-and-pause. The cost matrix cannot price them differently. Evidence that a richer state, or a separate intent flag alongside readiness, would be needed. A real finding about the factorisation, not a confession. | Decision 40, Q2 ruling |
| L6 | The hard constraint is treated as **observable and error-free**, while the hidden state is not. `constraints` rides on the case; in production a detector would fire it and would carry its own false-positive and false-negative rates, which this experiment does not model. | Decision 42, Q3 ruling |
| L7 | **F7 names a failure class this test set cannot exhibit by construction.** Every case in `data/cases.json` carries `message` as a single string and `context` as `{turn_index, repeat_count}`, and the harness evaluates one message per turn, so a turn containing two messages — one routine, one carrying the only `needs_human` signal — cannot occur in the set. This is narrower and more concrete than L1–L6: it is a specific instance of what the realism-for-measurability trade in L4 hides, namely an entire failure class that is invisible to a one-message-per-case harness rather than merely distorted by it. Surfacing it would require multi-message-per-turn cases and a per-message evaluation step before the turn is acted on; this experiment has neither, so no number reported here bears on it. | F7, `data/cases.json` schema |
| L8 | **The design scans for critical signals but never guarantees that no message is silently dropped.** The response to F7 is a per-message scan for hard-stop intents before the turn is scored, which lowers the chance of missing the expensive message but leaves the underlying property untouched: a message can still be dropped, because nothing in the design requires it to be resolved. The stronger form, raised by a practitioner in the F7 thread rather than by me, is to make every inbound item durable — a queue entry with an explicit acknowledge-or-close step, so that priority may be fuzzy but existence may not, and an unacknowledged request for a human keeps returning until something closes it. That is a different kind of fix from anything in this paper: the policy prices actions, whereas this constrains the transport underneath it, and no cost matrix can compensate for an input the agent never sees. Not implemented and not measured here. | r/AI_Agents F7 thread — Sufficient-Bear-460; see `discussion-record.md` |
| L9 | **Supersedes the base-rate comparison in L1.** L1 records the 42% `needs_human` rate as "far above a real inbound stream". That is an unsourced comparison: no measured base rate for this channel exists in this repo or in any source read for it, so "far above" asserts a magnitude nothing here establishes. Withdrawn. What survives is narrower and still enough to carry the limitation: the rate was **set for measurability rather than sampled**, so the precision and recall reported here are properties of this case set and should not be expected to transfer to production **in either direction** — the direction of the error is unknown, not just its size. The readiness distribution is off the design's own prior in the same way (the belief module assumes 85% cold, the case set is 39% cold), and the paper reports the reweighting to that prior instead of asserting a comparison. Everything else in L1 stands, including the transfer warning itself. | Q14; the paper's limitations section carries the withdrawal explicitly |
| L10 | **Temperature-0 reproduction is 89 of 100, not 100 of 100, so no number in this repo compares cleanly across cache dates.** Elicitor A sends v1's `SYSTEM_PROMPT` byte-identical at `temperature=0`, so the `needs_human` value it writes should equal the value already in `data/belief_cache.json` for the same case. It does for 89 cases; **11 differ** and 0 are unparseable. The largest single move is `a04-booking-040`, 0.9 → 0.3. **The cause is not determinable from the record, and this is a record-keeping failure in v1 rather than a finding about the provider.** Both runs requested the same alias, `config.DEFAULT_OPENAI_MODEL = "gpt-4o-mini"`, but v1 stored the alias it *asked for* (`model: "gpt-4o-mini"`, cached 2026-08-19) while v2 stores the snapshot the API *resolved to* (`gpt-4o-mini-2024-07-18`, cached 2026-08-24). Which snapshot served v1 was never written down, so a snapshot change five days apart is consistent with the evidence but unproven; serving-side nondeterminism at `temperature=0` is equally consistent. `temperature=0` pins the sampler, not the weights or the kernels, and pins neither if the alias re-resolves. **Lesson, applied from v2 on: record the resolved model id, not the requested alias** — v2's cache does, so comparisons *against* v2 will be checkable in a way this one is not. The structural consequence stands either way: v1's published 1.720/16 was computed against beliefs that cannot now be reproduced, so any v1-versus-v2 comparison mixes the effect being measured with whatever moved. `experiments/rebaseline.py` is the response — it re-runs v1's decision rule on the fresh beliefs so the before/after is taken **within** one snapshot. Two further consequences to carry: the only baselines that compare across cache dates without a caveat are the belief-free trivial policies, whose realised cost is a function of the labels alone (`always_notify` = 1.7400 on test, verified by recomputing from labels); and a cross-date aggregate can look unchanged while individual decisions move, which is exactly what happened here — see the coincidence recorded in `results/rebaseline.md`. | `results/logprob-elicitation.json` → `reproduction_check`; model ids from `data/belief_cache.json` and `data/logprob_cache.json`; pre-registered in `decisions/v2-gate2-preregistration.md` §6 as report-do-not-smooth |

---

## Findings for the paper

| # | Finding | Source | Evidence |
| --- | --- | --- | --- |
| F1 | **`escalate-pause` is never the minimum-expected-cost action.** Swept across the belief simplex it is never chosen on price; it is invoked only by the hard constraint. This is the correct shape for an emergency stop — you pause because continuing is unacceptable, not because it is cheapest — and is stated as a design finding rather than left to look like an accident. | Test — exhaustive simplex sweep | `tests/test_costs.py::test_pause_is_never_the_cheapest_action` |
| F2 | **Single-message belief is insufficient for roughly a third of the archetypes.** Archetypes 1, 3 and 11 need conversation position to be decidable at all. Answers research-file question 8. | Design — case construction | Decision 26, `data/cases.json` |
| F3 | **The cost-aware policy and the uniform baseline disagree over a wide band of beliefs**, not just at the edges — the baseline keeps answering while the cost-aware policy escalates, from around P(needs_human) ≈ 0.3 upward at high readiness. | Test | `tests/test_costs.py::test_baseline_and_real_matrix_can_disagree` |
| F4 | **Every missed escalation came from an under-estimated `needs_human`, not from misread readiness.** All 16 cases the cost-aware policy failed to escalate carry a belief `needs_human` of 0.30 or below — the values are 0.00, 0.10, 0.20 and 0.30 — against a true label of `True`. The readiness argmax on those same cases is spread across cold (7), hot (5) and warm (4), so high readiness is not what suppressed the escalation; the `needs_human` estimate is low regardless of readiness. This is consistent with the reliability bins, where the model is under-confident in exactly this range (bin 0.1–0.2: predicted 0.10, observed 0.40; bin 0.3–0.4: predicted 0.30, observed 0.588). It is therefore evidence **for** the independence assumed in locked design 0a rather than against it: the failure is a miscalibrated marginal, not a leak between the two parts of the state. One of the 16, `a11-repeated-097`, was decided at margin 0.0 — a tie broken by `ACTIONS` order, not by cost. | Run analysis — LLM run, n=100 | `results/run.json`, 16 rows where `labels.needs_human` is true and `decisions.cost_aware.action` is not an escalation. Realised costs are 3, 4 and 10, not uniform. |
| F5 | **Two of the five actions are never selected under LLM beliefs, and only one of them is dead by design.** Over the reported run the cost-aware policy chooses `escalate_notify` 43 times, `answer` 30 and `hold` 27. `escalate_pause` is absent by design (F1). `ask` is not: it is squeezed from both sides, with `hold` cheaper whenever holding is right and `escalate_notify` cheaper whenever a human is needed, so it is never the argmin at any belief the model actually produced. It is not dead in principle — under keyword beliefs the same cost matrix selects `ask` on 4 cases — so the action's viability is a property of the belief distribution, not of the cost matrix alone. This answers research-file question 2 empirically, and it undercuts the reasoning in decision 37, which set `ask` = 2 specifically to stop it becoming a dead action. | Run analysis — LLM run vs dry run | `results/run.json` action counts (43/30/27, no `ask`, no `escalate_pause`); `results/run_DRY.json` selects `ask` on 4 cases |
| F6 | **The hard constraint's value scales inversely with belief quality.** `no_direct_answer` binds — removes `answer` in a case where `answer` would otherwise have been selected — on 4 of the 8 restricted cases under keyword beliefs and 0 of 8 under LLM beliefs for the cost-aware policy. For the uniform baseline it is 7 of 8 versus 1 of 8. The constraint does the most work exactly when the belief is worst and almost none when the belief is good. It should be reported as insurance whose expected payout falls as the model improves, not as a contributing component of the headline result. | Run analysis — LLM run vs dry run | `decisions.*.constraint_bound` in `results/run.json` (0 and 1) and `results/run_DRY.json` (4 and 7), over the 8 cases carrying `no_direct_answer` |
| F7 | **A batched high-cost signal was dropped because the turn, not the message, was the unit of decision.** A callback request arrived in the same turn as a routine information request. The agent acted on the routine message and dropped the callback, which was the only one carrying a `needs_human` signal — a rare, high-cost signal averaged out by common, low-cost traffic because the two messages were treated as a single turn. Distinct from the synthetic misses: those are belief-scoring errors on a single message, whereas this is a turn-boundary error in which the important message never got its own belief evaluation. Motivates a per-message critical-trigger scan before acting on a turn as a whole. | Live run — single incident | Live run, not the synthetic set — no repo artifact. Every case in `data/cases.json` has `message` as a single string and `context` as `{turn_index, repeat_count}`, so the harness cannot currently produce this failure. |
| F8 | **Supersedes the last claim in F4.** F4 concluded that the misses localising to one marginal is "evidence **for** the independence assumed in locked design 0a rather than against it". That does not follow, and is retracted. The run records only the two marginals and never the joint, so it cannot distinguish a miscalibrated marginal from a genuine dependence between the two parts of the state — the result is *consistent with* independence, not evidence for it. Testing the assumption needs `P(s, h)` elicited directly and compared against `P(s)·P(h)`, which this run does not do. Locked design 0a remains a modelling assumption, not a measured fact. Everything else in F4 stands. | Review 1 comment 2 in `review-record.md`, accepted | `results/run.json` records `belief.readiness` and `belief.needs_human` separately and never a joint. The paper carries the same retraction, as does correction C3 in `results/wrong-decisions.md`. |

---

## Failure analysis — kept for the paper

**Context-token leakage into a keyword belief.** Rendering the conversation
context block into *every* provider let the keyword fallback score my own
generated prose. `"already received"` contains `"ready"`, a hot keyword, so a
template opener with no buying signal scored hot = 0.545 instead of 0.286.

Worth citing because of the shape, not the size: it pushed cold leads toward hot
(the direction that *suppresses* escalation), the resulting belief was a valid
distribution with a normal provenance record so nothing downstream could detect
it, and it fired only on the archetypes that carry context — so it would have
biased one subgroup rather than adding uniform noise.

Caught by a test, not by reading the code. Fixed by decision 30. Full note in
`src/belief.py` above `BeliefSourceError`; regression test is
`tests/test_context.py::test_context_does_not_change_the_keyword_belief`.

---

## Environment note

The `.env` holding the real OpenAI and Gemini keys exists on Kaps's machine and is
gitignored, so it is correctly **not** present in the build container. Any step
that needs a live LLM call has to run locally; the container can only exercise
offline paths.

---

## v2

v1 above is closed and is not edited. v2 work appends here, chronologically.
Design decisions with provenance tags live in `decisions/v2-design-decisions.md`;
this section records what was done and what it measured.

### Gate 0 — cache audit (2026-08-24)

Two questions gated the rest of v2: does a pre-quantization raw belief exist, and
do emoji or code-switched inputs score worse. Both were answered by inspection of
committed artifacts only. No LLM call was made.

**1. There is no discarded raw layer, because nothing in v1 ever quantized.**

The belief path holds no rounding step. `extract_json` is a plain `json.loads`
(`src/providers/json_utils.py:28`); `to_belief` clamps `needs_human` into [0, 1]
and normalises the readiness distribution, and rounds neither
(`src/belief.py:238`); the result is cached verbatim. Positive evidence that the
parsed values reached the cache untouched: readiness entries such as
`0.10000000000000002` in `data/belief_cache.json` are float residue from dividing
by a total of `1.0000000000000002`. That is normalisation arithmetic applied to
parsed values — a quantization grid would have produced an exact `0.1`.

So the coarseness is `gpt-4o-mini`'s own output granularity at `temperature=0`,
not the harness's. Re-running the same prompt reproduces the same values.

**The grid is 0.1, not 0.2.** Eight distinct `needs_human` values over 100 cases,
all exact multiples of 0.1 (counts from `data/belief_cache.json`):

| `needs_human` | 0.0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.7 | 0.8 | 0.9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n | 4 | 15 | **35** | 17 | 6 | 6 | 5 | 12 |
| observed frequency of `needs_human=True` | 0.250 | 0.400 | 0.171 | 0.588 | 0.333 | 0.333 | 0.800 | 0.917 |

0.2 is the modal value, 35 of 100. v1 had already recorded the one-decimal
granularity — see Q6 in the open-questions table above, and correction C4 in
`results/wrong-decisions.md`. What is new here is the confirmation that it
originates upstream of the harness, and that **0.5 and 0.6 never occur**: the
model steps 0.4 → 0.7 and will not report a near-coin-flip. That gap is why the
0.1 grid alone leaves a value-of-information analysis with no high-entropy cases
to price.

**2. An input normalizer is not justified, and this data cannot justify one.**

Only 4 of 100 messages contain an emoji: `a06-mild-061`, `a08-reaction-075`,
`a08-reaction-076`, `a08-reaction-078`. They score *better* than plain inputs, not
worse — mean `|p − y|` 0.100 against 0.379, Brier 0.015 against 0.225, readiness
argmax 4/4 against 52/96.

That comparison is confounded rather than informative. All four carry the label
`needs_human=False` and sit in the cold/warm corner; **no emoji case has
`needs_human=True`**, so the subgroup has no power where a normalizer would
matter. The tightest within-archetype comparison, archetype 8 "media, no text",
runs the same way: emoji reactions mean `|p − y|` 0.067 (n=3) against non-emoji
placeholders — `[sticker]` and four voice notes — at 0.200 (n=5).

**Code-switched inputs: zero.** No Devanagari and no romanised-Hindi markers
anywhere in `data/cases.json`. The construct is absent from the case set, so the
question is unanswerable rather than answered.

Normalizer dropped (v2 decision D4). Deciding it would require authoring emoji and
code-switched variants of cases that already carry `needs_human=True` and
re-scoring them — a data-collection task, not a normalizer task.

**3. Unplanned finding: v1 already ran a recalibration, so v2 must not claim the
result as new.**

`results/robustness.json` carries a `recalibration` block —
`experiments/robustness.py:446`, a histogram-bin lookup fit on all 100 labels and
documented in its own docstring as an in-sample upper bound. It reports mean cost
1.65 → 1.25 and misses 16 → 8, escalations 43 → 60, recall 0.619 → 0.810,
precision 0.605 → 0.567, with 9 misses fixed, 1 created (`a06-frustrated-055`,
`escalate_notify` → `hold`) and 7 surviving (1 at `b_h=0.00`, 6 at `b_h=0.20`).

v2's contribution is therefore doing recalibration *honestly*, not doing it at
all: held out rather than in-sample, a genuine monotone calibration map rather
than a per-bin oracle, and reported with cross-entropy and a reliability diagram
alongside ECE. Stated this way in the paper so nothing overclaims (D2).

**4. Unplanned finding: two different v1 baselines exist and they disagree on
cost.**

`choose_action` defaults to the safe tie-break and accepts
`legacy_tie_break=True` for the ACTIONS-order rule that produced the committed
run (`src/costs.py:231`). Re-run over `results/run.json` beliefs:

| tie-break | mean cost | missed escalations | reported in |
| --- | --- | --- | --- |
| legacy, ties → `answer` | **1.720** | 16 | `results/run.json`, the paper |
| safe, ties → `escalate_notify` | 1.650 | 16 | `experiments/robustness.py` |

Both agree on 16 misses; only the cost differs. v2 quotes legacy **1.720 / 16** as
the headline baseline because that is what the committed run and the paper report,
and notes the safe tie-break alongside it (D3).

**Feasibility probe — not a result.** Pool-adjacent-violators isotonic on the
exact cached values collapses the eight values into four blocks. Fit on the 50 dev
cases and evaluated on the 50 held-out test cases, the map
`{0.0, 0.1, 0.2} → 0.269`, `{0.3, 0.4, 0.7} → 0.400`, `{0.8, 0.9} → 0.889` gives
test mean cost 1.200 against 1.720 for the identity map, and 3 missed escalations
against 8. Two warnings travel with it: `answer` falls to zero on test (15 → 0),
so every case becomes `hold` or `escalate_notify`; and merging `{0.3, 0.4, 0.7}`
into one block destroys the score ordering that VoI needs in Gate 4.

These probe numbers were computed ad hoc during the audit and are **not** a
committed artifact. Gate 2 must reproduce them from a committed script before any
of them enters the paper.

### Gate 1 — definitions, and an impossibility theorem (2026-08-24)

Gate 1 was scoped to write definitions. It also produced a theorem, which changed
v2's scope premise (see G1–G8 in `decisions/v2-design-decisions.md`). Offline
throughout; no LLM call was made.

**1. Definitions written.** `decisions/v2-definitions.md`: entropy of readiness
and of `needs_human` (additive by the independence in locked design 0a, so
`H(b) ∈ [0, 2.585]` bits exactly), expected information gain, value of
information, and cross-entropy/KL as the recalibration loss with its decomposition
into an irreducible conditional-label-entropy term plus a KL miscalibration term.
The decomposition matters for Gate 2: it gives the fit a floor, so "how much of
the remaining loss is even reducible" becomes answerable rather than rhetorical.

**2. A definition error made and caught, recorded so Gate 4 does not repeat it.**
VoI was first written as `V(b) − V_q(b) − EC(ask | b)` with `V` minimising over
*all* feasible actions. Since `ask` is in that menu, `V(b) ≤ EC(ask | b)`
identically, so the expression is non-positive for any matrix, any belief, any
question — a tautology, not a finding. It was caught by a symptom rather than by
inspection: a λ-sensitivity probe returned exactly `+0.0000` across a whole range
and a bisection returned a nonsense root. The fix is `V_act(b) = min` over the
feasible **non-ask** actions, used both as the baseline and inside the lookahead.

**3. The ceiling, and the impossibility.** Because every cost is non-negative,
`V_q(b) ≥ 0`, so `VoI(q | b) ≤ V_act(b) − EC(ask | b)` with no reference to any
answer model — it grants a free perfect oracle. `experiments/voi_ceiling.py`
evaluates it and writes `results/voi-ceiling.json`:

```bash
python3 experiments/voi_ceiling.py --json results/voi-ceiling.json
```

| quantity | value | source |
| --- | --- | --- |
| cases with a positive ceiling (constraints applied) | **0 / 100** | `per_case.n_positive_ceiling` |
| least negative per-case ceiling | −0.400, attained by 11 cases | `per_case.max_ceiling`, `.n_at_max_ceiling` |
| most negative per-case ceiling | −3.500 | `per_case.min_ceiling` |
| anchor case `a02-deep-018` | −0.500 (`V_act` 2.100 via `escalate_notify`, `EC(ask)` 2.600) | `per_case.anchor_case` |
| max over **every** belief, closed form | **−2/13 = −0.153846**, at all-hot, `b_h = 3/13` | `global_ceiling.ceiling_exact` |
| `max_b V_act(b)` | `α·ν/(α+ν)` = 30/13 = 2.3077 | `global_ceiling.max_v_act_exact` |
| `min_b EC(ask \| b)` | 2 | `global_ceiling.ec_ask_range` |

The bound is attained, not merely a bound: at `b_h = 3/13` on the all-hot vertex,
`hold = 84/13` and `escalate_pause = 66/13` both exceed the cap `30/13`. So the
cause is a price mismatch, not myopia — the payoff ceiling and the price floor do
not occur at the same belief.

Three independent cross-checks, all in the same artifact: the witness belief
re-evaluated through `src/costs.py`'s own `expected_cost` rather than the script's
arithmetic (agrees to `1e−9`); a deliberately dumb 60-per-axis grid search
(`−0.166667`, below the closed form, short by `0.0128` because `3/13` is not on a
`1/60` grid — and never *exceeding* it, which is the direction that would signal a
bug); and a bisection for λ (agrees to `1e−9`). Readiness-flatness and the two
monotonicity side conditions `−ν < c_T − c_F < α` are asserted rather than
assumed, so a future matrix edit fails loudly instead of returning a quietly wrong
optimum.

**4. v1's action census was a necessity, not an observation.** `V_act == V` on
100/100, so `ask` is never even the myopic argmin. v1 reported 0 asks in 100 cases
and read it as evidence about the one-step horizon; it was evidence about the
matrix. Same fact, read off the arithmetic instead of off the census.

**5. The claim is conditional, and the wording is now binding (G7).** On the menu
`no_direct_answer` leaves, the ceiling *does* go positive: up to **+1.000** at the
all-hot vertex with `b_h = 0`, and positive for `b_h < 1/5` along the all-hot ray,
bound by `escalate_notify`. Asking beats a needless escalation when a lead is hot,
a human probably is not needed, and answering is forbidden. But **none of the 8
cases carrying that constraint lands in the region**: all 8 are `a05-restricted`
and every one has `b_h ≥ 0.40`, because the archetype that forbids answering is
the one where a human is likely needed. The two conditions are anti-correlated by
construction. So 0/100 holds for a verified reason rather than by accident, and
the theoretical and empirical claims are stated separately everywhere.

This was nearly missed. The first probes ignored `row["constraints"]` entirely,
which understates `V_act` on exactly the cases where asking is most plausible. The
committed script applies each case's constraints via `feasible_actions`.

**6. The transferable result.** With `ask` priced at `(c_F, c_T)`, the ceiling can
be positive iff

    α·c_F + ν·c_T < α·ν        ⟺        c_F/ν + c_T/α < 1

v1 sits at `2/3 + 4/10 = 16/15 ≈ 1.0667`, so uniformly scaling the `ask` row turns
the ceiling positive at exactly `λ = 1/(16/15) = 15/16` — `ask` at
`(15/8, 15/4) = (1.875, 3.750)`, a reduction of exactly `1/16` = **6.25%**. A
first grid estimate put this at ~6.3%; the exact value is 6.25%. Reported as a
declared sensitivity computed on a local copy of the matrix; `voi_ceiling.py`
contains no assignment into `COST` (G6).

**7. Verification.** 337 tests pass. `robustness.py` still reports `legacy path
reproduces results/run.json exactly: True`, so nothing in Gate 1 disturbed the v1
baseline. `results/voi-ceiling.json` is byte-identical across repeated runs.

**A note on what changed against the plan.** Unlike Gate 0, none of these numbers
are ad-hoc probes: the artifact was written before the definitions were finalised,
specifically so the five figures in the draft trace to a committed file the way
every other number in the project does. Three corrections came out of that
discipline — 11 cases at the least-negative value rather than 8, 6.25% rather than
~6.3%, and the conditional-impossibility finding in item 5, which no ad-hoc probe
had surfaced.

### Gate 2a — logprob elicitation, built offline (2026-08-24)

Gate 2 asks whether reading the token logprobs behind `needs_human` recovers a
better-calibrated belief than the rounded decimal the model writes. 2a is
everything that does not touch the network: the code, the tests, the
pre-registration, and proof that the reproduction path works. **No API call has
been made.** `data/logprob_cache.json` does not exist.

**1. Two elicitors, one criterion.** `src/elicit.py` implements
`digit_expectation` (v1's `SYSTEM_PROMPT` sent byte-identical, scoring the
expectation over numeric alternatives at the value token) and `yes_no_probability`
(`P(Yes) / (P(Yes) + P(No))` at the first content token). Both at
`temperature=0`, `top_logprobs=20` — the API ceiling, asserted in
`test_top_logprobs_is_within_the_api_limit`.

The two are only comparable if they ask about the same event, so
`NEEDS_HUMAN_CRITERION` is extracted and asserted to appear verbatim inside both
v1's prompt and elicitor B's (`test_needs_human_criterion_is_verbatim_from_v1`).
A reworded v1 prompt fails that test rather than silently changing what B means.

The digit scorer has three tokenisation paths, because the tokeniser does not
promise which one it will use: `0` `.` `2` (weight the fraction digit), `0.85` as
one token (weight whole values), and a bare integer (alternatives are 0 and 1).
All three are tested with hand-computed expectations. Out-of-range alternatives
are dropped rather than clamped — a probability cannot be 5.0 — and duplicate
surface forms are summed rather than overwritten, since a dict assignment would
silently lose probability mass and show up as a wrong score rather than an error.

**2. One real bug found by writing the tests.** `score_yes_no` read `reads[0]`
blindly. With `max_tokens=3`, a model that emits a leading space would have made
an entirely ordinary response raise. It now scans to the first *content* token and
reports `leading_whitespace_tokens`. Found by
`test_yes_no_ignores_leading_whitespace_token`, which was written because the
whitespace case was plausible, not because anything had failed.

**3. The cache stores payloads, not scores.** An extraction bug must be fixable
offline, which is only possible if the token reads survive. `cache_entry` is
asserted to contain no `score` field anywhere in its JSON
(`test_cache_entry_stores_the_payload_not_the_score`), and `--rescore` recomputes
every number from the stored payloads with zero calls.

Three integrity guards, each verified by tampering with a copy of the cache and
confirming the specific refusal:

| tampered field | refusal |
| --- | --- |
| `observation_hash` | "does not match ... recomputed from cases.json. The message or context changed after the call" |
| `prompt_hash` | "does not match the current prompt. Scores across cases are only comparable if every case was asked the same question" |
| `schema_version` | "99 is not the expected 1 ... silently mixing schema versions is how a cache stops meaning one thing" |

`elicit.observation_hash` is the same function as v1's `belief.input_hash`
(`test_observation_hash_matches_v1s`), so the two caches can be joined per case.

**4. A contamination bug, found and fixed.** `--rescore` pointed at the dry-run
cache wrote a fully **reportable** `results/logprob-elicitation.json` out of stub
payloads, because `reportable` was keyed on the `--dry-run` flag rather than on
where the data came from. Provenance now travels with the payload
(`STUB_MARKER = "offline_stub"`), `reportable` is derived from the absence of that
marker across all rows, and the output stem is keyed on `reportable`. Re-verified:
`--rescore` against the stub cache emits "**NOT REPORTABLE.** 200 of 200 rows come
from the offline stub", writes only `_DRY` files, and creates no
`results/logprob-elicitation.json`. The contaminated file was deleted.

**5. Determinism verified.** Two consecutive `--dry-run` invocations produced a
byte-identical cache; run 2 made **0 calls against 200 cache hits**. The two
reports differ in exactly three fields — `generated_at`, `calls` 200→0,
`cache_hits` 0→200 — and with those stripped the remaining 135,673 bytes of
analysis are byte-identical. That is the property that lets the reproduction check
be a diff.

Four refusal paths verified: `--cache-only` on a missing cache refuses (exit 2,
"not in the cache, and this mode makes no calls"); `--dry-run --cache-only` is
rejected outright ("one invents payloads, the others refuse to"); a live run with
no key refuses through v1's existing config error; and the contamination case
above.

**6. The pre-registration is executable, not just written.**
`decisions/v2-gate2-preregistration.md` fixes the elicitor rule, the map rule, the
collapse diagnostic and the metric split — but the rules themselves are functions
in `src/calibrate.py` with their thresholds as module constants, so the rule is run
rather than remembered. `test_preregistration_matches_the_constants_it_reports`
fails if the document and the code drift apart. All 18 test names cited in the
document were checked to exist.

Two choices worth stating here because they were made before the data existed.
The collapse threshold of 9 distinct values is set against v1's grid, which has 8
— an elicitor producing 8 or fewer has recovered nothing it did not already have.
And R7's preference for an order-preserving map is enforced as a 0.02-bit margin
rather than a prohibition: isotonic regression merges distinct scores by
construction, the VoI half of this project reads the ordering of beliefs and not
only their level, so a merge has a cost cross-entropy does not price.

**7. Platt scaling can fail, and the failure is reported rather than absorbed.**
The dry run surfaced this: perfectly separable scores make the logistic MLE
diverge, and no finite `(a, b)` exists. The first error message blamed a singular
Hessian, which was the wrong cause. There is now a `SeparableError` raised from an
explicit separation check with a correct message; the driver catches it, drops
Platt from the candidate set, and records the exclusion in `maps_excluded`. No L2
prior was added — a prior is a knob, and a knob chosen after seeing the fit fail is
exactly what this gate pre-registers away. The stub's scores were also made to
overlap the labels, so a dry run exercises the ordinary path rather than the
degenerate one.

**8. The `.gitignore` conflict is fixed** (pulled forward from Gate 8, since the
reliability diagram is Gate 2's first figure). Line 32's negation
`!when-to-escalate/paper/figures/*.pdf` was being defeated by a later line
re-ignoring that exact figure — last match wins — so `paper/main.tex` could not
compile from a fresh clone. Verified with `git status --porcelain --ignored=matching`,
not `git check-ignore`: check-ignore exits 0 on *any* match including a negation,
so it reports the opposite of the truth here. A PDF in `paper/figures/` is now
addable (`??`); root-level `figures/` scratch and all three DRY artifacts remain
ignored (`!!`).

**9. The cache is now written incrementally, because 2b is the one irreversible
step in this gate.** Found while writing the handover: the driver saved the cache
once, after the loop. A rate-limit error or a scoring bug at call 190 would have
discarded 189 calls that were already paid for, and the only way back to the
failure point would have been to pay for all of them again. The loop is now
wrapped in `try/finally` with a `flush()` that persists every ten calls
(`CHECKPOINT_EVERY = 10`) and once more on the way out, whatever the way out is —
success, an API error, or a Ctrl-C. `save_cache` writes to a temporary file and
renames, so an interrupt during a flush leaves the previous cache intact rather
than a truncated one.

`flush()` is guarded on `calls > saved_at`, which matters more than it looks: the
refusal paths raise before any call, so without that guard a refusal would leave
an *empty* `data/logprob_cache.json` behind, and a later `--cache-only` run would
serve it as a legitimately empty cache. Verified that all four refusals still
create no cache file at all.

Checkpointing verified by running 24 stub calls and watching the writes land at
10, 20 and 24. The `finally` path verified by deleting a required field from the
fourth case, so the loop raises after that case's first call: the run crashed with
`KeyError: 'split'` and the cache on disk held 7 entries for the 7 calls that had
been made, with no checkpoint having fired. Both checks were run against a
throwaway cache path, not the DRY artifact.

This driver has no unit tests, which is v1's convention for `experiments/` — the
drivers are verified by running them. Recording that here rather than implying the
new code is covered: the two checks above are the evidence, and they are ad-hoc.

**10. Verification.** 474 tests pass — the 337 from v1 unchanged, plus 88 in
`test_calibrate.py` and 49 in `test_elicit.py`. Every expected value in the new
tests is derived in the test body rather than copied from a run, because a test
asserting whatever the code produced today cannot catch the code being wrong
today. Two boundary tests needed care: a margin comparison can only be exercised
exactly at its threshold when the subtraction is exact in binary, since
`0.51 - 0.50` is `0.010000000000000009` and lands strictly outside a 0.01 margin.
Both the exact boundary and the near-boundary case are asserted.

Determinism was re-checked after the incremental-save change, from an empty cache
rather than a warm one, so the comparison is against bytes produced by the old
code path. The rebuilt cache differs from the pre-change cache in exactly one
field, `generated_at`, across all 200 entries; the entry key sets are identical.
The analysis JSON differs in exactly four fields — `generated_at`, `calls`,
`cache_hits` and `mode` — and in nothing else. A second consecutive run made 0
calls against 200 cache hits and left the cache hash unchanged.

**What 2b costs.** 200 calls to `gpt-4o-mini` — 100 cases, two elicitors. Nothing
downstream of it has been run.

**What 2a has not verified.** Payload extraction is tested against hand-built
fixtures matching OpenAI's documented logprob response shape. No live call has
confirmed the real shape. `--limit 1` is a two-call smoke test for exactly this,
and those two calls are not wasted — they land in the cache and are served as hits
by the full run.

### Gate 2b — the live run, and calibration measured held-out (2026-08-25)

The elicitation ran live. `data/logprob_cache.json` holds 200 entries, all
`gpt-4o-mini-2024-07-18`, all stamped 2026-08-24 — and the two `a01-first-001` rows
are stamped 13:53:38/40 against 13:55:31 for the next pair, which is the `--limit 1`
smoke test having already banked them, so the incremental cache from item 9 above
served those two as hits rather than re-buying them. The full run's own paid-vs-hit
counters were printed to the terminal and are not in any committed file; the cache
timestamps above are what the record supports, and 198 paid is inference from them,
not a logged number. What *is* committed is the reproduction path exercised for
real: `--rescore` recomputes the entire analysis from stored payloads with
**`calls: 0`, `cache_hits: 200`**, 0 stub rows, `reportable: true`, and that
`mode: rescore` state is what this commit contains. Sources for everything below:
`results/logprob-elicitation.json`, `data/logprob_cache.json`, and
`results/rebaseline.json`.

**1. The pre-registered elicitor rule fired, and it overturned the prior
preference.** `digit_expectation` won on dev cross-entropy by a wide margin:

| elicitor | dev CE (bits) | dev ECE | dev Brier | distinct (pooled) | median top-1 | `collapsed` |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `digit_expectation` | **0.9934** | **0.1616** | **0.2294** | 85 | 0.7731 | `false` |
| `yes_no_probability` | 1.8004 | 0.3352 | 0.3224 | 19 | 0.9999999 | `false` |

The gap is 0.8071 bits against a 0.01-bit tie margin, so `tie_break_used: false`
and ECE never entered it. The lean before the run was toward Yes/No, and it was
never written into a file — which is precisely why the rule being fixed in advance
mattered. Picked on judgement, the worse elicitor would have been picked.

Both raw elicitors are *worse on dev than predicting the base rate*, whose
cross-entropy is the label entropy 0.9815 bits: Yes/No by 0.819 bits,
`digit_expectation` by 0.012. Reading logprobs does not by itself produce a useful
probability. The calibration step is what makes it one, which is why the claim
below is the held-out improvement and not the raw score.

**2. The collapse diagnostic missed what the metric caught, and the threshold is
not being retuned.** `collapsed` came back `false` for **both** elicitors and
`disqualified` is `[]`. Yes/No is the exact pathology §5 was written to catch —
median top-1 0.99999987, essentially all mass on one token, cross-entropy worse
than a constant — and it cleared the gate, because §5 requires **both** halves and
Yes/No produced 19 distinct values against a threshold of 9.

The reason is worth recording because it generalises. §5 fixes distinctness over
all 100 cases, on the stated ground that collapse is a property of the elicitor
rather than of a split. But pooling can only ever *raise* a distinct-value count,
so the pooled form of that half is strictly the more permissive one. Re-running the
pre-registered `calibrate.collapse_verdict` per split:

| elicitor | split | distinct | median top-1 | `collapsed` |
| --- | --- | ---: | ---: | --- |
| `digit_expectation` | dev | 48 | 0.77778299 | `false` |
| `digit_expectation` | test | 43 | 0.75991074 | `false` |
| `digit_expectation` | pooled | 85 | 0.77305676 | `false` |
| `yes_no_probability` | dev | **8** | 0.99999993 | **`true`** |
| `yes_no_probability` | test | 14 | 0.99999983 | `false` |
| `yes_no_probability` | pooled | **19** | 0.99999987 | `false` |

On dev — the split the elicitor is actually chosen on — Yes/No sits on exactly 8
distinct values, v1's grid size, and would have been **disqualified**. The two
splits land on different subsets of the residual values, so pooling more than
doubled the count past the threshold. The transferable form: *a threshold on a
count of distinct values is not scale-free, and pooling `n` upward loosens it
monotonically* — a count threshold has to travel with the `n` it is counted over.

The thresholds are not changed and §5 is not rewritten. The rule fired as written,
the metric caught what the diagnostic missed, and a threshold edited after seeing
the data it governs is worth nothing. Recorded as Q9 rather than quietly fixed.

**3. Isotonic won inside R7's margin, and the merge cost is now measured.** On dev:
identity 0.9934 bits, Platt 0.9103, isotonic 0.8356. Isotonic beats the best
order-preserving candidate by 0.0747 bits — more than R7's 0.02 — so
`override_applied: false`. `maps_excluded` is empty: the `SeparableError` that
dropped Platt in the dry run was an artifact of the stub's separable scores and did
not recur on real data, so item 7 above describes a path that real data never took.

The predicted cost of the merge showed up exactly where R7 said it would. The
chosen map is `strictly_monotone: false` with 12 knots, seven of them at 1.0, and
`order_preserved_on_test: false`. **Carried to Gate 4 as an open flag**, unchanged
here: the VoI ceiling reads the ordering of beliefs and not only their level, so the
ceiling re-run has to state which scores it uses and must not assume the merge is
free. R7 priced the merge in bits; bits are not what Gate 4 reads.

**4. The Gate 2 result, held out.** Fitted on dev, evaluated on test, never the
other way:

| metric | raw | calibrated |
| --- | ---: | ---: |
| cross-entropy (bits) | 0.8546 | **0.8136** |
| ECE | 0.1526 | **0.0696** |
| Brier | 0.2063 | **0.1962** |

The decomposition puts the gain where it belongs: miscalibration falls 0.1643 →
0.0988 bits, while the irreducible conditional label entropy rises 0.6893 → 0.7321
as the merge coarsens the bins. Residual −0.0172 bits on the calibrated side.
ECE more than halves. That is the honest, held-out, measurably-better-agent half of
v2, and it is the Gate 2 claim.

**5. Temperature-0 reproduction is 89 of 100, and v1 cannot say why.** Elicitor A
sends v1's prompt byte-identical at `temperature=0`, so the value it writes should
equal `data/belief_cache.json`. It does for 89 cases; 11 differ, 0 unparseable,
largest move `a04-booking-040` 0.9 → 0.3. Both runs requested the same alias
(`config.DEFAULT_OPENAI_MODEL = "gpt-4o-mini"`), but v1 stored the alias it asked
for while v2 stores the snapshot the API resolved to — so a snapshot change between
2026-08-19 and 2026-08-24 and serving-side nondeterminism fit the evidence equally
well, and nothing here distinguishes them. That is a v1 record-keeping gap, not a
finding about the provider, and it is written up as limitation **L10** with the fix
already in place from v2 on: store the resolved model id, which v2's cache does.

**6. The re-baseline, because the drift makes a naive before/after meaningless.**
v1's published 1.720/16 was computed on beliefs that cannot be reproduced, so
comparing it against a calibrated v2 number would conflate the map with the drift.
`experiments/rebaseline.py` (no API calls, cache-only) scores three arms on the
test split using v1's own cost matrix, v1's own miss definition and v1's own
`choose_action`, varying one thing at a time:

| arm | beliefs | `needs_human` from | mean cost | missed esc. | escalates |
| --- | --- | --- | ---: | ---: | ---: |
| published (v1, committed) | v1 cache | written digit | 1.7200 | 8 | 20/50 |
| re-baselined | fresh | written digit | 1.7200 | 8 | 20/50 |
| raw continuous | fresh | logprob expectation | 1.4000 | 7 | 21/50 |
| calibrated | fresh | isotonic(raw) | 1.5000 | 2 | 41/50 |
| *always_notify* (reference) | none | *ignores the belief* | *1.7400* | *0* | *50/50* |

The map is reconstructed from the committed knots rather than refitted — a second
fit is a second chance to land on different parameters — and verified against every
stored recalibrated score at a 1e-12 tolerance, which it clears exactly
(`map_reconstruction_max_delta: 0.0`). The tie-break rule is
irrelevant here: legacy and fixed give identical mean cost and misses on all three
arms, reported rather than assumed. `always_notify` is in the table because it
ignores the belief entirely, so its cost is a function of the labels alone and no
drift can move it — verified by recomputing it from labels (total 87, mean 1.7400).
It is the yardstick an arm escalating 82% of the split has to be held against.

**7. On the decision metrics, calibration is a trade-off, not a win.** Misses fall
7 → 2 while mean cost **rises** 1.4000 → 1.5000. The mechanism is in the action
counts: the map lifts the low scores enough that the myopic rule escalates 41 of 50
instead of 21, so recall goes 0.6667 → 0.9048 and precision goes 0.6667 → 0.4634.
Better-calibrated probabilities slide the operating point toward recall; they do not
dominate the uncalibrated arm on both metrics at once. The −5 misses does exceed
R5's "one or two is not evidence" floor, and is written as exceeding it *while
arriving with a cost increase and a precision drop*. This is a finding about the
fixed cost matrix and the one-step rule, not a defect in the map — and it is why
Gate 2's claim is item 4 and not this table.

**8. A false stability claim, caught before it was written.** Published versus
re-baselined comes out identical — 1.7200, 8 misses, the same action counts — which
reads as "the beliefs are stable" and is not true. Six written values moved on
test; three crossed a decision boundary and their realised-cost deltas cancel
exactly (`a02-deep-017` 0→10, `a10-persistent-091` 3→0, `a11-repeated-100` 10→3),
while the action counts cancel term for term. The missed-escalation *set* changed
even though its size did not: drift fixed `a10-persistent-091` and introduced
`a02-deep-017`. Reported as an aggregate alone, this gate would have carried a
claim the data contradicts. Cross-date aggregates get a per-case table from here on.

**9. Verification.** 474 tests pass, unchanged from 2a — this gate added a driver,
not library code. `rebaseline.py` is deterministic across consecutive runs: two
invocations differ in `generated_at` and nothing else, in both the JSON and the
rendered report. It makes 0 API calls by construction and refuses outright if the
elicitation results are absent, marked not reportable, or contain stub rows. Two
corrections were made to it during review rather than after: duplicate definitions
of `belief_free_reference` and `drift_on_test` had accumulated, one pair referencing
an undefined name, and the drift write-up asserted a provider-side cause the record
cannot support. Like the drivers in `experiments/`, it has no unit tests — v1's
convention — so those checks are ad-hoc and this entry says so rather than implying
coverage.

**What Gate 2 has not done.** The reliability diagram (Q5) is still unwritten; it
consumes this output and is the one deferred item. Nothing downstream of Gate 2 has
been re-run against the calibrated beliefs, and the `order_preserved_on_test: false`
flag is carried, not addressed.

### Gate 3 — the question set, the answer model, and a withdrawn illustration (2026-08-25)

Gate 3 owed three things: a question set drawn from what the cases actually leave
ambiguous, an answer model with every assumption written down, and the six-vector
adapter OQ1 asked for. It makes **zero API calls** — the answer model is a
committed table and the beliefs come from `results/run.json`. Every number below is
from `results/answer-model.json`.

**1. The tables were locked before the computation existed, and the git history is
the proof.** `decisions/v2-gate3-preregistration.md` and `src/questions.py` landed
in one commit (`83217d8`): 2 files, 621 insertions, with
`experiments/answer_model.py` verified absent from the tree. Same mechanism Gate 2
used — the rules are module constants, committed before the run — so "the entries
were fixed before any information gain was seen" is checkable rather than asserted.
§7 names the violation in advance: `answer_model.py` existing in any commit that
does not already contain the filled tables.

Two things were corrected during the drafting, both before the lock. The
pre-registration first described the tables as "54 entries", which overstates how
tunable the model is: the axis-only questions repeat rows across the other axis and
every row is constrained to sum to 1, so the **free parameters are 22**, and 22 is
what the §5 sweep perturbs. And a first draft of the `q_timeline` table would have
made the pre-registration's own separability claim false; the exact `separates()`
check caught it while the tables were still being written. The 54 entries are
**(AI-proposed, Kaps-reviewed)** — drafted by Claude, reviewed by Kaps — and are
never described as practitioner-set anywhere, which is asserted by a test rather
than left to review.

**2. Information gain per question**, mean and range over the 100 beliefs, in bits
against a maximum possible `H(b)` of 2.585:

| question | targets | separable | mean IG | min | max | max at | cases with IG < 0.01 |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| `q_timeline` | readiness | True | 0.1290 | 0.0000 | 0.1540 | `a07-price-066` | 1 |
| `q_authority` | needs_human | True | 0.1278 | −0.0000 | 0.1999 | `a09-oversharer-082` | 4 |
| `q_specifics` | both | False | 0.1040 | 0.0000 | 0.1319 | `a10-early-086` | 1 |
| `q_null` | none | True | 0.0000 | −0.0000 | 0.0000 | — | 100 |

`q_null` is the control: its answer cannot depend on the state, so the equality case
of Gate 1 §2 forces `IG = 0`, and having it in `Q` makes that an executed assertion
instead of a sentence. The `−0.0000` entries are float rounding on cases whose true
value is exactly 0 — the most negative IG anywhere in the 400 question-case pairs is
`−4.44e-16`. Reported rather than clamped, so a real sign error could not hide
inside a tolerance.

**3. The coupling term is an independent check on separability.** `IG = IG_r + IG_h
+ I(R ; Hh | U)` holds exactly, and the residual is under `1e-12` on all 400 pairs.
The third term is the coupling an answer induces between the two axes, and it is
what makes the six-vector necessary. `q_specifics` is the only question with any:
mean 0.004283 bits, max 0.008493, and a coupled posterior on **96 of 100** cases.
The other three sit at zero up to float noise. That agreement is evidence rather
than restatement, because `separates()` is a rank-1 test on the integer table while
the coupling term is an entropy computed from the posteriors — two different
computations reaching the same verdict.

**4. The adapter, both directions — OQ1 discharged.** All 100 priors round-trip
`Belief → six-vector → Belief` to within `1.11e-16`. A coupled posterior arose in
the run rather than having to be constructed: `a01-first-001`, `q_specifics`, answer
`concrete` at `P(u) = 0.4488`, max deviation from the product of its own marginals
`6.80e-04`. `narrow()` raised on it instead of projecting. `Belief` is unmodified —
fields still `readiness` and `needs_human`, cache format and policy signature
untouched — which is what OQ1(b) required.

**5. The sweep fired its pre-registered fragile branch, so the illustration is
withdrawn.** 22 free parameters × 4 deltas = 88 variants, the unit being a distinct
table row, one non-`no_answer` entry at a time with the row renormalised. Baseline
order by mean IG: `q_timeline` 0.1290 > `q_authority` 0.1278 > `q_specifics` 0.1040.

- Order flips: **27 of 88**, **11 of them at `±0.05`**
- Largest shift in any one mean IG: 0.0786 bits
- Entries clipped to `[0.01, 0.99]`: 1; smallest entry after renormalisation 0.0100
- Fewest cases holding the baseline per-case order: 14 of 100
- Distinct orderings seen across the 88 variants: **5 of the 6 possible** — the
  baseline in 61, `q_authority > q_timeline > q_specifics` in 14, and three others
  in 6, 4 and 3

§5 pre-registered this reading: "If the ordering flips under a `±0.05` perturbation,
the answer model is too fragile to illustrate anything, and that is the finding —
reported as such, with the illustration withdrawn rather than repaired by choosing
better entries." Eleven flips at `±0.05`, so that is the verdict, recorded verbatim
in both artifacts. The grid is not changed and the sweep is not re-run on a
different one.

What this withdraws is the IG-ordering claim and the use of these magnitudes as a
stable illustration. What it leaves alone, because the sweep does not bear on them:
the eight invariants, the OQ1 adapter, and the impossibility result, which is
answer-model-free — `VoI(q | b) ≤ V_act(b) − EC(ask | b)` follows from
`V_q(b) ≥ 0` alone, grants a free perfect oracle, and so cannot be defended or
undermined by any sweep over likelihoods. That last point also corrects OQ3's
"load-bearing defence" line, recorded as S1 in the design record.

**6. Why it is fragile — and a first reading of it that was wrong.** Post-hoc
diagnosis, marked in the JSON as `post_hoc: true, changes_the_verdict: false`:

| delta | variants | flips | max shift in one mean IG | flips won by > 0.002 bits | post-flip top margin |
| ---: | ---: | ---: | ---: | ---: | --- |
| ±0.05 | 44 | 11 | 0.0341 | 9 | 0.00025 to 0.0317 |
| ±0.10 | 44 | 16 | 0.0786 | 14 | 0.00021 to 0.0774 |

The three mean IGs span **0.0250 bits** while a single `±0.05` perturbation of one
entry moves one of them by up to **0.0341 bits**. The ordering test was asked to
resolve a signal smaller than its own step size.

The first two readings of this, both mine, called the flips a near-tie artifact —
fourth-decimal noise crossing gaps of 0.0001 to 0.0016 bits. That was wrong, and
the mistake was reading the *gap crossed* as the margin. The margin that matters is
the one after the flip, and 9 of the 11 flips at `±0.05` leave the new winner ahead
by more than 0.002 bits, one of them by 0.0317. They are decisive re-orderings, and
the sharper answer is the one recorded.

The grid was written in absolute probability units and never checked against the
spread of the quantity it had to order. An absolute 0.10 is 14% of a 0.70 entry and
100% of a 0.10 entry, so the same grid is a mild perturbation in one place and a
total one in another. **This is the second time in v2 that a rule was written in
units it was never checked against** — the first was Gate 2's collapse diagnostic,
a threshold on a raw count of distinct values that loosened monotonically as `n`
grew. Recorded as a class to watch rather than a second one-off, with the pre-lock
check for Gate 4 onward, as S4 in the design record.

**7. The free check the data hands over, and it passes.** Four cases sit at
`b_h = 0.0` exactly, so `H_h = 0` and no answer can reduce it; one of them also has
a degenerate readiness belief, so `H(b) = 0` on both axes and invariant 5 forces
`IG = 0` for every question:

| case | b_h | H_r | H_h | H joint | max IG over Q |
| --- | ---: | ---: | ---: | ---: | ---: |
| `a08-reaction-075` | 0.00 | 1.1568 | 0.0000 | 1.1568 | 0.142598 |
| `a08-reaction-077` | 0.00 | 1.1568 | 0.0000 | 1.1568 | 0.142598 |
| `a11-first-095` | 0.00 | 0.4690 | 0.0000 | 0.4690 | 0.031862 |
| `a11-repeated-097` | 0.00 | 0.0000 | 0.0000 | 0.0000 | 0.000000 |

`H_h = 0` on all four, `IG_h = 0` on all four for every question, and `IG = 0` for
every question on `a11-repeated-097`. It would have failed loudly on a sign or
normalisation error in the entropy code, which is why it was stated in the
pre-registration in advance rather than found afterwards.

**8. Verification.** All eight invariants hold with **0 violations across all 400
question-case pairs**. The suite is **510 tests passing in 0.42s**, up from 474 —
Gate 3 added library code, so unlike Gate 2b it added tests. Both artifacts are
byte-identical across consecutive runs and carry no `generated_at` key, so
determinism is exact rather than modulo a timestamp. `answer_model.py` contains no
API-capable import, asserted structurally by a test rather than by inspection.

The 36 new tests passed on the first run, which is weak evidence that they test
anything, so four mutations were introduced to check: changing a sweep delta,
making `narrow()` project onto the marginals instead of raising, changing a
free-parameter count in the document, and using `H_r + H_h` for the posterior
entropy instead of the joint. All four were caught, by the prose-matches-constants
test, three adapter tests, the prose test again, and the decomposition test. The
tree was restored afterwards. Two AI-narration artifacts and one nonsense
expression were also removed from `answer_model.py` during review, and four
rendering defects were found by reading the generated report rather than trusting
it — `.capitalize()` lowercasing "IG" to "ig" mid-string among them.

**What Gate 3 has not done.** The answer model is **not validated**: nothing in the
data can confirm these numbers, because the cases are single messages with no
answers to fit to. A1 — the answer depends on the hidden state and not on which
case is being asked about — is false in detail and accepted for the reason given in
the pre-registration. No claim about `ask` follows from any number in this gate.
The reliability diagram (Q5) is still the one item carried from Gate 2, and
`order_preserved_on_test: false` is still carried, not addressed.

### Gate 4 — four belief arms, a calibration floor, and abstention priced (2026-08-26)

Gate 4 owed three things: the answer-model-free ceiling recomputed on the belief
sets Gate 2 produced, the cost of abstention measured rather than argued, and the
reliability-diagram data path Q5 has been carrying since Gate 2. It makes **zero API
calls** — every belief comes from `results/run.json` or
`results/logprob-elicitation.json`, and the cost matrix is read, never written.
Every number below traces to `results/voi-ceiling-arms.json`,
`results/abstention.json`, or `paper/figures/make_figures.py --check`.

**1. The pre-registration was locked first, and the git history is the proof again.**
`decisions/v2-gate4-preregistration.md` landed alone in `785adce`: 1 file, 404
insertions, with `experiments/abstention.py` verified absent from that tree. The
arms re-run followed in `d537ec2` and the abstention measurement in `874ecf2`. §9
names twelve conditions that would make the document false, including "τ defined in
absolute bits anywhere", "the analytic half of §4 written up as a finding", and "the
abstention call made on anything other than the measured numbers". All twelve held.
Two are checkable mechanically and were checked: nothing under `src/` and neither
`results/run.json` nor `results/voi-ceiling.json` changed between the lock and the
close, and no `COST[...] =` assignment exists anywhere in the repo.

**2. Four belief arms, and the part of the result no arm can move.** The arms are
`published` (the committed Gate 1 run), `rebaselined` (the cache's written digit
with fresh readiness), `raw` and `calibrated`. The last three share one fresh
readiness vector and differ only in `needs_human`, so each contrast isolates the
component that changed.

| arm | `b_h` range on test | positive ceilings | least negative | `V_act` argmin census |
| --- | --- | ---: | ---: | --- |
| `published` | 0.0000–0.9000 (8 distinct) | 0 / 50 | −0.4000 | `{answer: 30, escalate_notify: 43, hold: 27}` |
| `rebaselined` | 0.0000–0.9000 (9 distinct) | 0 / 50 | −0.4000 | `{answer: 29, escalate_notify: 44, hold: 27}` |
| `raw` | 0.0000–0.8996 (100 distinct) | 0 / 50 | −0.2598 | `{answer: 25, escalate_notify: 45, hold: 30}` |
| `calibrated` | 0.2609–1.0000 (84 distinct) | 0 / 50 | −0.4640 | `{escalate_notify: 83, hold: 17}` |

Nothing crosses zero, on either split, on any arm. That is not the interesting part.
`V_act(b) ≤ min(α·b_h, ν·(1−b_h))` for every belief and `EC(ask | b)` is flat in
readiness, so `max_b [V_act(b) − EC(ask | b)]` is a function of the cost matrix
alone — `−2/13` = −0.153846 — and on the unconstrained action menu the claim that
the impossibility survives recalibration is **analytic**. The artifact says so in
§2, not only the paper. Checked rather than assumed: the seven belief-independent
sections are identical across all four arms by exact equality of
`json.dumps(section, sort_keys=True)`, and the script refuses to report a contrast
if they ever differ. §4's regression guards reproduce counts
`results/rebaseline.json` already commits, including the calibrated arm's zero
`answer` decisions on test, and state that this shows the arm loader rebuilds the
same beliefs rather than discovering them.

**3. The calibration floor, which is the finding.** The committed isotonic map
cannot emit a score below `6/23`, and both thresholds that would let `answer` or
`ask` fire sit beneath it:

| | exact | float | what it is |
| --- | --- | ---: | --- |
| positive-VoI region bound | `1/5` | 0.200000 | `b_h` below which the constrained-menu ceiling is positive, on the argmax ray |
| t\* | `3/13` | 0.230769 | `ν/(α+ν)`, where `answer` stops beating `escalate_notify` |
| the map's floor | `6/23` | 0.260870 | the lowest score the committed map can emit |

`1/5 < 3/13 < 6/23`, all three within 0.061 of each other, which is why they are
carried as exact rationals: at 2dp the ordering is invisible. PAVA sets each pooled
block's level to that block's positive rate, and the lowest block pooled 23 dev
cases carrying 6 positives. All 12 blocks were recovered from the committed knots
and the committed dev scores without refitting, each level checked against its own
`positives / n`; the blocks cover 50 dev cases with 21 positives. Prediction
interpolates linearly between knots and clamps outside them, so the image of ℝ is
exactly `[6/23, 1]` — the flatness outside the fitted interval is what makes the
floor a bound on the whole real line rather than only on the fitted range. The floor
is attained by 1 case (`a11-repeated-097`, dev); interpolation lifts the other 22 in
that block strictly above it, so the bound is on the range and not a claim about how
many cases land on it.

Two consequences. `answer` is unreachable: 0 of 100 calibrated beliefs fall below
t\*, against 48 raw ones. And the positive-VoI region is unreachable: 0 calibrated
beliefs meet even the necessary condition `b_h < 1/5`, against 31 raw ones — of
which 0 also carry `no_direct_answer`.

Those two emptinesses are not the same kind and are not merged. For `calibrated` the
region is unreachable **by construction**: no input can produce a `b_h` below the
floor, so the necessary condition fails for every belief the map can emit. For
`published`, `rebaselined` and `raw` the bound **is** reached, and the region stays
empty only because none of the cases reaching it carries the constraint — a
contingent fact about these 100 cases. `b_h < 1/5` is also necessary and not
sufficient: `1/5` is the bound on the most favourable ray in the simplex, and the
sufficient test is the per-case ceiling with constraints applied, negative on all
400 case-arm pairs.

What generalises is not `6/23`. It is that **an isotonic map fitted by PAVA has a
reachable range bounded below by the positive rate of its lowest pooled block, so a
fixed decision threshold beneath that rate cannot fire post-calibration however many
bits of discrimination the map buys.** A calibration map has a reachable range and a
fixed-threshold policy has thresholds; cross-entropy and Brier score never check
that the thresholds sit inside the range. This does not say calibration is harmful —
the calibrated arm escalates more and misses fewer cases needing a human, which is
Gate 2's result and stands — nor that the map is misfitted; `6/23` is the correct
positive rate for that block.

**4. Abstention costs more than it saves, on every arm at every τ.** The matrix
settles most of it before any belief is loaded. `escalate_pause` costs strictly more
than `escalate_notify` in all six labelled states — +3/+2/+2 with `needs_human`
false, +2/+1/+1 with it true — so any notify→pause rule raises realised cost on
every case it touches; and `is_escalation` counts both actions, so no such rule can
change the miss count. What remained to measure is how many cases each rule touches.

| variant | published | raw | calibrated |
| --- | --- | --- | --- |
| baseline (test) | 86 cost, 8 misses | 70, 7 | 75, 2 |
| (b) fallback rewrite | 20 cases, +32, miss Δ 0 | 21, +33, 0 | 41, +74, 0 |
| (a) `H(b) ≥ τ` override | beats baseline at no τ | no τ | no τ |

(a) loses at all 33 arm-τ pairs; the cost of a miss it does avoid runs from 7.5
(published, q=0.7) to 72.0 (calibrated, q=0.3). Firing on all 50 test cases costs
177 as pause against 87 as notify, identically on all three arms, because both
figures depend only on labels. The resolution is (c): the diagnostic flag stays, the
override is dropped. **This is the abstention analogue of the impossibility result —
the existing minimum-cost policy already handles the "stop and hand off" case
correctly, so an abstention override is machinery the cost structure provably does
not need.** (Kaps-decided, on the measured numbers, at the close.)
`results/abstention.md` §8 records the call as open at the time it was written and
states that it recommends no variant; the decision is in the design record instead,
which is the ordering the pre-registration exists to enforce.

**5. τ was locked as deciles, and 12 decimal places of `H(b)` turned out to be
load-bearing.** S4's pre-lock check ran and earned itself: published `H(b)` spans
0.000000–2.456426 bits with 8 distinct values, so an absolute grid over the 0–2.585
theoretical range would have put most of its points where almost no cases live.
Deciles of the observed distribution on the arm being scored make the step
commensurate by construction, and both the quantile and the absolute bit value are
reported per arm with cross-arm incomparability in absolute bits declared.

Underneath that, mathematically equal `H(b)` values differ by up to 8.88e-16, and
two identical published deciles were firing on 49 cases and 44. `H(b)` is now
quantised to 12 decimals before any comparison, collapsing exactly 5 spurious
distinctions on published (24 → 19) and none on raw or calibrated. The guard is
non-circular by construction: the noise bound is derived independently as
`8 · math.ulp(max|H|)` = 3.55e-15, the 1e-12 tolerance is asserted to sit strictly
between it and the smallest genuine gap per arm (9.99e-03 published, 3.92e-05 raw,
4.97e-06 calibrated), and gaps are classified by the noise bound rather than by the
tolerance. Negative controls sit at both ends: `H_DECIMALS = 2` is refused for
crossing the signal, `H_DECIMALS = 17` for sitting below the noise. Without it the
artifact would have shipped two wrong firing counts.

**6. `--check` found a wrong bracket in the paper on its first run.** Q5's data path
landed: `figure_data()` now returns three panels — v1's `needs_human` diagram, and
the Gate 2 test-split raw and calibrated diagrams — and `check()` re-derives every
plotted number from the per-case records, taking ECE, cross-entropy in bits, Brier
and base rate to 1e-12 and asserting no test score falls below `6/23`. `_bin_index`
and `_ece` are restated in the module rather than imported from `src.calibrate`,
which is what wrote the committed tables; re-deriving a number with the function
that produced it checks nothing.

It failed immediately, on a real defect. The shaded band carries two claims with two
different brackets. No case takes a **value** in `(0.2, 0.3)` — open at both ends,
because 17 of the 100 cases sit at exactly 0.3. Every **threshold** in `(0.2, 0.3]`
decides identically — half-open, because the rule is `answer iff b_h < t`, so a
threshold at 0.3 leaves those 17 cases on the escalate side exactly as `3/13` does.
The script, its render legend, and two lines of `paper/main.tex` all wrote the
threshold bracket on the value claim. The script and legend are fixed, and the
threshold claim is now verified as a partition identity —
`partition(3/13) == partition(0.3)` is True, `== partition(0.2)` and
`== partition(0.4)` are False — rather than inferred from the emptiness of the gap.
`paper/main.tex:499` and `:728` are recorded for the paper gate rather than edited
by a figure script; `:971` is a threshold claim and its bracket was already right.
The pre-registration's own bracket on that region was also right; it is the
manuscript that drifted.

Rendering stays deferred. matplotlib is absent from the test environment, so
shipping a render path now would ship something untested; panels 2 and 3 declare
`renders: false` and name the paper gate. The test file's negative controls doctor
the committed payloads and assert each check family fires — including on a
deliberately stale panel-versus-records pair, because the shaded band is derived and
within one payload the band and the check move together and cannot disagree.

The suite is **654 passing** at the close, from 510 at the open.

**What Gate 4 has not done.** No `ask` feature was built and nothing was tuned to
make `ask` fire; the abstention override was measured and dropped. The unconstrained
impossibility is not an empirical result of this gate and is not written up as one.
The floor is a property of this fit on this dev split — what transfers is that a
floor exists and equals the lowest block's positive rate. `order_preserved_on_test:
false` is discharged rather than carried, and the flag turned out to overstate the
risk: isotonic regression is weakly monotone, so it cannot invert two cases, only
send them to the same value. On the test split there are **0 inversions and 16
merged pairs** at full precision (31 at the pre-registered 3dp). The ceiling is also
pointwise in the belief — `EC(ask | b) = 2 + 2·b_h` and `V_act` is a minimum over
that same belief — so it reads levels and not ranks, and merging cannot move it in a
direction the per-arm tables do not already show. The figure renders nothing yet,
and two `.tex` brackets are knowingly still wrong pending the paper gate.

### Review pass before Gate 5 — merge policy reversed, three paper debts (2026-08-26)

No new measurement. A read over the four closed gates before the last four open,
recorded as M5 and V1–V3 in `decisions/v2-design-decisions.md`.

**The merge policy is reversed.** Everything stays on `v2` and there is one merge to
`main` at the very end, with `v2.0.0` tagged at Gate 8 behind `v1.0.0`. This
supersedes M1 and M2, which had gates merging one at a time as they closed. The
reason is that keeping `main` current serves nobody on a single-person branch, and
the backlog — 26 commits, `git rev-list --count v2..main` = 0 — is pushed, so not
merging risks nothing. M3 and M4 describe what a merge carries and are unaffected.

**v1's paper answers to two of its own three open questions.** `main.tex:1039` asked
for a finer-grained belief and a held-out recalibration fit; Gate 2 did both.
`main.tex:1050` asked whether `ask`, scored by one-step value of information, earns
its place; Gates 3 and 4 answer no, and analytically rather than on these cases. The
third, the turn boundary at `main.tex:1060`, is untouched by v2 and stays open.

**Three defects in `main.tex` beyond U7's brackets.**

`reliability-needs-human.pdf` has never been committed on any branch — `git log
--all --diff-filter=A` finds no add — yet `main.tex:719` includes it and the tracked
`main.pdf` embeds it, three Form XObjects with the filename in the PDF body. It was
built from an untracked local file while the root `figures/*` rule still ignored it.
The published artifact therefore carries a figure no clone can rebuild. Q4 cleared
the `.gitignore` obstacle; the file itself is still missing and `render()` has never
been executed, matplotlib being absent.

`main.tex:683` says `ask` "can only win in a narrow middle band that the quantized
beliefs never land in." There is no such band on the unconstrained menu — the
maximum over every belief is `-2/13` — and quantization is not the cause either,
since the raw arm's 100 distinct beliefs leave the region empty too. Heavier than a
bracket, and it is where the theorem belongs.

`main.tex:1045` attributes v1's floor to elicitation granularity "not the calibration
method." Gate 4's floor, `6/23`, is set by the calibration method. Both are true of
different objects; under one word they read as a contradiction.

The `.gitignore` item the G-series paragraph lists as Gate 8's one open technical
item was discharged by Q4 during Gate 2a. The paragraph is left as written per the
G9/G12 rule; the correction is a line in the new section. Gate 8's remaining items
are the two tags and the single merge.

The suite is unchanged at **654 passing**, and `make_figures.py --check` exits 0.
