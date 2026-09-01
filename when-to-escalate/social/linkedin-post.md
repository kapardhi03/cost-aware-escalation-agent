Published: https://lnkd.in/p/dzkemd7u

Better calibration made my agent worse. Every metric said it got better.
 
Continuing the research project from last week: an agent replying to inbound leads that has to act before it knows intent. Answer, ask a question, hold, or hand off to a human.
 
The belief it works from is a probability, so I did the obvious thing and calibrated it. Fit a map on half the cases, scored the other half.
 
Cross-entropy down. ECE down. Brier down. Every calibration number moved the right way.
 
Then I looked at what it actually did. It stopped answering entirely and escalated 41 of 50 cases. Much worse at the real job.
 
The reason is structural, not a bug. The map I fit can't output a probability below 6/23, and the threshold for answering sits underneath that. So after calibration the belief physically cannot enter the region where answering is the right call.
 
Better calibrated. Blind to the one part of the space the decision needed.
 
None of my scoring rules would have caught this. They grade the probabilities. The failure is in the range the probabilities can reach, and no proper scoring rule looks there.
 
It's synthetic data and I say so throughout. But the lesson holds: a metric improving is not the decision improving, and the gap between them can be a wall you don't see until you check the decisions themselves.

#AIagents #MachineLearning #LLM #conversationalAI #humanintheloop


