# -*- coding: utf-8 -*-
"""
CLINICAL_VALID_HYPERAKTIV.py -- HYPERAKTIV dataset validator for the
"Allostatic Sprint" hypothesis (ADHD behavioral subtypes).

WHAT IT DOES
    Validates real clinical CPT-II data from the open HYPERAKTIV dataset
    (OSF) against the "Sustainable Flow", "Noise Resonance", and
    "Super D1 Flow" (subtype) hypotheses. Hypothesis anchor coordinates are
    embedded directly in this file.

HOW TO RUN
    1. pip install pandas numpy scipy matplotlib seaborn
    2. Place the two public HYPERAKTIV CSV files (patient_info.csv and
       CPT_II_ConnersContinuousPerformanceTest.csv) in your Downloads
       folder -- or just run the script, which will download them
       automatically from OSF if they are not found locally.
    3. python3 CLINICAL_VALID_HYPERAKTIV.py

OUTPUT
    Written to your Downloads folder:
    hyperaktiv_academic_diagnostic.txt, hyperaktiv_accuracy_validation.png,
    hyperaktiv_impulsivity_validation.png, hyperaktiv_fatigue_dynamics.png,
    (crash_log.txt only if something goes wrong)

NOTE: the "dopamine D1/D2" and "ATP depletion" language in this project is a
theoretical/narrative framing, not something directly measured in the data.

Author: D1D2DOPAMINE
"""

import json
import os
import platform
import re
import traceback
import urllib.request

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

PATIENT_INFO_URL = "https://osf.io/download/hypj6/"
CPT_II_URL = "https://osf.io/download/2gt3w/"
CSV_SEP = ";"

CLEAN_REPORT_NAME = "hyperaktiv_academic_diagnostic.txt"
ACCURACY_PLOT_NAME = "hyperaktiv_accuracy_validation.png"
IMPULSIVITY_PLOT_NAME = "hyperaktiv_impulsivity_validation.png"
FATIGUE_DYNAMICS_PLOT_NAME = "hyperaktiv_fatigue_dynamics.png"
CRASH_LOG_NAME = "crash_log.txt"

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
    "entropy_paradox": "Atypical Behavioral Noise (Sample Outliers)",
}

NOISE_CLUSTER_KEY = "entropy_paradox"
BONFERRONI_BASE_ALPHA = 0.05

EXCLUSION_MODE = "none"

CLINICAL_CUTOFF_RT_MEAN = 150.0
TECHNICAL_INVALID_LABEL = "Technical Invalid / Perseverative"

COLUMN_OVERRIDES = {
    "id": None, "group": None, "rt_mean": None, "rt_std": None,
    "omissions": None, "commissions": None, "accuracy": None,
    "age": None, "sex": None, "medication": None,
}

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

def get_search_dirs():
    dirs = [
        get_platform_downloads_dir(),
        "/storage/emulated/0/Download",
        "/storage/emulated/0/Downloads",
        "/sdcard/Download",
        os.path.expanduser("~/storage/downloads"),
        get_script_dir(),
        ".",
    ]
    seen, result = set(), []
    for d in dirs:
        if d and os.path.isdir(d) and d not in seen:
            seen.add(d)
            result.append(d)
    return result

def find_file(filenames):
    if isinstance(filenames, str):
        filenames = [filenames]
    for d in get_search_dirs():
        for filename in filenames:
            path = os.path.join(d, filename)
            if os.path.isfile(path):
                return path
    return None

def get_writable_dir():
    primary = get_platform_downloads_dir()
    candidates = [
        primary,
        "/storage/emulated/0/Download",
        "/storage/emulated/0/Downloads",
        "/sdcard/Download",
        os.path.expanduser("~/storage/downloads"),
        get_script_dir(),
        ".",
    ]
    for d in candidates:
        try:
            if d and os.path.isdir(d) and os.access(d, os.W_OK):
                return d
        except Exception:
            continue
    log("Note: no writable Downloads directory found (tried: %s) -- falling "
        "back to the script's current directory ('.')." % primary)
    return "."

def read_hyperaktiv_csv(path):
    return pd.read_csv(path, sep=CSV_SEP, engine="python")

def download_or_load(url, cache_names, save_name=None):
    if isinstance(cache_names, str):
        cache_names = [cache_names]
    save_name = save_name or cache_names[0]

    cached = find_file(cache_names)
    if cached:
        log("Using previously downloaded file: %s" % cached)
        return read_hyperaktiv_csv(cached)

    dest = os.path.join(get_writable_dir(), save_name)
    log("Downloading: %s" % url)
    log("   -> will be saved to: %s" % dest)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    log("   downloaded %d bytes, saving to disk..." % len(data))
    with open(dest, "wb") as f:
        f.write(data)
    log("   done: %s" % dest)
    return read_hyperaktiv_csv(dest)

def find_col(df, patterns, override_key=None, exclude=None, avoid=None):
    if override_key and COLUMN_OVERRIDES.get(override_key):
        return COLUMN_OVERRIDES[override_key]
    exclude = exclude or set()
    avoid = avoid or []
    cols_lower = {
        c: str(c).lower().replace("_", " ").replace("-", " ")
        for c in df.columns if c not in exclude
    }
    for pattern in patterns:
        for col, low in cols_lower.items():
            if any(a in low for a in avoid):
                continue
            if all(p in low for p in pattern):
                return col
    return None

def find_fatigue_change_columns(cpt_df):
    avoid = ["tscore", "t score", "percent"]
    rt_change_col = find_col(cpt_df, [
        ("raw", "hitrt", "block"), ("hitrt", "block"),
    ], avoid=avoid)
    se_change_col = find_col(cpt_df, [
        ("raw", "hitse", "block"), ("hitse", "block"),
    ], exclude={rt_change_col} if rt_change_col else None, avoid=avoid)
    return rt_change_col, se_change_col

TIME_AUDIT_KEYWORDS = ["hitrt", "hitse", "sd", "standard deviation"]

def audit_time_columns(cpt_df):
    matches = []
    for col in cpt_df.columns:
        low = str(col).lower().replace("_", " ").replace("-", " ")
        if any(k in low for k in TIME_AUDIT_KEYWORDS):
            matches.append(str(col))
    return matches

def load_aggregated_cpt(cpt_df, id_c, found_columns):
    TSCORE_AVOID = ["tscore", "t score", "percent", "block", "isi", "change"]

    rt_mean_col = find_col(cpt_df, [
        ("raw", "hitrt"), ("raw", "hit", "rt"),
        ("hit", "rt", "mean"), ("hit", "reaction", "mean"), ("mean", "rt"),
        ("hitrt",), ("hit", "rt"),
    ], "rt_mean", exclude={id_c},
       avoid=TSCORE_AVOID + ["std", "se", "variability"])

    rt_std_col = find_col(cpt_df, [
        ("raw", "hitse"), ("raw", "hit", "se"),
        ("raw", "hitrt", "sd"), ("raw", "hit", "rt", "sd"),
        ("raw", "hitrt", "std"), ("raw", "hit", "rt", "std"),
        ("hitrt", "sd"), ("hitrt", "std"), ("hitrt", "se"), ("hitse",),
        ("hit", "rt", "std"), ("hit", "rt", "sd"), ("hit", "rt", "se"), ("hit", "se"),
        ("variability",), ("std", "dev"),
    ], "rt_std", exclude={id_c, rt_mean_col} - {None},
       avoid=TSCORE_AVOID)

    percent_omissions_col = find_col(cpt_df, [("percent", "omission"), ("omission", "percent")],
                                      exclude={id_c, rt_mean_col, rt_std_col} - {None})
    percent_commissions_col = find_col(cpt_df, [("percent", "commission"), ("commission", "percent")],
                                        exclude={id_c, rt_mean_col, rt_std_col, percent_omissions_col} - {None})

    omissions_col = find_col(cpt_df, [("raw", "omission"), ("omission",)], "omissions",
                              exclude={id_c, rt_mean_col, rt_std_col, percent_omissions_col,
                                       percent_commissions_col} - {None},
                              avoid=["percent", "t score"])
    commissions_col = find_col(cpt_df, [("raw", "commission"), ("commission",)], "commissions",
                                exclude={id_c, rt_mean_col, rt_std_col, percent_omissions_col,
                                         percent_commissions_col, omissions_col} - {None},
                                avoid=["percent", "t score"])

    found_columns["ID (CPT-II)"] = id_c
    found_columns["RT Mean"] = rt_mean_col
    found_columns["RT Standard Deviation"] = rt_std_col
    found_columns["Percent Omissions"] = percent_omissions_col
    found_columns["Percent Commissions"] = percent_commissions_col
    found_columns["Omissions (raw count)"] = omissions_col
    found_columns["Commissions (raw count)"] = commissions_col

    log("Numeric CPT-II columns found: rt_mean=%r rt_std=%r percent_omissions=%r "
        "percent_commissions=%r raw_omissions=%r raw_commissions=%r" % (
            rt_mean_col, rt_std_col, percent_omissions_col, percent_commissions_col,
            omissions_col, commissions_col))

    if not (rt_mean_col and rt_std_col):
        raise RuntimeError(
            "Could not find the RT mean/RT std columns in the CPT-II csv. "
            "Set COLUMN_OVERRIDES['rt_mean'] and COLUMN_OVERRIDES['rt_std'] manually."
        )

    out = pd.DataFrame()
    out["id"] = cpt_df[id_c].astype(str).str.strip()
    out["rt_mean"] = pd.to_numeric(cpt_df[rt_mean_col], errors="coerce")

    rt_std_low = str(rt_std_col).lower().replace("_", " ").replace("-", " ")
    is_standard_error = ("se" in rt_std_low) and ("sd" not in rt_std_low) and ("std" not in rt_std_low)

    raw_rt_std = pd.to_numeric(cpt_df[rt_std_col], errors="coerce")

    if is_standard_error:
        if omissions_col:
            raw_omissions_n = pd.to_numeric(cpt_df[omissions_col], errors="coerce").fillna(0)
        elif percent_omissions_col:
            raw_omissions_n = (pd.to_numeric(cpt_df[percent_omissions_col], errors="coerce").fillna(0) / 100.0) * 360.0
        else:
            raw_omissions_n = 0.0
        n_hits = (360.0 - raw_omissions_n).clip(lower=1.0)
        out["Calculated_HitRT_SD"] = raw_rt_std * np.sqrt(n_hits)
        out["rt_std"] = out["Calculated_HitRT_SD"]
        found_columns["RT std -- calculation method"] = (
            "%s (SE) * sqrt(360 - Omissions) -> Calculated_HitRT_SD" % rt_std_col
        )
        log("Column %r identified as Standard Error -- recalculating to SD via * sqrt(n_hits)" % rt_std_col)
    else:
        out["rt_std"] = raw_rt_std
        found_columns["RT std -- calculation method"] = "%s -- already a raw SD, no recalculation needed" % rt_std_col

    if not (percent_omissions_col and percent_commissions_col):
        raise RuntimeError(
            "Could not find the 'Percent Omissions'/'Percent Commissions' columns in "
            "the CPT-II csv -- accuracy_pct is computed directly from these two "
            "columns. Set COLUMN_OVERRIDES manually if auto-detection got it wrong."
        )

    po = pd.to_numeric(cpt_df[percent_omissions_col], errors="coerce").fillna(0)
    pc = pd.to_numeric(cpt_df[percent_commissions_col], errors="coerce").fillna(0)
    out["accuracy_pct"] = 100.0 - (po + pc)

    if percent_commissions_col:
        out["percent_commissions"] = pd.to_numeric(cpt_df[percent_commissions_col], errors="coerce")
    elif commissions_col:
        out["percent_commissions"] = (pd.to_numeric(cpt_df[commissions_col], errors="coerce").fillna(0) / 360.0) * 100.0
    else:
        out["percent_commissions"] = np.nan

    rt_change_col, se_change_col = find_fatigue_change_columns(cpt_df)
    found_columns["Fatigue column -- HitRT Block Change"] = rt_change_col or "not found"
    found_columns["Fatigue column -- HitSE Block Change"] = se_change_col or "not found"
    log("Fatigue columns (Block Change): HitRTBlock=%r HitSEBlock=%r" % (
        rt_change_col, se_change_col))

    fatigue_cols = {"rt_change_col": rt_change_col, "se_change_col": se_change_col}
    if rt_change_col:
        out[rt_change_col] = pd.to_numeric(cpt_df[rt_change_col], errors="coerce")
    if se_change_col:
        out[se_change_col] = pd.to_numeric(cpt_df[se_change_col], errors="coerce")

    return out, fatigue_cols

def find_confounder_columns(patient_df, exclude):
    age_col = find_col(patient_df, [("age",)], "age", exclude=exclude)
    sex_col = find_col(patient_df, [("sex",), ("gender",)], "sex",
                        exclude=exclude | ({age_col} if age_col else set()))
    med_col = find_col(patient_df, [("medication",), ("stimulant",), ("medicine",)], "medication",
                        exclude=exclude | ({age_col} if age_col else set()) | ({sex_col} if sex_col else set()))
    return age_col, sex_col, med_col

def load_real_patients(found_columns):
    patient_df = download_or_load(
        PATIENT_INFO_URL,
        ["patient_info.csv", "hyperaktiv_patient_info.csv"],
        save_name="hyperaktiv_patient_info.csv",
    )
    cpt_df = download_or_load(
        CPT_II_URL,
        ["CPT_II_ConnersContinuousPerformanceTest.csv", "hyperaktiv_cpt_ii.csv"],
        save_name="hyperaktiv_cpt_ii.csv",
    )

    found_columns["patient_info.csv shape"] = "%d rows x %d columns" % patient_df.shape
    found_columns["CPT-II csv shape"] = "%d rows x %d columns" % cpt_df.shape

    time_audit_list = audit_time_columns(cpt_df)
    found_columns["__time_audit__"] = time_audit_list
    log("Raw timing metrics audit -- columns found: %d (%s)" % (
        len(time_audit_list), ", ".join(time_audit_list) if time_audit_list else "none"))

    id_p = find_col(patient_df, [("id",), ("patient",), ("subject",)], "id")
    group_col = find_col(patient_df, [("adhd",), ("group",), ("diagnos",), ("label",)], "group",
                          exclude={id_p} if id_p else None)
    id_c = find_col(cpt_df, [("id",), ("patient",), ("subject",)], "id")

    found_columns["ID (patient_info)"] = id_p
    found_columns["Group/diagnosis"] = group_col

    log("Key columns: id_p=%r group=%r id_c=%r" % (id_p, group_col, id_c))

    if not (id_p and group_col and id_c):
        raise RuntimeError(
            "Could not determine id/group in patient_info.csv or id in the CPT-II "
            "csv. Set COLUMN_OVERRIDES manually."
        )
    if id_p == group_col:
        raise RuntimeError(
            "The ID column and the group column are the same (%r) in "
            "patient_info.csv. Set COLUMN_OVERRIDES['id'] and "
            "COLUMN_OVERRIDES['group'] manually." % id_p
        )

    age_col, sex_col, med_col = find_confounder_columns(patient_df, exclude={id_p, group_col})
    found_columns["Confounder -- Age"] = age_col or "not found"
    found_columns["Confounder -- Sex/Gender"] = sex_col or "not found"
    found_columns["Confounder -- Medication/Stimulants"] = med_col or "not found"
    log("Confounder columns: age=%r sex=%r medication=%r" % (age_col, sex_col, med_col))

    cpt_agg, fatigue_cols = load_aggregated_cpt(cpt_df, id_c, found_columns)

    id_group_df = pd.DataFrame({
        "id": patient_df[id_p].astype(str).str.strip(),
        "group": patient_df[group_col],
    })
    confound_cols_present = []
    if age_col:
        id_group_df["age"] = pd.to_numeric(patient_df[age_col], errors="coerce")
        confound_cols_present.append("age")
    if sex_col:
        id_group_df["sex"] = patient_df[sex_col]
        confound_cols_present.append("sex")
    if med_col:
        id_group_df["medication"] = patient_df[med_col]
        confound_cols_present.append("medication")

    merged = pd.merge(id_group_df, cpt_agg, on="id", how="inner")
    if merged.empty:
        sample_left = id_group_df["id"].head(5).tolist()
        sample_right = cpt_agg["id"].head(5).tolist()
        raise RuntimeError(
            "Merging by ID produced 0 rows. Example IDs from patient_info.csv: %s. "
            "Example IDs from the CPT-II csv: %s. Set COLUMN_OVERRIDES['id']." % (sample_left, sample_right)
        )
    merged = merged.drop_duplicates(subset="id", keep="first")

    def to_adhd_flag(v):
        s = str(v).strip().lower()
        return s in ("1", "1.0", "true", "adhd", "yes", "patient")

    merged["is_adhd"] = merged["group"].apply(to_adhd_flag)

    core_cols = ["id", "is_adhd", "rt_mean", "rt_std", "accuracy_pct", "percent_commissions"]
    fatigue_all_cols = [c for c in (fatigue_cols.get("rt_change_col"), fatigue_cols.get("se_change_col")) if c]
    keep_cols = core_cols + fatigue_all_cols + confound_cols_present
    result = merged[keep_cols].dropna(subset=["rt_mean", "rt_std", "accuracy_pct"])

    found_columns["Shape after merge by ID"] = "%d rows x %d columns" % merged.shape
    found_columns["Participants with complete data"] = "%d (ADHD=%d, control=%d)" % (
        len(result), int(result["is_adhd"].sum()), int((~result["is_adhd"]).sum()))

    log("Participants loaded with complete data: %d (ADHD=%d, control=%d)" % (
        len(result), result["is_adhd"].sum(), (~result["is_adhd"]).sum()))

    if len(result) == 0:
        raise RuntimeError(
            "After computing rt_mean/rt_std/accuracy_pct, no complete row remained. "
            "Check the column auto-detection and set COLUMN_OVERRIDES if necessary."
        )
    return result, fatigue_cols, confound_cols_present

HYPOTHESIS_ANCHOR_POINTS = {
    "sustainable_flow": [
        (273.04722566604926, 51.99137103744097, 78.0),
        (311.3212321240381, 52.27661951777437, 79.0),
        (271.03738884185094, 51.91329102486071, 76.0),
        (298.1530707704137, 65.64049255715166, 84.0),
        (294.7356005032634, 60.481144855511374, 78.0),
        (315.94239106975135, 77.70872746580685, 86.0),
        (268.35487185184394, 76.9091842435304, 79.0),
        (289.4712657966125, 80.53226716712439, 79.0),
        (261.1495687663214, 85.07369570637209, 79.0),
        (263.3149884762494, 84.34978719252416, 79.0),
        (282.2601962885196, 83.57102932464502, 80.0),
        (305.9851178771107, 85.77669597973495, 80.0),
        (305.83513844296965, 92.9844494408887, 81.0),
        (270.25540698398083, 88.23551437895813, 77.0),
        (315.1745424697585, 100.65489292125253, 80.0),
        (295.9895706262679, 111.1621573476732, 84.0),
        (292.3936001135308, 107.07078950956785, 82.0),
        (269.53215563794697, 104.728513655194, 78.0),
        (267.98906676199647, 104.04757737977287, 77.0),
        (303.36875115957923, 100.33888136449681, 76.0),
        (294.94441126950545, 108.04892127768069, 80.0),
        (270.24770124793406, 108.90776815912814, 79.0),
        (279.7102112096168, 109.18150675882305, 79.0),
        (299.9, 107.58712748279879, 79.0),
        (251.6110132800594, 114.87622697996214, 78.0),
        (326.041739901707, 109.43952496369077, 77.0),
        (324.4060531010143, 114.67811885777458, 80.0),
        (281.85953039253735, 110.72233323157882, 77.0),
        (248.83908812543203, 119.9277928679177, 79.0),
        (279.2479043566055, 128.58415408846028, 85.0),
        (281.49442873340445, 110.08042914518808, 77.0),
        (314.6035913381742, 120.23694328954842, 81.0),
        (277.5951489152583, 119.12278587786936, 80.0),
        (243.9352683875989, 112.28676936069333, 76.0),
        (295.76556585902495, 115.65466969984288, 79.0),
        (298.67495017469895, 124.72120535840968, 83.0),
        (245.38204246009988, 123.67409135514795, 81.0),
        (295.4617228321855, 117.68016288334535, 77.0),
        (285.516731990261, 122.56138784738155, 79.0),
        (244.70546078381062, 122.55294959158455, 76.0),
        (319.4227556717379, 137.93216987802856, 85.0),
        (222.0037178929833, 131.41872424577383, 78.0),
        (312.830095593192, 125.16556797749259, 78.0),
        (316.1695912348552, 143.49953483584133, 87.0),
        (265.3767940504182, 128.81091527619978, 79.0),
        (288.9100718919646, 149.36113901204877, 88.0),
        (266.2901872928575, 133.9791527442757, 81.0),
        (267.3224871769892, 132.63919770908902, 79.0),
        (327.96624715173414, 144.09057792257667, 86.0),
        (298.9292340890359, 138.61567296432793, 79.79797979797979),
        (303.35399023895525, 137.22566889409885, 80.0),
        (333.8077159126946, 148.58386351431733, 86.0),
        (213.0341802875374, 138.77520259527924, 77.0),
        (268.9908963052639, 140.93295028184878, 80.0),
        (287.6774910075747, 137.13836954575976, 78.0),
        (257.0604968666862, 146.24727180635847, 81.0),
        (329.9669472916207, 146.2945483768605, 84.0),
        (293.9908542211532, 146.6848782827617, 83.0),
        (291.8347104354404, 148.26316488628018, 83.0),
        (305.33628897351383, 143.12026920966372, 77.0),
        (300.4625032879238, 147.04702868448285, 79.0),
        (282.9615165263879, 146.3182420176704, 78.0),
        (311.57154147177835, 149.147522872181, 80.0),
        (303.23268739888056, 140.17040760209576, 76.0),
        (232.27085955692084, 145.12271324486466, 76.0),
        (280.69043578611746, 146.92093516079706, 78.0),
        (312.30520950261405, 146.60317028906272, 79.0),
        (267.70475942214244, 148.20564981204797, 79.0),
        (269.19992700406897, 143.1169420336611, 77.0),
        (298.9896783936338, 152.03222414990145, 81.0),
        (276.3574837455394, 153.11057615166632, 81.0),
        (312.57100654059025, 154.20591375152256, 80.0),
        (258.88753103886006, 163.72672413602905, 84.0),
        (300.8590358105337, 158.47847455842236, 80.0),
        (273.07008040127914, 155.41600809810166, 79.0),
        (217.28933670675985, 162.97189675724732, 80.0),
        (232.02822841829834, 167.04721572472965, 79.0),
        (304.3163300524066, 162.18875818492307, 79.0),
        (298.44138217824957, 169.80235134911405, 82.0),
        (294.3606562033867, 171.69078543853993, 84.0),
        (318.60980488427845, 161.60698415901825, 79.0),
        (260.7193349129086, 161.87827291031178, 77.0),
        (283.0107636445231, 162.36158539129738, 77.0),
        (288.16229067017923, 162.9797711245499, 77.0),
        (282.30488929692683, 175.78832191471938, 82.0),
        (277.25139680460495, 165.51232196938543, 79.0),
        (288.4500384504893, 169.8584347247934, 81.0),
        (258.3101624014912, 165.01527208733177, 77.0),
        (285.47422853324167, 172.1951197015893, 79.0),
        (310.96303280912025, 174.69757215034917, 80.8080808080808),
        (308.57309720330323, 169.03963405736496, 76.0),
        (268.52630073366447, 177.79492703140633, 79.0),
        (250.98287538487872, 176.27071105936335, 80.0),
        (300.73000063155973, 172.32510795656628, 77.0),
        (307.91491744552457, 180.1727923895449, 80.0),
        (244.4575048903188, 179.46865228632078, 79.0),
        (286.2193777755995, 174.11652378998014, 77.0),
        (320.9915630738579, 173.69505953293145, 75.75757575757575),
        (303.76134996732935, 186.25903504132262, 81.0),
        (277.15217549358624, 174.373480733186, 76.0),
        (330.8518737698958, 180.3832996888187, 78.0),
        (305.2770896666644, 191.58910259587, 83.0),
        (264.12125226818824, 182.84586577127246, 76.0),
        (301.7019697624512, 179.09185708807215, 76.0),
        (273.22566837336285, 192.3231951947742, 79.59183673469387),
        (326.66598200407753, 183.35793363080313, 77.0),
        (241.97452555854355, 189.37044225366998, 77.0),
        (276.8784174006596, 187.58569096825312, 78.0),
        (307.02970608553596, 190.5150505807169, 77.0),
        (286.9081865832723, 192.079061035012, 76.76767676767676),
        (278.7661381643506, 191.65075030397858, 76.0),
        (250.9815613500237, 195.12128561060717, 78.0),
        (299.3665230041623, 202.7457449403774, 80.0),
        (341.5269574993001, 199.34389245356766, 77.0),
        (324.4623868408414, 203.89184158757405, 78.0),
        (276.17146821195075, 216.76471259040193, 82.0),
        (330.79766609747423, 205.73648999409772, 78.0),
        (249.57621243672656, 217.84529103919303, 75.75757575757575),
        (321.4058719071813, 219.58989917388806, 77.0),
        (312.8749853266035, 224.67882783916028, 75.51020408163265),
        (305.37922019310616, 229.15118005719347, 75.75757575757575),
        (278.5545976022456, 236.83557810270383, 77.77777777777777),
        (314.4737218133033, 236.9761455352636, 76.53061224489795),
    ],
    "noise_resonance": [
        (372.25377054243586, 246.5325251784459, 71.1340206185567),
        (373.25522548587736, 279.7083700519884, 75.78947368421052),
        (373.40027131712895, 191.95136626035955, 83.83838383838383),
        (429.04317866399634, 192.49400639848787, 83.33333333333333),
        (429.42224727519744, 281.3163865512566, 70.65217391304348),
        (408.0675169065206, 277.90486650631107, 75.26881720430107),
        (436.6917279926025, 241.18155687914376, 78.125),
        (426.5707024487319, 227.16519255711557, 80.0),
        (365.64905680927734, 271.9137272026621, 75.78947368421052),
        (392.89070309937875, 269.86181565159575, 72.04301075268818),
        (421.0673265984366, 233.77057997830576, 76.04166666666667),
        (407.9633715359736, 266.49303403750963, 71.27659574468085),
        (431.458910843816, 201.61720975946739, 74.48979591836735),
        (432.2351344536809, 194.77961055497505, 80.0),
        (369.5803095970512, 251.79938209200535, 75.25773195876289),
        (351.5844313572411, 226.9552870001719, 71.42857142857143),
        (366.5724289270459, 255.21776760991276, 81.25),
        (402.99221643378615, 178.62106426366125, 78.0),
        (403.543781786426, 259.86032187080906, 76.84210526315789),
        (379.0476092499612, 286.9748068808102, 73.33333333333333),
        (408.70374897543655, 222.24832942483275, 79.16666666666667),
        (332.5572772903586, 197.7093644603577, 75.75757575757575),
        (361.68326152883753, 210.40334393691813, 74.48979591836735),
        (423.2242567001378, 256.3306166623324, 78.94736842105263),
        (388.9723432851689, 312.88206959201864, 82.79569892473118),
        (345.98038306263857, 226.84174573913478, 74.48979591836735),
        (388.65849035844053, 270.629346036973, 71.27659574468085),
        (400.85181996670013, 215.3420608536752, 74.48979591836735),
        (405.47946668290183, 193.4836115412013, 74.74747474747475),
        (423.0927547333206, 178.91965125906003, 82.65306122448979),
        (421.8839138017814, 250.99702921098557, 74.22680412371135),
        (398.47026023389594, 197.59641456724765, 81.81818181818181),
    ],
    "super_d1_flow": [
        (229.81203331543236, 102.84477595109178, 75.0),
        (231.2441004103019, 99.91524272221284, 66.0),
        (234.4100910683215, 138.00990867024657, 76.0),
        (247.9037873179048, 211.98871698057837, 64.64646464646465),
        (255.4746918866045, 140.52510829873725, 78.0),
        (249.5001456883908, 116.04409610763436, 78.0),
        (230.85696385016942, 148.19462522840593, 70.0),
    ],
    "entropy_paradox": [
        (95.72969136083313, 228.34857376424986, 67.67676767676768),
        (119.83594082968644, 185.6078485171335, 68.0),
        (109.59793721250443, 168.86776338465754, 62.0),
        (117.7987250981036, 189.00696597790625, 69.0),
        (103.32953802775472, 192.79312522875404, 61.0),
        (105.97199119017569, 224.00042033418237, 64.0),
        (105.3032479023678, 191.07947859789167, 62.0),
        (103.92375820585721, 231.00749027789834, 64.64646464646465),
        (105.06975825330224, 194.65294252867113, 62.0),
        (134.7592234254029, 197.2322633709884, 69.0),
        (106.08805204877177, 177.44873127751018, 65.0),
        (132.63392672987382, 188.70023610827553, 69.0),
        (108.83796794872731, 176.891024384855, 69.0),
        (95.3, 233.4585830506131, 63.265306122448976),
        (114.31030753376102, 172.38494823258347, 65.0),
        (96.45937845676671, 160.5806186117654, 63.0),
        (111.23226207978456, 206.12824104152193, 61.0),
        (134.77682434437847, 212.5022189357258, 75.0),
        (128.5671800669637, 205.16993032507668, 72.0),
        (108.87752862671373, 185.50791564880387, 64.0),
        (106.62051297870696, 185.14251086307405, 62.0),
        (97.21339812608778, 199.12975597442085, 64.0),
        (116.51029304111627, 175.93688989878183, 71.0),
        (119.4117377247854, 210.69919511451585, 63.0),
        (93.68594139740628, 171.61407532172566, 63.0),
        (100.4, 212.63075976913592, 63.0),
        (97.42746825829025, 235.7304865985185, 64.94845360824742),
        (102.86155052045893, 198.0579773671954, 63.0),
        (108.99270258538134, 152.68974511565438, 62.0),
        (96.7931262808257, 205.19909993808753, 61.0),
        (136.54405885328515, 227.4808077081142, 70.0),
        (145.55174326232338, 168.81379455128706, 74.0),
        (107.78280978944913, 152.6447265061078, 62.0),
        (97.0455694764079, 161.17367119219156, 66.0),
        (100.51636521876675, 184.40842990051198, 61.0),
        (116.21960768857045, 222.85878724350974, 66.3265306122449),
        (127.98801583441971, 200.4869932353182, 70.0),
        (98.11812067910974, 158.6533815882933, 64.0),
        (112.87108961694008, 205.92755626186585, 66.66666666666667),
        (104.14441199217292, 183.22501348362533, 64.0),
        (133.6091968432333, 173.2280353707728, 68.0),
        (132.11950862870512, 202.01016132796954, 70.0),
        (113.27933932549736, 172.46685986839586, 63.0),
        (110.10517566519455, 164.74554778829082, 68.0),
        (114.1496256342858, 233.60142442980063, 65.3061224489796),
        (98.13249180083506, 198.05090177340543, 65.0),
        (106.5947225826353, 188.9262294359467, 64.0),
        (108.32428003780282, 196.69917826867217, 62.0),
        (95.40600382735651, 151.88820618482814, 61.0),
        (100.2, 185.91922977465242, 61.0),
        (122.17317732690252, 172.26767912710903, 65.0),
        (108.48965381637915, 229.77508975476195, 65.65656565656566),
        (124.01905980925378, 210.9297928748657, 70.0),
        (117.38080927920717, 187.7738395317706, 69.0),
        (92.81306486944348, 212.988375784064, 61.0),
        (159.0861293490435, 171.57272278652496, 78.0),
        (109.59911063096799, 219.3967044580079, 64.64646464646465),
        (119.7193183329505, 188.7936087485632, 66.0),
        (107.73631177207069, 174.23448226864068, 68.0),
        (97.58633363302417, 205.6045757436556, 63.0),
        (100.2540078543668, 206.21484517035628, 63.0),
        (96.4050684369099, 212.9021528465735, 61.61616161616162),
        (112.49932342217289, 228.17725934163443, 66.0),
        (106.61329072177794, 178.003698903012, 64.0),
        (102.77162578116037, 179.37874106243984, 62.0),
        (96.31827497365259, 184.851267288835, 64.0),
        (97.13991821193358, 250.44718804646604, 67.01030927835052),
        (111.07208794155929, 183.3334742972095, 62.0),
        (111.76546852657948, 158.2323488007332, 63.0),
        (107.16940892506202, 171.75943927059902, 65.0),
        (102.2105246125714, 211.9529952523131, 70.0),
        (123.19423101886707, 204.6806342820622, 69.0),
        (101.76296305705063, 213.1219761565325, 63.0),
        (112.94974884555047, 209.8982921658062, 67.0),
        (112.47503275186176, 215.76702896465628, 67.0),
        (113.57787746364318, 176.0818746048827, 65.0),
        (93.28040904332266, 166.09458691936877, 61.0),
        (108.71537242973781, 230.21510025633694, 68.68686868686869),
        (94.75788498046151, 199.9371130963218, 62.62626262626262),
    ],
}

def load_hypothesis_points():
    points = {
        name: list(vectors) for name, vectors in HYPOTHESIS_ANCHOR_POINTS.items()
    }

    for name, pts in points.items():
        log("  Hypothesis points '%s': %d" % (name, len(pts)))

    return {k: np.array(v, dtype=float) for k, v in points.items() if len(v) > 0}

def standardize(all_matrices):
    stacked = np.vstack(all_matrices)
    mu = stacked.mean(axis=0)
    sigma = stacked.std(axis=0)
    sigma[sigma == 0] = 1.0
    return mu, sigma

def run_mannwhitney_by_cluster(real_df, cluster_names, metric_col="percent_commissions"):
    num_comparisons = max(len(cluster_names), 1)
    bonferroni_alpha = BONFERRONI_BASE_ALPHA / num_comparisons

    results = []
    for name in cluster_names:
        cluster_sub = real_df[real_df["nearest_cluster"] == name]
        adhd_vals = pd.to_numeric(cluster_sub[cluster_sub["is_adhd"]][metric_col], errors="coerce").dropna()
        ctrl_vals = pd.to_numeric(cluster_sub[~cluster_sub["is_adhd"]][metric_col], errors="coerce").dropna()
        n1, n2 = len(adhd_vals), len(ctrl_vals)

        u_stat = p_value = effect_r = None
        error_note = None
        if n1 >= 1 and n2 >= 1:
            try:
                u_stat, p_value = scipy_stats.mannwhitneyu(adhd_vals, ctrl_vals, alternative="two-sided")
                u_stat = float(u_stat)
                p_value = float(p_value)
                effect_r = 1.0 - (2.0 * u_stat) / (n1 * n2)
            except Exception as e:
                error_note = str(e)
        else:
            error_note = "not enough data for the test (need n>=1 in both groups)"

        significant = (p_value is not None) and (p_value < bonferroni_alpha)
        results.append({
            "cluster": name,
            "n1_adhd": n1,
            "n2_control": n2,
            "u_stat": u_stat,
            "p_value": p_value,
            "effect_r": effect_r,
            "significant": significant,
            "error_note": error_note,
        })

        display_name = CLUSTER_DISPLAY_LABELS.get(name, name)
        if error_note:
            log("  Mann-Whitney [%s]: %s (n1=%d, n2=%d)" % (display_name, error_note, n1, n2))
        else:
            log("  Mann-Whitney [%s]: n1=%d n2=%d U=%.2f p=%.4f r=%.3f significant(<%.4f)=%s" % (
                display_name, n1, n2, u_stat, p_value, effect_r, bonferroni_alpha, significant))

    return results, bonferroni_alpha

N_PERMUTATIONS = 1000
PERMUTATION_TARGET_CLUSTER = "super_d1_flow"                                     
PERMUTATION_TARGET_METRIC = "percent_commissions"
PERMUTATION_REAL_P_VALUE = 0.0004                                                                                                                

def classify_nearest_cluster(vecs_z, centroids, cluster_names):
    dists = np.vstack([
        np.linalg.norm(vecs_z - centroids[name], axis=1) for name in cluster_names
    ]).T
    nearest_idx = dists.argmin(axis=1)
    return np.array([cluster_names[i] for i in nearest_idx])

def run_permutation_test(real_df, real_z, centroids, cluster_names,
                          target_cluster=PERMUTATION_TARGET_CLUSTER,
                          metric_col=PERMUTATION_TARGET_METRIC,
                          real_p_value=PERMUTATION_REAL_P_VALUE,
                          n_permutations=N_PERMUTATIONS):
    """
    Empirical permutation test for Subtype 1 ("Decompensated Sprint").

    Repeatedly shuffles the ADHD / Clinical Control diagnosis labels across
    the merged dataset while keeping every phenotypic measurement (RT,
    Calculated_HitRT_SD / HitSE, Percent Commissions, Accuracy) fixed in
    place. For each shuffle we re-run the same fixed-anchor Euclidean
    distance classification against HYPOTHESIS_ANCHOR_POINTS and recompute
    the two-tailed Mann-Whitney U test on Percent Commissions inside the
    resulting Subtype 1 cluster.

    Note: because the HYPOTHESIS_ANCHOR_POINTS centroids are fixed and never
    depend on the diagnosis labels, shuffling labels does not change which
    participants fall into Subtype 1 -- only which of those participants are
    labeled ADHD vs Control changes. That is exactly the correct null model
    here: it tests whether the observed Percent Commissions gap inside this
    fixed cluster could plausibly arise from random label assignment, which
    is precisely what would need to be true for the analytical p-value to be
    a geometric artifact of the centroid placement rather than a real signal.
    """
    log("\n===== EMPIRICAL PERMUTATION TEST (%s) =====" % CLUSTER_DISPLAY_LABELS.get(target_cluster, target_cluster))
    log("Running %d label-shuffle permutations against the fixed hypothesis anchors..." % n_permutations)

    metric_values = pd.to_numeric(real_df[metric_col], errors="coerce").to_numpy(dtype=float)
    is_adhd_actual = real_df["is_adhd"].to_numpy(dtype=bool)

    rng = np.random.default_rng()

    count_le_actual = 0
    valid_permutations = 0

    for i in range(1, n_permutations + 1):
        shuffled_is_adhd = rng.permutation(is_adhd_actual)

        nearest_cluster_perm = classify_nearest_cluster(real_z, centroids, cluster_names)

        cluster_mask = nearest_cluster_perm == target_cluster
        cluster_metric = metric_values[cluster_mask]
        cluster_labels = shuffled_is_adhd[cluster_mask]

        adhd_vals = cluster_metric[cluster_labels]
        adhd_vals = adhd_vals[~np.isnan(adhd_vals)]
        ctrl_vals = cluster_metric[~cluster_labels]
        ctrl_vals = ctrl_vals[~np.isnan(ctrl_vals)]

        if len(adhd_vals) >= 1 and len(ctrl_vals) >= 1:
            try:
                _, p_perm = scipy_stats.mannwhitneyu(adhd_vals, ctrl_vals, alternative="two-sided")
                valid_permutations += 1
                if p_perm <= real_p_value:
                    count_le_actual += 1
            except Exception:
                pass

        if i % 100 == 0:
            log("Running statistical permutations: %d/%d..." % (i, n_permutations))

    p_empirical = count_le_actual / float(n_permutations)

    log("Empirical permutation test complete.")
    log("  Valid permutations (both groups present in Subtype 1): %d/%d" % (valid_permutations, n_permutations))
    log("  Shuffles with p <= %.4f: %d" % (real_p_value, count_le_actual))
    log("  Empirical Permutation p-value (N=%d) = %.4f" % (n_permutations, p_empirical))

    return {
        "n_permutations": n_permutations,
        "count_le_actual": count_le_actual,
        "valid_permutations": valid_permutations,
        "p_empirical": p_empirical,
        "real_p_value": real_p_value,
        "target_cluster": target_cluster,
    }

def build_fatigue_profiles(real_df, fatigue_cols):
    rt_change_col = fatigue_cols.get("rt_change_col")
    se_change_col = fatigue_cols.get("se_change_col")

    profiles = {}
    for cluster_key, label in SUBTYPE_LABELS.items():
        sub = real_df[(real_df["nearest_cluster"] == cluster_key) & (real_df["is_adhd"])]
        n = len(sub)

        rt_change_mean = None
        se_change_mean = None
        if rt_change_col and rt_change_col in sub.columns:
            vals = pd.to_numeric(sub[rt_change_col], errors="coerce").dropna()
            rt_change_mean = float(vals.mean()) if len(vals) else None
        if se_change_col and se_change_col in sub.columns:
            vals = pd.to_numeric(sub[se_change_col], errors="coerce").dropna()
            se_change_mean = float(vals.mean()) if len(vals) else None

        profiles[cluster_key] = {
            "label": label, "n": n,
            "rt_change_col": rt_change_col, "se_change_col": se_change_col,
            "rt_change_mean": rt_change_mean, "se_change_mean": se_change_mean,
        }

    return profiles

def summarize_confounder_series(series):
    numeric = pd.to_numeric(series, errors="coerce")
    non_null = series.dropna()
    if len(non_null) == 0:
        return {"type": "empty"}
    if numeric.notna().sum() >= max(1, int(0.8 * len(non_null))):
        return {"type": "numeric", "mean": float(numeric.mean()), "std": float(numeric.std()), "n": int(numeric.notna().sum())}
    dist = non_null.astype(str).value_counts(normalize=True).mul(100).round(1).to_dict()
    return {"type": "categorical", "distribution": dist, "n": len(non_null)}

def build_confounder_summary(real_df, confound_cols_present):
    summary = {}
    for cluster_key, label in SUBTYPE_LABELS.items():
        sub = real_df[(real_df["nearest_cluster"] == cluster_key) & (real_df["is_adhd"])]
        entry = {"label": label, "n": len(sub), "fields": {}}
        for field in ("age", "sex", "medication"):
            if field in confound_cols_present and field in sub.columns:
                entry["fields"][field] = summarize_confounder_series(sub[field])
        summary[cluster_key] = entry
    return summary

def format_confounder_field(field_name, field_stats):
    en_names = {"age": "Age", "sex": "Sex/Gender", "medication": "Medication/Stimulants"}
    label = en_names.get(field_name, field_name)
    if field_stats["type"] == "empty":
        return "    %s: no data" % label
    if field_stats["type"] == "numeric":
        return "    %s: mean = %.2f (std = %.2f, n = %d)" % (
            label, field_stats["mean"], field_stats["std"], field_stats["n"])
    dist_str = ", ".join("%s = %.1f%%" % (k, v) for k, v in field_stats["distribution"].items())
    return "    %s: %s (n = %d)" % (label, dist_str, field_stats["n"])

def write_clean_report(found_columns, cluster_table, subtype_stats, mannwhitney_results,
                        bonferroni_alpha, fatigue_profiles, confound_summary, out_path,
                        permutation_result=None, exclusion_mode="centroid",
                        technical_invalid_summary=None):
    time_audit_list = found_columns.pop("__time_audit__", [])

    lines = []
    lines.append("HYPERAKTIV Validator -- Final Report (\"Allostatic Sprint\" Hypothesis)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("1. COLUMNS FOUND AND TABLE SHAPES")
    lines.append("-" * 70)
    for key, value in found_columns.items():
        lines.append("%-45s : %s" % (key, value))
    lines.append("")
    lines.append("2. RAW TIMING METRICS AUDIT")
    lines.append("-" * 70)
    if time_audit_list:
        for col_name in time_audit_list:
            marker = " <- CURRENTLY USED FOR RT" if col_name in (
                found_columns.get("RT Mean"), found_columns.get("RT Standard Deviation")
            ) else ""
            lines.append("  - %s%s" % (col_name, marker))
    else:
        lines.append("  (nothing found)")
    lines.append("")
    lines.append("3. DISTRIBUTION OF REAL PATIENTS ACROSS HYPOTHESIS CLUSTERS")
    lines.append("-" * 70)
    lines.append("CURRENT OUTLIER MITIGATION MODE: %s" % exclusion_mode)
    if technical_invalid_summary and technical_invalid_summary["n_total"] > 0:
        lines.append("  %s (rt_mean < %.1f): n=%d (ADHD=%d, Control=%d) -- excluded from the cluster "
                      "analysis below and reported here as a separate category." % (
                          technical_invalid_summary["label"], technical_invalid_summary["cutoff"],
                          technical_invalid_summary["n_total"], technical_invalid_summary["n_adhd"],
                          technical_invalid_summary["n_control"]))
    lines.append("")
    cluster_names = list(next(iter(cluster_table.values())).keys())
    label_col_width = max(20, max(len(CLUSTER_DISPLAY_LABELS.get(n, n)) for n in cluster_names) + 2)
    header = ("%-" + str(label_col_width) + "s") % "Hypothesis Cluster"
    for group_label in cluster_table:
        header += "%20s" % group_label
    lines.append(header)
    for cluster_name in cluster_names:
        display_name = CLUSTER_DISPLAY_LABELS.get(cluster_name, cluster_name)
        row = ("%-" + str(label_col_width) + "s") % display_name
        for group_label in cluster_table:
            row += "%19.1f%%" % cluster_table[group_label][cluster_name]
        lines.append(row)
    lines.append("")

    lines.append("4. ADHD SUBTYPES (renamed under the \"Allostatic Sprint\" hypothesis)")
    lines.append("-" * 70)
    for cluster_key, stats_row in subtype_stats.items():
        label = SUBTYPE_LABELS.get(cluster_key, cluster_key)
        desc = SUBTYPE_DESCRIPTIONS.get(cluster_key, "")
        lines.append("  %s (cluster '%s')" % (label, cluster_key))
        if desc:
            lines.append("    %s" % desc)
        for row_label, n, mean_pc, mean_acc in stats_row:
            if n == 0:
                lines.append("    %-12s: no real participants in this cluster (n=0)" % row_label)
                continue
            if mean_pc is None:
                lines.append("    %-12s: n=%d, Percent Commissions unavailable" % (row_label, n))
            else:
                lines.append("    %-12s: n=%d, mean Percent Commissions = %.1f%%" % (row_label, n, mean_pc))
            if mean_acc is None:
                lines.append("    %-12s  mean True Accuracy unavailable" % "")
            else:
                lines.append("    %-12s  mean True Accuracy = %.1f%%" % ("", mean_acc))
        lines.append("")
    lines.append("  Note: the ~66%% (super_d1_flow) and ~28%% (noise_resonance) shares refer")
    lines.append("  to the distribution of ADHD participants across hypothesis clusters shown")
    lines.append("  in Section 3, and are WORKING reference points for validation, not fixed")
    lines.append("  exact sample percentages.")
    lines.append("  The underlying dopamine D1/D2 receptor dynamics and ATP depletion profiles")
    lines.append("  are theoretical simulated mechanisms and were not directly measured in the")
    lines.append("  clinical participants.")
    lines.append("")

    lines.append("5. FATIGUE ANALYSIS: 'BLOCK CHANGE' (SLOPE OF THE FATIGUE CURVE OVER THE TEST)")
    lines.append("-" * 70)
    lines.append("  A positive value -> the participant slowed down/got fatigued toward the end")
    lines.append("  of the test. A negative value or near zero -> the participant held")
    lines.append("  speed/stability (\"sprint\") without burning out.")
    lines.append("")
    has_any_change_data = any(
        profile["rt_change_mean"] is not None or profile["se_change_mean"] is not None
        for profile in fatigue_profiles.values()
    )
    if not has_any_change_data:
        lines.append("  Columns 'Raw Score HitRTBlock' / 'Raw Score HitSEBlock' were not found in the CPT-II csv.")
    else:
        label_width = max(
            20,
            max(len("%s (n=%d)" % (p["label"], p["n"])) for p in fatigue_profiles.values()) + 2,
        )
        header = ("%-" + str(label_width) + "s%20s%20s") % (
            "Subtype", "HitRTBlock (RT)", "HitSEBlock (SE)")
        lines.append(header)
        for cluster_key, profile in fatigue_profiles.items():
            label_with_n = "%s (n=%d)" % (profile["label"], profile["n"])
            rt_str = "%.2f" % profile["rt_change_mean"] if profile["rt_change_mean"] is not None else "N/A"
            se_str = "%.2f" % profile["se_change_mean"] if profile["se_change_mean"] is not None else "N/A"
            row = ("%-" + str(label_width) + "s%20s%20s") % (label_with_n, rt_str, se_str)
            lines.append(row)
    lines.append("")

    lines.append("6. STATISTICS: MANN-WHITNEY U (TWO-SIDED), WITHIN-CLUSTER N, BONFERRONI, EFFECT SIZE")
    lines.append("   (comparison metric: Percent Commissions; alpha after Bonferroni correction = %.4f)" % bonferroni_alpha)
    lines.append("-" * 70)
    lines.append("CURRENT OUTLIER MITIGATION MODE: %s" % exclusion_mode)
    tested_clusters = {res["cluster"] for res in mannwhitney_results}
    if NOISE_CLUSTER_KEY not in tested_clusters:
        lines.append("  Note: '%s' (%s) was not tested -- it is not an active cluster under the current "
                      "EXCLUSION_MODE, so it is skipped here rather than raising an error." % (
                          CLUSTER_DISPLAY_LABELS.get(NOISE_CLUSTER_KEY, NOISE_CLUSTER_KEY), NOISE_CLUSTER_KEY))
    lines.append("")
    for res in mannwhitney_results:
        lines.append("  Cluster: %s" % CLUSTER_DISPLAY_LABELS.get(res["cluster"], res["cluster"]))
        lines.append("    N1 (ADHD) = %d, N2 (Control) = %d" % (res["n1_adhd"], res["n2_control"]))
        if res["error_note"]:
            lines.append("    Test not performed: %s" % res["error_note"])
        else:
            lines.append("    U = %.2f, p-value (two-tailed) = %.4f" % (res["u_stat"], res["p_value"]))
            lines.append("    Effect size (rank-biserial r) = %.3f" % res["effect_r"])
            sig_text = "SIGNIFICANT after Bonferroni correction" if res["significant"] else "not significant after Bonferroni correction"
            lines.append("    %s (threshold p < %.4f)" % (sig_text, bonferroni_alpha))
            if permutation_result and res["cluster"] == permutation_result["target_cluster"]:
                lines.append("    Empirical Permutation p-value (N=%d) = %.4f" % (
                    permutation_result["n_permutations"], permutation_result["p_empirical"]))
                lines.append("    (%d/%d shuffles reached p <= %.4f; %d/%d permutations had both groups present in this cluster)" % (
                    permutation_result["count_le_actual"], permutation_result["n_permutations"],
                    permutation_result["real_p_value"], permutation_result["valid_permutations"],
                    permutation_result["n_permutations"]))
        lines.append("")

    lines.append("7. CONFOUNDER CHECK: age / sex / medication by subtype")
    lines.append("-" * 70)
    any_confounders = any(entry["fields"] for entry in confound_summary.values())
    if not any_confounders:
        lines.append("  Age/sex/medication columns were not found in patient_info.csv.")
    else:
        for cluster_key, entry in confound_summary.items():
            lines.append("  %s (n=%d)" % (entry["label"], entry["n"]))
            if not entry["fields"]:
                lines.append("    No confounder data available for this subtype.")
            else:
                for field_name, field_stats in entry["fields"].items():
                    lines.append(format_confounder_field(field_name, field_stats))
            lines.append("")

    lines.append("  Note: the underlying dopamine D1/D2 receptor dynamics and ATP depletion")
    lines.append("  profiles are theoretical simulated mechanisms and were not directly")
    lines.append("  measured in the clinical participants.")
    lines.append("")

    lines.append("Note: 'Sustainable Flow', 'Noise Resonance', 'Super D1 Flow', and Subtypes")
    lines.append("1/2 are WORKING HYPOTHESES at the validation stage, not proven clinical")
    lines.append("theories.")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

CLUSTER_SCATTER_COLORS = {
    "sustainable_flow": "#2ca02c",
    "noise_resonance": "#9467bd",
    "super_d1_flow": "#8c564b",
    "entropy_paradox": "lightgray",
}

FATIGUE_BAR_COLORS = ["#8c564b", "#9467bd", "#7f7f7f"]

FATIGUE_YLIM = (-0.05, 0.05)

def build_scatter_plot(real_df, hypotheses, color_col, cmap, title, cbar_label, output_name,
                        hue_norm=(0, 100)):
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)

    for name, pts in hypotheses.items():
        color = CLUSTER_SCATTER_COLORS.get(name, "gray")
        display_name = CLUSTER_DISPLAY_LABELS.get(name, name)
        cloud_label = display_name if name == NOISE_CLUSTER_KEY else "Hypothesis: %s" % display_name
        ax.scatter(pts[:, 0], pts[:, 1], s=14, alpha=0.30, color=color, linewidths=0,
                   label=cloud_label)
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        ax.scatter([cx], [cy], marker="X", s=90, color=color, edgecolor="black",
                   linewidth=0.8, zorder=5)

    if "nearest_cluster" in real_df.columns:
        noise_mask = real_df["nearest_cluster"] == NOISE_CLUSTER_KEY
    else:
        noise_mask = pd.Series(False, index=real_df.index)
    noise_df = real_df[noise_mask]
    main_df = real_df[~noise_mask]

    if len(noise_df):
        noise_color = CLUSTER_SCATTER_COLORS.get(NOISE_CLUSTER_KEY, "lightgray")
        noise_ctrl = noise_df[~noise_df["is_adhd"]]
        noise_adhd = noise_df[noise_df["is_adhd"]]
        ax.scatter(noise_ctrl["rt_mean"], noise_ctrl["rt_std"], marker="o", s=55,
                   color=noise_color, alpha=0.3, edgecolor="black", linewidth=0.5, zorder=4)
        ax.scatter(noise_adhd["rt_mean"], noise_adhd["rt_std"], marker="^", s=55,
                   color=noise_color, alpha=0.3, edgecolor="black", linewidth=0.5, zorder=4)

    adhd_sub = main_df[main_df["is_adhd"]].copy()
    ctrl_sub = main_df[~main_df["is_adhd"]].copy()
    adhd_sub[color_col] = pd.to_numeric(adhd_sub[color_col], errors="coerce")
    ctrl_sub[color_col] = pd.to_numeric(ctrl_sub[color_col], errors="coerce")

    sns.scatterplot(data=ctrl_sub, x="rt_mean", y="rt_std", hue=color_col, palette=cmap,
                     hue_norm=hue_norm, marker="o", s=55, edgecolor="black", linewidth=0.5,
                     ax=ax, legend=False, zorder=6)
    sns.scatterplot(data=adhd_sub, x="rt_mean", y="rt_std", hue=color_col, palette=cmap,
                     hue_norm=hue_norm, marker="^", s=55, edgecolor="black", linewidth=0.5,
                     ax=ax, legend=False, zorder=6)

    norm = plt.Normalize(vmin=hue_norm[0], vmax=hue_norm[1])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(cbar_label, fontsize=9)

    shape_handles = [
        Line2D([0], [0], marker="^", linestyle="none", markerfacecolor="lightgray",
               markeredgecolor="black", markersize=8, label="ADHD Patients"),
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="lightgray",
               markeredgecolor="black", markersize=8, label="Clinical Control"),
    ]
    hypo_handles, _ = ax.get_legend_handles_labels()
    ax.legend(handles=hypo_handles + shape_handles, frameon=False, loc="upper left",
              fontsize=8, markerscale=1.2)

    ax.set_xlabel("RT Mean, 'Raw Score HitRT' (ms)")
    ax.set_ylabel("RT Standard Deviation, 'Calculated_HitRT_SD' (ms)")
    ax.set_title(title)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    plot_path = os.path.join(get_writable_dir(), output_name)
    fig.savefig(plot_path, dpi=150)
    log("Chart saved: %s" % plot_path)

    try:
        plt.show()
    except Exception:
        pass
    finally:
        plt.close(fig)

    return plot_path

def compute_fatigue_bar_groups(real_df, fatigue_cols):
    rt_change_col = fatigue_cols.get("rt_change_col")
    se_change_col = fatigue_cols.get("se_change_col")

    SHORT_AXIS_LABELS = {
        "super_d1_flow": "Subtype 1 (Sprint)",
        "noise_resonance": "Subtype 2 (Crash)",
    }

    def mean_of(sub, col):
        if not col or col not in sub.columns:
            return None
        vals = pd.to_numeric(sub[col], errors="coerce").dropna()
        return float(vals.mean()) if len(vals) else None

    groups = []
    for cluster_key in ("super_d1_flow", "noise_resonance"):
        sub = real_df[(real_df["nearest_cluster"] == cluster_key) & (real_df["is_adhd"])]
        groups.append({
            "label": CLUSTER_DISPLAY_LABELS.get(cluster_key, cluster_key),
            "short_label": SHORT_AXIS_LABELS.get(cluster_key, cluster_key),
            "n": len(sub),
            "rt_change_mean": mean_of(sub, rt_change_col),
            "se_change_mean": mean_of(sub, se_change_col),
        })

    control_sub = real_df[~real_df["is_adhd"]]
    groups.append({
        "label": "Clinical Control Group",
        "short_label": "Clinical Control",
        "n": len(control_sub),
        "rt_change_mean": mean_of(control_sub, rt_change_col),
        "se_change_mean": mean_of(control_sub, se_change_col),
    })
    return groups

def build_fatigue_dynamics_plot(fatigue_bar_groups, output_name):
    labels = [g["label"] for g in fatigue_bar_groups]
    short_labels = [g.get("short_label", g["label"]) for g in fatigue_bar_groups]
    colors = FATIGUE_BAR_COLORS[: len(labels)]
    x = np.arange(len(labels))

    fig, (ax_rt, ax_se) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)

    def draw_panel(ax, metric_key, title, ylabel):
        values = [g[metric_key] for g in fatigue_bar_groups]
        heights = [v if v is not None else 0.0 for v in values]
        sns.barplot(x=short_labels, y=heights, hue=short_labels, palette=colors,
                    order=short_labels, hue_order=short_labels, dodge=False,
                    legend=False, edgecolor="black", linewidth=0.6, width=0.6, ax=ax)
        bars = ax.patches
        ylim_span = FATIGUE_YLIM[1] - FATIGUE_YLIM[0]
        label_offset = 0.06 * ylim_span
        for xi, v, bar in zip(x, values, bars):
            text = "N/A" if v is None else "%.2f" % v
            bar_height = bar.get_height()
            y_pos = bar_height + label_offset if bar_height >= 0 else bar_height - label_offset
            va = "bottom" if bar_height >= 0 else "top"
            ax.text(xi, y_pos, text, ha="center", va=va, fontsize=9)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_ylim(*FATIGUE_YLIM)
        ax.set_xticks(x)
        ax.set_xticklabels(short_labels)
        plt.sca(ax)
        plt.xticks(rotation=15, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.4, alpha=0.35)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        legend_handles = [Patch(facecolor=colors[i], edgecolor="black", label=labels[i])
                           for i in range(len(labels))]
        ax.legend(handles=legend_handles, frameon=False, fontsize=8, loc="best")

    draw_panel(ax_rt, "rt_change_mean",
               "Fatigue: Speed ('Raw Score HitRTBlock')",
               "Mean HitRTBlock Slope (RT)")
    draw_panel(ax_se, "se_change_mean",
               "Fatigue: Stability ('Raw Score HitSEBlock')",
               "Mean HitSEBlock Slope (SE)")

    fig.suptitle("HYPERAKTIV: Fatigue Dynamics (Block Change) by Subtype", fontsize=12)
    fig.text(0.5, 0.02,
             "Positive value = fatigue toward the end of the test; near zero = pace maintained",
             ha="center", fontsize=9)

    plt.subplots_adjust(bottom=0.25, wspace=0.3)

    plot_path = os.path.join(get_writable_dir(), output_name)
    fig.savefig(plot_path, dpi=150)
    log("Chart saved: %s" % plot_path)

    try:
        plt.show()
    except Exception:
        pass
    finally:
        plt.close(fig)

    return plot_path

def run_validation():
    log("=" * 70)
    log("HYPERAKTIV Validator -- matching real patients against hypotheses")
    log("=" * 70)

    found_columns = {}
    real_df, fatigue_cols, confound_cols_present = load_real_patients(found_columns)
    hypotheses = load_hypothesis_points()

    if not hypotheses:
        raise RuntimeError("No hypothesis clusters were loaded -- check HYPOTHESIS_ANCHOR_POINTS.")

    log("\nCURRENT OUTLIER MITIGATION MODE: %s" % EXCLUSION_MODE)

    technical_invalid_summary = None

    if EXCLUSION_MODE in ("none", "clinical_cutoff"):
        if NOISE_CLUSTER_KEY in hypotheses:
            del hypotheses[NOISE_CLUSTER_KEY]
            log("EXCLUSION_MODE=%r -- dropped hypothesis cluster '%s' before Z-scaling/centroids; "
                "real patients will be force-distributed across the remaining clusters (%s)." % (
                    EXCLUSION_MODE, NOISE_CLUSTER_KEY, ", ".join(hypotheses.keys())))

    if EXCLUSION_MODE == "clinical_cutoff":
        rt_mean_numeric = pd.to_numeric(real_df["rt_mean"], errors="coerce")
        invalid_mask = rt_mean_numeric < CLINICAL_CUTOFF_RT_MEAN
        technical_invalid_df = real_df[invalid_mask].copy()
        real_df = real_df[~invalid_mask].copy()

        n_invalid = len(technical_invalid_df)
        n_invalid_adhd = int(technical_invalid_df["is_adhd"].sum()) if n_invalid else 0
        n_invalid_ctrl = n_invalid - n_invalid_adhd
        technical_invalid_summary = {
            "label": TECHNICAL_INVALID_LABEL,
            "cutoff": CLINICAL_CUTOFF_RT_MEAN,
            "n_total": n_invalid,
            "n_adhd": n_invalid_adhd,
            "n_control": n_invalid_ctrl,
        }
        log("EXCLUSION_MODE='clinical_cutoff' -- excluded %d participant(s) with rt_mean < %.1f as "
            "'%s' (ADHD=%d, control=%d). These are reported separately and are not part of the main "
            "cluster analysis, charts, or downstream statistics." % (
                n_invalid, CLINICAL_CUTOFF_RT_MEAN, TECHNICAL_INVALID_LABEL, n_invalid_adhd, n_invalid_ctrl))

    real_vecs = real_df[["rt_mean", "rt_std", "accuracy_pct"]].to_numpy(dtype=float)
    mu, sigma = standardize(list(hypotheses.values()) + [real_vecs])

    def z(v):
        return (v - mu) / sigma

    centroids = {name: z(pts).mean(axis=0) for name, pts in hypotheses.items()}
    real_z = z(real_vecs)

    cluster_names = list(centroids.keys())
    dists = np.vstack([
        np.linalg.norm(real_z - centroids[name], axis=1) for name in cluster_names
    ]).T
    nearest_idx = dists.argmin(axis=1)
    real_df = real_df.copy()
    real_df["nearest_cluster"] = [cluster_names[i] for i in nearest_idx]

    cluster_table = {}
    for label, flag in (("ADHD", True), ("Clinical Control", False)):
        sub = real_df[real_df["is_adhd"] == flag]
        n = len(sub)
        row = {}
        for name in cluster_names:
            row[name] = (100.0 * (sub["nearest_cluster"] == name).sum() / n) if n else 0.0
        cluster_table["%s (n=%d)" % (label, n)] = row

    log("\n===== DISTRIBUTION ACROSS HYPOTHESIS CLUSTERS =====")
    for group_label, row in cluster_table.items():
        log("\n%s:" % group_label)
        for name, pct in row.items():
            log("  -> nearest to '%s': %.1f%%" % (CLUSTER_DISPLAY_LABELS.get(name, name), pct))

    subtype_stats = {}
    log("\n===== ADHD SUBTYPES (renamed clusters) =====")
    for cluster_key, label in SUBTYPE_LABELS.items():
        if cluster_key not in cluster_names:
            log("Cluster '%s' (%s) is missing from the loaded hypotheses." % (cluster_key, label))
            continue
        cluster_sub = real_df[real_df["nearest_cluster"] == cluster_key]
        rows = []
        log("\n%s (cluster '%s'):" % (label, cluster_key))
        for row_label, flag in (("Clinical Control", False), ("ADHD", True)):
            sub = cluster_sub[cluster_sub["is_adhd"] == flag]
            n = len(sub)
            mean_pc = None
            if n > 0 and sub["percent_commissions"].notna().any():
                mean_pc = float(sub["percent_commissions"].mean())
            mean_acc = None
            if n > 0 and sub["accuracy_pct"].notna().any():
                mean_acc = float(sub["accuracy_pct"].mean())
            rows.append((row_label, n, mean_pc, mean_acc))
            if n == 0:
                log("  %s: no participants (n=0)" % row_label)
            elif mean_pc is None:
                log("  %s: n=%d, Percent Commissions unavailable" % (row_label, n))
            else:
                acc_part = (", mean True Accuracy = %.1f%%" % mean_acc) if mean_acc is not None else ""
                log("  %s: n=%d, mean Percent Commissions = %.1f%%%s" % (row_label, n, mean_pc, acc_part))
        subtype_stats[cluster_key] = rows

    log("\n===== FATIGUE ANALYSIS: BLOCK CHANGE (fatigue curve slope) =====")
    fatigue_profiles = build_fatigue_profiles(real_df, fatigue_cols)
    for cluster_key, profile in fatigue_profiles.items():
        rt_str = "%.2f" % profile["rt_change_mean"] if profile["rt_change_mean"] is not None else "N/A"
        se_str = "%.2f" % profile["se_change_mean"] if profile["se_change_mean"] is not None else "N/A"
        log("%s: n=%d, HitRTBlock=%s, HitSEBlock=%s" % (
            profile["label"], profile["n"], rt_str, se_str))

    log("\n===== STATISTICS: MANN-WHITNEY U BY CLUSTER =====")
    mannwhitney_results, bonferroni_alpha = run_mannwhitney_by_cluster(real_df, cluster_names)

    log("\n===== CONFOUNDER CHECK (age/sex/medication) =====")
    confound_summary = build_confounder_summary(real_df, confound_cols_present)
    for cluster_key, entry in confound_summary.items():
        log("%s (n=%d):" % (entry["label"], entry["n"]))
        if not entry["fields"]:
            log("  no confounder data")
        for field_name, field_stats in entry["fields"].items():
            log("  " + format_confounder_field(field_name, field_stats).strip())

    real_analytical_p = None
    for res in mannwhitney_results:
        if res["cluster"] == PERMUTATION_TARGET_CLUSTER and res["p_value"] is not None:
            real_analytical_p = res["p_value"]
            break
    if real_analytical_p is None:
        real_analytical_p = PERMUTATION_REAL_P_VALUE

    permutation_result = None
    if PERMUTATION_TARGET_CLUSTER in cluster_names:
        permutation_result = run_permutation_test(
            real_df, real_z, centroids, cluster_names,
            target_cluster=PERMUTATION_TARGET_CLUSTER,
            metric_col=PERMUTATION_TARGET_METRIC,
            real_p_value=real_analytical_p,
            n_permutations=N_PERMUTATIONS,
        )

    report_path = os.path.join(get_writable_dir(), CLEAN_REPORT_NAME)
    write_clean_report(found_columns, cluster_table, subtype_stats, mannwhitney_results,
                        bonferroni_alpha, fatigue_profiles, confound_summary, report_path,
                        permutation_result=permutation_result,
                        exclusion_mode=EXCLUSION_MODE,
                        technical_invalid_summary=technical_invalid_summary)
    log("\nClean report saved: %s" % report_path)

    log("Building charts...")
    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "legend.fontsize": 8,
    })

    build_scatter_plot(
        real_df, hypotheses, color_col="accuracy_pct", cmap="RdYlGn",
        title="HYPERAKTIV: True Accuracy of Test Performance by Subtype",
        cbar_label="True Accuracy, %",
        output_name=ACCURACY_PLOT_NAME,
    )

    build_scatter_plot(
        real_df, hypotheses, color_col="percent_commissions", cmap="YlOrRd",
        title="HYPERAKTIV: Impulsivity (Percent Commissions) by Subtype",
        cbar_label="Percent Commissions, % (Impulsivity)",
        output_name=IMPULSIVITY_PLOT_NAME,
    )

    fatigue_bar_groups = compute_fatigue_bar_groups(real_df, fatigue_cols)
    build_fatigue_dynamics_plot(fatigue_bar_groups, FATIGUE_DYNAMICS_PLOT_NAME)

def main():
    try:
        run_validation()
        log("\nDone. Script completed successfully.")
    except Exception as e:
        tb_text = traceback.format_exc()
        log("\n" + "!" * 70)
        log("ERROR: %s" % e)
        log(tb_text)
        log("!" * 70)
        try:
            crash_path = os.path.join(get_writable_dir(), CRASH_LOG_NAME)
            with open(crash_path, "w", encoding="utf-8") as f:
                f.write("HYPERAKTIV Validator crash log (full console history)\n")
                f.write("=" * 40 + "\n")
                f.write("\n".join(LOG_BUFFER))
                f.write("\n\n" + "=" * 40 + "\nTRACEBACK:\n")
                f.write(tb_text)
            log("Full log + traceback written to: %s" % crash_path)
        except Exception as e2:
            log("Failed to even write crash_log.txt: %s" % e2)

if __name__ == "__main__":
    main()
    input("\nExecution finished. Press ENTER to close the terminal...")
