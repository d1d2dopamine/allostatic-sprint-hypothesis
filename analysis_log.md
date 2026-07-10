# Analysis Log

This is an honest chronology of how the methodology changed, including the mistakes and dead ends, not just the final version. Compiled from one collaborator's conversation history; earlier work done elsewhere with other tools may be missing — please fill gaps if you find them.

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

## Where this stands

- **Supported:** in BALLADEER (genuine neurotypical controls, clean cohort), a subgroup of ADHD participants shows significantly elevated commission rates (p = 0.011, permutation-confirmed p = 0.014). This is the one result that clears a pre-specified, corrected significance threshold.
- **Directionally consistent, but not independently significant:** the same pattern appears in HYPERAKTIV (p = 0.031 uncorrected, permutation p = 0.042) but does not clear the Bonferroni-corrected threshold, and the comparison group there is *clinical* controls (other diagnoses), not genuinely healthy people — a weaker test to begin with. Read this as a trend consistent with the BALLADEER finding, not as a second independent confirmation.
- **Not supported:** the two subtypes following different trajectories *over time* within a task (though the test may be underpowered rather than a clean null).
- **Untested:** any dopaminergic/ATP mechanism; PRV-based physiological signature (data unavailable).
- **Open methodological caveat:** cluster assignment partly uses accuracy/commission rate as an input, so the significant commission-rate finding in "Decompensated Sprint" is partially, not purely, independent of the clustering method itself. A cluster-free confirmation (e.g., mixed model on the unclustered sample) is a natural next step, not yet done.
