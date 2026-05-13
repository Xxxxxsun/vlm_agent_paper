# Adaptive-CoF positioning notes

This note records which numbers are copied from the Adaptive-CoF paper and which
entries are placeholders for our own follow-up run.

Source: arXiv:2505.15436, "Adaptive Chain-of-Focus Reasoning via Dynamic Visual
Search and Zooming for Efficient VLMs".

## Reported Adaptive-CoF data

The paper uses Qwen2.5-VL-7B as the base model and trains an adaptive
search/zoom policy through:

- 5K MM-Adaptive-CoF SFT visual-search trajectories.
- 10K MM-Adaptive-CoF RL samples with adaptive group-aware reward.

Reported overall scores:

| Method | V* overall | MME-RealWorld-Lite overall | Update |
| --- | ---: | ---: | --- |
| Qwen2.5-VL-7B base | 71.2 | 42.3 | none |
| Adaptive-CoF cold-start | 89.5 | 50.1 | SFT |
| Adaptive-CoF | 90.1 | 50.9 | SFT+RL |

Additional reported resolution-level V* analysis:

| Resolution | Qwen2.5-VL-7B acc. | Adaptive-CoF acc. | Adaptive-CoF zoom calls |
| ---: | ---: | ---: | ---: |
| 224 | 37.70 | 39.27 | 2.50 |
| 336 | 41.36 | 43.98 | 2.05 |
| 448 | 52.88 | 53.93 | 1.65 |
| 672 | 62.30 | 60.21 | 1.03 |
| 1024 | 69.11 | 75.39 | 0.75 |
| 1920 | 79.58 | 87.96 | 0.52 |
| 2560 | 79.06 | 89.53 | 0.53 |

## Our row in the paper

The current paper table intentionally leaves the EvoAgent Qwen2.5-VL-7B
Adaptive-CoF-aligned accuracy as `TBD`. The repository does not yet contain raw
same-protocol runs for V* or MME-RealWorld-Lite under this setup. Do not turn the
placeholder into a claimed score until those runs exist.

The intended comparison is about resource profile:

- Adaptive-CoF: task-specific SFT+RL data construction and weight updates.
- EvoAgent: frozen Qwen2.5-VL-7B, failure-driven skill/tool evolution, no
  task-specific SFT/RL dataset.
