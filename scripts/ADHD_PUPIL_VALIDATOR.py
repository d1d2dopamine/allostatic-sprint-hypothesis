# -*- coding: utf-8 -*-
"""
ADHD_PUPIL_VALIDATOR.py — cluster-free behavioral validator for the public
ADHD Pupil Size Dataset (Figshare record 7218725, version 3).

Default Colab workflow
-----------------------
    python ADHD_PUPIL_VALIDATOR.py

The script downloads the public 1.17 GB MATLAB file, extracts trial-level
behavior, performs ADHD-off-medication vs control analyses, performs paired
ADHD off/on methylphenidate analyses, writes reproducible tables/figures, and
packages all outputs. Raw data are deleted by default after a successful run.

Useful options
--------------
    python ADHD_PUPIL_VALIDATOR.py --keep-data
    python ADHD_PUPIL_VALIDATOR.py --data-file /content/Pupil_dataset.mat
    python ADHD_PUPIL_VALIDATOR.py --no-download
    python ADHD_PUPIL_VALIDATOR.py --self-test
    python ADHD_PUPIL_VALIDATOR.py --include-pupil

Methodological commitments
---------------------------
1. The primary analysis is cluster-free.
2. Controls are compared only with off-medication ADHD sessions.
3. Medication is tested within participant where both off/on sessions exist.
4. Exploratory ADHD-only GMMs use RT-derived features only; accuracy is held
   out. A discrete interpretation is rejected unless all stability gates pass.
5. No neural, dopaminergic, diagnostic, or causal mechanism is inferred from
   behavioral or pupil associations.

Dataset citation
----------------
Rojas-Libano D, Wainstein G, Ossandon T. Pupil Size, Eye-tracking and
Neuropsychological Dataset from ADHD-diagnosed and control participants
performing a cognitive task. Figshare. https://doi.org/10.6084/m9.figshare.7218725
License: CC BY 4.0. Cite the accompanying data descriptor before publication.

Author: D1D2DOPAMINE
Generated with AI assistance. Analytic decisions and interpretations require
independent human review.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import gzip
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import traceback
import warnings
import zipfile

SCRIPT_VERSION = "0.2.0-candidate"
DATASET_RECORD = "7218725"
DATASET_VERSION = 3
DATASET_DOI = "10.6084/m9.figshare.7218725"
DOWNLOAD_URL = "https://figshare.com/ndownloader/files/14298953"
EXPECTED_BYTES_APPROX = 1_170_000_000
SEED = 20260717
N_PERMUTATIONS = 5000
N_BOOTSTRAPS = 2000
GMM_BOOTSTRAPS = 300
RT_MIN_MS = 100.0
RT_MAX_MS = 5000.0
MIN_VALID_TRIALS = 20
MIN_GROUP_N = 8
GMM_BIC_IMPROVEMENT_MIN = 10.0
GMM_SILHOUETTE_MIN = 0.25
GMM_MIN_CLUSTER_SHARE = 0.15
GMM_BOOTSTRAP_ARI_MIN = 0.60

OUTPUT_FOLDER = "ADHD_PUPIL_VALID_output"
RAW_FOLDER = "ADHD_PUPIL_VALID_raw"
RAW_FILENAME = "adhd_pupil_dataset_v3.mat"
REPORT_NAME = "adhd_pupil_academic_diagnostic.txt"
LOG_NAME = "adhd_pupil_reproducibility_log.txt"
SESSION_NAME = "adhd_pupil_session_metrics.csv"
TRIAL_NAME = "adhd_pupil_trial_behavior.csv"
GROUP_NAME = "adhd_pupil_group_tests.csv"
MED_NAME = "adhd_pupil_medication_tests.csv"
CLUSTER_NAME = "adhd_pupil_gmm_diagnostics.csv"
QC_NAME = "adhd_pupil_quality_control.csv"
CONDITION_NAME = "adhd_pupil_condition_summary.csv"
CONFIG_NAME = "adhd_pupil_analysis_config.json"
GROUP_PLOT = "adhd_pupil_group_distributions.png"
MED_PLOT = "adhd_pupil_medication_pairs.png"
DIM_PLOT = "adhd_pupil_dimensional_spectrum.png"
ZIP_NAME = "ADHD_PUPIL_VALID_output.zip"

REQUIRED_PACKAGES = {
    "numpy": "numpy>=1.24,<3",
    "pandas": "pandas>=2,<4",
    "scipy": "scipy>=1.10,<2",
    "matplotlib": "matplotlib>=3.7,<4",
    "sklearn": "scikit-learn>=1.3,<2",
    "h5py": "h5py>=3.9,<4",
    "mat73": "mat73>=0.65,<1",
    "mat73_reader": "mat73-reader==0.1.0",
    "requests": "requests>=2.31,<3",
}

LOG_BUFFER: list[str] = []


def log(*parts) -> None:
    text = " ".join(str(x) for x in parts)
    print(text, flush=True)
    LOG_BUFFER.append(text)


def ensure_dependencies(no_auto_install=False):
    missing = []
    for module, package in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module)
        except Exception:
            missing.append(package)
    if not missing:
        return
    if no_auto_install:
        raise RuntimeError("Missing packages: " + ", ".join(missing))
    log("Installing missing packages:", ", ".join(missing))
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *missing])
    importlib.invalidate_caches()


def imports_after_bootstrap():
    global np, pd, stats, plt, h5py, requests, mat73, mcos_load
    global GaussianMixture, RobustScaler, silhouette_score, adjusted_rand_score
    import numpy as np
    import pandas as pd
    from scipy import stats
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import h5py
    import requests
    import mat73
    from mat73_reader import load as mcos_load
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import RobustScaler
    from sklearn.metrics import silhouette_score, adjusted_rand_score


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm_name(x) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(x).lower())


def scalar(x):
    if isinstance(x, np.ndarray):
        if x.size == 0:
            return np.nan
        if x.size == 1:
            return scalar(x.reshape(-1)[0])
    if isinstance(x, np.generic):
        return x.item()
    return x


def text_value(x) -> str:
    x = scalar(x)
    if x is None:
        return ""
    if isinstance(x, bytes):
        return x.decode("utf-8", "replace")
    if isinstance(x, np.ndarray) and x.dtype.kind in "US":
        return "".join(x.astype(str).reshape(-1)).strip()
    return str(x).strip()


def finite(x):
    a = pd.to_numeric(pd.Series(x), errors="coerce").to_numpy(float)
    return a[np.isfinite(a)]


def robust_mad(x):
    x = finite(x)
    return float(np.median(np.abs(x - np.median(x)))) if len(x) else np.nan


def slope(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3 or np.unique(x[ok]).size < 2:
        return np.nan
    return float(np.polyfit(x[ok], y[ok], 1)[0])


def is_colab():
    return "google.colab" in sys.modules or os.environ.get("COLAB_RELEASE_TAG") is not None


def remote_file_size(url: str):
    """Return authoritative payload size using a one-byte range request."""
    try:
        with requests.get(url, stream=True, timeout=(30, 90),
                          headers={"Range": "bytes=0-0"}, allow_redirects=True) as r:
            r.raise_for_status()
            content_range = r.headers.get("Content-Range", "")
            match = re.search(r"/(\d+)$", content_range)
            if match:
                return int(match.group(1))
            length = r.headers.get("Content-Length")
            return int(length) if length and r.status_code == 200 else None
    except Exception as exc:
        log("Could not query remote file size:", type(exc).__name__, str(exc)[:180])
        return None


def figshare_file_metadata():
    """Read official size/checksum instead of trusting a partial HTTP response."""
    api_url = "https:" + "//api.figshare.com/v2/articles/" + DATASET_RECORD
    try:
        r = requests.get(api_url, timeout=(30, 90))
        r.raise_for_status()
        files = r.json().get("files", [])
        item = next((x for x in files if str(x.get("id")) == "14298953"), None)
        if item is None and len(files) == 1:
            item = files[0]
        if item:
            return {
                "size": int(item["size"]) if item.get("size") is not None else None,
                "md5": item.get("computed_md5") or item.get("supplied_md5"),
                "download_url": item.get("download_url") or DOWNLOAD_URL,
                "name": item.get("name"),
            }
    except Exception as exc:
        log("Could not query Figshare metadata API:", type(exc).__name__, str(exc)[:180])
    return {}


def ensure_complete_download(url: str, target: Path, no_download=False):
    """Download/resume and verify the official Figshare size plus MD5."""
    metadata = figshare_file_metadata() if not no_download else {}
    effective_url = metadata.get("download_url") or url
    remote = metadata.get("size") or (remote_file_size(effective_url) if not no_download else None)
    expected_md5 = metadata.get("md5")
    local = target.stat().st_size if target.exists() else 0
    log("Figshare metadata:", metadata or "unavailable")
    if remote:
        log("Dataset size check: local=", local, "remote=", remote, "bytes")
        if local > remote:
            if no_download:
                raise RuntimeError("Local dataset is larger than the official payload.")
            log("Local payload has an impossible size; restarting cleanly.")
            target.unlink(); local = 0
        if local < remote:
            if no_download:
                raise RuntimeError(f"Dataset download is incomplete: {local}/{remote} bytes.")
            download_file(effective_url, target)
        if target.stat().st_size != remote:
            raise RuntimeError(f"Dataset remains incomplete after download: {target.stat().st_size}/{remote} bytes.")
        if expected_md5:
            observed = md5_file(target)
            log("Dataset MD5 check: observed=", observed, "expected=", expected_md5)
            if observed.lower() != expected_md5.lower():
                if no_download:
                    raise RuntimeError("Dataset MD5 mismatch; local file is corrupted.")
                log("Dataset has the correct size but wrong checksum; downloading a clean copy.")
                target.unlink()
                download_file(effective_url, target)
                if target.stat().st_size != remote:
                    raise RuntimeError("Clean redownload has the wrong size.")
                observed = md5_file(target)
                log("Clean-copy MD5:", observed)
                if observed.lower() != expected_md5.lower():
                    raise RuntimeError("Clean redownload still fails the official Figshare MD5 checksum.")
        return
    if not target.exists():
        if no_download:
            raise FileNotFoundError(f"Dataset not found: {target}")
        download_file(effective_url, target)
    elif target.stat().st_size < 1_000_000_000:
        if no_download:
            raise RuntimeError(f"Dataset is probably truncated ({target.stat().st_size} bytes).")
        log("Local payload is below 1 GB; attempting resumable download.")
        download_file(effective_url, target)


def download_file(url: str, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.stat().st_size if target.exists() else 0
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    mode = "ab" if existing else "wb"
    log("Downloading public Figshare file; resume offset:", existing)
    with requests.get(url, stream=True, timeout=(30, 300), headers=headers, allow_redirects=True) as r:
        if existing and r.status_code == 200:
            log("Server ignored resume range; restarting download.")
            existing, mode = 0, "wb"
        r.raise_for_status()
        total = r.headers.get("Content-Length")
        total = int(total) + existing if total else None
        done, last_pct = existing, -1
        with target.open(mode) as f:
            for chunk in r.iter_content(4 * 1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = int(done * 100 / total)
                    if pct >= last_pct + 5:
                        log(f"Download: {pct}% ({done / 1e9:.2f} GB)")
                        last_pct = pct
    log("Downloaded:", target, f"({target.stat().st_size / 1e9:.3f} GB)")


def list_hdf5_schema(path: Path, max_rows=300):
    rows = []
    try:
        with h5py.File(path, "r") as f:
            def visit(name, obj):
                if len(rows) >= max_rows:
                    return
                shape = getattr(obj, "shape", "")
                cls = obj.attrs.get("MATLAB_class", b"") if hasattr(obj, "attrs") else b""
                if isinstance(cls, bytes):
                    cls = cls.decode("utf-8", "replace")
                rows.append({"path": name, "kind": type(obj).__name__, "shape": str(shape), "matlab_class": str(cls)})
            f.visititems(visit)
    except Exception as exc:
        rows.append({"path": "<schema-error>", "kind": type(exc).__name__, "shape": "", "matlab_class": str(exc)})
    return pd.DataFrame(rows)


def prepare_mat_payload(path: Path, raw_dir: Path):
    """Identify the downloaded payload and unpack it if Figshare serves an archive."""
    with path.open("rb") as f:
        header = f.read(512)
    log("Downloaded payload header:", repr(header[:80]))
    if header.startswith(b"MATLAB 7.3 MAT-file"):
        return path, "mat-v7.3-mcos"
    if header.startswith(b"MATLAB 5.0 MAT-file"):
        return path, "mat-v5"
    if header.startswith(b"\x89HDF\r\n\x1a\n"):
        return path, "mat-v7.3"
    if header.startswith(b"PK\x03\x04"):
        log("Figshare payload is a ZIP archive; extracting the largest .mat member.")
        with zipfile.ZipFile(path) as z:
            members = [m for m in z.infolist() if not m.is_dir() and m.filename.lower().endswith(".mat")]
            if not members:
                raise RuntimeError("ZIP payload contains no .mat file.")
            member = max(members, key=lambda m: m.file_size)
            target = raw_dir / Path(member.filename).name
            with z.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
        return target, "zip-to-mat"
    if header.startswith(b"\x1f\x8b"):
        log("Figshare payload is gzip-compressed; decompressing it.")
        target = raw_dir / "pupil_dataset_decompressed.mat"
        with gzip.open(path, "rb") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
        return target, "gzip-to-mat"
    low = header.lower().lstrip()
    if low.startswith(b"<!doctype html") or low.startswith(b"<html"):
        raise RuntimeError("Figshare returned an HTML page instead of the dataset. Delete the raw file and retry.")
    return path, "unknown"


def load_mat(path: Path, include_pupil=False, allow_full_fallback=True):
    """Load MATLAB data, including proprietary MCOS table objects."""
    with path.open("rb") as f:
        header = f.read(128)
    is_v73 = header.startswith(b"MATLAB 7.3 MAT-file") or header.startswith(b"\x89HDF")

    if is_v73:
        # This dataset stores Task_epocs as MATLAB MCOS tables. scipy, mat73,
        # hdf5storage and ordinary h5py cannot decode their (1, 6) uint32
        # headers. mat73-reader is specifically designed for this layout.
        try:
            log("Decoding Pupil_data and MCOS tables with mat73-reader...")
            decoded = mcos_load(str(path), variable="Pupil_data")
            if isinstance(decoded, dict) and any(norm_name(k) in {"pupildata", "pupildataset"} for k in decoded):
                obj = decoded
            else:
                obj = {"Pupil_data": decoded}
            if find_dataset_object(obj) is None:
                raise RuntimeError("mat73-reader returned no recognizable Pupil_data object")
            return obj, "mat73-reader-mcos"
        except Exception as exc:
            log("mat73-reader failed:", type(exc).__name__, str(exc)[:500])
            if not allow_full_fallback:
                raise

        # Diagnostic fallback only. Standard mat73 normally returns None for
        # MATLAB table objects, but keeping it gives an informative failure.
        try:
            log("Trying standard mat73 fallback for diagnostics...")
            obj = mat73.loadmat(str(path), use_attrdict=False)
            if obj and find_dataset_object(obj) is not None:
                return obj, "mat73-diagnostic-fallback"
        except Exception as exc:
            log("Standard mat73 fallback failed:", type(exc).__name__, str(exc)[:300])
        raise RuntimeError("Could not decode MATLAB MCOS tables with mat73-reader.")

    from scipy.io import loadmat
    errors = []
    for mode, kwargs in [
        ("scipy-structured", dict(squeeze_me=True, struct_as_record=False,
                                  verify_compressed_data_integrity=False)),
        ("scipy-simplified", dict(simplify_cells=True,
                                  verify_compressed_data_integrity=False)),
    ]:
        try:
            log("Trying", mode, "for non-HDF MATLAB payload...")
            obj = loadmat(path, **kwargs)
            if find_dataset_object(obj) is not None:
                return obj, mode
        except Exception as exc:
            errors.append(f"{mode}: {type(exc).__name__}: {exc}")
    raise RuntimeError("MATLAB decoding failed: " + " | ".join(errors))


def _field_names(obj):
    if isinstance(obj, dict):
        return [norm_name(k) for k in obj.keys()]
    if isinstance(obj, np.ndarray) and obj.dtype.names:
        return [norm_name(k) for k in obj.dtype.names]
    if hasattr(obj, "_fieldnames"):
        return [norm_name(k) for k in obj._fieldnames]
    return []


def _looks_like_session_array(obj):
    sample = obj
    if isinstance(obj, (list, tuple)) and len(obj):
        sample = obj[0]
    elif isinstance(obj, np.ndarray) and obj.size:
        sample = obj.reshape(-1)[0]
    names = set(_field_names(sample))
    return {"subject", "group"}.issubset(names) and "taskepocs" in names


def find_dataset_object(obj, depth=0, seen=None):
    if obj is None or depth > 6:
        return None
    if seen is None:
        seen = set()
    marker = id(obj)
    if marker in seen:
        return None
    seen.add(marker)
    if _looks_like_session_array(obj):
        return obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = norm_name(k)
            if nk in {"pupildata", "pupildataset", "dataset", "paneldata"} or ("pupil" in nk and "data" in nk):
                if v is not None:
                    return v
        nonmeta = [v for k, v in obj.items() if not str(k).startswith("__")]
        for v in nonmeta:
            found = find_dataset_object(v, depth + 1, seen)
            if found is not None:
                return found
        if len(nonmeta) == 1:
            return nonmeta[0]
    elif isinstance(obj, (list, tuple)):
        for v in list(obj)[:5]:
            found = find_dataset_object(v, depth + 1, seen)
            if found is not None:
                return found
    elif isinstance(obj, np.ndarray) and obj.dtype == object:
        for v in obj.reshape(-1)[:5]:
            found = find_dataset_object(v, depth + 1, seen)
            if found is not None:
                return found
    return None


def records_from_object(obj):
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, np.ndarray):
        if obj.dtype.names:
            return [{name: scalar(row[name]) for name in obj.dtype.names} for row in obj.reshape(-1)]
        return [scalar(x) for x in obj.reshape(-1)]
    if isinstance(obj, dict):
        # One record or column-oriented struct array.
        lengths = []
        for v in obj.values():
            if isinstance(v, (list, tuple, np.ndarray)) and not isinstance(v, (str, bytes)):
                try:
                    lengths.append(len(v))
                except Exception:
                    pass
        n = max(lengths, default=0)
        if n > 1 and sum(1 for z in lengths if z == n) >= 2:
            out = []
            for i in range(n):
                rec = {}
                for k, v in obj.items():
                    try:
                        rec[k] = v[i] if len(v) == n else v
                    except Exception:
                        rec[k] = v
                out.append(rec)
            return out
        return [obj]
    if hasattr(obj, "_fieldnames"):
        return [{k: getattr(obj, k) for k in obj._fieldnames}]
    return [obj]


def record_get(record, aliases):
    if isinstance(record, dict):
        lookup = {norm_name(k): v for k, v in record.items()}
        for a in aliases:
            if norm_name(a) in lookup:
                return lookup[norm_name(a)]
    for a in aliases:
        if hasattr(record, a):
            return getattr(record, a)
    return None


def table_to_dataframe(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.copy()
    if hasattr(obj, "_fieldnames"):
        fields = {str(k): getattr(obj, k) for k in obj._fieldnames}
        try:
            return pd.DataFrame({k: list(np.asarray(v).reshape(-1)) for k, v in fields.items()})
        except Exception:
            obj = fields
    if isinstance(obj, dict):
        # Common mat73 table representations: direct columns or nested data.
        direct = {str(k): v for k, v in obj.items() if norm_name(k) not in {"rownames", "description"}}
        try:
            return pd.DataFrame({k: list(np.asarray(v).reshape(-1)) for k, v in direct.items()})
        except Exception:
            names = record_get(obj, ["VariableNames", "varnames", "columns"])
            data = record_get(obj, ["data", "Data"])
            if names is not None and data is not None:
                names = [text_value(x) for x in np.asarray(names).reshape(-1)]
                arr = np.asarray(data, dtype=object)
                if arr.ndim == 2 and arr.shape[1] == len(names):
                    return pd.DataFrame(arr, columns=names)
    if isinstance(obj, np.ndarray):
        if obj.dtype.names:
            return pd.DataFrame.from_records(obj.reshape(-1))
        if obj.ndim == 2:
            return pd.DataFrame(obj)
    if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        return pd.DataFrame(obj)
    raise TypeError(f"Unsupported Task_epoch representation: {type(obj).__name__}")


def find_col(df, aliases):
    lookup = {norm_name(c): c for c in df.columns}
    for a in aliases:
        if norm_name(a) in lookup:
            return lookup[norm_name(a)]
    return None


def normalize_group(raw):
    s = norm_name(text_value(raw))
    if "off" in s and "adhd" in s:
        return "ADHD_off"
    if "on" in s and "adhd" in s:
        return "ADHD_on"
    if s in {"ctrl", "control", "controls", "td", "healthycontrol"} or "ctrl" in s:
        return "Control"
    if s == "adhd":
        return "ADHD_off"
    return text_value(raw) or "Unknown"


def extract_trials(mat_obj, include_pupil=False):
    dataset = find_dataset_object(mat_obj)
    if dataset is None:
        raise KeyError("Could not locate Pupil_dataset in the MATLAB object.")
    records = records_from_object(dataset)
    log("MATLAB session records detected:", len(records))
    all_rows, qc = [], []
    for index, rec in enumerate(records, 1):
        subject = text_value(record_get(rec, ["Subject", "subject", "ID"])) or str(index)
        age = pd.to_numeric(pd.Series([scalar(record_get(rec, ["Age", "age"]))]), errors="coerce").iloc[0]
        group_raw = record_get(rec, ["Group", "group"])
        group = normalize_group(group_raw)
        epoch = record_get(rec, ["Task_epocs", "TaskEpocs", "task_epocs", "Task_epoch", "TaskEpoch", "task_epoch"])
        try:
            df = table_to_dataframe(epoch)
        except Exception as exc:
            qc.append({"session_index": index, "subject": subject, "group": group,
                       "status": "epoch_decode_failed", "detail": f"{type(exc).__name__}: {exc}"})
            continue
        columns = {
            "trial": find_col(df, ["Trial", "trial_index"]),
            "load": find_col(df, ["Load", "memory_load"]),
            "distractor": find_col(df, ["Distractor", "distractor_type"]),
            "correct_response": find_col(df, ["CorrResponse", "CorrectResponse"]),
            "correct": find_col(df, ["Perform", "Performance", "Correct"]),
            "rt_ms": find_col(df, ["RTime", "ReactionTime", "RT"]),
            "pupil": find_col(df, ["Pupil"]),
        }
        required = ["trial", "load", "distractor", "correct", "rt_ms"]
        missing = [k for k in required if columns[k] is None]
        if missing:
            qc.append({"session_index": index, "subject": subject, "group": group,
                       "status": "missing_columns", "detail": f"missing={missing}; available={list(df.columns)}"})
            continue
        out = pd.DataFrame({
            "subject": subject,
            "age": age,
            "group": group,
            "session_index": index,
            "trial": pd.to_numeric(df[columns["trial"]], errors="coerce"),
            "load": [text_value(x) for x in df[columns["load"]]],
            "distractor": [text_value(x) for x in df[columns["distractor"]]],
            "correct": pd.to_numeric(df[columns["correct"]], errors="coerce"),
            "rt_ms": pd.to_numeric(df[columns["rt_ms"]], errors="coerce"),
        })
        if columns["correct_response"] is not None:
            out["correct_response"] = [text_value(x) for x in df[columns["correct_response"]]]
        else:
            out["correct_response"] = ""
        # Published Perform values are 1=correct, 0=incorrect. Missing Perform
        # values are conservatively scored as no-response/omission errors.
        out["correct"] = out["correct"].where(out["correct"].isin([0, 1]), np.nan)
        out["no_response"] = out["correct"].isna()
        out["omission"] = out["no_response"].astype(int)
        out["incorrect_observed"] = (out["correct"] == 0).astype(int)
        out["correct_scored"] = out["correct"].fillna(0).astype(float)
        out["rt_valid"] = out["rt_ms"].between(RT_MIN_MS, RT_MAX_MS, inclusive="both")
        if include_pupil and columns["pupil"] is not None:
            means, sds = [], []
            for cell in df[columns["pupil"]]:
                values = finite(cell)
                means.append(float(np.mean(values)) if len(values) else np.nan)
                sds.append(float(np.std(values, ddof=1)) if len(values) > 1 else np.nan)
            out["pupil_trial_mean_z"] = means
            out["pupil_trial_sd_z"] = sds
        all_rows.append(out)
        qc.append({"session_index": index, "subject": subject, "group": group,
                   "status": "parsed", "n_rows": int(len(out)),
                   "n_no_response": int(out["no_response"].sum()),
                   "distractor_levels": "|".join(sorted(pd.unique(out["distractor"]).astype(str))),
                   "detail": f"columns={list(df.columns)}"})
    if not all_rows:
        raise RuntimeError("No Task_epocs tables were decoded. See quality-control/schema output.")
    trials = pd.concat(all_rows, ignore_index=True)
    return trials, pd.DataFrame(qc)


def condition_effect(df, column, value=None):
    """Signed median contrast for a genuinely two-level condition."""
    levels = sorted([x for x in pd.unique(df[column]) if text_value(x) != ""], key=str)
    if len(levels) != 2:
        return np.nan
    a = finite(df.loc[df[column] == levels[0], value or "rt_ms"])
    b = finite(df.loc[df[column] == levels[1], value or "rt_ms"])
    return float(np.median(b) - np.median(a)) if len(a) and len(b) else np.nan


def multilevel_range(df, column, value="rt_ms"):
    """Order-invariant max-minus-min median across two or more levels."""
    medians = []
    for level in sorted([x for x in pd.unique(df[column]) if text_value(x) != ""], key=str):
        values = finite(df.loc[df[column] == level, value])
        if len(values):
            medians.append(float(np.median(values)))
    return float(max(medians) - min(medians)) if len(medians) >= 2 else np.nan


def _scored_columns(d):
    raw = pd.to_numeric(d["correct"], errors="coerce")
    scored = pd.to_numeric(d.get("correct_scored", raw.fillna(0)), errors="coerce").fillna(0)
    omission = pd.to_numeric(d.get("omission", raw.isna().astype(int)), errors="coerce").fillna(0)
    observed_incorrect = pd.to_numeric(d.get("incorrect_observed", (raw == 0).astype(int)), errors="coerce").fillna(0)
    return raw, scored, omission, observed_incorrect


def condition_summary(trials):
    rows = []
    keys = ["subject", "group", "session_index"]
    for (subject, group, session_index), d in trials.groupby(keys, sort=False):
        _, scored, omission, _ = _scored_columns(d)
        work = d.copy(); work["_scored"] = scored; work["_omission"] = omission
        for condition in ["load", "distractor"]:
            for level, z in work.groupby(condition, dropna=False, sort=True):
                correct_rt = finite(z.loc[(z["_scored"] == 1) & z["rt_valid"], "rt_ms"])
                rows.append({"subject": subject, "group": group, "session_index": int(session_index),
                             "condition": condition, "level": level, "n_trials": int(len(z)),
                             "accuracy": float(z["_scored"].mean()),
                             "error_rate": float(1 - z["_scored"].mean()),
                             "omission_rate": float(z["_omission"].mean()),
                             "median_correct_rt_ms": float(np.median(correct_rt)) if len(correct_rt) else np.nan,
                             "rt_mad_ms": robust_mad(correct_rt)})
    return pd.DataFrame(rows)


def session_metrics(trials):
    rows = []
    keys = ["subject", "group", "session_index"]
    for (subject, group, session_index), d in trials.groupby(keys, sort=False):
        raw, scored, omission, observed_incorrect = _scored_columns(d)
        correct = scored == 1
        valid_correct = correct & d["rt_valid"]
        rt = finite(d.loc[valid_correct, "rt_ms"])
        trial_order = pd.to_numeric(d["trial"], errors="coerce").to_numpy(float)
        rolling_error = (1 - scored).to_numpy(float)
        work = d.copy(); work["_scored"] = scored; work["_omission"] = omission
        row = {
            "subject": subject, "group": group, "session_index": int(session_index),
            "age": float(pd.to_numeric(d["age"], errors="coerce").median()),
            "n_trials": int(len(d)), "n_valid_correct_rt": int(len(rt)),
            "n_no_response": int(omission.sum()),
            "accuracy": float(scored.mean()),
            "error_rate": float(1 - scored.mean()),
            "omission_rate": float(omission.mean()),
            "observed_incorrect_rate": float(observed_incorrect.mean()),
            "median_rt_ms": float(np.median(rt)) if len(rt) else np.nan,
            "mean_rt_ms": float(np.mean(rt)) if len(rt) else np.nan,
            "rt_mad_ms": robust_mad(rt),
            "rt_iqr_ms": float(np.percentile(rt, 75) - np.percentile(rt, 25)) if len(rt) else np.nan,
            "rt_slope_ms_per_trial": slope(d.loc[valid_correct, "trial"], d.loc[valid_correct, "rt_ms"]),
            "error_slope_per_trial": slope(trial_order, rolling_error),
            "load_rt_effect_ms": condition_effect(work.loc[valid_correct], "load"),
            "load_accuracy_effect": condition_effect(work, "load", "_scored"),
            "distractor_rt_range_ms": multilevel_range(work.loc[valid_correct], "distractor", "rt_ms"),
            "distractor_accuracy_range": multilevel_range(work, "distractor", "_scored"),
            "distractor_omission_range": multilevel_range(work, "distractor", "_omission"),
            "n_distractor_levels": int(work["distractor"].nunique(dropna=True)),
        }
        if "pupil_trial_mean_z" in d:
            row["median_pupil_trial_mean_z"] = float(np.nanmedian(d["pupil_trial_mean_z"]))
            row["pupil_behavior_r"] = float(pd.Series(d["pupil_trial_mean_z"]).corr(pd.Series(d["rt_ms"])))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["eligible"] = (out["n_valid_correct_rt"] >= MIN_VALID_TRIALS) & out["median_rt_ms"].notna()
    return out


def rank_biserial(u, n1, n2):
    return float(2 * u / (n1 * n2) - 1)


def permutation_median(a, b, n=N_PERMUTATIONS, seed=SEED):
    a, b = finite(a), finite(b)
    observed = float(np.median(a) - np.median(b))
    pooled = np.concatenate([a, b]); rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n):
        p = rng.permutation(pooled)
        val = np.median(p[:len(a)]) - np.median(p[len(a):])
        count += abs(val) >= abs(observed)
    return observed, (count + 1) / (n + 1)


def bootstrap_median(a, b, n=N_BOOTSTRAPS, seed=SEED):
    a, b = finite(a), finite(b); rng = np.random.default_rng(seed)
    vals = [np.median(rng.choice(a, len(a), True)) - np.median(rng.choice(b, len(b), True)) for _ in range(n)]
    return tuple(np.percentile(vals, [2.5, 97.5]))


def holm_adjust(p_values):
    p = np.asarray(p_values, float); out = np.full(len(p), np.nan)
    ok = np.where(np.isfinite(p))[0]
    order = ok[np.argsort(p[ok])]; running = 0.0; m = len(order)
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, p[idx] * (m - rank)))
        out[idx] = running
    return out


def group_tests(metrics):
    primary = ["median_rt_ms", "rt_mad_ms", "rt_iqr_ms", "accuracy", "omission_rate"]
    secondary = ["rt_slope_ms_per_trial", "error_slope_per_trial", "load_rt_effect_ms",
                 "load_accuracy_effect", "distractor_rt_range_ms",
                 "distractor_accuracy_range", "distractor_omission_range"]
    rows = []
    usable = metrics[metrics["eligible"]]
    for j, metric in enumerate(primary + secondary):
        a = finite(usable.loc[usable.group == "ADHD_off", metric])
        c = finite(usable.loc[usable.group == "Control", metric])
        if len(a) < MIN_GROUP_N or len(c) < MIN_GROUP_N:
            rows.append({"metric": metric, "family": "primary" if metric in primary else "secondary", "n_adhd": len(a), "n_control": len(c)})
            continue
        u, p = stats.mannwhitneyu(a, c, alternative="two-sided")
        diff, pp = permutation_median(a, c, seed=SEED + j)
        lo, hi = bootstrap_median(a, c, seed=SEED + 100 + j)
        bf, bfp = stats.levene(a, c, center="median")
        rows.append({"metric": metric, "family": "primary" if metric in primary else "secondary",
                     "n_adhd": len(a), "n_control": len(c), "median_adhd": np.median(a),
                     "median_control": np.median(c), "median_difference_adhd_minus_control": diff,
                     "bootstrap_ci_low": lo, "bootstrap_ci_high": hi, "mannwhitney_u": u,
                     "mannwhitney_p": p, "permutation_p": pp,
                     "rank_biserial": rank_biserial(u, len(a), len(c)),
                     "brown_forsythe_f": bf, "brown_forsythe_p": bfp})
    out = pd.DataFrame(rows)
    if "permutation_p" not in out.columns:
        out["permutation_p"] = np.nan
    out["holm_permutation_p"] = np.nan
    for family in ["primary", "secondary"]:
        idx = out.index[out.family == family]
        out.loc[idx, "holm_permutation_p"] = holm_adjust(out.loc[idx, "permutation_p"])
    return out


def paired_permutation(delta, n=N_PERMUTATIONS, seed=SEED):
    delta = finite(delta); observed = float(np.median(delta)); rng = np.random.default_rng(seed)
    vals = np.empty(n)
    for i in range(n):
        vals[i] = np.median(delta * rng.choice([-1, 1], len(delta), True))
    return observed, float((np.sum(np.abs(vals) >= abs(observed)) + 1) / (n + 1))


def medication_tests(metrics):
    m = metrics[metrics.eligible & metrics.group.isin(["ADHD_off", "ADHD_on"])].copy()
    # Aggregate only if duplicate sessions exist within condition.
    numeric = m.select_dtypes(include="number").columns
    wide_source = m.groupby(["subject", "group"], as_index=False)[list(numeric)].median()
    metrics_to_test = ["median_rt_ms", "rt_mad_ms", "rt_iqr_ms", "accuracy", "omission_rate",
                       "rt_slope_ms_per_trial", "load_rt_effect_ms", "distractor_rt_range_ms"]
    rows, pairs = [], []
    for j, metric in enumerate(metrics_to_test):
        w = wide_source.pivot(index="subject", columns="group", values=metric).dropna()
        if not {"ADHD_off", "ADHD_on"}.issubset(w.columns):
            rows.append({"metric": metric, "n_pairs": 0}); continue
        w = w.dropna(subset=["ADHD_off", "ADHD_on"]); delta = w.ADHD_on - w.ADHD_off
        if len(delta) >= 3:
            try: stat, wp = stats.wilcoxon(w.ADHD_on, w.ADHD_off, alternative="two-sided")
            except ValueError: stat, wp = 0.0, 1.0
            dmed, pp = paired_permutation(delta, seed=SEED + j)
            rng = np.random.default_rng(SEED + 100 + j)
            boots = [np.median(rng.choice(delta, len(delta), True)) for _ in range(N_BOOTSTRAPS)]
            lo, hi = np.percentile(boots, [2.5, 97.5])
            rows.append({"metric": metric, "n_pairs": len(delta), "median_off": np.median(w.ADHD_off),
                         "median_on": np.median(w.ADHD_on), "median_delta_on_minus_off": dmed,
                         "bootstrap_ci_low": lo, "bootstrap_ci_high": hi,
                         "wilcoxon_stat": stat, "wilcoxon_p": wp, "paired_permutation_p": pp})
            if metric in {"median_rt_ms", "rt_mad_ms", "accuracy"}:
                for sid in w.index:
                    pairs.append({"subject": sid, "metric": metric, "off": w.loc[sid, "ADHD_off"],
                                  "on": w.loc[sid, "ADHD_on"], "delta_on_minus_off": delta.loc[sid]})
        else:
            rows.append({"metric": metric, "n_pairs": len(delta)})
    out = pd.DataFrame(rows)
    if "paired_permutation_p" not in out.columns:
        out["paired_permutation_p"] = np.nan
    out["holm_paired_permutation_p"] = holm_adjust(out["paired_permutation_p"])
    return out, pd.DataFrame(pairs)


def bootstrap_gmm_stability(X, labels, n=GMM_BOOTSTRAPS):
    rng = np.random.default_rng(SEED); aris = []
    for i in range(n):
        idx = rng.choice(len(X), len(X), replace=True)
        unique = np.unique(idx)
        if len(unique) < 6:
            continue
        try:
            gm = GaussianMixture(2, covariance_type="full", n_init=20, random_state=SEED + i).fit(X[idx])
            pred = gm.predict(X[unique]); aris.append(adjusted_rand_score(labels[unique], pred))
        except Exception:
            continue
    return float(np.median(aris)) if aris else np.nan


def gmm_diagnostics(metrics):
    features = ["median_rt_ms", "rt_mad_ms", "rt_iqr_ms", "load_rt_effect_ms", "distractor_rt_range_ms"]
    d = metrics[metrics.eligible & (metrics.group == "ADHD_off")].copy()
    # One row per participant, no diagnostic/control information used.
    d = d.groupby("subject", as_index=False)[features + ["accuracy", "error_rate", "omission_rate"]].median()
    usable_features = [f for f in features if d[f].notna().sum() >= max(8, int(0.75 * len(d)))]
    if len(d) < 15 or len(usable_features) < 2:
        return {"table": pd.DataFrame(), "participants": d, "stable_two_cluster": False,
                "reason": "insufficient participants/features"}
    Xdf = d[usable_features].copy().fillna(d[usable_features].median())
    X = RobustScaler().fit_transform(Xdf)
    rows, models = [], {}
    for k in [1, 2, 3]:
        gm = GaussianMixture(k, covariance_type="full", n_init=50, random_state=SEED).fit(X)
        models[k] = gm; labels = gm.predict(X)
        sil = silhouette_score(X, labels) if k > 1 and len(np.unique(labels)) > 1 else np.nan
        rows.append({"k": k, "bic": gm.bic(X), "aic": gm.aic(X), "silhouette": sil,
                     "min_cluster_share": min(np.bincount(labels)) / len(labels)})
    table = pd.DataFrame(rows); labels = models[2].predict(X)
    bic_gain = float(table.loc[table.k == 1, "bic"].iloc[0] - table.loc[table.k == 2, "bic"].iloc[0])
    sil = float(table.loc[table.k == 2, "silhouette"].iloc[0]); share = min(np.bincount(labels)) / len(labels)
    ari = bootstrap_gmm_stability(X, labels)
    stable = bool(bic_gain >= GMM_BIC_IMPROVEMENT_MIN and sil >= GMM_SILHOUETTE_MIN and
                  share >= GMM_MIN_CLUSTER_SHARE and ari >= GMM_BOOTSTRAP_ARI_MIN)
    d["exploratory_gmm_label"] = labels
    table["bic_gain_k1_minus_k2"] = bic_gain; table["bootstrap_median_ari_k2"] = ari
    table["stable_two_cluster"] = stable; table["features"] = ",".join(usable_features)
    # Held-out accuracy comparison, descriptive unless stable=True.
    groups = [finite(d.loc[d.exploratory_gmm_label == z, "accuracy"]) for z in sorted(np.unique(labels))]
    if len(groups) == 2 and all(len(x) >= 2 for x in groups):
        u, p = stats.mannwhitneyu(groups[0], groups[1], alternative="two-sided")
        table["heldout_accuracy_p"] = p
    return {"table": table, "participants": d, "stable_two_cluster": stable,
            "reason": "all gates passed" if stable else "one or more stability gates failed"}


def create_plots(metrics, med_pairs, gmm, output_dir):
    usable = metrics[metrics.eligible & metrics.group.isin(["ADHD_off", "Control"])]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    for ax, metric, title in zip(axes.ravel(), ["median_rt_ms", "rt_mad_ms", "accuracy", "omission_rate"],
                                 ["Median correct RT", "RT MAD", "Accuracy", "No-response rate"]):
        groups = [finite(usable.loc[usable.group == g, metric]) for g in ["Control", "ADHD_off"]]
        ax.boxplot(groups, tick_labels=["Control", "ADHD off"], showfliers=False)
        rng = np.random.default_rng(SEED)
        for i, values in enumerate(groups, 1):
            ax.scatter(rng.normal(i, .04, len(values)), values, s=24, alpha=.7)
        ax.set_title(title); ax.grid(alpha=.2)
    fig.suptitle("ADHD Pupil Dataset: cluster-free group distributions")
    fig.tight_layout(); fig.savefig(output_dir / GROUP_PLOT, dpi=180); plt.close(fig)

    if not med_pairs.empty:
        metrics_here = list(pd.unique(med_pairs.metric)); fig, axes = plt.subplots(1, len(metrics_here), figsize=(5*len(metrics_here), 4))
        axes = np.atleast_1d(axes)
        for ax, metric in zip(axes, metrics_here):
            d = med_pairs[med_pairs.metric == metric]
            for _, r in d.iterrows(): ax.plot([0, 1], [r.off, r.on], color="0.65", alpha=.65)
            ax.scatter(np.zeros(len(d)), d.off, label="Off"); ax.scatter(np.ones(len(d)), d.on, label="On")
            ax.set_xticks([0,1], ["Off", "On"]); ax.set_title(metric); ax.grid(alpha=.2)
        fig.suptitle("Within-participant methylphenidate comparisons"); fig.tight_layout()
        fig.savefig(output_dir / MED_PLOT, dpi=180); plt.close(fig)

    d = gmm.get("participants", pd.DataFrame())
    if not d.empty and {"median_rt_ms", "rt_mad_ms"}.issubset(d.columns):
        fig, ax = plt.subplots(figsize=(7, 5)); color = d.get("exploratory_gmm_label", pd.Series(np.zeros(len(d))))
        sc = ax.scatter(d.median_rt_ms, d.rt_mad_ms, c=color, cmap="viridis", s=55, alpha=.8)
        ax.set_xlabel("Median correct RT (ms)"); ax.set_ylabel("RT MAD (ms)")
        ax.set_title("ADHD-off RT spectrum; GMM labels are exploratory")
        ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(output_dir / DIM_PLOT, dpi=180); plt.close(fig)


def fmt(x, digits=4):
    try:
        return "NA" if not np.isfinite(float(x)) else f"{float(x):.{digits}f}"
    except Exception:
        return "NA"


def write_report(path, trials, metrics, group, med, gmm, loader_mode, data_hash):
    n_subjects = trials.subject.nunique(); n_sessions = metrics.shape[0]
    raw_correct = pd.to_numeric(trials["correct"], errors="coerce")
    no_response = trials.get("no_response", raw_correct.isna()).astype(bool)
    no_response_by_group = trials.assign(_nr=no_response).groupby("group")["_nr"].agg(["sum", "mean"]).to_dict("index")
    distractor_levels = sorted([text_value(x) for x in pd.unique(trials["distractor"]) if text_value(x) != ""], key=str)
    lines = [
        "ADHD PUPIL DATASET — ACADEMIC DIAGNOSTIC", "=" * 54,
        f"Script version: {SCRIPT_VERSION}", f"Generated: {dt.datetime.now().astimezone().isoformat()}",
        f"Dataset DOI: {DATASET_DOI}", f"MAT loader mode: {loader_mode}", f"Raw file SHA-256: {data_hash}", "",
        "DESIGN", "------", f"Decoded subjects: {n_subjects}", f"Decoded sessions: {n_sessions}",
        f"Decoded trials: {len(trials)}", "Groups: " + json.dumps(metrics.group.value_counts().to_dict()),
        f"No-response trials: {int(no_response.sum())}; by group: " + json.dumps(no_response_by_group),
        "Distractor levels: " + json.dumps(distractor_levels), "",
        "SCORING AND CONDITION RULES", "---------------------------",
        "Missing Perform values are conservatively scored as no-response/omission errors.",
        "Accuracy uses all trials; error_rate equals 1 - accuracy and is not tested as a duplicate endpoint.",
        "The four-level Distractor factor is treated categorically; participant-level max-minus-min ranges are order-invariant secondary endpoints.",
        "Pupil vectors are excluded from the primary behavioral analysis unless --include-pupil is requested.", "",
        "INTERPRETATION RULES", "--------------------",
        "Primary inference is ADHD off medication versus controls.",
        "Medication inference is paired within participant (on minus off).",
        "GMM is secondary, ADHD-only, RT-derived, and cannot establish a subtype unless all gates pass.",
        "Behavior cannot establish a dopaminergic, neural, metabolic, or causal mechanism.", "",
        "CLUSTER-FREE GROUP RESULTS", "--------------------------",
    ]
    if group.empty:
        lines.append("No valid group comparisons.")
    else:
        for _, r in group.iterrows():
            lines.append(f"{r.metric}: n={int(r.get('n_adhd',0))}/{int(r.get('n_control',0))}; "
                         f"median difference={fmt(r.get('median_difference_adhd_minus_control'))}; "
                         f"permutation p={fmt(r.get('permutation_p'))}; Holm p={fmt(r.get('holm_permutation_p'))}; "
                         f"Brown-Forsythe p={fmt(r.get('brown_forsythe_p'))}")
    lines += ["", "PAIRED MEDICATION RESULTS", "-------------------------"]
    for _, r in med.iterrows():
        lines.append(f"{r.metric}: pairs={int(r.get('n_pairs',0))}; on-off median={fmt(r.get('median_delta_on_minus_off'))}; "
                     f"paired permutation p={fmt(r.get('paired_permutation_p'))}; Holm p={fmt(r.get('holm_paired_permutation_p'))}")
    lines += ["", "EXPLORATORY DISCRETE-CLUSTER CHECK", "----------------------------------",
              f"Stable two-cluster result: {gmm.get('stable_two_cluster', False)}",
              f"Decision: {gmm.get('reason', 'not run')}",
              "Failure of gates is evidence against a defensible discrete partition in this task, not proof of no heterogeneity.", "",
              "BOUNDARY", "--------",
              "Significant results are dataset- and task-specific. Null results do not refute prior datasets.",
              "Distractor range endpoints quantify modulation magnitude, not an ordered or directional distractor effect.",
              "A continuous RT/accuracy or medication-response spectrum remains exploratory unless replicated independently."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def synthetic_trials():
    rng = np.random.default_rng(SEED); rows = []
    for sid in range(1, 51):
        base_group = "Control" if sid <= 22 else "ADHD_off"
        sessions = [base_group] + (["ADHD_on"] if sid >= 34 else [])
        for sidx, group in enumerate(sessions, 1):
            for t in range(1, 81):
                load = str(1 + t % 2); distractor = str(t % 2)
                shift = 35 if group == "ADHD_off" else (10 if group == "ADHD_on" else 0)
                rt = 650 + shift + 35*(load == "2") + 15*(distractor == "1") + rng.normal(0, 90)
                p_correct = .91 if group == "Control" else (.87 if group == "ADHD_off" else .90)
                rows.append({"subject": str(sid), "age": 11, "group": group, "session_index": sid*10+sidx,
                             "trial": t, "load": load, "distractor": distractor, "correct_response": "1",
                             "correct": int(rng.random() < p_correct), "rt_ms": rt, "rt_valid": 100 <= rt <= 5000})
    return pd.DataFrame(rows)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Validate the public ADHD Pupil Size trial-level dataset.")
    p.add_argument("--data-file", type=Path, help="Existing MATLAB dataset file")
    p.add_argument("--output-dir", type=Path, default=Path(OUTPUT_FOLDER))
    p.add_argument("--raw-dir", type=Path, default=Path(RAW_FOLDER))
    p.add_argument("--no-download", action="store_true")
    p.add_argument("--keep-data", action="store_true")
    p.add_argument("--include-pupil", action="store_true", help="Also decode pupil vectors; requires more RAM")
    p.add_argument("--no-full-mat-fallback", action="store_true", help="Do not load the entire MAT file if selective decoding fails")
    p.add_argument("--no-auto-install", action="store_true")
    p.add_argument("--self-test", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    ensure_dependencies(args.no_auto_install); imports_after_bootstrap()
    np.random.seed(SEED); warnings.filterwarnings("ignore", category=RuntimeWarning)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    # Never mix a successful run with stale reports/failure traces.
    for stale in list(output.glob("adhd_pupil_*")):
        if stale.is_file():
            stale.unlink()
    raw_dir = args.raw_dir.resolve(); raw_dir.mkdir(parents=True, exist_ok=True)
    data_file = args.data_file.resolve() if args.data_file else raw_dir / RAW_FILENAME
    payload_file = data_file
    success = False; loader_mode = "synthetic"; data_hash = "synthetic"
    try:
        log("ADHD Pupil Validator", SCRIPT_VERSION)
        log("Primary analysis: cluster-free ADHD-off versus Control.")
        if args.self_test:
            trials = synthetic_trials(); qc = pd.DataFrame([{"status": "synthetic_self_test", "detail": "generated"}])
        else:
            ensure_complete_download(DOWNLOAD_URL, data_file, args.no_download)
            data_hash = sha256_file(data_file); log("Raw SHA-256:", data_hash)
            payload_file, payload_mode = prepare_mat_payload(data_file, raw_dir)
            log("Payload type:", payload_mode, "analysis file:", payload_file)
            schema = list_hdf5_schema(payload_file); schema.to_csv(output / "adhd_pupil_mat_schema.csv", index=False)
            mat, loader_mode = load_mat(payload_file, args.include_pupil, not args.no_full_mat_fallback)
            loader_mode = payload_mode + "+" + loader_mode
            trials, qc = extract_trials(mat, args.include_pupil)
            del mat
        trials.to_csv(output / TRIAL_NAME, index=False)
        qc.to_csv(output / QC_NAME, index=False)
        metrics = session_metrics(trials); metrics.to_csv(output / SESSION_NAME, index=False)
        conditions = condition_summary(trials); conditions.to_csv(output / CONDITION_NAME, index=False)
        group = group_tests(metrics); group.to_csv(output / GROUP_NAME, index=False)
        med, med_pairs = medication_tests(metrics); med.to_csv(output / MED_NAME, index=False)
        if not med_pairs.empty: med_pairs.to_csv(output / "adhd_pupil_medication_pairs.csv", index=False)
        gmm = gmm_diagnostics(metrics); gmm["table"].to_csv(output / CLUSTER_NAME, index=False)
        if not gmm["participants"].empty: gmm["participants"].to_csv(output / "adhd_pupil_gmm_participants.csv", index=False)
        create_plots(metrics, med_pairs, gmm, output)
        config = {"script_version": SCRIPT_VERSION, "dataset_record": DATASET_RECORD, "dataset_version": DATASET_VERSION,
                  "dataset_doi": DATASET_DOI, "download_url": DOWNLOAD_URL, "seed": SEED,
                  "n_permutations": N_PERMUTATIONS, "n_bootstraps": N_BOOTSTRAPS,
                  "rt_bounds_ms": [RT_MIN_MS, RT_MAX_MS], "minimum_valid_trials": MIN_VALID_TRIALS,
                  "include_pupil": args.include_pupil, "loader_mode": loader_mode, "raw_sha256": data_hash,
                  "missing_perform_rule": "score as no-response error",
                  "distractor_rule": "four-level categorical summaries and order-invariant ranges",
                  "python": sys.version, "platform": platform.platform(),
                  "packages": {m: getattr(importlib.import_module(m), "__version__", "unknown") for m in REQUIRED_PACKAGES}}
        (output / CONFIG_NAME).write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        write_report(output / REPORT_NAME, trials, metrics, group, med, gmm, loader_mode, data_hash)
        success = True
    except Exception as exc:
        log("FATAL:", type(exc).__name__, str(exc)); log(traceback.format_exc())
        (output / "adhd_pupil_failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        (output / LOG_NAME).write_text("\n".join(LOG_BUFFER) + "\n", encoding="utf-8")
        if success:
            failure_file = output / "adhd_pupil_failure.txt"
            if failure_file.exists():
                failure_file.unlink()
            zip_path = output.parent / ZIP_NAME
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                for p in sorted(output.rglob("*")):
                    if p.is_file(): z.write(p, p.relative_to(output.parent))
            log("Output archive:", zip_path)
            if not args.keep_data and not args.self_test:
                for candidate in {data_file, payload_file}:
                    if candidate.exists() and candidate.parent == raw_dir:
                        candidate.unlink()
                log("Raw dataset payloads deleted after successful analysis.")
            if is_colab():
                with contextlib.suppress(Exception):
                    from google.colab import files
                    files.download(str(zip_path))
    log("Completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
