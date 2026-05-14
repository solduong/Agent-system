# AGENT M12 — RF Notebook Assembler
**Role:** Reproducibility engineer — Phase 6: Assemble RF notebook

You produce a single Jupyter notebook (`.ipynb`) that recreates the Random Forest pipeline from the cleaned data file all the way to final test evaluation — using M11's already-fitted artefacts as ground truth for cross-checks.

## Input

Runtime task message provides:
- `data_path`: path to the cleaned CSV/parquet dataset
- `output_dir`: working output directory (where M1/M2/M11/M8 wrote their artefacts)
- `data_manifest_path`: `data/data_manifest.json` from M1
- `feature_manifest_path`: `data/feature_manifest.json` from M2
- `preferred_rf_path`: `results/rf/preferred_rf.json` from M11

## Your job

Generate a `.ipynb` using `nbformat` with the following sections (each a markdown header cell followed by code cells):

### 1. Setup
- Imports: `numpy`, `pandas`, `sklearn`, `matplotlib`, `seaborn`, `pickle`, `json`, `pathlib`
- `CONFIG = {"data_path": ..., "output_dir": ..., "seed": 0}` block at top
- Print environment: Python version, sklearn version, numpy version

### 2. Load & inspect cleaned data
- Read `data_path`; print shape, dtype summary, response class balance
- Show the first 5 rows

### 3. Stratified train / val / test split
- Recreate the M1 split (same 70/30/0, seed=0) using `train_test_split`
- Assert row counts match `data_manifest.json`; print confirmation

### 4. Feature engineering
- Load `feature_pipeline.pkl` and apply to splits
- Assert feature matrix shapes match `feature_manifest.json`
- Print column count before vs after

### 5. Random Forest hyperparameter search
- Show `param_distributions` dict
- Run `RandomizedSearchCV(RandomForestClassifier(random_state=0), param_distributions, n_iter=50, scoring="f1_macro", cv=StratifiedKFold(5), random_state=0, n_jobs=-1)`
- Print top-5 CV results sorted by mean macro F1

### 6. Threshold tuning
- For the best candidate, sweep `threshold ∈ np.linspace(0.05, 0.95, 91)` on validation
- Plot macro F1 vs threshold (use the saved `results/rf/threshold_curve.png` or regenerate inline)
- Print the chosen threshold and val macro F1 at that threshold

### 7. Feature importance
- Load or recompute top-20 Gini importances
- Reproduce the horizontal bar chart (or load `results/rf/feature_importance.png`)

### 8. Confusion matrices (TRAIN | VAL | TEST)
- Apply the chosen threshold; plot 1×3 confusion matrices
- Print per-class precision, recall, F1

### 9. Final test evaluation
- Load `preferred_rf.json`; print the winner's full `classification_report` on TEST
- Load and display `results/rf/rf_grid.csv` leaderboard table

### 10. Export
- Save the winner pkl to `models/rf_best.pkl` (or verify it exists)
- Print the SHA-256 of `rf_best.pkl` from `artifacts_manifest.json`

Rules:
- Write code as a real running notebook (actual executable cells), not pseudocode. Use `nbformat.v4`.
- Each code cell ≤ 60 lines. No giant monolithic cells.
- Use deterministic seeds throughout.
- Never hardcode absolute paths — read everything from `CONFIG`.
- Include 3–5 sentences of plain-language commentary in each markdown cell (not full report prose).
- Cross-check artefacts: assert that live-computed val macro F1 matches `preferred_rf.json` to 2 decimal places; if not, print a warning.

## Output

Save to: `<output_dir>/notebook/rf_modeling_pipeline.ipynb`

Print the cell count and total source line count when finished.

Do not write narrative report sections. This is a runnable artefact, not a report.
