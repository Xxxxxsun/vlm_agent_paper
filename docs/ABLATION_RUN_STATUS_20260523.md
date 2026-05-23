# Ablation Run Status (2026-05-23)

This note records the guarded HRBench ablation pilot run on May 23, 2026.
The appendix-facing summary is in `sections/A_appendix.tex`,
Table `tab:ablation_guarded_pilot`.

## Protocol

- Dataset: HRBench validation split, first 30 cases under the structured ordering.
- Runtime: Doubao-Seed-2.0-Pro function-calling VQA endpoint.
- Evolution: one planning round, `tool_preference=require_tools`.
- Guards: `--require-generated-tool-candidate` and
  `--forbid-skill-only-fallback`.
- Reported score: candidate selection accuracy on the same 30-case subset
  against the same-run baseline. These are mechanism-audit scores, not
  held-out effect sizes.

## Reported rows

| Variant | Artifact | Baseline | Candidate | Delta | Outcome |
| --- | --- | ---: | ---: | ---: | --- |
| Full tool-guard pilot | `ablation_hrbench_toolguard_fastdry30_w8_v5_doubao_20260523T110300Z` | 0.5667 | 0.6000 | +0.0333 | accepted 1 generated tool + 1 paired skill |
| Failure-Only Diagnosis | `ablation_hrbench_failureonly_fastdry30_w3_doubao_20260523T114000Z` | 0.6000 | 0.7000 | +0.1000 | accepted 1 generated tool + 1 paired skill |
| Text-only Diagnosis | `ablation_hrbench_textonly_fastdry30_w3_doubao_20260523T114000Z` | 0.6667 | 0.6667 | 0.0000 | rejected: no visual artifact produced |
| Single-Candidate (`M=1`) | `ablation_hrbench_singlecandidate_fastdry30_w3_doubao_20260523T114000Z` | 0.5333 | 0.6000 | +0.0667 | accepted 1 generated tool + 1 paired skill |
| No Paired Mastery | `ablation_hrbench_nomastery_fastdry30_w3_doubao_20260523T114000Z` | 0.5667 | 0.5333 | -0.0333 | rejected: unpaired tool regressed |
| No Persistence | `ablation_hrbench_nopersistence_fastdry30_w3_doubao_20260523T114000Z` | 0.5667 | 0.5333 | -0.0333 | rejected before persistence mattered |

## Interpretation

The strongest usable mechanism evidence is:

- The guarded Full pilot accepted a real generated tool and improved the
  target HRBench-cross family from 0.5000 to 0.8125.
- Text-only diagnosis failed to produce a usable visual artifact.
- No Paired Mastery passed smoke validation but regressed at subset scale,
  supporting the need for the paired when-to-use gate.

Two rows should stay modest in the paper:

- Failure-Only Diagnosis improved on this narrow subset, so it should not be
  used to claim correct cases are always necessary.
- No Persistence did not isolate persistence because the candidate itself
  regressed before discard behavior mattered.

## Omitted run

`ablation_hrbench_full_fastdry30_w3_doubao_20260523T130500Z` was launched to
obtain a same-worker Full control, but it hit sustained Doubao 429005 / TPM
rate-limit errors during candidate evaluation after smoke validation. The
partial artifact and 128 MB log were removed, and the row is not reported.
