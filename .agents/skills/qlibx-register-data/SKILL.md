---
name: qlibx-register-data
description: Inspect and register CSV, Parquet, or DuckDB financial datasets in qlibx with canonical column mappings, immutable source identity, validation, and action-journal provenance. Use when adding a dataset, mapping unfamiliar headers, converting registered inputs into a Qlib target profile, or diagnosing a registration/mapping failure.
---

# Qlibx Register Data

Register data through qlibx's validated contract. Never modify the raw source.

## Workflow

1. Work from the qlibx project root and keep every source path project-relative.
2. Create or update a `qlibx.dataset_registration_bundle/v1` JSON config. Declare a stable dataset ID, source format/path, canonical required fields, key, date field/format, and known limitations.
3. Run:

   ```bash
   uv run qlibx data inspect --config <project-relative-config.json>
   ```

4. Review `available_columns` and `resolved_mapping`. Accept an automatic proposal only when one source column matches a canonical field unambiguously.
5. If a field has zero or multiple plausible matches, stop and ask the user which source column and semantic meaning are intended. Show the candidates and do not set `mapping_confirmed` to `true` until answered.
6. After confirmation, set explicit `mappings` and `mapping_confirmed: true`, then run:

   ```bash
   uv run qlibx data register --config <project-relative-config.json>
   ```

7. Confirm the command returns stable registration IDs, zero duplicate key groups unless explicitly accepted, and the expected row/date coverage. Re-run once to verify `reused: true`.
8. Materialize only through a versioned Qlib target profile. Run its preflight before materialization.

## Safety and semantics

- Treat headers as syntax and canonical mappings as semantics; similar names are not sufficient evidence.
- Preserve identifier and date strings during ingestion.
- Record unknown point-in-time, revision, unit, and corporate-action semantics as accepted limitations.
- Do not overwrite a dataset ID whose registered source or mapping changed. Use a new versioned dataset ID.
- Do not expose secrets, raw rows, or large data samples in the action journal.
- Use `uv run qlibx journal query --action data.registration.create` to inspect the audit trail.
