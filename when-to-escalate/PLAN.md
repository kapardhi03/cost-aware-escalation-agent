# PLAN — v1

> **Personal working file, not a project artifact.** Nobody reviews this file.
> It exists so I know what to do each morning. The reviewed work lives in
> `research-file.md`, `discussion-record.md`, `review-record.md`,
> `decisions/probability-decision-record.md`, `paper/`, `src/`, `experiments/`,
> `results/`, and `social/`.

**Why the public work sits at the front of the schedule:** Reddit and X depend on
strangers replying on their own schedule. A thread posted on Day 6 will not have
two replies by Day 7. So discussion starts on Day 1 and runs every single day,
and the writing, building, and reviewing stack up behind it.

## Running targets

- [ ] Reddit: 10+ contributions across 5+ communities
- [ ] Reddit: 5 threads that reach 2+ replies from real people
- [ ] X: 15-25 accounts followed
- [ ] X: 3-4 comments per day, every day
- [ ] X: 3 threads of my own that get replies
- [ ] Every row in `discussion-record.md` carries an explanation, not just a link

---

## Day 1 — Setup and first public contact

- [ ] Fill `research-file.md`: project objective, technical terms, search queries
- [ ] Check each candidate Reddit community for recent activity and topical fit; delete the ones that fail and write down the reason
- [ ] Fill the five sources section in `research-file.md`
- [ ] Write and post the Skool architecture writeup
- [ ] Reddit: 2 contributions in 2 different verified communities
- [ ] X: follow the first batch of accounts, heading for 15-25
- [ ] X: 3-4 comments
- [ ] X: post thread 1 (problem framing)
- [ ] Log everything posted today in `discussion-record.md`
- [ ] Outside the repo: post the Skool writeup, post on Reddit and X, read sources

## Day 2 — Agent design, keep the threads alive

- [ ] Reddit: 2 contributions in 2 new communities (running total 4 across 4)
- [ ] Reddit: reply to every human answer received so far
- [ ] X: 3-4 comments; keep following toward the target
- [ ] X: post thread 2
- [ ] Draft the agent-design writeup into `paper/main.tex`, Agent design section
- [ ] Write down the state, the action set, and the tool boundaries the design assumes
- [ ] Update `discussion-record.md` with today's replies and any design change they caused
- [ ] Outside the repo: post on Reddit and X, read sources

## Day 3 — Probability model

- [ ] Reddit: 2 contributions, reaching the 5th community (running total 6)
- [ ] Reddit: push the open threads toward 2+ replies
- [ ] X: 3-4 comments
- [ ] X: post thread 3
- [ ] Fill all nine rows of `decisions/probability-decision-record.md`
- [ ] Work the six Bayesian-update steps in that file; check the hidden-state probabilities sum to 100%
- [ ] Draft the probability-model writeup into `paper/main.tex`, Probability model and decision rule
- [ ] Outside the repo: post on Reddit and X, read sources

## Day 4 — Synthetic test harness

- [ ] Build the synthetic conversation set into `data/`
- [ ] Build the agent and the policy code into `src/`
- [ ] Build the harness and its run config into `experiments/`
- [ ] Write down what the harness measures **before** running it
- [ ] Reddit: 2 contributions (running total 8)
- [ ] X: 3-4 comments; chase replies on threads 1-3
- [ ] Outside the repo: post on Reddit and X, read sources

## Day 5 — Run the test, then the failure analysis

- [ ] Run the harness; write the raw output to `results/`
- [ ] Draft the Test method section in `paper/main.tex`
- [ ] Draft the Results section in `paper/main.tex`
- [ ] Pick the worst cases and write what broke, into the Failure analysis section
- [ ] Reddit: 2+ contributions to clear the 10+ target
- [ ] Check that 5 Reddit threads have 2+ replies; if not, post follow-ups today
- [ ] Check that 3 X threads have replies
- [ ] Record at least one design change traced to a public discussion in `discussion-record.md`
- [ ] Outside the repo: post on Reddit and X, follow up with everyone who replied

## Day 6 — Three AI reviews

- [ ] Review 1: run the draft through one AI tool; log every comment in `review-record.md`
- [ ] Review 2: second tool, same logging
- [ ] Review 3: third tool, same logging
- [ ] For each comment: accept or reject, give the reason, name the change, point at the evidence
- [ ] Apply the accepted changes
- [ ] Draft the remaining sections in `paper/main.tex`: Introduction, Related work and user discussions, Limitations ethics and human control, Conclusion and new questions
- [ ] X: 3-4 comments
- [ ] Outside the repo: post on Reddit and X

## Day 7 — Preprint and social

- [ ] Replace the placeholder document class in `paper/main.tex` with the IJCAI author-kit style file
- [ ] Fill `paper/references.bib`, verified sources only
- [ ] Write the abstract last; compile `paper/main.tex` clean, no missing references, no missing figures
- [ ] Fill the "How to reproduce the test" section in `README.md`
- [ ] Write `social/linkedin-post.md`: all 7 required items
- [ ] Write `social/x-thread.md`: problem, test, result, open question
- [ ] Final pass: no empty required cells left in any record file, and the counts are met
- [ ] X: 3-4 comments
- [ ] Outside the repo: post the LinkedIn post and the X thread, then reply to comments
