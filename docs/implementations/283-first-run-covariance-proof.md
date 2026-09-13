# 283 - First-run covariance proof

## Why

The existing certificate removes spectral inspection only after one complete audited run. The
real 309-name, 64-scenario DataModel spent most of its first run inspecting eigenvalues even
though its covariance construction already implied a useful lower bound.

## Outcome

`ShrunkCovarianceSolver` accepts weighted observations, builds the covariance itself, and proves
when the configured spectral floor cannot activate. A successful proof goes directly to the
linear solve on the first run. An inconclusive proof runs the original eigendecomposition and
floor formula.

## Design

- The API does not accept an arbitrary covariance, so callers cannot make an unchecked claim.
- For `C=(1-s)X'X+s*diag(X'X)+rI`, the minimum eigenvalue is at least
  `r+s*min(diag(X'X))`.
- A trace-derived upper bound on the median gives a conservative floor upper bound.
- The direct path requires the lower bound to clear that upper bound plus a numerical margin.
- One solver reuses its covariance work area. Different shrinkage policies use different solvers.
- `SpectralFloorSolver` remains for unsupported constructions and repeat certificates.

## Trade-offs

- The proof is conservative; 192 of 134,080 real scenarios used the old formula.
- Real full-run peak RSS was 1.91 GB versus the earlier checked baseline's 562 MB. The memory gate
  failed, so this is an opt-in authoring helper, not an automatic engine rewrite.
- A solver owns mutable work memory and must not be shared concurrently.

## Validation

- Narrow tests: `uv run pytest tests/signals/test_spectral_floor.py tests/boundaries/test_public.py tests/acceptance/test_certified_risk_onboarding.py -q`
- Full package: `uv run pytest tests/ -q -m ""`
- Lint: `uv run ruff check src/`
- Types: `uv run pyright`
- Real journey: `uv run python experiments/exp_251_first_run_structural_proof/run.py --mode full`
- Real result: 136.94 seconds versus 640.06 seconds; factor parquet and economic results unchanged.
