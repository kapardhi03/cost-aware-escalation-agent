Published: [https://x.com/kapardhi200903/status/2090948515669381337?s=20
](https://x.com/kapardhi200903/status/2094595265659584765?s=20)


Better calibration made my agent worse. Every metric said it got better.
Continuing last week's project: an agent replying to inbound leads that has to act before it knows intent. Answer, ask, hold, or hand off to a human.

The belief it acts on is a probability, so I calibrated it. Fit a map on half the cases, scored the other half. Standard move.

Cross-entropy down. ECE down. Brier down. Every calibration number moved the right way.
Then I looked at what it actually did.
It stopped answering entirely and escalated 41 of 50 cases. Much worse at the real job.

The reason is structural, not a bug. The map can't output a probability below 6/23, and the threshold for answering sits underneath that. After calibration, the belief physically can't enter the region where answering is right.

Better calibrated. Blind to the one part of the space the decision needed.None of my scoring rules would catch it. They grade the probabilities. The failure is in the range the probabilities can reach, and no proper scoring rule looks there.

Synthetic data, and I say so throughout. But the lesson holds: a metric improving is not the decision improving, and the gap can be a wall you don't see until you check the decisions themselves.
