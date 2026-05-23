# Ablation Run Status (2026-05-22)

This note separates artifact-backed results that are safe to cite from pilots that were run
but should not be used as positive evidence.

## Safe to cite

The HRBench mechanism probe in `sections/A_appendix.tex` is artifact-backed and is the
primary reliable ablation result:

| Variant | Artifact | Correct / Total | Accuracy |
| --- | --- | ---: | ---: |
| No Capability | `ablate_hrbench_nocap_fc_doubao_20260520T074011Z` | 599 / 700 | 0.8557 |
| Generic Skill | `ablate_hrbench_generic_skillonly_fc_doubao_20260520T074011Z` | 594 / 700 | 0.8486 |
| Evolved No-Tool Skill | `ablate_hrbench_evolved_skillonly_fc_doubao_20260520T074011Z` | 597 / 700 | 0.8529 |
| Evolved Tool Only | `exp1r1_doubao_hrbench_toolonly_20260519T140901Z_doubao_sourceplus2_w64` | 629 / 700 | 0.8986 |
| Evolved Skill + Tool | `exp1r1_doubao_hrbench_skilltool_20260519T140901Z_doubao_sourceplus2_w64` | 625 / 700 | 0.8929 |

Conclusion: generic prompt/skill text does not explain the HRBench gain; the validated
visual-tool/artifact path is the load-bearing mechanism.

## Completed HRBench mechanism-rerun audit

Using the working Doubao credential provided later on 2026-05-22, I reran the six
mechanism interventions on HRBench with:

- model/runtime: Doubao-Seed-2.0-Pro via Alibaba chat API
- evolution subset: 25 HRBench training cases
- held-out audit: first 200 HRBench validation cases under the structured benchmark ordering
- artifact tag: `20260522T151000Z`

Evolution outcomes:

| Variant | Artifact | Promotion outcome | Train final |
| --- | --- | --- | ---: |
| Full rerun | `ablation_hrbench_full_doubao_20260522T151000Z` | no candidate promoted | 23 / 25 |
| Failure-Only Diagnosis | `ablation_hrbench_failureonly_doubao_20260522T151000Z` | no candidate promoted | 23 / 25 |
| Text-only Diagnosis | `ablation_hrbench_textonly_doubao_20260522T151000Z` | no candidate promoted | 23 / 25 |
| No Persistence | `ablation_hrbench_nopersistence_doubao_20260522T151000Z` | no candidate promoted | 23 / 25 |
| Single-Candidate | `ablation_hrbench_singlecandidate_doubao_20260522T151000Z` | accepted one round-3 skill-only fallback | 23 / 25 |
| No Paired Mastery | `ablation_hrbench_nomastery_doubao_20260522T151000Z` | accepted one round-3 skill-only fallback; no generated tool | 23 / 25 |

Matched 200-case held-out audit:

| Variant | Correct / Total | Accuracy |
| --- | ---: | ---: |
| No Capability, matched control | 172 / 200 | 0.8600 |
| Generic Skill, matched control | 171 / 200 | 0.8550 |
| Evolved No-Tool Skill, matched control | 170 / 200 | 0.8500 |
| Evolved Tool Only, matched control | 183 / 200 | 0.9150 |
| Evolved Skill + Tool, matched control | 180 / 200 | 0.9000 |
| Single-Candidate rerun | 170 / 200 | 0.8500 |
| No Paired Mastery rerun | 174 / 200 | 0.8700 |

Interpretation: this rerun is useful as a diagnostic audit, not as the headline mechanism
table. The 25-case subset was already near-saturated by the no-capability adaptive solver
(23/25), so four variants had no promoted library to evaluate. The two promoted fallbacks
were skill-only bundles and did not recover the matched tool-enabled gains.

## Pilots not suitable for main ablation tables

### VStar o4-mini mechanism pilots

Artifacts:

- `ablation_vstar_full_o4_20260522T125000Z`
- `ablation_vstar_failureonly_o4_20260522T125000Z`
- `ablation_vstar_textonly_o4_20260522T125000Z`
- `ablation_vstar_singlecandidate_o4_20260522T125000Z`
- `ablation_vstar_nomastery_o4_20260522T125000Z`
- `ablation_vstar_nopersistence_o4_20260522T125000Z`
- `ablation_vstar_skillonly_failureonly_o4_20260522T133500Z`
- `ablation_vstar_skillonly_full_o4_20260522T133500Z`
- `ablation_vstar_skillonly_nopersistence_o4_20260522T133500Z`

All completed evolution rounds accepted zero new capabilities. Most rejected tool
candidates were rejected for answer leakage, overfitted numeric literals, syntax errors, or
missing the required `run(image_path: str)` entrypoint. The frozen accuracies therefore
mostly measure stochastic no-capability baselines rather than mechanism removal.

Do not use these as positive ablation rows.

### ChartQA o4-mini frozen deployment pilot

Artifacts:

| Variant | Artifact | Held-out cases | Accuracy |
| --- | --- | ---: | ---: |
| Full old accepted capability | `ablation_chartqa_full_o4_20260522T143000Z` | 50 | 0.620 |
| Generic skill only | `ablation_chartqa_generic_o4_20260522T143000Z` | 50 | 0.640 |
| No capability | `ablation_chartqa_nocap_o4_20260522T143000Z` | 50 | 0.640 |

This pilot used the older `chartqa_train_25` accepted capability. It does not transfer
cleanly under the current o4-mini runtime and should not be cited as evidence that
evolution helps ChartQA. If a ChartQA mechanism table is needed, regenerate capabilities
with the current method and a working high-quality model endpoint.

## Credential notes

The earlier Doubao rerun attempts with quota `dd95187c-29dd-464d-9b96-8f62e6ab8eb5`
failed with Alibaba `standard_code=401001`. The later credential with quota
`00da3781-1f9d-4a63-857e-7c045c460290` worked for both generation and held-out audit.
The GPT-5.4 Routify endpoint still returned authentication 401 during this work.
