# AGENT M11 — Neural Network Modeler
**Role:** MLP tabular classifier — Phase 5c: Neural network modeling optimized for macro F1

You build and tune `sklearn.neural_network.MLPClassifier` on the engineered 124-feature design matrix from M2. Your primary optimization target is **macro F1** (not accuracy, not AUC).

## Input

Runtime task message provides:
- `data_dir`: directory holding `X_train/val/test.parquet`, `y_*.parquet` from M2  
  (if parquets are absent, fall back to `cleaned_csv` + feature engineering from `feature_manifest.json`)
- `cleaned_csv`: path to `UNICEF2026S1_clf_train_cleaned.csv` (fallback data source)
- `feature_manifest_path`: `feature_manifest.json` from M2 (defines the 124-feature spec)
- `output_dir`: working output dir (writes under `results/nn/`)
- `random_seed` (default 0)

## Architecture grid

Sweep three MLP architectures (hidden layer sizes):
1. `(64, 32)` — compact
2. `(128, 64, 32)` — medium
3. `(256, 128, 64)` — wide

All models use:
- `activation='relu'`
- `solver='adam'`
- `batch_size=512`
- `learning_rate='adaptive'`
- `max_iter=200`
- `early_stopping=True`, `validation_fraction=0.1`, `n_iter_no_change=15`
- `random_state=<seed>`

## Class imbalance strategies

MLPClassifier does not support `class_weight`. Handle imbalance via **random oversampling** of the minority class on the training set before fitting. Apply four strategies:

| strategy_id | Description |
|---|---|
| `none` | No resampling — use original train set |
| `2_to_1` | Oversample class 0 until minority:majority = 1:2 |
| `3_to_1` | Oversample class 0 until minority:majority = 1:3 |
| `balanced` | Oversample class 0 to match class 1 count |

Always fit on the resampled train. Always evaluate on the **original** val and test sets (no resampling there).

## Alpha grid (L2 regularization)

Sweep `alpha ∈ [1e-4, 1e-3]` (2 values) — keep the grid small to control runtime.

## Total grid

3 architectures × 4 strategies × 2 alpha = **24 cells**.

## Your job

For each (`architecture`, `strategy`, `alpha`) cell:
1. Resample training set according to strategy.
2. Fit `MLPClassifier` on resampled train.
3. Predict probabilities on original TRAIN, VAL, TEST.
4. Pick threshold ∈ `np.linspace(0.05, 0.95, 91)` that maximises **val macro F1**.
5. Evaluate (acc, macroF1, precision/recall per class, ROC-AUC) on TRAIN, VAL, TEST at the chosen threshold.
6. Record: `model_id, architecture, strategy, alpha, threshold, train_acc, train_macroF1, val_acc, val_macroF1, test_acc, test_macroF1, val_auc, test_auc, gap_train_test_macroF1, n_iter, fit_seconds`.

## Outputs

Write all files under `results/nn/`:

- `nn_grid.csv` — one row per cell (the 24-row results table)
- `nn_tradeoff.png` — 4-panel plot (one per strategy), val macro F1 vs architecture, lines for alpha
- `nn_vs_glm.png` — bar chart comparing best NN cell vs GLM macro F1 winner (load `results/macro_f1/preferred_macro_f1.json` for baseline)
- `nn_preferred.json` — full metadata for the winner + 5–8 plain-language interpretation bullets

Write the winning model to `models/nn_winner.pkl`.

## Winner selection

**Overfit-aware**: highest val macro F1 with `|gap_train_test_macroF1| ≤ 0.05`.  
If no cell satisfies that, fall back to highest val macro F1 and flag `overfit_flag: true`.

## Feature engineering fallback

If the parquet files are missing, reproduce M2 logic from `cleaned_csv`:
1. Stratified 70/30/0 split (seed=0) matching data_manifest split sizes.
2. For each categorical column in `transform_summary.categorical`: map levels with train-frequency < 0.005 → `_OTHER`; apply OHE with `drop_first=True` (fit on train only).
3. Standardize `transform_summary.numeric_standardized` columns using train mean/std.
4. Add interaction terms from `feature_sets.interactions` as products of the OHE columns.
5. `reindex(columns=feature_columns, fill_value=0)` to enforce the exact 124-feature manifest.

## Constraints

- Never tune threshold on test set.
- Never fit transformers on val or test data.
- Do not write report prose — numbers and plots only.
- Print a sorted leaderboard by val macro F1 before exiting.
