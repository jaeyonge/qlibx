# KOSPI 200 Low-P/B First-Cycle Evidence Report

Run ID: `cfd6578fac72ec9051c83df0b9133ac9db44fab53fde5d81f17ce0a2eccb09b0`  
Decision: **INVALID**  
Returns are gross, research-only, and not evidence of investability.

## Research result

Selected holding returns are unresolved for A000030; without a registered successor/corporate-action mapping, the preregistered test is unreliable.

| Period | Portfolio | Annualized return | Volatility | Max drawdown | Positive months | Turnover |
|---|---|---:|---:|---:|---:|---:|
| discovery | low_pbr | -2.59% | 22.86% | -62.93% | 53.45% | 10.43% |
| discovery | baseline | -4.55% | 20.63% | -55.47% | 53.45% | 3.97% |
| discovery | high_pbr | -8.87% | 22.05% | -49.99% | 47.46% | 10.12% |
| confirmation | low_pbr | 17.06% | 19.36% | -16.75% | 55.56% | 10.32% |
| confirmation | baseline | 18.50% | 17.88% | -15.33% | 55.56% | 4.39% |
| confirmation | high_pbr | 12.85% | 23.16% | -29.00% | 58.33% | 11.88% |

## Primary comparisons

| Period | Comparison | N | Average monthly return | 95% moving-block bootstrap interval | Positive months |
|---|---|---:|---:|---:|---:|
| discovery | low_minus_baseline | 58 | 0.23% | [-0.35%, 0.86%] | 51.72% |
| discovery | low_minus_high | 58 | 0.65% | [-0.55%, 2.04%] | 50.00% |
| confirmation | low_minus_baseline | 36 | -0.10% | [-1.02%, 0.61%] | 44.44% |
| confirmation | low_minus_high | 36 | 0.13% | [-1.64%, 1.63%] | 41.67% |

## Annual portfolio returns

### Discovery

| Year | Low P/B | Baseline | High P/B |
|---|---:|---:|---:|
| 2018 | -19.26% | -19.54% | -22.43% |
| 2019 | -12.81% | -6.77% | -6.06% |
| 2020 | 14.77% | 21.67% | 34.63% |
| 2021 | 22.87% | 7.90% | -9.22% |
| 2022 | -11.01% | -18.55% | -28.11% |

### Confirmation

| Year | Low P/B | Baseline | High P/B |
|---|---:|---:|---:|
| 2023 | 15.60% | 14.87% | 6.99% |
| 2024 | -7.49% | -4.39% | -18.68% |
| 2025 | 47.67% | 48.98% | 63.23% |

## Exposure diagnostics

| Period | Portfolio | Market beta | Active momentum | Active log market cap | Sector active-weight distance |
|---|---|---:|---:|---:|---:|
| discovery | low_pbr | 1.047 | -0.140 | -0.357 | 27.77% |
| discovery | high_pbr | 0.949 | 0.209 | 0.323 | 31.42% |
| confirmation | low_pbr | 0.959 | -0.143 | -0.589 | 22.75% |
| confirmation | high_pbr | 1.120 | 0.255 | 0.363 | 26.43% |

## Regime diagnostics

| Period | Dimension | Regime | N | Low minus baseline | Low minus high |
|---|---|---|---:|---:|---:|
| discovery | market_direction | falling | 28 | -0.34% | -0.64% |
| discovery | market_direction | rising | 31 | 0.72% | 1.77% |
| discovery | volatility_regime | high | 29 | -0.27% | -0.18% |
| discovery | volatility_regime | low | 30 | 0.72% | 1.47% |
| confirmation | market_direction | falling | 16 | 1.28% | 4.02% |
| confirmation | market_direction | rising | 20 | -1.21% | -2.99% |
| confirmation | volatility_regime | high | 16 | 0.45% | 1.13% |
| confirmation | volatility_regime | low | 20 | -0.55% | -0.67% |

## Concentration diagnostics

- low_pbr: top-five absolute contribution share 17.20%; largest absolute contributors: A011210, A001230, A000150, A001120, A000240.
- high_pbr: top-five absolute contribution share 14.58%; largest absolute contributors: A267260, A012450, A003230, A019170, A042660.

## Diagnostics

- Eligibility audit: **failed**; minimum positive-P/B coverage 98.00%.
- Unresolved selected holding-return cases: 2. These invalidate the evidence decision under the frozen rule.
- Discovery-period high-volatility threshold: 16.83% annualized.
- Market beta is measured against the eligible equal-weight baseline; it is diagnostic, not hedged.
- Momentum and log-market-cap values are active weighted means versus the baseline.
- Sector diagnostics use unlabeled FGSC level-1 codes and are available only from 2020.
- Detailed regime, exposure, concentration, eligibility, and contribution results are preserved in the JSON/CSV artifacts.
- Missing case: A000030 in low_pbr for 2019-02; first missing date 2019-02-13.
- Missing case: A000030 in baseline for 2019-02; first missing date 2019-02-13.

## Limitations

- Historical P/B revision and point-in-time provenance are not documented.
- The exact corporate-action and dividend coverage of 기준가 and 수정계수 is not documented.
- FGSC classifications begin in 2020 and have no supplied label codebook.
- Results are gross of commissions, taxes, bid-ask spreads, and market impact.
- The study is research-only and is not evidence of real-world investability.

## Interpretation boundary

A completed run and an evidence classification are separate. This report does not model taxes, costs, spreads, market impact, shorting, hedging, or live execution. No parameter was changed after inspecting performance.
