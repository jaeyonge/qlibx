"""Compare current-environment direct and structural solves on the frozen real journey."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "exp_251_first_run_structural_proof" / "run.py"


def _load_previous():
    spec = importlib.util.spec_from_file_location("previous_risk_experiment", PREVIOUS)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the preceding frozen experiment")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("calibration", "full"), required=True)
    parser.add_argument(
        "--engine",
        choices=("scipy", "simple", "structural", "structural-scipy"),
        required=True,
    )
    parser.add_argument("--trial", type=int, required=True)
    args = parser.parse_args()
    previous = _load_previous()
    previous.HERE = HERE
    original_prepare = previous._prepare_driver

    if args.engine in {"scipy", "simple", "structural-scipy"}:
        def prepare_simple() -> Path:
            driver = original_prepare()
            path = driver / "models.py"
            source = path.read_text(encoding="utf-8")
            if args.engine in {"scipy", "structural-scipy"}:
                source = source.replace(
                    "import numpy as np\n",
                    "import numpy as np\nimport subprocess\nfrom scipy.linalg import cho_factor, cho_solve\n",
                )
                source = source.replace(
                    "atexit.register(_flush)\n",
                    '''atexit.register(_flush)

def _write_memory_map():
    target = os.environ.get("INTENSIVE_TIMING_PATH")
    if target:
        completed = subprocess.run(
            ["vmmap", "-summary", str(os.getpid())], capture_output=True, text=True
        )
        Path(target).with_name("vmmap.txt").write_text(completed.stdout, encoding="utf-8")

atexit.register(_write_memory_map)
''',
                )
            simple = '''        elif variant == "direct":
            with stage("simple_direct"):
                covariance = weighted.T @ weighted
                diagonal = np.diag(covariance).copy()
                covariance *= 1.0 - shrinkage
                covariance.flat[:: covariance.shape[0] + 1] += shrinkage * diagonal + 1e-6
                precision = np.linalg.solve(covariance, target)
'''
            if args.engine == "scipy":
                simple = simple.replace(
                    "precision = np.linalg.solve(covariance, target)",
                    "precision = cho_solve(cho_factor(covariance, check_finite=False), target, check_finite=False)",
                ).replace('stage("simple_direct")', 'stage("scipy_cholesky")')
            elif args.engine == "structural-scipy":
                simple = '''        elif variant == "direct":
            with stage("structural_scipy"):
                covariance = weighted.T @ weighted
                diagonal = np.diag(covariance).copy()
                covariance *= 1.0 - shrinkage
                covariance.flat[:: covariance.shape[0] + 1] += shrinkage * diagonal + 1e-6
                dimension = covariance.shape[0]
                roots = np.sqrt(diagonal)
                norm_upper = float(np.max((1.0 - shrinkage) * roots * roots.sum() + shrinkage * diagonal + 1e-6))
                lower = 1e-6 + shrinkage * float(np.min(diagonal))
                median_count = dimension // 2 if dimension % 2 == 0 else dimension // 2 + 1
                floor_upper = max(float(np.trace(covariance)) / median_count * 1e-3, 1e-7)
                margin = np.finfo(np.float64).eps * max(norm_upper, 1.0) * dimension * 64.0
                if lower > floor_upper + margin:
                    _CALLS["structural_proved"] += 1
                    precision = cho_solve(cho_factor(covariance, check_finite=False), target, check_finite=False)
                else:
                    _CALLS["structural_audited"] += 1
                    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
                    floor = max(float(np.median(eigenvalues)) * 1e-3, 1e-7)
                    _CALLS["floor_active"] += int(bool(np.any(eigenvalues < floor)))
                    precision = eigenvectors @ ((eigenvectors.T @ target) / np.maximum(eigenvalues, floor))
'''
            transformed, replacements = re.subn(
                r'^        elif variant == "direct":\n.*?(?=^        else:\n)',
                simple,
                source,
                count=1,
                flags=re.MULTILINE | re.DOTALL,
            )
            if replacements != 1:
                raise RuntimeError("could not replace the structural solve branch")
            path.write_text(transformed, encoding="utf-8")
            return driver

        previous._prepare_driver = prepare_simple

    sys.argv = [sys.argv[0], "--mode", args.mode]
    previous.main()
    output = HERE / "outputs" / "direct" / args.mode
    destination = HERE / "outputs" / args.engine / args.mode / f"trial-{args.trial}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.rename(destination)


if __name__ == "__main__":
    main()
