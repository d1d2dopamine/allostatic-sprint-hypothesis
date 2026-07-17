# BALLADEER Validator v1.0.1 Candidate — Status, Run Plan, and TODO

## Read this first

This folder preserves the partially improved BALLADEER validator that was written after the historical v1.0.0 analysis.

```text
Script: HEALTHY_VALID_BALLADEER.py
Internal version: 1.0.1
Status: candidate; syntax-valid; real-data rerun not completed
```

The file must not be described as a completed replication. It contains substantial methodological improvements, but its loaders and statistical outputs still need to be validated against the complete real BALLADEER dataset.

## Why the previous run stopped

The validator searched local folders and ZIP archives but could not find:

```text
users_demographics.json
```

The run therefore stopped before participant reconstruction and before any new inferential result was produced. The old `healthy_valid_academic_diagnostic.txt` belongs to historical validator v1.0.0 and is not an output of this candidate.

## What v1.0.1 already improves

Compared with historical v1.0.0, this candidate:

- removes forced Sprint/Crash labels from the active pipeline;
- uses Pure ADHD versus Pure Control as the cluster-free primary comparison;
- prevents accuracy, omissions, and commission errors from defining latent components;
- uses work-speed mean and work-speed variability as exploratory dimensions;
- keeps commission rate as a held-out outcome for dimensional and GMM analyses;
- adds two-sided Mann–Whitney tests;
- adds 5,000 label permutations;
- adds 2,000 bootstrap repetitions for median-difference confidence intervals;
- adds median-centered Brown–Forsythe dispersion tests;
- applies Holm correction to the four secondary group endpoints;
- adds a robust HC3 covariate model;
- restricts the secondary GMM to ADHD participants and tests K = 1, 2, and 3;
- requires BIC, silhouette, minimum-component-size, and bootstrap-ARI gates before accepting two components;
- assigns only numeric exploratory component labels, never Sprint/Crash names;
- adds temporal commission-rate slopes across task blocks;
- adds exploratory EDA/PRV associations when valid wearable data exist;
- writes a report, machine-readable files, figures, configuration, and reproducibility log.

## Required source files

The current loader expects the official BALLADEER data or a ZIP containing:

```text
users_demographics.json
balladeer_embraceplus_data.csv
<UserID>_GAME_DATA_<SessionDate>.csv
```

Game files are expected to have names resembling:

```text
UB1234_GAME_DATA_2026-01-01.csv
```

and the following block-level columns for blocks 1–4:

```text
velocidadTrabajoBloque<N>
comisionBloque<N>
omisionBloque<N>
aciertosBloque<N>
```

The biometrics file is currently read with semicolon separation and expects `username` plus EDA, PRV, and wearing-detection fields for sources such as `S1`, `S6`, `S11`, `Cognifit`, and `Robots`.

The script does not download BALLADEER automatically. It searches Downloads, the script directory, the current working directory, selected mobile storage locations, and local ZIP archives.

## Highest-priority corrections before final release

### P0 — required before trusting any result

1. **Obtain the complete official dataset and perform one real schema audit.**
   - Confirm the exact archive and internal paths.
   - Confirm that `users_demographics.json` really uses `username` or `user`, `group`, `diagnosed`, `age`, and `gender` as expected.
   - Confirm that group values `1 = Experimental/ADHD` and `2 = Control` match the authors' documentation.
   - Record file sizes and SHA-256 hashes.

2. **Verify the cohort rules against the data documentation.**
   - Current Pure Control rule: `group == 2` and `diagnosed == "no"`.
   - Current Pure ADHD rule: `group == 1`, plus any `group == 2` row marked `diagnosed == "yes"`.
   - Current suspected rule uses `diagnosed == "undetermined"`.
   - Do not assume these rules are correct until actual counts and source documentation are reviewed.

3. **Verify the GAME_DATA structure.**
   - The current loader reads only `session_df.iloc[0]` from each game file.
   - Confirm that each file truly contains one summary row. If files contain multiple meaningful rows, the loader must aggregate or reshape all applicable rows instead of silently ignoring them.
   - Confirm comma versus semicolon separation and decimal formatting.
   - Confirm all four block columns and inspect missingness.

4. **Clarify what `work_speed_std` measures.**
   - The current value is the standard deviation of block-level `velocidadTrabajoBloque<N>` values across available blocks/sessions.
   - It is not automatically equivalent to trial-level reaction-time variability.
   - Rename it to `block_work_speed_sd` or document the construct precisely unless the source documentation proves a direct RT-variability interpretation.

5. **Make biometrics optional for the primary behavioral analysis.**
   - The current script aborts if `balladeer_embraceplus_data.csv` is missing.
   - EDA/PRV are secondary and should not prevent the cluster-free behavioral analysis from running.
   - If biometrics are unavailable or unusable, write a clear skip reason and continue.

6. **Fit GMM preprocessing within ADHD only.**
   - The current standardized dimensions are created before the ADHD subset is selected.
   - For the secondary ADHD-only GMM, scaling and any PCA used by clustering should be fitted only on the ADHD sample so controls do not influence the component feature space.
   - The held-out outcome variables must remain excluded.

7. **Add multiplicity control to exploratory associations.**
   - `dimensional_associations()` currently tests three predictors against three outcomes without correction.
   - Add Holm or Benjamini–Hochberg correction, or explicitly designate the entire section descriptive/exploratory.
   - Apply the same decision consistently to biometric correlations.

8. **Add explicit QC and schema outputs.**
   Create at least:

   ```text
   balladeer_schema_audit.csv
   balladeer_quality_control.csv
   ```

   Include source paths, parsed files, failed files, participant matching, cohort counts, missingness, duplicate IDs, sessions per participant, usable blocks, and exclusion reasons.

### P1 — strongly recommended

9. **Handle repeated sessions deliberately.**
   - The current participant aggregation combines all discovered sessions.
   - Decide whether the estimand is first session, latest session, prespecified session, or participant-level aggregation.
   - If multiple sessions are retained, consider a hierarchical or repeated-measures model.

10. **Choose the inferential p-value consistently.**
    - The report gives both Mann–Whitney and permutation p-values.
    - Prespecify which one is primary before viewing results.
    - Secondary multiplicity correction currently uses Mann–Whitney p-values; decide whether corrected permutation p-values would be more consistent with the project.

11. **Audit the percentage-outcome model.**
    - HC3 OLS is robust to heteroskedasticity but does not respect 0–100 bounds.
    - If trial totals are available, consider a binomial or quasi-binomial model using commission counts and denominators.

12. **Clean stale outputs and package Colab results.**
    - Remove stale crash logs at the start of a new run.
    - Add an output ZIP.
    - Optionally trigger a Colab download after success.

13. **Add regression tests.**
    - Synthetic one-row game files.
    - Multi-row game files.
    - Missing biometrics.
    - Duplicate participants.
    - Multiple sessions.
    - Missing blocks.
    - GMM gate pass/fail fixtures.

### P2 — after the first successful corrected run

14. Review every generated count and plot before interpreting p-values.
15. Compare cluster-free results with historical v1.0.0 without reusing the old anchor-defined clusters.
16. Preserve null results and failed GMM gates exactly as returned.
17. Add final outputs under a new versioned directory, not inside v1.0.0:

```text
docs/results/balladeer/v1.0.1/
```

18. Update README, analysis log, changelog, release notes, and SHA-256 manifest only after the real run passes QC.
19. If code changes after the run, rerun the exact final code or preserve both the executed candidate and promoted version with explicit hashes.

## What the finished validator should do

A final BALLADEER validator should:

1. locate or accept an explicit path to the official dataset/ZIP;
2. verify and log source-file hashes;
3. inspect and record the actual schema;
4. reconstruct participants and clean diagnostic cohorts transparently;
5. produce block-, session-, and participant-level QC;
6. run a cluster-free Pure ADHD versus Pure Control primary comparison;
7. test commission rate as the prespecified primary behavioral endpoint;
8. summarize omissions, accuracy, work speed, and block-level stability as secondary endpoints;
9. use permutation, bootstrap, effect-size, and dispersion analyses;
10. correct related secondary/exploratory test families for multiplicity;
11. fit any ADHD-only GMM without outcome leakage or control-derived preprocessing;
12. reject discrete components when any stability gate fails;
13. examine within-session temporal change without claiming weeks-to-months cycling;
14. treat EDA/PRV as optional exploratory physiology;
15. avoid dopamine, ATP, causal, diagnostic, and treatment claims;
16. produce a complete report, config, QC, logs, CSVs, figures, and downloadable ZIP.

## Expected outputs from the current candidate

On success, the current script writes:

```text
HEALTHY_VALID_BALLADEER_output/
├── balladeer_cluster_free_report.txt
├── balladeer_participant_metrics.csv
├── balladeer_gmm_diagnostics.csv
├── balladeer_cluster_free_commissions.png
├── balladeer_dimensional_spectrum.png
├── balladeer_temporal_dynamics_dimensional.png
├── balladeer_analysis_config.json
└── balladeer_reproducibility_log.txt
```

On failure it writes:

```text
balladeer_crash_log.txt
```

The current candidate does not automatically create a result ZIP.

## Running in Google Colab

### Recommended: use Google Drive

Place the complete BALLADEER ZIP and the Python script in:

```text
MyDrive/BALLADEER/
```

Then run:

```python
from google.colab import drive
drive.mount('/content/drive')

%cd /content/drive/MyDrive/BALLADEER
!pip install -q pandas numpy scipy matplotlib seaborn openpyxl scikit-learn statsmodels
!python HEALTHY_VALID_BALLADEER.py
```

If successful, package and download the output:

```python
!zip -r /content/BALLADEER_v1.0.1_output.zip HEALTHY_VALID_BALLADEER_output

from google.colab import files
files.download('/content/BALLADEER_v1.0.1_output.zip')
```

If it fails, download:

```text
HEALTHY_VALID_BALLADEER_output/balladeer_crash_log.txt
```

and preserve it with the exact script hash.

## Decision rules after running

Do not interpret results until all of these are checked:

- correct source files were used;
- cohort counts match the documentation;
- participant IDs match across demographics, game, and biometrics;
- exclusions and missingness are plausible;
- commission, omission, and accuracy totals are internally consistent;
- repeated sessions were handled as intended;
- primary and secondary p-value families are correctly defined;
- GMM component sizes and stability gates are reported;
- no old v1.0.0 output was mixed into the new folder.

If the run succeeds technically but these checks fail, it remains a diagnostic run, not a valid scientific result.

## Interpretation boundaries

The validator can test behavioral differences, dimensional associations, and limited within-session dynamics. It cannot establish:

- permanent Sprint/Crash types;
- dopamine receptor states;
- ATP depletion or metabolic exhaustion;
- weeks-to-months allostatic cycles;
- medication efficacy;
- diagnosis, prognosis, or treatment selection.

## File identity

The included Python file is intentionally preserved unchanged from the existing v1.0.1 candidate. Its expected SHA-256 is:

```text
771582e2344497a17a4afbf5ac1a147eecb7920d241c657d8201cc6be30881e1
```
