"""Risk-model linear algebra whose expensive safety proof can be reused.

The cache in this module is derived evidence, never model state. Removing it only makes the next
solve audit the matrix again. It cannot change which formula is used when the spectral floor is
active.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = ["SpectralFloorSolver", "SpectralFloorStats"]

_MAGIC = "vqapr-spectral-floor-certificates-v1"
_DIGEST_SIZE = 64


@dataclass(frozen=True, slots=True)
class SpectralFloorStats:
    """Counts that distinguish a first safe execution from a certified repeat."""

    audited: int
    certified: int
    reused: int
    floor_fallbacks: int
    margin_fallbacks: int
    cache_usable: bool
    cache_warning: str | None

    def as_record(self) -> dict[str, int | bool | str | None]:
        """Return JSON-ready evidence for logs and result tables."""
        return {
            "audited": self.audited,
            "certified": self.certified,
            "reused": self.reused,
            "floor_fallbacks": self.floor_fallbacks,
            "margin_fallbacks": self.margin_fallbacks,
            "cache_usable": self.cache_usable,
            "cache_warning": self.cache_warning,
        }


class SpectralFloorSolver:
    """Solve a symmetric system with the legacy spectral-floor safety rule.

    On first sight of a matrix, the solver checks its eigenvalues. If none needs flooring, the
    exact matrix digest is saved and the system is solved directly. Seeing those exact bytes again
    skips only that check. If flooring is needed, the original eigendecomposition formula runs and
    no shortcut certificate is written.

    ``cache`` is optional. Without it every call is safely audited. A malformed or incompatible
    cache is left untouched and ignored; this may cost time but cannot alter a result.
    """

    def __init__(
        self,
        cache: str | Path | None = None,
        *,
        relative_floor: float = 1e-3,
        absolute_floor: float = 1e-7,
        flush_every: int = 256,
    ) -> None:
        if not np.isfinite(relative_floor) or relative_floor < 0:
            raise ValueError("relative_floor must be finite and non-negative")
        if not np.isfinite(absolute_floor) or absolute_floor <= 0:
            raise ValueError("absolute_floor must be finite and positive")
        if not isinstance(flush_every, int) or isinstance(flush_every, bool) or flush_every < 1:
            raise ValueError("flush_every must be a positive integer")

        self._cache = None if cache is None else Path(cache)
        self._relative_floor = float(relative_floor)
        self._absolute_floor = float(absolute_floor)
        self._flush_every = flush_every
        self._known: set[str] = set()
        self._pending: list[str] = []
        self._audited = 0
        self._certified = 0
        self._reused = 0
        self._fallbacks = 0
        self._margin_fallbacks = 0
        self._cache_usable = True
        self._cache_warning: str | None = None
        self._header = self._make_header()
        self._load_cache()

    @property
    def stats(self) -> SpectralFloorStats:
        """Current audit and reuse evidence."""
        return SpectralFloorStats(
            audited=self._audited,
            certified=self._certified,
            reused=self._reused,
            floor_fallbacks=self._fallbacks,
            margin_fallbacks=self._margin_fallbacks,
            cache_usable=self._cache_usable,
            cache_warning=self._cache_warning,
        )

    def solve(self, matrix: ArrayLike, target: ArrayLike) -> NDArray[np.float64]:
        """Return the floor-adjusted solution for one finite symmetric system."""
        system = np.ascontiguousarray(matrix, dtype=np.float64)
        vector = np.ascontiguousarray(target, dtype=np.float64)
        self._validate(system, vector)
        digest = self._digest(system)

        if digest in self._known:
            self._reused += 1
            return np.linalg.solve(system, vector)

        self._audited += 1
        eigenvalues = np.linalg.eigvalsh(system)
        floor = max(float(np.median(eigenvalues)) * self._relative_floor, self._absolute_floor)
        floor_is_active = bool(np.any(eigenvalues < floor))
        safety_margin = (
            np.finfo(np.float64).eps
            * max(float(np.linalg.norm(system, ord=np.inf)), 1.0)
            * system.shape[0]
            * 64.0
        )
        if floor_is_active or float(eigenvalues[0]) <= floor + safety_margin:
            if floor_is_active:
                self._fallbacks += 1
            else:
                self._margin_fallbacks += 1
            full_values, eigenvectors = np.linalg.eigh(system)
            full_floor = max(
                float(np.median(full_values)) * self._relative_floor,
                self._absolute_floor,
            )
            return eigenvectors @ (
                (eigenvectors.T @ vector) / np.maximum(full_values, full_floor)
            )

        solution = np.linalg.solve(system, vector)
        self._certified += 1
        self._known.add(digest)
        if self._cache is not None and self._cache_usable:
            self._pending.append(digest)
            if len(self._pending) >= self._flush_every:
                self._flush()
        return solution

    def close(self) -> None:
        """Write any buffered certificates. Safe to call more than once."""
        self._flush()

    def __enter__(self) -> SpectralFloorSolver:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _make_header(self) -> str:
        policy = json.dumps(
            {
                "absolute_floor": self._absolute_floor.hex(),
                "dtype": "<f8",
                "numpy": np.__version__,
                "relative_floor": self._relative_floor.hex(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"{_MAGIC} {policy}"

    def _load_cache(self) -> None:
        if self._cache is None or not self._cache.exists():
            return
        try:
            lines = self._cache.read_text(encoding="ascii").splitlines()
        except (OSError, UnicodeError) as error:
            self._disable_cache(f"certificate cache could not be read: {error}")
            return
        if not lines or lines[0] != self._header:
            self._disable_cache("certificate cache has a different version or solver policy")
            return
        for number, digest in enumerate(lines[1:], start=2):
            valid_digest = len(digest) == _DIGEST_SIZE and all(
                char in "0123456789abcdef" for char in digest
            )
            if not valid_digest:
                self._disable_cache(f"certificate cache has an invalid digest on line {number}")
                self._known.clear()
                return
            self._known.add(digest)

    def _flush(self) -> None:
        if self._cache is None or not self._cache_usable or not self._pending:
            return
        try:
            self._cache.parent.mkdir(parents=True, exist_ok=True)
            if not self._cache.exists():
                try:
                    descriptor = os.open(
                        self._cache,
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                        0o600,
                    )
                except FileExistsError:
                    self._load_cache()
                else:
                    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                        stream.write(self._header + "\n")
            if not self._cache_usable:
                return
            with self._cache.open("a", encoding="ascii") as stream:
                stream.write("".join(f"{digest}\n" for digest in self._pending))
            self._pending.clear()
        except OSError as error:
            self._disable_cache(f"certificate cache could not be written: {error}")

    def _disable_cache(self, warning: str) -> None:
        self._cache_usable = False
        self._cache_warning = warning
        self._pending.clear()

    @staticmethod
    def _digest(matrix: NDArray[np.float64]) -> str:
        digest = hashlib.sha256()
        digest.update(str(matrix.shape).encode("ascii"))
        digest.update(memoryview(matrix).cast("B"))
        return digest.hexdigest()

    def _validate(self, matrix: NDArray[np.float64], target: NDArray[np.float64]) -> None:
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] == 0:
            raise ValueError("matrix must be a non-empty square matrix")
        if target.ndim != 1 or target.shape[0] != matrix.shape[0]:
            raise ValueError("target must be a vector with one value per matrix row")
        if not np.isfinite(matrix).all() or not np.isfinite(target).all():
            raise ValueError("matrix and target must contain only finite values")
        if not np.array_equal(matrix, matrix.T):
            raise ValueError("matrix must be exactly symmetric")
