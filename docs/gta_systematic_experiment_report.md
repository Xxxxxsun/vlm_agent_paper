# GTA Systematic Manual Tool-Skill Experiments

Date: 2026-05-11

Model: `doubao-seed-2.0-pro`

Note: GPT-5.4 routify returned HTTP 401 on 2026-05-11 for both the stored env key and the key supplied in the earlier command, so the systematic reruns use Doubao. The earlier GPT-5.4 pilot results remain in `gta_experiment_report.md`.

## Experiment A: Same Environment, Different Tool Strength

Claim tested: when task environment is fixed but tool abstraction strength changes, the skill/tool policy changes. Stronger tools should require a shorter and more direct policy, without reducing the experiment to a saturated 100% accuracy setting.

Main non-saturated setting: first 30 single-image GTA train+val cases by numeric GTA id satisfying `OCR` and `Calculator` in annotated tools and excluding `GoogleSearch`. Multi-image cases are excluded so both atomic and composite tools receive the same single image input.

Tool conditions:
- Direct: no tools.
- Atomic tools: `OCR`, `Calculator`, `ImageDescription`, `CountGivenObject`.
- Composite strong tool: `VisualArithmeticSolver`.

| condition | cases | accuracy | tool usage | avg calls | dominant chain |
| --- | ---: | ---: | ---: | ---: | --- |
| Direct, no tools | 30 | 83.3% | 0.0% | 0.00 | `<none>` |
| Atomic OCR+Calc tools | 30 | 86.7% | 100.0% | 1.83 | `OCR -> Calculator` |
| Composite visual-arithmetic tool | 30 | 90.0% | 100.0% | 1.00 | `VisualArithmeticSolver` |

Chain distribution:
- Atomic: `OCR -> Calculator` 22, `OCR` 4, `Calculator` 2, `OCR -> ImageDescription` 1, `OCR -> ImageDescription -> Calculator` 1.
- Composite: `VisualArithmeticSolver` 30.

Result interpretation: direct performance is below ceiling, so the task set is not trivially solved by the model alone. Atomic and composite tools both improve over direct and are close in final accuracy, but they induce different skills: atomic tools require an extract-then-compute chain, while the stronger composite tool supports a one-call policy.

Paths:
- `artifacts/manual_gta_toolskills/gta_systematic_doubao_tool_strength_atomic_ocr_calc30_v1/summary.json`
- `artifacts/manual_gta_toolskills/gta_systematic_doubao_tool_strength_composite_ocr_calc30_v1/summary.json`

Saturated sanity run, not recommended as the main paper result:
- 17/17 math cases with atomic `MathOCR/Solver/Calculator` and composite `MathProblemSolver`.
- Both reach 100%, so it is useful only for showing chain compression, not task difficulty.
- Paths: `gta_systematic_doubao_tool_strength_atomic_math17_v2`, `gta_systematic_doubao_tool_strength_composite_math17_v2`.

## Experiment B: Same Tool, Different Environments

Claim tested: the same tool can acquire different roles under different task environments. Here `OCR` appears in both environments, but the downstream action differs.

Selection rule:
- OCR+Calc environment: first 20 train+val cases by numeric GTA id satisfying `OCR` and `Calculator` in annotated tools and excluding `GoogleSearch`.
- OCR+Search environment: first 20 train+val cases by numeric GTA id satisfying `OCR` and `GoogleSearch` in annotated tools.

Tool conditions:
- OCR+Calc: `OCR`, `Calculator`, `ImageDescription`, `CountGivenObject`
- OCR+Search: `OCR`, `GoogleSearch`, `ImageDescription`

| environment | cases | accuracy | tool usage | avg calls | downstream tool use |
| --- | ---: | ---: | ---: | ---: | --- |
| OCR+Calc | 20 | 80.0% | 100.0% | 2.20 | `Calculator` in 19/20 |
| OCR+Search | 20 | 85.0% | 100.0% | 2.35 | `GoogleSearch` in 20/20 |

Chain distribution:
- OCR+Calc: `OCR -> Calculator` 12, count-augmented OCR/calculator chains 5, `Calculator` only 2, `OCR` only 1.
- OCR+Search: `OCR -> GoogleSearch` 11, `OCR -> GoogleSearch -> GoogleSearch` 6, `OCR -> GoogleSearch -> ImageDescription` 2, `GoogleSearch` only 1.

Result interpretation: OCR is not used as a generic "read text then answer" habit. In the calculation environment it becomes an operand extractor whose output is routed to arithmetic. In the search environment it becomes an entity/query extractor whose output is routed to external lookup. The same OCR tool is therefore embedded into different skills depending on the environment.

Paths:
- `artifacts/manual_gta_toolskills/gta_systematic_doubao_same_ocr_calc20_v1/summary.json`
- `artifacts/manual_gta_toolskills/gta_systematic_doubao_same_ocr_search20_v1/summary.json`

## Reproduction Commands

All runs unset proxy variables before API calls:

```bash
set -a
source artifacts/batch_runs/20260420T174315Z/tasks/doubao.env
set +a
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
export NO_PROXY="*" no_proxy="*" PYTHONPATH=.
```

Atomic tool-strength run:

```bash
python scripts/run_gta_manual_toolskill_experiment.py \
  --subset-id gta_systematic_doubao_tool_strength_atomic_ocr_calc30_v1 \
  --split train,val \
  --selection all \
  --case-ids gta_24 gta_25 gta_26 gta_27 gta_28 gta_31 gta_32 gta_41 gta_53 gta_78 gta_97 gta_98 gta_99 gta_100 gta_101 gta_102 gta_103 gta_104 gta_105 gta_106 gta_107 gta_108 gta_109 gta_110 gta_111 gta_130 gta_131 gta_132 gta_133 gta_134 \
  --tool-profile ocr_calc \
  --skill-profile ocr_calc \
  --settings direct skill
```

Composite tool-strength run:

```bash
python scripts/run_gta_manual_toolskill_experiment.py \
  --subset-id gta_systematic_doubao_tool_strength_composite_ocr_calc30_v1 \
  --split train,val \
  --selection all \
  --case-ids gta_24 gta_25 gta_26 gta_27 gta_28 gta_31 gta_32 gta_41 gta_53 gta_78 gta_97 gta_98 gta_99 gta_100 gta_101 gta_102 gta_103 gta_104 gta_105 gta_106 gta_107 gta_108 gta_109 gta_110 gta_111 gta_130 gta_131 gta_132 gta_133 gta_134 \
  --tool-profile ocr_calc_composite \
  --skill-profile ocr_calc_composite \
  --settings skill
```

Same-tool OCR+Calc and OCR+Search runs are in the summary paths above; their exact case ids are stored in each `per_case.jsonl`.
