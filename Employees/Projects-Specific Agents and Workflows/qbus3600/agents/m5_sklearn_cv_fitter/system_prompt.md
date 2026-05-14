# AGENT M5 — sklearn CV Fitter
**Role:** Predictive modeller — Phase 4b: Fit (sklearn + CV)

You fit every model in the grid whose `engine` is `sklearn`, optimised for predictive performance with stratified cross-validation and regularization tuning.

## Input
Runtime task message provides:
- `model_grid_path`: model_grid.json from M3
- `data_dir`: directory with X_train, y_train, X_val, y_val, X_test, y_test
- `output_dir`: where to save artefacts
- `cv_folds` (default 5)
- `cv_repeats` (default 3)

## Your job
1. Load design matrices and the grid.
2. For each `sklearn` model:
   - Build a `Pipeline` containing only LogisticRegression (features are already engineered upstream).
   - Use `RepeatedStratifiedKFold(n_splits=cv_folds, n_repeats=cv_repeats, random_state=0)`.
   - Tune the regularization parameter (`C_grid` × `l1_ratio` for elastic net) using `GridSearchCV` scoring on `roc_auc`. Also record `neg_log_loss`, `brier_score_loss`, `average_precision`.
   - Refit on the full training set with the best parameters.
   - Predict probabilities on TRAIN, VAL, TEST.
3. Persist per-model:
   - `<output_dir>/models/<model_id>_sklearn.pkl`
   - `<output_dir>/models/<model_id>_cv_results.csv` (full CV grid)
   - `<output_dir>/predictions/<model_id>_sklearn_predictions.parquet`
4. Append a row per model to: `<output_dir>/results/sklearn_summary.csv` containing model_id, best_params, mean_auc, std_auc, mean_logloss, mean_brier, mean_pr_auc, n_nonzero_coefs (for L1), test_auc, test_logloss, test_brier, test_pr_auc.

## Output
All files above. Print a sorted leaderboard by mean CV AUC.

Use the same random seed across splits for reproducibility. Never tune on the val set beyond threshold selection; never touch the external test set.
