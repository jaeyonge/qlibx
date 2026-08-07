# KOSPI 200 Low-P/B Alpha Study Plan

Status: preregistered before inspecting portfolio-performance results  
Plan date: 2026-08-07

Implementation rules were frozen in the 2026-08-08 amendment below before
portfolio-performance results were computed.

## Research question

Among point-in-time KOSPI 200 members, does a lower positive P/B rank at
month-end predict higher returns during the following month than both the
equal-weighted eligible universe and a high-P/B portfolio?

## Hypothesis and proposed mechanism

The market may sometimes become too pessimistic about low-P/B companies. If
their assets and profitability prove better than expected, their prices may
recover. Low P/B can also correctly reflect weak profitability or distress, so
the direction and stability of the effect must be tested rather than assumed.

## Data

- Point-in-time universe: `DW/fng_k200_members.csv`
- Signal: `PBR` from `DW/dw_fng_mirror/dw_fng_valuation.parquet`
- Returns: `DW/fng_stock_daily_prices.csv`
- Frequency: daily source observations, sampled monthly for portfolio formation

### Known limitations

- The valuation history does not document whether old P/B observations were
  later revised. The study will treat the dated values as available on their
  recorded dates but will disclose that point-in-time safety is unverified.
- EDA strongly supports the daily adjusted-return relationship below, but the
  source does not document exactly which corporate actions, including cash
  dividends, are covered by `수정계수`.
- The high/low-volatility boundary is relative to the 2018–2022 discovery
  sample. It is a robust operational split for diagnostics, not a universal or
  economically absolute definition of high volatility.
- These limitations may restrict the strength of the conclusion even if the
  calculations complete successfully.

## Observation and execution clock

1. On each calendar month's final KOSPI trading day, observe membership and P/B.
2. Use only information dated no later than that observation day.
3. Form portfolios at the next trading day's close.
4. Hold until the next scheduled monthly rebalance.
5. Apply membership changes and P/B re-ranking only at scheduled rebalances.

## Eligibility and signal

At each observation date:

1. Begin with KOSPI 200 members recorded for that date.
2. Exclude stocks with missing, zero, or negative P/B.
3. Rank eligible stocks by P/B in ascending order.
4. Define the cheapest 20% as the low-P/B portfolio.
5. Define the most expensive 20% as the high-P/B portfolio.

No sector, market-beta, size, or momentum neutralization will be applied in the
initial study. Those exposures will be measured and treated as diagnostics.

## Portfolio construction

- Low-P/B portfolio: equal-weighted cheapest 20%
- High-P/B portfolio: equal-weighted most expensive 20%
- Baseline: equal-weighted set of all eligible KOSPI 200 members
- Stocks are not replaced between scheduled rebalances unless a valid price is
  unavailable. Any resulting handling rule and affected observations must be
  reported.

## Return calculation

For a valid security-day observation:

```text
adjusted daily return = 종가 / 기준가 - 1
```

The observed data also supports the equivalent relationship:

```text
adjusted daily return = 종가 × 수정계수 / 전일종가 - 1
```

Monthly holding-period returns will compound valid adjusted daily returns. Rows
with nonpositive required price inputs will not be silently converted to zero
return; their treatment and effect will be reported.

## Evaluation periods

- Discovery: 2018-01-01 through 2022-12-31
- Confirmation: 2023-01-01 through 2025-12-31
- Reserved: 2026, because the available year is incomplete

The confirmation period will not be used to tune the signal or portfolio rules.
Results will also be reported separately by year. For each holding month:

- Rising market: equal-weighted eligible-universe return is greater than zero.
- Falling market: equal-weighted eligible-universe return is zero or negative.
- Realized market volatility: standard deviation of the month's daily
  equal-weighted eligible-universe returns, annualized by multiplying by
  `sqrt(252)`.
- High volatility: realized market volatility is above the median monthly value
  observed during 2018–2022.
- Low volatility: realized market volatility is at or below that median.

The discovery-period volatility threshold will be applied unchanged to the
2023–2025 confirmation period. These regimes are retrospective diagnostics and
are not inputs to portfolio decisions. Because sector classifications start in
2020 and lack a complete codebook, sector exposure will be reported separately
where available rather than used to define a market regime.

## Comparisons and metrics

Primary comparisons:

1. Low-P/B portfolio minus the equal-weighted eligible-universe baseline
2. Low-P/B portfolio minus the high-P/B portfolio

The initial study reports gross returns before commissions, taxes, bid–ask
spreads, and market impact. Turnover will be retained so a later cost study can
reuse the result. Gross performance must not be described as net or directly
investable performance.

For each portfolio and comparison, report:

- Annualized return
- Volatility
- Maximum drawdown
- Percentage of positive months
- Turnover
- Results by year and by the predeclared market-regime diagnostics
- Uncertainty interval around the average monthly comparison return

Concentration and exposure diagnostics must show whether results are dominated
by one year, a few securities, or a sector exposure.

## Evidence decision rules

- **Supported:** Both primary comparisons are positive in discovery and
  confirmation, and both confirmation-period 95% confidence intervals exclude
  zero on the positive side.
- **Challenged:** Both confirmation-period comparison means are zero or negative.
- **Inconclusive:** Results are mixed, unstable across years, or too uncertain.
- **Invalid:** Data integrity, availability, timing, or return-construction
  problems make the test unreliable.

A completed run and a supported hypothesis are separate outcomes.

## Search and stopping rule

The initial study is one execution of the fixed rules above, not a parameter
search. Quintile boundaries, rebalance frequency, weighting, periods, and
comparisons will not be changed after viewing results. Any subsequent variation
must be labeled exploratory and registered as a separate study or dated plan
amendment.

## Explicitly deferred

- Sector/factor neutralization and hedging
- Short-position or synthetic-short implementation in Qlib
- Transaction-cost, tax, bid–ask-spread, and market-impact modeling
- Raw financial-statement factor construction
- Multi-factor models, machine learning, and parameter optimization
- Portfolio optimization, ensembles, futures, options, and live trading
- Claims of real-world investability or actual trading profitability

## Implementation-rule amendment — 2026-08-08

This amendment resolves mechanical ambiguities without changing the hypothesis,
signal, universe, periods, or comparisons.

- A holding month is named for the month containing the entry date. The signal
  is observed at the prior month's final trading-day close. Entry is at the next
  trading-day close. Returns begin on the trading day after entry and include
  the next scheduled entry/rebalance close as the exit.
- Securities are sorted by `(P/B, instrument ID)`. Each tail contains
  `floor(eligible_count × 20%)` securities, with a minimum of one. The ID
  secondary key gives deterministic exact-sized tails when P/B values tie.
- Eligibility uses only observation-date membership and finite, strictly
  positive observation-date P/B. A selected security without valid positive
  entry inputs is not replaced; its intended equal weight remains cash for that
  holding month. A missing holding-period return makes that portfolio-month
  invalid rather than silently treating the observation as zero.
- One-way turnover is `0.5 × sum(abs(new target weight - drifted pre-trade
  weight))` across securities and cash. Initial formation is excluded from
  average turnover.
- Annualized return, volatility, beta, and maximum drawdown use the stitched
  daily buy-and-hold portfolio path. Positive-month percentage and uncertainty
  intervals use holding-month returns.
- The 95% interval for an average monthly comparison return uses a deterministic
  moving-block bootstrap: three-month blocks, 20,000 resamples, seed 20260807.
- Market beta is the OLS slope of daily portfolio returns on daily eligible-
  universe returns. Momentum is trailing 12-to-1-month adjusted return at the
  observation date. Size is the weighted mean log market capitalization.
  Sector exposure uses the first FGSC hierarchy component and is reported only
  from 2020, without assigning names because no codebook is supplied.
- Gross returns assume zero interest on cash. The volatility threshold is the
  median discovery-period monthly annualized baseline volatility and remains
  frozen for confirmation.
