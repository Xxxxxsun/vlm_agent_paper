# Ablation Experiment Plan (2026-05-23, rev. 2)

Sequenced plan for completing the Mechanism Ablations section
(`sections/A_appendix.tex` Section B). Revised after the execution agent's
review (`docs/ABLATION_PLAN_REVIEW_20260523.md`) which caught two failure modes
in the original plan; both are addressed below before any expensive run.

## Background: why the 2026-05-22 reruns failed

The 2026-05-22 audit (`docs/ABLATION_RUN_STATUS_20260522.md`) ran six mechanism
interventions on a 25-case HRBench subset. Four of them (Full rerun,
Failure-Only Diagnosis, Text-only Diagnosis, No Persistence) **promoted no
capability** because the no-capability adaptive solver was already at 23/25 on
that subset. Two (Single-Candidate, No Paired Mastery) accepted a **skill-only
fallback**, which means the accepted bundle had zero generated tools and did
not instantiate the intended mechanism removal at all.

Both root causes are protocol/code issues, not bad luck, and the revised plan
addresses each explicitly:

1. The evolution subset must be large enough to leave a non-trivial gap
   between the no-capability baseline and the Full configuration. The
   review agent showed that "20% of `train.jsonl`" is only 20 cases locally
   and would have repeated the saturation failure. The fix is to match
   Experiment I's protocol exactly (`evolve_split = val`, `train_subset_size
   = 700`, `held_out_split = val`).
2. The Generator allows a skill-only fallback when the proposed tool fails its
   origin check. For Single-Candidate and No Paired Mastery this fallback
   silently bypasses the ablation. The fix is two new flags
   (`--require-generated-tool-candidate`, `--forbid-skill-only-fallback`) plus
   three summary fields (`accepted_tool_count`, `accepted_skill_count`,
   `is_fallback`) so that the run produces auditable evidence.

These two fixes are P0 prerequisites. **Do not launch the HRBench mechanism
grid until both are in place and a dry-run confirms `accepted_tool_count > 0`.**

## Priority 0: protocol pin + code guard + dry-run

Before any expensive run, do the following in order.

### P0.1 Pin the HRBench protocol

The 2026-05-22 audit used a 25-case subset and failed. The local
`datasets/structured_multibench/hrbench/train.jsonl` has only 100 cases, so a
literal "20% of train" would be 20 cases and would fail again.

**Decision: use Option A from the review agent.** Match Experiment I exactly:

- `evolve_split = val`
- `train_subset_size = 700`
- `held_out_split = val`
- `normalized_data_root = datasets/structured_multibench`
- backbone: Doubao-Seed-2.0-Pro via Alibaba chat API
- credential quota: `00da3781-1f9d-4a63-857e-7c045c460290` (the one that
  worked in the 2026-05-22 audit)
- iterations: $N{=}3$

This makes every mechanism row directly comparable to the existing Doubao
HRBench Experiment I artifacts:

- `exp1r1_doubao_hrbench_skilltool_20260519T140901Z_doubao_sourceplus2_w64`
- `exp1r1_doubao_hrbench_toolonly_20260519T140901Z_doubao_sourceplus2_w64`
- `exp1r1_doubao_hrbench_skillonly_20260519T140901Z_doubao_sourceplus2_w64`

Trade-off: this is in-distribution replay rather than fully held-out
generalisation. We accept the trade-off because the existing main-table
Doubao HRBench numbers also use this protocol, and the mechanism removal
question only requires consistent comparison across variants. If a cleaner
held-out story is needed later, re-run with Option B/C (see review note);
do not block this submission on that.

### P0.2 Patch the experiment code with two tool-enforcement guards

The experiment CLI already exposes the per-mechanism flags:

- `--failure-only-diagnosis`
- `--force-text-only-analysis`
- `--disable-capability-persistence`
- `--mastery-candidate-limit`
- `--disable-paired-mastery-skill`
- `--tool-preference require_tools`

But it does not yet enforce the two acceptance criteria below. Add them
before launching the grid:

| Flag | Behaviour |
| --- | --- |
| `--require-generated-tool-candidate` | A bundle is only eligible for promotion if it contains at least one generated tool. Skill-only bundles are rejected. |
| `--forbid-skill-only-fallback` | Disables the code path that converts a failed tool-candidate attempt into a skill-only accepted bundle. |

Add three summary fields per artifact so we can audit the result without
re-loading the JSONL:

- `accepted_tool_count`: number of generated tools in the promoted bundle.
- `accepted_skill_count`: number of skills in the promoted bundle.
- `is_fallback`: boolean, true if the accepted bundle came from the
  skill-only fallback path (irrelevant if `--forbid-skill-only-fallback` is
  set, but recorded for auditing).

Without these guards, Single-Candidate and No Paired Mastery will again
silently produce skill-only artifacts and the table will look complete while
not answering the ablation question.

### P0.3 Tool-guard dry-run

Run one HRBench dry-run to confirm the guards work and the protocol promotes
at least one generated tool:

```bash
python scripts/run_structured_experiment.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id ablation_hrbench_toolguard_dryrun_doubao_20260523T<HHMMSS>Z \
  --evolve-split val \
  --held-out-split val \
  --train-subset-size 700 \
  --held-out-limit 0 \
  --max-planning-rounds 3 \
  --max-attempts 5 \
  --tool-preference require_tools \
  --require-generated-tool-candidate \
  --forbid-skill-only-fallback \
  --settings agent_train_adaptive
```

Accept the dry-run only if the summary shows `accepted_tool_count > 0`. Only
then continue to Priority 1.

## Priority 1: HRBench mechanism rerun (5 new variants + 2 reused)

After P0 passes, build a single seven-row HRBench mechanism table.

| # | Variant | Run plan | CLI flags (in addition to the P0.1 protocol) |
| -:| --- | --- | --- |
| 1 | Full (reference) | reuse the existing Doubao Full HRBench artifact; do not rerun | --- |
| 2 | Generic Skill | reuse `ablate_hrbench_generic_skillonly_fc_doubao_20260520T074011Z` | --- |
| 3 | Failure-Only Diagnosis | new run on the P0.1 protocol | `--failure-only-diagnosis --require-generated-tool-candidate --forbid-skill-only-fallback` |
| 4 | Text-only Diagnosis | new run on the P0.1 protocol | `--force-text-only-analysis --require-generated-tool-candidate --forbid-skill-only-fallback` |
| 5 | Single-Candidate ($M{=}1$) | new run on the P0.1 protocol | `--mastery-candidate-limit 1 --tool-preference require_tools --require-generated-tool-candidate --forbid-skill-only-fallback` |
| 6 | No Paired Mastery Skill | new run on the P0.1 protocol | `--disable-paired-mastery-skill --tool-preference require_tools --require-generated-tool-candidate --forbid-skill-only-fallback` |
| 7 | No Persistence | new run on the P0.1 protocol | `--disable-capability-persistence`; record whether any candidate would have been promoted before discard |

Artifact tag template:
`ablation_hrbench_<variant>_doubao_20260523T<HHMMSS>Z`.

If a variant still promotes no generated tool after P0, report that in the
table caption explicitly. Do not fill the cell with held-out accuracy from a
skill-only or empty library and present it as a mechanism comparison.

## Priority 2: ChartQA mechanism table (3 rows)

Minimum set to give the appendix a procedural-benchmark counterpart to the
HRBench probe.

| # | Variant | Why |
| -:| --- | --- |
| 1 | Full ChartQA Doubao | establishes the ChartQA gain ceiling under the working endpoint |
| 2 | Generic Skill ChartQA | tests whether the gain is just prompt engineering on a cognitive benchmark |
| 3 | Single-Candidate ChartQA ($M{=}1$) | tests the multi-candidate $\arg\max$ on a procedural benchmark |

Protocol:

- Backbone: Doubao-Seed-2.0-Pro (the Routify GPT-5.4 endpoint was still 401
  on 2026-05-22; do not block on it).
- Iterations: $N{=}3$.
- Split sizes: **`[VERIFY]` the ChartQA test-split size before launching.**
  The local `datasets/structured_chartqa_hf_safe/chartqa/val.jsonl` has 1,920
  cases, but the paper currently claims a 2,500-question test split (which
  may also be wrong; V$^\star$ was already off by a factor of ~2.6 before
  the 2026-05-23 fix). Confirm against Masry et al. 2022 Table 2 / the HF
  dataset card before adding any ChartQA numbers to the paper.
- Same code guards as Priority 1 (require generated tool for the
  Single-Candidate row).
- Artifact tags: `ablation_chartqa_<variant>_doubao_20260524T<HHMMSS>Z`.

Acceptance criterion: the Full ChartQA row must be at least one accuracy
point above the No-Capability baseline. If not, the endpoint or the
ChartQA-specific evolution protocol is the bottleneck and the table should
not ship without further investigation.

## Priority 3: Sensitivity sweep (Appendix Figure)

Replace the placeholder `\fbox` in Appendix B (Figure `fig:k_sensitivity`).

- $k$ sweep at $N{=}3$: $k \in \{5\%, 10\%, 20\%, 40\%\}$ of the ChartQA
  training split.
- $N$ sweep at $k{=}20\%$: $N \in \{1, 3, 5\}$.
- Two-panel figure: left $k$ sweep, right $N$ sweep.
- ChartQA test accuracy under the Full configuration on the Doubao endpoint.
- Artifact tags:
  `sensitivity_chartqa_k<pct>_doubao_20260525T<HHMMSS>Z` and
  `sensitivity_chartqa_N<int>_doubao_20260525T<HHMMSS>Z`.

This only fires after Priority 2 confirms the Doubao ChartQA endpoint
produces a real Full gain.

## Priority 4 (optional): MathVista No Paired Mastery cell

The HRBench appendix prose currently cites MathVista as the "cautionary
case" for naive tool exposure, but we have no MathVista mechanism evidence.
If schedule allows, add one MathVista row: No Paired Mastery vs Full on the
same Doubao protocol, with the P0 code guards. Skip otherwise.

Artifact tag: `ablation_mathvista_no_paired_mastery_doubao_20260526T<HHMMSS>Z`.

## Writing cleanup that does not need new runs

These three items can ship before any of the runs complete and are
independent of the protocol/code work above.

1. `sections/A_appendix.tex`, `tab:hyperparams`. The rows `k = 200`,
   `Mastery sample = 50`, and `Regression buffer = 20` no longer match the
   current method:
   - replace `k = 200` with "20% of training split per benchmark" (and an
     HRBench-specific note that mechanism ablations use the
     Experiment-I-matched 700-case `val` evolve split per P0.1);
   - drop the `Mastery sample` row (mastery is now the paired skill,
     emitted by the Generator when action is `both`);
   - drop the `Regression buffer` row (the multi-candidate selection rule
     in Eq.~\ref{eq:selection} subsumes the regression check).
2. In each ablation subsection that has only "What is removed" and "What
   this rules out", add an explicit `\paragraph{Observed pattern.}` block.
   For rows we will not have data for at submission time, write
   "data pending; see Appendix release table" rather than letting "expected
   pattern" sentences look like assertions.
3. The commented-out alternate `tab:evolution_full` block in
   `sections/4_experiments.tex` still uses `Skill + Tool` labels. Replace
   with `Full` so the commented block is consistent if it is ever
   uncommented.

## V$^\star$ mechanism ablation

Not in this plan. The 2026-05-22 V$^\star$ pilots accepted zero capabilities
even with a working endpoint, which suggests the V$^\star$ training subset is
the wrong unit for mechanism removal. We cite the Experiment I V$^\star$
numbers in the main paper and leave V$^\star$ mechanism ablation as future
work.

## Recommended execution order

1. **P0.1**: pin the HRBench protocol to Option A (evolve_split=val,
   train_subset_size=700).
2. **P0.2**: patch the experiment code with the two tool-enforcement guards
   and three summary fields.
3. **P0.3**: run the tool-guard HRBench dry-run; only continue if
   `accepted_tool_count > 0`.
4. **P1**: launch the five HRBench mechanism variants (Failure-Only,
   Text-only, Single-Candidate, No Paired Mastery, No Persistence) in
   parallel.
5. **P2**: verify the ChartQA test-split size, then launch the three
   ChartQA mechanism rows.
6. **P3**: sensitivity sweep, after P2's Full row confirms a real ChartQA
   gain.
7. **P4** (optional): MathVista No-Paired-Mastery cell.
8. Apply the three writing-cleanup items in parallel with the runs.

## What this plan does NOT cover

- V$^\star$ mechanism ablation (see V$^\star$ section above).
- Cross-backbone mechanism robustness checks (GPT-4o, o4-mini, GPT-5.4) on
  the HRBench mechanism grid. The Doubao protocol is the only endpoint that
  has reliably promoted tools recently; add cross-backbone checks only after
  the Doubao mechanism table is published in the appendix.
- The `Optional Validation and Regression Filter` ablation that lived in
  the appendix before the method rewrite. It was removed when multi-candidate
  selection subsumed the origin and regression checks; it does not return in
  this plan.
