# First-Cycle Closure: KOSPI 200 Low-P/B

Closed: 2026-08-08  
Frozen study: `k200-low-pbr-v1`  
Run ID: `cfd6578fac72ec9051c83df0b9133ac9db44fab53fde5d81f17ce0a2eccb09b0`  
Evidence classification: **INVALID**

## What this cycle established

The first cycle took one fundamental-investing idea from a written research
question through registered source data, Qlib-compatible materialization,
eligibility checks, deterministic portfolio construction, diagnostics,
reporting, and byte-for-byte reproduction.

The frozen comparison was monthly low-P/B KOSPI 200 stocks versus an eligible
equal-weight KOSPI 200 baseline and a high-P/B comparison portfolio. The
discovery period was 2018-2022 and the untouched confirmation period was
2023-2025. The implementation did not add shorting, hedging, transaction costs,
or execution simulation.

## Final decision

The study is **invalid under its preregistered data-quality rule**. `A000030`
was selected in both the low-P/B and baseline portfolios for February 2019, but
its adjusted holding returns are missing from 2019-02-13 through the exit date.
The supplied sources do not contain a registered successor or security-
conversion mapping. Filling, dropping, or replacing the security after seeing
the result would change the frozen experiment.

Performance outputs are therefore descriptive diagnostics only. In the
confirmation period, low P/B averaged -0.10% per month versus the baseline
(95% moving-block interval -1.02% to 0.61%) and +0.13% versus high P/B
(-1.64% to 1.63%). Neither comparison supplies robust confirmatory evidence,
even before the invalidating data issue is considered.

## Completion checklist

- Research question, universe, timing, portfolios, periods, missing-data rules,
  bootstrap method, diagnostics, and decision rules were frozen before the run.
- Calendar, KOSPI 200 membership/market cap, valuation/beta, prices, and sector
  sources were registered with explicit mappings, hashes, profiles, and
  immutable identities.
- Ambiguous mappings require user confirmation; registrations and builds are
  idempotent.
- The Qlib binary dataset was materialized and structurally validated.
- A public-Qlib-API smoke test independently reproduced sampled P/B and return
  values from the generated provider.
- Eligibility, membership changes, look-ahead timing, missing returns,
  corporate-action formula consistency, ties, turnover, and bootstrap behavior
  were tested.
- Monthly portfolios, daily and monthly returns, turnover, exposures, regimes,
  concentration, security contributions, decision, and provenance were
  preserved as artifacts.
- A second execution reproduced all frozen result artifacts byte for byte.
- Agent actions were recorded in the append-only journal.

## Preserved evidence

- `runs/k200-low-pbr-v1/evidence-report.md`: human-readable results and limits
- `runs/k200-low-pbr-v1/run-manifest.json`: immutable run identity and hashes
- `runs/k200-low-pbr-v1/decision.json`: machine-readable classification
- `runs/k200-low-pbr-v1/eligibility-audit.json`: blocking data issue and audit
- `runs/k200-low-pbr-v1/*.csv`: portfolios, returns, turnover, and contributions
- `qlib-public-api-smoke.json`: public Qlib compatibility check
- `k200-low-pbr-study-plan.md`: frozen design and implementation amendment

## Follow-up hypotheses and infrastructure

These are new work, not retroactive changes to `k200-low-pbr-v1`:

1. Register a point-in-time corporate-action/security-successor table, then
   preregister and run a `v2` study that explicitly handles conversions such as
   `A000030`.
2. Obtain or document revision history for P/B so a later study can establish
   that valuation observations were genuinely available on each decision date.
3. If the cleaned `v2` remains worth investigating, test whether any low-P/B
   effect survives sector, size, momentum, and market-risk controls.
4. Only after a signal survives those checks, add Korean-market transaction
   costs, taxes, bid-ask spreads, and execution constraints.

## Boundary

Completing the cycle means the process reached a reproducible, honest decision;
it does not mean the alpha was validated. No investment conclusion should be
drawn from this invalid study.
