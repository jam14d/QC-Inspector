# HistoQC Setup, Usage, and QC Triage

This guide documents my process for setting up and running HistoQC, including memory/configuration notes and my QC triage script for post-analysis filtering.  

It uses Docker for reproducibility but can be adapted for other environments.

---

## Helpful Links

- [HistoQC Documentation](https://github.com/choosehappy/HistoQC/wiki)  
- [HistoQC Paper (Janowczyk et al.)](https://andrewjanowczyk.com/wp-content/uploads/2019/04/HistoQC_w_supplemental.pdf)

---

## One-Time Setup (First-Time Only)

Run this once to create the container:

```bash
docker run -v /path/to/local/data:/data \
  --name my_container -p 3000:5000 \
  -it histotools/histoqc:master /bin/bash

# Example with external volume
docker run -v /mnt/external_drive/data:/data \
  --name my_container -p 3000:5000 \
  -it histotools/histoqc:master /bin/bash
```

**Flags explained:**
- `-v /path/to/local/data:/data` → Mounts local data folder into `/data` inside the container  
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
# Across multiple directories
python -m histoqc --config /data/default.ini -n 1 */*.mrxs

# Full recursive search
python -m histoqc --config /data/default.ini -n 1 $(find /data -type f -iname "*.mrxs")
```

**Tips:**
- `-n N` → Number of CPU cores (use as high as stable for your system; default `1` for reliability)  
- Outputs are stored in timestamped folders:
  ```
  /path/to/local/data/histoqc_output_YYYYMMDD-HHMMSS/results.tsv
  ```

---

### 3. Launch Web Viewer (Optional)

Inside the container:

```bash
python -m histoqc.ui /data/histoqc_output_YYYYMMDD-HHMMSS/results.tsv
```

Then visit [http://localhost:3000](http://localhost:3000/) in your browser.

---

## Input/Output Paths

- **Host machine:** `/path/to/local/data`  
- **Inside container:** `/data`  

HistoQC will skip already processed images if re-run in the same output folder.

---

## Memory & Config Notes

These example results illustrate memory tuning for large datasets:

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
- Consistent run command: `-n 1`.  

**Back-up Plan:**  
If memory becomes limiting:
1. Create a lightweight config with:
   - Blur detection  
   - Dark speck detection  
   - Bubble detection  
2. Or run on cloud resources (e.g., AWS) with higher RAM allocation.  

---

## QC Triage Script

A helper script `qc_triage.py` can be used after running HistoQC to filter slides based on blur, bubble, and dark speck thresholds.

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
INPUT_PATH = "/path/to/local/data/histoqc_output_YYYYMMDD-HHMMSS/results.tsv"
OUTPUT_PATH = "qc_results.csv"
```

Example output:
```csv
filename,qc_flag,qc_reason
slide1.mrxs,pass,none
slide2.mrxs,warn,blur
slide3.mrxs,fail, blur, dark speck, bubble
```

---

## Final Notes
- This workflow is tuned for common use cases and may need adjustment for specific datasets.  
- Memory, config, and thresholds should be balanced for speed, accuracy, and system stability.  
- The QC triage step is essential for automated downstream filtering.  
