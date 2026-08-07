from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from qlibx.research import (
    QlibBinaryStore,
    StudyConfig,
    _bootstrap_ci,
    _portfolio_month,
    _select_portfolios,
    _turnover,
    build_holding_schedule,
)


def _feature(path: Path, values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.asarray([0, *values], dtype="<f4").tofile(path)


class ResearchTest(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[StudyConfig, QlibBinaryStore]:
        provider = root / "provider"
        (provider / "calendars").mkdir(parents=True)
        (provider / "instruments").mkdir()
        calendar = [
            "2020-01-30",
            "2020-01-31",
            "2020-02-03",
            "2020-02-28",
            "2020-03-02",
            "2020-03-31",
            "2020-04-01",
        ]
        (provider / "calendars" / "day.txt").write_text("\n".join(calendar) + "\n")
        (provider / "instruments" / "k200.txt").write_text(
            "A\t2020-01-30\t2020-01-31\n"
            "B\t2020-01-30\t2020-03-31\n"
            "C\t2020-01-30\t2020-03-31\n"
            "D\t2020-01-30\t2020-03-31\n"
            "E\t2020-01-30\t2020-03-31\n"
            "F\t2020-02-03\t2020-03-31\n",
            encoding="utf-8",
        )
        pbrs = {
            "A": [1, 1, 1, 1, 1, 1, 1],
            "B": [1, 1, 1, 2, 2, 2, 2],
            "C": [1, 2, 2, 3, 3, 3, 3],
            "D": [1, 3, 3, 4, 4, 4, 4],
            "E": [1, 4, 4, 5, 5, 5, 5],
            "F": [9, 9, 9, 1, 1, 1, 1],
        }
        for instrument, values in pbrs.items():
            _feature(provider / "features" / instrument.lower() / "pbr.day.bin", values)
            returns = [
                0.0,
                0.0,
                0.0,
                0.01,
                1.0 if instrument == "B" else 0.01,
                0.01,
                0.01,
            ]
            _feature(
                provider
                / "features"
                / instrument.lower()
                / "adjusted_daily_return.day.bin",
                returns,
            )
        config = {
            "schema": "qlibx.research_study/v1",
            "study_id": "fixture/v1",
            "provider_dir": "provider",
            "registry_dir": "registry",
            "output_dir": "output",
            "audit_output": "audit.json",
            "periods": {
                "discovery": ["2020-01-01", "2020-12-31"],
                "confirmation": ["2021-01-01", "2021-12-31"],
                "reserved_from": "2021-01-01",
            },
            "portfolio": {"tail_fraction": 0.2, "weighting": "equal"},
            "statistics": {
                "confidence_interval": "moving_block_bootstrap",
                "confidence_level": 0.95,
                "bootstrap_block_months": 2,
                "bootstrap_resamples": 500,
                "seed": 7,
                "annualization_days": 252,
            },
            "diagnostics": {
                "momentum_lookback_days": 4,
                "momentum_skip_days": 1,
                "extreme_return_threshold": 0.3,
            },
        }
        config_path = root / "study.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        return StudyConfig.load(config_path), QlibBinaryStore(provider)

    def test_schedule_membership_ties_missing_and_extreme_returns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, store = self._fixture(root)
            schedules = build_holding_schedule(store, config)
            self.assertEqual(
                [item.holding_month for item in schedules], ["2020-02", "2020-03"]
            )
            pbr = store.feature_matrix("pbr")
            selected, summary = _select_portfolios(store, pbr, schedules[0], 0.2)
            self.assertEqual(summary["members"], 5)
            self.assertEqual(
                [store.instruments[item] for item in selected["low_pbr"]], ["A"]
            )
            # Future P/B cannot change an already formed portfolio.
            pbr[store.instrument_index["A"], -1] = 999
            repeated, _ = _select_portfolios(store, pbr, schedules[0], 0.2)
            self.assertEqual(repeated["low_pbr"], selected["low_pbr"])

            result, _, _ = _portfolio_month(
                "baseline",
                selected["baseline"],
                schedules[0],
                store,
                pbr,
                store.feature_matrix("adjusted_daily_return"),
                {},
                {},
                config,
            )
            self.assertIsNotNone(result["return"])
            self.assertGreater(
                result["return"], 0.2
            )  # the split-like 100% return is compounded, not clipped

            returns = store.feature_matrix("adjusted_daily_return")
            returns[store.instrument_index["A"], schedules[0].exit_index] = np.nan
            missing_result, _, _ = _portfolio_month(
                "low_pbr",
                selected["low_pbr"],
                schedules[0],
                store,
                pbr,
                returns,
                {},
                {},
                config,
            )
            self.assertIsNone(missing_result["return"])

    def test_turnover_and_bootstrap_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, _ = self._fixture(Path(directory))
            self.assertAlmostEqual(_turnover({"A": 0.5, "B": 0.5}, {"A": 1.0}), 0.5)
            values = [0.01, -0.02, 0.03, 0.04, -0.01]
            self.assertEqual(
                _bootstrap_ci(values, config), _bootstrap_ci(values, config)
            )


if __name__ == "__main__":
    unittest.main()
