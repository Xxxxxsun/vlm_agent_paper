# Ablation Plan Review (2026-05-23)

This note reviews `docs/ABLATION_EXPERIMENT_PLAN_20260523.md` after pulling the
latest paper repo. The plan is directionally correct: the current appendix should not
pretend that the 2026-05-22 25-case audit is a complete mechanism ablation, and a
cleaner HRBench rerun is the right next target. However, two protocol/code issues need
to be fixed before launching expensive runs.

## Summary Judgment

The proposed priority order is sound:

1. Rebuild the HRBench mechanism table with a protocol that can actually promote tools.
2. Add a small ChartQA mechanism table if the Doubao endpoint produces a real Full gain.
3. Replace the placeholder sensitivity figure only after the core mechanism rows are stable.
4. Treat MathVista as optional.

The main change I recommend is to insert a short engineering/protocol checkpoint before
Priority 1. Running the plan exactly as written risks repeating the 2026-05-22 failure
mode: empty libraries, skill-only fallbacks, and no interpretable No-Mastery or
Single-Candidate row.

## Issue 1: HRBench "20% Training Split" Is Ambiguous Locally

The plan says to use "the 20% HRBench training split used by Experiment I." In the current
experiment repo, the normalized HRBench files are:

- `datasets/structured_multibench/hrbench/train.jsonl`: 100 cases
- `datasets/structured_multibench/hrbench/val.jsonl`: 700 cases

If we literally take 20% of `train.jsonl`, the evolution subset is only 20 cases, which is
smaller than the 25-case 2026-05-22 audit. That will not solve the saturation problem.

The existing Doubao HRBench Experiment I artifacts instead report:

- `evolve_split = val`
- `train_subset_size = 700`
- `held_out_split = val`
- `normalized_data_root = datasets/structured_multibench`

Example artifacts:

- `exp1r1_doubao_hrbench_skilltool_20260519T140901Z_doubao_sourceplus2_w64`
- `exp1r1_doubao_hrbench_toolonly_20260519T140901Z_doubao_sourceplus2_w64`
- `exp1r1_doubao_hrbench_skillonly_20260519T140901Z_doubao_sourceplus2_w64`

Before running Priority 1, choose one explicit HRBench protocol:

| Option | Protocol | Pros | Risk |
| --- | --- | --- | --- |
| A | Match Exp I exactly: `evolve_split=val`, `train_subset_size=700`, validate on the same 700-case HRBench set | Directly comparable to existing main-table artifacts | It is closer to full-set replay than held-out validation |
| B | Use `train.jsonl` but increase beyond 20%, e.g. all 100 train cases, validate on 700 val cases | Cleaner train/val separation | May still be too small to promote robust generated tools |
| C | Regenerate a larger official HRBench train split from raw data, then use 20% | Best long-term protocol | Requires data-prep work before ablation runs |

My recommendation is Option A for paper deadline pragmatism, because the current main
HRBench numbers already use that protocol. If we want a cleaner split story, choose Option B
but do a dry-run first and only continue if it promotes a generated tool.

## Issue 2: Single-Candidate and No-Mastery Need Stronger Code Guards

The 2026-05-22 audit showed that `Single-Candidate` and `No Paired Mastery` both accepted a
skill-only fallback. That means they did not test the intended mechanisms:

- Single-Candidate should test whether one generated proposal is enough, not whether a
  no-tool skill can be promoted.
- No Paired Mastery should test generated tool exposure without its paired applicability
  skill, not another skill-only fallback.

The current experiment CLI already has useful flags:

- `--failure-only-diagnosis`
- `--force-text-only-analysis`
- `--disable-capability-persistence`
- `--mastery-candidate-limit`
- `--disable-paired-mastery-skill`
- `--tool-preference require_tools`
- `--case-offset` / `--case-limit` for sharded frozen evaluation

But it does not yet enforce the two strongest acceptance criteria in the new plan:

- "do not fall back to skill-only when the single candidate fails the origin check"
- "No Paired Mastery must still accept the generated tool"

Before launching the expensive HRBench rerun, add explicit safeguards such as:

- `--require-generated-tool-candidate`: reject/promote nothing unless the accepted bundle
  contains at least one generated tool.
- `--forbid-skill-only-fallback`: disable the fallback path that converts a failed tool
  attempt into a skill-only accepted bundle.
- Summary fields that record `accepted_tool_count`, `accepted_skill_count`, and whether the
  accepted bundle was fallback-derived.

Without these guards, the new run can produce numbers that look complete but do not answer
the ablation question.

## Recommended Execution Checkpoint

Before launching all five HRBench variants:

1. Patch the experiment code with the two tool-enforcement guards above.
2. Run a small HRBench dry-run with `--tool-preference require_tools` and the selected
   protocol.
3. Continue only if at least one generated tool is promoted and the summary confirms
   `accepted_tool_count > 0`.

Suggested dry-run target:

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

The exact `train_subset_size` should be changed if we choose Option B or C above.

## Priority 1 Revisions

After the checkpoint passes, run these HRBench variants:

| Variant | Required flags / notes |
| --- | --- |
| Failure-Only Diagnosis | `--failure-only-diagnosis`; keep the tool guards enabled if the row is meant to evaluate generated tools |
| Text-only Diagnosis | `--force-text-only-analysis`; keep the tool guards enabled |
| Single-Candidate | `--mastery-candidate-limit 1 --tool-preference require_tools --require-generated-tool-candidate --forbid-skill-only-fallback` |
| No Paired Mastery | `--disable-paired-mastery-skill --tool-preference require_tools --require-generated-tool-candidate --forbid-skill-only-fallback` |
| No Persistence | `--disable-capability-persistence`; record whether any candidate would have been accepted before discard |

If a variant still promotes no generated tool after the guard patch, report that explicitly.
Do not fill the table with held-out accuracy for an empty or skill-only library as if it were
the intended mechanism ablation.

## Priority 2 ChartQA Notes

The ChartQA plan is useful, but it is expensive:

- The safe normalized ChartQA split has 28,298 train cases and 1,920 val cases locally.
- The plan mentions a 2,500-question test split, which is not the currently visible local
  normalized file.

Before launching the three ChartQA mechanism rows, confirm the split to use:

- If using local files now: `datasets/structured_chartqa_hf_safe/chartqa/val.jsonl`
  has 1,920 cases.
- If the paper requires 2,500 test cases: prepare or locate that normalized test split first.

Also keep the acceptance criterion from the plan: if Full is not at least one point above
No-Capability, do not add the ChartQA mechanism table.

## Writing Cleanup

I agree with the three writing cleanup items in the plan:

1. Update `tab:hyperparams`; the current `k=200`, `Mastery sample=50`, and
   `Regression buffer=20` rows are stale.
2. Add `Observed pattern` paragraphs to ablation subsections, marking rows as pending or
   artifact-backed.
3. Replace stale "Skill + Tool" labels in commented-out tables with "Full" for consistency.

These can be done immediately and do not depend on new experiments.

## Recommended Next Step

Do not launch the full Priority 1 grid yet. First:

1. Decide HRBench protocol Option A, B, or C.
2. Patch the experiment code to enforce generated-tool acceptance for the relevant ablations.
3. Run one tool-guard dry-run.
4. Only then launch the HRBench mechanism grid.

This keeps the ablation section honest and prevents another expensive run whose accepted
capabilities do not instantiate the mechanism being tested.
