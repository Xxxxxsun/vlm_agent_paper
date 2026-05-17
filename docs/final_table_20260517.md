# Final Table, 2026-05-17

This table uses the completed full runs available in `results/qwen25vl7b_agent_results/`.

## Overall Scores

| Model | Mode | V* direct | V* relative | V* overall | HRBench4K single | HRBench4K cross | HRBench4K overall | Delta vs baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen2.5-VL-3B | Baseline | - | - | - | 79.00 | 48.25 | 63.62 | - |
| Qwen2.5-VL-3B | Focus skill + zoom tool | 86.09 | 81.58 | 84.29 | 89.50 | 51.50 | 70.50 | HR +6.88 |
| Qwen2.5-VL-7B | Baseline | 80.87 | 76.32 | 79.06 | 86.50 | 54.50 | 70.50 | - |
| Qwen2.5-VL-7B | Focus skill + zoom tool | 90.43 | 78.95 | 85.86 | 89.50 | 60.75 | 75.12 | V* +6.80, HR +4.62 |
| Qwen2.5-VL-32B | Baseline | 80.87 | 82.89 | 81.68 | 88.75 | 62.50 | 75.62 | - |
| Qwen2.5-VL-32B | Focus skill + zoom tool | 86.96 | 90.79 | 88.48 | 92.75 | 63.25 | 78.00 | V* +6.81, HR +2.38 |

## Run Paths

| Model | Mode | Result directory |
| --- | --- | --- |
| 3B | Baseline HRBench4K | `results/qwen25vl7b_agent_results/qwen25vl3b_baseline_3b_baseline_hrbench4k_20260517_192248` |
| 3B | Focus skill + zoom tool | `results/qwen25vl7b_agent_results/qwen25vl3b_focus_skill_zoom_3b_focus_parser_full_20260517_124733` |
| 7B | Baseline | `results/qwen25vl7b_agent_results/qwen25vl7b_baseline_full2_20260517_055545` |
| 7B | Focus skill + zoom tool, V* | `results/qwen25vl7b_agent_results/qwen25vl7b_focus_skill_zoom_vstar_focus_full2_fused_20260517_102040` |
| 7B | Focus skill + zoom tool, HRBench4K | `results/qwen25vl7b_agent_results/qwen25vl7b_focus_skill_zoom_hrbench4k_focus_full_20260517_103534` |
| 32B | Baseline | `results/qwen25vl7b_agent_results/qwen25vl32b_baseline_32b_baseline_full_20260517_185927` |
| 32B | Focus skill + zoom tool | `results/qwen25vl7b_agent_results/qwen25vl32b_focus_skill_zoom_32b_focus_parser_full_20260517_131846` |

## Notes

- 3B V* baseline was not run; only the requested 3B HRBench4K baseline was added.
- 7B V* focus score is the local fused exact/answer-text score from the saved fused V* run, not a fresh official LLM judge run.
- HRBench4K values in the table are from `final_acc_hrbench4k.json`.
- 3B and 32B focus scores are from the hardened parser/tool runs.
- The judge endpoint produced intermittent timeouts; the patched judge scripts use timeout/retry and conservative failure handling, so timeout samples are counted as wrong rather than blocking completion.
