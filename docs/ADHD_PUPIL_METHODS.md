# ADHD Pupil Validator Methods

## Scope

The validator performs a behavioral conceptual replication using the public ADHD Pupil Dataset. The primary question is whether off-medication ADHD participants differ from controls in response speed, robust RT variability, all-trial accuracy, and omissions without requiring subtype assignment.

## Acquisition and integrity

The script downloads the official Figshare file, queries public metadata, verifies byte count and MD5, records SHA-256, and supports resumed downloads. Raw data are removed after a successful run unless `--keep-data` is used.

## MATLAB decoding

The source is MATLAB 7.3/HDF5. `Task_epocs` is stored as MATLAB MCOS tables with `(1, 6) uint32` object headers. Standard SciPy and `mat73` do not reconstruct these tables. The validator uses `mat73-reader==0.1.0`, which resolves MCOS references and returns pandas DataFrames.

Actual source fields:

```text
Pupil_data
Subject
Age
Group
Task_data
Task_epocs
Wisc
```

Trial fields:

```text
Trial
Load
Distractor
CorrResponse
Perform
Rtime
Pupil
```

## Scoring

- `Perform = 1`: correct.
- `Perform = 0`: observed incorrect response.
- Missing `Perform`: conservatively scored as no-response/omission error.
- Accuracy is calculated over all trials.
- Correct-RT metrics use valid correct responses within 100–5,000 ms.
- Sessions require at least 20 valid correct-RT trials.

## Conditions

`Load` has two levels and is summarized with a signed median contrast. `Distractor` has four categorical levels (`3`, `4`, `5`, `6`). Because no ordinal direction is assumed, secondary distractor endpoints use participant-level max-minus-min ranges across level-specific medians or rates.

## Inference

Primary ADHD-off vs control endpoints:

- median correct RT;
- RT MAD;
- RT IQR;
- all-trial accuracy;
- omission rate.

Tests include two-sided Mann–Whitney U, rank-biserial effect size, 5,000 median-difference permutations, 2,000 bootstrap repetitions, and Brown–Forsythe dispersion tests. Holm correction is applied within primary and secondary endpoint families.

Paired medication analyses use 17 off/on pairs, Wilcoxon tests, sign permutations, bootstrap confidence intervals, and Holm correction.

## Clustering boundary

The secondary GMM is fit only within off-medication ADHD participants using RT-derived features. Diagnosis and control data do not define components. A discrete two-component interpretation requires all configured BIC, silhouette, minimum-size, and bootstrap-ARI gates. Failed gates prohibit subtype claims.

## Interpretation boundary

Behavioral differences do not identify dopamine, ATP, metabolic, neural, or allostatic mechanisms. The reported primary run excludes pupil time-series analysis. Medication comparisons are exploratory and do not support treatment recommendations.
