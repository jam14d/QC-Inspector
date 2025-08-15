#!/usr/bin/env python3
import pandas as pd, numpy as np
from pathlib import Path
from typing import Optional, Dict, Any

#  Hardcoded path to your results 
TSV_PATH = Path("/Volumes/PALETAS/data/histoqc_output_20250814215448/results.tsv")
CSV_PATH = TSV_PATH.with_name("qc_output.csv")

#  Helpers 
def read_histoqc_tsv(path: Path) > pd.DataFrame:
    """Read a HistoQC results.tsv that has a '#dataset:' header line."""
    header_cols = None
    with open(path, "r", errors="replace") as f:
        for line in f:
            if line.startswith("#dataset:"):
                header_cols = [c.strip() for c in line.lstrip("#").strip().split("\t")]
                break
    if header_cols is None:
        raise RuntimeError("Couldn't find header line that starts with #dataset:.")
    df = pd.read_csv(path, sep="\t", comment="#", header=None, names=header_cols)
    return df

def to_num(series: pd.Series) > pd.Series:
    return pd.to_numeric(series, errors="coerce")

def iqr_hi(series: pd.Series, drop_below: Optional[float] = None) > float:
    x = series.dropna()
    if drop_below is not None:
        x = x[x > drop_below]
    if len(x) == 0:
        return float("nan")
    q1, q3 = np.percentile(x, [25, 75])
    return float(q3 + 1.5 * (q3  q1))

def iqr_lo(series: pd.Series, drop_below: Optional[float] = None) > float:
    x = series.dropna()
    if drop_below is not None:
        x = x[x > drop_below]
    if len(x) == 0:
        return float("nan")
    q1, q3 = np.percentile(x, [25, 75])
    return float(q1  1.5 * (q3  q1))

def present(df: pd.DataFrame, col: str) > bool:
    return col in df.columns

#  Artifact logic 
def compute_thresholds(df: pd.DataFrame) > Dict[str, Any]:
    """Derive datadriven thresholds w/ sane floors for robustness."""
    thr: Dict[str, Any] = {}

    # Blur (two signals): high blur %, low sharpness/contrast
    if present(df, "blurry_removed_percent"):
        s = to_num(df["blurry_removed_percent"])
        thr["blur_pct_hi"] = max(0.5, iqr_hi(s))  # at least 50% blurred area
    if present(df, "tenenGrad_contrast"):
        s = to_num(df["tenenGrad_contrast"])
        lo = iqr_lo(s, drop_below=50)  # drop sentinel 100s
        thr["tenen_lo"] = 0.0 if (np.isnan(lo) or lo < 0) else float(lo)
    if present(df, "michelson_contrast"):
        s = to_num(df["michelson_contrast"])
        lo = iqr_lo(s, drop_below=50)
        thr["michelson_lo"] = max(0.02, 0.0 if np.isnan(lo) else float(lo))
    if present(df, "rms_contrast"):
        s = to_num(df["rms_contrast"])
        lo = iqr_lo(s, drop_below=50)
        thr["rms_lo"] = max(0.02, 0.0 if np.isnan(lo) else float(lo))

    # Bubbles
    if present(df, "flat_areas"):
        s = to_num(df["flat_areas"])
        thr["flat_hi"] = max(0.005, iqr_hi(s))  # >= 0.5% area by default

    # Folds / spurs
    if present(df, "spur_pixels"):
        s = to_num(df["spur_pixels"])
        hi = iqr_hi(s[s >= 0])  # ignore sentinel negatives
        thr["spur_hi"] = max(0.30, 0.0 if np.isnan(hi) else float(hi))  # at least 30%

    # Notissue safeguard (nonwhite & brightness hints)
    if present(df, "nonwhite"):
        thr["nonwhite_hi"] = 0.90  # used for paletissue override
    if present(df, "grayscale_brightness"):
        thr["bright_hi"] = 0.60

    return thr

def looks_like_pale_tissue(row: pd.Series, thr: Dict[str, Any]) > bool:
    nonwhite_ok = float(row.get("nonwhite", 0) or 0) >= thr.get("nonwhite_hi", 0.90)
    bright_ok = (row.get("grayscale_brightness") is None) or \
                (float(row.get("grayscale_brightness") or 0) >= thr.get("bright_hi", 0.60))
    return nonwhite_ok and bright_ok

def is_low_contrast(row: pd.Series, thr: Dict[str, Any]) > bool:
    mic_ok = ("michelson_lo" in thr) and (float(row.get("michelson_contrast", 1) or 1) <= thr["michelson_lo"])
    rms_ok = ("rms_lo" in thr) and (float(row.get("rms_contrast", 1) or 1) <= thr["rms_lo"])
    ten_ok = ("tenen_lo" in thr) and (float(row.get("tenenGrad_contrast", 1) or 1) <= thr["tenen_lo"])
    # Any of these indicate low sharpness/contrast
    return mic_ok or rms_ok or ten_ok

def analyze(df: pd.DataFrame) > pd.DataFrame:
    fn_col = "dataset:filename"
    thr = compute_thresholds(df)

    out_rows = []
    for _, r in df.iterrows():
        reasons = []

        # No tissue?
        pixels_to_use = float(r.get("pixels_to_use", np.nan)) if pd.notna(r.get("pixels_to_use", np.nan)) else np.nan
        warnings = str(r.get("warnings", "") or "")
        no_tissue_flag = (pd.notna(pixels_to_use) and pixels_to_use <= 0) or ("NO tissue" in warnings)

        if no_tissue_flag and not looks_like_pale_tissue(r, thr):
            reasons.append("no_tissue_detected")
        elif no_tissue_flag and looks_like_pale_tissue(r, thr):
            reasons.append("tissue_mask_missed_pale_tissue")

        # Blur (strict): requires high blur % OR very low Tenengrad,
        # AND at least one lowcontrast signal (Michelson/RMS/Tenengrad)
        blur_hit = False
        if "blur_pct_hi" in thr and pd.notna(r.get("blurry_removed_percent")):
            try:
                blur_hit = blur_hit or float(r["blurry_removed_percent"]) >= thr["blur_pct_hi"]
            except Exception:
                pass
        if "tenen_lo" in thr and pd.notna(r.get("tenenGrad_contrast")):
            try:
                blur_hit = blur_hit or float(r["tenenGrad_contrast"]) <= thr["tenen_lo"]
            except Exception:
                pass
        if blur_hit and is_low_contrast(r, thr):
            reasons.append("blur")

        # Bubbles: large flat areas
        if "flat_hi" in thr and pd.notna(r.get("flat_areas")):
            try:
                if float(r["flat_areas"]) >= thr["flat_hi"]:
                    reasons.append("bubble")
            except Exception:
                pass

        # Folds/spurs
        if "spur_hi" in thr and pd.notna(r.get("spur_pixels")):
            try:
                sp = float(r["spur_pixels"])
                # Ignore sentinel negatives
                if sp >= 0 and sp >= thr["spur_hi"]:
                    reasons.append("fold")
            except Exception:
                pass

        status = "FAIL" if reasons else "PASS"
        out_rows.append({
            "image": r.get(fn_col, ""),
            "status": status,
            "reasons": "; ".join(sorted(set(reasons))),
            # key metrics for transparency (only add if present)
            "blurry_removed_percent": r.get("blurry_removed_percent", np.nan),
            "tenenGrad_contrast": r.get("tenenGrad_contrast", np.nan),
            "michelson_contrast": r.get("michelson_contrast", np.nan),
            "rms_contrast": r.get("rms_contrast", np.nan),
            "flat_areas": r.get("flat_areas", np.nan),
            "spur_pixels": r.get("spur_pixels", np.nan),
            "nonwhite": r.get("nonwhite", np.nan),
            "pixels_to_use": r.get("pixels_to_use", np.nan),
            "warnings": r.get("warnings", ""),
        })

    out = pd.DataFrame(out_rows)
    # Only keep failures in the CSV (triage list)
    out[out["status"] == "FAIL"].to_csv(CSV_PATH, index=False)
    print("QC thresholds used:")
    for k, v in compute_thresholds(df).items():
        print(f"  {k}: {v}")
    print(f"\nWrote: {CSV_PATH}  (rows: {len(out[out['status']=='FAIL'])})")
    return out

#  Run 
if __name__ == "__main__":
    df = read_histoqc_tsv(TSV_PATH)
    # Numeric coercion for likely numeric fields (robust to missing cols)
    numeric_candidates = [
        "blurry_removed_percent","tenenGrad_contrast",
        "michelson_contrast","rms_contrast",
        "flat_areas","spur_pixels","pixels_to_use",
        "nonwhite","grayscale_brightness"
    ]
    for c in numeric_candidates:
        if c in df.columns:
            df[c] = to_num(df[c])
    analyze(df)
