# Universal Validator Core Guide

`validator_core.py` is a reusable architecture and statistical utility layer extracted from the project’s HYPERAKTIV, BALLADEER, UCLA CNP, and ADHD Pupil validators. It is intended for researchers who want to build a transparent validator without redesigning downloading, integrity checks, quality control, reproducibility logging, robust group comparisons, paired tests, multiplicity correction, exploratory clustering gates, plots, reports, and output packaging each time.

The core is an engineering convenience, **not a substitute for scientific design**. A new validator still needs dataset-specific parsing, defensible inclusion rules, declared outcomes, appropriate comparison groups, and limitations.

## What the Core Includes

### Reproducible execution

- frozen configuration dataclasses;
- deterministic random seeds;
- permutation and bootstrap counts recorded in metadata;
- UTC run timestamps, Python version, and platform metadata;
- console logging with reproducibility and crash logs;
- atomic text and JSON writes;
- optional raw-data cleanup.

### Data acquisition and integrity

- atomic HTTP downloads;
- expected byte-size checks;
- MD5 and SHA-256 verification;
- local file discovery;
- safe ZIP extraction with path-traversal protection;
- output ZIP creation;
- repository/output SHA-256 manifest generation.

### Normalization and metrics

- alias-based column discovery;
- numeric coercion and finite-value filtering;
- median absolute deviation and IQR;
- accuracy, errors, omissions, and valid-RT counts;
- temporal slopes and equal-count task blocks;
- two-level condition effects;
- multilevel condition ranges;
- numeric and categorical confounder summaries.

### Statistical tests

- two-sided Mann–Whitney U;
- rank-biserial effect size with documented direction;
- median-difference permutation tests;
- bootstrap confidence intervals for median differences;
- Brown–Forsythe dispersion tests;
- paired Wilcoxon tests;
- paired sign-flip permutation tests;
- paired bootstrap confidence intervals;
- Holm and Bonferroni multiplicity correction;
- separate correction within declared endpoint families.

### Exploratory clustering

- robust feature scaling;
- Gaussian mixture models for `k = 1, 2, 3`;
- BIC and AIC diagnostics;
- silhouette diagnostics;
- minimum-component-size gate;
- bootstrap adjusted Rand index stability;
- optional requirement that `k = 2` outperform `k = 3` by BIC;
- held-out outcome comparisons;
- an explicit `stable_two_cluster` result that remains `False` if any gate fails.

The core never names components “Sprint,” “Crash,” “clinical subtype,” or any other scientific category automatically.

## Files

```text
scripts/validator_core.py
    Reusable implementation.

docs/VALIDATOR_CORE_GUIDE.md
    This guide.
```

A project-specific validator should normally remain a separate file:

```text
scripts/MY_DATASET_VALIDATOR.py
```

Do not copy the entire core into every validator. Import it so corrections to shared logic can be made once.

## Installation

The repository requirements already cover the main scientific stack. From the repository root:

```bash
python -m pip install -r requirements.txt
```

The core directly uses:

- NumPy;
- pandas;
- SciPy.

Clustering requires scikit-learn. Plotting requires Matplotlib and seaborn. Markdown table output uses pandas’ optional `tabulate` dependency if `DataFrame.to_markdown()` is called.

## Verify the Core

Run the deterministic synthetic smoke test:

```bash
python scripts/validator_core.py --self-test
```

For machine-readable output:

```bash
python scripts/validator_core.py --self-test --json
```

A passing smoke test checks independent-group statistics, Holm correction, paired statistics, and gated GMM execution. It does not validate a new dataset adapter or prove that an analysis is scientifically appropriate.

## Recommended Architecture

Every validator should have the following stages:

1. **Acquire** — locate or download source files and verify integrity.
2. **Load** — decode the source format without scientific filtering.
3. **Normalize** — produce stable, tidy columns.
4. **Quality control** — apply declared inclusion rules and record every exclusion.
5. **Compute metrics** — create one row per independent analysis unit.
6. **Analyze** — run declared primary, secondary, paired, and exploratory tests.
7. **Render** — save reports, tables, plots, configuration, and logs.

The `ValidatorAdapter` abstract class enforces this separation.

## Minimal Adapter Example

```python
#!/usr/bin/env python3
from pathlib import Path
import argparse
import pandas as pd

from validator_core import (
    CoreConfig,
    ValidatorAdapter,
    add_core_cli_arguments,
    basic_session_metrics,
    compare_metric_families,
    config_from_args,
    write_markdown_report,
)


class MyDatasetValidator(ValidatorAdapter):
    name = "my-dataset-validator"
    version = "0.1.0"

    def __init__(self, config: CoreConfig, input_csv: Path):
        super().__init__(config)
        self.input_csv = input_csv

    def acquire(self):
        # For public data, call download_file(...) here and provide an official
        # expected hash when one exists.
        return self.input_csv

    def load(self, source):
        return pd.read_csv(source)

    def normalize(self, loaded):
        # Rename source-specific fields exactly once. Downstream code should
        # use these stable names only.
        return loaded.rename(columns={
            "participant_id": "subject",
            "diagnostic_group": "group",
            "reaction_time_ms": "rt_ms",
            "is_correct": "correct",
            "trial_number": "trial",
        })

    def quality_control(self, normalized):
        required = ["subject", "group", "rt_ms", "correct", "trial"]
        missing = [c for c in required if c not in normalized]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        clean = normalized.copy()
        clean["rt_ms"] = pd.to_numeric(clean["rt_ms"], errors="coerce")
        clean["correct"] = clean["correct"].astype(bool)

        qc = pd.DataFrame([{
            "input_rows": len(normalized),
            "normalized_rows": len(clean),
            "missing_rt_rows": int(clean["rt_ms"].isna().sum()),
        }])
        return clean, qc

    def compute_metrics(self, clean):
        return basic_session_metrics(
            clean,
            subject_col="subject",
            group_col="group",
            rt_col="rt_ms",
            correct_col="correct",
            order_col="trial",
            rt_min=100,
            rt_max=5_000,
            min_valid_rt=20,
        )

    def analyze(self, metrics):
        tests = compare_metric_families(
            metrics,
            group_col="group",
            first_group="ADHD",
            second_group="Control",
            families={
                "primary": ["median_rt", "rt_mad", "accuracy"],
                "secondary": ["rt_slope_per_trial", "omission_rate"],
            },
            config=self.config,
            correction="holm",
        )
        return {"group_tests": tests}

    def render(self, artifacts):
        metrics_path = self.context.output_dir / "participant_metrics.csv"
        tests_path = self.context.output_dir / "group_tests.csv"
        report_path = self.context.output_dir / "REPORT.md"

        artifacts["metrics"].to_csv(metrics_path, index=False)
        artifacts["analyses"]["group_tests"].to_csv(tests_path, index=False)
        write_markdown_report(
            report_path,
            title="My Dataset Validator",
            summary=["Exploratory analysis; not a diagnostic tool."],
            sections={"Group tests": artifacts["analyses"]["group_tests"]},
            limitations=["Replace this with dataset-specific limitations."],
        )
        return [metrics_path, tests_path, report_path]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    add_core_cli_arguments(parser)
    args = parser.parse_args()
    validator = MyDatasetValidator(config_from_args(args), args.input_csv)
    validator.run()


if __name__ == "__main__":
    main()
```

Because the adapter is stored next to `validator_core.py`, the import works when the validator is executed as:

```bash
python scripts/MY_DATASET_VALIDATOR.py data.csv
```

## Using Integrity-Checked Downloads

```python
from validator_core import download_file, verify_file

path = download_file(
    "https://example.org/public-data.csv",
    self.context.raw_dir / "public-data.csv",
    expected_bytes=123456,
    expected_sha256="official_sha256_here",
)

check = verify_file(path, expected_sha256="official_sha256_here")
assert check["ok"]
```

Use an official checksum from the dataset host whenever possible. A checksum calculated only after downloading detects later corruption, but it does not independently authenticate the first download.

## Using Paired Tests

Pair observations by participant before calling the test:

```python
from validator_core import compare_paired

wide = sessions.pivot_table(
    index="subject",
    columns="condition",
    values="rt_mad",
    aggfunc="median",
).dropna(subset=["off", "on"])

result = compare_paired(
    wide["off"],
    wide["on"],
    config=self.config,
)
```

If several paired endpoints are tested, collect their permutation p-values and apply `holm_adjust()` within the declared family.

## Using Gated Exploratory Clustering

```python
from validator_core import gated_gmm

adhd = metrics[
    metrics["eligible"] & (metrics["group"] == "ADHD")
].copy()

clustering = gated_gmm(
    adhd,
    feature_cols=["median_rt", "rt_mad", "rt_iqr"],
    heldout_cols=["accuracy", "omission_rate"],
    config=self.config,
    min_rows=20,
)

print(clustering["stable_two_cluster"])
print(clustering["reason"])
```

Follow these rules:

- use only features justified before inspecting the cluster result;
- do not include diagnosis when clustering an already selected diagnostic group;
- keep confirmatory outcomes out of the clustering features;
- do not assign biological or clinical names when stability gates fail;
- treat held-out comparisons as exploratory unless the complete design supports stronger inference;
- save the diagnostics table and failed gates, not only the final labels.

## Modifying the Core

Modify the shared core only when a feature is genuinely dataset-agnostic.

### Appropriate core changes

- adding a general checksum algorithm;
- adding a reusable statistical test with documented assumptions;
- improving atomic output handling;
- adding a general correction method;
- fixing a seed, effect-direction, or missing-value bug;
- extending the adapter lifecycle without encoding a particular dataset.

### Changes that belong in an adapter

- source column mappings;
- diagnostic group normalization;
- reaction-time validity windows;
- minimum trial counts;
- clinical exclusions;
- medication definitions;
- task-specific SSRT calculation;
- pupil-signal decoding;
- BALLADEER archive/file discovery rules;
- HYPERAKTIV anchor definitions;
- scientific labels and interpretation.

### Compatibility policy

Before changing a public function:

1. add or update a synthetic test;
2. preserve the old argument behavior when practical;
3. increment `CORE_VERSION` for meaningful changes;
4. record the change in `CHANGELOG.md`;
5. rerun existing validators or explicitly state which ones were not rerun;
6. regenerate `MANIFEST_SHA256.txt` only after every release file is final.

## Scientific Guardrails

The core cannot determine whether:

- a hypothesis was preregistered;
- groups are clinically comparable;
- an outcome was selected after looking at significance;
- missing values represent omissions or absent recording;
- trials are statistically independent;
- a multiple-testing family was defined correctly;
- a dataset license permits redistribution;
- a cluster corresponds to a real biological subtype.

These decisions must be made and documented in the adapter, methods file, analysis log, and report.

## Why Keep a Project-Specific Core?

It is not necessary for the core to become a popular standalone package to be useful. Its immediate value is:

- eliminating inconsistent copies of the same statistical functions;
- making effect-size direction and random seeds consistent;
- reducing accidental differences between validators;
- making future methodological corrections easier to audit;
- giving readers a compact reference for the project’s shared architecture;
- providing a starting point that can be copied without copying dataset-specific claims.

If external users eventually adopt it, it can later be split into a separate package. Until then, keeping it inside this repository is simpler and more honest than presenting it as a mature general-purpose framework.

## Release Checklist

Before publishing a release containing the core:

- [ ] Run `python scripts/validator_core.py --self-test --json`.
- [ ] Compile the core and all active validators.
- [ ] Confirm that dataset-specific conclusions have not changed silently.
- [ ] Review generated configuration and reproducibility logs.
- [ ] Ensure README and CHANGELOG mention the core.
- [ ] Verify third-party notices and licenses.
- [ ] Regenerate `MANIFEST_SHA256.txt` after all files are final.
- [ ] Verify the manifest against the release directory.
- [ ] Never move or overwrite an existing release tag.
