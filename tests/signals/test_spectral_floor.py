"""The checked fast path for repeated spectral-floor solves."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vqapr.signals.risk import SpectralFloorSolver


def _legacy(matrix: np.ndarray, target: np.ndarray) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    floor = max(float(np.median(eigenvalues)) * 1e-3, 1e-7)
    return eigenvectors @ ((eigenvectors.T @ target) / np.maximum(eigenvalues, floor))


def test_the_solver_is_on_the_one_public_author_surface() -> None:
    from vqapr import public as vq

    assert vq.SpectralFloorSolver is SpectralFloorSolver


def test_a_safe_matrix_is_audited_once_then_reused(tmp_path: Path) -> None:
    cache = tmp_path / "risk.certificates"
    matrix = np.array([[2.0, 0.25], [0.25, 1.0]])
    target = np.array([0.5, -0.25])

    first = SpectralFloorSolver(cache)
    observed = first.solve(matrix, target)
    first.close()

    assert np.allclose(observed, _legacy(matrix, target), rtol=1e-12, atol=1e-12)
    assert first.stats.as_record() == {
        "audited": 1,
        "certified": 1,
        "reused": 0,
        "floor_fallbacks": 0,
        "margin_fallbacks": 0,
        "cache_usable": True,
        "cache_warning": None,
    }

    repeated = SpectralFloorSolver(cache)
    again = repeated.solve(matrix, target)
    repeated.close()

    assert np.array_equal(again, observed)
    assert repeated.stats.reused == 1
    assert repeated.stats.audited == 0


def test_a_changed_matrix_cannot_reuse_the_old_certificate(tmp_path: Path) -> None:
    cache = tmp_path / "risk.certificates"
    target = np.array([1.0, 2.0])
    original = np.array([[2.0, 0.0], [0.0, 1.0]])
    changed = np.array([[2.0, 0.1], [0.1, 1.0]])

    with SpectralFloorSolver(cache) as solver:
        solver.solve(original, target)
    with SpectralFloorSolver(cache) as solver:
        solver.solve(changed, target)
        assert solver.stats.audited == 1
        assert solver.stats.reused == 0


def test_an_active_floor_uses_the_original_formula_and_is_never_certified(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "risk.certificates"
    matrix = np.diag([1.0, 1e-12])
    target = np.array([1.0, 1.0])

    with SpectralFloorSolver(cache) as solver:
        observed = solver.solve(matrix, target)
        assert solver.stats.floor_fallbacks == 1
        assert solver.stats.certified == 0
    with SpectralFloorSolver(cache) as solver:
        solver.solve(matrix, target)
        assert solver.stats.audited == 1
        assert solver.stats.reused == 0

    assert np.array_equal(observed, _legacy(matrix, target))


def test_a_damaged_cache_is_ignored_without_changing_the_answer(tmp_path: Path) -> None:
    cache = tmp_path / "risk.certificates"
    cache.write_text("not a vqapr certificate cache\n", encoding="utf-8")
    matrix = np.array([[3.0, 0.25], [0.25, 2.0]])
    target = np.array([1.0, -1.0])

    with SpectralFloorSolver(cache) as solver:
        observed = solver.solve(matrix, target)
        stats = solver.stats

    assert np.allclose(observed, _legacy(matrix, target), rtol=1e-12, atol=1e-12)
    assert stats.audited == 1
    assert stats.cache_usable is False
    assert stats.cache_warning is not None
    assert cache.read_text(encoding="utf-8") == "not a vqapr certificate cache\n"


@pytest.mark.parametrize(
    ("matrix", "target", "message"),
    [
        (np.ones((2, 3)), np.ones(2), "square"),
        (np.array([[1.0, 1.0], [0.0, 1.0]]), np.ones(2), "symmetric"),
        (np.eye(2), np.ones(3), "target"),
        (np.array([[1.0, np.nan], [np.nan, 1.0]]), np.ones(2), "finite"),
    ],
)
def test_invalid_linear_systems_are_refused(
    tmp_path: Path, matrix: np.ndarray, target: np.ndarray, message: str
) -> None:
    with SpectralFloorSolver(tmp_path / "risk.certificates") as solver:
        with pytest.raises(ValueError, match=message):
            solver.solve(matrix, target)
