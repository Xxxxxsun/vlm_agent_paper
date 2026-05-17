# Handover: Qwen2.5-VL Skill/Zoom Tool Evaluation, 2026-05-17

## Goal

Evaluate Qwen2.5-VL on V* and HRBench4K with the base model only, then add a prompt skill plus an external zoom tool to improve small-detail performance without changing model weights.

Primary target from the discussion was Qwen2.5-VL-7B reaching roughly 85 on V*. After the focus skill and tool parser were hardened, 7B reached 85.86 on V* using the local exact/answer-text evaluator, and the same setup was then run on HRBench4K plus Qwen2.5-VL-3B and 32B.

Final comparison table after the later baseline backfill is in `docs/final_table_20260517.md`.

## Repositories and Remotes

- Main work repo: `/root/training-v2`
- Remote: `https://github.com/VTool-R1/training-v2.git`
- DeepEyes repo used for local judging utilities: `/root/DeepEyes`
- Remote: `https://github.com/Visual-Agent/DeepEyes.git`

`gh` is not installed on this machine, so automatic draft PR creation through the GitHub CLI is unavailable. Plain `git push` can still work if network and HTTPS credentials are available.

## Main Files

- `eval/eval_vstar_hrbench_agent_tool.py`
  - Standalone evaluator for V* and HRBench4K.
  - Supports `baseline`, `skill_tool`, `selective_skill_tool`, and `focus_skill_tool`.
  - Implements the zoom tool locally and sends the model a follow-up multimodal message with:
    - overview image with marked region
    - wider context crop
    - magnified detail crop
  - Redacts image payloads in saved JSONL records.
  - Hardened tool-call parsing for Qwen outputs:
    - `<tool_call>...</tool_call>` JSON
    - loose JSON or list payloads
    - bare `[x1, y1, x2, y2]`
    - `{"action": "image_zoom_in_tool", "coordinate": [x, y], "scale": ...}`
    - normalized coordinate spaces
  - Focus mode hides multiple-choice options in the first turn and forces localization before answering.

- `eval/deepeyes_tool_chat_template.jinja`
  - Qwen2.5-VL chat template for tool-style prompts.

- `scripts/run_qwen25vl7b_vstar_hrbench_agent_eval_managed.sh`
  - Managed runner for vLLM serve, evaluation, optional judging, and GPU filler restore.
  - Supports 3B/7B/32B by overriding `MODEL_PATH`, `SERVED_MODEL_NAME`, `MODEL_TP_SIZE`, and GPU env vars.
  - Fixed `IDLE_FILL_GPUS=` handling: an explicitly empty value now disables idle filler instead of falling back to `4,5,6,7`.

- `/root/DeepEyes/eval/judge_result.py`
- `/root/DeepEyes/eval/judge_result_hrbench.py`
  - Local DeepEyes judge scripts patched with request timeout/retry env vars and conservative fallback on judge API failure.
  - `judge_result_hrbench.py` also fixes the HRBench path variable and adds `--test_types`, allowing HRBench4K-only judging.

## Result Directories

All raw result JSONL files and final accuracy JSON files are under:

`eval/qwen25vl7b_agent_results/`

The full directory is about 47 MB with 108 files. Largest individual files are about 4.3 MB, so they are suitable for normal Git storage.

Important final runs:

- 7B baseline:
  - `qwen25vl7b_baseline_full2_20260517_055545`
- 7B final focus V*:
  - `qwen25vl7b_focus_skill_zoom_vstar_focus_full2_fused_20260517_102040`
- 7B final focus HRBench4K:
  - `qwen25vl7b_focus_skill_zoom_hrbench4k_focus_full_20260517_103534`
- 3B final focus:
  - `qwen25vl3b_focus_skill_zoom_3b_focus_parser_full_20260517_124733`
- 3B baseline HRBench4K:
  - `qwen25vl3b_baseline_3b_baseline_hrbench4k_20260517_192248`
- 32B baseline:
  - `qwen25vl32b_baseline_32b_baseline_full_20260517_185927`
- 32B final focus:
  - `qwen25vl32b_focus_skill_zoom_32b_focus_parser_full_20260517_131846`

Diagnostic/smoke runs are also kept in the same result directory, including the early failed 3B run where the model produced tool-like text but the parser did not execute the tool.

## Reported DeepEyes Reference Values

From the DeepEyes paper PDF checked during the session:

- Qwen2.5-VL-7B V*: 71.2 overall
- Qwen2.5-VL-7B HRBench4K: 68.8 overall
- PDF: `https://openreview.net/pdf/866137764df3dc9a9e356c2eb50ff7efeb65938d.pdf`

These are reference numbers only. The official DeepEyes evaluation loop was not used directly because its loop did not match the local agent/tool flow cleanly.

## Final Metrics

| Model | Mode | V* direct | V* relative | V* overall | HRBench4K single | HRBench4K cross | HRBench4K overall | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen2.5-VL-7B | DeepEyes paper | - | - | 71.2 | - | - | 68.8 | Reference only |
| Qwen2.5-VL-7B | Local baseline | 80.87 | 76.32 | 79.06 | 86.50 | 54.50 | 70.50 | `qwen25vl7b_baseline_full2_20260517_055545` |
| Qwen2.5-VL-7B | Early skill/tool | 65.22 | 72.37 | 68.06 | 77.25 | 57.00 | 67.12 | Tool prompt existed but parser/behavior was weak |
| Qwen2.5-VL-7B | Focus skill/tool | 90.43 | 78.95 | 85.86 | 89.50 | 60.75 | 75.12 | V* from local exact/answer-text fused judge; HRBench from official judge |
| Qwen2.5-VL-3B | Baseline | - | - | - | 79.00 | 48.25 | 63.62 | HRBench4K baseline only |
| Qwen2.5-VL-3B | Early focus/tool | 61.74 | 52.63 | 58.12 | - | - | - | Parser missed most tool calls |
| Qwen2.5-VL-3B | Hardened focus/tool | 86.09 | 81.58 | 84.29 | 89.50 | 51.50 | 70.50 | HRBench +6.88 vs baseline |
| Qwen2.5-VL-32B | Baseline | 80.87 | 82.89 | 81.68 | 88.75 | 62.50 | 75.62 | Official judge outputs |
| Qwen2.5-VL-32B | Hardened focus/tool | 86.96 | 90.79 | 88.48 | 92.75 | 63.25 | 78.00 | V* +6.81, HRBench +2.38 vs baseline |

Local multiple-choice HRBench checks:

- 7B focus HRBench4K: 74.00 overall
- 3B hardened focus HRBench4K: 69.00 overall
- 32B hardened focus HRBench4K: 76.50 overall

## Tool Execution Notes

The final hardened parser made a large difference. Before hardening, 3B often emitted tool intent without a parseable call, so the tool was not executed. After hardening:

- 3B V* direct: 113 success, 2 tool retries
- 3B V* relative: 75 success, 1 tool retry
- 3B HRBench4K: 796 success, 4 tool retries
- 32B V* direct: 115 success
- 32B V* relative: 76 success
- 32B HRBench4K: 796 success, 4 tool retries
- 7B HRBench4K earlier focus run: 219 success, 581 tool retries before the final parser hardening

The 7B V* focus result above is from the fused/local evaluator because the remote judge was unavailable during that step.

## Commands Used

Final 3B run:

```bash
STAMP=3b_focus_parser_full_$(date +%Y%m%d_%H%M%S); RUN_STAMP=$STAMP FOCUS_RUN_NAME=qwen25vl3b_focus_skill_zoom_$STAMP MODEL_PATH=/root/Qwen2.5-VL-3B-Instruct SERVED_MODEL_NAME=qwen25vl3b_agent_eval MODEL_TP_SIZE=4 EVAL_GPUS=0,1,2,3 IDLE_FILL_GPUS=4,5,6,7 MODEL_GPU_UTIL=0.70 RUN_BASELINE=0 RUN_SKILL_TOOL=0 RUN_SELECTIVE=0 RUN_FOCUS=1 RUN_VSTAR=1 RUN_HRBENCH=1 RUN_JUDGE=1 NUM_WORKERS=8 REFILL_GPU_AFTER=1 OPENAI_JUDGE_TIMEOUT=30 OPENAI_JUDGE_MAX_RETRIES=1 /root/training-v2/scripts/run_qwen25vl7b_vstar_hrbench_agent_eval_managed.sh
```

Final 32B run:

```bash
STAMP=32b_focus_parser_full_$(date +%Y%m%d_%H%M%S); RUN_STAMP=$STAMP FOCUS_RUN_NAME=qwen25vl32b_focus_skill_zoom_$STAMP MODEL_PATH=/root/Qwen2.5-VL-32B-Instruct SERVED_MODEL_NAME=qwen25vl32b_agent_eval MODEL_TP_SIZE=8 EVAL_GPUS=0,1,2,3,4,5,6,7 IDLE_FILL_GPUS= MODEL_GPU_UTIL=0.80 RUN_BASELINE=0 RUN_SKILL_TOOL=0 RUN_SELECTIVE=0 RUN_FOCUS=1 RUN_VSTAR=1 RUN_HRBENCH=1 RUN_JUDGE=1 NUM_WORKERS=8 REFILL_GPU_AFTER=1 OPENAI_JUDGE_TIMEOUT=30 OPENAI_JUDGE_MAX_RETRIES=1 /root/training-v2/scripts/run_qwen25vl7b_vstar_hrbench_agent_eval_managed.sh
```

After the script fix, `IDLE_FILL_GPUS=` is safe for full 8-GPU model serving.

## Current GPU State

After the final run, the all-card filler was restored:

```text
/usr/bin/python /root/gpu_fill.py --devices all --mem-fraction 0.70 --reserve-gb 10 --matrix-size 4096
```

`nvidia-smi` showed all GPUs filled and active again after the evaluation.

## Caveats

- The remote judge endpoint produced intermittent 502 errors. The patched judge scripts use timeout, retry, and conservative `0` fallback so judging completes instead of hanging.
- The 7B V* 85.86 number is not from the official LLM judge run; it is the local fused exact/answer-text score. HRBench4K 7B, 3B, and 32B numbers listed as official came from the judge output JSONs.
- The 3B V* baseline was not run. The requested 3B baseline backfill was HRBench4K only.
- The focused skill is very aggressive: it forces one zoom before answering. That helps V* and HRBench4K but may be wasteful for easy examples.
- The result folder name still says `qwen25vl7b_agent_results` even though it contains 3B and 32B runs. It was kept to avoid moving already-generated artifacts.

## Suggested Next Steps

1. Re-run 7B V* focus with the hardened parser and a working official judge endpoint so the 85+ result has an official judge number.
2. Add a small unit test for tool-call parsing variants in `eval_vstar_hrbench_agent_tool.py`.
3. If this workflow becomes the main evaluation path, rename the result root to a model-neutral name and keep `qwen25vl7b_agent_results` as a legacy artifact folder.
