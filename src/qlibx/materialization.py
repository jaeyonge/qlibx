from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from .errors import (
    ConfigError,
    DataContractError,
    MaterializationError,
    ValidationError,
)
from .journal import ActionJournal
from .profiles import QlibTargetProfile, get_profile

CONFIG_SCHEMA = "qlibx.qlib_materialization/v1"
MANIFEST_SCHEMA = "qlibx.qlib_materialization_manifest/v1"
PRODUCER_ID = "qlibx.qlib_binary_materializer"
PRODUCER_SCHEMA_VERSION = 1
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SAFE_FIELD = re.compile(r"^[a-z][a-z0-9_]*$")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _producer_identity() -> dict[str, Any]:
    try:
        package_version = version("qlibx")
    except PackageNotFoundError:
        package_version = "0+unknown"
    return {
        "id": PRODUCER_ID,
        "schema_version": PRODUCER_SCHEMA_VERSION,
        "package_version": package_version,
        "implementation_sha256": _file_hash(Path(__file__)),
    }


def _json_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require(mapping: dict[str, Any], key: str, expected: type, context: str) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected):
        raise ConfigError(f"{context}.{key} must be {expected.__name__}")
    return value


def _project_path(project_root: Path, value: str, *, context: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ConfigError(f"{context} must be project-relative: {value}")
    resolved = (project_root / path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ConfigError(f"{context} escapes the project root: {value}") from exc
    return resolved


def _parse_date(value: Any, date_format: str, *, context: str) -> date:
    try:
        return (
            datetime.strptime(str(value).strip(), date_format)
            .replace(tzinfo=UTC)
            .date()
        )
    except (TypeError, ValueError) as exc:
        raise DataContractError(f"Invalid date in {context}: {value!r}") from exc


def _parse_boundary(value: str | None, *, context: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"{context} must use YYYY-MM-DD: {value}") from exc


def _parse_float(value: Any) -> float:
    if value is None:
        return math.nan
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return math.nan
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return math.nan
    return parsed if math.isfinite(parsed) else math.nan


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


@dataclass(frozen=True)
class SourceRef:
    dataset_id: str
    type: str
    path: str
    table: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, context: str) -> SourceRef:
        source_type = _require(value, "type", str, context).lower()
        if source_type not in {"csv", "parquet", "duckdb"}:
            raise ConfigError(f"{context}.type must be csv, parquet, or duckdb")
        table = value.get("table")
        if source_type == "duckdb" and not isinstance(table, str):
            raise ConfigError(f"{context}.table is required for DuckDB sources")
        return cls(
            dataset_id=_require(value, "dataset_id", str, context),
            type=source_type,
            path=_require(value, "path", str, context),
            table=table,
        )


@dataclass(frozen=True)
class CalendarSpec:
    source: SourceRef
    date_column: str
    date_format: str
    include_column: str | None
    include_values: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CalendarSpec:
        include = value.get("include", {})
        if not isinstance(include, dict):
            raise ConfigError("calendar.include must be an object")
        include_column = include.get("column")
        include_values = include.get("values", [])
        if include_column is not None and not isinstance(include_column, str):
            raise ConfigError("calendar.include.column must be a string")
        if include_column is not None and not (
            isinstance(include_values, list)
            and all(isinstance(item, (str, int, float)) for item in include_values)
        ):
            raise ConfigError("calendar.include.values must be a list of scalar values")
        return cls(
            source=SourceRef.from_dict(
                _require(value, "source", dict, "calendar"), context="calendar.source"
            ),
            date_column=_require(value, "date_column", str, "calendar"),
            date_format=value.get("date_format", "%Y%m%d"),
            include_column=include_column,
            include_values=tuple(str(item) for item in include_values),
        )


@dataclass(frozen=True)
class UniverseSpec:
    name: str
    source: SourceRef
    instrument_column: str
    date_column: str
    date_format: str

    @classmethod
    def from_dict(cls, value: dict[str, Any], index: int) -> UniverseSpec:
        context = f"universes[{index}]"
        name = _require(value, "name", str, context).lower()
        if not _SAFE_FIELD.fullmatch(name):
            raise ConfigError(f"{context}.name is not a safe Qlib market name: {name}")
        return cls(
            name=name,
            source=SourceRef.from_dict(
                _require(value, "source", dict, context), context=f"{context}.source"
            ),
            instrument_column=_require(value, "instrument_column", str, context),
            date_column=_require(value, "date_column", str, context),
            date_format=value.get("date_format", "%Y%m%d"),
        )


@dataclass(frozen=True)
class TransformSpec:
    kind: str
    column: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    require_positive_inputs: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, context: str) -> TransformSpec:
        kind = _require(value, "kind", str, context)
        if kind == "field":
            return cls(kind=kind, column=_require(value, "column", str, context))
        if kind == "ratio_minus_one":
            return cls(
                kind=kind,
                numerator=_require(value, "numerator", str, context),
                denominator=_require(value, "denominator", str, context),
                require_positive_inputs=bool(
                    value.get("require_positive_inputs", False)
                ),
            )
        raise ConfigError(f"Unsupported transform kind in {context}: {kind}")

    @property
    def columns(self) -> tuple[str, ...]:
        if self.kind == "field":
            assert self.column is not None
            return (self.column,)
        assert self.numerator is not None and self.denominator is not None
        return (self.numerator, self.denominator)

    def apply(self, values: Sequence[Any]) -> float:
        if self.kind == "field":
            return _parse_float(values[0])
        numerator = _parse_float(values[0])
        denominator = _parse_float(values[1])
        if math.isnan(numerator) or math.isnan(denominator) or denominator == 0:
            return math.nan
        if self.require_positive_inputs and (numerator <= 0 or denominator <= 0):
            return math.nan
        return numerator / denominator - 1.0


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    source: SourceRef
    instrument_column: str
    date_column: str
    date_format: str
    transform: TransformSpec

    @classmethod
    def from_dict(cls, value: dict[str, Any], index: int) -> FeatureSpec:
        context = f"features[{index}]"
        name = _require(value, "name", str, context).lower()
        if not _SAFE_FIELD.fullmatch(name):
            raise ConfigError(f"{context}.name is not a safe Qlib field name: {name}")
        return cls(
            name=name,
            source=SourceRef.from_dict(
                _require(value, "source", dict, context), context=f"{context}.source"
            ),
            instrument_column=_require(value, "instrument_column", str, context),
            date_column=_require(value, "date_column", str, context),
            date_format=value.get("date_format", "%Y%m%d"),
            transform=TransformSpec.from_dict(
                _require(value, "transform", dict, context),
                context=f"{context}.transform",
            ),
        )


@dataclass(frozen=True)
class MaterializationConfig:
    profile_id: str
    output_dir: str
    start_date: date | None
    end_date: date | None
    calendar: CalendarSpec
    universes: tuple[UniverseSpec, ...]
    features: tuple[FeatureSpec, ...]
    accepted_limitations: tuple[str, ...]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> MaterializationConfig:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Unable to read materialization config: {path}") from exc
        if not isinstance(raw, dict):
            raise ConfigError("Materialization config must be a JSON object")
        if raw.get("schema") != CONFIG_SCHEMA:
            raise ConfigError(f"Materialization config schema must be {CONFIG_SCHEMA}")
        universes_raw = _require(raw, "universes", list, "config")
        features_raw = _require(raw, "features", list, "config")
        limitations = raw.get("accepted_limitations", [])
        if not isinstance(limitations, list) or not all(
            isinstance(item, str) for item in limitations
        ):
            raise ConfigError("accepted_limitations must be a list of strings")
        config = cls(
            profile_id=_require(raw, "profile_id", str, "config"),
            output_dir=_require(raw, "output_dir", str, "config"),
            start_date=_parse_boundary(raw.get("start_date"), context="start_date"),
            end_date=_parse_boundary(raw.get("end_date"), context="end_date"),
            calendar=CalendarSpec.from_dict(_require(raw, "calendar", dict, "config")),
            universes=tuple(
                UniverseSpec.from_dict(value, index)
                for index, value in enumerate(universes_raw)
            ),
            features=tuple(
                FeatureSpec.from_dict(value, index)
                for index, value in enumerate(features_raw)
            ),
            accepted_limitations=tuple(limitations),
            raw=raw,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ConfigError("start_date must not be after end_date")
        profile = get_profile(self.profile_id)
        universe_names = [item.name for item in self.universes]
        feature_names = [item.name for item in self.features]
        if len(universe_names) != len(set(universe_names)):
            raise ConfigError("Universe names must be unique")
        if len(feature_names) != len(set(feature_names)):
            raise ConfigError("Feature names must be unique")
        missing_universes = sorted(
            set(profile.required_universes) - set(universe_names)
        )
        missing_features = sorted(set(profile.feature_map) - set(feature_names))
        extra_features = sorted(set(feature_names) - set(profile.feature_map))
        if missing_universes:
            raise ConfigError(f"Missing required universes: {missing_universes}")
        if missing_features or extra_features:
            raise ConfigError(
                "Configured features do not match the target profile",
                details={"missing": missing_features, "extra": extra_features},
            )
        for feature in self.features:
            allowed = profile.feature_map[feature.name].allowed_transforms
            if feature.transform.kind not in allowed:
                raise ConfigError(
                    f"Feature {feature.name} does not allow transform {feature.transform.kind}; allowed={allowed}"
                )

    @property
    def sources(self) -> tuple[SourceRef, ...]:
        unique: dict[tuple[str, str, str | None], SourceRef] = {}
        for source in [
            self.calendar.source,
            *(item.source for item in self.universes),
            *(item.source for item in self.features),
        ]:
            unique[(source.type, source.path, source.table)] = source
        return tuple(unique.values())


class SourceReader:
    def __init__(self, project_root: Path, source: SourceRef) -> None:
        self.path = _project_path(
            project_root, source.path, context=f"source {source.dataset_id}.path"
        )
        if not self.path.is_file():
            raise ConfigError(f"Source file does not exist: {source.path}")
        self.source = source

    def column_names(self) -> tuple[str, ...]:
        connection = (
            duckdb.connect(str(self.path), read_only=True)
            if self.source.type == "duckdb"
            else duckdb.connect(":memory:")
        )
        try:
            if self.source.type == "csv":
                relation = connection.read_csv(
                    str(self.path), header=True, all_varchar=True
                )
            elif self.source.type == "parquet":
                relation = connection.read_parquet(str(self.path))
            else:
                assert self.source.table is not None
                relation = connection.table(self.source.table)
            return tuple(relation.columns)
        except duckdb.Error as exc:
            raise DataContractError(
                f"Unable to inspect {self.source.dataset_id}: {exc}"
            ) from exc
        finally:
            connection.close()

    def rows(
        self, columns: Sequence[str], *, order_by: Sequence[str] = ()
    ) -> Iterator[tuple[Any, ...]]:
        connection = (
            duckdb.connect(str(self.path), read_only=True)
            if self.source.type == "duckdb"
            else duckdb.connect(":memory:")
        )
        try:
            if self.source.type == "csv":
                relation = connection.read_csv(
                    str(self.path), header=True, all_varchar=True
                )
            elif self.source.type == "parquet":
                relation = connection.read_parquet(str(self.path))
            else:
                assert self.source.table is not None
                relation = connection.table(self.source.table)
            expression = ", ".join(_quote_identifier(column) for column in columns)
            relation = relation.project(expression)
            if order_by:
                relation = relation.order(
                    ", ".join(_quote_identifier(column) for column in order_by)
                )
            cursor = relation.execute()
            while batch := cursor.fetchmany(65_536):
                yield from batch
        except duckdb.Error as exc:
            raise DataContractError(
                f"Unable to read {self.source.dataset_id}: {exc}",
                details={"path": self.source.path, "columns": list(columns)},
            ) from exc
        finally:
            connection.close()


def _source_identities(
    project_root: Path, config: MaterializationConfig
) -> list[dict[str, Any]]:
    identities = []
    for source in config.sources:
        path = _project_path(
            project_root, source.path, context=f"source {source.dataset_id}.path"
        )
        if not path.is_file():
            raise ConfigError(f"Source file does not exist: {source.path}")
        identities.append(
            {
                "dataset_id": source.dataset_id,
                "type": source.type,
                "path": source.path,
                "table": source.table,
                "size": path.stat().st_size,
                "sha256": _file_hash(path),
            }
        )
    return sorted(identities, key=lambda item: (item["path"], item.get("table") or ""))


def preflight_materialization_config(
    config_path: Path,
    *,
    project_root: Path,
    actor_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    config_path = config_path.resolve()
    try:
        relative_config = str(config_path.relative_to(project_root))
    except ValueError as exc:
        raise ConfigError(
            "Materialization config must be inside the project root"
        ) from exc
    journal = ActionJournal(project_root, actor_id=actor_id, session_id=session_id)
    with journal.operation(
        "data.materialize.preflight",
        read_only=True,
        inputs={"parameters": {"config": relative_config}},
    ) as operation:
        config = MaterializationConfig.load(config_path)
        profile = get_profile(config.profile_id)
        target = _project_path(project_root, config.output_dir, context="output_dir")
        required: dict[tuple[str, str, str | None], set[str]] = {}
        source_by_key: dict[tuple[str, str, str | None], SourceRef] = {}

        def add(source: SourceRef, columns: Iterable[str]) -> None:
            key = (source.type, source.path, source.table)
            source_by_key[key] = source
            required.setdefault(key, set()).update(columns)

        calendar_columns = [config.calendar.date_column]
        if config.calendar.include_column:
            calendar_columns.append(config.calendar.include_column)
        add(config.calendar.source, calendar_columns)
        for universe in config.universes:
            add(universe.source, [universe.instrument_column, universe.date_column])
        for feature in config.features:
            add(
                feature.source,
                [
                    feature.instrument_column,
                    feature.date_column,
                    *feature.transform.columns,
                ],
            )

        source_results = []
        for key in sorted(source_by_key, key=lambda item: (item[1], item[2] or "")):
            source = source_by_key[key]
            reader = SourceReader(project_root, source)
            available = set(reader.column_names())
            missing = sorted(required[key] - available)
            if missing:
                raise DataContractError(
                    f"Source {source.dataset_id} is missing configured columns: {missing}",
                    details={"available_columns": sorted(available)},
                )
            source_results.append(
                {
                    "dataset_id": source.dataset_id,
                    "type": source.type,
                    "path": source.path,
                    "table": source.table,
                    "size": reader.path.stat().st_size,
                    "required_columns": sorted(required[key]),
                }
            )
        result = {
            "status": "passed",
            "profile_id": profile.profile_id,
            "output_dir": str(target.relative_to(project_root)),
            "output_exists": target.exists(),
            "sources": source_results,
            "required_universes": list(profile.required_universes),
            "required_features": sorted(profile.feature_map),
            "accepted_limitations": list(config.accepted_limitations),
        }
        operation.succeed(
            outputs={"result_summary": result},
            accepted_limitations=list(config.accepted_limitations),
        )
        return result


def _read_calendar(
    project_root: Path, config: MaterializationConfig
) -> tuple[list[date], dict[date, int], dict[str, Any]]:
    spec = config.calendar
    columns = [spec.date_column]
    if spec.include_column:
        columns.append(spec.include_column)
    rows = SourceReader(project_root, spec.source).rows(
        columns, order_by=[spec.date_column]
    )
    dates: list[date] = []
    seen: set[date] = set()
    excluded = 0
    for row in rows:
        current = _parse_date(row[0], spec.date_format, context=spec.source.dataset_id)
        if config.start_date and current < config.start_date:
            continue
        if config.end_date and current > config.end_date:
            continue
        if spec.include_column and str(row[1]).strip() not in spec.include_values:
            excluded += 1
            continue
        if current in seen:
            raise DataContractError(f"Duplicate trading-calendar date: {current}")
        seen.add(current)
        dates.append(current)
    dates.sort()
    if not dates:
        raise DataContractError(
            "Trading calendar is empty after applying the configured bounds"
        )
    return (
        dates,
        {current: index for index, current in enumerate(dates)},
        {
            "dataset_id": spec.source.dataset_id,
            "count": len(dates),
            "start": dates[0].isoformat(),
            "end": dates[-1].isoformat(),
            "excluded_rows": excluded,
        },
    )


def _safe_instrument(value: Any, *, context: str) -> str:
    instrument = str(value).strip()
    if not instrument or not _SAFE_NAME.fullmatch(instrument):
        raise DataContractError(f"Unsafe or empty instrument in {context}: {value!r}")
    return instrument


def _compress_indexes(indexes: list[int]) -> list[tuple[int, int]]:
    if not indexes:
        return []
    result: list[tuple[int, int]] = []
    start = previous = indexes[0]
    for current in indexes[1:]:
        if current == previous + 1:
            previous = current
            continue
        result.append((start, previous))
        start = previous = current
    result.append((start, previous))
    return result


def _write_instrument_file(
    path: Path, intervals: dict[str, list[tuple[int, int]]], calendar: list[date]
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as stream:
        for instrument in sorted(intervals):
            for start, end in intervals[instrument]:
                stream.write(
                    f"{instrument}\t{calendar[start].isoformat()}\t{calendar[end].isoformat()}\n"
                )
                count += 1
    return count


def _materialize_universe(
    project_root: Path,
    target: Path,
    spec: UniverseSpec,
    calendar: list[date],
    calendar_index: dict[date, int],
    config: MaterializationConfig,
) -> dict[str, Any]:
    rows = SourceReader(project_root, spec.source).rows(
        [spec.instrument_column, spec.date_column],
        order_by=[spec.instrument_column, spec.date_column],
    )
    membership: dict[str, list[int]] = {}
    seen: set[tuple[str, int]] = set()
    outside_bounds = 0
    for instrument_raw, date_raw in rows:
        current = _parse_date(
            date_raw, spec.date_format, context=spec.source.dataset_id
        )
        if config.start_date and current < config.start_date:
            outside_bounds += 1
            continue
        if config.end_date and current > config.end_date:
            outside_bounds += 1
            continue
        if current not in calendar_index:
            raise DataContractError(
                f"Universe {spec.name} contains a non-trading date inside the study range: {current}"
            )
        instrument = _safe_instrument(instrument_raw, context=spec.source.dataset_id)
        key = (instrument.lower(), calendar_index[current])
        if key in seen:
            raise DataContractError(
                f"Duplicate universe membership: {instrument} on {current}"
            )
        seen.add(key)
        membership.setdefault(instrument, []).append(calendar_index[current])
    intervals = {
        instrument: _compress_indexes(indexes)
        for instrument, indexes in membership.items()
    }
    interval_count = _write_instrument_file(
        target / "instruments" / f"{spec.name}.txt", intervals, calendar
    )
    return {
        "name": spec.name,
        "dataset_id": spec.source.dataset_id,
        "instruments": len(intervals),
        "member_dates": len(seen),
        "intervals": interval_count,
        "outside_configured_bounds": outside_bounds,
    }


def _write_feature_group(
    target: Path,
    instrument: str,
    field: str,
    values: dict[int, float],
) -> tuple[int, int, int]:
    if not values:
        return 0, 0, 0
    start = min(values)
    end = max(values)
    array = np.full(end - start + 1, np.nan, dtype="<f4")
    for index, value in values.items():
        array[index - start] = value
    directory = target / "features" / instrument.lower()
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{field}.day.bin"
    with output.open("wb") as stream:
        np.asarray([start], dtype="<f4").tofile(stream)
        array.tofile(stream)
    return start, end, int(np.count_nonzero(~np.isnan(array)))


def _materialize_feature(
    project_root: Path,
    target: Path,
    spec: FeatureSpec,
    calendar: list[date],
    calendar_index: dict[date, int],
    config: MaterializationConfig,
    all_coverage: dict[str, tuple[str, int, int]],
) -> dict[str, Any]:
    columns = [spec.instrument_column, spec.date_column, *spec.transform.columns]
    rows = SourceReader(project_root, spec.source).rows(
        columns, order_by=[spec.instrument_column, spec.date_column]
    )
    current_instrument: str | None = None
    current_values: dict[int, float] = {}
    seen_normalized: dict[str, str] = {}
    row_count = valid_count = missing_count = outside_bounds = 0
    output_instruments = 0

    def flush() -> None:
        nonlocal current_values, output_instruments, valid_count
        if current_instrument is None or not current_values:
            current_values = {}
            return
        start, end, valid = _write_feature_group(
            target, current_instrument, spec.name, current_values
        )
        output_instruments += 1
        valid_count += valid
        normalized = current_instrument.lower()
        previous = all_coverage.get(normalized)
        if previous and previous[0] != current_instrument:
            raise DataContractError(
                f"Instrument identifiers collide across features after Qlib lowercasing: "
                f"{previous[0]} and {current_instrument}"
            )
        all_coverage[normalized] = (
            current_instrument,
            min(start, previous[1]) if previous else start,
            max(end, previous[2]) if previous else end,
        )
        current_values = {}

    for row in rows:
        instrument = _safe_instrument(row[0], context=spec.source.dataset_id)
        normalized = instrument.lower()
        previous_spelling = seen_normalized.setdefault(normalized, instrument)
        if previous_spelling != instrument:
            raise DataContractError(
                f"Instrument identifiers collide after Qlib lowercasing: {previous_spelling} and {instrument}"
            )
        if current_instrument is not None and instrument != current_instrument:
            flush()
        current_instrument = instrument
        current = _parse_date(row[1], spec.date_format, context=spec.source.dataset_id)
        if config.start_date and current < config.start_date:
            outside_bounds += 1
            continue
        if config.end_date and current > config.end_date:
            outside_bounds += 1
            continue
        if current not in calendar_index:
            raise DataContractError(
                f"Feature {spec.name} contains a non-trading date inside the study range: {current}"
            )
        index = calendar_index[current]
        if index in current_values:
            raise DataContractError(
                f"Duplicate feature key for {spec.name}: {instrument} on {current}"
            )
        value = spec.transform.apply(row[2:])
        if math.isnan(value):
            missing_count += 1
        current_values[index] = value
        row_count += 1
    flush()
    if output_instruments == 0:
        raise DataContractError(f"Feature {spec.name} produced no output")
    return {
        "name": spec.name,
        "dataset_id": spec.source.dataset_id,
        "transform": asdict(spec.transform),
        "rows": row_count,
        "valid_values": valid_count,
        "missing_values": missing_count,
        "instruments": output_instruments,
        "outside_configured_bounds": outside_bounds,
        "storage_dtype": "float32",
    }


def _write_all_universe(
    target: Path, coverage: dict[str, tuple[str, int, int]], calendar: list[date]
) -> dict[str, Any]:
    intervals = {display: [(start, end)] for display, start, end in coverage.values()}
    interval_count = _write_instrument_file(
        target / "instruments" / "all.txt", intervals, calendar
    )
    return {
        "name": "all",
        "instruments": len(intervals),
        "intervals": interval_count,
        "basis": "feature_union",
    }


def _write_calendar(target: Path, calendar: Iterable[date]) -> None:
    directory = target / "calendars"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "day.txt").open("w", encoding="utf-8", newline="") as stream:
        for current in calendar:
            stream.write(current.isoformat())
            stream.write("\n")


def _manifest_path(target: Path) -> Path:
    return target / "qlibx-manifest.json"


def materialize_from_config(
    config_path: Path,
    *,
    project_root: Path,
    actor_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    config_path = config_path.resolve()
    try:
        config_path.relative_to(project_root)
    except ValueError as exc:
        raise ConfigError(
            "Materialization config must be inside the project root"
        ) from exc
    journal = ActionJournal(project_root, actor_id=actor_id, session_id=session_id)
    relative_config = str(config_path.relative_to(project_root))
    with journal.operation(
        "data.materialize.qlib",
        read_only=False,
        inputs={"parameters": {"config": relative_config}},
    ) as operation:
        config = MaterializationConfig.load(config_path)
        profile = get_profile(config.profile_id)
        target = _project_path(project_root, config.output_dir, context="output_dir")
        source_identities = _source_identities(project_root, config)
        producer = _producer_identity()
        materialization_id = _json_hash(
            {
                "producer": producer,
                "profile": profile.to_dict(),
                "config": config.raw,
                "sources": source_identities,
            }
        )
        if target.exists():
            manifest_file = _manifest_path(target)
            if manifest_file.is_file():
                existing = json.loads(manifest_file.read_text(encoding="utf-8"))
                if existing.get("materialization_id") == materialization_id:
                    validation = validate_qlib_store(target, profile)
                    operation.succeed(
                        outputs={
                            "result_summary": {
                                "materialization_id": materialization_id,
                                "output_dir": config.output_dir,
                                "reused": True,
                                "validation": validation,
                            }
                        },
                        accepted_limitations=list(config.accepted_limitations),
                    )
                    return existing
            raise MaterializationError(
                f"Output directory already exists with different or unknown content: {config.output_dir}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent)
        )
        try:
            calendar, calendar_index, calendar_summary = _read_calendar(
                project_root, config
            )
            _write_calendar(temporary, calendar)
            universe_summaries = [
                _materialize_universe(
                    project_root, temporary, spec, calendar, calendar_index, config
                )
                for spec in config.universes
            ]
            all_coverage: dict[str, tuple[str, int, int]] = {}
            feature_summaries = [
                _materialize_feature(
                    project_root,
                    temporary,
                    spec,
                    calendar,
                    calendar_index,
                    config,
                    all_coverage,
                )
                for spec in config.features
            ]
            universe_summaries.insert(
                0, _write_all_universe(temporary, all_coverage, calendar)
            )
            manifest = {
                "schema": MANIFEST_SCHEMA,
                "materialization_id": materialization_id,
                "created_at": _utc_now(),
                "producer": producer,
                "output_dir": config.output_dir,
                "profile": profile.to_dict(),
                "config_sha256": _json_hash(config.raw),
                "sources": source_identities,
                "calendar": calendar_summary,
                "universes": universe_summaries,
                "features": feature_summaries,
                "accepted_limitations": list(config.accepted_limitations),
                "capabilities": list(profile.capabilities),
                "excluded_capabilities": list(profile.excluded_capabilities),
            }
            _manifest_path(temporary).write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            validation = validate_qlib_store(temporary, profile)
            manifest["validation"] = validation
            _manifest_path(temporary).write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            temporary.rename(target)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        operation.succeed(
            outputs={
                "artifacts": [{"id": materialization_id, "type": "qlib_dataset"}],
                "result_summary": {
                    "materialization_id": materialization_id,
                    "output_dir": config.output_dir,
                    "reused": False,
                    "validation": manifest["validation"],
                },
            },
            side_effects={
                "changed_paths": [config.output_dir],
                "created_artifacts": [materialization_id],
            },
            accepted_limitations=list(config.accepted_limitations),
        )
        return manifest


def _read_instrument_rows(path: Path, calendar_set: set[str]) -> tuple[int, int]:
    instruments: set[str] = set()
    intervals = 0
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                raise ValidationError(
                    f"Malformed instrument row at {path}:{line_number}"
                )
            instrument, start, end = parts
            if start not in calendar_set or end not in calendar_set or start > end:
                raise ValidationError(
                    f"Invalid instrument interval at {path}:{line_number}"
                )
            instruments.add(instrument.lower())
            intervals += 1
    return len(instruments), intervals


def validate_qlib_store(
    target: Path, profile: QlibTargetProfile | None = None
) -> dict[str, Any]:
    target = target.resolve()
    manifest_file = _manifest_path(target)
    if not manifest_file.is_file():
        raise ValidationError(f"Missing materialization manifest: {manifest_file}")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"Invalid materialization manifest: {manifest_file}"
        ) from exc
    profile = profile or get_profile(manifest.get("profile", {}).get("profile_id", ""))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValidationError(f"Unsupported manifest schema: {manifest.get('schema')}")
    producer = manifest.get("producer", {})
    if (
        producer.get("id") != PRODUCER_ID
        or producer.get("schema_version") != PRODUCER_SCHEMA_VERSION
    ):
        raise ValidationError(
            "Unsupported or missing materialization producer identity"
        )
    calendar_file = target / "calendars" / "day.txt"
    if not calendar_file.is_file():
        raise ValidationError("Missing Qlib daily calendar")
    calendar = [
        line.strip()
        for line in calendar_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not calendar or calendar != sorted(set(calendar)):
        raise ValidationError(
            "Qlib daily calendar must be nonempty, sorted, and unique"
        )
    calendar_set = set(calendar)
    universe_summary: dict[str, Any] = {}
    for name in ("all", *profile.required_universes):
        path = target / "instruments" / f"{name}.txt"
        if not path.is_file():
            raise ValidationError(f"Missing Qlib instrument universe: {name}")
        instruments, intervals = _read_instrument_rows(path, calendar_set)
        if instruments == 0:
            raise ValidationError(f"Qlib instrument universe is empty: {name}")
        universe_summary[name] = {"instruments": instruments, "intervals": intervals}
    feature_summary: dict[str, Any] = {}
    for feature in profile.features:
        paths = sorted((target / "features").glob(f"*/{feature.name}.day.bin"))
        if not paths:
            raise ValidationError(
                f"No Qlib binaries found for required feature: {feature.name}"
            )
        invalid = 0
        for path in paths:
            size = path.stat().st_size
            if size < 8 or size % 4:
                invalid += 1
                continue
            with path.open("rb") as stream:
                start = float(np.frombuffer(stream.read(4), dtype="<f4")[0])
            value_count = size // 4 - 1
            if (
                not start.is_integer()
                or start < 0
                or int(start) + value_count > len(calendar)
            ):
                invalid += 1
        if invalid:
            raise ValidationError(
                f"Feature {feature.name} has {invalid} invalid Qlib binaries"
            )
        feature_summary[feature.name] = {
            "instruments": len(paths),
            "invalid_binaries": 0,
        }
    return {
        "status": "passed",
        "calendar_dates": len(calendar),
        "universes": universe_summary,
        "features": feature_summary,
        "qlib_public_api_smoke": "not_run",
    }


def validate_materialized_path(
    target: Path,
    *,
    project_root: Path,
    actor_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    target = target.resolve()
    try:
        relative_target = str(target.relative_to(project_root))
    except ValueError as exc:
        raise ConfigError("Validation target must be inside the project root") from exc
    journal = ActionJournal(project_root, actor_id=actor_id, session_id=session_id)
    with journal.operation(
        "data.validate",
        read_only=True,
        inputs={"parameters": {"target": relative_target}},
    ) as operation:
        result = validate_qlib_store(target)
        operation.succeed(outputs={"result_summary": result})
        return result
