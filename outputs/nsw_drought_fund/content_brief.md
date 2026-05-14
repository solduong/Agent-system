# PROPOSAL CONTENT BRIEF

## Document Overview

- **Target document:** Strategic asset allocation brief — risk, return & liquidity analysis
- **Word/page limit:** ~3,000 words of body text (estimated 8–10 formatted pages including tables; assumes 12pt Calibri/TNR, 1.5 line spacing, 2.54 cm margins, ~300 words per text page)
- **Citation style:** APA 7th
- **Output format:** .docx

### Upstream status

| Input | Status | Impact on brief |
|---|---|---|
| Task description | **NOT PROVIDED** | Section scope inferred from project.json and workflow definition |
| Marking rubric | **NOT PROVIDED** | Rubric criteria are *inferred* (see below) — must be validated when rubric is available |
| Asset class data | **NOT PROVIDED** | All table content, statistical claims, and specific findings are placeholders — writing agents must wait for data |
| Reference library | Available (20 sources) | Sufficient for theoretical framing; will need supplementation once data-specific claims emerge |

> **CRITICAL FLAG:** This brief is a *structural scaffold*. Every `[DATA REQUIRED]` tag below marks content that cannot be written until the asset class dataset is provided. Downstream writing agents should treat those tags as hard blockers — do not fabricate data.

---

### Inferred rubric criteria

Because no marking rubric was supplied, the following criteria are inferred from the document type (strategic asset allocation brief at postgraduate finance level). **These must be cross-checked and revised once the actual rubric is available.**

| ID | Inferred criterion | Weight (assumed) | Primary section(s) |
|---|---|---|---|
| RC1 | Understanding of risk-return trade-offs across asset classes | 20% | S2, S3 |
| RC2 | Application of portfolio theory (diversification, correlation, optimisation) | 20% | S3 |
| RC3 | Quality and justification of allocation recommendation | 20% | S4 |
| RC4 | Critical evaluation — limitations, assumptions, sensitivity | 15% | S5 |
| RC5 | Executive communication — clarity, conciseness, actionability | 10% | S1 |
| RC6 | Use of evidence — data integration, in-text citations, table references | 10% | S2, S3, S4 |
| RC7 | Presentation — formatting, table quality, professional structure | 5% | All |

---

### Reference library summary (available for all sections)

| Coverage area | Key sources | Section fit |
|---|---|---|
| Modern Portfolio Theory | Markowitz (1952); DeMiguel et al. (2009); Black & Litterman (1992) | S3, S4 |
| Capital Market Assumptions | Ilmanen (2011); Dimson et al. (2021) | S2, S3 |
| Risk Parity | Asness et al. (2012); Qian (2011); Roncalli (2013) | S3, S4 |
| Liquidity Premia | Amihud & Mendelson (1986); Ang et al. (2014); Pastor & Stambaugh (2003) | S2, S5 |
| Strategic vs Tactical Allocation | Brinson et al. (1986); Ibbotson & Kaplan (2000); Campbell & Viceira (2002) | S1, S3, S4 |
| Factor-Based Allocation | Fama & French (2015); Asness et al. (2013); Ang (2014) | S2, S3 |

---

## Page Budget

| Component | Pages (est.) |
|---|---|
| Total page limit (assumed) | 10 |
| Tables (T1 + T2 + T3 + optional T4) | 1.5 |
| Figures (0–1 optional; e.g., efficient frontier or correlation heatmap) | 0.5 |
| References (APA list, ~20 entries) | 1.0 |
| **Available text pages** | **7.0** |
| **Available text words** (~300 words/page) | **~2,100** |
| Front matter / title / spacing overhead | absorbed into margins |

> Note: The 3,000-word total budget includes table captions, section headings, and minor structural text. The ~2,100 figure is *pure analytical prose*. The difference is consumed by table content, captions, headings, and white space.

---

## Table & Figure Budget

### Mandatory tables

| ID | Title | Content | Est. size | Section |
|---|---|---|---|---|
| T1 | Asset Class Risk-Return Summary | Columns: asset class, annualised return (%), annualised volatility (%), max drawdown (%), Sharpe ratio | ~15 rows × 5 cols | S2 |
| T2 | Liquidity Comparison | Columns: asset class, bid-ask spread, redemption frequency, market depth tier, liquidity score | ~15 rows × 5 cols | S2 |
| T3 | Correlation Matrix | Pairwise correlations across all asset classes | N×N symmetric matrix | S3 |

### Optional table (include if word budget allows)

| ID | Title | Content | Section |
|---|---|---|---|
| T4 | Recommended Allocation | Columns: asset class, weight (%), risk contribution (%), rationale | S4 |

### Figures (0–1)

| ID | Title | Include? | Section |
|---|---|---|---|
| F1 | Efficient frontier with labelled asset classes | Optional — include only if data supports mean-variance plot | S3 |

**Total table/figure page budget: 1.5–2.0 pages.** Writing agents must reference tables by number (e.g., "as shown in Table 1") and not duplicate table data in prose.

---

## Section Allocations

### Section 1: Executive Overview

- **Rubric criteria:** RC5 (executive communication), RC7 (presentation)
- **Word count:** 250–350 words
- **Tables:** 0 (may reference T4 by number)
- **Figures:** 0
- **Depth:** SURFACE
- **Key arguments:**
  - State the investment context and objective (capital preservation vs. growth vs. income — `[DATA REQUIRED]`)
  - Summarise the recommended allocation in 1–2 sentences with the primary risk-return rationale
  - Highlight the single most important trade-off or constraint (e.g., liquidity vs. returns)
  - Conclude with 2–3 actionable next steps or implementation considerations
- **Evidence required:**
  - Brinson et al. (1986) — strategic allocation explains ~90% of return variation
  - Ibbotson & Kaplan (2000) — corroboration of allocation primacy
  - Summary statistics drawn from T1 and T4
- **Flags:**
  - Cannot be written until S2–S4 are complete (it synthesises their conclusions)
  - Investment objective is unknown without task description — writing agent must infer from data context or flag `[OBJECTIVE UNSPECIFIED]`

---

### Section 2: Asset Class Profiles — Risk, Return & Liquidity

- **Rubric criteria:** RC1 (risk-return understanding), RC6 (evidence and data integration), RC7 (table quality)
- **Word count:** 650–800 words
- **Tables:** 2 — **include: T1 (risk-return summary), T2 (liquidity comparison)**
- **Figures:** 0
- **Depth:** DEEP
- **Key arguments:**
  - Profile each asset class on three dimensions: expected return, risk (volatility + tail risk), and liquidity
  - Identify the risk-return frontier — which classes offer superior risk-adjusted returns (Sharpe ratio), which are dominated `[DATA REQUIRED]`
  - Characterise liquidity tiers — distinguish liquid (daily-traded equities, bonds) from illiquid (private equity, real estate, infrastructure) asset classes `[DATA REQUIRED]`
  - Note the liquidity premium — illiquid assets should command higher expected returns to compensate; assess whether the data supports this `[DATA REQUIRED]`
  - Flag any data quality issues (missing periods, survivorship bias, stale pricing for illiquid assets)
- **Evidence required:**
  - T1 data for all risk-return claims (do not state statistics without table reference)
  - T2 data for liquidity claims
  - Ilmanen (2011) — expected returns framework and risk premia decomposition
  - Dimson et al. (2021) — long-run historical asset class returns
  - Amihud & Mendelson (1986) — theoretical basis for liquidity premium
  - Fama & French (2015) — factor-based return drivers where relevant
- **Flags:**
  - This section is entirely data-dependent — it is a hard blocker until asset class data is provided
  - Writing agent must not invent return or volatility figures; use `[DATA REQUIRED]` placeholders
  - If fewer than 5 asset classes are in the dataset, T1 and T2 can be combined into a single table (reclaim ~0.3 pages for prose)

---

### Section 3: Portfolio Construction Rationale

- **Rubric criteria:** RC2 (portfolio theory application), RC6 (evidence and citations), RC1 (risk-return, partial)
- **Word count:** 550–700 words
- **Tables:** 1 — **include: T3 (correlation matrix)**
- **Figures:** 0–1 — **include F1 (efficient frontier) only if data supports it**
- **Depth:** DEEP
- **Key arguments:**
  - Explain the diversification benefit — how combining imperfectly correlated assets reduces portfolio risk below the weighted average of individual risks
  - Reference T3 to identify key low-correlation or negative-correlation pairs that drive diversification `[DATA REQUIRED]`
  - Discuss the choice of construction methodology — mean-variance optimisation (Markowitz), risk parity, or Black-Litterman, with justification for which approach suits the given data and constraints
  - Acknowledge estimation error — MVO is sensitive to expected return inputs; cite DeMiguel et al. (2009) on the competitiveness of naive 1/N allocation as a robustness benchmark
  - If risk parity is used or recommended: explain why equalising risk contributions across asset classes may be preferable when return forecasts are unreliable (Asness et al., 2012; Qian, 2011)
  - Connect correlation structure to allocation logic — low-correlation assets receive higher weight because they contribute more diversification per unit of capital
- **Evidence required:**
  - T3 correlation data (reference specific pairs)
  - Markowitz (1952) — foundational mean-variance framework
  - DeMiguel et al. (2009) — estimation error and 1/N benchmark
  - Black & Litterman (1992) — Bayesian approach to incorporating views
  - Asness et al. (2012) — risk parity and leverage aversion
  - Qian (2011) — risk budgeting framework
  - Roncalli (2013) — standby, use if risk parity discussion warrants deeper treatment
- **Flags:**
  - The depth of this section depends on how many asset classes are in the dataset — with fewer than 4 classes, correlation analysis is thin
  - If no optimisation is actually run (no data), this section becomes purely theoretical — writing agent should frame it as "recommended approach" rather than "results of optimisation"
  - F1 (efficient frontier) should only be included if the writing agent or table-maker can compute it from actual data; do not include a generic textbook diagram

---

### Section 4: Allocation Recommendation

- **Rubric criteria:** RC3 (quality of recommendation), RC6 (evidence and citations)
- **Word count:** 400–550 words
- **Tables:** 0–1 — **include T4 (recommended allocation) if budget allows; otherwise embed in prose**
- **Figures:** 0
- **Depth:** MODERATE
- **Key arguments:**
  - Present the specific recommended allocation (% weight per asset class) `[DATA REQUIRED]`
  - Justify each weight with explicit reference to the risk-return profile (S2 / T1) and diversification benefit (S3 / T3)
  - Quantify the portfolio-level expected return, volatility, and Sharpe ratio under the recommended allocation `[DATA REQUIRED]`
  - Compare against at least one alternative allocation (e.g., equal-weight 1/N, or a more aggressive/conservative tilt) to demonstrate why the recommended allocation is preferred
  - Address any binding constraints — e.g., minimum liquidity requirements, regulatory limits, concentration caps
  - Note implementation considerations: rebalancing frequency, transaction costs, tax efficiency
- **Evidence required:**
  - T1 and T3 data (referenced by number)
  - T4 if included
  - Ibbotson & Kaplan (2000) — allocation as primary performance driver
  - Campbell & Viceira (2002) — strategic allocation for long-horizon investors (if time horizon is specified)
  - Ang (2014) — systematic factor-based allocation framework
  - Sharpe (1992) — standby, use if style analysis is relevant
- **Flags:**
  - Without asset class data, the writing agent cannot compute portfolio-level statistics — all quantitative claims must be tagged `[DATA REQUIRED]`
  - The comparison to an alternative allocation is important for RC3 (justification quality) — even without data, the writing agent should structure the argument as "our allocation vs. naive benchmark"
  - If T4 is included as a table, keep prose tight (closer to 400 words); if allocation is embedded in prose, allow up to 550 words

---

### Section 5: Limitations and Caveats

- **Rubric criteria:** RC4 (critical evaluation), RC5 (communication, partial)
- **Word count:** 250–350 words
- **Tables:** 0
- **Figures:** 0
- **Depth:** MODERATE
- **Key arguments:**
  - **Data limitations:** historical returns may not predict future performance; short sample periods amplify estimation error; illiquid asset classes may have stale or smoothed return series
  - **Model assumptions:** mean-variance optimisation assumes normally distributed returns and stable correlations — both are violated in practice (fat tails, regime shifts)
  - **Liquidity mismatch:** portfolio-level liquidity may differ from weighted-average asset-class liquidity if redemption gates or lock-ups bind simultaneously in stress
  - **Scope boundaries:** the brief covers strategic allocation only — it does not address manager selection, tactical timing, or implementation (currency hedging, derivatives overlays)
  - **Sensitivity:** the recommended allocation is conditional on the capital market assumptions used; small changes in expected returns can produce large swings in optimal weights (DeMiguel et al., 2009)
- **Evidence required:**
  - DeMiguel et al. (2009) — estimation error sensitivity
  - Ang et al. (2014) — illiquidity constraints in portfolio choice
  - Franzoni et al. (2012) — standby, use if private equity / alternatives are in the asset mix
  - Pastor & Stambaugh (2003) — standby, use if systematic liquidity risk is discussed
- **Flags:**
  - This section can be written without data (it is about limitations of the *approach*), but specific data limitations depend on knowing what the dataset contains
  - Writing agent should ensure this section does not read as a generic disclaimer — tie each limitation back to a specific choice made in S3 or S4

---

## Rubric-to-Section Mapping (Summary)

| Criterion | Primary section | Supporting section(s) | Key evidence |
|---|---|---|---|
| RC1: Risk-return understanding | S2 | S3 | T1, Ilmanen (2011), Dimson et al. (2021) |
| RC2: Portfolio theory application | S3 | — | T3, Markowitz (1952), DeMiguel et al. (2009), Black & Litterman (1992) |
| RC3: Recommendation quality | S4 | S2, S3 | T4, Ibbotson & Kaplan (2000), Campbell & Viceira (2002) |
| RC4: Critical evaluation | S5 | — | DeMiguel et al. (2009), Ang et al. (2014) |
| RC5: Executive communication | S1 | S5 | Brinson et al. (1986) |
| RC6: Evidence & citations | S2, S3, S4 | — | All tables, all targeted references |
| RC7: Presentation & formatting | All | — | Table captions, APA style, heading hierarchy |

---

## Word Budget Summary

| Section | Word range | % of text budget | Depth | Tables | Figures |
|---|---|---|---|---|---|
| S1: Executive Overview | 250–350 | 11% | SURFACE | 0 | 0 |
| S2: Asset Class Profiles | 650–800 | 28% | DEEP | 2 (T1, T2) | 0 |
| S3: Portfolio Construction | 550–700 | 24% | DEEP | 1 (T3) | 0–1 (F1) |
| S4: Allocation Recommendation | 400–550 | 18% | MODERATE | 0–1 (T4) | 0 |
| S5: Limitations & Caveats | 250–350 | 11% | MODERATE | 0 | 0 |
| Headings, captions, transitions | ~200 | 8% | — | — | — |
| **Total** | **~2,500–2,950** | **100%** | — | **3–4** | **0–1** |

---

## Gaps and Risks

### Hard blockers (must be resolved before writing begins)

| # | Gap | Impact | Resolution |
|---|---|---|---|
| G1 | **No asset class data provided** | Sections 2, 3, 4 cannot include any quantitative claims, table content, or data-driven arguments | Provide the asset class CSV/XLSX with risk, return, and liquidity metrics per class |
| G2 | **No task description provided** | Investment objective, time horizon, investor profile, and constraints are unknown — Section 1 cannot frame the brief; Section 4 cannot justify constraints | Provide the task description document |
| G3 | **No marking rubric provided** | All rubric criteria above are *inferred* — actual weightings and assessment focus may differ substantially | Provide the marking rubric so criteria can be validated and section weights adjusted |

### Soft risks (can proceed, but quality may be reduced)

| # | Risk | Mitigation |
|---|---|---|
| R1 | Reference library built without data — some targeted sources may not match actual findings | Re-run reference matching after data is provided; add empirical sources specific to the asset classes in the dataset |
| R2 | Word budget assumes ~10 pages — actual page limit may differ | Adjust all word counts proportionally once page limit is confirmed |
| R3 | No efficient frontier figure may be computable without optimisation code | Table-maker or writing agent should assess feasibility; omit F1 if not computable from raw data |
| R4 | Inferred rubric over-weights quantitative analysis — actual rubric may emphasise qualitative judgement or practical implementation | Revise depth levels and word allocations once rubric is confirmed |
| R5 | Correlation matrix (T3) requires pairwise return data at matching frequencies | If only summary statistics (no time series) are provided, T3 may need to be sourced from literature rather than computed — flag as a limitation in S5 |

---

## Instructions for Downstream Agents

1. **Table-maker:** Build T1, T2, T3 (and T4 if budget allows) from analysis_findings once data is available. Each table needs: number, descriptive caption, aligned columns, source note. Do not exceed 4 tables total.

2. **Section writers (body + executive):** Respect word count ranges strictly — the budget is tight. Every statistical claim must reference a table by number. Every theoretical claim must have an in-text citation. Use `[DATA REQUIRED]` for any claim that depends on the missing dataset. Use `[CITE NEEDED]` for claims needing a source not in the reference library.

3. **Assembler:** Section order is S1 → S2 → S3 → S4 → S5 → References. Insert tables at their first reference point, not at the end. Apply sequential numbering (Table 1, Table 2, ...).

4. **Reviewer:** When the rubric becomes available, re-map criteria to sections and flag any misallocations. The inferred rubric is a best guess — treat all RC mappings as provisional.
