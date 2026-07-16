# Allostatic Sprint Hypothesis — Exploring Impulsivity Heterogeneity in ADHD

<p align="center">
  <a href="https://doi.org/10.5281/zenodo.21304761"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.21304761.svg" alt="DOI"></a>
  <img src="https://img.shields.io/badge/status-exploratory-orange" alt="status">
  <img src="https://img.shields.io/badge/peer--reviewed-no-red" alt="not peer reviewed">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="license">
  <img src="https://img.shields.io/badge/python-3.x-blue" alt="python">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/BALLADEER%20impulsivity-p%3D0.011%20✓-brightgreen" alt="balladeer significant">
  <img src="https://img.shields.io/badge/HYPERAKTIV%20trend-p%3D0.031%2C%20ns-yellow" alt="hyperaktiv trend">
  <img src="https://img.shields.io/badge/UCLA%20CNP-group%20differences%20ns-lightgrey" alt="UCLA CNP group differences not significant">
  <img src="https://img.shields.io/badge/discrete%20subtypes-not%20supported-red" alt="discrete subtypes not supported">
  <img src="https://img.shields.io/badge/temporal%20dynamics-not%20supported-red" alt="temporal dynamics not supported">
  <img src="https://img.shields.io/badge/dimensional%20model-exploratory-orange" alt="dimensional model exploratory">
  <img src="https://img.shields.io/badge/mechanism-untested-lightgrey" alt="mechanism untested">
</p>

**Not a diagnostic or clinical tool.** Findings are preliminary, independently produced, and not peer reviewed. The project reports positive, null, and methodologically inconclusive results together; read the limitations before citing or reusing any claim.

## Overview

This project investigates whether ADHD-related performance on sustained-attention and response-inhibition tasks is behaviorally heterogeneous. It began with an informal **"Allostatic Sprint"** hypothesis proposing two contrasting patterns of decompensation: a relatively fast but disinhibited **Sprint-like** pattern and a slower, more variable **Crash-like** pattern.

Three independent public datasets have now been examined:

1. **HYPERAKTIV** — clinical CPT-II data, used for initial exploration.
2. **BALLADEER** — a CPT/go-no-go-like attention task with diagnostically clean neurotypical controls.
3. **UCLA CNP / OpenNeuro ds000030** — an adult Stop-Signal Task dataset used as a third, cluster-free conceptual test.

The evidence is mixed. BALLADEER contains a corrected, permutation-confirmed commission-error effect within one analysis-defined cluster. HYPERAKTIV shows a directionally similar but correction-nonsignificant trend. UCLA CNP shows no significant ADHD-control differences in go reaction time, reaction-time variability, omission rate, or stop-signal reaction time (SSRT), no significant increase in ADHD variance, and no acceptable two-cluster solution.

Accordingly, the current evidence does **not** establish two discrete, task-general ADHD subtypes. A more cautious possibility is a **continuous and context-dependent behavioral space**—for example, speed, variability, caution, and inhibitory control as partially independent dimensions—rather than permanent categories. This dimensional interpretation is a reformulation motivated by the accumulated results, not a confirmed finding.

## Current Evidence at a Glance

| Dataset | Comparison | Sample used in key test | Result | Interpretation |
|---|---|---:|---|---|
| BALLADEER | Pure ADHD vs pure control within the Decompensated Sprint cluster | 20 vs 20 | Mann–Whitney p = 0.011; permutation p = 0.014 | Significant task-specific commission-error effect; partially circular because accuracy contributed to cluster definition |
| HYPERAKTIV | ADHD vs clinical controls within the analogous cluster | 24 vs 11 | p = 0.031; permutation p = 0.042; Bonferroni α = 0.0167 | Directionally consistent trend, but not an independent corrected confirmation |
| UCLA CNP | All eligible ADHD vs healthy controls, cluster-free | 41 vs 126 | All primary group tests nonsignificant; all variance tests nonsignificant | No replication of a broad, task-general ADHD difference on Stop-Signal measures |
| UCLA CNP clustering | ADHD-only GMM using median go RT and go RT MAD | 41 ADHD | K = 2 isolated one participant (2.4%); minimum required share = 15% | Outlier-like component, not accepted as a discrete subtype |

## What the Data Show

### Supported within a specific task and analysis

- In the diagnostically clean BALLADEER subsample, the analysis-defined **Decompensated Sprint** cluster showed higher commission-error rates in ADHD than in confirmed non-ADHD controls: Mann–Whitney U, n = 20 vs 20, p = 0.011, surviving Bonferroni correction across three clusters (α = 0.0167), with rank-biserial r ≈ -0.465. A label-permutation test gave empirical p = 0.014.
- HYPERAKTIV showed the same direction of effect (p = 0.031, r = -0.462; empirical permutation p = 0.042), but the result did **not** cross the Bonferroni-corrected threshold. Its comparison group consists of participants with other psychiatric diagnoses, not confirmed-healthy controls. It is therefore reported as a trend, not a second significant replication.
- These task-specific observations are compatible with published ADHD literature describing reaction-time and commission-error heterogeneity. They do not, by themselves, establish new biological subtypes.

<table>
<tr>
<td width="50%"><img src="balladeer_impulsivity_by_subtype.png" alt="BALLADEER commission-error rate by analysis-defined subtype" width="100%"></td>
<td width="50%"><img src="balladeer_accuracy_by_subtype.png" alt="BALLADEER accuracy by analysis-defined subtype" width="100%"></td>
</tr>
</table>
<p align="center"><sub>BALLADEER descriptive plots. The clusters are analysis-defined and partly use accuracy; these figures are not evidence of separate neural or metabolic mechanisms.</sub></p>

### Not supported or not generalized

- **UCLA CNP cluster-free analysis:** ADHD and healthy-control participants did not differ significantly in median go RT (p = 0.282), go RT MAD (p = 0.728), go RT IQR (p = 0.802), go omission rate (p = 0.325), or SSRT (p = 0.709). Median SSRT was 206 ms in ADHD and 217 ms in controls; group means were nearly identical (224 vs 223 ms).
- **UCLA CNP variance tests:** Brown–Forsythe tests found no significant evidence of greater ADHD dispersion in median go RT (p = 0.766), go RT MAD (p = 0.399), go RT IQR (p = 0.480), or SSRT (p = 0.204).
- **UCLA CNP discrete clustering:** a two-component Gaussian mixture improved BIC and produced high silhouette separation, but the smaller component contained only one of 41 ADHD participants (2.4%). Because it failed the prespecified minimum-size criterion of 15%, it was treated as an outlier-like component rather than a subtype. No Sprint/Crash labels were assigned.
- **BALLADEER within-session trajectories:** the hypothesized difference in minute-scale commission-error trajectories between Sprint and Crash clusters was not supported (`commission ~ block × cluster`, Pure ADHD only, interaction p = 0.847). This test was underpowered because only 4 of 20 Sprint participants had complete four-block data.
- No clear physiological signature separating the BALLADEER clusters was found in available skin-conductance data.

<table>
<tr>
<td width="58%"><img src="ucla_cnp_group_distributions.png" alt="UCLA CNP cluster-free distributions of median go RT, go RT MAD, and SSRT" width="100%"></td>
<td width="42%"><img src="ucla_cnp_temporal_dynamics.png" alt="UCLA CNP descriptive within-session reaction-time dynamics" width="100%"></td>
</tr>
</table>
<p align="center"><sub>UCLA CNP conceptual replication. Left: ADHD-control distributions were highly overlapping and all primary tests were nonsignificant. Right: both groups slowed descriptively across four task blocks; no longitudinal phase claim can be inferred from a single session.</sub></p>

<p align="center">
  <img src="balladeer_eda_change_by_cohort.png" width="560" alt="BALLADEER skin-conductance change by cohort and subtype">
</p>
<p align="center"><sub>No clear BALLADEER skin-conductance pattern separated the proposed clusters. This negative result is retained rather than omitted.</sub></p>

## From Discrete Subtypes to a Dimensional Interpretation

The original cross-sectional implementation asked whether participants could be sorted into stable Sprint and Crash categories. The accumulated evidence does not support that strong categorical claim across tasks.

A weaker, dimensional formulation is now more plausible:

- **Speed:** faster ↔ slower responding.
- **Temporal stability:** consistent ↔ variable responding.
- **Response policy:** disinhibited ↔ cautious responding.
- **Inhibitory control:** shorter ↔ longer stopping latency.
- **State dependence:** position on these dimensions may vary with fatigue, motivation, medication, sleep, stress, and task demands.

Under this interpretation, Sprint-like and Crash-like patterns are descriptive poles, not diagnoses or immutable kinds of people. Most participants may occupy intermediate positions, and different tasks may reveal different projections of the same multidimensional behavioral space.

However, UCLA CNP did not show greater ADHD dispersion on the measured Stop-Signal variables. Therefore, the current results do not prove that ADHD occupies a broader dimensional spectrum than controls. Testing that proposal requires preregistered dimensional models across comparable tasks and, ideally, repeated measurement within the same individuals.

## Untested — Not Measured and Not Claimed as Fact

- **Dopaminergic or ATP-depletion mechanism.** D1/D2 receptor and ATP language remains a motivating metaphor. No receptor imaging, pharmacological manipulation, ATP measurement, or direct mechanistic validation was performed.
- **PRV-based physiological signature.** Pulse-rate variability was missing across all participants and activity sources in the available BALLADEER export. This is a data-availability gap, not evidence for or against the proposed mechanism.
- **Long-timescale cyclical dynamics.** The informal hypothesis proposes within-person movement between Sprint-like and Crash-like states over weeks or months. The personal durations that motivated this idea are single-case, self-reported observations—not dataset-derived estimates. All three datasets used here are cross-sectional or single-session for the present purposes. A valid test would require longitudinal repeated measurement, such as ecological momentary assessment or daily behavioral sampling over several months.

## Methodology

### HYPERAKTIV and BALLADEER legacy analyses

1. Participants were represented by task speed, speed variability, and accuracy.
2. They were assigned to the nearest z-scaled hypothesis anchor.
3. ADHD-control differences within clusters were evaluated with two-sided Mann–Whitney U tests, Bonferroni correction across clusters, effect sizes, and label-permutation checks.

**Known caveat:** accuracy/commission rate contributed to cluster definition and commission errors were subsequently compared across diagnostic groups within those clusters. The result is therefore partly circular: the outcome is related to a feature that helped construct the groups. The BALLADEER finding is retained, but interpreted as task-specific and methodologically qualified.

### UCLA CNP cluster-free and ADHD-only analysis

1. The primary analysis compared all eligible ADHD participants with all eligible healthy controls without assigning subtypes.
2. Participant metrics included median go RT, robust RT variability (MAD and IQR), omission rate, and integration-method SSRT when trial-level stop-signal delay was available.
3. Group location was tested with two-sided Mann–Whitney U, rank-biserial effect size, bootstrap confidence intervals, and median-difference permutation tests.
4. Group dispersion was tested with median-centered Brown–Forsythe tests.
5. Secondary clustering was restricted to ADHD participants and used only median go RT and go RT MAD. Diagnosis, control data, SSRT, and stop accuracy did not define clusters.
6. Gaussian mixture models with K = 1, 2, and 3 were compared. A two-cluster interpretation required all of the following: BIC improvement over K = 1 of at least 10; K = 2 best BIC among candidates; silhouette ≥ 0.25; each cluster ≥ 15% of the ADHD sample; and bootstrap median adjusted Rand index ≥ 0.60.
7. If those gates failed, the validator did not force subtype labels. SSRT remained a held-out validation outcome.

The UCLA analysis used 5,000 label permutations, 500 bootstrap repetitions, and a fixed random seed. Raw MRI data were never required.

## Datasets and Attribution

- **HYPERAKTIV** — Hicks et al. Open clinical CPT-II dataset used for initial exploration. Its control group is a *clinical control* group with other psychiatric diagnoses, not a confirmed-healthy sample. Check current license terms before reuse or redistribution.
- **BALLADEER** — Trujillo, Ferrer-Cascales, Teruel et al., *Scientific Data* (2026), [doi:10.1038/s41597-026-06758-7](https://doi.org/10.1038/s41597-026-06758-7). Includes diagnostically characterized ADHD, suspected ADHD, and neurotypical participants. Verify the data repository's current license independently from the article license before reuse or redistribution.
- **UCLA CNP / OpenNeuro ds000030** — Bilder, Poldrack, Cannon, London, Freimer, Congdon, Karlsgodt, Sabb, and colleagues, "A phenome-wide examination of neural and cognitive function," *Scientific Data* (2016), [doi:10.1038/sdata.2016.110](https://doi.org/10.1038/sdata.2016.110); [OpenNeuro ds000030](https://openneuro.org/datasets/ds000030). The present analysis downloaded only public tabular phenotype and Stop-Signal event files. The dataset is distributed under PDDL on OpenNeuro.

Raw participant data from these datasets are not redistributed in this repository. Only analysis code, aggregated results, diagnostics, and derived figures are included. Cite the original dataset publications and accessions when reusing the code or results.

## Limitations

- The project is exploratory, independently produced, and not peer reviewed or preregistered.
- BALLADEER and HYPERAKTIV contain small within-cluster comparisons and legacy forced-anchor classification.
- The BALLADEER commission-error result is partially circular because accuracy contributed to cluster definition.
- HYPERAKTIV uses clinical controls rather than confirmed-healthy controls.
- UCLA CNP is a conceptual rather than exact replication: an adult adaptive Stop-Signal Task is not equivalent to CPT-II or BALLADEER's attention task.
- UCLA CNP yielded a substantive null result, but absence of evidence in one task does not establish equivalence across every ADHD-relevant process.
- The UCLA validator did not use MRI and does not test neural mechanisms.
- Age, sex, medication, symptom severity, and comorbidity require dedicated sensitivity analyses before strong causal or clinical interpretation.
- Multiple analytic iterations create researcher degrees of freedom beyond the correction used within any single reported test.
- Cross-sectional and single-session data cannot test weeks-to-months cyclical state transitions.
- No direct physiological or molecular validation exists.

## Reproducing the Analyses

### Install dependencies

```bash
pip install pandas numpy scipy matplotlib seaborn scikit-learn boto3
```

### Run the validators

```bash
python scripts/CLINICAL_VALID_HYPERAKTIV.py
python scripts/HEALTHY_VALID_BALLADEER.py
python scripts/UCLA_CNP_VALIDATOR.py
```

The HYPERAKTIV validator can retrieve its public source files when they are not present locally. BALLADEER requires the original dataset in the directory structure documented in the script header. The UCLA CNP validator downloads only public tabular metadata and Stop-Signal event files from OpenNeuro's anonymous S3 mirror, excludes MRI by design, generates a reproducibility report, and deletes downloaded raw tables after a successful run unless `--keep-data` is specified.

### Google Colab

Upload `scripts/UCLA_CNP_VALIDATOR.py` to the Colab session and run:

```python
!python /content/UCLA_CNP_VALIDATOR.py
```

The validator creates `UCLA_CNP_VALID_output.zip` and initiates a browser download in Colab.

## Repository Outputs

Recommended derived UCLA files for version control:

```text
ucla_cnp_academic_diagnostic.txt
ucla_cnp_cluster_diagnostics.csv
ucla_cnp_group_distributions.png
ucla_cnp_temporal_dynamics.png
ucla_cnp_analysis_config.json
ucla_cnp_reproducibility_log.txt
```

Do not commit downloaded participant-level raw event files. Before publishing participant-level derived tables, verify that their redistribution is consistent with the dataset terms and your intended privacy standard.

## Interpretation Boundaries

This repository supports the following narrow conclusions:

- BALLADEER contains a significant, task-specific commission-error difference in one analysis-defined cluster.
- HYPERAKTIV contains a directionally consistent but corrected-nonsignificant trend.
- UCLA CNP does not show corresponding ADHD-control differences or an acceptable discrete two-cluster structure on the examined Stop-Signal measures.
- The three datasets do not establish permanent Sprint/Crash subtypes or a common biological mechanism.
- A dimensional, state-sensitive reformulation is scientifically reasonable to test next, but remains exploratory.

It does **not** support using these analyses for diagnosis, treatment selection, medication decisions, or claims about an individual's dopamine, ATP, receptor state, or metabolic condition.

## Acknowledgments

Developed iteratively with assistance from AI systems for coding, statistical guidance, visualization, and methodological critique. All conceptual direction, analytic decisions, interpretations, and errors remain the author's responsibility. AI-generated outputs were reviewed against the available data and corrected when problems were identified.

## License

Code in this repository: MIT License.

Data are not included and remain governed by the original datasets' licenses and terms. The code license does not override those terms.

## Author

D1D2DOPAMINE
