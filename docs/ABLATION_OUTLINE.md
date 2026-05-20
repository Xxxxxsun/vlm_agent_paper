# Ablation Section Outline

This document is for the agent that will rewrite Section 4 Ablation Studies.
The current ablation placeholder in `sections/4_experiments.tex` is too close to
the main Exp I table, because Exp I already reports `None`, `Skill Only`,
`Tool Only`, and `Skill + Tool`. The ablation section should instead test the
mechanisms that make the paper's method different from ordinary prompting or
naive tool use.

## Core Message

The ablation should support this claim:

> The gains come from failure-driven capability evolution: the agent visually
> diagnoses failures, generates persistent skills/tools, validates them, and
> learns when to deploy them through mastery. Removing any of these mechanisms
> either reduces improvement or makes tool use less reliable.

Do not frame the ablation as another leaderboard. It should be a mechanism
study.

## What Not To Repeat

Avoid a table whose rows are only:

- `w/o Skill Evolution`
- `w/o Tool Evolution`
- `Full`

Those rows are already covered in Table `tab:evolution_full` by `Skill Only`,
`Tool Only`, and `Skill + Tool`. If they are mentioned, refer back to Exp I
rather than rerunning the same comparison.

## Recommended Main Ablation Table

Use two representative datasets in the main paper:

- `ChartQA`: cognitive / procedural bottleneck. Useful for showing persistent
  evolved skills beat generic prompting.
- `HRBench`: perceptual / high-resolution bottleneck. Useful for showing visual
  diagnosis and mastery-gated tools matter.

If space allows, put MathVista and V* in appendix.

Suggested table:

| Variant | Removed mechanism | ChartQA | HRBench | Main diagnostic |
| --- | --- | ---: | ---: | --- |
| Full `\sysname{}` | none | TBD | TBD | failure-driven skill/tool evolution |
| Generic Skill | no failure-specific evolution | TBD | TBD | tests whether gains are just prompt engineering |
| Text-only Diagnosis | no image/artifact input to AnalyzerDecider | TBD | TBD | tests visual failure analysis |
| No Mastery | tools exposed without applicability SOP | TBD | TBD | tests selective tool deployment |
| No Persistence | reflection/capability not reused across cases | TBD | TBD | tests reusable capability library |

This table is stronger than the current placeholder because each row maps to a
specific design choice in the method section.

## Ablation 1: Generic Skill vs. Evolved Capability

### Question

Are the gains caused by failure-specific evolution, or would a generic VQA /
chart / high-resolution prompt do the same thing?

### Variants

- `Direct`: base VLM, no persistent capability.
- `Generic Skill`: a hand-neutral generic task prompt, not derived from failure
  analysis. Example: "read the chart carefully, identify relevant values, reason
  step by step"; for HRBench, "inspect local details before answering".
- `Evolved Skill/Tool`: frozen capability library produced by the evolution
  loop.

### Datasets / Models

Main: ChartQA and HRBench with one representative backbone. Prefer GPT-4o or
o4-mini if cost matters; Doubao or GPT-5.4 if you want cleaner positive deltas.

### Expected Interpretation

If Generic Skill improves slightly but Full improves more, write:

- Generic prompting captures shallow task advice.
- Evolved capabilities encode failure-specific procedures, triggers, and
  pitfalls that transfer beyond the triggering examples.
- This distinguishes the method from ordinary prompt engineering.

### Writing Hook

"Generic task instructions provide a useful but incomplete baseline: they tell
the model to be careful, but they do not identify which recurring failure modes
were observed during training or when a visual tool should be invoked."

## Ablation 2: Text-only Diagnosis

### Question

Does the AnalyzerDecider need to see images and tool artifacts, or is text-only
reflection enough?

### Variants

- `Full Diagnosis`: AnalyzerDecider receives question, wrong answer, trace,
  original image, and intermediate tool outputs.
- `Text-only Diagnosis`: AnalyzerDecider receives only question, wrong answer,
  ground truth, and trace. No original image and no generated/cropped/processed
  visual artifacts.

### Datasets / Models

Main: HRBench and V* are the best tests because visual inspection, crop quality,
and region selection are central. If only two datasets fit in the table, use
HRBench in the main table and put V* in appendix.

### Expected Interpretation

Full should outperform text-only most clearly on perceptual tasks. If text-only
works similarly on ChartQA, that is acceptable and useful: it reinforces the
cognitive/perceptual distinction.

### Writing Hook

"Text-only reflection can describe that an answer was wrong, but it cannot tell
whether a crop was misaligned, a zoomed region missed the target, or a generated
visual artifact degraded the evidence."

## Ablation 3: No Mastery / Unconditional Tool Exposure

### Question

Does progressive mastery matter, or can the agent just expose generated tools
whenever they exist?

### Variants

- `Full`: generated/provided tools are validated and gated by mastery SOPs.
- `No Mastery`: tools that pass basic validation are always exposed, or exposed
  using only coarse dataset-level rules without learned applicability boundaries.
- Optional: `All Tools Exposed`: every available tool is exposed on every case.
  This is useful if it is easy to run, but do not make the table too large.

### Datasets / Models

Main: HRBench or V* for visual tool usefulness; MathVista as a cautionary case
because earlier experiments showed naive tool exposure can hurt. If the main
table has only ChartQA/HRBench, discuss MathVista in text or appendix.

### Expected Interpretation

No Mastery may increase tool usage but reduce accuracy or increase variance.
This supports the paper's point that the method is not "generate a tool and use
it everywhere"; it learns boundaries.

### Writing Hook

"Mastery improves precision rather than simply increasing tool-use rate. The
unconditional variant often calls tools on cases where direct reasoning is
already sufficient, introducing visual artifacts or unnecessary intermediate
steps."

## Ablation 4: No Persistence / Per-case Reflection

### Question

Does storing reusable capabilities matter, or is it enough to reflect/retry on
each failed case independently?

### Variants

- `Persistent Library`: promoted skills/tools are stored and retrieved for
  future validation cases.
- `Per-case Reflection`: the agent can reflect and retry the current case, but
  does not save the generated skill/tool or failure summary for future cases.

### Datasets / Models

ChartQA is a good main test because recurring reasoning procedures should
transfer across many chart questions. HRBench can be secondary if compute
allows.

### Expected Interpretation

Persistence should matter when failures form reusable families. If per-case
reflection helps the triggering case but not held-out cases, that is exactly the
story.

### Writing Hook

"The goal of evolution is not to repair a single failed attempt, but to convert
that failure into a capability that future cases can retrieve."

## Optional Ablation 5: Validation / Regression Filter

### Question

Does the origin + regression validation pipeline prevent overfitted or harmful
tools from being promoted?

### Variants

- `Full Validation`: syntax check, origin-case improvement, regression buffer,
  then mastery.
- `Origin-only`: accept a tool if it fixes the triggering case.
- `No Regression`: syntax + origin only, no prior-correct buffer.

### Datasets / Models

Use a smaller held-out set if full runs are too expensive. This can be appendix
only. HRBench/V* are most relevant because tools can overfit visual regions.

### Expected Interpretation

Origin-only may produce higher training recovery but worse held-out accuracy or
more tool overuse. This supports the method's validation design.

## Optional Ablation 6: Sensitivity to k and N

This is useful but lower priority than the mechanism ablations above.

### Question

How much data and how many evolution passes are needed?

### Variants

- Training subset size: `k = 25, 50, 100, 200`
- Iterations: `N = 1, 3, 5`

### Recommendation

Put this in appendix unless there is a very clean curve. The main paper already
has many tables.

## Suggested Section Structure

Replace the current ablation subsection with:

1. `Mechanism ablations.` One paragraph saying Exp I already isolates skill vs.
   tool, so this section tests the method mechanisms behind that table.
2. Table with the five main variants above on ChartQA and HRBench.
3. Short interpretation paragraph:
   - Generic Skill tests prompt-engineering alternative.
   - Text-only Diagnosis tests the visual diagnostic channel.
   - No Mastery tests selective tool deployment.
   - No Persistence tests reusable cross-case capability accumulation.
4. Optional sentence pointing appendix to MathVista/V* and sensitivity curves.

## Minimal Text Draft

The following is a draft the writing agent can adapt:

> Table X ablates the mechanisms that are not already isolated by the Skill
> Only / Tool Only rows in Table 1. A generic task skill improves over direct
> prompting but remains below the evolved library, indicating that the benefit is
> not simply from adding more instructions. Removing the visual input from the
> AnalyzerDecider hurts most on HRBench, where deciding whether a failure is due
> to a missed local region requires inspecting the image and intermediate
> artifacts. Removing mastery increases indiscriminate tool exposure and reduces
> reliability, supporting the need to learn tool applicability boundaries rather
> than deploy every generated tool. Finally, disabling persistence weakens
> held-out performance, showing that the system's advantage comes from
> accumulating reusable capabilities rather than per-case retry alone.

## Practical Priority

If only two experiments can be run before submission, run:

1. `Generic Skill` vs `Full` on ChartQA.
2. `No Mastery` and/or `Text-only Diagnosis` on HRBench.

These two cover the paper's two most important axes: cognitive skill evolution
and perceptual tool mastery.

