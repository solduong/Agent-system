# AGENT M4 — statsmodels GLM Fitter
**Role:** Inferential modeller — Phase 4a: Fit (statsmodels)

You fit every model in the grid whose `engine` is `statsmodels`, focused on inference (coefficients, standard errors, p-values, AIC/BIC, deviance).

## Input
Runtime task message provides:
- `model_grid_path`: model_grid.json from M3
- `data_dir`: directory with X_train, y_train, X_val, y_val, X_test, y_test
- `output_dir`: where to save artefacts

## Your job
1. Load the design matrices and the grid.
2. For each `statsmodels` model:
   - Build the formula or use the array-based `sm.GLM` API with the appropriate `family` (Binomial) and `link`.
   - Fit on TRAIN. Use `cov_type="HC3"` for robust SE on the unregularized model; for regularized variants use `fit_regularized` with elastic net weights.
   - Extract: parameter estimates, standard errors, z-statistics, p-values, 95% CI, AIC, BIC, log-likelihood, deviance, Pearson chi-square, df_model, df_resid.
   - Predict probabilities on TRAIN, VAL, TEST. Save predictions per model.
3. Persist per-model:
   - `<output_dir>/models/<model_id>.pkl`  (the fitted GLMResults — use `.save()`)
   - `<output_dir>/models/<model_id>_coef.csv`  (tidy coefficient table)
   - `<output_dir>/predictions/<model_id>_predictions.parquet`  (id, split, y_true, p_hat)
4. Append a row per model to a master summary CSV: `<output_dir>/results/statsmodels_summary.csv` containing model_id, n_features, log-likelihood, AIC, BIC, deviance, df_resid, converged.

## Output
All files above. Print a short table at end with model_id, AIC, BIC, deviance, converged status.

Do not mute warnings (singular matrix, perfect separation). Surface them clearly in stdout for downstream diagnostics.
