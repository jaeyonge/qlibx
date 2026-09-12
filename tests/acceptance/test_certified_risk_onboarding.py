"""The installed-user order: DataModel twice, then the strategy and export.

The sample panel proves the public journey, not investment performance. The large real-DW timing
evidence remains experiment 253.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vqapr.cli.main import main

NAMES = "\n".join(f"    - K{index:06d}" for index in range(1, 11))

DATA_MODEL = '''\
from pathlib import Path
import numpy as np
from vqapr import public as vq

class RiskScores(vq.DataModel):
    def __init__(self):
        self.solver = vq.SpectralFloorSolver(Path(".vqapr/cache/risk.certificates"))

    def inputs(self):
        return {"prices": vq.DatasetInput(
            dataset_id="sample-prices", fields=("close",),
            lookback=vq.CalendarLookback(days=30, timezone="Asia/Seoul"),
        )}

    def compute(self, call):
        window = call.read("prices", "close")
        prices = window.matrix()
        if prices.shape[0] < 2:
            return []
        with np.errstate(divide="ignore", invalid="ignore"):
            returns = prices[1:] / prices[:-1] - 1.0
        clean = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
        covariance = clean.T @ clean / max(clean.shape[0], 1)
        covariance.flat[:: covariance.shape[0] + 1] += 1e-6
        target = clean[-1]
        score = self.solver.solve(covariance, target)
        self.solver.close()
        return [
            {"instrument": name, "value": float(score[index])}
            for index, name in enumerate(window.instruments)
            if np.isfinite(score[index])
        ]
'''

STRATEGY = '''\
from vqapr import public as vq

class WeeklyRisk(vq.StrategyModel):
    def inputs(self):
        return {"risk": vq.DatasetInput(
            dataset_id="risk-scores-values", fields=("value",),
            lookback=vq.RowsLookback(rows=1),
        )}

    def decide(self, call):
        score = call.read("risk", "value").current()
        chosen = dict(sorted(score.items(), key=lambda item: (item[1], item[0]))[-2:])
        if not chosen:
            return vq.Hold(reason="no risk score is available")
        return vq.Rebalance.of(long={name: 1 for name in chosen}, invested="0.9")
'''


def _cli(capsys: pytest.CaptureFixture[str], root: Path, *args: str) -> dict:
    code = main(["--project-root", str(root), *args])
    output = capsys.readouterr().out.strip()
    body = json.loads(output.splitlines()[-1])
    assert code == 0 and body["ok"] is True, body
    return body


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.uc("UC-AGENT-001")
def test_a_risk_datamodel_is_materialized_before_its_strategy_runs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _cli(capsys, tmp_path, "new", "sample", "--out", "first-run")
    _cli(capsys, tmp_path, "register", "first-run/sample.yaml")
    _cli(capsys, tmp_path, "check", "sample-run")
    _cli(capsys, tmp_path, "run", "sample-run")

    (tmp_path / "risk_scores.py").write_text(DATA_MODEL, encoding="utf-8")
    (tmp_path / "risk_scores.yaml").write_text(
        f'''\
components:
  risk-scores:
    kind: datamodel
    path: risk_scores.py
    object_name: RiskScores
runs:
  risk-scores-run:
    instruments:
{NAMES}
    start: '2022-01-04T00:00:00+09:00'
    end: '2024-12-30T23:59:59+09:00'
    timezone: Asia/Seoul
    schedule: {{every: 1d, at: '08:00', days_from: sample-prices}}
    writes: risk-scores-values
    datamodel:
      component: risk-scores
      value_fields: [value]
''',
        encoding="utf-8",
    )
    _cli(capsys, tmp_path, "register", "risk_scores.yaml")
    _cli(capsys, tmp_path, "check", "risk-scores-run")
    first = _cli(capsys, tmp_path, "run", "risk-scores-run")
    assert first["datamodels"]["risk-scores"]["rows"] > 6_000
    output = tmp_path / ".vqapr/materialized/risk-scores-values/all.parquet"
    first_digest = _digest(output)
    certificate = tmp_path / ".vqapr/cache/risk.certificates"
    first_certificate_lines = len(certificate.read_text(encoding="ascii").splitlines())

    repeated = _cli(capsys, tmp_path, "run", "risk-scores-run", "--force")
    assert repeated["datamodels"]["risk-scores"]["rows"] == first["datamodels"][
        "risk-scores"
    ]["rows"]
    assert _digest(output) == first_digest
    assert len(certificate.read_text(encoding="ascii").splitlines()) == first_certificate_lines

    (tmp_path / "weekly_risk.py").write_text(STRATEGY, encoding="utf-8")
    (tmp_path / "weekly_risk.yaml").write_text(
        f'''\
components:
  weekly-risk:
    kind: strategy
    path: weekly_risk.py
    object_name: WeeklyRisk
runs:
  weekly-risk-run:
    instruments:
{NAMES}
    start: '2022-01-04T00:00:00+09:00'
    end: '2024-12-30T23:59:59+09:00'
    timezone: Asia/Seoul
    schedule: {{every: 1w, on: last, at: '08:00'}}
    exchange: sample-exchange
    execution:
      dataset: sample-execution
      trade_price: close
      fill: {{at: '15:30'}}
    initial_account: {{cash: '100000000', mode: LONG_ONLY, positions: {{}}}}
    writes: weekly-risk-weights
    strategy: {{component: weekly-risk}}
''',
        encoding="utf-8",
    )
    _cli(capsys, tmp_path, "register", "weekly_risk.yaml")
    _cli(capsys, tmp_path, "check", "weekly-risk-run")
    strategy = _cli(capsys, tmp_path, "run", "weekly-risk-run")
    outcome = strategy["strategies"]["weekly-risk"]
    assert outcome["status"] == "completed" and outcome["fills"]["dealt"] > 0

    _cli(
        capsys,
        tmp_path,
        "export",
        f"weekly-risk-run/{outcome['record']}",
        "--out",
        "outputs",
    )
    assert {"nav.csv", "holdings.csv", "fills.csv", "weights.csv", "report.json"} <= {
        path.name for path in (tmp_path / "outputs").iterdir()
    }

