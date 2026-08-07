from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import qlib
from qlib.data import D


def direct_value(
    provider: Path, instrument: str, field: str, calendar_index: int
) -> float:
    path = provider / "features" / instrument.lower() / f"{field}.day.bin"
    raw = np.fromfile(path, dtype="<f4")
    start = int(raw[0])
    offset = calendar_index - start + 1
    return float(raw[offset]) if 1 <= offset < len(raw) else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    provider = args.provider.resolve()
    qlib.init(
        provider_uri=str(provider),
        region="cn",
        expression_cache=None,
        dataset_cache=None,
        kernels=1,
    )
    calendar = D.calendar(start_time="2018-01-02", end_time="2026-01-05", freq="day")
    features = D.features(
        D.instruments("k200"),
        ["$pbr", "$adjusted_daily_return"],
        start_time="2025-12-29",
        end_time="2026-01-05",
        freq="day",
        disk_cache=0,
    )
    finite = features.dropna().iloc[0]
    instrument, timestamp = finite.name
    date_text = timestamp.strftime("%Y-%m-%d")
    calendar_text = [str(item)[:10] for item in calendar]
    calendar_index = calendar_text.index(date_text)
    direct_pbr = direct_value(provider, instrument, "pbr", calendar_index)
    direct_return = direct_value(
        provider, instrument, "adjusted_daily_return", calendar_index
    )
    result = {
        "status": "passed"
        if np.isclose(finite["$pbr"], direct_pbr)
        and np.isclose(finite["$adjusted_daily_return"], direct_return)
        else "failed",
        "qlib_version": qlib.__version__,
        "calendar_count": len(calendar),
        "calendar_start": calendar_text[0],
        "calendar_end": calendar_text[-1],
        "feature_rows": len(features),
        "feature_columns": list(features.columns),
        "instruments": features.index.get_level_values("instrument").nunique(),
        "finite_pbr": int(np.isfinite(features["$pbr"]).sum()),
        "finite_adjusted_daily_return": int(
            np.isfinite(features["$adjusted_daily_return"]).sum()
        ),
        "sample_comparison": {
            "instrument": instrument,
            "date": date_text,
            "qlib_pbr": float(finite["$pbr"]),
            "direct_pbr": direct_pbr,
            "qlib_adjusted_daily_return": float(finite["$adjusted_daily_return"]),
            "direct_adjusted_daily_return": direct_return,
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
