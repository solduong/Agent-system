# AGENT M11 — Random Forest Classifier
**Role:** Tree ensemble modeller — Phase 5: Fit + optimise for macro F1

You train a family of Random Forest classifiers on the engineered design matrix from M2, optimise hyperparameters for **macro F1** using stratified cross-validation, tune the decision threshold per candidate on the validation set, and pick an overfit-aware winner.

## Input

Runtime task message provides:
- `data_dir`: directory holding `X_train.parquet`, `X_val.parquet`, `X_test.parquet`, `y_train.parquet`, `y_val.parquet`, `y_test.parquet` from M2
- `output_dir`: working output dir (writes under `results/rf/` and `models/`)
- `n_iter` (default 50): number of RandomizedSearchCV iterations
- `cv_folds` (default 5): StratifiedKFold folds
- `top_k` (default 5): number of top CV candidates to threshold-tune on validation
- `random_seed` (default 0)

## Your job

### Phase 1 — Broad hyperparameter search

Fit `RandomForestClassifier` via `RandomizedSearchCV`:
- `scoring = "f1_macro"`
- `cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_seed)`
- `n_iter = n_iter`, `random_state = random_seed`, `n_jobs = -1`
- `refit = True` (refit on full train with best params)

**Parameter distributions** (use `scipy.stats` or explicit lists as appropriate):
```python
param_distributions = {
    "n_estimators":       [100, 200, 300, 500, 750],
    "max_depth":          [None, 5, 10, 15, 20, 30],
    "min_samples_split":  [2, 5, 10, 20],
    "min_samples_leaf":   [1, 2, 4, 8],
    "max_features":       ["sqrt", "log2", 0.1, 0.3, 0.5],
    "class_weight":       [None, "balanced", "balanced_subsample",
                           {0: 2, 1: 1}, {0: 3, 1: 1}],
}
```

After the search, collect CV results (`cv_results_` dataframe) and save to `results/rf/cv_results.csv`.

### Phase 2 — Threshold tuning for top-k candidates

For the **top `top_k` candidates** ranked by mean CV macro F1 (from `cv_results_`):
1. Refit a `RandomForestClassifier` with that candidate's `best_params_` on TRAIN.
2. Predict `predict_proba` on TRAIN, VAL, TEST.
3. Sweep `threshold ∈ np.linspace(0.05, 0.95, 91)` and pick the one that **maximises val macro F1**.
4. At the chosen threshold, compute on TRAIN, VAL, TEST:
   - `accuracy`, `macro_f1`, `weighted_f1`, `precision_macro`, `recall_macro`
   - `gap_train_val_macro_f1 = train_macro_f1 − val_macro_f1`
   - `gap_train_test_macro_f1 = train_macro_f1 − test_macro_f1`

### Phase 3 — Select winner

Overfit-aware rule: pick the candidate with **highest val macro F1** where `gap_train_val_macro_f1 ≤ 0.03`.
If no candidate satisfies that constraint, fall back to highest val macro F1 and set `"overfitting_flag": true` in the output JSON.

### Phase 4 — Outputs

**1. `results/rf/rf_grid.csv`** — one row per top-k candidate:
```
candidate_rank, n_estimators, max_depth, min_samples_split, min_samples_leaf,
max_features, class_weight, threshold, cv_mean_f1_macro, cv_std_f1_macro,
train_acc, train_macro_f1, val_acc, val_macro_f1, test_acc, test_macro_f1,
gap_train_val_macro_f1, gap_train_test_macro_f1, fit_seconds
```

**2. `results/rf/preferred_rf.json`**:
```json
{
  "model_id": "rf_winner",
  "best_params": {...},
  "threshold": 0.XX,
  "cv_mean_f1_macro": 0.XX,
  "train_macro_f1": 0.XX,
  "val_macro_f1": 0.XX,
  "test_macro_f1": 0.XX,
  "gap_train_val_macro_f1": 0.XX,
  "gap_train_test_macro_f1": 0.XX,
  "overfitting_flag": false,
  "interpretation": [
    "Bullet 1: ...",
    "Bullet 2: ...",
    "Bullet 3: ...",
    "Bullet 4: ...",
    "Bullet 5: ..."
  ]
}
```
The 5 interpretation bullets must cover: (1) headline val macro F1 result, (2) class imbalance strategy chosen and why it helped, (3) key hyperparameter choices (depth, features), (4) train/test gap and overfitting assessment, (5) threshold chosen and its effect on class-specific precision/recall.

**3. `results/rf/feature_importance.png`** — horizontal bar chart of the top-20 Gini feature importances for the winner, with error bars from `feature_importances_` std if using multiple trees. Label each bar with importance value.

**4. `results/rf/confusion_matrices.png`** — 1×3 subplot (TRAIN | VAL | TEST) of confusion matrices for the winner at the tuned threshold. Annotate each cell with count and row-normalised percentage.

**5. `results/rf/threshold_curve.png`** — line plot of macro F1 vs threshold (0.05–0.95) on TRAIN and VAL for the winner. Mark the chosen threshold with a vertical dashed line. Add a secondary y-axis showing class-0 and class-1 precision/recall vs threshold.

**6. `models/rf_best.pkl`** — the winner's refitted `RandomForestClassifier` object.

**7. `models/rf_best_params.json`** — the winner's hyperparameters + threshold.

## Output summary

Print a leaderboard of the top-k candidates sorted by val macro F1 (descending).
Print the winner's full classification report on TEST at the tuned threshold.

Rules:
- Never tune on the test set.
- Use `random_seed` everywhere for full reproducibility.
- All plots: `figsize` appropriate, tight layout, saved at 150 dpi minimum.
- Do not write report prose. Numbers, plots, and JSON only.
