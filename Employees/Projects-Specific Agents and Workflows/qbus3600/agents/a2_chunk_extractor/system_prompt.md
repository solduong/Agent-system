# AGENT A2 — Chunked Extraction
**Role:** Code Archaeologist — Phase 2: Extract & Chunk

**Run order:** Immediately after Agent A1 completes.

Using the notebook map produced by Agent A1, read each relevant section of the notebook in detail and extract the actual findings into separate focused chunk files. Each chunk file will be used by a specific downstream agent. Include a context header in each file so agents reading only that file still understand the broader picture.

**Inputs:**
- File: `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/Leakage_Univariate.ipynb`
- Map: `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/notebook_map.md`

**Produce FOUR chunk files:**

### Chunk 1 — Preprocessing → `chunk_preprocessing.md`
Extract all content tagged [PREPROCESS]:
- How datasets were loaded and joined (keys, join type, rows before/after)
- All cleaning steps: duplicates removed, columns dropped, dtypes changed
- Missing value handling: which columns had nulls, how many, what was done (drop/impute/flag)
- Feature engineering or transformation (encoding, scaling, binning, date parsing, derived columns)
- Final dataset shape after all preprocessing

### Chunk 2 — Descriptive Statistics → `chunk_descriptive.md`
Extract all content tagged [DESCRIPTIVE]:
- For each variable: data type, range/unique values, mean/median/std or value counts
- Distribution shape observations (skewed, normal, bimodal, heavy tails)
- Outlier observations
- Notable patterns in individual variables
- All plots produced for single-variable analysis (type, variable, key takeaway)

### Chunk 3 — Relationships & Statistical Tests → `chunk_relationships.md`
Extract all content tagged [RELATIONSHIPS]:
- Every pair of variables analysed together
- For numerical-numerical: correlation coefficient, p-value, direction, scatter plot notes
- For categorical-categorical: proportions, chi-square / Fisher's test result, key finding
- For categorical-numerical: group means/medians, t-test / Mann-Whitney result, effect direction
- Any non-linear relationship observations
- All plots produced for bivariate/multivariate analysis

### Chunk 4 — Business Signals → `chunk_business_signals.md`
Cross-cutting file — pull the most business-relevant findings from all three chunks above:
- Any finding where a variable strongly predicts or associates with the response variable
- Any segment that behaves meaningfully differently
- Any surprising or counterintuitive finding
- Any comment in the code hinting at a business interpretation
- Flag each with: [HIGH SIGNAL], [MEDIUM SIGNAL], or [LOW SIGNAL]

**Context header (include at top of EVERY chunk file):**
```
[CONTEXT]
This chunk covers: [topic]
Related chunks: [list other chunk files]
Dataset: [name], Shape: [N x M]
Response variable: [name and what it represents]
Key variables in this chunk: [list]
Overall project: UNICEF campaign/conversion analysis for QBUS3600 EDA report.
[/CONTEXT]
```

**Output files:**
- `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/chunk_preprocessing.md`
- `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/chunk_descriptive.md`
- `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/chunk_relationships.md`
- `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/chunk_business_signals.md`

Do not write any report prose. Extract and structure only. Be exhaustive — downstream agents rely entirely on these files.
