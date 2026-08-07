# Qlib Target Profiles

## Purpose

A Qlib target profile is a versioned contract between qlibx logical datasets
and a Qlib-compatible provider directory. It fixes calendar, universe, feature,
dtype, missing-value, and capability semantics so different agents produce the
same result from the same registered inputs.

Raw column names and file formats belong to registration mappings. Profile
features use canonical names. The included project config demonstrates the
mapping until the full registration catalog is implemented.

## `qlib.research_daily/v1`

The initial profile supports research-only feature access:

| Contract | Meaning |
|---|---|
| Calendar | Open Korean stock-market days at daily frequency |
| `all` universe | Union of instruments with materialized feature observations |
| `k200` universe | Historical KOSPI 200 membership compressed into trading-day intervals |
| `$pbr` | Observed price-to-book value; zero is preserved for later eligibility rules |
| `$adjusted_daily_return` | `종가 / 기준가 - 1`; invalid/nonpositive inputs become missing |
| Storage dtype | Qlib-compatible little-endian float32 |

Execution is excluded. In particular, the DataGuide daily `수정계수` is not
renamed to Qlib `$factor`: the observed source value is an event-day adjustment,
while Qlib execution uses a cumulative factor for price and quantity behavior.

## Materialization config

The config schema is `qlibx.qlib_materialization/v1`. Each source declares:

- Stable logical `dataset_id`
- `type`: `csv`, `parquet`, or `duckdb`
- Project-relative `path`
- `table` for DuckDB sources
- Explicit date, instrument, and feature columns
- A bounded transform from the profile's allowed transform set

Supported transforms are currently:

- `field`: preserve one numeric source field
- `ratio_minus_one`: calculate `numerator / denominator - 1`, optionally
  requiring positive inputs

The built-in profile requires exactly `pbr` and `adjusted_daily_return`; unknown
or missing features fail before reading full data.

## Workflow

1. `data preflight` validates schema, paths, formats, required columns, and the
   profile contract without scanning full tables.
2. `data materialize` hashes source files, reads rows deterministically by
   instrument and date, and writes to a temporary provider directory.
3. Daily membership is compressed using trading-calendar adjacency, not ordinary
   calendar-day adjacency.
4. qlibx writes the Qlib calendar, named instrument files, and per-instrument
   feature binaries.
5. Structural validation checks calendars, intervals, binary headers, bounds,
   and required feature coverage.
6. The completed directory is atomically published. A conflicting existing
   target fails rather than being overwritten.

The materialization identity covers the producer and package version, complete
profile, config, and source-file hashes. The manifest records the same lineage.

## Output

```text
data/qlibx/qlib/research_daily_v1/
  calendars/day.txt
  instruments/all.txt
  instruments/k200.txt
  features/<instrument>/pbr.day.bin
  features/<instrument>/adjusted_daily_return.day.bin
  qlibx-manifest.json
```

Generated provider data and action-journal state are ignored by Git. The config,
profile implementation, tests, and documentation remain project-owned source.
The first-cycle provider includes trading data through 2026-01-05 solely to
close the December 2025 holding period at its next scheduled rebalance; no 2026
holding month is evaluated.

## Current limitations

- Historical P/B revision provenance is unknown.
- Exact corporate-action coverage of `기준가` and `수정계수` is undocumented.
- Qlib 0.9.8.dev32 was compiled from the sibling checkout under Python 3.12.
  Its public API loaded the full calendar and dynamic KOSPI 200 universe, and
  sample `$pbr` and `$adjusted_daily_return` values matched the binaries exactly.
  The repeatable smoke script and preserved result live under `scripts/` and
  `qlibx-research/`.
- Registration, eligibility-audit, and Korean execution profiles remain separate
  follow-up modules.
