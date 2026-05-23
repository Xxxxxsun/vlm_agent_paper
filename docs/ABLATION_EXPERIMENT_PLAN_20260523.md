# Ablation Experiment Plan (2026-05-23)

Plan for filling the gaps in `sections/A_appendix.tex` Mechanism Ablations
(Section B). Sequenced by paper-impact / risk; each run lists the variant, what
it isolates, the protocol fix needed, and an artifact-tag suggestion so the
written prose can cite a concrete record.

## Background: why the previous reruns failed

The 2026-05-22 audit (`docs/ABLATION_RUN_STATUS_20260522.md`) showed that a
25-case HRBench training subset is **already near-saturated** by the
no-capability adaptive solver (23/25 correct), which left four mechanism
interventions (Full rerun, Failure-Only, Text-only, No Persistence) with **no
promoted capability** to evaluate. Single-Candidate and No Paired Mastery did
promote skill-only fallbacks but those bundles never instantiated the intended
"tool without paired mastery" or "single tool candidate" condition. The matched
ChartQA o4-mini pilot and the V* o4-mini pilots are also currently unusable.

Take-away for this plan: the training subset must be **large enough to leave a
non-trivial gap between the no-capability baseline and the tool-enabled Full
configuration** for any mechanism removal to be measurable. Use the same 20% of
the official training split that Experiments I uses; pin the working
Doubao-Seed-2.0-Pro credential (quota `00da3781-1f9d-4a63-857e-7c045c460290`).

## Priority 1: HRBench mechanism rerun (the five missing rows)

Goal: produce a single HRBench table where the six planned ablations are run
with the same protocol so that the deltas to Full are interpretable.

| # | Variant | Mechanism removed | Required intervention |
| -:| --- | --- | --- |
| 1 | Full (reference) | none | replay the Full Doubao HRBench training run that already exists; cite it instead of rerunning |
| 2 | Generic Skill | evolved library $\to$ neutral task prompt | reuse the existing `ablate_hrbench_generic_skillonly_*` artifact, already in Table 6 |
| 3 | Failure-Only Diagnosis | AnalyzerDecider sees only incorrect cases | new run; drop the correct-case channel in the AnalyzerDecider prompt |
| 4 | Text-only Diagnosis | AnalyzerDecider sees no images or tool artefacts | new run; strip multimodal input from AnalyzerDecider role |
| 5 | Single-Candidate ($M{=}1$) | one Generator proposal, no $\arg\max$ | new run; set `candidates_per_iter = 1`; do **not** fall back to skill-only when the single candidate fails the origin check |
| 6 | No Paired Mastery Skill | tool without paired skill | new run; when action is `both`, drop the paired skill, but **still accept the generated tool**; this requires removing the "skill-only fallback" path that currently masked the comparison |
| 7 | No Persistence | capabilities not stored across cases | new run; reset $\mathcal{C}$ to empty between cases so retrieval is per-case only |

Protocol for runs 3-7:

- Backbone: Doubao-Seed-2.0-Pro via Alibaba chat API (use the working quota
  above).
- Training subset: **the 20% HRBench training split used by Experiment I**, not
  the 25-case audit subset. This is the change that prevents saturation.
- Iterations: $N{=}3$.
- Multi-candidate $M$: matches the Full Experiment I setting (record the value
  used).
- Validation: full 700-case HRBench validation set, identical to the existing
  Doubao Full and Tool-Only artifacts.
- Artifact tags: `ablation_hrbench_<variant>_doubao_20260523T<HHMMSS>Z`.

Acceptance criteria for each run:

- A non-empty capability library is promoted for at least the Full and
  No-Persistence variants. If a variant still produces an empty library, that
  becomes evidence rather than a bug, but the prose must say so explicitly.
- For Single-Candidate and No Paired Mastery, the run must accept at least one
  candidate with a generated tool (otherwise the comparison reduces to a
  no-tool baseline and does not test the intended mechanism). If the skill-only
  fallback path triggers, disable it.

## Priority 2: ChartQA mechanism table (3 core rows)

The current appendix has no ChartQA mechanism evidence. Reviewers will ask
whether the HRBench picture transfers to a cognitive / procedural benchmark.

Minimum set:

| # | Variant | Why this row |
| -:| --- | --- |
| 1 | Full ChartQA Doubao | establishes the ChartQA gain ceiling under the working endpoint |
| 2 | Generic Skill ChartQA | parallels the HRBench Generic Skill row; tests whether the cognitive gain is just prompt engineering |
| 3 | Single-Candidate ChartQA ($M{=}1$) | tests the multi-candidate mechanism on a procedural benchmark, complementing the HRBench rerun |

Protocol:

- Backbone: Doubao-Seed-2.0-Pro (or any endpoint that completes ChartQA
  evolution under the current method — the Routify GPT-5.4 endpoint is still
  failing 401 per the 2026-05-22 audit).
- Training subset: 20% of the official ChartQA training split.
- Iterations: $N{=}3$.
- Validation: ChartQA test split (2,500 questions), relaxed accuracy with 5%
  tolerance.
- Artifact tags: `ablation_chartqa_<variant>_doubao_20260524T<HHMMSS>Z`.

Acceptance criterion: the Full row must be at least one accuracy point above
the No-Capability baseline. If not, the ChartQA endpoint is the bottleneck and
the rerun should be retried before adding the table to the paper.

## Priority 3: Sensitivity sweep (Appendix Figure)

The current Figure (`fig:k_sensitivity`) is an empty `\fbox`. Replace with a
real curve.

- Sweep $k \in \{5\%, 10\%, 20\%, 40\%\}$ of the ChartQA training split at
  $N{=}3$.
- Sweep $N \in \{1, 3, 5\}$ at $k{=}20\%$.
- Two-panel figure: left panel $k$ sweep, right panel $N$ sweep. Both report
  ChartQA test accuracy under the Full configuration.
- Artifact tags:
  `sensitivity_chartqa_k<pct>_<doubao|gpt54>_20260525T<HHMMSS>Z` and
  `sensitivity_chartqa_N<int>_<doubao|gpt54>_20260525T<HHMMSS>Z`.

## Priority 4 (optional): MathVista mechanism cell

The HRBench probe motivates the No Paired Mastery row using MathVista as the
"cautionary case." We do not yet have MathVista evidence for that claim. If
time allows, add a single No Paired Mastery vs Full row on MathVista with the
same Doubao protocol to substantiate the prose. Skip otherwise.

## Writing cleanup that does not need new runs

These items can ship before the runs complete:

1. Update `sections/A_appendix.tex` Table `tab:hyperparams`. The rows
   `k = 200`, `Mastery sample = 50`, and `Regression buffer = 20` no longer
   match the current method. Replace `k` with "20% of training split per
   benchmark", drop the mastery-sample and regression-buffer rows (mastery is
   now the paired skill, and the multi-candidate selection rule subsumes the
   regression check).
2. In each ablation subsection that currently lists "What is removed" and
   "What this rules out", add an explicit `\paragraph{Observed pattern.}`
   block that either cites the artifact or marks the row as pending. This
   makes the appendix self-contained and prevents stale "expected pattern"
   sentences from looking like assertions.
3. Replace "Skill + Tool" leftovers in any commented-out tables with "Full"
   for consistency (already done in the active tables, but the commented
   alternates in `sections/4_experiments.tex` still have the old label).

## Suggested execution order

1. Pin the Doubao quota and dry-run a single Failure-Only Diagnosis variant on
   the full 20% HRBench training subset. Confirm a non-empty capability library
   is promoted before launching the other four HRBench runs.
2. Launch HRBench runs 3-7 in parallel once the dry-run succeeds.
3. While those finish, launch the three ChartQA mechanism runs.
4. Two days after, launch the sensitivity sweep (cheaper, can use whatever
   capacity is left).
5. Optional MathVista run if there is room in the budget.
6. Apply the three writing cleanup items in parallel; they do not depend on
   the runs.

## What this plan does NOT cover

- The V* mechanism table is not in the plan. The 2026-05-22 V* pilot showed
  zero accepted capabilities even with the working endpoint, which suggests
  the V* training subset is the wrong unit for mechanism removal. We will
  cite the Experiment I V* numbers in the main paper and leave V* mechanism
  ablation as future work.
- The Validation/Regression-Filter ablation (previously in the appendix as
  "Optional") was removed when the method changed to multi-candidate
  selection. It does not return in this plan.
