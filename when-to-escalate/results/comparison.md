# Provider comparison

Generated 2026-09-18T00:30:25.057552+00:00 · 100 cases
Confidence gate threshold: 0.7

## Summary

| source | total cost | mean | missed esc. | precision | recall | ECE n_h | ECE rdx |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **openai** | 165 | 1.65 | 16 | 0.6047 | 0.619 | 0.142 | 0.11 |
| **typesafe** | 137 | 1.37 | 20 | 0.7586 | 0.5238 | 0.1373 | 0.3625 |
| **hybrid_average** | 129 | 1.29 | 16 | 0.7027 | 0.619 | 0.1292 | 0.1761 |
| **hybrid_conf_gate** | 137 | 1.37 | 20 | 0.7586 | 0.5238 | 0.1373 | 0.3625 |
| **hybrid_oracle** | 116 | 1.16 | 17 | 0.7576 | 0.5952 | 0.1511 | 0.0976 |

## Action agreement

- **openai vs typesafe**: 66/100 (66%)
- **openai vs hybrid_average**: 85/100 (85%)
- **openai vs hybrid_conf_gate**: 66/100 (66%)
- **openai vs hybrid_oracle**: 72/100 (72%)
- **typesafe vs hybrid_average**: 80/100 (80%)
- **typesafe vs hybrid_conf_gate**: 100/100 (100%)
- **typesafe vs hybrid_oracle**: 84/100 (84%)
- **hybrid_average vs hybrid_conf_gate**: 80/100 (80%)
- **hybrid_average vs hybrid_oracle**: 80/100 (80%)
- **hybrid_conf_gate vs hybrid_oracle**: 84/100 (84%)

## Per-archetype mean cost

| archetype | openai | typesafe | hybrid_average | hybrid_conf_gate | hybrid_oracle |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.3 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2 | 1.375 | 1.375 | 0.125 | 1.375 | 1.125 |
| 3 | 2.75 | 2.0 | 2.0 | 2.0 | 2.75 |
| 4 | 2.5 | 2.5 | 3.125 | 2.5 | 1.875 |
| 5 | 1.0 | 0.5 | 0.833 | 0.5 | 0.583 |
| 6 | 0.25 | 1.25 | 0.25 | 1.25 | 0.125 |
| 7 | 1.125 | 0.75 | 0.75 | 0.75 | 0.75 |
| 8 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 |
| 9 | 3.0 | 2.667 | 3.0 | 2.667 | 2.667 |
| 10 | 1.6 | 1.7 | 1.1 | 1.7 | 1.0 |
| 11 | 4.333 | 1.5 | 1.5 | 1.5 | 1.5 |
