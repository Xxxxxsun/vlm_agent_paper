# Distribution Shift Adaptation Experiment

This experiment simulates a realistic non-stationary benchmark stream where the
incoming task distribution changes over time.  The goal is to show that a system
starting with HRBench-only capabilities can detect new task families and quickly
activate the corresponding hand-written skill/tool pack.

## Setup

The stream has four phases:

| Phase | Cases |
| --- | ---: |
| `warmup_hrbench` | 48 HRBench |
| `mathvista_shift` | 12 HRBench + 36 MathVista |
| `chartqa_shift` | 8 HRBench + 12 MathVista + 32 ChartQA |
| `four_way_mixed` | 8 HRBench + 12 MathVista + 12 ChartQA + 28 VStar |

The experiment is a replay over completed per-case model outputs.  This keeps
the drift/adaptation mechanism controlled and avoids mixing it with the noise
and cost of regenerating skills/tools.  The currently reported profile is:

```text
gpt54_skilltool
```

It uses direct/reasoned VLM outputs as the no-capability baseline and
function-calling skill/tool outputs as the task-specific capability pack.

## Compared Methods

| Method | Meaning |
| --- | --- |
| `direct_vlm` | No persistent skill/tool pack; direct/reasoned VLM output only. |
| `static_hrbench_only` | Starts with the HRBench pack and never adapts. |
| `online_adaptive` | Starts with HRBench, detects new benchmark families in a rolling stream window, then activates the matching pack. |
| `oracle_all_packs` | Upper bound that has all four packs from the beginning. |

The online detector uses a rolling window of 12 cases.  A new dataset triggers
adaptation after it appears 3 times in that window.  The pack is activated after
2 additional cases, simulating the latency of analyzing failures and writing the
new skill/tool.

## Main Results

Controlled capability-sensitive stream:

```bash
python scripts/run_distribution_shift_experiment.py \
  --output-id gpt54_capability_sensitive_gr040_v1
```

| Method | Accuracy |
| --- | ---: |
| `direct_vlm` | 0.490 |
| `static_hrbench_only` | 0.654 |
| `online_adaptive` | 0.889 |
| `oracle_all_packs` | 0.909 |

Stress stream, selecting cases where the relevant capability pack fixes the
direct model:

```bash
python scripts/run_distribution_shift_experiment.py \
  --protocol stress \
  --output-id gpt54_stress_v1
```

| Method | Accuracy |
| --- | ---: |
| `direct_vlm` | 0.029 |
| `static_hrbench_only` | 0.394 |
| `online_adaptive` | 0.952 |
| `oracle_all_packs` | 1.000 |

Natural fixed-seed stream:

```bash
python scripts/run_distribution_shift_experiment.py \
  --protocol natural \
  --seed 33 \
  --output-id gpt54_natural_seed33_v1
```

| Method | Accuracy |
| --- | ---: |
| `direct_vlm` | 0.692 |
| `static_hrbench_only` | 0.736 |
| `online_adaptive` | 0.832 |
| `oracle_all_packs` | 0.851 |

Kimi skill-only profile, capability-sensitive stream:

```bash
python scripts/run_distribution_shift_experiment.py \
  --model-profile kimik26_skillonly \
  --protocol capability_sensitive \
  --gain-ratio 0.4 \
  --output-id kimik26_capability_sensitive_gr040_v1
```

| Method | Accuracy |
| --- | ---: |
| `direct_vlm` | 0.495 |
| `static_hrbench_only` | 0.649 |
| `online_adaptive` | 0.861 |
| `oracle_all_packs` | 0.885 |

o4-mini best-available profile, capability-sensitive stream:

```bash
python scripts/run_distribution_shift_experiment.py \
  --model-profile o4mini_best_available \
  --protocol capability_sensitive \
  --gain-ratio 0.4 \
  --output-id o4mini_capability_sensitive_gr040_v1
```

| Method | Accuracy |
| --- | ---: |
| `direct_vlm` | 0.481 |
| `static_hrbench_only` | 0.649 |
| `online_adaptive` | 0.870 |
| `oracle_all_packs` | 0.894 |

Natural 200-seed aggregate for non-GPT-5.4 models:

```text
artifacts/distribution_shift/natural_200seed_other_models_v1/
  summary.md
  summary.json
  natural_200seed_rows.csv
```

| Model profile | Direct mean | Static mean | Adaptive mean | Oracle mean |
| --- | ---: | ---: | ---: | ---: |
| `o4mini_best_available` | 0.745 | 0.787 | 0.807 | 0.808 |
| `kimik26_skillonly` | 0.781 | 0.804 | 0.836 | 0.839 |

## Live Smoke

The replay experiment is the main result.  A small live smoke verifies that the
current VLM endpoint can execute the same adaptation loop on actual image
requests.  This run uses the Doubao Alibaba-chat backend from the saved batch
env file, disables tools to avoid backend tool-call latency, and tests the
hand-written skill packs live.

```bash
source artifacts/batch_runs/20260420T174315Z/tasks/doubao.env
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
PYTHONUNBUFFERED=1 python scripts/run_distribution_shift_live_smoke.py \
  --protocol stress \
  --cases-per-dataset 2 \
  --disable-tools \
  --prefer-no-tool-cases \
  --window-size 4 \
  --new-dataset-threshold 1 \
  --adapt-latency 0 \
  --output-id doubao_live_smoke_skillonly_fastadapt2_v2
```

| Method | Accuracy |
| --- | ---: |
| cached direct baseline | 0.125 |
| cached static HR-only | 0.375 |
| live online adaptive | 0.750 |
| live oracle all packs | 1.000 |

## Generated Artifacts

Main result:

```text
artifacts/distribution_shift/gpt54_capability_sensitive_gr040_v1/
  summary.md
  summary.json
  stream_results.jsonl
  rolling_accuracy.csv
  rolling_accuracy.svg
```

Natural sanity check:

```text
artifacts/distribution_shift/gpt54_natural_seed33_v1/
  summary.md
  summary.json
  stream_results.jsonl
  rolling_accuracy.csv
  rolling_accuracy.svg
```

Stress result:

```text
artifacts/distribution_shift/gpt54_stress_v1/
  summary.md
  summary.json
  stream_results.jsonl
  rolling_accuracy.csv
  rolling_accuracy.svg
```

Live smoke:

```text
artifacts/distribution_shift/doubao_live_smoke_skillonly_fastadapt2_v2/
  summary.md
  summary.json
  stream_results.jsonl
```

Doubao has many complete capability-pack caches, but not a complete four-benchmark
direct/reasoned baseline cache.  For that reason it is reported as a live smoke
only, not in the same replay table as GPT-5.4, Kimi, and o4-mini.

`rolling_accuracy.svg` is the figure to use for the story: accuracy is high on
the HRBench warmup, drops when new distributions arrive, and recovers after the
adaptive pack activation events.

## Interpretation

The capability-sensitive protocol is intentionally a controlled stress test: it
selects a fixed fraction of cases where the direct model fails and the matching
capability pack succeeds.  This is useful for making the adaptation mechanism
visible and reproducible.

The natural protocol is closer to ordinary random sampling.  It still shows a
clear gain, but the effect is smaller because some random cases do not require
new capabilities and some capability packs are not uniformly better than direct
reasoning on every case.
