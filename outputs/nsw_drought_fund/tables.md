# Tables — Strategic Asset Allocation Brief

> **STATUS: DATA REQUIRED**
> All tables below are structural scaffolds only. The asset class dataset has not been provided. Every cell marked `[DR]` requires data from the upstream `parsed_inputs` step. Once the dataset is supplied, this file will be regenerated with publication-ready values.

---

## [SECTION 2: ASSET CLASS PROFILES]

**Table 1: Asset Class Risk-Return Summary**

| # | Asset Class | Ann. Return (%) | Ann. Volatility (%) | Max Drawdown (%) | Sharpe Ratio |
|--:|:------------|----------------:|---------------------:|------------------:|-------------:|
| 1 | [DR]        |            [DR] |                [DR]  |             [DR]  |         [DR] |
| 2 | [DR]        |            [DR] |                [DR]  |             [DR]  |         [DR] |
| 3 | [DR]        |            [DR] |                [DR]  |             [DR]  |         [DR] |
| 4 | [DR]        |            [DR] |                [DR]  |             [DR]  |         [DR] |
| 5 | [DR]        |            [DR] |                [DR]  |             [DR]  |         [DR] |
| 6 | [DR]        |            [DR] |                [DR]  |             [DR]  |         [DR] |
| 7 | [DR]        |            [DR] |                [DR]  |             [DR]  |         [DR] |
| 8 | [DR]        |            [DR] |                [DR]  |             [DR]  |         [DR] |

*Notes:* Ann. Return = annualised geometric mean return. Ann. Volatility = annualised standard deviation of returns. Max Drawdown = largest peak-to-trough decline over the sample period. Sharpe Ratio = (Ann. Return - Risk-Free Rate) / Ann. Volatility. All figures rounded to 2 decimal places.
*Source:* [DR] — asset class dataset not yet provided.

---

**Table 2: Liquidity Comparison by Asset Class**

| # | Asset Class | Bid-Ask Spread (bps) | Redemption Frequency | Market Depth Tier | Liquidity Score |
|--:|:------------|---------------------:|:---------------------|:------------------|----------------:|
| 1 | [DR]        |                [DR]  | [DR]                 | [DR]              |            [DR] |
| 2 | [DR]        |                [DR]  | [DR]                 | [DR]              |            [DR] |
| 3 | [DR]        |                [DR]  | [DR]                 | [DR]              |            [DR] |
| 4 | [DR]        |                [DR]  | [DR]                 | [DR]              |            [DR] |
| 5 | [DR]        |                [DR]  | [DR]                 | [DR]              |            [DR] |
| 6 | [DR]        |                [DR]  | [DR]                 | [DR]              |            [DR] |
| 7 | [DR]        |                [DR]  | [DR]                 | [DR]              |            [DR] |
| 8 | [DR]        |                [DR]  | [DR]                 | [DR]              |            [DR] |

*Notes:* Bid-Ask Spread in basis points (1 bp = 0.01%). Redemption Frequency = shortest standard redemption interval (e.g., daily, monthly, quarterly, locked). Market Depth Tier = High / Medium / Low based on average daily trading volume or NAV turnover. Liquidity Score = composite ranking (1 = most liquid).
*Source:* [DR] — asset class dataset not yet provided.

---

## [SECTION 3: PORTFOLIO CONSTRUCTION RATIONALE]

**Table 3: Pairwise Correlation Matrix Across Asset Classes**

|              | Class 1 | Class 2 | Class 3 | Class 4 | Class 5 | Class 6 | Class 7 | Class 8 |
|:-------------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|--------:|
| **Class 1**  |    1.00 |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |
| **Class 2**  |    [DR] |    1.00 |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |
| **Class 3**  |    [DR] |    [DR] |    1.00 |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |
| **Class 4**  |    [DR] |    [DR] |    [DR] |    1.00 |    [DR] |    [DR] |    [DR] |    [DR] |
| **Class 5**  |    [DR] |    [DR] |    [DR] |    [DR] |    1.00 |    [DR] |    [DR] |    [DR] |
| **Class 6**  |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    1.00 |    [DR] |    [DR] |
| **Class 7**  |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    1.00 |    [DR] |
| **Class 8**  |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    [DR] |    1.00 |

*Notes:* Pairwise Pearson correlations computed on [DR — specify: monthly/quarterly] returns over the sample period [DR — specify: date range]. Diagonal entries are 1.00 by definition. Values below -0.20 indicate meaningful diversification potential; values above 0.80 suggest high co-movement. Row and column labels will be replaced with actual asset class names once data is provided.
*Source:* [DR] — asset class dataset not yet provided.

---

## [SECTION 4: ALLOCATION RECOMMENDATION] *(Optional — include if word budget allows)*

**Table 4: Recommended Portfolio Allocation** *(OPTIONAL)*

| # | Asset Class | Weight (%) | Risk Contribution (%) | Rationale |
|--:|:------------|:-----------:|:---------------------:|:----------|
| 1 | [DR]        |        [DR] |                  [DR] | [DR]      |
| 2 | [DR]        |        [DR] |                  [DR] | [DR]      |
| 3 | [DR]        |        [DR] |                  [DR] | [DR]      |
| 4 | [DR]        |        [DR] |                  [DR] | [DR]      |
| 5 | [DR]        |        [DR] |                  [DR] | [DR]      |
| 6 | [DR]        |        [DR] |                  [DR] | [DR]      |
| 7 | [DR]        |        [DR] |                  [DR] | [DR]      |
| 8 | [DR]        |        [DR] |                  [DR] | [DR]      |
|   | **Total**   |   **100.0** |              **100.0**| —         |

*Notes:* Weight = strategic allocation as a percentage of total portfolio value. Risk Contribution = each asset class's share of total portfolio volatility (marginal contribution to risk × weight, summing to 100%). Rationale summarises the key driver behind each weight decision (risk-return profile, diversification, liquidity constraint).
*Source:* [DR] — derived from optimisation or risk-budgeting model applied to the asset class dataset (not yet provided).

---

## Table Budget Reconciliation

| Table | Section | Status | Type |
|:------|:--------|:-------|:-----|
| T1: Asset Class Risk-Return Summary | S2 | Scaffold only — `[DATA REQUIRED]` | Mandatory |
| T2: Liquidity Comparison | S2 | Scaffold only — `[DATA REQUIRED]` | Mandatory |
| T3: Correlation Matrix | S3 | Scaffold only — `[DATA REQUIRED]` | Mandatory |
| T4: Recommended Allocation | S4 | Scaffold only — `[DATA REQUIRED]` | Optional |
| **Total: 4 tables** | — | **0 of 4 populated** | Budget max: 4 |

---

## Data Requirements for Table Population

To populate these tables, the following **must be provided**:

1. **Asset class dataset** (CSV or XLSX) containing, at minimum:
   - Asset class names/labels
   - Annualised return (or periodic returns from which to compute)
   - Annualised volatility (or return series to compute)
   - Maximum drawdown
   - Risk-free rate (for Sharpe ratio computation)
   - Bid-ask spread or equivalent liquidity proxy
   - Redemption frequency/terms
   - Pairwise return series (for correlation matrix) OR pre-computed correlation matrix

2. **Number of asset classes** — determines the row count for T1/T2 and the dimensions of T3.

3. **Sample period** — needed for table source notes.

Once the data file path is provided, this file will be regenerated with publication-ready values (2–3 significant figures, consistent units, proper alignment).
