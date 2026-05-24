# Diagnosis Polarity Ablation (2026-05-24)

This note records the ChartQA diagnosis-polarity stress test requested after
the C.1 sensitivity runs. The appendix-facing summary is in
`sections/A_appendix.tex`, Table `tab:ablation_diagnosis_polarity`.

## Protocol

- Dataset: ChartQA training split, first 50 cases under the structured ordering.
- Runtime: Doubao-Seed-2.0-Pro function-calling VQA endpoint.
- Evolution: three planning rounds, `tool_preference=prefer_tools`.
- Evaluation: train-subset replay only. This is a mechanism stress test, not a
  held-out effect-size estimate.
- Variants:
  - Correct-only diagnosis: expose only baseline-correct cases to the
    diagnosis digest.
  - Error-only diagnosis: expose only baseline-incorrect cases to the
    diagnosis digest.

## Artifacts

| Variant | Artifact |
| --- | --- |
| Correct-only diagnosis | `ablation_chartqa_correctonly_k50_n3_doubao_20260524T124038Z` |
| Error-only diagnosis | `ablation_chartqa_erroronly_k50_n3_doubao_20260524T124038Z` |

## Results

| Variant | Rounds attempted | Promoted bundles | Promoted tools | Promoted skills | Train replay |
| --- | ---: | ---: | ---: | ---: | ---: |
| Correct-only diagnosis | 0 | 0 | 0 | 0 | 45/50 (0.900) |
| Error-only diagnosis | 3 | 0 | 0 | 0 | 45/50 (0.900) |

The error-only run had a 46/50 (0.920) selection baseline. Round 1 generated
`chart_data_point_highlighter` but failed smoke validation because the paired
skill referenced an unavailable tool. Rounds 2 and 3 generated
`chart_series_value_overlay` and `chart_data_point_overlay_generator`,
respectively; both passed smoke validation but tied the 46/50 selection
baseline and were rejected.

## Interpretation

Correct-only diagnosis gives the loop no failure cluster, so generation never
starts. Error-only diagnosis is not inert, but it repeatedly asks for a broad
`generate_both` repair on the same ChartQA error cluster and produces a fresh
overlay/highlighter-style tool each round. Because none of those candidates
beats the same-run baseline, the library remains unchanged.

This supports the intended qualitative mechanism claim: useful evolution needs
contrast between solved and unsolved cases. Correct cases alone cannot define a
repair target; errors alone can identify pain points but tend to push the
generator toward repeated large rewrites instead of stable reusable capability
formation.
