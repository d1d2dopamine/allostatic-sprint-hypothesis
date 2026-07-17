# Analysis Log

This is an honest chronology of how the methodology changed, including mistakes, negative results, abandoned approaches, and unresolved limitations—not just the latest preferred interpretation. It was reconstructed from available scripts, generated outputs, repository history, and one collaborator's conversation history; earlier work performed elsewhere may still be incomplete. Last substantially updated: **17 July 2026**.

## v1 — HYPERAKTIV, first pass

- Built a Monte Carlo simulation of a hypothesized dopamine D1/D2 + ATP-depletion mechanism, producing four fixed "theoretical centroids."
- Real HYPERAKTIV participants were assigned to the nearest centroid (z-scaled Euclidean distance) and compared via Mann-Whitney U.
- Initial result: "Decompensated Sprint" cluster, p = 0.0004, r = -0.582 (survives Bonferroni).

**Final corrected HYPERAKTIV run** (Clinical Control label, noise cluster fully dissolved, permutation test added): "Decompensated Sprint" gives U=193.00, p=0.0312, r=-0.462 (n=24 ADHD vs 11 clinical control) — this does **not** clear the Bonferroni-corrected threshold (0.0167), and the permutation test confirms this (empirical p = 0.0420, also above threshold). So on HYPERAKTIV this is a trend in the same direction as BALLADEER, not an independently significant result — see the "Where this stands" summary below for why this matters.

**Problems identified on review:**
- The comparison group was labeled "Healthy Control" but is actually HYPERAKTIV's *clinical* control group (other psychiatric diagnoses, not confirmed-healthy people).
- Circularity: centroids came from an untested simulated mechanism, not from real receptor/biological measurement; a within-cluster ADHD/control difference doesn't validate the mechanism, since RT variability and commission-rate differences are already well-documented ADHD markers on their own.
- The "entropy_paradox" (noise) cluster was explicitly designed to absorb ambiguous participants and clean up the boundary between the two hypothesized subtypes — a form of post-hoc boundary sharpening.
- Small per-cluster sample sizes; multiple analytic choices not accounted for beyond the cluster-count Bonferroni correction.

## Correction plan

1. Rename "Healthy Control" → "Clinical Control"; separate observed pattern from proposed mechanism explicitly in all text output.
2. Add a label-permutation test (shuffle ADHD/control labels, not cluster assignments) to properly account for pipeline flexibility.
3. Resolve/justify the noise-cluster exclusion criterion.
4. Find a dataset with genuine neurotypical (not clinical) controls for independent testing.

## BALLADEER — first run

- Identified BALLADEER (Trujillo, Ferrer-Cascales, Teruel et al., *Scientific Data*, 2026) as a dataset with true neurotypical controls and a CPT-like attention task (Nesplora AULA/AQUARIUM, "Attention Robots").
- First run revealed the dataset's own `group` field is not perfectly clean: within the nominal "Control" group, a separate `diagnosed` field showed a meaningful fraction coded `yes` or `undetermined` for ADHD (per the dataset's own data dictionary: `undetermined` = no formal diagnosis, but project psychologists suspected ADHD).

## BALLADEER — clean cohort run

- Rebuilt groups from the `diagnosed` field directly: Pure ADHD (`diagnosed == yes`), Pure Control (`diagnosed == no`), Suspected ADHD (`diagnosed == undetermined`, analyzed separately, excluded from the primary test).
- Results (Mann-Whitney U, Bonferroni-corrected across 3 clusters, α = 0.0167):
  - **Decompensated Sprint** (n = 20 vs 20): p = 0.011, r ≈ -0.465 — **significant**, confirmed by permutation test (empirical p = 0.014).
  - Compensated Crash (n = 28 vs 23): p = 0.443 — not significant.
  - True Resilience (n = 17 vs 33): p = 0.256 — not significant.
- PRV (pulse-rate variability) confirmed genuinely unavailable — NaN across every participant and every activity source in this export, not a script bug. The physiological "crash" mechanism remains untested, not disproven.
- EDA (skin conductance) change was examined descriptively as a substitute; no clear pattern distinguishing "Crash" from "Sprint" emerged, and no significance test was run on it — treat as inconclusive, not evidence either way.

## Testing the temporal-dynamics claim

- The original hypothesis also claimed the two subtypes diverge *over time within the task* (stable vs. progressively worsening). This was tested directly:
  - A pooled, cluster-free mixed model across all diagnosed ADHD participants came back flat (p ≈ 0.98). **This is not itself evidence that the two subtypes "cancel each other out" — that specific claim was proposed after the fact and was not tested directly, and was correctly rejected as an unfalsifiable post-hoc story.**
  - A direct test, restricted to Pure ADHD only (`commission ~ block × cluster`, Sprint vs. Crash), came back p = 0.847 — no support for differing trajectories. However, only 4 of the 20 "Sprint" participants had complete 4-block data (missing-data attrition), so this specific result is likely underpowered and should be read as inconclusive rather than a clean disproof.
- **Rejected approach:** after the flat result, a suggestion was made to either loosen missing-data filters or switch the outcome variable (to work-speed mean, then speed variability) until something crossed p < 0.05. This is a textbook significance-hunting pattern and was not pursued. If missing-data handling or alternate metrics are revisited later, the choice must be made *before* seeing results, and any additional metrics tested must be corrected for as additional comparisons.

## UCLA CNP — selecting a third independent test

Following the BALLADEER result and the HYPERAKTIV trend, the next priority was an independent dataset that would not reuse the same forced-anchor classification. Several constraints were imposed before selecting a dataset:

- Publicly accessible participant-level behavioral data.
- A genuine healthy-control group rather than a clinical comparison group.
- An ADHD sample large enough for a whole-group test.
- Trial-level response-inhibition data permitting independent recalculation of participant metrics.
- No requirement to download MRI data.
- A primary analysis that could be performed without assigning Sprint/Crash labels.

The selected dataset was **UCLA Consortium for Neuropsychiatric Phenomics / OpenNeuro `ds000030`**, distributed under PDDL. It contains multiple diagnostic groups and several tasks; only phenotype metadata and Stop-Signal Task event tables were required for the present analysis. This was explicitly treated as a **conceptual replication**, because an adaptive Stop-Signal Task is not equivalent to HYPERAKTIV CPT-II or BALLADEER's Attention Robots task.

Relevant sources:

- OpenNeuro: `https://openneuro.org/datasets/ds000030/versions/1.0.0`
- Dataset repository: `https://github.com/OpenNeuroDatasets/ds000030`
- Data descriptor: `https://doi.org/10.1038/sdata.2016.110`
- Anonymous object store: `s3://openneuro.org/ds000030`

## UCLA CNP validator — prespecified methodological changes

A new universal script, `UCLA_CNP_VALIDATOR.py`, was written for local terminals and Google Colab. It was designed as a reusable validator rather than a one-off notebook fragment.

### Data acquisition and safety

- Selective anonymous S3 retrieval via `boto3`; no Git clone or DataLad requirement.
- Downloads only tabular phenotype, metadata, and Stop-Signal event files.
- Safety gate excludes `.nii`, `.nii.gz`, DICOM, `bval`, and `bvec` files.
- Flexible event-schema detection with documented aliases.
- Supports `--data-dir`, `--output-dir`, `--no-download`, `--keep-data`, `--no-auto-install`, `--self-test`, and `--no-colab-download`.
- Downloaded raw tabular files are removed only after a successful run unless `--keep-data` is specified.
- A crash log is written if execution fails.

### Primary analysis

The UCLA primary analysis was deliberately **cluster-free**:

- All eligible ADHD participants were compared with all eligible healthy controls.
- No subtype labels were assigned before the group comparison.
- Participant metrics were calculated directly from trial-level events.
- Primary and supporting measures included median go RT, go RT MAD, go RT IQR, omission rate, and integration-method SSRT when the required stop-signal information was available.
- Group location was evaluated with two-sided Mann–Whitney U, rank-biserial effect size, bootstrap confidence intervals, and a median-difference label-permutation test.
- Group dispersion was evaluated with median-centered Brown–Forsythe tests.

### Secondary ADHD-only clustering

Clustering was made secondary and restricted to ADHD participants. To avoid repeating the BALLADEER outcome-circularity problem:

- Component features were only `median_go_rt_s` and `go_rt_mad_s`.
- Diagnosis, healthy controls, SSRT, stop accuracy, and other held-out outcomes did not define components.
- Gaussian mixture models with K = 1, 2, and 3 were compared.
- A two-component interpretation required **all** prespecified gates:
  - BIC improvement over K = 1 of at least 10;
  - K = 2 must have the best BIC among K = 1, 2, 3;
  - silhouette score at least 0.25;
  - each component at least 15% of the ADHD sample;
  - bootstrap median adjusted Rand index at least 0.60.
- Failure of any gate prevented a stable-two-cluster conclusion.
- No component was automatically named Sprint or Crash.
- SSRT was retained as a held-out validation measure.

The script used a fixed seed (`20260716`), 5,000 label permutations, and 500 bootstrap repetitions. Script version at the completed UCLA run: `0.1.0`.

## UCLA CNP — actual data retrieval and quality control

The completed Colab run retrieved **639 tabular/metadata files totaling 14.52 MB**—not the raw MRI dataset.

Metadata coverage:

- 272 participants represented in the retrieved metadata.
- 43 labeled ADHD.
- 130 labeled healthy control.
- 99 belonging to other diagnoses or otherwise outside the target comparison.

Eligible analysis sample:

- 41 ADHD participants.
- 126 healthy controls.
- Six metadata participants lacked usable scanner event files.
- No additional participants were excluded by the remaining implemented QC criteria.

Parsed event coverage:

- 266 scanner event files.
- 267 training event files.

Detected task columns:

```text
trial_type
ReactionTime
StopSignalDelay
SubjectResponseCorrectness
SubjectResponseButton
onset
```

The schema was recorded in the reproducibility output rather than silently assumed.

## UCLA CNP — cluster-free results

### Group location

| Metric | ADHD | Healthy control | Test result |
|---|---:|---:|---:|
| Median go RT | 0.4768 s | 0.4481 s | p = 0.2817; permutation p = 0.1500 |
| Go RT MAD | 0.0602 s | 0.0612 s | p = 0.7281 |
| Go RT IQR | 0.1237 s | 0.1219 s | p = 0.8018 |
| Go omission rate | median 0 | median 0 | p = 0.3252 |
| SSRT | 0.2061 s | 0.2172 s | p = 0.7086 |

None of the examined whole-group location tests was statistically significant. ADHD median go RT was descriptively slower, but the uncertainty and p-values do not support a reliable group difference in this sample.

### Group dispersion

Median-centered Brown–Forsythe p-values:

| Metric | p-value |
|---|---:|
| Median go RT | 0.7661 |
| Go RT MAD | 0.3992 |
| Go RT IQR | 0.4803 |
| SSRT | 0.2037 |

These results provided no significant evidence that the ADHD group had greater dispersion than healthy controls on the examined Stop-Signal measures. This matters because a broad dimensional-heterogeneity account might predict wider ADHD distributions, but this dataset did not show that pattern on these variables.

## UCLA CNP — GMM result and rejected subtype interpretation

ADHD-only Gaussian mixture diagnostics:

| K | BIC |
|---:|---:|
| 1 | 201.47 |
| 2 | 183.90 |
| 3 | 199.13 |

Additional diagnostics:

- BIC improvement, K = 1 minus K = 2: **17.57** — passes the ≥10 gate.
- K = 2 had the best BIC — passes.
- Silhouette: **0.726** — passes.
- Bootstrap median ARI: **0.638** — passes.
- Minimum component share: **0.02439**, corresponding to one participant out of 41 — fails the required ≥0.15 gate.

Final decision:

```text
stable_two_cluster = False
```

Although several diagnostics looked strong, the smaller component contained only one person. It was therefore interpreted as an **outlier-like component**, not a behavioral subtype. Sprint/Crash labels were not assigned. This is an example of why a single favorable clustering metric is insufficient: BIC and silhouette can reward isolation of an extreme observation.

## UCLA CNP — interpretation

The UCLA result is a meaningful null conceptual replication:

- It does not support a broad task-general ADHD-control difference on the examined Stop-Signal measures.
- It does not support greater ADHD variance on those measures.
- It does not support two adequately sized, stable ADHD components.
- It does not prove equivalence between groups.
- It does not directly refute the BALLADEER commission-error finding, because the tasks and outcome structures differ.
- It constrains any claim that Sprint/Crash are universal, discrete, cross-task ADHD subtypes.

The correct interpretation is not that UCLA “failed.” The validator successfully tested a broader claim and returned a reproducible null result.

Generated UCLA artifacts:

```text
ucla_cnp_academic_diagnostic.txt
ucla_cnp_group_distributions.png
ucla_cnp_temporal_dynamics.png
ucla_cnp_participant_metrics.csv
ucla_cnp_quality_control.csv
ucla_cnp_cluster_diagnostics.csv
ucla_cnp_analysis_config.json
ucla_cnp_reproducibility_log.txt
```

The completed validator file contained 1,204 lines and 52,531 bytes at delivery. Recorded SHA-256:

```text
c7d588adc49c0754d44d01c8f4f58472f11b4727764a710beb07ba65ef934abb
```

## Reformulation: discrete subtypes to dimensional behavioral space

The cumulative evidence no longer supports presenting Sprint and Crash as established, permanent, task-general categories. The working reformulation is a multidimensional behavioral space with partly independent axes:

1. Response speed.
2. Reaction-time or work-speed variability.
3. Commission-error propensity / disinhibited responding.
4. Omission propensity / inattention.
5. Stopping latency or inhibitory control.
6. Motor activity when independently measured.
7. Within-session deterioration or stabilization.

Under this formulation:

- “Sprint-like” and “Crash-like” describe possible poles or regions, not diagnoses.
- Most participants may occupy intermediate positions.
- A participant's position may depend on sleep, medication, motivation, stress, fatigue, task structure, reward, and time.
- Discrete clusters should be accepted only when they are sufficiently large, stable, independently validated, and not constructed from the outcome later used to validate them.
- A null cluster result should remain null; labels must not be forced.

Important boundary: UCLA CNP did **not** prove a dimensional spectrum. It rejected an acceptable discrete two-component solution on the examined features and left the dimensional/state-sensitive account as an exploratory next model.

## README update after UCLA CNP

The project README was substantially rewritten in English while preserving the existing DOI, status, peer-review, license, and Python badges. Additions included:

- UCLA CNP evidence and figures.
- An evidence-at-a-glance table covering BALLADEER, HYPERAKTIV, and UCLA CNP.
- Explicit separation of positive, nonsignificant, and null findings.
- A “From Discrete Subtypes to a Dimensional Interpretation” section.
- Updated methodology and clustering acceptance gates.
- Stronger interpretation boundaries.
- Explicit disclosure that dopamine receptor states, ATP depletion, and the proposed biological mechanism were not measured.
- A statement that the analyses are not diagnostic or clinical tools.

The README continues to report the historical BALLADEER result, but labels it task-specific and partially circular. UCLA figures were added without presenting descriptive block dynamics as a significant longitudinal interaction.

## Search for additional datasets

Several potential follow-up datasets were reviewed.

### ATTLAPSE

- 28 medication-naïve adults with ADHD and 28 healthy controls.
- Sustained Attention to Response Task / Go-No-Go structure.
- Behavioral performance, thought probes, ASRS, and 64-channel EEG.
- Scientifically close to the current question, especially for fatigue, motivation, mind wandering, and within-session state changes.
- Zenodo record: `https://zenodo.org/records/17314289`.
- Description and license are public, but files were marked restricted at the time of review; access must be requested.
- Exact file structure and availability of convenient trial-level behavioral tables have not yet been independently validated.

### OpenNeuro `ds003500`

- Response inhibition and selective attention in participants with and without ADHD.
- 12 children with ADHD, 15 age-matched child controls, and 11 adults.
- Twelve blocks of 18 trials, half go and half no-go.
- CC0 and fully open.
- Close to commission-error analyses but underpowered for a decisive test; better treated as a pilot exact-task replication.

### OpenNeuro `ds005899`

- Children with ADHD and typically developing controls.
- Cued Stop-Signal Task.
- OpenNeuro release includes 61 participants; the associated paper mentions a larger behavior-only sample of 50 ADHD and 37 typically developing participants.
- Full raw behavioral availability for the behavior-only sample remains uncertain.
- Useful but conceptually overlaps with UCLA's Stop-Signal construct.

### OpenNeuro `ds002424`

- 79 children, including 35 ADHD participants at the first time point.
- Working-memory and reward manipulation using multiple n-back tasks.
- CC0.
- Relevant to context dependence, cognitive load, and reward, but not a direct commission-error replication.

### Healthy Brain Network

- Large pediatric transdiagnostic resource with phenotypes, EEG, behavioral tasks, and other modalities.
- Particularly attractive for dimensional rather than binary subtype analysis.
- Phenotypic linkage requires a Data Usage Agreement.

### ABCD

- Very large longitudinal cohort with Stop-Signal and ADHD symptom measures.
- Requires controlled-access application through NDA/NBDC rather than frictionless public download.
- Known Stop-Signal design and QC issues require specialized handling.
- Considered a later, higher-complexity longitudinal test rather than the next low-barrier validator.

## HBN Quotient ADHD System Child request

An access request was submitted for the **Healthy Brain Network Quotient ADHD System — Child** data.

Why it is relevant:

- It combines a computerized sustained-attention task with motion tracking.
- It targets attention, impulsivity, and hyperactivity together.
- Potential measures include response accuracy, commission errors, omission errors, latency, response fluctuations, and movement.
- Some Quotient implementations classify short time windows into proprietary attention-state categories.

Important limitations identified before access:

- HBN no longer administers Quotient, so coverage is likely restricted to an earlier subset.
- The released table may contain only proprietary summary scores rather than raw trials or 30-second windows.
- Proprietary `Attentive`, `Impulsive`, or `Distracted` labels must not be treated as independent confirmation of Sprint/Crash.
- Quotient alone may not contain diagnostic/control labels; participant IDs must be joined to HBN phenotype and diagnostic tables.
- Age, sex, medication status, symptom severity, and comorbid diagnoses must be considered.
- CPT-style scores should not be treated as stand-alone diagnostic evidence.

A preregistration-style document, `docs/HBN_QUOTIENT_PREREGISTRATION.md`, was created before receipt of the requested data. Any changes made after data access should be recorded as dated amendments rather than silently replacing the original plan.

## BALLADEER methodological correction — candidate v1.0.1

The unresolved circularity in the historical BALLADEER analysis became the next code target. A candidate replacement `HEALTHY_VALID_BALLADEER.py` was written with the following design:

### Primary cluster-free analysis

- Pure ADHD versus Pure Control without subtype assignment.
- Commission rate designated as the sole primary outcome.
- Two-sided Mann–Whitney U.
- Rank-biserial effect size.
- 5,000 label permutations for the median difference.
- 2,000 bootstrap repetitions for the median-difference confidence interval.
- Brown–Forsythe dispersion test.
- Secondary outcomes include omissions, accuracy, speed, and speed variability; secondary p-values use Holm correction.

### Independent dimensional analysis

- Component/dimension features are only work-speed mean and work-speed variability.
- Commission rate, omission rate, and accuracy are excluded from dimension and component formation.
- A principal speed/variability axis is calculated.
- ADHD-only Spearman associations relate independent dimensions to held-out behavioral outcomes.
- An HC3 robust OLS model evaluates diagnosis, speed, variability, diagnosis interactions, and available age/sex covariates.

### Secondary ADHD-only GMM

- K = 1, 2, and 3 compared by BIC.
- Two-component acceptance gates mirror the UCLA logic:
  - BIC improvement ≥10;
  - K = 2 best BIC;
  - silhouette ≥0.25;
  - minimum component share ≥0.15;
  - bootstrap median ARI ≥0.60.
- Components remain numeric exploratory components.
- The validator defines no Sprint/Crash subtype labels.

### Temporal and physiological checks

- Individual commission-rate slopes across blocks are related to the independent dimensional axis.
- Available EDA/PRV changes are analyzed dimensionally rather than as forced subtype bar groups.

Candidate output files:

```text
balladeer_cluster_free_report.txt
balladeer_participant_metrics.csv
balladeer_gmm_diagnostics.csv
balladeer_cluster_free_commissions.png
balladeer_dimensional_spectrum.png
balladeer_temporal_dynamics_dimensional.png
balladeer_analysis_config.json
balladeer_reproducibility_log.txt
```

Validation status as of 17 July 2026:

- Python syntax compilation passed.
- Static checks confirmed removal of active forced-anchor and nearest-cluster logic.
- The local sandbox lacked SciPy, preventing a complete runtime self-test there.
- A Colab attempt did not constitute a real test: the session contained an older validator and no BALLADEER dataset files. The error was a missing `users_demographics.json`, not a statistical or parser result.
- The complete BALLADEER dataset would need to be downloaded again because it is not mirrored in the project repository. That download was deferred.
- Therefore **no v1.0.1 BALLADEER numerical result exists yet**.
- The historical v1.0.0 BALLADEER numbers remain the only completed BALLADEER result and must not be silently replaced.

Candidate script SHA-256 at delivery:

```text
771582e2344497a17a4afbf5ac1a147eecb7920d241c657d8201cc6be30881e1
```

## Repository reorganization and reproducibility

The repository was reorganized to make active code, documentation, figures, and historical versions easier to distinguish.

Current intended top-level organization:

```text
docs/
images/
scripts/
CITATION.cff
LICENSE
README.md
analysis_log.md
requirements.txt
.gitignore
```

Repository actions completed or prepared:

- Active validators placed under `scripts/`.
- Original BALLADEER validator preserved under `docs/legacy/v1.0.0/` with an explanatory README.
- HBN preregistration placed under `docs/`.
- Figures moved under `images/`.
- README figure references updated to `images/...` paths.
- UCLA figures retained alongside historical BALLADEER figures.
- Dependency list expanded to include the libraries used across all validators, including `boto3`, `scikit-learn`, and `statsmodels`.
- Compatible version ranges were recommended rather than exact environment pins.
- The incorrectly named `d1.gitignore` was identified for renaming to `.gitignore`.

Recommended dependency ranges:

```text
# Supported Python: 3.10–3.13
numpy>=1.24,<3
pandas>=2.0,<3
scipy>=1.10,<2
matplotlib>=3.7,<4
seaborn>=0.12,<1
openpyxl>=3.1,<4
scikit-learn>=1.3,<2
statsmodels>=0.14,<1
boto3>=1.28,<2
```

A future `requirements-lock.txt` should be produced only after all active validators have been run successfully in one controlled environment. A lock file generated before that would imply a validation status that has not been achieved.

## Versioning decision

The current public release remains **v1.0.0**.

The planned next release is **v1.0.1**, framed as a methodological correction rather than a claim of new positive evidence. The release tag must be created only after:

1. The candidate BALLADEER validator is run on the complete real dataset.
2. Generated metrics and plots are inspected.
3. README numerical statements and badges are updated to match the result.
4. `analysis_log.md`, `requirements.txt`, and `CITATION.cff` are finalized.
5. The repository reproduces from the final commit.

The existing `v1.0.0` tag must never be moved or overwritten. Until the real BALLADEER rerun occurs, the new code should be described as **candidate**, **unreleased**, or **not yet validated on the complete source dataset**.

## Current evidence status as of 17 July 2026

### Supported, with a major methodological qualification

- The historical BALLADEER v1.0.0 analysis found a commission-rate difference in the Decompensated Sprint anchor-defined cluster: p = 0.011 and empirical permutation p = 0.014.
- This is task-specific and partly circular because accuracy/commission-related information contributed to defining the groups later compared on commission errors.
- It remains reportable as a historical result, not as clean confirmation of a biological subtype.

### Directionally consistent but corrected-nonsignificant

- HYPERAKTIV produced p = 0.0312 and permutation p = 0.0420 in the analogous cluster.
- It did not pass Bonferroni α = 0.0167.
- Its comparison group contains other psychiatric diagnoses and is not a confirmed-healthy control group.

### Null conceptual replication

- UCLA CNP found no significant ADHD-control differences in median go RT, robust go-RT variability, omissions, or SSRT.
- UCLA CNP found no significant evidence of greater ADHD dispersion.
- Its apparent two-component GMM solution failed the minimum-size gate because one component contained only one participant.

### Not supported

- BALLADEER Sprint-versus-Crash within-session trajectory difference: interaction p = 0.847, with substantial missing-block limitations.
- A task-general discrete two-subtype interpretation across all three datasets.
- A clear BALLADEER EDA signature separating proposed subtypes.

### Exploratory but unconfirmed

- A continuous, context-sensitive multidimensional behavioral model.
- Within-person movement through behavioral states over days, weeks, or months.
- HBN Quotient-based links between attention, impulsivity, motion, and time-varying state.

### Untested

- Dopamine D1/D2 receptor states.
- ATP depletion or metabolic exhaustion.
- A causal allostatic mechanism.
- Medication response prediction.
- Diagnostic or treatment utility.

## Pending analyses and decision rules

1. **Real BALLADEER v1.0.1 rerun:** do not update the main numerical claim until complete source data are available and the candidate validator finishes successfully.
2. **HBN Quotient:** inspect exact columns before analysis; distinguish raw/block-level data from proprietary summary scores; record any post-access amendments.
3. **ATTLAPSE:** if access is granted, inspect license, exact file list, trial-level behavioral structure, group mapping, and whether behavior can be downloaded without EEG.
4. **OpenNeuro `ds003500`:** suitable as a fully open, close Go/No-Go pilot, but interpret low power explicitly.
5. **Longitudinal hypothesis:** requires repeated within-person sampling; single-session block plots cannot validate weeks-to-months cycles.
6. **No outcome switching:** missing data, alternative outcomes, exclusion rules, and multiplicity corrections must be set before inspecting significance.
7. **No forced labels:** a failed stability or size gate remains a failed clustering result.

## Final interpretation boundary

At this stage the repository documents an evolving exploratory hypothesis, not a validated disease model. The strongest responsible summary is:

> BALLADEER produced one task-specific, methodologically qualified positive result; HYPERAKTIV produced a corrected-nonsignificant trend; UCLA CNP produced a substantive cluster-free null result. Together they do not support permanent, task-general Sprint/Crash subtypes. A dimensional and state-sensitive reformulation is reasonable to test, but remains unconfirmed. No molecular mechanism, diagnostic application, or treatment implication has been established.

Negative and inconclusive results are retained because they define the limits of the hypothesis and reduce the risk of presenting an exploratory narrative as settled evidence.


## ADHD Pupil Dataset — fourth independent conceptual test

### Selection rationale

After the UCLA CNP cluster-free null, the Figshare ADHD Pupil Dataset (`7218725`, version 3) was selected to test a different but related construct: behavioral stability during visuospatial working memory rather than adaptive stopping. It provides trial-level reaction time and accuracy, ADHD and control groups, and paired off/on-methylphenidate sessions for a subset. This is an independent conceptual test of the broad behavioral-instability premise, not an exact Go/No-Go replication.

Dataset source and attribution:

- Figshare DOI: `10.6084/m9.figshare.7218725`.
- Data descriptor: `10.1038/s41597-019-0037-2`.
- License: CC BY 4.0.
- Official file: `Pupil_dataset.mat`, 1,257,809,856 bytes.
- Official MD5: `d4a1e92c8e125e93831f12797a783d52`.
- Verified SHA-256: `44aa997e37815e7d2a003a4fc4e967f69438a86bdf04650b02f37aaa2a81819b`.

### Validator-development chronology

The first validator versions were written from the public description before the actual MATLAB object layout had been inspected. Several failures were corrected and are retained here rather than hidden:

1. A partial download was initially accepted as complete; SciPy reported a truncated MAT file. Official size and MD5 verification were added.
2. The source was MATLAB 7.3 with an HDF5 user block, not an ordinary pre-7.3 MAT file.
3. Actual names differed from the prose description: `Pupil_data`, `Task_epocs`, and `Wisc`.
4. `Task_epocs` consisted of MATLAB MCOS table objects represented by `(1, 6) uint32` headers with `MATLAB_object_decode = 3`.
5. SciPy cannot open MATLAB 7.3, standard `mat73` cannot reconstruct MCOS tables, and ordinary `h5py` exposes only headers and references.
6. A targeted HDF5 inspector confirmed 67 references for `Subject`, `Age`, `Group`, `Task_epocs`, and `Wisc`.
7. `mat73-reader==0.1.0`, specifically designed for MATLAB 7.3 MCOS tables, successfully decoded the trial tables into pandas DataFrames.

The real file produced the expected structure:

- 50 unique participants;
- 67 sessions;
- 28 off-medication ADHD sessions;
- 22 control sessions;
- 17 paired on-medication ADHD sessions;
- 160 trials per session;
- 10,720 total trials;
- columns `Trial`, `Load`, `Distractor`, `CorrResponse`, `Perform`, `Rtime`, and `Pupil`.

### Initial successful run and scoring correction

Validator `0.1.5-candidate` completed the first successful real-data run. Review showed 796 missing `Perform` values. The initial successful run excluded them from the accuracy denominator. Missingness was uneven:

- ADHD off: 478 / 4,480 trials = 10.67%;
- ADHD on: 127 / 2,720 trials = 4.67%;
- controls: 191 / 3,520 trials = 5.43%.

Because `Perform` is documented as 1 for correct and 0 for incorrect, missing values were conservatively reclassified as no-response/omission errors. A second issue was corrected: `Distractor` had four levels (`3`, `4`, `5`, `6`), while the first script assumed a two-level contrast.

### Corrected validator `0.2.0-candidate`

The corrected analysis implemented:

- missing `Perform` scored as no-response error;
- accuracy calculated over all trials;
- `error_rate = 1 - accuracy` retained descriptively but not tested as a duplicate primary endpoint;
- omission rate tested separately;
- four-level `Distractor` treated categorically;
- order-invariant max-minus-min ranges used as secondary modulation endpoints;
- condition-level output for load and distractor levels;
- cluster-free primary analysis;
- ADHD-only RT-derived GMM with BIC, silhouette, minimum-size, and bootstrap-ARI gates;
- pupil vectors excluded from the reported primary behavioral analysis;
- stale failure traces removed before successful packaging.

Inferential settings:

- 5,000 permutations;
- 2,000 bootstrap repetitions;
- seed `20260717`;
- RT window 100–5,000 ms;
- minimum 20 valid correct-RT trials;
- Mann–Whitney, rank-biserial, bootstrap median-difference intervals, Brown–Forsythe, and Holm correction;
- paired Wilcoxon and sign-permutation analyses for medication sessions.

### Corrected cluster-free results

Primary comparison: 28 off-medication ADHD participants versus 22 controls.

Median correct RT did not differ:

- difference: −19.5 ms;
- permutation p = 0.4479;
- Holm p = 0.4479;
- Brown–Forsythe p = 0.1371.

Robust RT variability was greater in ADHD:

- RT MAD difference: +61.75 ms; permutation p = 0.0022; Holm p = 0.0088; Brown–Forsythe p < 0.00001.
- RT IQR difference: +99.625 ms; permutation p = 0.0024; Holm p = 0.0088; Brown–Forsythe p = 0.000052.

Accuracy was lower when no-response trials were scored as errors:

- difference: −0.275;
- permutation p = 0.0002;
- Holm p = 0.0010;
- Brown–Forsythe p = 0.0676.

Median omission rate was not significant after correction:

- difference: +0.0375;
- permutation p = 0.1054;
- Holm p = 0.2108.

Omission-rate dispersion differed (Brown–Forsythe p = 0.0119), but a dispersion result is not a median group difference and does not establish a subtype.

### Secondary condition and temporal results

No temporal or load endpoint survived correction:

- RT slope: Holm p = 1.0;
- error slope: Holm p = 0.6479;
- load RT contrast: Holm p = 1.0;
- load accuracy contrast: Holm p = 1.0.

Four-level distractor modulation was larger descriptively in ADHD but did not survive Holm correction:

- distractor RT-range difference: +48.25 ms; nominal p = 0.0392; Holm p = 0.2352;
- distractor accuracy-range difference: +0.50; nominal p = 0.0190; Holm p = 0.1330;
- distractor omission range: Holm p = 1.0.

These are exploratory signals. Range statistics quantify modulation magnitude and do not identify a directional ordered effect.

### Paired medication results

Seventeen ADHD participants had both off- and on-methylphenidate sessions. No endpoint survived Holm correction:

- median RT: +58 ms; paired permutation p = 0.0710; Holm p = 0.5679;
- RT MAD: −17 ms; paired permutation p = 0.0720; Holm p = 0.5679;
- RT IQR: −20.5 ms; paired permutation p = 0.2613; Holm p = 1.0;
- accuracy: +0.0125; paired permutation p = 0.6161; Holm p = 1.0;
- omission rate: −0.0187; paired permutation p = 0.4189; Holm p = 1.0;
- distractor RT range: −45 ms; paired permutation p = 0.2589; Holm p = 1.0.

The descriptive reduction in RT MAD is insufficient evidence of a medication effect.

### Exploratory clustering

The ADHD-only GMM failed one or more required gates:

```text
stable_two_cluster = False
```

Figure colors remain exploratory numeric assignments, not Sprint/Crash labels.

### Interpretation after the fourth dataset

ADHD Pupil provides independent support for the broad behavioral premise that ADHD-related impairment can involve unstable performance rather than uniform slowing. Similar median RT combined with greater robust RT variability and lower accuracy is consistent with impaired stability of cognitive performance.

This strengthens the general behavioral premise and dimensional reformulation, but does not prove the full hypothesis:

- UCLA remains a substantive null in an adult Stop-Signal task.
- Increased variability is task- and context-dependent, not universal.
- Stable discrete components again failed.
- Pupil dynamics were not analyzed in the reported run.
- Medication endpoints were corrected-nonsignificant.
- No receptor, neurotransmitter, ATP, metabolic, neural, or causal allostatic variable was measured.

The strongest responsible synthesis is:

> Across four independent datasets, evidence is heterogeneous but no longer reducible to one isolated positive result. The ADHD Pupil working-memory task independently shows greater behavioral instability and lower accuracy without uniform slowing. This strengthens a task-dependent dimensional behavioral-instability formulation, while permanent discrete subtypes and the proposed biological mechanism remain unsupported or untested.

## Repository update after ADHD Pupil

The candidate update adds:

```text
scripts/ADHD_PUPIL_VALIDATOR.py
images/adhd_pupil_group_distributions.png
images/adhd_pupil_medication_pairs.png
images/adhd_pupil_dimensional_spectrum.png
docs/results/adhd_pupil/adhd_pupil_academic_diagnostic.txt
docs/results/adhd_pupil/adhd_pupil_analysis_config.json
docs/results/adhd_pupil/adhd_pupil_reproducibility_log.txt
docs/results/adhd_pupil/RESULTS.md
```

The 1.258 GB source MAT file and participant-level raw exports are not included.

## Superseding evidence status — 17 July 2026

### Independently supported at the behavioral level

- ADHD Pupil: greater RT MAD and IQR after Holm correction, lower all-trial accuracy, and no significant median-RT difference.

### Historical positive with methodological qualification

- BALLADEER v1.0.0: p = 0.011 and permutation p = 0.014 within an anchor-defined cluster; partial circularity prevents clean subtype validation.

### Corrected-nonsignificant

- HYPERAKTIV analogous cluster result.
- ADHD Pupil paired medication effects.
- ADHD Pupil temporal, load, and distractor-range endpoints after Holm correction.

### Substantive null conceptual replication

- UCLA CNP cluster-free Stop-Signal outcomes and dispersion tests.

### Not supported

- Stable task-general Sprint/Crash subtypes.
- BALLADEER Sprint-versus-Crash trajectory interaction.
- A clear physiological signature separating proposed categories.

### Untested

- Pupil-linked arousal in the reported ADHD Pupil run.
- Dopamine D1/D2 receptor states.
- ATP depletion or metabolic exhaustion.
- Causal allostatic dynamics.
- Diagnostic, prognostic, or treatment utility.

## Updated versioning decision

The public release remains `v1.0.0`. Because this bundle adds a fourth dataset, a substantial validator, corrected scoring, three figures, and a revised synthesis, the appropriate next release is a minor release candidate (`v1.1.0`), not a patch-only `v1.0.1`.

No tag should be created until:

1. The candidate bundle is placed into the repository and paths are verified.
2. README images render correctly on GitHub.
3. Validator and artifact hashes are recorded.
4. The final commit is archived and citation metadata are updated.
5. The pending BALLADEER cluster-free rerun remains clearly labeled pending.

The existing `v1.0.0` tag must not be moved.
