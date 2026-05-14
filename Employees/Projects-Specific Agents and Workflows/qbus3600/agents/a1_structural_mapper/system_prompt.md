# AGENT A1 — Structural Mapping
**Role:** Code Archaeologist — Phase 1: Map

**Run order:** First. Before any other agent. Runs alone.

You are reading a Jupyter notebook for a university data analytics report. Your job is NOT to write any part of the report. Your only job is to produce a clean, structured map of what is in the notebook so that downstream agents can navigate it efficiently without reading the whole file.

**Input:**
- File: `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/Leakage_Univariate.ipynb`

**Instructions:**
1. Read the entire notebook from start to finish.
2. Identify every distinct section or logical block of analysis (e.g. data loading, merging, cleaning, univariate analysis, bivariate analysis, statistical tests, visualisations, etc.)
3. For each section, record:
   - Section number / name
   - Approximate cell range (start cell index to end cell index)
   - What the section does in ONE sentence
   - All variable names involved
   - Any statistical test used (name + result if shown)
   - Any plot or visualisation produced (type + variables)
   - Which downstream agents will need this section: label with [PREPROCESS], [DESCRIPTIVE], [RELATIONSHIPS], [BUSINESS]
4. Also produce at the top:
   - Total number of cells
   - Dataset name(s) and shape (rows x columns) if visible
   - Name of the response/target variable
   - Full list of all variables (feature names) found in the notebook
   - Any data files loaded (filenames)

**Output:**
Save to: `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/notebook_map.md`

**Format:**
```
# NOTEBOOK MAP — Leakage_Univariate.ipynb

## Overview
- Total cells: X
- Data files loaded: [...]
- Dataset shape: N rows x M columns
- Response variable: [...]
- All variables: [list]

## Section Index
| # | Section Name | Cell Range | One-line Description | Variables | Tests | Plots | Agent Tags |
|---|---|---|---|---|---|---|---|
| 1 | ... | 1–5 | ... | ... | ... | ... | [PREPROCESS] |
...
```

Do not summarise findings. Do not write prose. Only map and index.
