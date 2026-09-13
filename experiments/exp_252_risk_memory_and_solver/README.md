# Risk memory and solver experiment

This concluded experiment measures the remaining first-run risk-model bottleneck on the fixed
real-data journey from `TEST-PLAN.md`.

- `run.py` reproduces calibration and full-period runs.
- `outputs/REPORT.md` is the human-readable conclusion.
- `outputs/validation.json` is the compact machine-readable evidence summary.
- Generated databases, Parquet files, and profiling traces remain ignored because they are large
  and can be recreated from the prepared private input.

The private source data is not committed. Reproduction therefore requires the same prepared DW
input recorded in `experiment.yaml`.
