# A long risk model: safe first run, fast repeat, then the strategy

## The answer first

- Keep the risk calculation in a DataModel when several strategies reuse its scores.
- Keep the portfolio choice in a StrategyModel. The two runs are separate and ordered.
- The first DataModel run must inspect every new risk matrix.
- An unchanged repeat may reuse only the inspection of the exact same matrix bytes.
- A changed date or value makes a new matrix digest and is inspected automatically.
- Deleting the certificate file changes only elapsed time. It does not change the calculation.

This path is for a model that repeatedly performs a symmetric eigendecomposition only to apply a
small-eigenvalue floor and solve one linear system. It is not a general cache for arbitrary Python
results.

## The whole path

```text
source files
    -> register and inspect the point-in-time datasets
    -> materialise the risk-score DataModel
         first run: inspect each matrix, then solve
         repeat:    reuse exact-matrix certificates, inspect new matrices
    -> register the materialised score dataset automatically
    -> check and run the StrategyModel that reads those scores
    -> read the report and export the result
```

Do not combine the DataModel run and the StrategyModel run in one batch. The second reads the
dataset written by the first, and vqapr refuses a batch whose member consumes another member's
output.

## 1. Start in a project that has vqapr

```bash
uv add vqapr
uv run vqapr skill install
uv run vqapr new sample --out ./first-run
uv run vqapr register ./first-run/sample.yaml
uv run vqapr check sample-run
uv run vqapr run sample-run
```

The sample proves that the environment and command path work. Its data is synthetic and is not
evidence for an investment idea.

## 2. Register the real inputs before calculating a factor

```bash
uv run vqapr new dataset --out research-data.yaml
uv run vqapr register research-data.yaml
uv run vqapr list datasets
uv run vqapr show dataset prices --limit 20
```

Fill the generated declaration only after the observation time, publication time, timezone, price
meaning, and missing-value meaning are settled. The **register-dataset** skill owns those decisions.
Do not prepare rolling momentum, ranks, or covariance in the source file; they belong in the
DataModel so their point-in-time inputs remain visible.

## 3. Generate the DataModel and keep its run separate

```bash
uv run vqapr new datamodel risk-scores --dataset prices --calendar-lookback 370
```

Keep the generated component shape and run declaration. Add every price, factor, and financial
dataset to `inputs()`. Use a calendar lookback for a cross-sectional covariance so every name is
measured over the same dates.

The generated run must write a reusable dataset, for example `risk-scores-output`. Run it daily if
the model genuinely produces a daily score. The later strategy may still rebalance weekly.

## 4. Replace only the expensive solve

Create one solver on the DataModel instance. The relative and absolute floors must be the same as
the old formula. Give each distinct model policy its own certificate path.

```python
from pathlib import Path

import numpy as np
from vqapr import public as vq


class RiskScores(vq.DataModel):
    def __init__(self) -> None:
        self._risk_solver = vq.SpectralFloorSolver(
            Path(".vqapr/cache/risk-scores-v1.certificates"),
            relative_floor=1e-3,
            absolute_floor=1e-7,
        )

    # Keep inputs() from the generated file and add the real registered inputs.

    def compute(self, call: vq.DataCall):
        # Build `covariance`, `signal`, `names`, and `eligible` only from call.read(...).
        # `covariance` must be a finite, exactly symmetric float matrix.
        adjusted_signal = self._risk_solver.solve(covariance, signal)

        # Flush once after all scenario solves in this callback. A crash may then lose a few
        # certificates and repeat their inspections, but can never lose a research result.
        self._risk_solver.close()

        return tuple(
            {"instrument": str(names[i]), "score": float(adjusted_signal[i])}
            for i in np.flatnonzero(eligible & np.isfinite(adjusted_signal))
        )
```

For 64 scenarios, call `solve()` 64 times and call `close()` once after the loop. Do not create a
solver inside that loop.

What the helper does:

1. Converts the matrix and target to contiguous 64-bit floats.
2. Refuses a non-square, non-finite, or non-symmetric system.
3. Hashes the exact matrix bytes and solver policy.
4. On a miss, checks the eigenvalues.
5. If the floor is active or numerically too close, runs the original full decomposition formula.
6. Otherwise solves directly and records the matrix digest.
7. On an exact repeat, skips only step 4 and solves directly.

The certificate is not a DataModel result, model state, or lineage record. It is disposable proof
for a performance shortcut. Keep it under `.vqapr/cache/`, out of source control. A malformed or
incompatible file is left untouched and ignored, so the safe inspection runs again.

## 5. Prove and run the DataModel first

```bash
uv run vqapr register risk_scores.yaml
uv run vqapr check risk-scores-run
time uv run vqapr run risk-scores-run
uv run vqapr list datasets
uv run vqapr show dataset risk-scores-values --limit 20
```

Record the first elapsed time. It includes the safety inspections. Confirm that the output row
count, dates, names, null policy, and score range are credible before a strategy reads it.

During a small standalone calculation, `solver.stats.as_record()` gives `audited`, `certified`,
`reused`, `floor_fallbacks`, and `margin_fallbacks`. Do not print from `compute()`: every vqapr CLI
command owns its one JSON output line. For the full run, compare the command elapsed times and the
certificate line count instead.

## 6. Repeat without weakening the check

```bash
time uv run vqapr run risk-scores-run --force
uv run vqapr show dataset risk-scores-values --limit 20
```

`--force` replaces the standing DataModel record and its materialised dataset together. It does not
mean “skip safety”. Exact matrices reuse certificates; changed and newly appended dates are audited.

Before accepting the speedup, compare the old and new materialised parquet files and the later
strategy's economic tables. Distinguish three claims:

- numeric values agree within the study's declared tolerance;
- instrument choices, weights, fills, holdings, and returns agree;
- files are byte-identical.

The third is strongest and is not implied by the first two. Component code changes also change the
run fingerprint even when every economic value agrees.

## 7. Build and execute the weekly long-short strategy

```bash
uv run vqapr new strategy weekly-risk-momentum --dataset risk-scores-values
uv run vqapr register weekly_risk_momentum.yaml
uv run vqapr new run --out weekly_risk_momentum_run.yaml
uv run vqapr register weekly_risk_momentum_run.yaml
uv run vqapr check weekly-risk-momentum-run
time uv run vqapr run weekly-risk-momentum-run
```

The StrategyModel reads the latest score, applies the real universe and tradability rules, and
returns a signed rebalance. Put the weekly cadence in the strategy run's `schedule`; do not make the
DataModel weekly merely to make the test faster if the research question needs daily values.

## 8. Read and export the result

```bash
uv run vqapr show run weekly-risk-momentum-run
uv run vqapr list strategies --run weekly-risk-momentum-run
uv run vqapr export weekly-risk-momentum-run/<strategy-record> --out outputs/
```

Use `strategy_report` for returns, drawdown, turnover, costs, and exposure. The **analyze-result**
skill owns interpretation and figures.

## Stop condition

- DataModel `check` and `run` succeed and its output is registered.
- Strategy `check` and `run` succeed after the DataModel.
- The first and repeat times are reported separately.
- New or changed matrices were not treated as cache hits.
- Old and new economic outputs were compared, not just elapsed time.
- The exported files and the limits of the point-in-time assumptions were handed to the user.
