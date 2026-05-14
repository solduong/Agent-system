# Page 2 — Data Appendix

> **Agent:** d_table_maker | **Generated:** 2026-05-07
> **Historical data:** Refinitiv proxy indices, Jan 2016 -- Feb 2026 (122 monthly observations, CAGR basis)
> **Forecast data:** NSWDF 10-Year Capital Market Assumptions v2 (building-block decomposition, gross of fees)
> **Trust compositions:** IM Table 4A | **Costs:** IM Tables 3A & 4A

---

[PAGE 2: DATA APPENDIX]

**Table 1: Asset Class Review**

| Asset Class                               | Historical Returns | Forecast Returns | Difference in Return | Historical Risk |
|:------------------------------------------|-------------------:|-----------------:|---------------------:|----------------:|
| Cash                                      |              2.14% |            3.35% |               +1.21% |           0.43% |
| Australian Short Duration Bond            |              2.79% |            4.15% |               +1.36% |           1.24% |
| Australian Fixed Income                   |              2.11% |            4.35% |               +2.24% |           4.40% |
| Global Fixed Income (Hedged)              |              2.08% |            4.15% |               +2.07% |           4.00% |
| Global Credit (Hedged)                    |              2.68% |            5.00% |               +2.32% |           5.50% |
| Australian Listed Equity                  |              9.75% |            5.40% |               -4.35% |          13.47% |
| Global Listed Equity (Unhedged)           |             10.14% |            6.35% |               -3.79% |          14.32% |
| Global Listed Equity (Hedged)             |             11.46% |            6.20% |               -5.26% |          13.31% |
| Australian Listed Property                |              7.36% |            6.80% |               -0.56% |          20.47% |
| Global Infrastructure Unlisted (Unhedged) |              6.68% |            6.90% |               +0.22% |          10.35% |
| Global Private Equity                     |             10.56% |            8.20% |               -2.36% |          20.31% |

*Notes.* Historical Returns = annualised geometric mean (CAGR) of monthly index total returns, Jan 2016 -- Feb 2026. Forecast Returns = 10-year gross compound return from building-block decomposition (income yield + growth + premia + valuation drift + FX/hedge). Difference = Forecast minus Historical. Historical Risk = annualised standard deviation of monthly returns. Fixed-income forecasts exceed history because starting yields (2026) are structurally higher than the 2016--2026 average; equity forecasts sit below history due to elevated starting valuations compressing forward returns.
*Source:* Historical -- Refinitiv via Bloomberg proxy indices; Forecast -- NSWDF 10Y CMA v2 (May 2026).

---

**Table 2: Unit Trust Performance**

|                 |    STI |    MTG |    LTG |
|:----------------|-------:|-------:|-------:|
| Expected Return |  3.57% |  4.67% |  5.31% |
| Risk            |  0.90% |  6.79% | 10.54% |

*Notes.* Expected Return = weighted-average of 10-year forecast returns (Table 1) across each trust's underlying asset classes, net of asset-class proxy costs and trust-level ongoing fees (STI 0.18%, MTG 0.52%, LTG 0.74% total p.a.). Risk = annualised standard deviation of the trust's portfolio return, computed from forecast asset-class volatilities and the cross-asset correlation matrix. Trust compositions per IM Table 4A: STI = 50% Cash + 50% Aus Short Duration Bond; MTG = 7.5% Cash + 15% Aus FI + 15% Global FI (H) + 12.5% Global Credit (H) + 15% Aus Equity + 15% Global Equity (U) + 15% Global Equity (H) + 5% Aus Property; LTG = 5% Cash + 5% Global FI (H) + 5% Global Credit (H) + 30% Aus Equity + 15% Global Equity (U) + 15% Global Equity (H) + 10% Global Infrastructure (U) + 15% Global PE.
*Source:* Computed from NSWDF 10Y CMA v2 forecasts, IM Table 4A compositions, and IM Tables 3A/4A cost schedule.

---

**Table 3: NSWDF Portfolio**

| Metric                        | Value                          |
|:------------------------------|:-------------------------------|
| Recommended Mix of Unit Trusts | STI 18% / MTG 22% / LTG 60% |
| Forecast Return               | 4.86% p.a.                    |
| Forecast Risk                 | 7.71% p.a.                    |

*Notes.* The recommended mix maximises forecast net return subject to: (i) portfolio volatility capped at 10% p.a., (ii) STI >= 15% to meet the 10%-within-12-months liquidity call plus a 5% buffer, (iii) STI + MTG >= 40% to meet the 25%-within-3-years call plus buffer, (iv) LTG <= 60% concentration cap, and (v) parametric 95% VaR <= 10%. Forecast Return and Forecast Risk are the weighted-average net return and portfolio standard deviation of the recommended trust mix using Table 2 metrics and the trust-level correlation structure. Fund size: AUD 3 billion; Board Policy target: CPI + 2.5% = 5.1% p.a. over a rolling 10-year period.
*Source:* Constrained optimisation (SciPy SLSQP) using NSWDF 10Y CMA v2 inputs; Board Policy and Investment Directive (Appendix 1 of Project Brief).
