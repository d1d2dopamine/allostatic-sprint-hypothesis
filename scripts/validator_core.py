#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable validation core for behavioral and clinical research datasets.

This module extracts the stable, dataset-agnostic architecture shared by the
Allostatic Sprint validators. Dataset-specific parsing and scientific choices
remain in small adapter classes. The core deliberately does not encode ADHD,
Sprint/Crash labels, column names, clinical cutoffs, or a preferred outcome.

License: MIT (see repository LICENSE).
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import traceback
import urllib.request
import warnings
import zipfile
from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats

CORE_VERSION = "1.0.0"
DEFAULT_SEED = 20260717


# ---------------------------------------------------------------------------
# Configuration and run logging
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class GMMGates:
    """Acceptance gates for an exploratory two-component GMM."""

    bic_improvement_min: float = 10.0
    silhouette_min: float = 0.35
    minimum_cluster_share: float = 0.15
    bootstrap_median_ari_min: float = 0.70
    require_k2_best_bic: bool = True


@dataclasses.dataclass(frozen=True)
class CoreConfig:
    """Reproducibility and output settings shared by validators."""

    seed: int = DEFAULT_SEED
    n_permutations: int = 5_000
    n_bootstraps: int = 2_000
    gmm_bootstraps: int = 500
    alpha: float = 0.05
    min_group_n: int = 5
    output_dir: Path = Path("validator_output")
    raw_dir_name: str = "raw"
    keep_raw: bool = False
    gmm_gates: GMMGates = dataclasses.field(default_factory=GMMGates)


class RunLogger:
    """Console logger that retains an exact in-memory run transcript."""

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.lines: list[str] = []

    def log(self, *parts: Any) -> None:
        text = " ".join(str(x) for x in parts)
        self.lines.append(text)
        if self.verbose:
            print(text, flush=True)

    def write(self, path: Path) -> Path:
        atomic_write_text(path, "\n".join(self.lines) + "\n")
        return path


@dataclasses.dataclass
class RunContext:
    config: CoreConfig
    logger: RunLogger
    output_dir: Path
    raw_dir: Path
    started_at: str = dataclasses.field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat()
    )

    @classmethod
    def create(cls, config: CoreConfig, verbose: bool = True) -> "RunContext":
        output = Path(config.output_dir).expanduser().resolve()
        raw = output / config.raw_dir_name
        output.mkdir(parents=True, exist_ok=True)
        raw.mkdir(parents=True, exist_ok=True)
        return cls(config=config, logger=RunLogger(verbose), output_dir=output, raw_dir=raw)

    def metadata(self) -> dict[str, Any]:
        return {
            "core_version": CORE_VERSION,
            "started_at_utc": self.started_at,
            "python": sys.version,
            "platform": platform.platform(),
            "seed": self.config.seed,
            "n_permutations": self.config.n_permutations,
            "n_bootstraps": self.config.n_bootstraps,
            "gmm_bootstraps": self.config.gmm_bootstraps,
            "alpha": self.config.alpha,
        }


# ---------------------------------------------------------------------------
# Runtime, filesystem, integrity, downloads, and archives
# ---------------------------------------------------------------------------

def ensure_dependencies(requirements: Mapping[str, str], no_auto_install: bool = False) -> None:
    """Import required modules and optionally install missing pip distributions.

    ``requirements`` maps import names to pip requirement strings, for example
    ``{"sklearn": "scikit-learn>=1.3", "matplotlib": "matplotlib>=3.7"}``.
    """

    missing: list[str] = []
    for import_name, requirement in requirements.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(requirement)
    if not missing:
        return
    if no_auto_install:
        raise RuntimeError("Missing dependencies: " + ", ".join(missing))
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding=encoding, dir=path.parent, delete=False) as tmp:
        tmp.write(text)
        temp_name = tmp.name
    os.replace(temp_name, path)


def json_ready(value: Any) -> Any:
    """Convert common NumPy, pandas, dataclass, and Path values to JSON."""

    if dataclasses.is_dataclass(value):
        return json_ready(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_ready(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, pd.DataFrame):
        return json_ready(value.to_dict(orient="records"))
    if isinstance(value, pd.Series):
        return json_ready(value.tolist())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, value: Any) -> Path:
    atomic_write_text(path, json.dumps(json_ready(value), indent=2, ensure_ascii=False) + "\n")
    return path


def file_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.new(algorithm)
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    return file_hash(path, "sha256")


def md5_file(path: Path) -> str:
    return file_hash(path, "md5")


def verify_file(
    path: Path,
    *,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    expected_md5: str | None = None,
) -> dict[str, Any]:
    path = Path(path)
    result: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
    if not path.is_file():
        result["ok"] = False
        return result
    result["bytes"] = path.stat().st_size
    if expected_bytes is not None:
        result["bytes_match"] = result["bytes"] == expected_bytes
    if expected_sha256 is not None:
        result["sha256"] = sha256_file(path)
        result["sha256_match"] = result["sha256"].lower() == expected_sha256.lower()
    if expected_md5 is not None:
        result["md5"] = md5_file(path)
        result["md5_match"] = result["md5"].lower() == expected_md5.lower()
    checks = [v for k, v in result.items() if k.endswith("_match")]
    result["ok"] = bool(result["exists"] and all(checks))
    return result


def download_file(
    url: str,
    target: Path,
    *,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    expected_md5: str | None = None,
    timeout: int = 60,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """Download atomically and verify before replacing the destination."""

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "validator-core/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, partial.open("wb") as out:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
        check = verify_file(
            partial,
            expected_bytes=expected_bytes,
            expected_sha256=expected_sha256,
            expected_md5=expected_md5,
        )
        if not check["ok"]:
            raise ValueError("Downloaded file failed integrity checks: " + json.dumps(check))
        os.replace(partial, target)
        return target
    finally:
        with contextlib.suppress(FileNotFoundError):
            partial.unlink()


def find_file(names: str | Sequence[str], search_dirs: Sequence[Path]) -> Path | None:
    names = [names] if isinstance(names, str) else list(names)
    for directory in search_dirs:
        directory = Path(directory).expanduser()
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate.resolve()
    return None


def safe_extract_zip(zip_path: Path, destination: Path, members: Sequence[str] | None = None) -> list[Path]:
    """Extract selected members while rejecting path traversal."""

    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as archive:
        selected = archive.infolist() if members is None else [archive.getinfo(x) for x in members]
        for info in selected:
            target = (destination / info.filename).resolve()
            if destination != target and destination not in target.parents:
                raise ValueError(f"Unsafe archive member: {info.filename}")
            archive.extract(info, destination)
            if target.is_file():
                extracted.append(target)
    return extracted


def create_output_zip(output_dir: Path, zip_path: Path, exclude: Sequence[str] = ("raw",)) -> Path:
    output_dir, zip_path = Path(output_dir), Path(zip_path)
    excluded = set(exclude)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file() or path.resolve() == zip_path.resolve():
                continue
            relative = path.relative_to(output_dir)
            if relative.parts and relative.parts[0] in excluded:
                continue
            archive.write(path, relative.as_posix())
    return zip_path


def write_sha256_manifest(root: Path, output_name: str = "MANIFEST_SHA256.txt") -> Path:
    root = Path(root).resolve()
    output = root / output_name
    lines: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p != output):
        lines.append(f"{sha256_file(path)}  ./{path.relative_to(root).as_posix()}")
    atomic_write_text(output, "\n".join(lines) + "\n")
    return output


# ---------------------------------------------------------------------------
# Data normalization and participant/session metrics
# ---------------------------------------------------------------------------

def normalize_name(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value) if ch.isalnum())


def find_column(frame: pd.DataFrame, aliases: Sequence[str], required: bool = True) -> str | None:
    normalized = {normalize_name(c): c for c in frame.columns}
    for alias in aliases:
        key = normalize_name(alias)
        if key in normalized:
            return str(normalized[key])
    if required:
        raise KeyError(f"None of the expected columns were found: {list(aliases)}")
    return None


def finite(values: Iterable[Any]) -> np.ndarray:
    array = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(float)
    return array[np.isfinite(array)]


def robust_mad(values: Iterable[Any], scale: float = 1.0) -> float:
    array = finite(values)
    if not len(array):
        return float("nan")
    median = np.median(array)
    return float(scale * np.median(np.abs(array - median)))


def linear_slope(x: Iterable[Any], y: Iterable[Any]) -> float:
    frame = pd.DataFrame({"x": x, "y": y}).apply(pd.to_numeric, errors="coerce").dropna()
    if len(frame) < 3 or frame["x"].nunique() < 2:
        return float("nan")
    return float(np.polyfit(frame["x"], frame["y"], 1)[0])


def condition_effect(
    frame: pd.DataFrame,
    condition: str,
    value: str,
    high: Any | None = None,
    low: Any | None = None,
) -> float:
    data = frame[[condition, value]].dropna()
    levels = list(pd.unique(data[condition]))
    if len(levels) < 2:
        return float("nan")
    low = min(levels) if low is None else low
    high = max(levels) if high is None else high
    a = finite(data.loc[data[condition] == high, value])
    b = finite(data.loc[data[condition] == low, value])
    return float(np.median(a) - np.median(b)) if len(a) and len(b) else float("nan")


def multilevel_range(frame: pd.DataFrame, condition: str, value: str) -> float:
    medians = frame.groupby(condition, dropna=True)[value].median().dropna()
    return float(medians.max() - medians.min()) if len(medians) >= 2 else float("nan")


def assign_equal_blocks(order: Sequence[Any], n_blocks: int = 4) -> np.ndarray:
    result = np.full(len(order), -1, dtype=int)
    valid = np.where(pd.notna(order))[0]
    valid = valid[np.argsort(np.asarray(order, dtype=object)[valid])]
    for block, indices in enumerate(np.array_split(valid, n_blocks), start=1):
        result[indices] = block
    return result


def basic_session_metrics(
    trials: pd.DataFrame,
    *,
    subject_col: str,
    group_col: str,
    rt_col: str,
    correct_col: str,
    order_col: str | None = None,
    session_col: str | None = None,
    condition_cols: Sequence[str] = (),
    rt_min: float | None = None,
    rt_max: float | None = None,
    min_valid_rt: int = 20,
    n_blocks: int = 4,
) -> pd.DataFrame:
    """Build robust participant/session metrics from normalized trial rows."""

    keys = [subject_col, group_col] + ([session_col] if session_col else [])
    rows: list[dict[str, Any]] = []
    for key, part in trials.groupby(keys, dropna=False, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, key))
        rt = pd.to_numeric(part[rt_col], errors="coerce")
        correct = part[correct_col].fillna(False).astype(bool)
        valid = correct & rt.notna()
        if rt_min is not None:
            valid &= rt >= rt_min
        if rt_max is not None:
            valid &= rt <= rt_max
        values = finite(rt[valid])
        row.update({
            "n_trials": int(len(part)),
            "n_valid_correct_rt": int(valid.sum()),
            "median_rt": float(np.median(values)) if len(values) else np.nan,
            "rt_mad": robust_mad(values),
            "rt_iqr": float(np.percentile(values, 75) - np.percentile(values, 25)) if len(values) else np.nan,
            "accuracy": float(correct.mean()) if len(correct) else np.nan,
            "error_rate": float(1.0 - correct.mean()) if len(correct) else np.nan,
            "omission_rate": float((~correct & rt.isna()).mean()) if len(correct) else np.nan,
            "eligible": bool(len(values) >= min_valid_rt),
        })
        order = part[order_col] if order_col else pd.Series(np.arange(len(part)), index=part.index)
        row["rt_slope_per_trial"] = linear_slope(order[valid], rt[valid])
        blocks = assign_equal_blocks(order.to_numpy(), n_blocks)
        for block in range(1, n_blocks + 1):
            mask = (blocks == block) & valid.to_numpy()
            block_values = finite(rt.to_numpy()[mask])
            row[f"block{block}_median_rt"] = float(np.median(block_values)) if len(block_values) else np.nan
            row[f"block{block}_rt_mad"] = robust_mad(block_values)
        for condition in condition_cols:
            row[f"{condition}_rt_range"] = multilevel_range(part.loc[valid], condition, rt_col)
            row[f"{condition}_accuracy_range"] = multilevel_range(
                part.assign(_correct_numeric=correct.astype(float)), condition, "_correct_numeric"
            )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_confounder(values: Iterable[Any]) -> dict[str, Any]:
    series = pd.Series(values).dropna()
    if series.empty:
        return {"n": 0}
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() >= 0.8:
        numeric = numeric.dropna()
        return {
            "n": int(len(numeric)),
            "median": float(numeric.median()),
            "iqr": float(numeric.quantile(0.75) - numeric.quantile(0.25)),
            "min": float(numeric.min()),
            "max": float(numeric.max()),
        }
    counts = series.astype(str).value_counts(dropna=False)
    return {"n": int(len(series)), "counts": counts.to_dict()}


# ---------------------------------------------------------------------------
# Statistical tests and multiplicity correction
# ---------------------------------------------------------------------------

def rank_biserial_from_u(u: float, n_first: int, n_second: int) -> float:
    """Rank-biserial effect; positive means larger values in the first group."""

    return float(2.0 * u / (n_first * n_second) - 1.0)


def permutation_median_difference(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    n_permutations: int = 5_000,
    seed: int = DEFAULT_SEED,
) -> tuple[float, float]:
    a, b = finite(first), finite(second)
    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan
    observed = float(np.median(a) - np.median(b))
    pooled = np.concatenate([a, b])
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(n_permutations):
        shuffled = rng.permutation(pooled)
        statistic = np.median(shuffled[: len(a)]) - np.median(shuffled[len(a) :])
        exceed += abs(statistic) >= abs(observed) - 1e-15
    return observed, float((exceed + 1) / (n_permutations + 1))


def bootstrap_median_difference(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    n_bootstraps: int = 2_000,
    seed: int = DEFAULT_SEED,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    a, b = finite(first), finite(second)
    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    values = np.empty(n_bootstraps)
    for i in range(n_bootstraps):
        values[i] = np.median(rng.choice(a, len(a), replace=True)) - np.median(
            rng.choice(b, len(b), replace=True)
        )
    tail = (1.0 - confidence) * 50.0
    low, high = np.percentile(values, [tail, 100.0 - tail])
    return float(np.median(a) - np.median(b)), float(low), float(high)


def paired_permutation_median(
    differences: Iterable[Any],
    *,
    n_permutations: int = 5_000,
    seed: int = DEFAULT_SEED,
) -> tuple[float, float]:
    delta = finite(differences)
    if len(delta) < 3:
        return np.nan, np.nan
    observed = float(np.median(delta))
    rng = np.random.default_rng(seed)
    values = np.empty(n_permutations)
    for i in range(n_permutations):
        values[i] = np.median(delta * rng.choice([-1, 1], len(delta), replace=True))
    p_value = (np.sum(np.abs(values) >= abs(observed) - 1e-15) + 1) / (n_permutations + 1)
    return observed, float(p_value)


def holm_adjust(p_values: Iterable[Any]) -> np.ndarray:
    p = np.asarray(list(p_values), dtype=float)
    adjusted = np.full(len(p), np.nan)
    valid = np.where(np.isfinite(p))[0]
    order = valid[np.argsort(p[valid])]
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, p[index] * (len(order) - rank)))
        adjusted[index] = running
    return adjusted


def bonferroni_adjust(p_values: Iterable[Any]) -> np.ndarray:
    p = np.asarray(list(p_values), dtype=float)
    valid_n = int(np.isfinite(p).sum())
    return np.where(np.isfinite(p), np.minimum(1.0, p * valid_n), np.nan)


def compare_independent_groups(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    first_name: str = "first",
    second_name: str = "second",
    config: CoreConfig = CoreConfig(),
    seed_offset: int = 0,
) -> dict[str, Any]:
    a, b = finite(first), finite(second)
    result: dict[str, Any] = {
        "first_group": first_name,
        "second_group": second_name,
        "n_first": len(a),
        "n_second": len(b),
    }
    if len(a) < config.min_group_n or len(b) < config.min_group_n:
        result.update({
            "status": "insufficient sample",
            "median_first": np.nan,
            "median_second": np.nan,
            "median_difference_first_minus_second": np.nan,
            "bootstrap_ci_low": np.nan,
            "bootstrap_ci_high": np.nan,
            "mannwhitney_u": np.nan,
            "mannwhitney_p": np.nan,
            "permutation_p": np.nan,
            "rank_biserial": np.nan,
            "brown_forsythe_f": np.nan,
            "brown_forsythe_p": np.nan,
        })
        return result
    u, mw_p = stats.mannwhitneyu(a, b, alternative="two-sided")
    difference, permutation_p = permutation_median_difference(
        a, b, n_permutations=config.n_permutations, seed=config.seed + seed_offset
    )
    _, ci_low, ci_high = bootstrap_median_difference(
        a, b, n_bootstraps=config.n_bootstraps, seed=config.seed + 10_000 + seed_offset
    )
    bf_stat, bf_p = stats.levene(a, b, center="median")
    result.update({
        "status": "ok",
        "median_first": float(np.median(a)),
        "median_second": float(np.median(b)),
        "median_difference_first_minus_second": difference,
        "bootstrap_ci_low": ci_low,
        "bootstrap_ci_high": ci_high,
        "mannwhitney_u": float(u),
        "mannwhitney_p": float(mw_p),
        "permutation_p": permutation_p,
        "rank_biserial": rank_biserial_from_u(float(u), len(a), len(b)),
        "brown_forsythe_f": float(bf_stat),
        "brown_forsythe_p": float(bf_p),
    })
    return result


def compare_metric_families(
    metrics: pd.DataFrame,
    *,
    group_col: str,
    first_group: Any,
    second_group: Any,
    families: Mapping[str, Sequence[str]],
    config: CoreConfig = CoreConfig(),
    correction: str = "holm",
    eligible_col: str | None = "eligible",
) -> pd.DataFrame:
    usable = metrics if eligible_col is None else metrics[metrics[eligible_col].fillna(False)]
    rows: list[dict[str, Any]] = []
    counter = 0
    for family, columns in families.items():
        for metric in columns:
            result = compare_independent_groups(
                usable.loc[usable[group_col] == first_group, metric],
                usable.loc[usable[group_col] == second_group, metric],
                first_name=str(first_group),
                second_name=str(second_group),
                config=config,
                seed_offset=counter,
            )
            result.update({"family": family, "metric": metric})
            rows.append(result)
            counter += 1
    output = pd.DataFrame(rows)
    output["adjusted_permutation_p"] = np.nan
    adjust = holm_adjust if correction.lower() == "holm" else bonferroni_adjust
    for family in families:
        indices = output.index[output["family"] == family]
        output.loc[indices, "adjusted_permutation_p"] = adjust(output.loc[indices, "permutation_p"])
    return output


def compare_paired(
    before: Iterable[Any],
    after: Iterable[Any],
    *,
    config: CoreConfig = CoreConfig(),
    seed_offset: int = 0,
) -> dict[str, Any]:
    pair = pd.DataFrame({"before": before, "after": after}).apply(pd.to_numeric, errors="coerce").dropna()
    delta = pair["after"] - pair["before"]
    result: dict[str, Any] = {"n_pairs": len(pair)}
    if len(pair) < 3:
        result["status"] = "insufficient pairs"
        return result
    try:
        wilcoxon_stat, wilcoxon_p = stats.wilcoxon(pair["after"], pair["before"], alternative="two-sided")
    except ValueError:
        wilcoxon_stat, wilcoxon_p = 0.0, 1.0
    observed, permutation_p = paired_permutation_median(
        delta, n_permutations=config.n_permutations, seed=config.seed + seed_offset
    )
    rng = np.random.default_rng(config.seed + 10_000 + seed_offset)
    boot = [np.median(rng.choice(delta, len(delta), replace=True)) for _ in range(config.n_bootstraps)]
    low, high = np.percentile(boot, [2.5, 97.5])
    result.update({
        "status": "ok",
        "median_before": float(pair["before"].median()),
        "median_after": float(pair["after"].median()),
        "median_delta_after_minus_before": observed,
        "bootstrap_ci_low": float(low),
        "bootstrap_ci_high": float(high),
        "wilcoxon_stat": float(wilcoxon_stat),
        "wilcoxon_p": float(wilcoxon_p),
        "paired_permutation_p": permutation_p,
    })
    return result


# ---------------------------------------------------------------------------
# Exploratory clustering with explicit stability gates
# ---------------------------------------------------------------------------

def gated_gmm(
    frame: pd.DataFrame,
    *,
    feature_cols: Sequence[str],
    config: CoreConfig = CoreConfig(),
    min_rows: int = 15,
    heldout_cols: Sequence[str] = (),
    k_values: Sequence[int] = (1, 2, 3),
) -> dict[str, Any]:
    """Fit exploratory GMMs without turning failed components into subtypes."""

    try:
        from sklearn.cluster import adjusted_rand_score
        from sklearn.mixture import GaussianMixture
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import RobustScaler
    except ImportError as exc:
        raise RuntimeError("gated_gmm requires scikit-learn") from exc

    data = frame.copy().reset_index(drop=True)
    usable_features = [
        name for name in feature_cols
        if name in data and data[name].notna().sum() >= max(8, math.ceil(0.75 * len(data)))
    ]
    outcome: dict[str, Any] = {
        "stable_two_cluster": False,
        "reason": "",
        "features": usable_features,
        "participants": data,
        "diagnostics": pd.DataFrame(),
    }
    if len(data) < min_rows or len(usable_features) < 2:
        outcome["reason"] = "insufficient participants or usable features"
        return outcome

    values = data[usable_features].apply(pd.to_numeric, errors="coerce")
    values = values.fillna(values.median())
    scaler = RobustScaler(quantile_range=(25, 75))
    scaled = scaler.fit_transform(values)
    models: dict[int, Any] = {}
    labels: dict[int, np.ndarray] = {}
    diagnostics: list[dict[str, Any]] = []
    for k in k_values:
        if len(data) <= k * 3:
            continue
        model = GaussianMixture(
            n_components=k,
            covariance_type="full",
            n_init=50,
            random_state=config.seed,
            reg_covar=1e-5,
        ).fit(scaled)
        prediction = model.predict(scaled)
        models[k], labels[k] = model, prediction
        silhouette = (
            silhouette_score(scaled, prediction)
            if k > 1 and len(np.unique(prediction)) > 1
            else np.nan
        )
        diagnostics.append({
            "k": k,
            "bic": float(model.bic(scaled)),
            "aic": float(model.aic(scaled)),
            "silhouette": float(silhouette) if np.isfinite(silhouette) else np.nan,
            "minimum_cluster_share": float(np.bincount(prediction, minlength=k).min() / len(data)),
        })
    table = pd.DataFrame(diagnostics)
    outcome["diagnostics"] = table
    if 1 not in models or 2 not in models:
        outcome["reason"] = "K=1 or K=2 model unavailable"
        return outcome

    reference = labels[2]
    rng = np.random.default_rng(config.seed)
    ari_scores: list[float] = []
    for i in range(config.gmm_bootstraps):
        indices = rng.choice(len(scaled), len(scaled), replace=True)
        if len(np.unique(indices)) < max(6, scaled.shape[1] * 3):
            continue
        try:
            model = GaussianMixture(
                n_components=2,
                covariance_type="full",
                n_init=20,
                random_state=config.seed + i + 1,
                reg_covar=1e-5,
            ).fit(scaled[indices])
            ari_scores.append(float(adjusted_rand_score(reference, model.predict(scaled))))
        except Exception:
            continue

    gates = config.gmm_gates
    bic_gain = float(models[1].bic(scaled) - models[2].bic(scaled))
    silhouette = float(table.loc[table["k"] == 2, "silhouette"].iloc[0])
    minimum_share = float(np.bincount(reference, minlength=2).min() / len(data))
    median_ari = float(np.median(ari_scores)) if ari_scores else np.nan
    k2_bic = float(models[2].bic(scaled))
    k3_bic = float(models[3].bic(scaled)) if 3 in models else np.nan
    gate_results = {
        "bic_improvement": bic_gain >= gates.bic_improvement_min,
        "k2_best_bic": (not gates.require_k2_best_bic) or (not np.isfinite(k3_bic)) or k2_bic <= k3_bic,
        "silhouette": silhouette >= gates.silhouette_min,
        "minimum_cluster_share": minimum_share >= gates.minimum_cluster_share,
        "bootstrap_stability": np.isfinite(median_ari) and median_ari >= gates.bootstrap_median_ari_min,
    }
    stable = bool(all(gate_results.values()))
    data["exploratory_gmm_label"] = reference
    outcome.update({
        "stable_two_cluster": stable,
        "reason": "all gates passed" if stable else "failed gates: " + ", ".join(k for k, v in gate_results.items() if not v),
        "participants": data,
        "gates": gate_results,
        "bic_improvement_k1_minus_k2": bic_gain,
        "bic_k2": k2_bic,
        "bic_k3": k3_bic,
        "silhouette_k2": silhouette,
        "minimum_cluster_share_k2": minimum_share,
        "bootstrap_median_ari_k2": median_ari,
        "valid_bootstraps": len(ari_scores),
        "scaler_center": scaler.center_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "centers_original": scaler.inverse_transform(models[2].means_).tolist(),
    })

    heldout: list[dict[str, Any]] = []
    for column in heldout_cols:
        if column not in data:
            continue
        heldout.append({
            "metric": column,
            **compare_independent_groups(
                data.loc[data["exploratory_gmm_label"] == 0, column],
                data.loc[data["exploratory_gmm_label"] == 1, column],
                first_name="component_0",
                second_name="component_1",
                config=config,
            ),
            "confirmatory": False,
            "interpret_only_if_stable": True,
        })
    outcome["heldout_comparisons"] = pd.DataFrame(heldout)
    return outcome


# ---------------------------------------------------------------------------
# Generic plots and reports
# ---------------------------------------------------------------------------

def save_distribution_plot(
    frame: pd.DataFrame,
    *,
    metric: str,
    group: str,
    path: Path,
    title: str | None = None,
    ylabel: str | None = None,
) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.violinplot(data=frame, x=group, y=metric, inner=None, cut=0, color="#DDEBFA", ax=ax)
    sns.boxplot(data=frame, x=group, y=metric, width=0.25, color="white", fliersize=0, ax=ax)
    sns.stripplot(data=frame, x=group, y=metric, color="#2C2C2B", alpha=0.65, jitter=0.18, ax=ax)
    ax.set_title(title or metric)
    ax.set_xlabel("")
    ax.set_ylabel(ylabel or metric)
    sns.despine(ax=ax)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return Path(path)


def save_paired_plot(
    frame: pd.DataFrame,
    *,
    subject: str,
    condition: str,
    value: str,
    path: Path,
    condition_order: Sequence[Any],
    title: str | None = None,
) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    wide = frame.pivot_table(index=subject, columns=condition, values=value, aggfunc="median")
    wide = wide.dropna(subset=list(condition_order))
    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(len(condition_order))
    for _, row in wide.iterrows():
        ax.plot(x, [row[c] for c in condition_order], color="#7D7A75", alpha=0.45, marker="o")
    ax.set_xticks(x, [str(c) for c in condition_order])
    ax.set_title(title or value)
    ax.set_ylabel(value)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return Path(path)


def dataframe_markdown(frame: pd.DataFrame, max_rows: int = 50) -> str:
    """Render a compact Markdown table without an optional tabulate dependency."""

    if frame.empty:
        return "_No rows._"
    shown = frame.head(max_rows).copy()
    columns = [str(column) for column in shown.columns]

    def cell(value: Any) -> str:
        if pd.isna(value):
            return ""
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in shown.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
    if len(frame) > max_rows:
        lines.append(f"\n_Showing {max_rows} of {len(frame)} rows._")
    return "\n".join(lines)


def write_markdown_report(
    path: Path,
    *,
    title: str,
    summary: Sequence[str],
    sections: Mapping[str, str | pd.DataFrame],
    limitations: Sequence[str] = (),
) -> Path:
    lines = [f"# {title}", "", *[f"- {item}" for item in summary]]
    for heading, content in sections.items():
        lines += ["", f"## {heading}", ""]
        lines.append(dataframe_markdown(content) if isinstance(content, pd.DataFrame) else str(content))
    if limitations:
        lines += ["", "## Limitations", "", *[f"- {item}" for item in limitations]]
    atomic_write_text(Path(path), "\n".join(lines).rstrip() + "\n")
    return Path(path)


# ---------------------------------------------------------------------------
# Adapter lifecycle
# ---------------------------------------------------------------------------

class ValidatorAdapter(ABC):
    """Subclass this and implement only the dataset-specific hooks."""

    name = "unnamed-validator"
    version = "0.1.0"
    required_packages: Mapping[str, str] = {}

    def __init__(self, config: CoreConfig) -> None:
        self.config = config
        self.context = RunContext.create(config)

    def acquire(self) -> Any:
        """Download, locate, or return source paths. Optional hook."""
        return None

    @abstractmethod
    def load(self, source: Any) -> Any:
        """Read source data without performing scientific inference."""

    @abstractmethod
    def normalize(self, loaded: Any) -> pd.DataFrame:
        """Return a documented, tidy table with stable column names."""

    @abstractmethod
    def quality_control(self, normalized: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return analysis-ready rows and a QC table explaining exclusions."""

    @abstractmethod
    def compute_metrics(self, clean: pd.DataFrame) -> pd.DataFrame:
        """Return one analysis unit per row (usually participant/session)."""

    @abstractmethod
    def analyze(self, metrics: pd.DataFrame) -> Mapping[str, Any]:
        """Run preregistered/declared tests and exploratory analyses."""

    def render(self, artifacts: Mapping[str, Any]) -> Sequence[Path]:
        """Create reports and plots. Optional hook."""
        return []

    def run(self) -> dict[str, Any]:
        ctx = self.context
        ctx.logger.log(f"{self.name} v{self.version}; validator-core v{CORE_VERSION}")
        try:
            ensure_dependencies(self.required_packages)
            source = self.acquire()
            loaded = self.load(source)
            normalized = self.normalize(loaded)
            clean, qc = self.quality_control(normalized)
            metrics = self.compute_metrics(clean)
            analyses = dict(self.analyze(metrics))
            artifacts = {
                "source": source,
                "normalized": normalized,
                "clean": clean,
                "qc": qc,
                "metrics": metrics,
                "analyses": analyses,
            }
            rendered = list(self.render(artifacts))
            config_path = write_json(ctx.output_dir / "analysis_config.json", {
                "validator": self.name,
                "validator_version": self.version,
                "core": ctx.metadata(),
                "config": self.config,
            })
            log_path = ctx.logger.write(ctx.output_dir / "reproducibility_log.txt")
            return {**artifacts, "rendered": rendered + [config_path, log_path]}
        except Exception as exc:
            ctx.logger.log("FATAL:", repr(exc))
            ctx.logger.log(traceback.format_exc())
            ctx.logger.write(ctx.output_dir / "crash_log.txt")
            raise
        finally:
            if not self.config.keep_raw:
                shutil.rmtree(ctx.raw_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI and deterministic smoke test
# ---------------------------------------------------------------------------

def add_core_cli_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--output-dir", type=Path, default=Path("validator_output"))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--permutations", type=int, default=5_000)
    parser.add_argument("--bootstraps", type=int, default=2_000)
    parser.add_argument("--gmm-bootstraps", type=int, default=500)
    parser.add_argument("--keep-raw", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> CoreConfig:
    return CoreConfig(
        seed=args.seed,
        n_permutations=args.permutations,
        n_bootstraps=args.bootstraps,
        gmm_bootstraps=args.gmm_bootstraps,
        output_dir=args.output_dir,
        keep_raw=args.keep_raw,
    )


def self_test() -> dict[str, Any]:
    rng = np.random.default_rng(DEFAULT_SEED)
    first = rng.normal(0.4, 1.0, 30)
    second = rng.normal(0.0, 1.0, 35)
    config = CoreConfig(n_permutations=199, n_bootstraps=199, gmm_bootstraps=49)
    independent = compare_independent_groups(first, second, config=config)
    adjusted = holm_adjust([0.01, 0.04, 0.20])
    paired = compare_paired(first[:20], first[:20] + rng.normal(0.1, 0.3, 20), config=config)
    cluster_frame = pd.DataFrame({
        "speed": np.r_[rng.normal(-2, 0.3, 20), rng.normal(2, 0.3, 20)],
        "variability": np.r_[rng.normal(-1, 0.3, 20), rng.normal(1, 0.3, 20)],
        "heldout": rng.normal(size=40),
    })
    gmm = gated_gmm(
        cluster_frame,
        feature_cols=["speed", "variability"],
        heldout_cols=["heldout"],
        config=config,
    )
    assert independent["status"] == "ok"
    assert np.allclose(adjusted, [0.03, 0.08, 0.20])
    assert paired["status"] == "ok"
    assert len(gmm["diagnostics"]) >= 2
    return {
        "core_version": CORE_VERSION,
        "independent_group_test": independent,
        "holm_example": adjusted.tolist(),
        "paired_test": paired,
        "gmm_stable": gmm["stable_two_cluster"],
        "gmm_reason": gmm["reason"],
        "status": "PASS",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run deterministic synthetic checks")
    parser.add_argument("--json", action="store_true", help="print self-test output as JSON")
    args = parser.parse_args(argv)
    if not args.self_test:
        parser.print_help()
        return 0
    result = self_test()
    print(json.dumps(json_ready(result), indent=2) if args.json else "validator_core self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
