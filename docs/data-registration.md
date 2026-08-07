# Dataset Registration

The first-cycle registry separates source syntax from canonical financial
semantics. Its bundle schema is `qlibx.dataset_registration_bundle/v1`.

Each dataset declares a versioned dataset ID, project-relative CSV/Parquet/
DuckDB source, canonical required fields, explicit source-column mappings,
candidate key, date field/format, confirmation state, and limitations.

`data inspect` reads headers and resolves only unambiguous aliases. A missing or
ambiguous mapping returns `mapping_confirmation_required`; agents must ask the
user rather than guess. `data register` accepts only `mapping_confirmed: true`,
profiles row/date/key coverage, hashes the complete source and implementation,
and publishes immutable registration records under `data/qlibx/registry/`.

The included first-cycle bundle registers:

- Korean trading calendar
- Point-in-time KOSPI 200 membership and market capitalization
- Daily P/B and beta
- Daily price/corporate-action inputs
- Point-in-time FGSC classification

Reusing identical content is idempotent. Reusing a dataset ID for changed
source content or semantics fails and requires a new dataset version.
