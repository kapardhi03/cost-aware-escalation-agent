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

### Gate 5 — the ask baseline priced, and the bound attained (2026-08-26–27)

The first per-case VoI computation in the project: not the analytic bound but the whole
`V_q` term, over 400 case-question pairs on each of four belief arms, with the
entropy-threshold ask baseline priced over the pre-registered decile grid for τ. The
pre-registration was committed before any of these numbers existed.

Entropy-thresholding is never free. At the cheapest threshold that asks at all — the
0.9 decile, 5 or 6 of 50 test cases — it costs +13.80 realised on published, +7.70 on
raw and +5.60 on calibrated. Ask on everything and it costs +113.62 to +128.02. There
is no threshold on any arm at which asking pays for itself, and the answer-model-free
expected tier is positive at every firing threshold on every arm. That is the baseline
sentence §6 was owed.

Invariant 6 was supposed to be the cross-check tying this gate's VoI to Gate 4's
ceiling, and it is a tautology. Its slack equals `V_q` to within 7.77e-16, so
substituting VoI's definition cancels the other two terms and the invariant reduces to
`V_q ≥ 0` — free, since every entry of `costs.COST` is non-negative. It passes on all
400 pairs per arm and its passing is worth close to nothing. The pre-registration is
locked and was not edited; the correction is X2.

`ceiling_agreement` is the check that was actually wanted: a different invariant with
the same intended outcome. Recomputing `EC(ask | b) − V_act(b)` from the beliefs
against the per-case ceilings committed in Gate 4 gives a maximum delta of exactly
**0.0** on all four arms — bit-identical, because `widen` mirrors `state_probability`
and `STATES` iterates in the order `expected_cost` sums in. Two further routes agree:
`EC(ask | b)` against the exact `2 + 2·b_h` of invariant 5 to 8.9e-16, and `V_act`
recovered as `ceiling + EC(ask | b)` to 2.2e-16. Non-positive tier-1 excesses: 0 of
400 on every arm.

The bound is attained, not merely respected. `V_q = 0` exactly on 16 published, 12
rebaselined, 0 raw and 52 calibrated pairs. On those pairs a free, perfect oracle
drives the post-answer expected cost to zero and asking still loses by the full
`−ceiling`. The ceiling's negativity is therefore not slack in the bound, and on
roughly a quarter of the calibrated pairs there is no slack to be had. Raw has none
because its beliefs are continuous. This is the gate's real new content, and it goes
in the theorem section as a second beat sharpening the main claim rather than as a
separate finding.

Three things the pre-registration did not anticipate. A cost-side adapter was needed:
`costs.expected_cost` requires a factorised belief, `q_specifics` produces posteriors
that do not factorise, and `narrow` raises rather than projecting onto marginals — so
`ec_joint` prices the joint directly and is asserted to agree with `expected_cost` on
all 500 (prior, action) pairs, maximum delta 0. Each arm is scored against its own
committed v1 total — 86, 86, 70, 75 — and not against published's 86; the first
version of the render printed 86 under every table while computing each excess against
the arm's own total, which is S4's shape in a new place. And the realised column is not
monotone in τ.

The exception is worth keeping. The expected tiers must fall as τ rises, since the
firing sets are nested and every firing case contributes a positive excess, and both
are now asserted. The realised column carries no such guarantee: on the rebaselined
arm the firing count falls 12 to 11 between the 0.7 and 0.8 deciles while the realised
total rises 109.60 to 113.60. One case does it. `a02-deep-017` leaves the firing set;
v1 answers it and eats a realised 10 where ask-then-act realised 6. Its expected
tier-1 excess is `+0.40` throughout. Asking was expected to lose that case and won it
— the cleanest illustration in the repo that the impossibility result constrains
expected cost and says nothing about a single realised draw. It is written off the case
and not off that arm's totals, which carry no claim.

The anchors hold. Terminal `always_ask` pricing from v1 is 142 total, 2.84 mean; the
same 50 cases under ask-then-act cost 199.62, mean 3.9924, strictly dearer as required
— the follow-up action is not free. Invariant 8 reproduces v1 exactly on the published
arm: 0 mismatches across 100 per-case actions and a recomputed test aggregate of 86
total, 1.72 mean, on v1's legacy tie-break. It is checked on the published arm only,
because asserting it on a rebuilt arm would be asserting that recalibration changed
nothing. The VoI oracle agrees with argmax-IG on 29 of 50 test cases, which is why the
ordering-fragile IG route stays secondary.

The honesty check is named self-consistency, never validation: the exact expectation of
199.62 against a Monte Carlo mean of 199.607 over 2000 draws, delta 0.013, seed
20260826. The answer is simulated from the same `P(u | s)` that produced the
prediction, so it is circular with respect to the answer model by construction and
checks arithmetic rather than reality. The seed is recorded and is not offered as a
defence.

The suite is **690 passing**, up from 654: 36 new tests, most of them negative controls
that doctor one input and assert the guard raises — a disagreeing committed ceiling, a
non-positive excess, an unnested firing set, a rising expected tier, a mislabelled
per-arm reference, a state-reachable answer with no belief branch.

### Gate 6 — the lookahead boundary, and a theorem that survives depth (2026-08-27)

The smallest gate, and the only one that computed nothing. Gate 1 defined the
one-question lookahead and left a note that Gate 6 would have to state the boundary it
implies. Gate 4 then asserted, off a `k = 1` ceiling, that "the horizon was not the
binding constraint" — a claim a reader was entitled to refuse, since a one-step ceiling
does not obviously speak for a two-step policy. This gate supplies the argument, in
`decisions/v2-policy-boundary.md`.

The policy class is written down: `W_0(b) = V_act(b)` and
`W_k(b) = min{ V_act(b), EC(ask | b) + Σ_u P_b(u)·W_{k−1}(b^u) }`. The shipped analysis
is `W_1`, and the only thing that fixes the depth at one is that `V_q`'s continuation is
`V_act(b^u)`, a terminal act. Nothing else in the definition of VoI sets a depth. The
budget counts questions, not turns.

Then the trap, which is worth more than the boundary it protects. Substituting `V(b^u)`
for `V_act(b^u)` looks like buying a second step for free, and is wrong twice. `ask` is
in the menu, so `V(b^u) ≤ EC(ask | b^u)` identically — the tautology already recorded in
the definitions, moved one level down and hidden rather than fixed. And the result is
not `W_2`: `W_2` charges the second question a continuation too, and the difference is
that whole missing term. What `V(b^u)` implements is a policy that believes the second
question's follow-up is free. Because the under-pricing sits entirely on the ask branch,
it tilts the comparison toward the action the analysis exists to test. The file carries
the instruction not to call it "two-step," since that name makes a rigged test sound
like an upgrade.

The result needs two premises, no new code, and holds at every depth. Premise A is
Gate 4's ceiling, leaning on a property of it not used before: `check_global_ceiling`
maximises over *all* beliefs — the whole readiness simplex crossed with `b_h ∈ [0,1]` —
in exact `Fraction` arithmetic, attained at the all-hot vertex at `b_h = 3/13`, where
`V_act = 30/13` against `EC(ask) = 32/13`. Posteriors are beliefs, so the bound binds at
every node of any lookahead tree and not only at its root. Premise B is `W_k ≥ 0`, from
the non-negativity of the cost matrix. The chain is three lines: the ask branch is at
least `EC(ask | b)`, which is at least `V_act(b) + 2/13`, which exceeds `V_act(b)`. So
`W_k = V_act` for every `k`. Asking is never rational on the unconstrained action menu
at any lookahead depth, and the margin cannot narrow with depth, because every term the
chain drops is non-negative.

Premise B is invariant 6 — the check Gate 5 demoted to a tautology. The feature that
made it worthless as evidence for the `k = 1` bound is exactly what makes it usable
here: it follows from the matrix alone, with no reference to the data, the answer model,
the question set or the depth, so it can be asserted at every node of a tree nobody
enumerates. A data-dependent check would have to be verified per node. It is
load-bearing *because* it is trivial. Two gates running, being precise about what a
check actually proves has changed what could be claimed with it.

What this settles about v1: the myopia claim splits, and the halves go different ways.
"A strict one-step rule does not price asking" is true — v1's policy compared
`EC(ask | b) = 2 + 2·b_h` terminally against the other actions, which is not a price for
a question — and it stays a named limitation. "Asking is undervalued, and would earn its
place if priced" is false here: it was priced, and it loses by at least `2/13` per case,
at every depth. Five passages carry the old framing (`main.tex:249`, `:343`, `:687`,
`:947`, `:1050`) and are Gate 7's to rewrite, with `:687` folded into the `:683`
band-claim debt so that line is touched once.

The four scope limits are what keep it honest, and they are stated as flatly as the
result. Premise A fails on the constrained menu, where removing `answer` lifts the
ceiling to `+1.0` and asking can be rational for `b_h < 1/5` on the hot ray; that region
is empty here for two different reasons, unreachable by construction on the calibrated
arm because the isotonic range starts at `6/23`, and merely unoccupied on the other
three. The bound is a statement about the `(2, 4)` ask row, and `λ = 15/16` — 6.25% —
flips it. No row of `costs.COST` prices a state transition, so "hold now, decide later"
is outside all of this, which leaves v1's turn-boundary limitation exactly where it was.
And the claim bounds the value of one more question inside a deeper policy; it is not
the claim that no interaction design could justify asking.

No code, no new tests, and no `W_2`. Both premises are already under test — the
ceiling in the `voi_ceiling` suite, `V_q ≥ 0` as invariant 6 in
`tests/test_entropy_baseline.py`. A `W_2` computation would have exhibited depth 2
while the argument covers every depth, so building it would have added scope and
subtracted nothing. The suite is unchanged at **690 passing** and
`make_figures.py --check` exits 0.

Recorded as Y1–Y5 in `decisions/v2-design-decisions.md`, with one-line pointers into
`decisions/v2-definitions.md` at the boundary note and at the horizon sentence. This is
the one gate with no pre-registration, because nothing is computed and so there is no
result to be tempted by after the fact.

### Float reproduction — two undeclared tie-breaks and a Python floor (2026-08-27)

Five tests failed on Python 3.11 and passed on 3.14. The cause is not the operating
system: CPython 3.12 made `sum()` over floats use Neumaier compensated summation, so
every float that reaches an artifact through a `sum()` differs in its last bit or two
across the boundary. Verified by running the whole suite on 3.11, 3.12, 3.13 and 3.14 —
green from 3.12 up, five failures below. Two earlier hypotheses, macOS versus Linux
`libm` for `log2` and hash-order nondeterminism, were tested and disproved rather than
left in the record as maybes.

The float part is noise: 818 of the 826 differing leaves in
`results/entropy-baseline.json` are floats, the largest disagreement is 1.110e-15, and
no published number moves. The other 8 leaves are discrete, survive any tolerance, and
are the actual find. Both trace to an `argmax` whose ties were resolved by the last bit
of a float sum.

The first is the oracle. `argmax_q VoI(q | b)` over the three real questions is a
`max()` over a list, and on some cases those VoIs are exactly equal, so which question
the oracle picked — and the "agrees with argmax-IG on 29 of 50" count computed from it —
was decided by summation order. This is the S4 failure mode a fourth time: a numeric
rule selecting on a quantity whose tie structure the rule never consulted. It now rounds
at 12 decimals, resolves by declaration order in `QUESTIONS`, and records the tied set
per case, since `by_question` is stripped from the JSON and nothing else would keep it.

That declaration produced the one genuinely new number here. The oracle's pick needed
the tie-break on **13 of 50 test cases** on the published arm and 12 of 50 on raw. So
the agreement count was never a clean comparison of two selection rules: on a quarter
of the cases, agreement is an artifact of whichever tie-break is in force. Both figures
are now printed together, in the JSON and in `results/entropy-baseline.md`, and neither
is quotable alone.

The second is the grid crosscheck, which reported a single point as *the* argmax of the
ceiling over the readiness simplex. 1185 of its 115351 points attain the maximum to 12
decimals. The witness was never unique, so the claim was slightly false before it became
unstable, and the truer statement is shorter: report the plateau. It now returns the
plateau size, the points searched, `grid_argmax_is_unique: false`, and a declared
lowest-`(hot, warm, b_h)` tie-break. The reported point moves across the plateau;
`grid_max` moves 4.4e-16 to `-0.16666666666666696` and still rounds to the `−0.1667`
that `decisions/v2-design-decisions.md:1090` and `decisions/v2-policy-boundary.md:93`
cite. No file cites the point itself.

Two smaller changes fall out of the same reading. The invariant tables printed residuals
like `-2.22e-16` as three significant figures, which reads as a measurement when it is
the order the terms were added in; they now print `0` for exact zero and `~0` for
below-tolerance, with the legend under the table. Exact `0` keeps its own symbol because
X2's "recomputed and committed ceilings agree to the last bit" is precisely the
difference between the two. A magnitude form like `< 1e-12` was rejected:
`invariant_2_min_slack` is signed and a bound drops the sign.

And the reproduction guarantee is pinned. A claim that byte reproduction holds, which
silently depends on the interpreter, is the same class of gap as v1's unrecorded model
id — the artifact was produced under conditions the artifact does not record. Two
committed claims genuinely need 3.12 or later: `ceiling_agreement.max_ceiling_delta` is
`0.0` exactly on all four arms, and the md distinguishes an exactly-zero residual from
a below-tolerance one. So the floor is 3.12, declared once as `MIN_PYTHON` in
`tests/reproduction.py` with its reason beside it, and asserted against the CI matrix,
the README and the running interpreter, plus a fourth test requiring the matrix to run
the floor itself. The matrix moves from `["3.10", "3.12"]` to
`["3.12", "3.13", "3.14"]`; the 3.10 leg it replaces could not have passed.

`tests/reproduction.py` is the comparator the three JSON artifacts now use. It forgives
a float-versus-float leaf within 1e-9 and nothing else, and it runs two independent
comparisons — a walk over the parsed structure and a line-by-line text comparison —
because each catches what the other cannot: the walk sees `100` becoming `100.0` and a
reordered key, the text comparison sees a changed indent and a missing trailing newline.
Every `Fraction` is rendered as a string, so the exactness claims still compare
character for character, as do every count, id, bool, null, list length and the key
order. `results/entropy-baseline.md` stays byte for byte.

On 3.11 after the fix there are three failures instead of five, and they are the two
real version-dependent exactness claims plus the floor test that names the reason —
which is the intended behaviour, not a residue. The suite is **712 passing** on 3.12,
3.13 and 3.14, up from 690 by the 22 tests in `tests/test_reproduction.py`. One earlier
report to correct: I said the agreement count would move 29 → 30. It does not. Under the
declared tie-break both interpreters produce 29 on published and 26 on raw, matching the
committed artifact, so no paper line or decision file is touched by it.

Recorded as AB1–AB7 in `decisions/v2-design-decisions.md`.

### Gate 7 — the theorem subsection, written first and alone (2026-08-27)

`main.tex:677` was v1's `\subsection{Two actions that are never used}`: 14 lines
carrying two false claims and, between them, the impossibility theorem asserted a year
before it was proved. It is now 166 lines, and it was written before any other v2 prose
because the pre-registration puts five of the eight results, three of the nine debts
and seven of the sentence dispositions inside it. Writing the three beats separately is
how the theorem ends up stated three times at three strengths.

What was kept: the census — `answer` 30, `hold` 27, `escalate-notify` 43 — now with the
note that the value-of-information analysis reproduces it independently; the `ask`
arithmetic, 2 against 0 and 4 against 0, which is true; and `:681`, "a property of the
matrix rather than of the cases," which is the theorem in v1's own words and is upgraded
in place rather than replaced.

What was replaced. The band claim is false twice and the rewrite says both: there is no
narrow middle band on the unconstrained menu, because the ceiling is negative at every
belief in the simplex with a maximum of `−2/13`; and quantization is not the cause,
because the `raw` arm carries 100 distinct `b_h` where `published` carries 8 and leaves
the region exactly as empty — no case with a positive ceiling on any of the four arms,
400 case-arm pairs. Naming one error alone leaves a reader believing a finer belief
would find the band. The "untested" claim is replaced by "tested, and each fails for a
different proven reason," with the census unchanged. The myopia sentence is absorbed
here rather than retracted a second time.

Four beats. The theorem, with a proof sketch that carries the monotonicity conditions
`−ν < c_T − c_F < α` the implementation asserts rather than assumes. Attainment, written
as what makes the theorem sharp rather than as a second finding: on 16 of 400
case-question pairs the continuation term is exactly zero — a free perfect oracle — and
asking still loses the full ceiling, so the negativity cannot be read as slack in the
bound. Depth-independence: `W_k = V_act` at every `k`, from the simplex-wide ceiling
plus `W_k ≥ 0`, with `2/13` a floor on the gap and not an estimate of it. And the
portable form, `c_F/ν + c_T/α < 1`, which fails here at `16/15` and fails by 6.25% —
scaling the `ask` row by `15/16` to `(1.875, 3.75)` puts the ceiling at zero. That last
beat is the one a reader can carry to another cost matrix.

The binding wording holds throughout: the claim is asking is never rational **on the
unconstrained action menu**. The constrained paragraph gives the positive region its
own sentences — `+1` at the all-hot vertex with `b_h = 0`, the region `b_h < 1/5` on
that ray bounded by `escalate_notify`, 8 cases carrying the constraint and every one at
`b_h ≥ 0.40` — and keeps the two kinds of emptiness apart. Structural on `calibrated`,
where the fitted map cannot emit a belief low enough to qualify. Contingent on the other
three, where 31 raw beliefs do fall below `1/5` and none of them carries
`no_direct_answer`. That is a fact about this dataset, not about the matrix.

`escalate-pause` is the other half. Dominance in the matrix is stronger than absence
from the census: the gap over `escalate-notify` is 3, 2, 2, 2, 1, 1 across the six
states, strictly positive in all of them, and expected cost is a belief-weighted
average over columns, so no belief can invert it. That also prices abstention: a
notify-to-pause rewrite raises realised cost by 1 to 3 on every case it touches and
cannot lower the missed-escalation count, since both escalate actions count as
escalating.

Every number in the subsection resolves against a committed key path; all 27 were
re-checked after the prose was written, with no mismatch. Four of the paths were not in
the pre-registration's §4.1 and were added to it rather than cut from the prose, since
three of them carry the half of the band replacement a reader is most likely to doubt.

Two things stayed out deliberately. `6/23` and the fact that the calibrated arm makes
"two unused actions" three: both are consequences of the reachable-score floor, which
belongs with the calibration result it cannot be separated from. The structural half of
the emptiness argument therefore names that floor without its value and points forward.

One edit landed outside the subsection. `amsthm` is loaded but declares no
`\newtheorem`, and `ijcai26.sty` defines no theorem environment, so `\begin{theorem}`
would not have compiled; one preamble line was added. No TeX distribution exists here,
so that line is unfalsified rather than verified — Kaps holds the compile, on this
subsection alone and ahead of the final build, because a broken theorem environment
blocks every section after it. The bold run-in fallback is written down in case it
collides.

Recorded as AC1–AC4 in `decisions/v2-design-decisions.md`.

### Gate 7 — the Calibration subsection, R7 and R8 as one object (2026-08-27)

The second section, and the last one where two results have to be read together. v1's
reliability diagnosis of the `needs_human` marginal stays whole: the figure, the 16
misses that all came from that one marginal, and the two qualifications about the bin
that actually contains `3/13`. What was missing is that the diagnosis was a testable
claim about the elicitation, and Gate 2 tested it, so the fit now follows the diagnosis
in the same subsection.

R7 and R8 land in one paragraph, not one subsection. The pre-registration required the
same subsection; a subsection can still be quoted a paragraph at a time, so the
paragraph that reports cross-entropy 0.8546 → 0.8136 bits, ECE 0.1526 → 0.0696 and
Brier 0.2063 → 0.1962 is the same paragraph that reports the action census going from
`{answer 12, notify 21, hold 17}` to `{notify 41, hold 9}`. The mechanism follows in
its own paragraph: PAVA's lowest block pools 23 dev cases with 6 positives, so the map
cannot emit below `6/23 = 0.260870`, the ordering `1/5 < 3/13 < 6/23` spans less than
0.061 end to end, and 24 of the 50 test cases sit below `3/13` on the raw score where 0
do after the map. The calibrated arm is a two-action policy by construction.

D4 is discharged three times, deliberately. The table header names the population; the
caption states that the test half carries only 8 of the 100-case run's 16 misses, so a
change of one or two on it is not evidence; and the closing paragraph says outright
that the in-sample fit on 100 cases and the restriction from 100 cases to 50 produce
the same pair "16 to 8" by unrelated routes. The mean is named as the quantity that
survives the change of population and the count as the one that does not.

The cost and miss numbers are in a table captioned as secondary, with the
pre-registered caveat in the caption rather than in a footnote. The calibration
contrast is 7 misses of 50 down to 2 of 50 at a mean rising 1.40 → 1.50, and the
calibrated arm escalates 41 of 50 against always-notify's 50 — breakable, and not free.

Nine key paths were not in §4.3 and were added to it. Two of them are prices rather
than results: the 0.02-bit rule that allowed a non-order-preserving map to ship, and
`order_preserved_on_test: false`. Reporting the win from the selection rule while
leaving its cost unregistered is the shape of omission the trace exists to catch.

The 11-of-100 belief drift stays out of Results. Its cause is undetermined, so the
only honest sentence about it is that the cause is undetermined, which is a limitation
and not a result. Results carries the aggregate consequence instead: the written-belief
row reaches the same total, mean and miss count on this half as the cached beliefs do,
aggregate agreement only and not a case-for-case replay. Keeping it out of Results is
not the same as dropping it — Limitations owes it one line that gives the count and
says the cause is undetermined, and that line is an open debt of this gate.

The escalation precision and recall of the two re-elicited arms go into the same
paragraph as the scores and the census: precision 0.667 to 0.463 against recall 0.667
to 0.905. "Escalates 41 of 50" says how often the calibrated policy escalates; this
pair says what the change bought and what it cost, which is the paragraph's tension
stated as numbers instead of characterised. It sits immediately before "These are not
two findings", so the pair cannot be lifted away from the sentence binding it to the
score improvement. A tenth §4.3 row registers all four values.

Three edits landed outside the subsection: `\label{sec:split}`, so the closing
paragraph can point at the matched-by-construction argument instead of restating it;
the theorem subsection's forward reference, wired to `Section~\ref{sec:calibration}`
as AC3 deferred; and U7's prose twin at `:499`, which carries the same false bracket
as the caption. U7 is one debt with two false lines and both are now replaced with the
value gap `(0.2, 0.3)` open at both ends against the threshold interval `(0.2, 0.3]`,
with the 17 cases at exactly `0.3` given as the reason. `:1123` was already correct and
is untouched.

Recorded as AD1–AD7 in `decisions/v2-design-decisions.md`.

### Gate 7 — Method: τ as deciles, and the split that fits and scores (2026-08-27)

The τ definition goes in §Method's metrics subsection rather than in the section that
reports what thresholding costs. A threshold on `H(b)` set in absolute bits is the S4
shape — a numeric rule governing a quantity whose scale the rule never consulted — and
the fix only reads as a fix where the quantity is defined. Met for the first time in
the section that reports its cost, a designed grid is indistinguishable from a
convenient one.

The paper gives the reason without naming the failure mode. `H(b)` runs from 0 to
2.456 bits with a median of 2.017 on the run's own beliefs, so an evenly spaced grid
over the theoretical `[0, log2 6]` range would put most of its points where almost no
case sits and would report the spacing of the grid rather than the behaviour of the
rule. Deciles make the step commensurate with the observed spread by construction.

All three definitional consequences are stated in Method, not left for the section
that uses them: the eleven quantiles collapse to eight distinct thresholds on the
run's own beliefs and eleven on the two re-elicited sets, and equal thresholds give
the same asked set and the same cost by construction; the same quantile is a
different number of bits on each set of beliefs, because `H(b)` moves when the belief
moves; and the grid is taken over all 100 cases of an arm while the sweep scores the
50 test cases, so the top decile asks about nothing when an arm's highest-entropy
case is a development case. Each is a place where a mechanical property of the grid
could be presented later as a finding about the rule.

The units constraint is now in the paper: no quantity in bits is compared to a
quantity in cost points, the entropy selects which cases are asked about and the cost
matrix scores what happens. It has held in the code since it was set; this is the
first sentence that makes it checkable by a reader rather than only by the tests.

The firing fallback is defined as the cheapest action other than asking, with the
coincidence — that it is the policy's own action case for case on these beliefs, and
reproduces the committed fallback total — as a following clause. Defining it as "what
the policy would have done" would make the baseline depend on the theorem that asking
never wins, and the baseline has to be readable without it.

τ's consumer is named in words, not with a `\ref`. R5's subsection does not exist, so
a `\ref` would dangle and fail the resolve check that runs at every paper commit; the
wiring is owed to that pass, the same debt AC3 carried for `sec:calibration`.
`\subsection{Policies and baselines}` is untouched: the entropy baseline is not one of
Table 2's five policies and listing it there would misstate the table.

§Method's split subsection gains the fit-and-score assignment — the map is fitted on
the 50 development cases and judged on the 50 test cases, so calibrated beliefs on the
development half are in-sample and are not reported as a result — and turns the
existing matched-by-construction caveat both ways. It gets no `\label`; nothing points
at it yet.

Six definitional numbers are registered in §4.2. Definitions trace on the same terms
as results, and an unregistered definition is where a later gate would be free to
re-choose the grid and call the old numbers comparable. `[0, log2 6]` stays
unregistered as arithmetic on the six-state belief.

Recorded as AE1–AE9 in `decisions/v2-design-decisions.md`.

### Gate 7 — the offline compile check, and the figure the README got wrong (2026-08-28)

Three sections are now stacked on a build nobody has confirmed, and the compile is not
mine to run: there is no TeX in this environment. `pdflatex`, `xelatex`, `lualatex`,
`latexmk` and `latex` are all absent; `tectonic` is installed and panics creating its
own cache directory, and would need network for its bundle either way. So "it builds"
stays Kaps's falsifier. What could be established without TeX was established instead.

The `\newtheorem` collision is statically excluded rather than merely unlikely.
`ijcai26.sty` is 335 lines and contains zero occurrences of "theorem"; neither
`article` nor `amsmath` nor `amsthm` defines a `theorem` environment. The tracked
`paper/main.pdf` is a v1 build product, and the preamble at the commit that produced it
already loaded `amssymb` and `amsthm` — so the package list is known to compile and the
only delta since is one `\newtheorem` line that cannot collide with anything.

The scratch preflight is now `tests/paper_preflight.py` with 60 tests over it, and the
suite is **772 passing** on 3.14, up from 712. Nine checks: environment balance by
stack rather than by count, preamble hygiene against the style file, duplicate labels
and dangling references, `\cite` keys against `references.bib`, `\includegraphics`
targets through `\graphicspath`, brace and math-mode balance, `tabular` column counts,
an unknown-macro scan, and every float carrying a `\label`. It PASSes on the 1413-line
working `main.tex`: 19 labels, 17 distinct references, notes only for `sec:intro` and
`sec:conclusion`, which nothing references on purpose.

Its own first run is why the tests are shaped the way they are. Eleven failures, every
one false: four were inline math legally spanning two lines, six came from a
column-spec regex truncating `lr p{3.2cm}` at the inner brace, one from not counting a
`\multicolumn{3}` span. Parity is now checked per blank-line-separated block, the spec
is read by brace matching, and spans are added back — and each of those three fixes has
a positive-control test that must stay quiet, because a fix with no test against it
comes back at the next refactor. Findings are split into failures and notes, and notes
never fail a run: the paper has two deliberately unreferenced labels, and a check that
fails on intent is a check that gets switched off.

What the module cannot see is written into its docstring: an overfull box, a font
substitution, a float landing three pages from its reference, a bibliography style
error. A pass means the source is structurally sound, not that the PDF is right.

It has already earned its place twice. Its one real failure was `\includegraphics`
naming `figures/reliability-needs-human`, which is not in the repository — and README
step 5 said that was deliberate, while `.gitignore` says the opposite in as many words:
it un-ignores `when-to-escalate/paper/figures/*.pdf` and records "committing the
rendered figure is the fix", because the figure needs matplotlib, which nothing else
here depends on, so a clone that had to render it first could not compile at all. The
README was the file that was wrong. Step 5 now states that the rendered PDF is committed
so a fresh clone compiles without running the step.

The second time was its own bug. After Kaps rendered the figure locally, the working
tree held `reliability-needs-human.png` and no `.pdf`, and the check said the figure was
present — because it tried `.pdf` and `.png` for every target, and the paper's target
names `.pdf` explicitly. LaTeX loads what that names and nothing else. Extensions are
now substituted only for a target that names none, and the case has a test. With that
fixed the check correctly failed, which is how the missing render was found rather than
committed around.

Two questions were being conflated there, and are now separate. Whether the working
tree can compile is what `check_graphics` asks. Whether a *fresh clone* can compile —
V1's actual criterion — needs `git ls-files`, and the preflight module has to run on a
fragment with no repository, so it does not know about git. That question is asked in
the test module instead, and it is red as of this entry: the render is untracked, and it
goes green when the figure is staged.

One thing that render cannot claim is byte reproducibility, and that is now measured
rather than argued. `make_figures.py:586` is
`fig.savefig(out, dpi=300, bbox_inches="tight")` with no metadata argument, so
matplotlib writes its own version into `/Creator` and `/Producer` and the render time
into `/CreationDate`. The render of 2026-08-20 is 39907 bytes and says
`Matplotlib v3.10.8`; Kaps's render of 2026-08-28 00:29 is 27151 bytes and says
`Matplotlib v3.11.1`. Same data, same script, two files that share no useful prefix.
Step 1 now excludes this one file from the byte-for-byte comparison and step 5 says why,
and the values are checked instead by `make_figures.py --check` and
`tests/test_make_figures.py` against `results/run.json` — both re-run against the new
render, both pass, every plotted number still derived from `results/run.json`. Pinning
`/CreationDate` is declined rather than left open: the criterion V1 carries is that a
clean clone builds, committing the binary satisfies it, and byte-stability on a
renderer's output is not worth engineering for. The matplotlib-version dependence is a
noted limitation.

The compile came back green — equation numbering, the theorem environment, the refs, the
figure — and the figure was still wrong on the page. A stray `35` sat at
`(0.200, 0.171)`, inside the largest marker and across the curve. Every check in this
repository was green while it did, which is the part worth recording: `--check` and
`tests/test_make_figures.py` verify each plotted *number* against `results/run.json`,
neither imports matplotlib, and nothing verifies *placement*. The defect was found the
only way it could be, by a human looking at a compiled PDF.

The cause is one line of `render()`. `ax.annotate` used a fixed `xytext=(0, -3.2)`
points with `va="center"`, while marker area is `s = 8 + 3.2n`, so the radius runs about
2.6pt at `n = 4` to about 6.2pt at `n = 35`. A 3.2pt drop clears the small marker and
lands well inside the large one — seven bins looked acceptable and the eighth looked
broken. It is the S4 shape again: a numeric rule governing a quantity whose scale the
rule never consulted, and here the scale is a function of the very number being printed,
so the bin that most needs a legible count is the one guaranteed to get the worst
placement.

The labels are removed rather than nudged. Two things pass through every marker — the
Wilson bar, vertical and straddling the point, `[0.081, 0.327]` around an observed 0.171
for this bin, so up and down are both taken; and the segment joining the bins. Sideways
fails here too: `r + pad` is roughly 0.04 in data units on this axis, which puts the
digits on the dashed `3/13 = 0.2308` line. The count is already carried by marker area,
by the legend entry that names it, and by the caption, which gives the 4-to-35 range and
`n = 35` for this bin outright. A comment in place of the loop records why, so a later
edit does not re-add it with a different offset. `--check` still passes and
`tests/test_make_figures.py` is unchanged at 43 passing, because neither reads the
render path. No test is added for the removal: the property is about pixels, matplotlib
is absent here, and asserting that one `annotate` call is gone would pin the fix instead
of the property. The render is Kaps's to regenerate and recompile before anything is
committed.

`paper/figures/*.png` is now ignored. One `savefig` loop writes both extensions,
`main.tex` includes the PDF, nothing reads the PNG, and it kept showing as untracked
work. The ignore names the PNG only; the `!…/*.pdf` un-ignore above it is what the
clean-clone compile depends on and is untouched.

Recorded as AF1–AF14 in `decisions/v2-design-decisions.md`.

### Gate 7 — Limitations: v1's myopia claim withdrawn (2026-08-28)

The section v1 got wrong. `:947` claimed the policy is myopic and therefore undervalues
the ask action, that the honest handling would be to compute its one-step value of
information, and that `ask`'s absence from the census was the consequence. The middle
clause is now false — Gate 5 and Gate 6 computed it — and the other two are the wrong
direction. Asking is not underpriced by the one-step rule; it is priced, and it loses at
every belief and every depth. So the paragraph is a withdrawal, not a qualification,
and it says so.

What survives is smaller and it is the honest part. The policy is myopic and carries no
machinery that prices a question's downstream value: true, and still a limitation. The
collapse that makes this harmless is a property of this cost matrix — `c_F/ν + c_T/α <
1` is the condition, this matrix gives `16/15`, the break-even multiplier on the ask row
is `15/16` — and the policy never checks it. Being myopic is safe here for a reason the
code does not verify, and on a matrix that satisfied the condition the myopia would cost
exactly what v1 said it costs. Both misreadings are named in the text: `2/13` is a floor
on the gap and not an estimate of it, and the theorem bounds one more question inside a
deeper policy on this matrix and this menu, not interaction design in general.

The retraction is written once. `:250` and `:347` state the result and point at
`sec:unused`; neither carries retraction language, because five wordings of one
withdrawal is how one of them overreaches. The Conclusion's passage is the fifth and is
left for its own pass, where the map assigns it a replacement by the answer rather than
a retraction.

Three further entries. OQ3: the value-of-information machinery simulates replies from
the design's own model of the lead, so running it and finding it consistent is a
self-consistency check of the implementation and nothing more. That is written as a
bounded result rather than a hedge, and what bounds it is the theorem's independence
from the answer model — it needs only non-negativity of the cost matrix, so the
unvalidated model touches the per-case ceilings and the count of resolving questions,
not the result that `ask` is never selected. Abstention, new at this pass: priced out
under this matrix by column-wise dominance of `escalate-pause` by `escalate-notify` in
all six columns, by between 1 and 3, with the scope stated as the matrix rather than the
design space, since the costs are expert-set and §4 already shows at least one magnitude
is load-bearing. And L1's two carried caveats now have their own paragraph instead of
living only in §6: the cost result is against the uniform baseline only,
always-notify is a near-tie at 1.72 against 1.74 and the win is human load, and the
dev/test totals agree
because the split was matched by construction.

AD3's debt is one line: 89 of 100 beliefs reproduce at temperature 0, 11 differ, none
unparseable, cause not determinable from the record. The count comes from
`results/rebaseline.md` and `reproduction_check.unparseable` in
`results/logprob-elicitation.json`. It is not attributed to the calibration map, and
L10's resolved-snapshot half stays out — v1 stored the alias, so "no dated snapshot is
recorded" is the true statement about the beliefs this paper reports.

AF8's debt is a paragraph: Python 3.12 named as the floor with the compensated-summation
reason, the two float-bearing artifacts compared to 1e-9 rather than exactly, the figure
excluded from the byte comparison because a PDF records its renderer's version and its
render time, and every plotted value checked against `results/run.json` instead. A
reproducibility claim in the paper without the interpreter floor is a named falsifier.

Nothing was computed. Every number in the section resolves to `main.tex` §4 or §6, to
`results/rebaseline.md`, to `results/logprob-elicitation.json`, or to the README's
reproduction floor. Checks: preflight PASS on `main.tex` (19 labels, 17 distinct refs,
5/5 citations, 1 graphic, 4 tabulars), 772 tests passing, no new line over 84
characters, and the six that are over are the same six as before this edit.

Recorded as AG1–AG11 in `decisions/v2-design-decisions.md`.

One more defect, found by reading the abstract against the section just written. The
abstract said recalibration "halves the misses, from 16 to 8" and moved straight on to
the residual 8. §7.3 states the same change two-sidedly — escalations 43 to 60,
precision 0.605 to 0.567, 9 of the 16 fixed and 1 new miss created — so the body was
never one-sided; the summary was. That is the failure this whole gate is meant to catch,
and it survived four sections because nobody reads the abstract again after writing it.
Fixed at `paper/main.tex:116`, and registered as falsifier Z19 so it cannot drift back.

The instruction that found it asked for "cost up". Cost falls: 1.650 to 1.250, in
`results/robustness.json` and in §7.3. What rises is load. The abstract now says mean
cost falls and names the load — escalations 43 of 100 to 60, precision 0.605 to 0.567 —
with the composition, and every count carries its denominator. The pair 1.650/1.250 is
left to §7.3 rather than printed eight lines under the abstract's 1.72, which is the
legacy tie-break total against a different baseline.

Recorded as AH1–AH4 in `decisions/v2-design-decisions.md`.

The trade-off wording lasted one exchange. The next instruction removed the miss count
from the abstract entirely: state the calibration result as a calibration-quality
improvement scoped by the reachable-score floor, cite the held-out measures, carry no
miss count. `paper/main.tex:116-129` now does that. The in-sample sentence keeps its
scope claim — recalibrating on the same 100 cases is an in-sample ceiling and the body
reports it as one — and loses its number. Next to it are §6.6's held-out figures on the
50 test cases, ECE 0.1526 to 0.0696, cross-entropy 0.8546 to 0.8136 bits, Brier 0.2063
to 0.1962, then the `6/23` reachable-score floor sitting above the `3/13` a belief must
fall below for answering to be cheapest, then what that costs: `answer` gone from the
census, precision 0.667 to 0.463, recall 0.667 to 0.905. R7 and R8 in one paragraph, as
Z10 requires everywhere else. Zero miss counts remain in `:85-133`, checked numeral by
numeral.

Two premises came with that instruction and one of them is wrong. The abstract's
"16 to 8" was not a train/test split artifact: `recalibration.before.misses` is 16 and
`recalibration.after.misses` is 8 in `results/robustness.json`, both on the 100 cases,
which is exactly what the abstract said. What is true is that restricting the same
policy and beliefs from those 100 cases to the 50 test cases also prints 16 to 8
(`paper/main.tex:1082`), so two unrelated operations render the same string within sight
of each other — confusable, which is D4's shape and Z8's rule, not false. And "the floor
sits above both thresholds so recalibration cannot improve the decision" holds for the
held-out isotonic map, whose lowest pooled block puts `6/23` above both `3/13` and
`1/5`, but not for the in-sample bin map, whose `recalibration.mapping` sends the
`0.2-0.3` bin to `0.1714` — below the threshold — and which changes 8 decisions and 0.4
of mean cost. In-sample recalibration does improve the decision. What it does not do is
generalise.

The reframing is still the right abstract, on the ground that survives: the abstract was
carrying the weaker of the two calibration results. §7.3 fits and scores on the same 100
cases; §6.6 fits on 50 and scores on the other 50. Held out is the stronger claim, and
its ceiling is more interesting than the in-sample one, because the gain stops at the
map's own range rather than at the data.

Z19 is marked changed and superseded by Z20, which is the rule as now stated. Z11 wanted
the in-sample sentence kept and extended; it is kept and shortened, and Z20 records that
resolution. Recorded as AH5–AH12 in `decisions/v2-design-decisions.md`; AH1–AH4 stay as
written because they record what was tried.

### Gate 7 — Conclusion: the ask question closed, the two floors named (2026-08-28)

Three sites, all in `paper/main.tex`, all assigned by the map.

The ask entry at `:1474-1502` is the paper's last word on asking and the map files it as
REPLACED by the answer rather than by a retraction, because v1 asked the exact question
v2 settles — whether the action is genuinely useful or merely unpriced. The answer is
neither: it was priced, and it lost. The replacement leads with the bound, at most
`-2/13` at every belief in the simplex on the unconstrained menu, attained at the
all-hot vertex, then closes the horizon question outright: posteriors are beliefs, the
bound holds at every node of a lookahead tree, `W_k = V_act` for every `k >= 1`. Two
short sentences carry it — asking does not fail here because the policy looks only one
step ahead, it fails at every depth. What v1 had was the opposite shape, a myopic policy
that "cannot price the value of asking, because that value is a better belief next
turn," which reads as an admission. The one-step rule is still named as a rule that does
not price downstream value; the inference that this is why *ask* is absent is gone. No
retraction language anywhere in the Conclusion — that is written once, in Limitations,
and Y5b's falsifier is exactly the claim being withdrawn in five wordings.

Second paragraph carries R2 as the portable claim, which is where the map puts it:
`c_F/ν + c_T/α < 1` in words and symbols, the `16/15` that fails it, the 6.25% margin,
the `15/16` scaling that puts the ceiling at zero, and the designer with a cheaper
question who is on the other side of the line. The constrained carve-out is referenced
and not re-derived — a region of hot beliefs that no case in this set occupies — since a
second thinner version of a committed passage is how two versions come to disagree.

The calibration entry at `:1454-1472` discharges KEPT-AND-PROVEN. v1 claimed the
residual-miss floor is set by the granularity of the elicitation and not by the
calibration method, and named a finer belief plus a held-out fit as the next step.
Gate 2 took that step and the claim held, so the entry reports it as tested rather
than
asserted and the "next step is" becomes a reference to §6.6. On the 50 test cases the
misses go 7 of 50 to 2 of 50 — breakable, and it broke when the elicitation got finer,
which is what the claim predicted. Not free: mean 1.40 to 1.50 and 41 of the 50
escalated, with R8's mechanism in the same sentence per Z10, so the granularity
claim survives and the bound moves out of the elicitation and into the calibration
map.

One number in the pre-registration is wrong and stays as written. D1 at
`decisions/v2-gate7-preregistration.md:394` says Gate 2 moved misses "8 → 2 on the same
50 test cases". `tab:calibration` gives the re-elicited uncalibrated arm 7 of 50 and the
calibrated arm 2 of 50; the 8 is the written-belief arm on that half, a third row. The
pre-reg pairs a before from one arm with an after from another. The Conclusion uses 7 to
2 and no historical row is edited for wording.

The bare-"floor" stragglers are four sites, not one, and the instruction misnamed the
first. `:1220` closes §7.3, the in-sample bin map on 100 cases, and its antecedent is
the 8 misses that recalibrating this marginal cannot remove — a count, which is Z9's
residual-miss floor. `6/23` is §6.6's isotonic map and V3 keeps it in the Calibration
subsection. Calling `:1220` the reachable-score floor would have put §6.6's probability
onto §7.3's count, which is the two-maps collapse for the third time this pass. Fixed to
residual-miss floor at `:1220`, `:1458` and `:1466`, and to reachable-score floor at
`:870`.
Left alone: `2/13` is a floor on the gap at `:837` and `:1311`, a third object and
qualified there on purpose per AG3, and the declared Python floor at `:1385`.

`:1451` stops calling all three questions open, since one closes here and one is mostly
answered. Raised in the plan as an addition beyond the map rather than folded in
quietly.

Untouched: the turn-boundary entry, which `v2-policy-boundary.md` part 4 depends on; the
summary paragraph; the AI-use statement. AG11's deferral is discharged.

Checks: preflight PASS on `main.tex` (19 labels, 17 distinct refs, 5/5 citations, 1
graphic, 4 tabulars), 772 tests passing, `main.tex` at 1548 lines with over-84 lines
only at 2, 108, 209, 436, 1356 and 1422 — the same six as before this edit — no banned
token,
`cohort` still 4, and no number that is not already in §4, §6.6, §7.3 or
`results/`. Nothing was computed. Recorded as AJ1–AJ11 in
`decisions/v2-design-decisions.md`.

The closing sentence the instruction asked to replace is not in the paper. `main.tex`
has no future-work section and no promise of richer belief representations to make
asking worthwhile: "richer", "belief representation", "worthwhile", "future work" and
"further work" all return zero hits, in v1's text as much as v2's. The Conclusion's
three questions are the nearest thing, the ask one is now the closed one, and the
transferable open question — which cost matrices satisfy `c_F/ν + c_T/α < 1` — is
already stated in its designer-facing form at the end of the ask entry. So there is
nothing to replace. The rule is worth having anyway and is registered as Z21 with a
§7 falsifier: no forward-looking sentence may name a richer belief, a longer horizon
or a better question model as a route to making *ask* worthwhile on this matrix,
because the theorem disproves that direction at every belief and every depth. It is
satisfied vacuously today, which is the honest status to record rather than claiming
a fix. Recorded as AJ12.
