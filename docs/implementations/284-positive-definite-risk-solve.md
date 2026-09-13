# 284 - Positive-definite risk solve

## Why

After structural proof removed the first-run eigenvalue inspection, the general linear solve was
89.34 of the remaining 112.64 DataModel seconds. The supported covariance is positive definite
whenever the structural proof succeeds, so a general solver was doing unnecessary work.

## Outcome

The proved path now uses SciPy's Cholesky factorization and solve. The proof remains in front of
the fast path. An inconclusive proof or factorization failure uses the existing eigendecomposition
and spectral-floor formula.

## Dependencies

- Added runtime dependency `scipy>=1.18,<2` from the public Python package index.
- SciPy 1.18 supports the package's declared Python 3.12 through 3.14 range.
- The lock changed only to make SciPy a direct vqapr dependency; NumPy was already present.

## Alternatives

- Two NumPy triangular solves were 2.3 times slower than the general NumPy solve and were rejected.
- An unchecked SciPy solve was used only as a speed ceiling, then replaced by the structural proof
  plus fallback candidate.
- Covariance reuse and incremental covariance remained rejected because they changed last-bit
  results and saved little whole-run time.

## Validation

- Real 309-name, 2,095-day, 64-scenario journey, three alternating full runs.
- Baseline median: 123.75 seconds overall, 111.03 seconds DataModel.
- Candidate median: 91.27 seconds overall, 78.45 seconds DataModel.
- All three factor parquet files have the unchanged SHA-256
  `e50702562ba46f73296f7c14da38f205ae9bb5c10ea6259d42d56770e688f9d0`.
- Structural proof: 133,888 of 134,080; 192 conservative fallbacks; zero active floors.
- `vmmap` physical-footprint peak: 302.5 MB. The 2.21 GB sampled RSS included shared and reserved
  mappings and was not retained physical memory.
- Exact package validation commands and final counts are recorded when the full suite completes.
- `uv run pytest tests/ -q -m ""`: 1,816 passed, 6 skipped on the primary Python 3.12 environment.
- Fresh Python 3.12.4, 3.13.1, and 3.14.7 environments: 1,815 passed and 6 skipped on each before
  the final factorization-failure unit test was added; install and import succeeded on all three.
- `uv run ruff check src/`: passed.
- `uv run pyright`: 0 errors.
- `uvx uv@latest lock --check`: passed.
- `uvx uv@latest build --no-sources`: wheel and sdist built.
- The wheel installed and completed a public solver smoke test in fresh Python 3.12, 3.13, and
  3.14 environments.

## Limitations

- The improvement applies only to the supported shrunk covariance construction.
- Cholesky changes low-order floating-point values, though the full emitted factor file and all
  economic results in the fixed real journey are unchanged.
- Solver instances own mutable work memory and are not for concurrent sharing.
