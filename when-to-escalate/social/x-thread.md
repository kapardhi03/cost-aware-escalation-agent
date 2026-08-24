Published: https://x.com/kapardhi200903/status/2090948515669381337?s=20

## Corrections

The link in the last post of the thread points at
`.../tree/main/week1/when-to-escalate`. That path no longer exists: the project
was moved to the repository root and now lives at
`.../tree/main/when-to-escalate`. The post body below is left exactly as
published — a published record is not edited after the fact — so the link in it
is stale by design and this note is the correction.

---

Built a small agent this week for a problem I hit in production: a lead messages you and you can't tell if they're a real buyer, a competitor, or a bot. Answer, ask, hold, or escalate to a human?

Every wrong choice costs a different amount. Most agents treat them as equal.
The approach: instead of one confidence score, hold a two-part belief, readiness (hot/warm/cold) and a separate needs-human probability, then pick the action with the lowest expected cost, where a missed escalation is priced far above a needless one.
Then I spent most of the week trying to break my own result.

The cost-blind baseline I was beating? Turned out to be just a 0.5 threshold in disguise. So part of the "win" is less than it looks. Said so in the writeup.
Against a policy that just escalates everything, my agent doesn't win on cost at all.

What it buys is human load: same expected cost, but 43 escalations out of 100 instead of all 100.
Every missed escalation came from one under-confident probability. But recalibrating it only halved the misses.
The rest survive because the model emits probabilities at one decimal place, and 35% of cases sit pinned at 0.2, just under the line.
Two of the five actions were selected zero times in 100 cases. The five-action design is a three-action policy in practice. I report that instead of hiding it.
It's synthetic data, so none of the precision/recall transfers to a live inbox, and I'm clear about that throughout.

Open question for anyone running these in production: where does a myopic one-step cost policy break in ways synthetic tests can't show?
Kaps
@kapardhi200903
Code + writeup:  https://github.com/kapardhi03/cost-aware-escalation-agent/tree/main/week1/when-to-escalate

#AIagents #LLM #MachineLearning #humanintheloop