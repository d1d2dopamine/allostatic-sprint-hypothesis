# -*- coding: utf-8 -*-
"""
HEALTHY_VALID_BALLADEER.py -- BALLADEER validator, release v1.0.1.

Methodological correction relative to v1.0.0:
  * primary analysis is cluster-free (Pure ADHD vs Pure Control);
  * accuracy and commission errors never define groups or latent components;
  * dimensional analyses use work-speed mean and work-speed variability only;
  * an ADHD-only 2-component GMM is strictly secondary and receives no
    Sprint/Crash labels; it is accepted only if all prespecified stability
    gates pass;
  * commission errors remain a held-out outcome for dimensional/GMM analyses.

Input files:
  users_demographics.json, balladeer_embraceplus_data.csv, and
  <UserID>_GAME_DATA_<SessionDate>.csv files from BALLADEER.

Install:
  pip install pandas numpy scipy matplotlib seaborn openpyxl scikit-learn statsmodels

Run:
  python HEALTHY_VALID_BALLADEER.py

The script never downloads data. It searches local folders and writes a new
HEALTHY_VALID_BALLADEER_output directory. Dopamine/ATP language is theoretical
framing and is not directly measured by BALLADEER.

Author: D1D2DOPAMINE
Version: 1.0.1
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

CLEAN_REPORT_NAME = "balladeer_cluster_free_report.txt"
GROUP_PLOT_NAME = "balladeer_cluster_free_commissions.png"
DIMENSIONAL_PLOT_NAME = "balladeer_dimensional_spectrum.png"
TEMPORAL_PLOT_NAME = "balladeer_temporal_dynamics_dimensional.png"
CRASH_LOG_NAME = "balladeer_crash_log.txt"
OUTPUT_FOLDER_NAME = "HEALTHY_VALID_BALLADEER_output"

GROUP_LABEL_ADHD = "Experimental (ADHD)"
GROUP_LABEL_CONTROL = "Control"

COHORT_PURE_CONTROL = "Pure Control"
COHORT_PURE_ADHD = "Pure ADHD"
COHORT_SUSPECTED = "Suspected ADHD"
COHORT_ORDER = [COHORT_PURE_CONTROL, COHORT_PURE_ADHD, COHORT_SUSPECTED]

# v1.0.1 intentionally defines no Sprint/Crash subtype labels.
# The active pipeline uses clean diagnostic cohorts and independent behavioral dimensions.

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

    core_cols = ["id", "is_adhd", "cohort", "work_speed_mean", "work_speed_std", "accuracy_pct", "percent_commissions", "percent_omissions"]
    biometric_cols = [c for c in ("eda_change", "prv_change") if c in merged.columns]
    keep_cols = core_cols + biometric_cols + confound_cols_present
    result = merged[keep_cols].dropna(subset=["work_speed_mean", "work_speed_std", "percent_commissions"]).reset_index(drop=True)

    if len(result) == 0:
        raise RuntimeError(
            "After merging and dropping rows with missing work_speed_mean/work_speed_std/"
            "percent_commissions, 0 participants remained -- check that the GAME_DATA files actually "
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


SCRIPT_VERSION = "1.0.1"
RANDOM_SEED = 20260716
N_PERMUTATIONS = 5000
N_BOOTSTRAPS = 2000
GMM_BOOTSTRAPS = 300
GMM_BIC_IMPROVEMENT_MIN = 10.0
GMM_SILHOUETTE_MIN = 0.25
GMM_MIN_CLUSTER_SHARE = 0.15
GMM_BOOTSTRAP_ARI_MIN = 0.60

PARTICIPANT_CSV_NAME = "balladeer_participant_metrics.csv"
GMM_CSV_NAME = "balladeer_gmm_diagnostics.csv"
CONFIG_JSON_NAME = "balladeer_analysis_config.json"
LOG_NAME = "balladeer_reproducibility_log.txt"


def _finite(values):
    return pd.to_numeric(pd.Series(values), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().to_numpy(float)


def _rank_biserial_from_u(u_stat, n_adhd, n_control):
    return 2.0 * float(u_stat) / float(n_adhd * n_control) - 1.0


def _permutation_median_difference(x, y, rng, n_permutations=N_PERMUTATIONS):
    x, y = _finite(x), _finite(y)
    if len(x) < 2 or len(y) < 2:
        return {"observed": None, "p_value": None, "n": 0}
    observed = float(np.median(x) - np.median(y))
    pooled = np.concatenate([x, y])
    exceed = 0
    for _ in range(n_permutations):
        perm = rng.permutation(pooled)
        stat = float(np.median(perm[:len(x)]) - np.median(perm[len(x):]))
        exceed += abs(stat) >= abs(observed) - 1e-15
    return {"observed": observed, "p_value": (exceed + 1.0) / (n_permutations + 1.0), "n": n_permutations}


def _bootstrap_median_difference(x, y, rng, n_bootstraps=N_BOOTSTRAPS):
    x, y = _finite(x), _finite(y)
    if len(x) < 2 or len(y) < 2:
        return (None, None)
    vals = np.empty(n_bootstraps, float)
    for i in range(n_bootstraps):
        vals[i] = np.median(rng.choice(x, len(x), replace=True)) - np.median(rng.choice(y, len(y), replace=True))
    return tuple(float(v) for v in np.percentile(vals, [2.5, 97.5]))


def cluster_free_group_tests(real_df):
    metrics = [
        ("percent_commissions", "Commission rate (%)"),
        ("percent_omissions", "Omission rate (%)"),
        ("accuracy_pct", "Accuracy (%)"),
        ("work_speed_mean", "Work-speed mean"),
        ("work_speed_std", "Work-speed variability"),
    ]
    adhd = real_df[real_df["cohort"] == COHORT_PURE_ADHD]
    control = real_df[real_df["cohort"] == COHORT_PURE_CONTROL]
    rng = np.random.default_rng(RANDOM_SEED)
    results = []
    for metric, label in metrics:
        x, y = _finite(adhd[metric]), _finite(control[metric])
        row = {"metric": metric, "label": label, "n_adhd": len(x), "n_control": len(y),
               "median_adhd": float(np.median(x)) if len(x) else None,
               "median_control": float(np.median(y)) if len(y) else None}
        if len(x) >= 2 and len(y) >= 2:
            u, p = scipy_stats.mannwhitneyu(x, y, alternative="two-sided")
            row.update({"u": float(u), "p_mwu": float(p),
                        "rank_biserial": _rank_biserial_from_u(u, len(x), len(y))})
            perm = _permutation_median_difference(x, y, rng)
            row["median_difference"] = perm["observed"]
            row["p_permutation"] = perm["p_value"]
            row["bootstrap_ci"] = _bootstrap_median_difference(x, y, rng)
            bf = scipy_stats.levene(x, y, center="median")
            row["brown_forsythe_p"] = float(bf.pvalue)
        else:
            row.update({"u": None, "p_mwu": None, "rank_biserial": None,
                        "median_difference": None, "p_permutation": None,
                        "bootstrap_ci": (None, None), "brown_forsythe_p": None})
        results.append(row)
    # Holm correction across secondary outcomes only; commission is the sole primary outcome.
    secondary = [(i, r["p_mwu"]) for i, r in enumerate(results[1:], start=1) if r["p_mwu"] is not None]
    ordered = sorted(secondary, key=lambda z: z[1])
    running = 0.0
    for rank, (idx, pval) in enumerate(ordered):
        adjusted = min(1.0, (len(ordered) - rank) * pval)
        running = max(running, adjusted)
        results[idx]["holm_p"] = running
    results[0]["holm_p"] = None
    return results


def add_independent_dimensions(real_df):
    out = real_df.copy()
    features = out[["work_speed_mean", "work_speed_std"]].to_numpy(float)
    means = np.nanmean(features, axis=0)
    sds = np.nanstd(features, axis=0, ddof=0)
    sds[sds == 0] = 1.0
    z = (features - means) / sds
    out["z_work_speed_mean"] = z[:, 0]
    out["z_work_speed_variability"] = z[:, 1]
    covariance = np.cov(z, rowvar=False)
    vals, vecs = np.linalg.eigh(covariance)
    loading = vecs[:, np.argmax(vals)]
    axis = z @ loading
    if np.corrcoef(axis, z[:, 0])[0, 1] < 0:
        loading = -loading
        axis = -axis
    out["behavioral_axis_pc1"] = axis
    explained = float(np.max(vals) / np.sum(vals)) if np.sum(vals) > 0 else None
    return out, {"means": means.tolist(), "sds": sds.tolist(), "pc1_loading": loading.tolist(),
                 "pc1_explained_variance": explained}


def dimensional_associations(real_df):
    adhd = real_df[real_df["cohort"] == COHORT_PURE_ADHD]
    predictors = ["z_work_speed_mean", "z_work_speed_variability", "behavioral_axis_pc1"]
    outcomes = ["percent_commissions", "percent_omissions", "accuracy_pct"]
    rows = []
    for pred in predictors:
        for outcome in outcomes:
            pair = adhd[[pred, outcome]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(pair) >= 5 and pair[pred].nunique() > 1 and pair[outcome].nunique() > 1:
                rho, p = scipy_stats.spearmanr(pair[pred], pair[outcome])
                rows.append({"predictor": pred, "outcome": outcome, "n": len(pair),
                             "rho": float(rho), "p_value": float(p)})
            else:
                rows.append({"predictor": pred, "outcome": outcome, "n": len(pair),
                             "rho": None, "p_value": None})
    return rows


def robust_covariate_model(real_df):
    clean = real_df[real_df["cohort"].isin([COHORT_PURE_ADHD, COHORT_PURE_CONTROL])].copy()
    required = ["percent_commissions", "work_speed_mean", "work_speed_std"]
    clean = clean.dropna(subset=required)
    if len(clean) < 20:
        return {"available": False, "reason": "fewer than 20 complete clean-cohort participants"}
    try:
        import statsmodels.api as sm
    except Exception as exc:
        return {"available": False, "reason": "statsmodels unavailable: %s" % exc}
    clean["adhd_indicator"] = (clean["cohort"] == COHORT_PURE_ADHD).astype(float)
    for col in ("work_speed_mean", "work_speed_std"):
        sd = clean[col].std(ddof=0)
        clean["z_" + col] = (clean[col] - clean[col].mean()) / (sd if sd else 1.0)
    x = pd.DataFrame({
        "adhd": clean["adhd_indicator"],
        "z_speed": clean["z_work_speed_mean"],
        "z_variability": clean["z_work_speed_std"],
    }, index=clean.index)
    x["adhd_x_speed"] = x["adhd"] * x["z_speed"]
    x["adhd_x_variability"] = x["adhd"] * x["z_variability"]
    if "age" in clean.columns:
        age = pd.to_numeric(clean["age"], errors="coerce")
        if age.notna().sum() >= int(0.7 * len(clean)):
            x["age"] = age.fillna(age.median())
    if "sex" in clean.columns:
        sex = clean["sex"].astype(str).replace("nan", "Unknown")
        dummies = pd.get_dummies(sex, prefix="sex", drop_first=True, dtype=float)
        x = pd.concat([x, dummies], axis=1)
    x = sm.add_constant(x.astype(float), has_constant="add")
    y = clean["percent_commissions"].astype(float)
    try:
        fit = sm.OLS(y, x).fit(cov_type="HC3")
    except Exception as exc:
        return {"available": False, "reason": "OLS failed: %s" % exc}
    terms = {}
    for term in ["adhd", "z_speed", "z_variability", "adhd_x_speed", "adhd_x_variability"]:
        if term in fit.params:
            ci = fit.conf_int().loc[term]
            terms[term] = {"coef": float(fit.params[term]), "p": float(fit.pvalues[term]),
                           "ci_low": float(ci.iloc[0]), "ci_high": float(ci.iloc[1])}
    return {"available": True, "n": int(len(clean)), "r_squared": float(fit.rsquared),
            "terms": terms, "columns": list(x.columns)}


def gmm_diagnostics(real_df):
    adhd = real_df[real_df["cohort"] == COHORT_PURE_ADHD].copy()
    x = adhd[["z_work_speed_mean", "z_work_speed_variability"]].to_numpy(float)
    result = {"available": False, "stable_two_component": False, "rows": [], "labels": None}
    if len(x) < 15:
        result["reason"] = "fewer than 15 Pure ADHD participants"
        return result
    try:
        from sklearn.mixture import GaussianMixture
        from sklearn.metrics import adjusted_rand_score, silhouette_score
    except Exception as exc:
        result["reason"] = "scikit-learn unavailable: %s" % exc
        return result
    models = {}
    for k in (1, 2, 3):
        model = GaussianMixture(n_components=k, covariance_type="full", n_init=20,
                                random_state=RANDOM_SEED, reg_covar=1e-6).fit(x)
        models[k] = model
        result["rows"].append({"k": k, "bic": float(model.bic(x)), "aic": float(model.aic(x))})
    labels = models[2].predict(x)
    counts = np.bincount(labels, minlength=2)
    min_share = float(counts.min() / len(labels))
    silhouette = float(silhouette_score(x, labels)) if len(np.unique(labels)) == 2 else None
    bic = {r["k"]: r["bic"] for r in result["rows"]}
    improvement = float(bic[1] - bic[2])
    k2_best = bic[2] == min(bic.values())
    rng = np.random.default_rng(RANDOM_SEED)
    aris = []
    for b in range(GMM_BOOTSTRAPS):
        idx = rng.integers(0, len(x), len(x))
        try:
            boot = GaussianMixture(n_components=2, covariance_type="full", n_init=5,
                                   random_state=RANDOM_SEED + b + 1, reg_covar=1e-6).fit(x[idx])
            aris.append(float(adjusted_rand_score(labels, boot.predict(x))))
        except Exception:
            continue
    median_ari = float(np.median(aris)) if aris else None
    gates = {
        "bic_improvement": improvement >= GMM_BIC_IMPROVEMENT_MIN,
        "k2_best_bic": bool(k2_best),
        "silhouette": silhouette is not None and silhouette >= GMM_SILHOUETTE_MIN,
        "minimum_share": min_share >= GMM_MIN_CLUSTER_SHARE,
        "bootstrap_ari": median_ari is not None and median_ari >= GMM_BOOTSTRAP_ARI_MIN,
    }
    result.update({"available": True, "labels": labels, "participant_index": adhd.index.tolist(),
                   "bic_improvement": improvement, "silhouette": silhouette,
                   "minimum_share": min_share, "bootstrap_median_ari": median_ari,
                   "gates": gates, "stable_two_component": all(gates.values())})
    return result


def temporal_dimension_test(long_df, real_df):
    lookup = real_df.set_index("id")[["cohort", "behavioral_axis_pc1"]]
    long = long_df.merge(lookup, left_on="id", right_index=True, how="inner")
    long = long[long["cohort"] == COHORT_PURE_ADHD].dropna(subset=["block", "percent_commissions", "behavioral_axis_pc1"])
    slopes = []
    for pid, sub in long.groupby("id"):
        collapsed = sub.groupby("block", as_index=False)["percent_commissions"].mean()
        if len(collapsed) >= 3 and collapsed["block"].nunique() >= 3:
            slope = np.polyfit(collapsed["block"].to_numpy(float), collapsed["percent_commissions"].to_numpy(float), 1)[0]
            slopes.append({"id": pid, "commission_slope_per_block": float(slope),
                           "behavioral_axis_pc1": float(sub["behavioral_axis_pc1"].iloc[0])})
    slope_df = pd.DataFrame(slopes)
    if len(slope_df) < 5:
        return {"available": False, "reason": "fewer than 5 ADHD participants with >=3 blocks", "slopes": slope_df}
    rho, p = scipy_stats.spearmanr(slope_df["behavioral_axis_pc1"], slope_df["commission_slope_per_block"])
    return {"available": True, "n": len(slope_df), "rho": float(rho), "p_value": float(p), "slopes": slope_df}


def biometric_dimension_tests(real_df, fatigue_cols):
    rows = []
    adhd = real_df[real_df["cohort"] == COHORT_PURE_ADHD]
    for metric in [fatigue_cols.get("eda_change_col"), fatigue_cols.get("prv_change_col")]:
        if not metric or metric not in adhd.columns:
            continue
        pair = adhd[["behavioral_axis_pc1", metric]].dropna()
        if len(pair) >= 5 and pair[metric].nunique() > 1:
            rho, p = scipy_stats.spearmanr(pair["behavioral_axis_pc1"], pair[metric])
            rows.append({"metric": metric, "n": len(pair), "rho": float(rho), "p_value": float(p)})
        else:
            rows.append({"metric": metric, "n": len(pair), "rho": None, "p_value": None})
    return rows


def build_group_plot(real_df, output_path):
    clean = real_df[real_df["cohort"].isin([COHORT_PURE_CONTROL, COHORT_PURE_ADHD])]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    order = [COHORT_PURE_CONTROL, COHORT_PURE_ADHD]
    sns.violinplot(data=clean, x="cohort", y="percent_commissions", order=order, inner=None,
                   color="#9ecae1", cut=0, ax=axes[0])
    sns.stripplot(data=clean, x="cohort", y="percent_commissions", order=order,
                  color="black", alpha=.65, jitter=.16, size=4, ax=axes[0])
    axes[0].set_title("Cluster-free primary outcome")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Commission rate (%)")
    sns.scatterplot(data=clean, x="work_speed_mean", y="percent_commissions", hue="cohort",
                    style="cohort", s=65, ax=axes[1])
    axes[1].set_title("Commission errors vs work speed")
    axes[1].set_xlabel("Work-speed mean")
    axes[1].set_ylabel("Commission rate (%)")
    fig.suptitle("BALLADEER v1.0.1: no outcome-defined subtypes")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_dimensional_plot(real_df, gmm, output_path):
    adhd = real_df[real_df["cohort"] == COHORT_PURE_ADHD].copy()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    sc = axes[0].scatter(adhd["z_work_speed_mean"], adhd["z_work_speed_variability"],
                         c=adhd["percent_commissions"], cmap="viridis", s=75, edgecolor="black", linewidth=.4)
    axes[0].set_xlabel("Standardized work-speed mean")
    axes[0].set_ylabel("Standardized speed variability")
    axes[0].set_title("Held-out commission outcome")
    fig.colorbar(sc, ax=axes[0], label="Commission rate (%)")
    sns.regplot(data=adhd, x="behavioral_axis_pc1", y="percent_commissions", lowess=True,
                scatter_kws={"s": 45, "alpha": .75}, line_kws={"color": "crimson"}, ax=axes[1])
    axes[1].set_xlabel("Independent speed/variability axis (PC1)")
    axes[1].set_ylabel("Commission rate (%)")
    status = "stable" if gmm.get("stable_two_component") else "not accepted"
    axes[1].set_title("Dimensional association; GMM: %s" % status)
    fig.suptitle("BALLADEER ADHD-only dimensional analysis")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_temporal_plot(temporal, output_path):
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    if not temporal.get("available"):
        ax.text(.5, .5, "Temporal analysis unavailable:\n%s" % temporal.get("reason", "unknown"), ha="center", va="center")
        ax.set_axis_off()
    else:
        slopes = temporal["slopes"]
        sns.regplot(data=slopes, x="behavioral_axis_pc1", y="commission_slope_per_block",
                    scatter_kws={"s": 55, "alpha": .75}, line_kws={"color": "crimson"}, ax=ax)
        ax.axhline(0, color="black", lw=.8, ls="--")
        ax.set_title("ADHD-only temporal dynamics: rho=%.3f, p=%.4f" % (temporal["rho"], temporal["p_value"]))
        ax.set_xlabel("Independent speed/variability axis (PC1)")
        ax.set_ylabel("Commission-rate slope per block")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_report(path, found_columns, real_df, group_results, dimensions, dimensional_rows,
                 covariate_model, gmm, temporal, biometric_rows):
    lines = ["=" * 78, "BALLADEER v1.0.1 -- CLUSTER-FREE ACADEMIC DIAGNOSTIC", "=" * 78, ""]
    lines += ["0. METHOD CORRECTION", "-" * 78,
              "Primary inference compares Pure ADHD with Pure Control without clustering.",
              "Accuracy, omissions and commission errors never define groups/components.",
              "Speed and speed variability define exploratory dimensions; commission errors are held out.",
              "No Sprint/Crash labels are assigned by this validator.", ""]
    lines += ["1. DATA", "-" * 78]
    for key, value in found_columns.items(): lines.append("%s: %s" % (key, value))
    lines.append("")
    lines += ["2. PRIMARY CLUSTER-FREE TEST", "-" * 78,
              "Primary outcome: commission rate. Mann-Whitney and two-sided label permutation are reported.",
              "Secondary outcomes receive Holm correction as one family.", ""]
    for r in group_results:
        ci = r["bootstrap_ci"]
        lines.append("%s: n_ADHD=%d, n_control=%d; medians=%.4f vs %.4f" % (
            r["label"], r["n_adhd"], r["n_control"], r["median_adhd"], r["median_control"]))
        if r["p_mwu"] is not None:
            lines.append("  U=%.3f, p_MWU=%.6f, rank-biserial=%.4f" % (r["u"], r["p_mwu"], r["rank_biserial"]))
            lines.append("  median difference=%.4f, 95%% bootstrap CI=[%.4f, %.4f], permutation p=%.6f" % (
                r["median_difference"], ci[0], ci[1], r["p_permutation"]))
            lines.append("  Brown-Forsythe variance p=%.6f%s" % (r["brown_forsythe_p"],
                (", Holm p=%.6f" % r["holm_p"]) if r.get("holm_p") is not None else ""))
    lines.append("")
    lines += ["3. ROBUST COVARIATE MODEL", "-" * 78,
              "Outcome: commission rate; HC3 OLS; terms include diagnosis, independent speed/variability,",
              "diagnosis interactions, and available age/sex covariates."]
    if covariate_model.get("available"):
        lines.append("n=%d, R-squared=%.4f" % (covariate_model["n"], covariate_model["r_squared"]))
        for term, r in covariate_model["terms"].items():
            lines.append("  %s: b=%.5f, 95%% CI=[%.5f, %.5f], p=%.6f" % (term, r["coef"], r["ci_low"], r["ci_high"], r["p"]))
    else: lines.append("Unavailable: %s" % covariate_model.get("reason"))
    lines.append("")
    lines += ["4. ADHD-ONLY DIMENSIONAL ANALYSIS", "-" * 78,
              "PC1 loading [speed mean, speed variability]=%s; explained variance=%s" % (
                  [round(v, 5) for v in dimensions["pc1_loading"]],
                  "%.4f" % dimensions["pc1_explained_variance"] if dimensions["pc1_explained_variance"] is not None else "N/A")]
    for r in dimensional_rows:
        lines.append("  %s -> %s: n=%d, rho=%s, p=%s" % (r["predictor"], r["outcome"], r["n"],
            "%.4f" % r["rho"] if r["rho"] is not None else "N/A",
            "%.6f" % r["p_value"] if r["p_value"] is not None else "N/A"))
    lines.append("")
    lines += ["5. SECONDARY ADHD-ONLY GMM", "-" * 78]
    if not gmm.get("available"):
        lines.append("Unavailable: %s" % gmm.get("reason"))
    else:
        for r in gmm["rows"]: lines.append("  K=%d: BIC=%.4f, AIC=%.4f" % (r["k"], r["bic"], r["aic"]))
        lines.append("  BIC improvement K1-K2=%.4f; silhouette=%.4f; minimum share=%.4f; median bootstrap ARI=%s" % (
            gmm["bic_improvement"], gmm["silhouette"], gmm["minimum_share"],
            "%.4f" % gmm["bootstrap_median_ari"] if gmm["bootstrap_median_ari"] is not None else "N/A"))
        for gate, passed in gmm["gates"].items(): lines.append("  Gate %-22s %s" % (gate, "PASS" if passed else "FAIL"))
        lines.append("  stable_two_component=%s" % gmm["stable_two_component"])
        lines.append("  Components are numeric exploratory components only; no subtype names are assigned.")
    lines.append("")
    lines += ["6. TEMPORAL AND BIOMETRIC DIMENSIONAL CHECKS", "-" * 78]
    if temporal.get("available"):
        lines.append("ADHD axis vs commission slope: n=%d, rho=%.4f, p=%.6f" % (temporal["n"], temporal["rho"], temporal["p_value"]))
    else: lines.append("Temporal test unavailable: %s" % temporal.get("reason"))
    for r in biometric_rows:
        lines.append("ADHD axis vs %s: n=%d, rho=%s, p=%s" % (r["metric"], r["n"],
            "%.4f" % r["rho"] if r["rho"] is not None else "N/A",
            "%.6f" % r["p_value"] if r["p_value"] is not None else "N/A"))
    lines += ["", "7. INTERPRETATION BOUNDARY", "-" * 78,
              "This observational behavioral dataset cannot test dopamine receptor states, ATP depletion,",
              "or a biological allostatic mechanism. Positive associations are behavioral support only.",
              "Null results constrain the hypothesis and must not be converted into forced subtype labels.", "=" * 78]
    with open(path, "w", encoding="utf-8") as f: f.write("\n".join(lines))


def run_validation():
    np.random.seed(RANDOM_SEED)
    found_columns = {}
    real_df, fatigue_cols, confound_cols_present, long_df = load_balladeer_participants(found_columns)
    real_df, dimensions = add_independent_dimensions(real_df)
    group_results = cluster_free_group_tests(real_df)
    dimensional_rows = dimensional_associations(real_df)
    covariate_model = robust_covariate_model(real_df)
    gmm = gmm_diagnostics(real_df)
    real_df["exploratory_gmm_component"] = np.nan
    if gmm.get("available") and gmm.get("labels") is not None:
        real_df.loc[gmm["participant_index"], "exploratory_gmm_component"] = gmm["labels"]
    real_df["gmm_two_component_accepted"] = bool(gmm.get("stable_two_component"))
    temporal = temporal_dimension_test(long_df, real_df)
    biometric_rows = biometric_dimension_tests(real_df, fatigue_cols)
    out = get_output_dir()
    paths = {
        "report": os.path.join(out, CLEAN_REPORT_NAME),
        "participants": os.path.join(out, PARTICIPANT_CSV_NAME),
        "gmm": os.path.join(out, GMM_CSV_NAME),
        "group_plot": os.path.join(out, GROUP_PLOT_NAME),
        "dimensional_plot": os.path.join(out, DIMENSIONAL_PLOT_NAME),
        "temporal_plot": os.path.join(out, TEMPORAL_PLOT_NAME),
        "config": os.path.join(out, CONFIG_JSON_NAME),
        "log": os.path.join(out, LOG_NAME),
    }
    write_report(paths["report"], found_columns, real_df, group_results, dimensions,
                 dimensional_rows, covariate_model, gmm, temporal, biometric_rows)
    real_df.to_csv(paths["participants"], index=False)
    pd.DataFrame(gmm.get("rows", [])).to_csv(paths["gmm"], index=False)
    build_group_plot(real_df, paths["group_plot"])
    build_dimensional_plot(real_df, gmm, paths["dimensional_plot"])
    build_temporal_plot(temporal, paths["temporal_plot"])
    config = {
        "script_version": SCRIPT_VERSION, "seed": RANDOM_SEED,
        "n_permutations": N_PERMUTATIONS, "n_bootstraps": N_BOOTSTRAPS,
        "gmm_bootstraps": GMM_BOOTSTRAPS,
        "gmm_gates": {"bic_improvement_min": GMM_BIC_IMPROVEMENT_MIN,
                      "silhouette_min": GMM_SILHOUETTE_MIN,
                      "minimum_cluster_share": GMM_MIN_CLUSTER_SHARE,
                      "bootstrap_median_ari_min": GMM_BOOTSTRAP_ARI_MIN},
        "primary_outcome": "percent_commissions",
        "component_features": ["work_speed_mean", "work_speed_std"],
        "outcome_features_excluded_from_components": ["percent_commissions", "percent_omissions", "accuracy_pct"],
        "dimensions": dimensions,
    }
    with open(paths["config"], "w", encoding="utf-8") as f: json.dump(config, f, indent=2)
    log("BALLADEER v%s validation complete." % SCRIPT_VERSION)
    log("GMM two-component solution accepted: %s" % bool(gmm.get("stable_two_component")))
    for name, path in paths.items(): log("Output %-18s %s" % (name + ":", path))
    with open(paths["log"], "w", encoding="utf-8") as f: f.write("\n".join(LOG_BUFFER) + "\n")
    return {"paths": paths, "real_df": real_df, "group_results": group_results,
            "gmm": gmm, "temporal": temporal}


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
            print("An error occurred. Crash log: %s" % crash_log_path)
        except Exception as inner_e:
            print("An error occurred, and the crash log could not be written: %s" % inner_e)
        traceback.print_exc()


if __name__ == "__main__":
    main()
