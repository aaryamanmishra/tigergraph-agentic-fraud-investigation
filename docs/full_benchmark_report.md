# HHGOA 2026 — 20-Case Benchmark Report

## Execution Summary

- Cases executed: 20/20
- Backend: TigerGraph / FraudNet
- LLM: Groq (`openai/gpt-oss-20b`) via OpenAI-compatible provider
- GraphRAG: Enabled
- Fraud verdicts: 18
- Legitimate verdicts: 2
- SAR-required cases: 0
- Total LLM tokens: 13,511
- Average workflow latency: 29.98s

## Per-Case Results

| Case | Status | Verdict | Pattern | Exposure | SAR | Tokens | Latency |
|---|---|---|---|---:|---|---:|---:|
| HHG-001 | closed_legitimate | legitimate | none | $0.00 | False | 850 | 21.05s |
| HHG-002 | closed_fraud | fraud | out_of_region_use | $292.36 | False | 754 | 19.11s |
| HHG-003 | closed_fraud | fraud | undocumented | $49.00 | False | 747 | 26.18s |
| HHG-004 | closed_fraud | fraud | undocumented | $128.33 | False | 814 | 21.06s |
| HHG-005 | closed_fraud | fraud | undocumented | $100.07 | False | 613 | 22.25s |
| HHG-006 | closed_fraud | fraud | undocumented | $482.12 | False | 605 | 20.74s |
| HHG-007 | closed_fraud | fraud | out_of_region_use | $111.92 | False | 658 | 36.93s |
| HHG-008 | closed_fraud | fraud | undocumented | $55.68 | False | 587 | 29.11s |
| HHG-009 | closed_fraud | fraud | undocumented | $30.02 | False | 818 | 21.55s |
| HHG-010 | closed_fraud | fraud | undocumented | $1000.03 | False | 584 | 19.37s |
| HHG-011 | closed_fraud | fraud | undocumented | $131.30 | False | 572 | 81.76s |
| HHG-012 | closed_legitimate | legitimate | none | $0.00 | False | 814 | 25.45s |
| HHG-013 | closed_fraud | fraud | undocumented | $35.66 | False | 610 | 28.81s |
| HHG-014 | closed_fraud | fraud | undocumented | $74.96 | False | 809 | 22.89s |
| HHG-015 | closed_fraud | fraud | out_of_region_use | $599.94 | False | 638 | 23.34s |
| HHG-016 | closed_fraud | fraud | undocumented | $59.67 | False | 599 | 19.49s |
| HHG-017 | closed_fraud | fraud | undocumented | $100.09 | False | 583 | 20.29s |
| HHG-018 | closed_fraud | fraud | undocumented | $39.08 | False | 726 | 95.01s |
| HHG-019 | closed_fraud | fraud | out_of_region_use | $99.92 | False | 565 | 20.77s |
| HHG-020 | closed_fraud | fraud | undocumented | $125.08 | False | 565 | 24.43s |

## Notes

- Results are generated from the individually executed case JSON artifacts.
- The earlier rate-limited batch run is not used as the authoritative result set.
- The final result set contains 20 individually executed cases.
