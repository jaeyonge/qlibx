from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from qlibx.materialization import (
    materialize_from_config,
    preflight_materialization_config,
    validate_qlib_store,
)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class MaterializationTest(unittest.TestCase):
    def test_materializes_qlib_layout_and_reuses_identical_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_csv(
                root / "calendar.csv",
                ["date", "open"],
                [
                    {"date": "20200102", "open": "0"},
                    {"date": "20200103", "open": "0"},
                    {"date": "20200104", "open": "1"},
                    {"date": "20200106", "open": "0"},
                    {"date": "20200131", "open": "0"},
                    {"date": "20200203", "open": "0"},
                ],
            )
            _write_csv(
                root / "members.csv",
                ["instrument", "date"],
                [
                    {"instrument": "A", "date": "20200102"},
                    {"instrument": "A", "date": "20200103"},
                    {"instrument": "A", "date": "20200106"},
                    {"instrument": "A", "date": "20200131"},
                    {"instrument": "A", "date": "20200203"},
                    {"instrument": "B", "date": "20200102"},
                    {"instrument": "B", "date": "20200103"},
                    {"instrument": "C", "date": "20200131"},
                    {"instrument": "C", "date": "20200203"},
                ],
            )
            feature_rows = []
            price_rows = []
            for instrument, base_pbr in (("A", 1.0), ("B", 2.0), ("C", 3.0)):
                for offset, current in enumerate(
                    ("20200102", "20200103", "20200106", "20200131", "20200203")
                ):
                    feature_rows.append(
                        {
                            "instrument": instrument,
                            "date": current,
                            "pbr_raw": base_pbr + offset / 10,
                        }
                    )
                    price_rows.append(
                        {
                            "instrument": instrument,
                            "date": current,
                            "close": 101 + offset,
                            "base": 100 + offset,
                        }
                    )
            _write_csv(
                root / "valuation.csv", ["instrument", "date", "pbr_raw"], feature_rows
            )
            _write_csv(
                root / "prices.csv", ["instrument", "date", "close", "base"], price_rows
            )
            config = {
                "schema": "qlibx.qlib_materialization/v1",
                "profile_id": "qlib.research_daily/v1",
                "output_dir": "output/research",
                "start_date": "2020-01-02",
                "end_date": "2020-02-03",
                "calendar": {
                    "source": {
                        "dataset_id": "calendar/v1",
                        "type": "csv",
                        "path": "calendar.csv",
                    },
                    "date_column": "date",
                    "date_format": "%Y%m%d",
                    "include": {"column": "open", "values": ["0"]},
                },
                "universes": [
                    {
                        "name": "k200",
                        "source": {
                            "dataset_id": "members/v1",
                            "type": "csv",
                            "path": "members.csv",
                        },
                        "instrument_column": "instrument",
                        "date_column": "date",
                        "date_format": "%Y%m%d",
                    }
                ],
                "features": [
                    {
                        "name": "pbr",
                        "source": {
                            "dataset_id": "valuation/v1",
                            "type": "csv",
                            "path": "valuation.csv",
                        },
                        "instrument_column": "instrument",
                        "date_column": "date",
                        "date_format": "%Y%m%d",
                        "transform": {"kind": "field", "column": "pbr_raw"},
                    },
                    {
                        "name": "adjusted_daily_return",
                        "source": {
                            "dataset_id": "prices/v1",
                            "type": "csv",
                            "path": "prices.csv",
                        },
                        "instrument_column": "instrument",
                        "date_column": "date",
                        "date_format": "%Y%m%d",
                        "transform": {
                            "kind": "ratio_minus_one",
                            "numerator": "close",
                            "denominator": "base",
                            "require_positive_inputs": True,
                        },
                    },
                ],
                "accepted_limitations": ["fixture limitation"],
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            preflight = preflight_materialization_config(
                config_path,
                project_root=root,
                actor_id="test-agent",
                session_id="test-session",
            )
            self.assertEqual(preflight["status"], "passed")
            self.assertEqual(len(preflight["sources"]), 4)

            manifest = materialize_from_config(
                config_path,
                project_root=root,
                actor_id="test-agent",
                session_id="test-session",
            )
            target = root / "output" / "research"

            self.assertEqual(manifest["validation"]["status"], "passed")
            self.assertEqual(
                manifest["producer"]["id"], "qlibx.qlib_binary_materializer"
            )
            self.assertEqual(manifest["calendar"]["count"], 5)
            self.assertEqual(
                manifest["validation"]["universes"]["k200"]["instruments"], 3
            )
            self.assertEqual(
                (target / "calendars" / "day.txt").read_text().splitlines()[0],
                "2020-01-02",
            )
            self.assertTrue(
                (target / "instruments" / "all.txt").read_text().startswith("A\t")
            )
            pbr = np.fromfile(target / "features" / "a" / "pbr.day.bin", dtype="<f4")
            returns = np.fromfile(
                target / "features" / "a" / "adjusted_daily_return.day.bin", dtype="<f4"
            )
            self.assertEqual(pbr[0], 0)
            np.testing.assert_allclose(pbr[1:], [1.0, 1.1, 1.2, 1.3, 1.4], rtol=1e-6)
            np.testing.assert_allclose(returns[1], 0.01, rtol=1e-6)
            self.assertEqual(validate_qlib_store(target)["status"], "passed")

            reused = materialize_from_config(
                config_path,
                project_root=root,
                actor_id="test-agent",
                session_id="test-session",
            )
            self.assertEqual(
                reused["materialization_id"], manifest["materialization_id"]
            )

            events = [
                json.loads(line)
                for line in (root / ".qlibx" / "events" / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(events[-1]["phase"], "succeeded")
            self.assertTrue(events[-1]["outputs"]["result_summary"]["reused"])


if __name__ == "__main__":
    unittest.main()
