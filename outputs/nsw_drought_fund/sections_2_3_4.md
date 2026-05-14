# Sections 2–4: Core Analytical Sections

> **Writer:** e_eda_writer equivalent (section_writer)
> **Date:** 2026-05-02
> **Status:** Structural draft — all quantitative claims are placeholders pending asset class data
> **Citation style:** APA 7th (in-text)
> **Word counts:** S2 ≈ 773 words | S3 ≈ 700 words | S4 ≈ 533 words

---

## 2. Asset Class Profiles — Risk, Return, and Liquidity

An effective strategic allocation begins with a rigorous characterisation of each asset class along three dimensions: expected return, risk, and liquidity. This section profiles the candidate asset classes on those dimensions, drawing on the summary statistics compiled in Table 1 and the liquidity comparison in Table 2.

### 2.1 Return and Risk Characteristics

Table 1 presents the annualised return, annualised volatility, maximum drawdown, and Sharpe ratio for each asset class over the sample period [DATA REQUIRED — specify date range]. The Sharpe ratio — excess return over the risk-free rate divided by volatility — provides a standardised measure of risk-adjusted performance that facilitates cross-asset comparison.

As shown in Table 1, [DATA REQUIRED — identify the asset class with the highest annualised return] delivered the highest nominal return at [DATA REQUIRED]% per annum, accompanied by volatility of [DATA REQUIRED]% and a Sharpe ratio of [DATA REQUIRED]. Conversely, [DATA REQUIRED — identify the lowest-volatility asset class] exhibited annualised volatility of [DATA REQUIRED]%, though its return of [DATA REQUIRED]% was commensurately modest.

The risk-return frontier implied by Table 1 reveals whether any asset classes are dominated — that is, whether any class offers both lower return and higher risk than an alternative. [DATA REQUIRED — identify dominated asset classes, if any.] Ilmanen (2011) cautioned that historical average returns embed period-specific biases and may not reflect forward-looking risk premia, a consideration particularly relevant for asset classes with short or unrepresentative sample histories. Dimson et al. (2021), drawing on over 120 years of global data, demonstrated that while equities have outperformed bonds and bills across major markets, the magnitude of the equity risk premium has varied substantially across countries and periods, underscoring the danger of naive extrapolation from a single-market sample.

Maximum drawdown — the largest peak-to-trough decline over the sample period — provides a complementary tail-risk perspective. As reported in Table 1, [DATA REQUIRED — identify the asset class with the deepest drawdown] suffered the most severe drawdown of [DATA REQUIRED]%, reflecting sensitivity to [DATA REQUIRED — economic regime or market event]. Notably, [DATA REQUIRED — comment on whether any asset class exhibited a non-linear risk-return profile, e.g., modest volatility but an outsized drawdown, indicating negative skewness or fat tails in its return distribution].

From a factor-based perspective, return differences across asset classes are not solely attributable to market beta. Fama and French (2015) showed that size, value, profitability, and investment factors explain substantial return variation, while Asness et al. (2013) documented value and momentum premia across equities, bonds, currencies, and commodities. Decomposing asset class returns into factor exposures may clarify whether superior Sharpe ratios reflect genuine alpha or compensation for systematic factor tilts [CITE NEEDED — empirical factor decomposition for the specific asset classes].

### 2.2 Liquidity Assessment

Table 2 characterises each asset class across four liquidity dimensions: bid-ask spread, redemption frequency, market depth tier, and a composite liquidity score. These dimensions capture distinct facets of liquidity — transaction cost (spread), time-to-cash (redemption), and capacity (depth) — that together determine the practical ease with which positions can be established or unwound without material price impact.

Amihud and Mendelson (1986) established the theoretical basis for a liquidity premium, demonstrating that assets with wider bid-ask spreads earn higher average returns to compensate investors for elevated trading costs and reduced exit flexibility. As shown in Table 2, [DATA REQUIRED — identify the least liquid asset classes and their bid-ask spreads]. The question of whether these illiquid asset classes command a return premium commensurate with their liquidity costs can be assessed by comparing their Sharpe ratios in Table 1 against those of their liquid counterparts. [DATA REQUIRED — state whether the liquidity premium is empirically supported in this dataset.]

Critically, the liquidity characteristics of individual asset classes do not aggregate linearly at the portfolio level. Ang et al. (2014) demonstrated that optimal allocation to illiquid assets is substantially lower than mean-variance analysis alone would suggest, because lock-up periods and restricted redemption frequencies constrain the investor's ability to rebalance. This finding implies that the allocations derived in Section 4 must discount the theoretical appeal of high-returning illiquid asset classes to account for portfolio-level liquidity requirements [DATA REQUIRED — note any binding liquidity constraints relevant to the investor's profile].

### 2.3 Data Quality Considerations

Several data quality issues warrant acknowledgement. [DATA REQUIRED — flag specific issues such as: stale or appraisal-based pricing for illiquid assets, which artificially smooths return series and understates true volatility; short sample periods for newer asset classes; survivorship bias if failed funds or delisted securities are excluded.] These issues are revisited in Section 5 as formal limitations.

---

## 3. Portfolio Construction Rationale

The preceding asset class profiles establish the building blocks; this section explains how those building blocks are combined into a portfolio. The construction rationale rests on three pillars: the diversification benefit of imperfectly correlated assets, the choice of optimisation methodology, and the mapping from correlation structure to allocation weights.

### 3.1 Diversification and Correlation Structure

The foundational insight of modern portfolio theory is that portfolio risk is a function not only of individual asset volatilities but also of pairwise correlations among assets (Markowitz, 1952). When assets are imperfectly correlated — that is, when their returns do not move in lockstep — combining them in a portfolio yields a total volatility that is strictly less than the weighted average of individual volatilities. The magnitude of this diversification benefit depends directly on the correlation structure summarised in Table 3.

Table 3 presents the pairwise Pearson correlation matrix computed on [DATA REQUIRED — monthly/quarterly] returns over the sample period [DATA REQUIRED — date range]. Correlations below approximately −0.20 indicate meaningful diversification potential, while correlations above 0.80 suggest high co-movement that limits risk reduction. As shown in Table 3, the lowest pairwise correlation is observed between [DATA REQUIRED — asset class pair], at [DATA REQUIRED], indicating that these two classes are strong candidates for joint inclusion on diversification grounds. Conversely, [DATA REQUIRED — identify highly correlated pairs], with a correlation of [DATA REQUIRED], move largely in tandem and therefore contribute limited incremental diversification when held together.

Pairwise correlations are not static; they tend to increase during market stress — precisely when diversification is most needed [CITE NEEDED — regime-dependent correlation literature, e.g., Longin & Solnik, 2001]. Kinlaw et al. (2017) surveyed robust methods for addressing this non-stationarity, including regime-switching models and shrinkage estimation. Reliance on a single-period correlation matrix should be interpreted with caution.

### 3.2 Construction Methodology

Three principal methodologies are considered for translating the risk-return profiles (Section 2) and correlation structure (Table 3) into portfolio weights: mean-variance optimisation (MVO), risk parity, and the Black-Litterman framework.

**Mean-variance optimisation (MVO)**, pioneered by Markowitz (1952), identifies portfolios on the efficient frontier that maximise expected return for a given level of risk. However, MVO is highly sensitive to errors in expected return estimates. DeMiguel et al. (2009) demonstrated that, across 14 models and seven datasets, the naive 1/N portfolio consistently matched or outperformed optimised allocations out-of-sample, because estimation error in means, variances, and covariances dominates theoretical optimisation gains. This finding serves as a critical robustness benchmark.

**Risk parity** sidesteps return forecasting by equalising each asset class's marginal contribution to total portfolio risk (Qian, 2011). Asness et al. (2012) argued that this approach exploits the empirical finding that low-risk assets deliver higher risk-adjusted returns — a phenomenon attributable to institutional leverage aversion. A traditional 60/40 equity-bond portfolio derives approximately 90% of its risk from equities despite only 60% capital allocation (Qian, 2011), rendering it far less diversified in risk terms than its dollar weights suggest.

The **Black-Litterman model** (Black & Litterman, 1992) begins with market-equilibrium implied returns and allows investors to overlay subjective views with specified confidence levels. The resulting posterior expected returns produce more stable and intuitive portfolio weights than unconstrained MVO [DATA REQUIRED — state whether investor views or forward-looking capital market assumptions are available].

### 3.3 From Correlation Structure to Allocation Logic

The correlation evidence in Table 3 has direct implications for allocation weights. Asset classes that exhibit low or negative correlations with the rest of the portfolio are disproportionately valuable because they contribute more diversification per unit of capital. Conversely, highly correlated asset classes provide diminishing marginal diversification and, absent a compelling return advantage, warrant reduced allocation. [DATA REQUIRED — map specific correlation pairs from Table 3 to allocation weight implications.]

The choice among MVO, risk parity, and Black-Litterman ultimately depends on the reliability of available return forecasts and the investor's risk tolerance. In the absence of high-conviction return views, risk parity or a Black-Litterman approach anchored to equilibrium returns may be preferable to unconstrained MVO, which risks producing unstable and unintuitive allocations (DeMiguel et al., 2009). The recommended allocation presented in Section 4 reflects this reasoning. [DATA REQUIRED — state which methodology was selected and why.]

---

## 4. Allocation Recommendation

Drawing on the risk-return profiles established in Section 2 and the diversification rationale developed in Section 3, this section presents and justifies a specific portfolio allocation. The recommendation balances expected return, risk, liquidity, and diversification considerations within the constraints applicable to the investor's mandate [DATA REQUIRED — specify investor profile, time horizon, and any binding constraints].

### 4.1 Recommended Weights

[DATA REQUIRED — present the specific percentage allocation to each asset class. If Table 4 is included, reference it here; otherwise embed weights in prose.]

As shown in Table 4, the recommended allocation assigns [DATA REQUIRED]% to [DATA REQUIRED — highest-weighted asset class], reflecting its favourable risk-adjusted return profile as documented in Table 1 (Sharpe ratio: [DATA REQUIRED]) and its role as a core portfolio anchor. [DATA REQUIRED — continue for each material allocation, linking the weight to evidence from Table 1, Table 2, and Table 3.]

The portfolio-level expected return under this allocation is [DATA REQUIRED]% per annum, with an expected annualised volatility of [DATA REQUIRED]% and a portfolio Sharpe ratio of [DATA REQUIRED]. These figures represent an improvement over the naive 1/N benchmark, which — while robust to estimation error (DeMiguel et al., 2009) — does not exploit the correlation structure documented in Table 3.

### 4.2 Comparison with Alternative Allocations

To demonstrate that the recommended allocation is not merely one of many arbitrary configurations, it is compared against at least one alternative benchmark. The equally-weighted (1/N) allocation, which assigns [DATA REQUIRED]% to each of the [DATA REQUIRED — number] asset classes, serves as the primary benchmark. Brinson et al. (1986) and Ibbotson and Kaplan (2000) established that strategic allocation is the dominant driver of portfolio return variability, implying that even modest improvements in allocation policy can meaningfully affect long-term outcomes.

Under the 1/N benchmark, the portfolio-level expected return is [DATA REQUIRED]%, with volatility of [DATA REQUIRED]% and a Sharpe ratio of [DATA REQUIRED]. The recommended allocation improves upon this benchmark by [DATA REQUIRED — describe the source of improvement: tilting toward higher-Sharpe assets, exploiting low-correlation pairs, or reducing exposure to dominated classes]. [DATA REQUIRED — if a more aggressive or more conservative alternative is also considered, present it here for comparison.]

For long-horizon investors, Campbell and Viceira (2002) demonstrated that optimal allocation differs from the single-period solution because return predictability and intertemporal hedging demand create horizon-dependent portfolios [DATA REQUIRED — specify investor time horizon and evaluate horizon appropriateness].

### 4.3 Implementation Considerations

Several practical factors bear on implementation. Rebalancing frequency must balance trading costs against drift; for portfolios with illiquid components, quarterly or semi-annual rebalancing may be the highest feasible frequency, as reflected in the redemption constraints documented in Table 2. Transaction costs — particularly the bid-ask spreads in Table 2 — erode realised returns and should be incorporated into net-of-cost projections [DATA REQUIRED — estimate round-trip costs]. Ang et al. (2014) cautioned that optimal allocation to illiquid assets must be discounted relative to frictionless solutions, as lock-up periods constrain rebalancing flexibility. The illiquid allocations in this portfolio account for this by [DATA REQUIRED — explain how illiquidity was addressed]. The allocation is a strategic target; tactical deviations lie beyond the scope of this brief.

---

*End of Sections 2–4. Section 1 (Executive Overview) and Section 5 (Limitations and Caveats) are produced by separate writing agents.*
