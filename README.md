# HistoQC Setup, Usage, and QC Triage

This guide documents my personal process for setting up and running [HistoQC](https://github.com/choosehappy/HistoQC/wiki), including my optimal memory/config choices for my datasets, and a QC triage script for post-analysis filtering.

It is tailored for my setup (Mac + Docker) but can be adapted for other environments.

---

## Helpful Links

- [HistoQC Documentation](https://github.com/choosehappy/HistoQC/wiki)  
- [HistoQC Paper (Janowczyk et al.)](https://andrewjanowczyk.com/wp-content/uploads/2019/04/HistoQC_w_supplemental.pdf)

---

## One-Time Setup (First-Time Only)

Run this once to create the container:

```bash
docker run -v /Users/jamieannemortel/Documents/data:/data \
  --name my_container -p 3000:5000 \
  -it histotools/histoqc:master /bin/bash

# Example for external volume
docker run -v /Volumes/PALETAS/data:/data \
  --name my_container -p 3000:5000 \
  -it histotools/histoqc:master /bin/bash
```

**Flags explained:**
- `-v /path/to/data:/data` → Mounts local data folder into `/data` inside the container
- `--name my_container` → Names the container for easy restart
- `-p 3000:5000` → Maps the HistoQC web UI to [http://localhost:3000](http://localhost:3000/)
- `-it ... /bin/bash` → Starts an interactive shell inside the container

---

## Daily Use: Running HistoQC

### 1. Start the Existing Container

```bash
docker start -i my_container
```

---

### 2. Run Analysis

Inside the container:

```bash

# Across multiple dirs
python -m histoqc --config /data/default.ini -n 1 */*.mrxs

# Full recursive find
python -m histoqc --config /data/default.ini -n 1 $(find /data -type f -iname "*.mrxs")
```

**Tips:**
- `-n N` → Number of CPU cores (use as high as stable for your system; I default to `1` for reliability)
- Outputs are stored in timestamped folders:
  ```
  /Volumes/PALETAS/data/histoqc_output_YYYYMMDD-HHMMSS/results.tsv
  ```

---

### 3. Launch Web Viewer (Optional -- it's just okay)

Inside the container:

```bash
python -m histoqc.ui /data/histoqc_output_YYYYMMDD-HHMMSS/results.tsv
```

Then visit [http://localhost:3000](http://localhost:3000/) in your browser.

---

## Input/Output Paths

- **Host machine:** `/Users/jamieannemortel/Documents/data`
- **Inside container:** `/data`

HistoQC will skip already processed images if you re-run in the same output folder.

---

## My Optimal Memory & Config Notes

I ran iterative tests to find a balance between accuracy and memory stability.

### Iteration 1 — Single Image
| Memory | Result |
|--------|--------|
| 8 GB   | Missed true positives |
| 16 GB  | Crashed mid-process |
| 18 GB  | Full tissue mask, stable, ~2.5 min/image |

**Tweaks:** Commented out `finalProcessingArea`, kept *Fill Small Holes* → better tissue coverage.

---

### Iteration 2 — Cohort
- Ran at **1.5× image working size** on 16 GB RAM without crashing.
- Processed multiple datasets (including RCR-H).
- Consistent run command: `-n 1`.

**Back-up Plan:**  
If memory becomes limiting:
1. Create a lightweight config with:
   - Blur detection
   - Dark speck detection
   - Bubble detection
2. Or run on AWS with higher RAM allocation.

---

## QC Triage Script

I use `qc_triage.py` after running HistoQC to filter slides based on blur, bubble, and dark speck thresholds.

### Features:
- Reads `results.tsv` (handles `#dataset:` headers)
- Applies thresholds (can edit sensitivity if needed):
  - Blur: Warn ≥ 0.35%, Fail ≥ 1.5%
  - Bubble: Warn ≥ 0.05%, Fail ≥ 0.10%
  - Dark speck: Warn ≥ 0.05%, Fail ≥ 0.20%
- Outputs: `filename, qc_flag, qc_reason`
- Prints pass/warn/fail summary

### Usage:

```bash
python qc_triage.py
```

**Hardcoded paths** — adjust inside the script:
```python
INPUT_PATH = "/Volumes/PALETAS/data/histoqc_output_YYYYMMDD-HHMMSS/results.tsv"
OUTPUT_PATH = "qc_results.csv"
```

Example output:
```csv
filename,qc_flag,qc_reason
slide1.mrxs,pass,none
slide2.mrxs,warn,blur
slide3.mrxs,fail,all three
```

---

## Final Notes
- This workflow is tuned for my datasets and may need adjustment for others.
- Memory, config, and thresholds were chosen to balance speed, accuracy, and system stability.
- The QC triage step is essential for automated downstream filtering.
