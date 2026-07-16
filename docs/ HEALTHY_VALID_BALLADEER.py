# -*- coding: utf-8 -*-
"""
HEALTHY_VALID_BALLADEER.py -- BALLADEER dataset validator for the
"Allostatic Sprint" hypothesis (ADHD behavioral subtypes).

WHAT IT DOES
    Reads the real BALLADEER dataset (users_demographics.json,
    balladeer_embraceplus_data.csv, and per-participant
    [UserID]_GAME_DATA_[SessionDate].csv files), clusters participants into
    three subtypes ("True Resilience", "Decompensated Sprint",
    "Compensated Crash") based on work speed / accuracy, and runs the
    statistical tests (Mann-Whitney U, Bonferroni correction, permutation
    test, MixedLM) reported in the project README.

    This script never downloads anything -- it only searches local folders
    for files you have already placed on disk.

HOW TO RUN
    1. pip install pandas numpy scipy matplotlib seaborn openpyxl
    2. Get the BALLADEER dataset yourself (registration required):
         IEEE DataPort: DOI 10.21227/nevp-3a70
         Figshare:      DOI 10.6084/m9.figshare.28676042
       Place the extracted files (users_demographics.json,
       balladeer_embraceplus_data.csv, and the [UserID]/ folders) in your
       Downloads folder, next to this script, or in the current directory.
    3. python3 HEALTHY_VALID_BALLADEER.py

OUTPUT
    Written to a new 'HEALTHY_VALID_BALLADEER_output' folder:
    healthy_valid_academic_diagnostic.txt, healthy_valid_accuracy_validation.png,
    healthy_valid_impulsivity_validation.png, healthy_valid_fatigue_dynamics.png,
    (crash_log.txt only if something goes wrong)

NOTE: the "dopamine D1/D2" and "ATP depletion" language in this project is a
theoretical/narrative framing, not something directly measured in the data.

Author: D1D2DOPAMINE
"""

import json
import os
import platform
import re
import shutil
import traceback
import warnings
import zipfile

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

LOG_BUFFER = []

def log(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    LOG_BUFFER.append(text)
    print(text, flush=True, **kwargs)

MAX_LOCAL_FILE_SIZE_MB = 200

BALLADEER_SCIDATA_DOI = "10.1038/s41597-026-06758-7"
BALLADEER_IEEE_DATAPORT_DOI = "10.21227/nevp-3a70"
BALLADEER_FIGSHARE_DOI = "10.6084/m9.figshare.28676042"

CLEAN_REPORT_NAME = "healthy_valid_academic_diagnostic.txt"
ACCURACY_PLOT_NAME = "healthy_valid_accuracy_validation.png"
IMPULSIVITY_PLOT_NAME = "healthy_valid_impulsivity_validation.png"
FATIGUE_DYNAMICS_PLOT_NAME = "healthy_valid_fatigue_dynamics.png"
CRASH_LOG_NAME = "crash_log.txt"
OUTPUT_FOLDER_NAME = "HEALTHY_VALID_BALLADEER_output"

GROUP_LABEL_ADHD = "Experimental (ADHD)"
GROUP_LABEL_CONTROL = "Control"

COHORT_PURE_CONTROL = "Pure Control"
COHORT_PURE_ADHD = "Pure ADHD"
COHORT_SUSPECTED = "Suspected ADHD"
COHORT_ORDER = [COHORT_PURE_CONTROL, COHORT_PURE_ADHD, COHORT_SUSPECTED]

SUBTYPE_LABELS = {
    "super_d1_flow": "Subtype 1: \"Decompensated Sprint\"",
    "noise_resonance": "Subtype 2: \"Compensated Crash / Metabolic Fatigue\"",
}
SUBTYPE_DESCRIPTIONS = {
    "super_d1_flow": (
        "the brain runs at maximum ATP, holds speed, but completely loses "
        "impulse inhibition, producing a high Percent Commissions"
    ),
    "noise_resonance": (
        "the brain shifts into energy-saving mode, timing becomes ragged "
        "and noisy, but the manual brake engages, so false clicks are rare"
    ),
}

CLUSTER_DISPLAY_LABELS = {
    "super_d1_flow": "Subtype 1: Decompensated Sprint",
    "noise_resonance": "Subtype 2: Compensated Crash",
    "sustainable_flow": "True Resilience",
}

SUBTYPE_SHORT_LABELS = {
    "super_d1_flow": "Sprint",
    "noise_resonance": "Crash",
}

BONFERRONI_BASE_ALPHA = 0.05

N_PERMUTATIONS = 1000
PERMUTATION_TARGET_CLUSTER = "super_d1_flow"
PERMUTATION_TARGET_METRIC = "percent_commissions"
PERMUTATION_REAL_P_VALUE = 0.05                                                                          

CLUSTER_SCATTER_COLORS = {
    "sustainable_flow": "seagreen",
    "super_d1_flow": "crimson",
    "noise_resonance": "steelblue",
}

FATIGUE_BAR_COLOR_EDA = "steelblue"
FATIGUE_BAR_COLOR_PRV = "crimson"

DEMOGRAPHICS_FILENAME = "users_demographics.json"
BIOMETRICS_FILENAME = "balladeer_embraceplus_data.csv"
GAME_DATA_FILENAME_RE = re.compile(r"^(UB\w+)_GAME_DATA_.*\.csv$", re.IGNORECASE)

GROUP_EXPERIMENTAL_ADHD = 1
GROUP_CONTROL = 2

BIOMETRIC_SOURCES = ["S1", "S6", "S11", "Cognifit", "Robots"]
BIOMETRIC_DELTA_METRICS = ["eda", "prv"]
WEARING_DETECTION_METRIC = "wearing_detection"

GAME_BLOCK_NUMBERS = [1, 2, 3, 4]

def get_script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return "."

def get_platform_downloads_dir():
    system_name = platform.system()

    if system_name == "Windows":
        userprofile = os.environ.get("USERPROFILE")
        return os.path.join(userprofile, "Downloads") if userprofile else None

    if os.path.isdir("/storage/emulated/0") or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
        return "/storage/emulated/0/Download"

    if system_name in ("Linux", "Darwin"):
        home = os.path.expanduser("~")
        return os.path.join(home, "Downloads") if home and home != "~" else None

    home = os.path.expanduser("~")
    return os.path.join(home, "Downloads") if home and home != "~" else None

def _script_parent_dir():
    try:
        return os.path.dirname(get_script_dir())
    except Exception:
        return None

def get_search_dirs():
    dirs = [
        get_platform_downloads_dir(),
        "/storage/emulated/0/Download",
        "/storage/emulated/0/Downloads",
        "/storage/emulated/0/Documents",
        "/storage/emulated/0",
        "/storage/self/primary/Download",
        "/storage/self/primary",
        "/sdcard/Download",
        "/sdcard/Documents",
        "/sdcard",
        os.path.expanduser("~/storage/downloads"),
        os.path.expanduser("~/storage/shared/Download"),
        get_script_dir(),
        _script_parent_dir(),
        os.getcwd(),
        ".",
    ]
    seen, result = set(), []
    for d in dirs:
        if not d:
            continue
        try:
            real = os.path.realpath(d)
        except Exception:
            real = d
        if os.path.isdir(d) and real not in seen:
            seen.add(real)
            result.append(d)
    return result

_ANDROID_SHARED_STORAGE_PREFIXES = (
    "/storage/emulated/0", "/storage/self/primary", "/sdcard",
)

def _is_android_shared_storage_path(path):
    try:
        real = os.path.realpath(path)
    except Exception:
        real = path
    return any(real.startswith(p) or path.startswith(p) for p in _ANDROID_SHARED_STORAGE_PREFIXES)

def _is_probably_android():
    return (
        os.path.isdir("/storage/emulated/0")
        or "ANDROID_ROOT" in os.environ
        or "ANDROID_DATA" in os.environ
    )

def _log_android_storage_permission_hint():
    log("  This looks like an Android device. If you're running this in Pydroid 3, the\n"
        "  most common cause is that Pydroid 3 has not been granted storage permission yet:\n"
        "  in Android Settings -> Apps -> Pydroid 3 -> Permissions -> Files and media,\n"
        "  choose 'Allow management of all files' (Android 11+) or 'Allow' (older Android),\n"
        "  then fully close and reopen Pydroid 3 and re-run the script. Without this\n"
        "  permission, Pydroid 3 cannot see the dataset files you placed in Downloads/shared\n"
        "  storage, and any outputs it does produce will land only inside its own private app\n"
        "  folder, invisible to the phone's normal Files app.")

def _test_write_ok(d):
    """
    Android's os.access(d, os.W_OK) can report True for a shared-storage
    directory Pydroid 3 cannot actually write to (scoped-storage permission
    checks do not always match the classic POSIX access() bits). The only
    reliable test is to actually create and remove a throwaway file.
    """
    if not d or not os.path.isdir(d):
        return False, "not a directory"
    probe_path = os.path.join(d, ".healthy_valid_balladeer_write_test.tmp")
    try:
        with open(probe_path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe_path)
        return True, None
    except Exception as e:
        return False, str(e)

def get_writable_dir():
    primary = get_platform_downloads_dir()
    candidates = [
        primary,
        "/storage/emulated/0/Download",
        "/storage/emulated/0/Downloads",
        "/storage/self/primary/Download",
        "/sdcard/Download",
        os.path.expanduser("~/storage/downloads"),
        get_script_dir(),
        os.getcwd(),
        ".",
    ]
    failures = []
    for d in candidates:
        if not d:
            continue
        ok, err = _test_write_ok(d)
        if ok:
            if failures:
                log("Note: skipped %d unwritable candidate director(y/ies) before finding a "
                    "writable one -- %s" % (len(failures), "; ".join(failures)))
            return d
        failures.append("%s (%s)" % (d, err))

    log("Note: no writable Downloads-like directory found -- tried and failed: %s. Falling "
        "back to the script's current directory ('.')." % "; ".join(failures))
    if _is_probably_android():
        _log_android_storage_permission_hint()
    return "."

def get_output_dir():
    """
    Returns (creating it if needed) a dedicated output subfolder inside the
    writable Downloads-like directory, so report/plot/crash-log files never
    get scattered loose into Downloads itself alongside the dataset files.
    Falls back to the writable directory itself if the subfolder cannot be
    created (e.g. a permissions issue).
    """
    base_dir = get_writable_dir()
    output_dir = os.path.join(base_dir, OUTPUT_FOLDER_NAME)
    try:
        os.makedirs(output_dir, exist_ok=True)
        ok, _err = _test_write_ok(output_dir)
        if ok:
            abs_output_dir = os.path.abspath(output_dir)
            if _is_probably_android() and not _is_android_shared_storage_path(output_dir):
                log("=" * 70)
                log("IMPORTANT: outputs are being saved to:\n    %s" % abs_output_dir)
                log("This is NOT inside your phone's shared Downloads/storage area, so it will\n"
                    "NOT show up in your normal Files app or Download folder -- it's a private\n"
                    "folder that only Pydroid 3 itself can browse (use Pydroid 3's own file\n"
                    "browser to retrieve the files from that exact path).")
                log("To make outputs land in the real, visible Downloads folder instead: open\n"
                    "Android Settings -> Apps -> Pydroid 3 -> Permissions -> Files and media,\n"
                    "choose 'Allow management of all files' (Android 11+) or 'Allow' (older\n"
                    "Android), fully close Pydroid 3, reopen it, and re-run the script.")
                log("=" * 70)
            else:
                log("Output folder: %s" % abs_output_dir)
            return output_dir
    except Exception:
        pass
    log("Note: could not create/use output folder '%s' -- falling back to %s."
        % (output_dir, base_dir))
    return base_dir

def find_file_in_dirs(filename, search_dirs):
    """
    Looks for a file matching `filename` (case-insensitive, exact name) in
    each of `search_dirs`. Checks a flat listing of each directory first,
    then falls back to a recursive walk (since the extracted BALLADEER
    dataset root may be nested a few folders deep inside Downloads).
    """
    target = filename.lower()
    for d in search_dirs:
        try:
            for name in os.listdir(d):
                if name.lower() == target:
                    path = os.path.join(d, name)
                    if os.path.isfile(path):
                        return path
        except Exception:
            continue
    for d in search_dirs:
        try:
            for root, _dirs, files in os.walk(d):
                for name in files:
                    if name.lower() == target:
                        return os.path.join(root, name)
        except Exception:
            continue
    return None

def find_game_data_files(search_dirs):
    """
    Recursively walks every search directory looking for files named
    [UserID]_GAME_DATA_[SessionDate].csv (typically nested under each
    participant's AttentionRobotsDesktop/[UnixSessionDate]/ folder).

    Returns a dict: { user_id: [path, path, ...] } (a participant can have
    more than one session file).
    """
    found = {}
    seen_real_paths = set()
    for d in search_dirs:
        try:
            for root, _dirs, files in os.walk(d):
                for name in files:
                    m = GAME_DATA_FILENAME_RE.match(name)
                    if not m:
                        continue
                    path = os.path.join(root, name)
                    try:
                        real_path = os.path.realpath(path)
                    except Exception:
                        real_path = path
                    if real_path in seen_real_paths:
                        continue                                                            
                    seen_real_paths.add(real_path)
                    user_id = m.group(1).upper()
                    found.setdefault(user_id, []).append(path)
        except Exception:
            continue
    return found

def log_search_diagnostics(extensions):
    """
    Prints exactly which directories were scanned (and which candidate
    directories do not exist / are not accessible on this device), plus a
    short listing of whatever files with a matching extension actually sit
    in each accessible directory. Turns a bare "file not found" error into
    an actionable diagnosis.
    """
    log("  -- Search diagnostics --")
    accessible = get_search_dirs()
    log("  Accessible/searched directories (%d):" % len(accessible))
    unlistable_count = 0
    total_matching = 0
    for d in accessible:
        try:
            entries = os.listdir(d)
        except Exception as e:
            log("    %s  [could not list: %s]" % (d, e))
            unlistable_count += 1
            continue
        matching_ext = [n for n in entries if os.path.splitext(n.lower())[1] in extensions]
        total_matching += len(matching_ext)
        log("    %s  (%d file(s) with a matching extension %s)" % (d, len(matching_ext), sorted(extensions)))
        for n in matching_ext[:20]:
            log("       - %s" % n)
        if len(matching_ext) > 20:
            log("       ... and %d more" % (len(matching_ext) - 20))
    log("  Expected BALLADEER files: '%s', '%s', and '<UserID>_GAME_DATA_<SessionDate>.csv' "
        "files under each participant's 'AttentionRobotsDesktop' folder. If these are not "
        "listed above (directly or in a subfolder), extract/download the BALLADEER dataset "
        "into one of the searched directories (Downloads is checked automatically), or place "
        "a local .zip archive of it there instead." % (DEMOGRAPHICS_FILENAME, BIOMETRICS_FILENAME))
    if _is_probably_android() and (unlistable_count > 0 or total_matching == 0):
        log("  -- Likely cause on Android --")
        _log_android_storage_permission_hint()
        log("  Also double-check exactly where the BALLADEER dataset files/zip currently sit on\n"
            "  the phone -- if they were saved by a browser or file manager into shared storage\n"
            "  but Pydroid 3 still can't see them after granting the permission above, try\n"
            "  moving them into the phone's main 'Download' folder specifically, since that is\n"
            "  the first place this script looks.")

def check_size_guard(path, max_mb=MAX_LOCAL_FILE_SIZE_MB):
    try:
        size_mb = os.path.getsize(path) / (1024.0 * 1024.0)
    except Exception:
        return
    if size_mb > max_mb:
        log("  WARNING: %s is %.1f MB, larger than the %.0f MB sanity guard "
            "(MAX_LOCAL_FILE_SIZE_MB) expected for a lightweight BALLADEER "
            "per-participant table. Loading it anyway since the filename matched "
            "exactly, but double-check this is really the correct file." % (path, size_mb, max_mb))

def find_zip_archives():
    archives = []
    for d in get_search_dirs():
        try:
            entries = os.listdir(d)
        except Exception:
            continue
        for name in entries:
            if not name.lower().endswith(".zip"):
                continue
            path = os.path.join(d, name)
            if not os.path.isfile(path):
                continue
            try:
                size = os.path.getsize(path)
            except Exception:
                size = -1
            archives.append((path, size))
    return archives

def extract_member(zip_path, member_info, dest_dir):
    """
    Extracts exactly ONE member from the archive -- never the whole zip --
    as a flat copy (no internal subfolders) into dest_dir. Guards against
    zip-slip path traversal by only ever using the member's basename.
    """
    safe_name = os.path.basename(member_info.filename)
    if not safe_name:
        return None
    final_path = os.path.join(dest_dir, safe_name)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(member_info, "r") as src, open(final_path, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
        return final_path
    except Exception as e:
        log("  Failed to extract %s from %s: %s" % (member_info.filename, zip_path, e))
        try:
            if os.path.exists(final_path):
                os.remove(final_path)
        except Exception:
            pass
        return None

def find_member_in_zip_by_exact_name(zip_path, filename):
    target = filename.lower()
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if os.path.basename(info.filename).lower() == target:
                    return info
    except Exception as e:
        log("  Could not scan %s as a zip archive: %s" % (zip_path, e))
    return None

def find_game_data_members_in_zip(zip_path):
    matches = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base_name = os.path.basename(info.filename)
                m = GAME_DATA_FILENAME_RE.match(base_name)
                if m:
                    matches.append((info, m.group(1).upper()))
    except Exception as e:
        log("  Could not scan %s as a zip archive: %s" % (zip_path, e))
    return matches

def find_file_with_zip_fallback(filename, search_dirs, description):
    path = find_file_in_dirs(filename, search_dirs)
    if path:
        check_size_guard(path)
        return path
    log("No loose local '%s' found for %s -- checking local .zip archives..." % (filename, description))
    for zip_path, _zip_size in find_zip_archives():
        info = find_member_in_zip_by_exact_name(zip_path, filename)
        if info is None:
            continue
        log("  Found '%s' inside archive %s -- extracting only this member." % (filename, zip_path))
        extracted = extract_member(zip_path, info, get_output_dir())
        if extracted:
            return extracted
    return None

def load_demographics(search_dirs):
    path = find_file_with_zip_fallback(DEMOGRAPHICS_FILENAME, search_dirs, "participant demographics/group labels")
    if not path:
        log_search_diagnostics({".json"})
        raise RuntimeError(
            "Could not find '%s' anywhere in the searched directories or local .zip "
            "archives. This file provides the Experimental/Control group labels "
            "('group': 1 = Experimental/ADHD, 2 = Control) and cannot be substituted." % DEMOGRAPHICS_FILENAME
        )
    log("Using demographics file: %s" % path)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        records = []
        for key, value in raw.items():
            if isinstance(value, dict):
                value = dict(value)
                value.setdefault("username", key)
                records.append(value)
        raw = records if records else raw

    df = pd.DataFrame(raw)
                                                                         
    id_field = "username" if "username" in df.columns else ("user" if "user" in df.columns else None)
    if id_field is None or "group" not in df.columns:
        raise RuntimeError(
            "'%s' is missing the required 'username'/'user' and/or 'group' field(s). Found "
            "columns: %s" % (DEMOGRAPHICS_FILENAME, list(df.columns))
        )

    group_numeric = pd.to_numeric(df["group"], errors="coerce")
    valid_mask = group_numeric.isin([GROUP_EXPERIMENTAL_ADHD, GROUP_CONTROL])
    n_dropped = int((~valid_mask).sum())
    if n_dropped:
        log("Warning: dropping %d participant(s) from '%s' with a missing/unrecognized "
            "'group' value (expected %d = Experimental/ADHD or %d = Control)."
            % (n_dropped, DEMOGRAPHICS_FILENAME, GROUP_EXPERIMENTAL_ADHD, GROUP_CONTROL))
    df = df[valid_mask].copy()
    group_numeric = group_numeric[valid_mask]

    out = pd.DataFrame()
    out["id"] = df[id_field].astype(str).str.strip()
    out["is_adhd"] = (group_numeric == GROUP_EXPERIMENTAL_ADHD).to_numpy()

    if "age" in df.columns:
        out["age"] = pd.to_numeric(df["age"], errors="coerce").to_numpy()
    if "gender" in df.columns:
        def _map_gender(v):
            s = str(v).strip()
            return {"1": "m", "2": "f"}.get(s, s)
        out["sex"] = df["gender"].apply(_map_gender).to_numpy()

    if "diagnosed" in df.columns:
        out["diagnosed"] = df["diagnosed"].to_numpy()
        diagnosed_norm = df["diagnosed"].astype(str).str.strip().str.lower()
    else:
        diagnosed_norm = pd.Series([np.nan] * len(df), index=df.index)

    is_pure_control = (group_numeric == GROUP_CONTROL) & (diagnosed_norm == "no")
    is_pure_adhd = (group_numeric == GROUP_EXPERIMENTAL_ADHD) | (
        (group_numeric == GROUP_CONTROL) & (diagnosed_norm == "yes"))
    is_suspected = (diagnosed_norm == "undetermined") & (~is_pure_control) & (~is_pure_adhd)

    cohort = pd.Series([None] * len(df), index=df.index, dtype=object)
    cohort.loc[is_pure_control] = COHORT_PURE_CONTROL
    cohort.loc[is_pure_adhd] = COHORT_PURE_ADHD
    cohort.loc[is_suspected] = COHORT_SUSPECTED
    out["cohort"] = cohort.to_numpy()

    n_unclassified_cohort = int(cohort.isna().sum())
    if n_unclassified_cohort:
        log("Warning: %d participant(s) did not match any of the three clean cohort rules "
            "(%s/%s/%s) based on 'group'+'diagnosed' -- they are kept in the raw dataset but "
            "excluded from cohort-based comparisons and plots."
            % (n_unclassified_cohort, COHORT_PURE_CONTROL, COHORT_PURE_ADHD, COHORT_SUSPECTED))
    log("Clean cohort split (group+diagnosed): %s" % cohort.value_counts(dropna=False).to_dict())

    out = out.drop_duplicates(subset="id", keep="first").reset_index(drop=True)
    return out, path

def load_biometrics(search_dirs):
    """
    Reads balladeer_embraceplus_data.csv (one row per participant, wide
    [source]_[measurement]_[stat] columns) and, for each activity source
    in BIOMETRIC_SOURCES, computes:

        delta = [source]_[metric]_last_two_mean - [source]_[metric]_first_two_mean

    for metric in ('eda', 'prv') -- but ONLY when
    [source]_wearing_detection_mean is present and != 0. Rows/sources where
    wearing_detection == 0 (the device was not worn -- a motion artifact)
    are excluded before the delta is ever computed. The per-source deltas
    are then averaged into a single eda_change / prv_change value per
    participant.
    """
    path = find_file_with_zip_fallback(BIOMETRICS_FILENAME, search_dirs, "EmbracePlus biometrics")
    if not path:
        log_search_diagnostics({".csv"})
        raise RuntimeError(
            "Could not find '%s' anywhere in the searched directories or local .zip "
            "archives. This file provides the EmbracePlus EDA/PRV biometrics used for "
            "the fatigue/arousal-change analysis." % BIOMETRICS_FILENAME
        )
    log("Using biometrics file: %s" % path)
                                                                               
    df = pd.read_csv(path, sep=";")
    if "username" not in df.columns:
        raise RuntimeError("'%s' is missing the required 'username' column." % BIOMETRICS_FILENAME)
    df["id"] = df["username"].astype(str).str.strip()

    def _eda_first_last_cols(source):
        return ("%s_eda_values_first_two_mean" % source, "%s_eda_values_last_two_mean" % source)

    def _prv_first_last_cols(source):
        return ("%s_prv_first_two_mean" % source, "%s_prv_last_two_mean" % source)

    METRIC_COLUMN_BUILDERS = {"eda": _eda_first_last_cols, "prv": _prv_first_last_cols}
    WEARING_UNIT = "percentage"

    n_excluded_artifact = 0
    n_used = 0
    out_rows = []
    for _, row in df.iterrows():
        entry = {"id": row["id"]}
        per_metric_deltas = {metric: [] for metric in BIOMETRIC_DELTA_METRICS}
        for source in BIOMETRIC_SOURCES:
            wearing_col = "%s_%s_mean_%s" % (source, WEARING_DETECTION_METRIC, WEARING_UNIT)
            wearing_val = pd.to_numeric(row.get(wearing_col), errors="coerce") if wearing_col in df.columns else np.nan
            for metric in BIOMETRIC_DELTA_METRICS:
                first_col, last_col = METRIC_COLUMN_BUILDERS[metric](source)
                if first_col not in df.columns or last_col not in df.columns:
                    continue
                if pd.isna(wearing_val) or wearing_val == 0:
                    n_excluded_artifact += 1
                    continue
                first_val = pd.to_numeric(row.get(first_col), errors="coerce")
                last_val = pd.to_numeric(row.get(last_col), errors="coerce")
                if pd.isna(first_val) or pd.isna(last_val):
                    continue
                per_metric_deltas[metric].append(float(last_val) - float(first_val))
                n_used += 1
        result_row = {"id": entry["id"]}
        for metric in BIOMETRIC_DELTA_METRICS:
            deltas = per_metric_deltas[metric]
            result_row["%s_change" % metric] = float(np.mean(deltas)) if deltas else np.nan
            result_row["%s_change_n_sources" % metric] = len(deltas)
        out_rows.append(result_row)

    log("Biometric delta computation: %d (source x metric) row(s) used, %d excluded due to "
        "wearing_detection == 0 (motion artifact)." % (n_used, n_excluded_artifact))
    biometrics_df = pd.DataFrame(out_rows).drop_duplicates(subset="id", keep="first").reset_index(drop=True)
    return biometrics_df, path

def load_game_features(search_dirs):
    """
    Finds every [UserID]_GAME_DATA_[SessionDate].csv (searched recursively
    under AttentionRobotsDesktop folders, with a local-.zip fallback),
    reshapes the wide Bloque1-Bloque4 columns into a LONG-FORMAT table with
    one row per (id, session_file, block) and columns:
        block        -- 1, 2, 3, or 4
        work_speed   -- from velocidadTrabajoBloque<N>
        commission   -- from comisionBloque<N>
        omission     -- from omisionBloque<N>
        correct      -- from aciertosBloque<N>
        percent_commissions -- row-level (id, block) impulsivity rate = 100 *
                       commission / (commission + omission + correct); used by
                       the MixedLM interaction test, not the participant-level
                       aggregate of the same name in game_features_df below.

    Then aggregates the long table per participant into the direct
    replacements for the old CPT-style features:
        work_speed_mean, work_speed_std   (replaces rt_mean, rt_std)
        percent_commissions, percent_omissions, accuracy_pct
    """
    game_files = find_game_data_files(search_dirs)
    if not game_files:
        log("No loose '<UserID>_GAME_DATA_<SessionDate>.csv' files found -- checking local .zip archives...")
        for zip_path, _zip_size in find_zip_archives():
            members = find_game_data_members_in_zip(zip_path)
            if not members:
                continue
            log("  Found %d game-log member(s) inside archive %s -- extracting only these." % (len(members), zip_path))
            dest_dir = get_output_dir()
            for info, user_id in members:
                extracted = extract_member(zip_path, info, dest_dir)
                if extracted:
                    game_files.setdefault(user_id, [])
                    if extracted not in game_files[user_id]:
                        game_files[user_id].append(extracted)

    if not game_files:
        log_search_diagnostics({".csv"})
        raise RuntimeError(
            "Could not find any '<UserID>_GAME_DATA_<SessionDate>.csv' files under an "
            "'AttentionRobotsDesktop' folder in the searched directories or local .zip archives."
        )

    long_rows = []
    files_read, files_failed = 0, 0
    for user_id, paths in game_files.items():
        for path in paths:
            check_size_guard(path, max_mb=20)
            try:
                session_df = pd.read_csv(path)
            except Exception as e:
                log("  Failed to read game data file %s: %s" % (path, e))
                files_failed += 1
                continue
            if session_df.empty:
                continue
            files_read += 1
            session_row = session_df.iloc[0]
            session_name = os.path.basename(path)
            for block in GAME_BLOCK_NUMBERS:
                ws_col = "velocidadTrabajoBloque%d" % block
                om_col = "omisionBloque%d" % block
                co_col = "comisionBloque%d" % block
                ac_col = "aciertosBloque%d" % block
                if ws_col not in session_df.columns and co_col not in session_df.columns:
                    continue
                commission_val = pd.to_numeric(session_row.get(co_col), errors="coerce")
                omission_val = pd.to_numeric(session_row.get(om_col), errors="coerce")
                correct_val = pd.to_numeric(session_row.get(ac_col), errors="coerce")
                block_total = commission_val + omission_val + correct_val
                if pd.isna(block_total) or block_total <= 0:
                    block_percent_commissions = np.nan
                else:
                    block_percent_commissions = 100.0 * commission_val / block_total
                long_rows.append({
                    "id": user_id,
                    "session_file": session_name,
                    "block": block,
                    "work_speed": pd.to_numeric(session_row.get(ws_col), errors="coerce"),
                    "commission": commission_val,
                    "omission": omission_val,
                    "correct": correct_val,
                                                                                       
                    "percent_commissions": block_percent_commissions,
                })

    log("Game-log files: %d read successfully, %d failed to parse." % (files_read, files_failed))
    if not long_rows:
        raise RuntimeError(
            "Could not build the long-format game-log table -- no velocidadTrabajoBloque<N>/ "
            "comisionBloque<N> columns were found in any GAME_DATA file that was read."
        )

    long_df = pd.DataFrame(long_rows)

    agg_rows = []
    for user_id, sub in long_df.groupby("id"):
        work_speed_vals = sub["work_speed"].dropna()
        total_commission = float(sub["commission"].sum(skipna=True))
        total_omission = float(sub["omission"].sum(skipna=True))
        total_correct = float(sub["correct"].sum(skipna=True))
        total_trials = total_commission + total_omission + total_correct
        if total_trials > 0:
            percent_commissions = 100.0 * total_commission / total_trials
            percent_omissions = 100.0 * total_omission / total_trials
            accuracy_pct = 100.0 - percent_commissions - percent_omissions
        else:
            percent_commissions = np.nan
            percent_omissions = np.nan
            accuracy_pct = np.nan
        agg_rows.append({
            "id": user_id,
            "work_speed_mean": float(work_speed_vals.mean()) if len(work_speed_vals) else np.nan,
            "work_speed_std": float(work_speed_vals.std()) if len(work_speed_vals) > 1 else (0.0 if len(work_speed_vals) == 1 else np.nan),
            "percent_commissions": percent_commissions,
            "percent_omissions": percent_omissions,
            "accuracy_pct": accuracy_pct,
            "n_blocks": int(len(sub)),
            "n_sessions": int(sub["session_file"].nunique()),
        })
    game_features_df = pd.DataFrame(agg_rows)
    return long_df, game_features_df

def load_balladeer_participants(found_columns):
    search_dirs = get_search_dirs()
    log("Searching local folders for the BALLADEER dataset files ('%s', '%s', and "
        "'<UserID>_GAME_DATA_<SessionDate>.csv' under 'AttentionRobotsDesktop')..."
        % (DEMOGRAPHICS_FILENAME, BIOMETRICS_FILENAME))
    log("(This script never downloads anything automatically -- register manually at IEEE "
        "DataPort DOI %s or Figshare DOI %s and place the extracted dataset somewhere under "
        "Downloads, next to the script, or in the current working directory.)"
        % (BALLADEER_IEEE_DATAPORT_DOI, BALLADEER_FIGSHARE_DOI))

    demo_df, demo_path = load_demographics(search_dirs)
    found_columns["Demographics file used"] = demo_path
    found_columns["Demographics file shape"] = "%d participant(s)" % len(demo_df)
    found_columns["Group source"] = "users_demographics.json field 'group' (%d = %s, %d = %s)" % (
        GROUP_EXPERIMENTAL_ADHD, GROUP_LABEL_ADHD, GROUP_CONTROL, GROUP_LABEL_CONTROL)
    found_columns["Clean cohort logic"] = (
        "%s = group==%d OR (group==%d AND diagnosed=='yes'); %s = group==%d AND diagnosed=='no'; "
        "%s = diagnosed=='undetermined'" % (
            COHORT_PURE_ADHD, GROUP_EXPERIMENTAL_ADHD, GROUP_CONTROL,
            COHORT_PURE_CONTROL, GROUP_CONTROL, COHORT_SUSPECTED))

    biometrics_df, biometrics_path = load_biometrics(search_dirs)
    found_columns["Biometrics file used"] = biometrics_path
    found_columns["Biometrics file shape"] = "%d participant row(s)" % len(biometrics_df)

    long_df, game_features_df = load_game_features(search_dirs)
    found_columns["Game-log files parsed"] = "%d session file(s) across %d participant(s)" % (
        long_df["session_file"].nunique(), long_df["id"].nunique())
    found_columns["Game long-format rows"] = "%d rows (id x session_file x block)" % len(long_df)

    merged = pd.merge(demo_df, game_features_df, on="id", how="inner")
    if merged.empty:
        raise RuntimeError(
            "Merging '%s' demographics with the game-log features by participant id produced 0 "
            "rows. Check that the UB#### usernames match between users_demographics.json and the "
            "AttentionRobotsDesktop GAME_DATA folders." % DEMOGRAPHICS_FILENAME
        )
    merged = pd.merge(merged, biometrics_df, on="id", how="left")
    merged = merged.drop_duplicates(subset="id", keep="first").reset_index(drop=True)

    confound_cols_present = [c for c in ("age", "sex", "diagnosed") if c in merged.columns]

    core_cols = ["id", "is_adhd", "cohort", "work_speed_mean", "work_speed_std", "accuracy_pct", "percent_commissions"]
    biometric_cols = [c for c in ("eda_change", "prv_change") if c in merged.columns]
    keep_cols = core_cols + biometric_cols + confound_cols_present
    result = merged[keep_cols].dropna(subset=["work_speed_mean", "work_speed_std", "accuracy_pct"]).reset_index(drop=True)

    if len(result) == 0:
        raise RuntimeError(
            "After merging and dropping rows with missing work_speed_mean/work_speed_std/"
            "accuracy_pct, 0 participants remained -- check that the GAME_DATA files actually "
            "contain velocidadTrabajoBloque<N>/comisionBloque<N>/omisionBloque<N>/aciertosBloque<N> "
            "columns."
        )

    n_adhd = int(result["is_adhd"].sum())
    n_control = int((~result["is_adhd"]).sum())
    cohort_counts = result["cohort"].value_counts(dropna=False)
    n_pure_adhd = int(cohort_counts.get(COHORT_PURE_ADHD, 0))
    n_pure_control = int(cohort_counts.get(COHORT_PURE_CONTROL, 0))
    n_suspected = int(cohort_counts.get(COHORT_SUSPECTED, 0))
    n_unclassified_cohort = len(result) - (n_pure_adhd + n_pure_control + n_suspected)
    found_columns["Participants with complete data"] = "%d (%s=%d, %s=%d)" % (
        len(result), GROUP_LABEL_ADHD, n_adhd, GROUP_LABEL_CONTROL, n_control)
    found_columns["Clean cohort split (group+diagnosed)"] = "%s=%d, %s=%d, %s=%d, unclassified=%d" % (
        COHORT_PURE_ADHD, n_pure_adhd, COHORT_PURE_CONTROL, n_pure_control,
        COHORT_SUSPECTED, n_suspected, n_unclassified_cohort)
    log("Final analysis sample: %d participants (%s=%d, %s=%d); clean cohorts: %s=%d, %s=%d, %s=%d, "
        "unclassified=%d."
        % (len(result), GROUP_LABEL_ADHD, n_adhd, GROUP_LABEL_CONTROL, n_control,
           COHORT_PURE_ADHD, n_pure_adhd, COHORT_PURE_CONTROL, n_pure_control,
           COHORT_SUSPECTED, n_suspected, n_unclassified_cohort))

    fatigue_cols = {
        "eda_change_col": "eda_change" if "eda_change" in result.columns else None,
        "prv_change_col": "prv_change" if "prv_change" in result.columns else None,
    }
    if not fatigue_cols["eda_change_col"] and not fatigue_cols["prv_change_col"]:
        log("Warning: no usable EDA/PRV change columns were found -- the biometric change "
            "analysis section of the report will be empty.")

    return result, fatigue_cols, confound_cols_present, long_df

CALIBRATION_FEATURE_COLUMNS = ["work_speed_mean", "work_speed_std", "accuracy_pct"]
CALIBRATION_FEATURE_DISPLAY = {
    "work_speed_mean": "Work Speed Mean (velocidadTrabajo)",
    "work_speed_std": "Work Speed SD (velocidadTrabajo variability)",
    "accuracy_pct": "Accuracy % (complement of comision / percent_commissions)",
}

def compute_calibration_stats(real_df):
    """
    Empirical mean/sd for each calibration feature, computed separately for
    the Experimental (ADHD) and Control groups directly from the real
    BALLADEER participants -- plus the real overall [min, max] bounds per
    feature, used to clip the simulated anchors below so they can never
    drift outside the numeric range the real participants actually occupy.
    """
    def stats_for(col, is_adhd_flag):
        vals = pd.to_numeric(real_df.loc[real_df["is_adhd"] == is_adhd_flag, col], errors="coerce").dropna()
        if len(vals) == 0:
            return {"mean": 0.0, "sd": 1.0, "n": 0}
        mean_val = float(vals.mean())
        sd_val = float(vals.std()) if len(vals) > 1 else 0.0
        if sd_val <= 1e-9:
            sd_val = max(abs(mean_val) * 0.1, 1.0)
        return {"mean": mean_val, "sd": sd_val, "n": int(len(vals))}

    def bounds_for(col):
        vals = pd.to_numeric(real_df[col], errors="coerce").dropna()
        if len(vals) == 0:
            return (0.0, 1.0)
        return (float(vals.min()), float(vals.max()))

    stats = {}
    for col in CALIBRATION_FEATURE_COLUMNS:
        stats[col] = {
            "adhd": stats_for(col, True),
            "control": stats_for(col, False),
            "bounds": bounds_for(col),
        }
    return stats

def simulate_hypothesis_anchors(calibration_stats, n_sustainable=120, n_decompensated=32,
                                 n_compensated=32, seed=42):
    """
    Monte-Carlo-generates the three hypothesis anchor clouds directly from
    this dataset's own empirical work-speed/accuracy parameters (see
    compute_calibration_stats), instead of reusing fixed HYPERAKTIV-scale
    coordinates. Every generated point is clipped to the real participants'
    own [min, max] range per feature, so anchors can never land outside the
    numeric space the real BALLADEER participants actually occupy.

      - sustainable_flow ("True Resilience"): centered on the Control
        group's own empirical profile (steady speed, low variability, high
        accuracy).
      - super_d1_flow (Subtype 1, "Decompensated Sprint"): the fast/high-
        impulsivity end of the ADHD distribution (speed above the ADHD mean,
        accuracy pulled toward the low end of the ADHD accuracy range).
      - noise_resonance (Subtype 2, "Compensated Crash"): the slow/fatigued
        end of the ADHD distribution with elevated timing variability, but
        accuracy preserved near/above the ADHD mean (the "manual brake"
        keeps false clicks rare).
    """
    rng = np.random.default_rng(seed)
    speed = calibration_stats["work_speed_mean"]
    spread = calibration_stats["work_speed_std"]
    acc = calibration_stats["accuracy_pct"]

    def draw_cluster(n, speed_c, speed_s, spread_c, spread_s, acc_c, acc_s):
        pts = rng.normal(
            loc=[speed_c, spread_c, acc_c],
            scale=[max(abs(speed_s), 1e-6) * 0.6, max(abs(spread_s), 1e-6) * 0.6, max(abs(acc_s), 1e-6) * 0.6],
            size=(n, 3),
        )
        pts[:, 0] = np.clip(pts[:, 0], speed["bounds"][0], speed["bounds"][1])
        pts[:, 1] = np.clip(pts[:, 1], spread["bounds"][0], spread["bounds"][1])
        pts[:, 2] = np.clip(pts[:, 2], acc["bounds"][0], acc["bounds"][1])
        return pts

    sustainable = draw_cluster(
        n_sustainable,
        speed["control"]["mean"], speed["control"]["sd"],
        spread["control"]["mean"], spread["control"]["sd"] * 0.7,
        acc["control"]["mean"], acc["control"]["sd"] * 0.7,
    )
    decompensated = draw_cluster(
        n_decompensated,
        speed["adhd"]["mean"] + 0.5 * speed["adhd"]["sd"], speed["adhd"]["sd"],
        spread["adhd"]["mean"], spread["adhd"]["sd"],
        acc["adhd"]["mean"] - 0.6 * acc["adhd"]["sd"], acc["adhd"]["sd"],
    )
    compensated = draw_cluster(
        n_compensated,
        speed["adhd"]["mean"] - 0.5 * speed["adhd"]["sd"], speed["adhd"]["sd"],
        spread["adhd"]["mean"] + 0.6 * spread["adhd"]["sd"], spread["adhd"]["sd"],
        acc["adhd"]["mean"] + 0.3 * acc["adhd"]["sd"], acc["adhd"]["sd"],
    )

    return {
        "sustainable_flow": sustainable,
        "super_d1_flow": decompensated,
        "noise_resonance": compensated,
    }

def standardize_on_real(real_vecs):
    """
    Fits the z-score scaler strictly on the real participant vectors
    (scaler.fit(real_data)) -- never jointly with the simulated anchors.
    The returned mean/std must then be reused to transform both the real
    vectors and the calibrated Monte-Carlo anchors, so both live on the
    same, real-data-defined scale.
    """
    mean = real_vecs.mean(axis=0)
    std = real_vecs.std(axis=0)
    std[std == 0] = 1.0
    return mean, std

def classify_nearest_cluster(vecs_z, centroids, cluster_names):
    centroid_matrix = np.vstack([centroids[name] for name in cluster_names])
    dists = np.linalg.norm(vecs_z[:, None, :] - centroid_matrix[None, :, :], axis=2)
    nearest_idx = np.argmin(dists, axis=1)
    return np.array([cluster_names[i] for i in nearest_idx])

def run_mannwhitney_by_cluster(real_df, cluster_names, metric_col="percent_commissions"):
    n_tests = len(cluster_names)
    bonferroni_alpha = BONFERRONI_BASE_ALPHA / n_tests if n_tests else BONFERRONI_BASE_ALPHA
    results = {}
    for cluster_key in cluster_names:
        sub = real_df[real_df["nearest_cluster"] == cluster_key]
        adhd_vals = sub.loc[sub["cohort"] == COHORT_PURE_ADHD, metric_col].dropna()
        control_vals = sub.loc[sub["cohort"] == COHORT_PURE_CONTROL, metric_col].dropna()
        n1, n2 = len(adhd_vals), len(control_vals)
        if n1 == 0 or n2 == 0:
            results[cluster_key] = {
                "n1_adhd": n1, "n2_control": n2, "u_stat": None, "p_value": None,
                "effect_size_r": None, "significant": False,
            }
            continue
        u_stat, p_value = scipy_stats.mannwhitneyu(adhd_vals, control_vals, alternative="two-sided")
        effect_size_r = 1.0 - (2.0 * u_stat) / (n1 * n2)
        results[cluster_key] = {
            "n1_adhd": n1, "n2_control": n2, "u_stat": float(u_stat), "p_value": float(p_value),
            "effect_size_r": float(effect_size_r), "significant": bool(p_value < bonferroni_alpha),
        }
    return results, bonferroni_alpha

def run_permutation_test(real_df, real_z, centroids, cluster_names, target_cluster, metric_col,
                          real_p_value, n_permutations=N_PERMUTATIONS):
    """
    Label-shuffle permutation test restricted to the two clean cohorts
    (Pure ADHD / Pure Control) inside the target cluster -- Suspected ADHD
    participants never receive a shuffled label, since they are not part of
    either 'pure' reference group being compared.
    """
    rng = np.random.default_rng(42)
    cluster_assignment = real_df["nearest_cluster"].to_numpy()
    metric_values = real_df[metric_col].to_numpy()
    pure_mask = real_df["cohort"].isin([COHORT_PURE_ADHD, COHORT_PURE_CONTROL]).to_numpy()
    is_pure_adhd = (real_df["cohort"] == COHORT_PURE_ADHD).to_numpy()

    in_target = (cluster_assignment == target_cluster) & pure_mask
    if in_target.sum() == 0:
        return {"empirical_p": None, "n_permutations": n_permutations, "note": "no participants in target cluster"}

    target_is_adhd = is_pure_adhd[in_target]
    target_metric = metric_values[in_target]

    shuffle_p_values = []
    for _ in range(n_permutations):
        shuffled = target_is_adhd.copy()
        rng.shuffle(shuffled)
        adhd_vals = target_metric[shuffled]
        control_vals = target_metric[~shuffled]
        adhd_vals = adhd_vals[~pd.isna(adhd_vals)]
        control_vals = control_vals[~pd.isna(control_vals)]
        if len(adhd_vals) == 0 or len(control_vals) == 0:
            continue
        try:
            _, p = scipy_stats.mannwhitneyu(adhd_vals, control_vals, alternative="two-sided")
        except ValueError:
            continue
        shuffle_p_values.append(p)

    if not shuffle_p_values:
        return {"empirical_p": None, "n_permutations": n_permutations, "note": "no valid shuffles"}

    shuffle_p_values = np.array(shuffle_p_values)
    empirical_p = float(np.mean(shuffle_p_values <= real_p_value))
    return {
        "empirical_p": empirical_p,
        "n_permutations": int(len(shuffle_p_values)),
        "real_p_value": real_p_value,
        "note": None,
    }

def run_mixedlm_within_adhd_test(long_df, real_df):
    """
    Within-ADHD confirmatory test: a Linear Mixed-Effects Model fit on the
    long-format (id x block) table, restricted STRICTLY to Pure ADHD
    participants (Pure Control and Suspected are fully excluded). It compares
    the block-to-block impulsivity dynamics of the two ADHD subtypes assigned
    by the nearest-centroid step -- Sprint ('super_d1_flow') vs Crash
    ('noise_resonance').

    Formula: percent_commissions ~ block * cluster
    Random effect (groups): participant id (repeated measures per person).

    Returns a dict:
        {"available": True, "coefficient", "std_err", "z_value", "p_value",
         "n_participants", "n_sprint", "n_crash", "formula"}
    or
        {"available": False, "reason": "<why the test could not run>"}

    Must never raise -- statsmodels may be missing on a mobile Python build,
    and MixedLM may fail to converge on small/noisy samples. Any such problem
    is caught here and reported as a skip reason, never allowed to crash the run.
    """
    try:
        import statsmodels.formula.api as smf
        from statsmodels.tools.sm_exceptions import ConvergenceWarning
    except Exception as e:
        return {"available": False, "reason": "statsmodels is not available (%s)" % e}

    try:
        cohort_lookup = real_df.set_index("id")["cohort"]
        cluster_lookup = real_df.set_index("id")["nearest_cluster"]
        sub = long_df.copy()
        sub["clean_cohort"] = sub["id"].map(cohort_lookup)
        sub = sub[sub["clean_cohort"] == COHORT_PURE_ADHD]
        sub["cluster"] = sub["id"].map(cluster_lookup).map(SUBTYPE_SHORT_LABELS)
        sub = sub.dropna(subset=["percent_commissions", "block", "cluster"])
        if sub.empty:
            return {
                "available": False,
                "reason": "no Pure ADHD rows left with an assigned Sprint/Crash subtype and non-missing percent_commissions",
            }
        sub["cluster"] = sub["cluster"].astype(str)
        sub["block"] = pd.to_numeric(sub["block"], errors="coerce")
        sub = sub.dropna(subset=["block"])

        n_sprint = sub.loc[sub["cluster"] == "Sprint", "id"].nunique()
        n_crash = sub.loc[sub["cluster"] == "Crash", "id"].nunique()
        if n_sprint < 2 or n_crash < 2:
            return {
                "available": False,
                "reason": "insufficient participants for MixedLM (n_Sprint=%d, n_Crash=%d, need >=2 each)"
                          % (n_sprint, n_crash),
            }

        formula = "percent_commissions ~ block * cluster"
        model = smf.mixedlm(formula, data=sub, groups=sub["id"])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            mdf = model.fit()
        non_convergence = [w for w in caught if issubclass(w.category, ConvergenceWarning)]
        if non_convergence:
            return {"available": False, "reason": "model did not converge (%s)" % non_convergence[0].message}

        interaction_terms = [name for name in mdf.params.index if name.startswith("block:")]
        if len(interaction_terms) != 1:
            return {
                "available": False,
                "reason": "unexpected number of interaction terms in MixedLM result (%d found)" % len(interaction_terms),
            }
        term = interaction_terms[0]

        return {
            "available": True,
            "coefficient": float(mdf.params[term]),
            "std_err": float(mdf.bse[term]),
            "z_value": float(mdf.tvalues[term]),
            "p_value": float(mdf.pvalues[term]),
            "n_participants": int(n_sprint + n_crash),
            "n_sprint": int(n_sprint),
            "n_crash": int(n_crash),
            "formula": formula,
        }
    except Exception as e:
        return {"available": False, "reason": "%s: %s" % (type(e).__name__, e)}

def summarize_confounder_series(series):
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() >= max(1, int(0.5 * len(series.dropna()))):
        valid = numeric.dropna()
        if len(valid) == 0:
            return None
        return {"type": "numeric", "mean": float(valid.mean()), "std": float(valid.std()) if len(valid) > 1 else 0.0, "n": int(len(valid))}
    valid = series.dropna().astype(str)
    if len(valid) == 0:
        return None
    counts = valid.value_counts().to_dict()
    return {"type": "categorical", "counts": counts, "n": int(len(valid))}

def build_confounder_summary(real_df, confound_cols_present):
    summary = {}
    for col in confound_cols_present:
        if col not in real_df.columns:
            continue
        adhd_summary = summarize_confounder_series(real_df.loc[real_df["is_adhd"], col])
        control_summary = summarize_confounder_series(real_df.loc[~real_df["is_adhd"], col])
        summary[col] = {"adhd": adhd_summary, "control": control_summary}
    return summary

def format_confounder_field(field_name, field_summary):
    display_names = {"age": "Age", "sex": "Sex/Gender", "diagnosed": "Clinical ADHD Diagnosis (self/clinician-reported)"}
    display_name = display_names.get(field_name, field_name)
    lines = ["  %s:" % display_name]
    for group_key, group_label in (("adhd", GROUP_LABEL_ADHD), ("control", GROUP_LABEL_CONTROL)):
        info = field_summary.get(group_key)
        if not info:
            lines.append("    %s: no data" % group_label)
            continue
        if info["type"] == "numeric":
            lines.append("    %s: mean=%.2f, sd=%.2f (n=%d)" % (group_label, info["mean"], info["std"], info["n"]))
        else:
            counts_str = ", ".join("%s=%d" % (k, v) for k, v in sorted(info["counts"].items()))
            lines.append("    %s: %s (n=%d)" % (group_label, counts_str, info["n"]))
    return lines

def write_clean_report(output_path, found_columns, real_df, cluster_table, subtype_stats,
                        fatigue_bar_groups, mannwhitney_results, bonferroni_alpha,
                        permutation_result, confounder_summary, calibration_stats,
                        mixedlm_result):
    lines = []
    lines.append("=" * 70)
    lines.append("HEALTHY_VALID (BALLADEER) -- ACADEMIC DIAGNOSTIC REPORT")
    lines.append("=" * 70)
    lines.append("")

    lines.append("0. DATASET NOTES")
    lines.append("-" * 70)
    lines.append("  Source: BALLADEER open dataset (Nesplora-independent; EmbracePlus ")
    lines.append("  biometrics + Attention Robots game logs). DOI: %s" % BALLADEER_SCIDATA_DOI)
    lines.append("  Access: IEEE DataPort DOI %s / Figshare DOI %s (manual registration "
                 "required; this script never downloads anything automatically)."
                 % (BALLADEER_IEEE_DATAPORT_DOI, BALLADEER_FIGSHARE_DOI))
    lines.append("  Group assignment: users_demographics.json field 'group' (%d = %s, %d = %s)."
                 % (GROUP_EXPERIMENTAL_ADHD, GROUP_LABEL_ADHD, GROUP_CONTROL, GROUP_LABEL_CONTROL))
    lines.append("  Clean diagnostic cohorts (used for cohort-based stats/plots): %s = group==%d "
                 "OR (group==%d AND diagnosed=='yes'); %s = group==%d AND diagnosed=='no'; "
                 "%s = diagnosed=='undetermined'."
                 % (COHORT_PURE_ADHD, GROUP_EXPERIMENTAL_ADHD, GROUP_CONTROL,
                    COHORT_PURE_CONTROL, GROUP_CONTROL, COHORT_SUSPECTED))
    lines.append("")

    lines.append("1. FILES AND COLUMNS FOUND")
    lines.append("-" * 70)
    for key, value in found_columns.items():
        lines.append("  %s: %s" % (key, value))
    lines.append("")

    lines.append("2. MONTE-CARLO ANCHOR CALIBRATION (empirical parameters, real BALLADEER data)")
    lines.append("-" * 70)
    lines.append("  The hypothesis anchors are re-simulated on every run from this dataset's ")
    lines.append("  own empirical parameters below (not a fixed, dataset-independent table), ")
    lines.append("  then clipped to the real participants' own numeric range.")
    lines.append("")
    for col in CALIBRATION_FEATURE_COLUMNS:
        info = calibration_stats[col]
        lines.append("  %s:" % CALIBRATION_FEATURE_DISPLAY.get(col, col))
        lines.append("    %s: mean=%.3f, sd=%.3f (n=%d)"
                     % (GROUP_LABEL_ADHD, info["adhd"]["mean"], info["adhd"]["sd"], info["adhd"]["n"]))
        lines.append("    %s: mean=%.3f, sd=%.3f (n=%d)"
                     % (GROUP_LABEL_CONTROL, info["control"]["mean"], info["control"]["sd"], info["control"]["n"]))
        lines.append("    Real-data bounds used to clip anchors: [%.3f, %.3f]" % info["bounds"])
    lines.append("")

    lines.append("3. CLUSTER DISTRIBUTION (nearest hypothesis anchor, forced classification)")
    lines.append("-" * 70)
    header = "%-38s %6s %6s %6s %10s %10s %10s" % (
        "Cluster", "Total", GROUP_LABEL_ADHD[:6], GROUP_LABEL_CONTROL[:6], "PureADHD", "PureCtrl", "Suspect")
    lines.append(header)
    for cluster_key, row in cluster_table.items():
        display = CLUSTER_DISPLAY_LABELS.get(cluster_key, cluster_key)
        lines.append("%-38s %6d %6d %6d %10d %10d %10d" % (
            display, row["total"], row["adhd"], row["control"],
            row["pure_adhd"], row["pure_control"], row["suspected"]))
    lines.append("")

    lines.append("4. ADHD SUBTYPE PROFILES (BALLADEER Attention Robots game metrics)")
    lines.append("-" * 70)
    lines.append("  %-55s %8s %14s %14s" % ("Subtype", "n", "Pct.Comm.", "Accuracy%%"))
    for row_label, n, mean_pc, mean_acc in subtype_stats:
        pc_str = "%.2f" % mean_pc if mean_pc is not None else "N/A"
        acc_str = "%.2f" % mean_acc if mean_acc is not None else "N/A"
        lines.append("  %-55s %8d %14s %14s" % (row_label, n, pc_str, acc_str))
    lines.append("")

    prv_available = any(g["prv_change_mean"] is not None for g in fatigue_bar_groups)
    eda_available = any(g["eda_change_mean"] is not None for g in fatigue_bar_groups)
    lines.append("5. BIOMETRIC CHANGE ANALYSIS: EMBRACEPLUS EDA%s (fixed)"
                 % (" / PRV" if prv_available else " (PRV skipped -- no usable data this run)"))
    lines.append("   (delta = mean(last two min) - mean(first two min))")
    lines.append("-" * 70)
    lines.append("  Delta is averaged across all activity sources (S1/S6/S11/Cognifit/Robots)")
    lines.append("  for which wearing_detection was present and non-zero; rows where ")
    lines.append("  wearing_detection == 0 were excluded as motion artifacts before averaging.")
    lines.append("  Broken down by clean cohort (Pure Control / Pure ADHD / Suspected ADHD) x subtype.")
    if not prv_available:
        lines.append("  NOTE: PRV is entirely NaN for every participant/source in this run's biometrics ")
        lines.append("  file, so the PRV column is omitted below and from the fatigue-dynamics plot -- ")
        lines.append("  only EDA is shown. This is a data-coverage gap in the source export, not a bug.")
    lines.append("")
    if not eda_available and not prv_available:
        lines.append("  No usable EDA/PRV delta data was found (missing columns, or all rows ")
        lines.append("  were excluded by the wearing_detection filter).")
    else:
        label_width = max(30, max(len(g["label"]) for g in fatigue_bar_groups) + 2)
        header = ("%-" + str(label_width) + "s") % "Cohort / Subtype"
        if prv_available:
            header += "%8s%18s%18s" % ("n", "EDA Change", "PRV Change")
        else:
            header += "%8s%18s" % ("n", "EDA Change")
        lines.append(header)
        for g in fatigue_bar_groups:
            row = ("%-" + str(label_width) + "s") % g["label"]
            row += "%8d" % g["n"]
            row += "%18s" % ("%.4f" % g["eda_change_mean"] if g["eda_change_mean"] is not None else "N/A")
            if prv_available:
                row += "%18s" % ("%.4f" % g["prv_change_mean"] if g["prv_change_mean"] is not None else "N/A")
            lines.append(row)
    lines.append("")

    lines.append("6. STATISTICAL VALIDATION: MANN-WHITNEY U (per cluster) + PERMUTATION TEST + MIXEDLM")
    lines.append("-" * 70)
    lines.append("  Groups compared: %s vs %s | Metric: %s" % (COHORT_PURE_ADHD, COHORT_PURE_CONTROL, PERMUTATION_TARGET_METRIC))
    lines.append("  Bonferroni-corrected alpha: %.5f (base alpha %.2f / %d clusters)"
                 % (bonferroni_alpha, BONFERRONI_BASE_ALPHA, len(mannwhitney_results)))
    lines.append("")
    for cluster_key, res in mannwhitney_results.items():
        display = CLUSTER_DISPLAY_LABELS.get(cluster_key, cluster_key)
        if res["p_value"] is None:
            lines.append("  %s: insufficient data (n_%s=%d, n_%s=%d)"
                         % (display, COHORT_PURE_ADHD, res["n1_adhd"], COHORT_PURE_CONTROL, res["n2_control"]))
            continue
        sig_str = "SIGNIFICANT" if res["significant"] else "not significant"
        lines.append("  %s: U=%.2f, p=%.5f, effect size r=%.3f, n_%s=%d, n_%s=%d -> %s"
                     % (display, res["u_stat"], res["p_value"], res["effect_size_r"],
                        COHORT_PURE_ADHD, res["n1_adhd"], COHORT_PURE_CONTROL, res["n2_control"], sig_str))
    lines.append("")
    if permutation_result.get("empirical_p") is not None:
        lines.append("  Permutation test (target cluster: %s, %d label-shuffles):"
                     % (CLUSTER_DISPLAY_LABELS.get(PERMUTATION_TARGET_CLUSTER, PERMUTATION_TARGET_CLUSTER),
                        permutation_result["n_permutations"]))
        lines.append("    Real analytical p-value: %.5f" % permutation_result["real_p_value"])
        lines.append("    Empirical permutation p-value: %.5f" % permutation_result["empirical_p"])
    else:
        lines.append("  Permutation test could not be run: %s" % permutation_result.get("note"))
    lines.append("")

    lines.append("  Linear Mixed-Effects Model (MixedLM), within-ADHD subtype dynamics:")
    lines.append("    Formula: percent_commissions ~ block * cluster | groups=participant id")
    lines.append("    Sample: strictly %s only, split by assigned subtype (Sprint vs Crash); "
                 "Pure Control and Suspected are fully excluded." % COHORT_PURE_ADHD)
    if not mixedlm_result.get("available"):
        lines.append("    MixedLM тест внутри ADHD пропущен: %s" % mixedlm_result.get("reason"))
    else:
        lines.append("    n participants: %d (Sprint=%d, Crash=%d)"
                     % (mixedlm_result["n_participants"], mixedlm_result["n_sprint"], mixedlm_result["n_crash"]))
        lines.append("    Interaction effect (block x cluster, Sprint vs Crash):")
        lines.append("      Coefficient: %.5f" % mixedlm_result["coefficient"])
        lines.append("      Std.Err.:    %.5f" % mixedlm_result["std_err"])
        lines.append("      z-value:     %.5f" % mixedlm_result["z_value"])
        lines.append("      p-value:     %.5f" % mixedlm_result["p_value"])
        if mixedlm_result["p_value"] < 0.05:
            lines.append("      ПОДТВЕРЖДЕНО: Подтипы Sprint и Crash демонстрируют статистически значимо "
                         "разную динамику импульсивности во времени.")
        else:
            lines.append("      НЕ ПОДТВЕРЖДЕНО: Динамика изменения ошибок по блокам между подтипами "
                         "внутри ADHD не имеет значимых различий.")
    lines.append("")

    lines.append("7. CONFOUNDER CHECK")
    lines.append("-" * 70)
    if not confounder_summary:
        lines.append("  No confounder columns (age/sex/diagnosed) were found in users_demographics.json.")
    else:
        for field_name, field_summary in confounder_summary.items():
            lines.extend(format_confounder_field(field_name, field_summary))
    lines.append("")

    lines.append("-" * 70)
    lines.append("NOTE: The hypothesis anchor points (see section 2) are re-simulated on every ")
    lines.append("run from this dataset's own empirical parameters, not reused from a fixed ")
    lines.append("prior simulation. The z-score scaler is fit strictly on the real participant ")
    lines.append("vectors (never jointly with the anchors), then reused to transform both the ")
    lines.append("real vectors and the anchors before nearest-centroid classification. ")
    lines.append("Interpret cluster membership as a relative, hypothesis-driven grouping, not ")
    lines.append("an absolute clinical classification.")
    lines.append("=" * 70)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log("Wrote report: %s" % output_path)

def build_scatter_plot(real_df, hypotheses, color_col, cmap, title, cbar_label, output_name, hue_norm=(0, 100)):
    fig, ax = plt.subplots(figsize=(9, 7))

    for cluster_key, pts in hypotheses.items():
        color = CLUSTER_SCATTER_COLORS.get(cluster_key, "gray")
        ax.scatter(pts[:, 0], pts[:, 1], c=color, alpha=0.15, s=40, edgecolors="none",
                   label="%s (hypothesis)" % CLUSTER_DISPLAY_LABELS.get(cluster_key, cluster_key))

    cohort_marker_style = {
        COHORT_PURE_ADHD: {"marker": "^", "edgecolor": "black"},
        COHORT_PURE_CONTROL: {"marker": "o", "edgecolor": "black"},
        COHORT_SUSPECTED: {"marker": "s", "edgecolor": "darkorange"},
    }

    if "cohort" in real_df.columns:
        cohort_col = real_df["cohort"]
    else:
        cohort_col = pd.Series([None] * len(real_df), index=real_df.index)
    classified_mask = cohort_col.isin(list(cohort_marker_style.keys())).to_numpy()

    last_scatter = None
    for cohort, style in cohort_marker_style.items():
        mask = (cohort_col == cohort).to_numpy()
        if not mask.any():
            continue
        last_scatter = ax.scatter(
            real_df.loc[mask, "work_speed_mean"], real_df.loc[mask, "work_speed_std"],
            c=real_df.loc[mask, color_col], cmap=cmap, vmin=hue_norm[0], vmax=hue_norm[1],
            marker=style["marker"], s=90, edgecolors=style["edgecolor"], linewidths=0.9,
            label="%s Participants" % cohort,
        )

    unclassified_mask = ~classified_mask
    if unclassified_mask.any():
        unclassified_scatter = ax.scatter(
            real_df.loc[unclassified_mask, "work_speed_mean"], real_df.loc[unclassified_mask, "work_speed_std"],
            c=real_df.loc[unclassified_mask, color_col], cmap=cmap, vmin=hue_norm[0], vmax=hue_norm[1],
            marker="x", s=90, edgecolors="gray", linewidths=0.9, label="Unclassified",
        )
        if last_scatter is None:
            last_scatter = unclassified_scatter

    if last_scatter is not None:
        cbar = fig.colorbar(last_scatter, ax=ax)
        cbar.set_label(cbar_label)

    ax.set_xlabel("Work Speed Mean, BALLADEER Attention Robots (responses/min)")
    ax.set_ylabel("Work Speed SD / Variability, BALLADEER Attention Robots (responses/min)")
    ax.set_title(title)
    ax.set_ylim(bottom=0)

    legend_elements = [
        Line2D([0], [0], marker=style["marker"], color="w", markerfacecolor="gray",
               markeredgecolor=style["edgecolor"], markersize=10, label="%s Participants" % cohort)
        for cohort, style in cohort_marker_style.items()
    ]
    legend_elements.append(
        Line2D([0], [0], marker="x", color="w", markerfacecolor="gray", markeredgecolor="gray",
               markersize=10, label="Unclassified")
    )
    for cluster_key in hypotheses:
        legend_elements.append(Patch(facecolor=CLUSTER_SCATTER_COLORS.get(cluster_key, "gray"), alpha=0.4,
                                      label=CLUSTER_DISPLAY_LABELS.get(cluster_key, cluster_key)))
    ax.legend(handles=legend_elements, loc="best", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_name, dpi=150)
    plt.close(fig)
    log("Wrote plot: %s" % output_name)

def compute_fatigue_bar_groups(real_df, fatigue_cols):
                                                                            
    eda_col = fatigue_cols.get("eda_change_col")
    prv_col = fatigue_cols.get("prv_change_col")
    subtype_order = ("sustainable_flow", "super_d1_flow", "noise_resonance")

    groups = []
    for cohort in COHORT_ORDER:
        if "cohort" in real_df.columns:
            cohort_df = real_df[real_df["cohort"] == cohort]
        else:
            cohort_df = real_df.iloc[0:0]
        for cluster_key in subtype_order:
            if "nearest_cluster" in cohort_df.columns:
                sub = cohort_df[cohort_df["nearest_cluster"] == cluster_key]
            else:
                sub = cohort_df.iloc[0:0]
            n = len(sub)
            if n == 0:
                continue
            eda_mean = None
            if eda_col and eda_col in sub.columns:
                vals = pd.to_numeric(sub[eda_col], errors="coerce").dropna()
                eda_mean = float(vals.mean()) if len(vals) else None
            prv_mean = None
            if prv_col and prv_col in sub.columns:
                vals = pd.to_numeric(sub[prv_col], errors="coerce").dropna()
                prv_mean = float(vals.mean()) if len(vals) else None
            subtype_label = CLUSTER_DISPLAY_LABELS.get(cluster_key, cluster_key)
            groups.append({
                "cohort": cohort,
                "cluster_key": cluster_key,
                "label": "%s / %s" % (cohort, subtype_label),
                "short_label": "%s\n%s" % (cohort, subtype_label),
                "n": n,
                "eda_change_mean": eda_mean,
                "prv_change_mean": prv_mean,
            })
    return groups

def build_fatigue_dynamics_plot(fatigue_bar_groups, output_name):
                                                                             
    if not fatigue_bar_groups:
        fig, ax = plt.subplots(figsize=(11, 6.5))
        ax.text(0.5, 0.5, "No EDA/PRV delta data available for this run.",
                 ha="center", va="center", fontsize=11, transform=ax.transAxes)
        ax.set_axis_off()
        fig.savefig(output_name, dpi=150)
        plt.close(fig)
        return

    prv_available = any(g["prv_change_mean"] is not None for g in fatigue_bar_groups)
    eda_available = any(g["eda_change_mean"] is not None for g in fatigue_bar_groups)

    fig, ax = plt.subplots(figsize=(11, 6.5))

    labels = [g["short_label"] for g in fatigue_bar_groups]
    eda_values = [g["eda_change_mean"] for g in fatigue_bar_groups]
    prv_values = [g["prv_change_mean"] for g in fatigue_bar_groups] if prv_available else []
    numeric_values = [v for v in (eda_values + prv_values) if v is not None]

    if numeric_values:
        v_max = max(abs(v) for v in numeric_values)
        pad = v_max * 0.35 if v_max > 0 else 1.0
        ylim = (-(v_max + pad), (v_max + pad))
    else:
        ylim = (-1.0, 1.0)

    x_positions = list(range(len(labels)))
    label_offset = 0.06 * (ylim[1] - ylim[0])

    if prv_available:
                                                  
        bar_width = 0.38
        eda_plot_values = [v if v is not None else 0.0 for v in eda_values]
        prv_plot_values = [v if v is not None else 0.0 for v in prv_values]

        eda_bars = ax.bar([i - bar_width / 2 for i in x_positions], eda_plot_values, width=bar_width,
                           color=FATIGUE_BAR_COLOR_EDA, edgecolor="black", label="EDA Change")
        prv_bars = ax.bar([i + bar_width / 2 for i in x_positions], prv_plot_values, width=bar_width,
                           color=FATIGUE_BAR_COLOR_PRV, edgecolor="black", label="PRV Change")

        for bar, value in zip(eda_bars, eda_values):
            height = bar.get_height()
            text = "%.4f" % value if value is not None else "N/A"
            y_pos = height + label_offset if height >= 0 else height - label_offset
            va = "bottom" if height >= 0 else "top"
            ax.text(bar.get_x() + bar.get_width() / 2, y_pos, text, ha="center", va=va, fontsize=7)
        for bar, value in zip(prv_bars, prv_values):
            height = bar.get_height()
            text = "%.4f" % value if value is not None else "N/A"
            y_pos = height + label_offset if height >= 0 else height - label_offset
            va = "bottom" if height >= 0 else "top"
            ax.text(bar.get_x() + bar.get_width() / 2, y_pos, text, ha="center", va=va, fontsize=7)
        title = "BALLADEER: EDA / PRV Change by Clean Cohort and Subtype"
    else:
                                                                            
        bar_width = 0.55
        eda_plot_values = [v if v is not None else 0.0 for v in eda_values]

        eda_bars = ax.bar(x_positions, eda_plot_values, width=bar_width,
                           color=FATIGUE_BAR_COLOR_EDA, edgecolor="black", label="EDA Change")

        for bar, value in zip(eda_bars, eda_values):
            height = bar.get_height()
            text = "%.4f" % value if value is not None else "N/A"
            y_pos = height + label_offset if height >= 0 else height - label_offset
            va = "bottom" if height >= 0 else "top"
            ax.text(bar.get_x() + bar.get_width() / 2, y_pos, text, ha="center", va=va, fontsize=7)
        title = "BALLADEER: EDA Change by Clean Cohort and Subtype (PRV omitted -- no usable data)"

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylim(*ylim)
    ax.set_ylabel("Mean Change (last two min - first two min)")
    ax.set_title(title)
    ax.set_xticks(x_positions)
    tick_labels = ["%s\n(n=%d)" % (g["short_label"], g["n"]) for g in fatigue_bar_groups]
    ax.set_xticklabels(tick_labels, rotation=25, ha="right", fontsize=8)
    if eda_available or prv_available:
        ax.legend(loc="best", fontsize=9)

    fig.tight_layout()
    fig.savefig(output_name, dpi=150)
    plt.close(fig)
    log("Wrote plot: %s" % output_name)

def run_validation():
    found_columns = {}
    real_df, fatigue_cols, confound_cols_present, long_df = load_balladeer_participants(found_columns)

    calibration_stats = compute_calibration_stats(real_df)
    for col in CALIBRATION_FEATURE_COLUMNS:
        info = calibration_stats[col]
        log("Calibration %s: %s mean=%.3f sd=%.3f (n=%d), %s mean=%.3f sd=%.3f (n=%d), bounds=[%.3f, %.3f]"
            % (col, GROUP_LABEL_ADHD, info["adhd"]["mean"], info["adhd"]["sd"], info["adhd"]["n"],
               GROUP_LABEL_CONTROL, info["control"]["mean"], info["control"]["sd"], info["control"]["n"],
               info["bounds"][0], info["bounds"][1]))

    hypotheses = simulate_hypothesis_anchors(calibration_stats)
    cluster_names = list(hypotheses.keys())

    real_vecs = real_df[CALIBRATION_FEATURE_COLUMNS].to_numpy(dtype=float)
    mean, std = standardize_on_real(real_vecs)

    centroids_z = {name: (pts - mean) / std for name, pts in hypotheses.items()}
    centroids_z = {name: pts.mean(axis=0) for name, pts in centroids_z.items()}
    real_vecs_z = (real_vecs - mean) / std

    real_df = real_df.copy()
    real_df["nearest_cluster"] = classify_nearest_cluster(real_vecs_z, centroids_z, cluster_names)

    cluster_table = {}
    for cluster_key in cluster_names:
        sub = real_df[real_df["nearest_cluster"] == cluster_key]
        cluster_table[cluster_key] = {
            "total": len(sub),
            "adhd": int(sub["is_adhd"].sum()),
            "control": int((~sub["is_adhd"]).sum()),
            "pure_adhd": int((sub["cohort"] == COHORT_PURE_ADHD).sum()),
            "pure_control": int((sub["cohort"] == COHORT_PURE_CONTROL).sum()),
            "suspected": int((sub["cohort"] == COHORT_SUSPECTED).sum()),
        }
        log("Cluster %s: total=%d, %s=%d, %s=%d, pure_adhd=%d, pure_control=%d, suspected=%d"
            % (CLUSTER_DISPLAY_LABELS.get(cluster_key, cluster_key), cluster_table[cluster_key]["total"],
               GROUP_LABEL_ADHD, cluster_table[cluster_key]["adhd"],
               GROUP_LABEL_CONTROL, cluster_table[cluster_key]["control"],
               cluster_table[cluster_key]["pure_adhd"], cluster_table[cluster_key]["pure_control"],
               cluster_table[cluster_key]["suspected"]))

    subtype_stats = []
    for row_label, flag in ((GROUP_LABEL_CONTROL, False), (GROUP_LABEL_ADHD, True)):
        sub = real_df[real_df["is_adhd"] == flag]
        n = len(sub)
        mean_pc = float(sub["percent_commissions"].dropna().mean()) if sub["percent_commissions"].notna().any() else None
        mean_acc = float(sub["accuracy_pct"].dropna().mean()) if sub["accuracy_pct"].notna().any() else None
        subtype_stats.append((row_label, n, mean_pc, mean_acc))
        if not flag:
            continue
        for cluster_key in ("super_d1_flow", "noise_resonance"):
            csub = real_df[(real_df["nearest_cluster"] == cluster_key) & (real_df["is_adhd"])]
            n2 = len(csub)
            mean_pc2 = float(csub["percent_commissions"].dropna().mean()) if csub["percent_commissions"].notna().any() else None
            mean_acc2 = float(csub["accuracy_pct"].dropna().mean()) if csub["accuracy_pct"].notna().any() else None
            subtype_stats.append(("  -> %s" % SUBTYPE_LABELS.get(cluster_key, cluster_key), n2, mean_pc2, mean_acc2))

    fatigue_bar_groups = compute_fatigue_bar_groups(real_df, fatigue_cols)

    mannwhitney_results, bonferroni_alpha = run_mannwhitney_by_cluster(
        real_df, cluster_names, metric_col=PERMUTATION_TARGET_METRIC)

    confounder_summary = build_confounder_summary(real_df, confound_cols_present)

    target_result = mannwhitney_results.get(PERMUTATION_TARGET_CLUSTER, {})
    real_p_value = target_result.get("p_value")
    if real_p_value is None:
        real_p_value = PERMUTATION_REAL_P_VALUE
        log("Warning: could not compute a real analytical p-value for cluster '%s' -- "
            "falling back to PERMUTATION_REAL_P_VALUE=%.2f for the permutation test threshold."
            % (PERMUTATION_TARGET_CLUSTER, PERMUTATION_REAL_P_VALUE))

    permutation_result = run_permutation_test(
        real_df, real_vecs_z, centroids_z, cluster_names,
        target_cluster=PERMUTATION_TARGET_CLUSTER, metric_col=PERMUTATION_TARGET_METRIC,
        real_p_value=real_p_value, n_permutations=N_PERMUTATIONS,
    )

    mixedlm_result = run_mixedlm_within_adhd_test(long_df, real_df)
    if not mixedlm_result.get("available"):
        log("MixedLM тест внутри ADHD пропущен: %s" % mixedlm_result.get("reason"))
    else:
        log("MixedLM interaction (block x cluster, Sprint vs Crash, within %s): coef=%.5f, se=%.5f, z=%.5f, p=%.5f"
            % (COHORT_PURE_ADHD, mixedlm_result["coefficient"],
               mixedlm_result["std_err"], mixedlm_result["z_value"], mixedlm_result["p_value"]))

    writable_dir = get_output_dir()
    written_paths = {}

    report_path = os.path.join(writable_dir, CLEAN_REPORT_NAME)
    try:
        write_clean_report(report_path, found_columns, real_df, cluster_table, subtype_stats,
                            fatigue_bar_groups, mannwhitney_results, bonferroni_alpha,
                            permutation_result, confounder_summary, calibration_stats,
                            mixedlm_result)
        written_paths["report_path"] = report_path
    except Exception as e:
        log("Warning: failed to write the report (%s) -- skipping it, continuing with the rest "
            "of the run: %s" % (report_path, e))

    accuracy_plot_path = os.path.join(writable_dir, ACCURACY_PLOT_NAME)
    try:
        build_scatter_plot(
            real_df, hypotheses, color_col="accuracy_pct", cmap="RdYlGn",
            title="BALLADEER: True Accuracy of Test Performance by Subtype",
            cbar_label="Accuracy %", output_name=accuracy_plot_path, hue_norm=(0, 100),
        )
        written_paths["accuracy_plot_path"] = accuracy_plot_path
    except Exception as e:
        log("Warning: failed to build the accuracy plot (%s) -- skipping it, continuing with the "
            "rest of the run: %s" % (accuracy_plot_path, e))

    impulsivity_plot_path = os.path.join(writable_dir, IMPULSIVITY_PLOT_NAME)
    try:
        max_pc = real_df["percent_commissions"].dropna().max() if real_df["percent_commissions"].notna().any() else 100
        build_scatter_plot(
            real_df, hypotheses, color_col="percent_commissions", cmap="RdYlGn_r",
            title="BALLADEER: Impulsivity (Percent Commissions) by Subtype",
            cbar_label="Percent Commissions", output_name=impulsivity_plot_path, hue_norm=(0, max(max_pc, 1)),
        )
        written_paths["impulsivity_plot_path"] = impulsivity_plot_path
    except Exception as e:
        log("Warning: failed to build the impulsivity plot (%s) -- skipping it, continuing with "
            "the rest of the run: %s" % (impulsivity_plot_path, e))

    fatigue_plot_path = os.path.join(writable_dir, FATIGUE_DYNAMICS_PLOT_NAME)
    try:
        build_fatigue_dynamics_plot(fatigue_bar_groups, fatigue_plot_path)
        written_paths["fatigue_plot_path"] = fatigue_plot_path
    except Exception as e:
        log("Warning: failed to build the fatigue dynamics plot (%s) -- skipping it, continuing "
            "with the rest of the run: %s" % (fatigue_plot_path, e))

    log("Validation complete. %d/4 output artifact(s) written to: %s (%s)"
        % (len(written_paths), writable_dir, ", ".join(sorted(written_paths.keys())) or "none"))
    return {
        "report_path": report_path if "report_path" in written_paths else None,
        "accuracy_plot_path": accuracy_plot_path if "accuracy_plot_path" in written_paths else None,
        "impulsivity_plot_path": impulsivity_plot_path if "impulsivity_plot_path" in written_paths else None,
        "fatigue_plot_path": fatigue_plot_path if "fatigue_plot_path" in written_paths else None,
        "real_df": real_df,
        "long_df": long_df,
    }

def main():
    try:
        run_validation()
    except Exception:
        writable_dir = get_output_dir()
        crash_log_path = os.path.join(writable_dir, CRASH_LOG_NAME)
        try:
            with open(crash_log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(LOG_BUFFER))
                f.write("\n\n" + "=" * 70 + "\nTRACEBACK\n" + "=" * 70 + "\n")
                f.write(traceback.format_exc())
            print("An error occurred. A crash log was written to: %s" % crash_log_path)
        except Exception as inner_e:
            print("An error occurred, and the crash log could not be written: %s" % inner_e)
        traceback.print_exc()

if __name__ == "__main__":
    main()
