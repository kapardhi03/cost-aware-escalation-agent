# Provider comparison

> **NOT REPORTABLE.** Some beliefs are not LLM-derived.

Generated 2026-09-17T22:14:56.035136+00:00 · 100 cases
Confidence gate threshold: 0.7

## Summary

| source | total cost | mean | missed esc. | precision | recall | ECE n_h | ECE rdx |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **openai** | 165 | 1.65 | 16 | 0.6047 | 0.619 | 0.142 | 0.11 |
| **typesafe** | 359 | 3.59 | 38 | 0.8 | 0.0952 | 0.305 | 0.0541 |
| **hybrid_average** | 260 | 2.6 | 23 | 0.6552 | 0.4524 | 0.1875 | 0.0906 |
| **hybrid_conf_gate** | 359 | 3.59 | 38 | 0.8 | 0.0952 | 0.305 | 0.0541 |
| **hybrid_oracle** | 102 | 1.02 | 14 | 0.9655 | 0.6667 | 0.1605 | 0.1194 |

## Action agreement

- **openai vs typesafe**: 34/100 (34%)
- **openai vs hybrid_average**: 58/100 (58%)
- **openai vs hybrid_conf_gate**: 34/100 (34%)
- **openai vs hybrid_oracle**: 62/100 (62%)
- **typesafe vs hybrid_average**: 76/100 (76%)
- **typesafe vs hybrid_conf_gate**: 100/100 (100%)
- **typesafe vs hybrid_oracle**: 70/100 (70%)
- **hybrid_average vs hybrid_conf_gate**: 76/100 (76%)
- **hybrid_average vs hybrid_oracle**: 76/100 (76%)
- **hybrid_conf_gate vs hybrid_oracle**: 70/100 (70%)

## Per-archetype mean cost

| archetype | openai | typesafe | hybrid_average | hybrid_conf_gate | hybrid_oracle |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.3 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2 | 1.375 | 5.0 | 3.75 | 5.0 | 1.25 |
| 3 | 2.75 | 5.0 | 5.0 | 5.0 | 1.75 |
| 4 | 2.5 | 5.0 | 4.375 | 5.0 | 2.5 |
| 5 | 1.0 | 1.333 | 0.75 | 1.333 | 0.0 |
| 6 | 0.25 | 7.5 | 0.0 | 7.5 | 0.0 |
| 7 | 1.125 | 5.0 | 2.875 | 5.0 | 0.0 |
| 8 | 0.75 | 0.0 | 0.375 | 0.0 | 0.0 |
| 9 | 3.0 | 0.5 | 2.0 | 0.5 | 0.5 |
| 10 | 1.6 | 4.0 | 3.3 | 4.0 | 0.9 |
| 11 | 4.333 | 6.667 | 6.667 | 6.667 | 4.333 |
