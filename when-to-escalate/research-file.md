# Research File

## Problem statement

The agent observes an inbound message from a sales lead. It must
select one action from {`answer`, `ask`, `hold`, `escalate_notify`,
`escalate_pause`} because the lead's true intent and buying-readiness are not
known. `ask` is a qualifying question rather than an answer; `escalate_notify`
tells a human while the conversation continues; `escalate_pause` stops the agent
and hands over. The two escalations are separate actions because they carry
different costs (build decision 25, superseding the original four-action set).

---

## Project objective

Design and test a decision policy for a conversational sales agent that must choose, on each inbound message, whether to answer, ask a qualifying question, hold, notify a human while the conversation continues, or pause and hand over to a human, when the lead's true intent and buying-readiness cannot be observed. The agent maintains an explicit belief over that hidden state and selects the action with the lowest expected cost, where the costs reflect real business damage rather than what is easy to detect. The goal is to compare this cost-aware policy against a baseline and show where reasoning about the cost of each mistake changes the decision.

## Technical terms

| Term | My definition |
| --- | --- |
| Bayes decision rule (minimum-expected-cost action) | Choose the action with the lowest expected cost under the current belief over hidden states. |
| Loss / cost matrix | Table of costs for each (action, true-state) pair; asymmetric when some errors cost far more than others. |
| Cost-sensitive classification | Optimizing expected cost rather than raw error rate, because misclassifications aren't equally expensive. |
| Reject option / abstention | Letting the agent decline to act (defer/hold) instead of forcing a decision when expected cost warrants. |
| Selective prediction / selective classification | Acting only on a subset of cases (coverage) and abstaining on the rest; trades coverage against risk. |
| Risk-coverage curve / AURC | Error (risk) plotted against fraction of cases acted on (coverage); AURC is the area under it, lower is better. |
| Learning to defer (L2D) | Training the agent to choose between deciding itself or deferring to a human, modeling the human's own error and cost. |
| Learning to complement | Training the agent to be strong specifically where the human is weak, as a team, not standalone. |
| Human-AI deferral / triage / routing | Sending each case to whichever decision-maker (agent or human) has the lower expected cost. |
| POMDP | Sequential decision problem where the true state is hidden; the agent acts on noisy observations while maintaining a belief. |
| Belief state | Probability distribution over hidden states given everything observed so far; a sufficient statistic for choosing an action. |
| Belief update / Bayesian filtering | Revising the belief with new evidence via Bayes' rule (prior × likelihood → posterior). |
| Belief-state MDP | Recasting a POMDP as an MDP over beliefs; optimal in principle but generally intractable to solve exactly. |
| Myopic / one-step-lookahead policy | Pick the action minimizing *immediate* expected cost under the current belief, without planning over future belief changes. My chosen approach. |
| Value of information (VOI) / myopic VOI | Expected reduction in decision cost from gathering evidence before acting; myopic = evaluated only one step ahead. This is how "ask a qualifying question" earns its place. |
| EVSI (expected value of sample information) | VOI for one specific piece of evidence, e.g. the answer to a single qualifying question. |
| Optimal stopping | Deciding when to stop waiting/gathering versus act; the conceptual home of my "hold" action. |
| Probability calibration | Whether predicted probabilities match reality: a stated 70% should be right about 70% of the time. |
| Reliability diagram | Predicted probability vs observed frequency; the diagonal is perfect calibration. |
| ECE / MCE | Expected / Maximum Calibration Error: average / worst gap between confidence and accuracy across probability bins. |
| Proper scoring rule (Brier, log loss) | Scoring rule minimized only by reporting true probabilities; rewards calibration and sharpness together. |
| Sharpness vs calibration | Sharpness = how confident/concentrated predictions are; calibration = whether those probabilities are correct. Want both. |
| Temperature / Platt scaling, isotonic regression | Post-hoc methods that remap raw model scores into calibrated probabilities. |
| Verbalized / elicited confidence | Confidence a model states in words or numbers rather than derived from logits; often poorly calibrated in RLHF'd LLMs. |
| Lead qualification / BANT / MEDDIC | Sales frameworks (Budget, Authority, Need, Timeline, etc.) that are human-built proxies for my hidden buying-readiness state. |
| Buying-intent detection / lead scoring | Estimating conversion likelihood from observable signals. |
| Escalation / human handoff | Transferring a case from the automated agent to a human. |
| SLA / response-time budget | Expected maximum response time; what makes "hold" costly and makes the problem genuinely sequential. |
| Deflection rate | Support-side metric: fraction of cases resolved without a human. |

## Search queries

Deferral / reject option (core academic)

learning to defer to an expert
consistent surrogate loss learning to reject
classification with a reject option cost
learning to complement human
human-AI deferral calibration

Selective prediction / abstention

selective classification risk coverage
selective prediction deep learning coverage
abstention cost-sensitive threshold

POMDP / myopic VOI

myopic value of information POMDP
belief state one-step lookahead policy
value of information active sensing agent
expected value of sample information decision

Cost-sensitive decision theory

cost-sensitive classification loss matrix
Bayes minimum risk decision threshold asymmetric cost

LLM confidence / calibration (your belief source)

LLM confidence calibration overconfident
verbalized confidence language model calibration
selective prediction large language models

Applied human-AI handoff (practitioner + applied research)

chatbot escalation to human policy
when should an AI agent defer to a human
LLM agent confidence-based escalation
customer support automation deflection escalation tradeoff

Sales/ops framing (for the cost side)

lead qualification model cost of missed lead
sales lead routing human vs automation cost

## Verified Reddit communities

| Community | Checked on | Active | Relevant | Keep or remove, and why |
| --- | --- | --- | --- | --- |
| r/reinforcementlearning | 14/08/26| Yes | Yes | Keep. Active, and found a poster with my exact structure (hidden state, noisy signals, asymmetric escalation cost, POMDP-vs-heuristic doubt) in a medical domain. Strong venue for the myopic-vs-planning question and for a completed 2+ reply discussion. |
| r/sales | 14/08/26| Yes | Yes | Keep. Active with decent replies. Best venue for the error-cost reality (over-escalate vs mis-answer a hot lead) and whether a qualifying question backfires. Frame in sales language, watch anti-self-promo. |
| r/LocalLLaMA | 14/08/26| Yes | Yes (LLM-only) | Keep. Very active. On-topic only for LLM-confidence/calibration questions; code not allowed, so keep posts conceptual/applied. My venue for the "is elicited LLM confidence trustworthy enough to act on" thread. |
| r/AI_Agents | 14/08/26| Yes | Yes | Keep. Already joined and posted. Continue that thread as replies come in to hit the 2+ reply bar. Still need to judge whether replies are substantive humans vs promotional noise. |
| r/LanguageTechnology | 14/08/26| Yes | Yes | Keep (secondary). Rules align, active, but replies are thin. Use for one targeted intent-as-hidden-state post; don't rely on it for a completed discussion. |
| r/AskStatistics | 14/08/26| Yes | Partial | Keep only if reframed. Bans AI questions, but calibration / decision-threshold / proper-scoring questions are on-topic in pure stats language (predicted probabilities, loss matrix, threshold). No LLM/agent framing. |
| r/MachineLearning | 14/08/26| Yes | Partial | Deprioritize. Redirects Q&A elsewhere and reads paper/news-curated; felt beginner-heavy for me. Not for asking. Possible later home for a results/preprint post only. |
| r/datascience | 14/08/26| Low (for me) | Partial | Remove / deprioritize. I found it quiet with low activity, so it fails the reply test. r/sales covers the cost-intuition side better. |

## X accounts

<!-- Only accounts I have opened and checked. "Active" and the keep/remove reason
     reflect what I found when I opened the profile, not a pre-made list. Dormant
     or off-topic accounts are kept in the table with the reason, so the removal
     is auditable rather than silent. -->

| Account | Handle | Checked on | Active | Relevant to my problem | Keep or remove, and why |
| --- | --- | --- | --- | --- | --- |
| Hussein Mozannar | @HsseinMzannar | 14/08/2026 | Yes | Yes | Keep. Learning-to-defer author, now at MS Research; best-matched researcher and most plausibly engageable of the academic set. Follow + attempt one substantive reply. |
| Jerry Liu | @jerryjliu0 | 14/08/2026 | Yes | Partial | Keep (low expectation). LlamaIndex co-founder; relevant to applied agents/orchestration, but posts product/ecosystem content, not deferral theory. Follow for pulse, not for topical debate. |
| Yarin Gal | @yaringal | 14/08/2026 | Low (last ~Jul) | Yes (citation) | Keep as citation-follow. Bayesian deep learning / uncertainty; only mildly active, so treat as read-the-work, not a discussion target. |
| David Sontag | @david_sontag / @layerhealth | 14/08/2026 | Yes | No (current content) | Remove for discussion. Real L2D pedigree but pivoted to health (Layer Health CEO); current feed is medical, not my problem. Cite his past work if used; don't expect topical engagement. |
| Gomez-Rodriguez | @autreche | 14/08/2026 | Very low | Yes (work) | Remove for discussion, keep for citation. Triage/deferral work is relevant; account rarely active, so no realistic discussion. |
| Nastaran Okati | @Nastaranokt | 14/08/2026 | No (no content) | Yes (work) | Remove for discussion. Paper verified real on Scholar; X account has no content, so it can't yield a discussion. Cite the paper, not the account. |
| Balaji Lakshminarayanan | @balajiln | 14/08/2026 | No (last 2022) | Yes (work) | Remove. Calibration/uncertainty work is relevant but account dormant since 2022. Read/cite only. |
## Five sources

<!-- Papers, articles, repos, or datasets. Fill a block in only after reading
     the source, not after finding it. -->

### Source 1

- Type: Paper (peer-reviewed, ML)
- Title: Consistent Estimators for Learning to Defer to an Expert (Mozannar & Sontag)
- Link: https://arxiv.org/pdf/2006.01862
- Why it matters here: Formal basis for treating "escalate to a human" as a costed decision, where the human is a second decision-maker with its own error and cost, not an automatic safe fallback.
- What I took from it: The framework that justifies pricing escalation as a real cost in my policy. I use it conceptually, not by implementing its joint surrogate loss, my project keeps an explicit belief and a myopic expected-cost rule rather than a jointly trained defer-classifier.
### Source 2

- Type: Paper (peer-reviewed, ML)
- Title: Predict Responsibly: Improving Fairness and Accuracy by Learning to Defer (Madras, Pitassi, Zemel)
- Link: https://arxiv.org/pdf/1711.06664
- Why it matters here: Frames rejection as a special case of deferral, and shows a fair model composed with a fair human can still yield an unfair system , relevant to my ethics/limitations, not my method.
- What I took from it: The system-level fairness point: even if each part is fair, escalation delays can fall unevenly (e.g. on non-standard or code-switched messages). I treat this as a limitations/ethics concern for a production deployment, not as a fairness objective I optimise in the v1 policy.

### Source 3

- Type: Paper (peer-reviewed, ML)
- Title: On Calibration of Modern Neural Networks (Guo, Pleiss, Sun, Weinberger)
- Link: https://arxiv.org/pdf/1706.04599
- Why it matters here: My myopic policy thresholds on a belief, so whether that belief's probabilities are calibrated is load-bearing. Source for ECE, reliability diagrams, and temperature scaling.
- What I took from it: That overconfidence would make automated actions look artificially cheap and suppress escalation, which is exactly my failure mode. I plan to measure ECE / plot a reliability diagram before trusting any threshold, and recalibrate if needed. Method depends on my belief source (LLM-derived), so it may be closer to Platt/isotonic than textbook temperature scaling. to be decided empirically.

### Source 4

- Type: Paper (peer-reviewed, ML)
- Title: Selective Classification for Deep Neural Networks (Geifman & El-Yaniv)
- Link: https://arxiv.org/pdf/1705.08500
- Why it matters here: Formal backbone for my "hold" and "escalate-on-low-confidence" actions as a reject option, and for reporting risk vs coverage instead of accuracy alone.
- What I took from it: (reword) A post-hoc rejection layer over a fixed belief source fits my design better than joint training, and softmax-response (max belief) is a cheap confidence signal for triggering escalation on low-confidence/OOD input. I report risk-coverage; the SGR formal guarantee is the principled version I approximate with empirical threshold tuning.
### Source 5

- Type: Paper (survey)
- Title: Planning and Acting in Partially Observable Stochastic Domains (Kaelbling, Littman & Cassandra)
- Link: https://people.smp.uq.edu.au/YoniNazarathy/Control4406_2014/resources/KaelblingLittmanCassandra1998.pdf
- Why it matters here: Grounds belief-as-sufficient-statistic and the intractability of exact POMDP planning, which is the justification for solving myopically rather than planning over belief space.
- What I took from it: The formal warrant for my scope: full belief-state planning is intractable, so a myopic one-step expected-cost policy is a defensible approximation. It also names the tension I care about, a strict myopic rule undervalues "ask a qualifying question," which is where VOI/EVSI comes in (implement vs. name as future work still open). I do not use RL or an RNN belief; my belief update is explicit.
<!-- Source 5 is provisional until verified. If it drops, the replacement is
     whichever VOI/EVSI or POMDP reference I actually read: search "Information
     Value Theory Howard 1966" or "expected value of sample information". Do not
     fill a block for a source I have not opened. -->

## Questions to answer

<!-- Questions that can actually be closed by the end of the week, and how I
     would know each one is closed. -->

| # | Question | How I will know it is answered |
| --- | --- | --- |
| 1 | Is the belief's probability calibrated enough to threshold on? The belief comes from an LLM, and if it's overconfident the expected-cost math is wrong and automated actions look artificially cheap. | Reliability diagram + ECE computed on my labeled/synthetic cases. Closed when I can say whether the numbers are trustworthy, and if not, that I recalibrated and re-checked. |
| 2 | Should "ask a qualifying question" be priced by myopic VOI/EVSI, or hand-tuned as a special case? A strict one-step policy structurally undervalues it because its payoff is a better belief next turn, not immediate. | Closed as a decision, not a proof: I state which path I took for v1 and why. If I defer VOI to future work, that counts as answered as long as I say so plainly. |
| 3 | Which error actually costs the most, and by roughly what ratio — missed escalation vs false escalation vs needless question? | Closed when the cost ranking is backed by practitioner input (r/sales) or a stated assumption + sensitivity analysis, not just my intuition. |
| 4 | Does asking a qualifying question backfire in practice (friction, drop-off, looking robotic)? | Closed by real answers from people who run inbound sales (r/sales), recorded in the discussion record with any design change. |
| 5 | Is a two-part hidden state (readiness distribution + separate needs-human probability) the right factorization, or does collapsing/adding a dimension change policy cost? | Closed when I've tested whether the factorization changes the policy's cost on my cases; if it doesn't, I prefer the simpler state and say so. |
| 6 | How do I even measure a missed escalation, given there's no missed-escalation label without a follow-up signal? | Likely closed as "structurally unmeasurable this week." Answered means I've stated the gap clearly: precision is measurable but biased upward, recall/false-negatives are not. |
| 7 | What is a baseline I can actually defend as "what a reasonable person would ship" (confidence-threshold-without-cost / always-answer / LLM-picks-action-directly)? | Closed when the baseline is chosen, justified in one line, and used in the experiment. |
| 8 | For a single first inbound message, is there enough signal to justify a belief, or does the hidden state only firm up as the conversation develops? | Partially closable via discussion (r/LanguageTechnology, r/sales) + my own cases. Answered means I can state whether single-message belief is worth it or whether this is really multi-turn. |

## AI prompts and important AI errors

### Prompts used

<!-- The actual prompt text, verbatim, under each slot. Real prompt beats a tidy
     description — paste what I actually typed. -->

**Prompt 1 — Research preparation (Claude)**
Purpose: prepare the research file — terms at my level, grouped search queries, candidate Reddit communities and X accounts (with confidence flags and exact verification steps), questions to take to real people, five real sources, which of my own claims need a source/test, and which parts of my problem are under-specified. Asked for candidates to verify in small batches, with the AI flagging its own uncertainty instead of guessing.
```
I'm working on a project and I'm on the step where I prepare a research file. I want your help preparing research, but I need you to be honest about confidence and never present uncertain things as fact.

Context that's already locked, do not re-open these:

- My problem: "The agent observes an inbound message from a sales lead. It must select answer, ask a qualifying question, hold, or escalate to a human because the lead's true intent and buying-readiness are not known."

- My real level: I'm not a beginner on this. I run a live conversational sales agent in production, and I have a probability/options-trading background, so I'm comfortable with belief distributions, expected value, and cost asymmetry. Aim the technical terms and sources at that level, not at an intro level.

- My framing: I treat this as a POMDP but solve it with a myopic (one-step) expected-cost policy over a belief, not full belief-state planning. Keep that distinction accurate in any terminology you give me.

- My objective: design and test a cost-aware escalation policy where the agent holds a belief over the lead's hidden intent/readiness and picks the action with the lowest expected cost, then compare it against a baseline.

- Public boundary: everything stays at the general problem level. No product name, no client details, no real prompts or data.

Now help me with these, and for anything you can't verify, say so explicitly rather than guessing:

1. The precise technical terms for this problem (decision theory, POMDP, escalation/deferral, calibration, cost-sensitive decisions, etc.), so I can search and write accurately.
2. Useful search queries, grouped by what they'd turn up.
3. 5 to 10 candidate Reddit communities. For EACH: why it's relevant, and your confidence that it's active and on-topic. Mark ones I must verify myself. I will remove any that are dead or irrelevant.
4. Candidate researchers/engineers on X relevant to this (learning-to-defer, human-AI handoff, decision under uncertainty, applied LLM agents). Mark each with confidence and flag that I need to verify they're real and active.
5. Questions I should be able to answer about hidden states, evidence, actions, and error costs, phrased so I can take them to real people.
6. 5 genuinely useful and REAL papers/articles/repos/datasets, with enough detail that I can find and read them myself. Do not invent citations. If you're not confident a specific paper exists as described, say so and give me a search path instead.
7. Which of my own claims/assumptions need a source or a test to back them.
8. Which parts of my problem statement are still unclear or under-specified.

Give me all of this as candidates for me to verify, not as finished answers.

[plus formatting instructions: present each Reddit community, X account, and source as a verify-and-mark row with Item / Why relevant / Your confidence / What I should check / MY VERDICT; be interactive and give candidates in small batches, pausing after each; do not write my error log.]
```

**Prompt 2 — Paper understanding + usefulness + self-quiz (NotebookLM)**
Purpose: understand each research paper in depth (including hard-to-read
formulas), get a usefulness verdict, and be quizzed on it to test my own grasp
before deciding if it fits my project.
```
I've uploaded the PDFs of my research papers. For each one:

1. Give me a complete, detailed understanding of the paper — enough that it
feels like I actually read the full paper, so I can form my own opinion.

2. Explain every important formula that's hard to read: what each symbol means,
what the equation is doing, and why it's built that way. Do not tie any of
this to my project yet.

3. Then, separately, give me a usefulness analysis: is this paper's findings
useful or not useful, and why. Cover both the strengths and the limitations.

4. Then quiz me on the paper as multiple-choice questions (no limit on how many),
and based on my answers, give me an overall assesment.
```

**Prompt 3 — X post finder (Boardy, daily)**
Purpose: find 3–4 recent real X posts I could genuinely reply to, with URL, who posted, a one-line summary, and one specific non-generic angle for me to reply from — with an instruction not to invent URLs and to give fewer if it couldn't find good ones.

```
You are helping me find X posts to comment on. My project: an AI agent that decides, on an inbound sales message, whether to answer, ask a qualifying question, hold, or escalate to a human — under hidden lead intent and readiness. I frame it as a POMDP solved with a myopic one-step expected-cost policy over an explicit belief, with asymmetric error costs (a missed escalation is far more expensive than a needless one). I care about: human-AI handoff, when agents should defer to a human, LLM confidence/calibration, cost-sensitive decisions, and applied LLM-agent building.

Find me 3–4 recent X posts (last 7 days, ideally last 48h) that I could genuinely reply to — posts making a claim, sharing a build, or asking a question about any of: agent escalation / human handoff, confidence-based deferral, LLM calibration or overconfidence, when to trust an agent vs a human, or cost-aware agent decisions.

For each: give the post URL, who posted it (name + why they're relevant), a one-line summary of what they're claiming or asking, and one specific, non-generic angle I could reply from based on my project. Prefer posts with some engagement (so a reply gets seen) but not so viral my reply drowns. Skip anything I can't add a substantive, specific comment to. Do not invent URLs — only real posts you can actually find; if you can't find 3–4 good ones today, give me fewer and say so.
```
### Important AI errors

<!-- Every case where an AI tool was confidently wrong. This section is
     evidence that the output was checked rather than trusted. -->

| Tool | What it claimed | How I caught it | What was actually true |
| --- | --- | --- | --- |
| NotebookLM | Its "grand synthesis" of the five papers recommended building my project as joint neural training of a classifier+rejector, Gumbel-Softmax, fairness regularization, model-free RL (DQN/PPO), and an RNN/LSTM hidden state as the belief. | I compared its recommendation against my locked design and saw it contradicted it directly. It had run with my exploratory MCQ answers (e.g. "direct neural policy", "model-free RL") and treated them as my project direction. | Those architectures are the opposite of my design. My project is an explicit two-part belief with a myopic one-step expected-cost policy. The papers are justification/framing for that design, not a to-do list of architectures to implement. |
| NotebookLM | Presented its per-paper study guides with confident specifics, e.g. that the calibration paper contains a "complete proof that temperature scaling is the unique solution to the entropy maximization problem," and attributed a selective-classification bound to "Gascuel & Caraux." | Flagged as claims to verify against the actual papers before writing them down, rather than repeating them. | Still to be confirmed at source — reads like embellishment. Not recorded as fact until checked in the real paper; the "unique solution" phrasing and the bound attribution are not to be cited on NotebookLM's word. |
| Claude | Suggested candidate X accounts for learning-to-defer / calibration / handoff, and implied there was a canonical "myopic VOI" paper I could cite. | I verified each account myself on X, and searched for the VOI paper. | Several accounts were dormant or off-topic (e.g. researcher last active 2022; another pivoted to a health startup; another had no content). There is no single canonical "myopic VOI" title — the concept traces to Howard's decision analysis and shows up under EVSI / active learning, so it's a search path, not one citation. Claude flagged low confidence on these itself and declined to guess exact handles. |
| Claude | Drafted public-facing text (LinkedIn reply, Reddit thank-you replies) in a clean, tidy style. | Ayush's feedback flagged that AI-written prose reads as AI in seconds; I also felt the drafts didn't sound like me. | The thinking was mine but the wording had AI-polish tells. Fix: draft public writing in my own voice and use AI to pressure-test, not to ghostwrite. Recorded as a process change, not a design change. |
| NotebookLM | Claimed it had produced a comprehensive report giving "the depth of the complete 40+ page work" for the deferral paper. | I checked the output against the real paper length and pushed back — it was far thinner than the actual 40–48 page paper. | The report was a partial summary, not equivalent to the full paper. It also kept trying to jump to project-fit MCQs before delivering the depth I asked for. |
<!-- 
Full NotebookLM report/MCQ transcripts and full Claude session available on
     request if the raw exchanges are needed for audit. -->