# C.1 ChartQA Training-Size Sensitivity

Date: 2026-05-23

Protocol: safe ChartQA normalization, `agent_train_adaptive` + `frozen_inference`, `N=3`, `max_attempts=5`, `tool_preference=prefer_tools`, held-out `val[:200]`, Doubao-Seed-2.0-Pro.

| k | Artifact SID | Train replay | Frozen val[:200] | Promoted capabilities | Snapshot |
|---:|---|---:|---:|---:|---|
| 10 | `c1_chartqa_k10_n3_doubao_20260523T144946Z` | 9/10 = 0.900 | 162/200 = 0.810 | 0 | `c1_chartqa_k10_n3_doubao_20260523T144946Z_train_snapshot` |
| 25 | `c1_chartqa_k25_n3_doubao_20260523T161500Z` | 23/25 = 0.920 | 159/200 = 0.795 | 0 | `c1_chartqa_k25_n3_doubao_20260523T161500Z_train_snapshot` |
| 50 | `c1_chartqa_k50_n3_doubao_20260523T170000Z` | 45/50 = 0.900 | 159/200 = 0.795 | 1 skill | `c1_chartqa_k50_n3_doubao_20260523T170000Z_train_snapshot` |
| 100 | `c1_chartqa_k100_n3_doubao_20260523T170000Z` | 88/100 = 0.880 | 158/200 = 0.790 | 1 skill | `c1_chartqa_k100_n3_doubao_20260523T170000Z_train_snapshot` |
| 200 | `c1_chartqa_k200_n3_doubao_20260523T171000Z` | 180/200 = 0.900 | 161/200 = 0.805 | 1 skill + 1 tool | `c1_chartqa_k200_n3_doubao_20260523T171000Z_round_1_accepted` |

Notes:

- `k=200` round 1 accepted a generated `chart_value_overlay` tool with a paired ChartQA mastery skill. Rounds 2 and 3 were evaluated and rejected (`0.885` and `0.890` candidate train accuracy against the `0.900` active baseline).
- The `k=200` final held-out pass was restarted cleanly after an initial finalize attempt inherited an incompatible endpoint parameter and wrote empty-answer failures. Those bad `frozen_inference` rows were removed, and the reported `161/200` comes from the clean restart using the same Doubao environment as the successful C.1 runs.
- The paper figure is `figures/chartqa_k_sensitivity.pdf`.
