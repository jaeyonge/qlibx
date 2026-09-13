"""Run the frozen real-data journey with the structural first-run solver."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = Path(
    "/Users/jason/Documents/Codex/2026-09-10/vqapr-015-performance/experiments/"
    "exp_253_daily_risk_solver/candidate"
)


def _prepare_driver() -> Path:
    driver = HERE / "driver"
    driver.mkdir(exist_ok=True)
    source = (OLD / "models.py").read_text(encoding="utf-8")
    source = source.replace(
        '_METRICS: dict[str, float] = {}',
        '_METRICS: dict[str, float] = {}\n_STRUCTURAL_SOLVERS = {}',
    )
    old_build = '''            with stage("covariance_build"):
                weighted = clean * np.sqrt(weights[:, None])
                covariance = weighted.T @ weighted
                diagonal = np.diag(covariance).copy()
        with stage("regularize"):
            shrinkage = 0.05 + 0.02 * stress
            covariance *= 1.0 - shrinkage
            covariance.flat[:: covariance.shape[0] + 1] += shrinkage * diagonal + 1e-6
        target = np.nan_to_num(alpha, nan=0.0)
'''
    new_build = '''            weighted = clean * np.sqrt(weights[:, None])
            if variant != "direct":
                with stage("covariance_build"):
                    covariance = weighted.T @ weighted
                    diagonal = np.diag(covariance).copy()
        shrinkage = 0.05 + 0.02 * stress
        if variant != "direct":
            with stage("regularize"):
                covariance *= 1.0 - shrinkage
                covariance.flat[:: covariance.shape[0] + 1] += shrinkage * diagonal + 1e-6
        target = np.nan_to_num(alpha, nan=0.0)
'''
    old = '''        elif variant in {"direct", "combined"}:
            with stage("eigenvalue_check"):
                checked_eigenvalues = np.linalg.eigvalsh(covariance)
                checked_floor = max(
                    float(np.median(checked_eigenvalues)) * 1e-3, 1e-7
                )
            floor_is_active = bool(np.any(checked_eigenvalues < checked_floor))
            _CALLS["floor_active"] += int(floor_is_active)
            _METRICS["largest_floor"] = max(
                _METRICS.get("largest_floor", 0.0), checked_floor
            )
            _METRICS["smallest_eigenvalue"] = min(
                _METRICS.get("smallest_eigenvalue", float("inf")),
                float(checked_eigenvalues[0]),
            )
            if not floor_is_active:
                _CALLS["direct_fast_path"] += 1
                with stage("direct_solve"):
                    precision = np.linalg.solve(covariance, target)
            else:
                _CALLS["direct_fallback"] += 1
                with stage("eigendecomposition"):
                    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
                    floor = max(float(np.median(eigenvalues)) * 1e-3, 1e-7)
                    precision = eigenvectors @ (
                        (eigenvectors.T @ target) / np.maximum(eigenvalues, floor)
                    )
'''
    new = '''        elif variant == "direct":
            solver = _STRUCTURAL_SOLVERS.get(shrinkage)
            if solver is None:
                solver = vq.ShrunkCovarianceSolver(shrinkage=shrinkage, ridge=1e-6)
                _STRUCTURAL_SOLVERS[shrinkage] = solver
            before = solver.stats
            with stage("structural_solve"):
                solved = solver.solve(weighted, target)
            precision = solved.solution
            diagonal = solved.diagonal
            after = solver.stats
            _CALLS["structural_proved"] += after.proved - before.proved
            _CALLS["structural_audited"] += after.audited - before.audited
            _CALLS["floor_active"] += after.floor_fallbacks - before.floor_fallbacks
'''
    if old_build not in source or old not in source:
        raise RuntimeError("frozen intensive model no longer matches the test contract")
    transformed = source.replace(old_build, new_build).replace(old, new)
    (driver / "models.py").write_text(transformed, encoding="utf-8")
    (driver / "exchange.py").write_bytes((OLD / "exchange.py").read_bytes())
    (driver / "certificate.py").write_bytes((OLD / "certificate.py").read_bytes())
    return driver


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("calibration", "full"), required=True)
    args = parser.parse_args()
    output = HERE / "outputs" / "direct" / args.mode
    if output.exists():
        shutil.rmtree(output)
    driver = _prepare_driver()
    spec = importlib.util.spec_from_file_location("first_run_driver", OLD / "run_experiment.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the frozen user-path driver")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(driver))
    spec.loader.exec_module(module)
    module.HERE = driver
    sys.argv = [sys.argv[0], "--mode", args.mode, "--variant", "direct"]
    module.main()


if __name__ == "__main__":
    main()
