# qlibx

`qlibx` provides agent-facing, reproducible alpha-research interfaces around
[Qlib](https://github.com/microsoft/qlib). The current implementation focuses on
safe research-data materialization rather than execution.

## First project: KOSPI 200 low P/B

The first research cycle tests whether the lowest-P/B KOSPI 200 stocks
outperform an eligible equal-weight baseline and the highest-P/B stocks. It
covers 2018-2025, with 2018-2022 used for discovery and 2023-2025 reserved for
confirmation.

The cycle completed reproducibly but was classified **invalid**: a selected
February 2019 holding (`A000030`) has unresolved returns and no registered
successor or corporate-action conversion. Performance is therefore descriptive
only and supports no investment conclusion.

- [HTML presentation](qlibx-research/first-cycle-presentation.html)
- [Cycle closure](qlibx-research/first-cycle-closure.md)
- [Evidence report](qlibx-research/runs/k200-low-pbr-v1/evidence-report.md)
- [Frozen study design](qlibx-research/k200-low-pbr-study-plan.md)

## First target profile

`qlib.research_daily/v1` publishes:

- A daily Korean trading calendar
- Dynamic `all` and `k200` instrument universes
- `$pbr`
- `$adjusted_daily_return`, calculated as `종가 / 기준가 - 1`

It intentionally does **not** publish Qlib `$close`, `$factor`, volume,
tradability, transaction-cost, or Korean execution settings. The resulting
dataset is suitable for eligibility and signal research, not order simulation.

## Commands

Install the project environment:

```bash
uv sync
```

Inspect installed profiles:

```bash
uv run qlibx profile list
uv run qlibx profile show qlib.research_daily/v1
```

Inspect and register confirmed source mappings:

```bash
uv run qlibx data inspect \
  --config config/qlibx/k200-low-pbr-registrations.json
uv run qlibx data register \
  --config config/qlibx/k200-low-pbr-registrations.json
```

Validate source formats and mapped columns without reading the full datasets:

```bash
uv run qlibx data preflight \
  --config config/qlibx/k200-research-materialization.json
```

Materialize the research dataset atomically:

```bash
uv run qlibx data materialize \
  --config config/qlibx/k200-research-materialization.json
```

Validate an existing result:

```bash
uv run qlibx data validate \
  --target data/qlibx/qlib/research_daily_v1
```

Run the preregistered eligibility audit and frozen study:

```bash
uv run qlibx research audit \
  --config config/qlibx/k200-low-pbr-study.json
uv run qlibx research run \
  --config config/qlibx/k200-low-pbr-study.json
```

Running the study command again recomputes every deterministic result artifact
and fails if it differs from the frozen run.

Query lifecycle events:

```bash
uv run qlibx journal query --action research.run.execute --limit 20
```

Commands accept `--project-root` before the command when invoked outside the
repository root.

## Guarantees

- Source files are read-only and must use project-relative paths.
- CSV, Parquet, and DuckDB sources share the same explicit mapping contract.
- Materialization writes to a temporary directory and publishes by atomic rename.
- Existing output with different provenance is never overwritten.
- Identical source/config/profile content reuses the verified materialization.
- Calendar, universe, and feature keys are validated before publication.
- Producer identity, source hashes, mappings, limitations, counts, and validation
  results are saved in `qlibx-manifest.json`.
- Every public operation writes append-only lifecycle events under `.qlibx/`.
- Registration, materialization, and research identities include the exact
  implementation hash as well as package/config/source identities.

See [Qlib target profiles](docs/qlib-target-profiles.md), the
[action-journal contract](docs/agent-action-journal-contract.md), and the
[product requirements](docs/qlibx-prd.md) for details.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```
