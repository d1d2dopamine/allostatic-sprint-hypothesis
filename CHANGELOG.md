# Changelog

All notable repository changes are documented here.

## [released] — v1.1.0 

### Added

- Fourth independent conceptual test using Figshare ADHD Pupil Dataset `7218725`.
- `scripts/ADHD_PUPIL_VALIDATOR.py` with public download, official size/MD5 verification, MATLAB 7.3 MCOS decoding, QC, cluster-free tests, paired medication tests, gated ADHD-only GMM, reports, figures, and Colab export.
- Corrected no-response/omission scoring for missing `Perform` values.
- Four-level categorical distractor summaries and order-invariant range endpoints.
- ADHD Pupil figures and aggregated diagnostic artifacts.
- `LICENSE-CONTENT.txt` with CC BY 4.0 terms for original non-code project material.
- `THIRD_PARTY_NOTICES.md` with dataset attribution, source, and licensing notes.
- `mat73-reader==0.1.0`, `h5py`, `mat73`, and `requests` dependencies.

### Changed

- README synthesis now covers four datasets.
- The main interpretation shifts from an unsupported categorical subtype model toward task-dependent dimensional behavioral instability.
- Next-release planning changes from patch-only `v1.0.1` to minor-release candidate `v1.1.0`.
- Citation metadata and dependency ranges updated.
- Repository licensing clarified: original code remains under MIT, while original documentation, figures, tables, and aggregated research outputs are under CC BY 4.0.
- README license badges, dataset-notice link, and validator commands updated.
- Historical BALLADEER reproduction instructions now point to the archived v1.0.0 validator; the uncompleted cluster-free candidate is not presented as a supported current run.

### Results

- ADHD off medication vs controls: no median-RT difference (Holm p = 0.4479).
- Greater RT MAD and IQR in ADHD (both Holm p = 0.0088).
- Lower all-trial accuracy in ADHD (Holm p = 0.0010).
- Omission-rate median difference nonsignificant (Holm p = 0.2108).
- No paired medication endpoint survived Holm correction.
- No acceptable stable two-component ADHD-only GMM.

### Unresolved

- Pupil time series were not analyzed in the reported primary run.
- The cluster-free BALLADEER candidate still lacks a complete real-data rerun.
- No release tag should be created until repository paths, rendered figures, hashes, and archived artifacts are reviewed.
