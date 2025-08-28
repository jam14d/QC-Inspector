#!/usr/bin/env python3
"""
qc_triage.py

QC triage for HistoQC results.tsv focusing on:
  - blur (blurry_removed_percent)
  - bubble (flat_areas)
  - dark speck (dark)

Outputs CSV with only:
  filename, qc_flag, qc_reason


Run via:
python qc_triage.py /path/to/results.tsv

"""

import argparse
import os
import pandas as pd

#  Column names 
COL_FILENAME = "filename"
COL_BLUR = "blurry_removed_percent"
COL_BUBBLE = "flat_areas"
COL_DARK = "dark"

#  Thresholds 
BLUR_WARN = 0.0035   # 0.35%
BLUR_FAIL = 0.015    # 1.5%

BUBBLE_WARN = 0.0005 # 0.05%
BUBBLE_FAIL = 0.0010 # 0.10%

DARK_WARN = 0.0005   # 0.05%
DARK_FAIL = 0.0020   # 0.20%

def read_histoqc_tsv(path: str) -> pd.DataFrame:
    """Reads HistoQC results.tsv, handling '#dataset:' headers."""
    header_cols = None
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if line.startswith("#dataset:"):
                header_cols = line.strip()[len("#dataset:"):].split("\t")
                break

    if header_cols is None:
        df = pd.read_csv(path, sep="\t")
    else:
        df = pd.read_csv(path, sep="\t", comment="#", header=None, names=header_cols)

    missing = [c for c in [COL_FILENAME, COL_BLUR, COL_BUBBLE, COL_DARK] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns in TSV: {missing}")
    return df


def apply_qc_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Returns DataFrame with filename, qc_flag, qc_reason."""
    rows = []

    for _, row in df.iterrows():
        blur = float(row.get(COL_BLUR, 0) or 0)
        bubble = float(row.get(COL_BUBBLE, 0) or 0)
        dark = float(row.get(COL_DARK, 0) or 0)

        blur_level = "fail" if blur >= BLUR_FAIL else ("warn" if blur >= BLUR_WARN else "pass")
        bubble_level = "fail" if bubble >= BUBBLE_FAIL else ("warn" if bubble >= BUBBLE_WARN else "pass")
        dark_level = "fail" if dark >= DARK_FAIL else ("warn" if dark >= DARK_WARN else "pass")

        if blur_level == "fail" or bubble_level == "fail":
            qc_flag = "fail"
        elif blur_level == "warn" or bubble_level == "warn" or dark_level == "fail":
            qc_flag = "warn"
        else:
            qc_flag = "pass"

        offender_list = []
        if blur_level in ("warn", "fail"):
            offender_list.append("blur")
        if bubble_level in ("warn", "fail"):
            offender_list.append("bubble")
        if dark_level in ("warn", "fail"):
            offender_list.append("dark speck")

        if len(offender_list) == 3:
            qc_reason = "all three"
        elif offender_list:
            qc_reason = ", ".join(offender_list)
        else:
            qc_reason = "none"

        rows.append({
            "filename": row[COL_FILENAME],
            "qc_flag": qc_flag,
            "qc_reason": qc_reason
        })

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="QC triage for HistoQC results.tsv")
    parser.add_argument("input_path", help="Path to HistoQC results.tsv file")
    args = parser.parse_args()

    input_path = args.input_path
    output_path = os.path.join(os.path.dirname(input_path), "qc_results.csv")

    df = read_histoqc_tsv(input_path)
    result_df = apply_qc_flags(df)
    result_df.to_csv(output_path, index=False)

    summary = result_df["qc_flag"].value_counts(dropna=False)
    print("QC Summary:")
    for k in ["fail", "warn", "pass"]:
        if k in summary:
            print(f"  {k}: {summary[k]}")
    print(f"\nWrote: {output_path}")


if __name__ == "__main__":
    main()


