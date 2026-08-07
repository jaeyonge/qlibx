from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from .errors import ConfigError, DataContractError, MappingConfirmationRequired
from .journal import ActionJournal
from .materialization import (
    SourceReader,
    SourceRef,
    _file_hash,
    _json_hash,
    _project_path,
)

REGISTRATION_BUNDLE_SCHEMA = "qlibx.dataset_registration_bundle/v1"
REGISTRATION_SCHEMA = "qlibx.dataset_registration/v1"
REGISTRY_INDEX_SCHEMA = "qlibx.dataset_registry/v1"
REGISTRATION_PRODUCER = "qlibx.dataset_registration/v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$")

DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "trading_date", "일자", "거래일자", "적용일자"),
    "instrument": ("instrument", "security", "ticker", "종목약코드", "종목코드2"),
    "is_open": ("is_open", "open_flag", "주식개장구분"),
    "pbr": ("pbr", "PBR", "price_to_book"),
    "beta": ("beta", "베타"),
    "close": ("close", "종가"),
    "reference_price": ("reference_price", "기준가"),
    "previous_close": ("previous_close", "전일종가"),
    "adjustment_factor": ("adjustment_factor", "수정계수"),
    "market_cap": ("market_cap", "상장시가총액"),
    "sector_code": ("sector_code", "FGSC지수코드"),
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_column(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _registry_filename(dataset_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "__", dataset_id) + ".json"


def propose_mapping(
    available_columns: Iterable[str], required_fields: Iterable[str]
) -> dict[str, Any]:
    available = tuple(available_columns)
    normalized: dict[str, list[str]] = {}
    for column in available:
        normalized.setdefault(_normalize_column(column), []).append(column)
    proposed: dict[str, str] = {}
    ambiguous: dict[str, list[str]] = {}
    missing: list[str] = []
    for canonical in required_fields:
        aliases = DEFAULT_ALIASES.get(canonical, (canonical,))
        candidates: list[str] = []
        for alias in aliases:
            candidates.extend(normalized.get(_normalize_column(alias), []))
        candidates = sorted(set(candidates))
        if len(candidates) == 1:
            proposed[canonical] = candidates[0]
        elif candidates:
            ambiguous[canonical] = candidates
        else:
            missing.append(canonical)
    return {"proposed": proposed, "ambiguous": ambiguous, "missing": sorted(missing)}


@dataclass(frozen=True)
class DatasetRegistrationSpec:
    dataset_id: str
    kind: str
    source: SourceRef
    required_fields: tuple[str, ...]
    mappings: dict[str, str]
    mapping_confirmed: bool
    key: tuple[str, ...]
    date_field: str
    date_format: str
    accepted_limitations: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> DatasetRegistrationSpec:
        context = f"datasets[{index}]"
        dataset_id = raw.get("dataset_id")
        if not isinstance(dataset_id, str) or not _SAFE_ID.fullmatch(dataset_id):
            raise ConfigError(f"{context}.dataset_id is invalid")
        required = raw.get("required_fields")
        mappings = raw.get("mappings", {})
        key = raw.get("key")
        limitations = raw.get("accepted_limitations", [])
        if not isinstance(required, list) or not all(
            isinstance(item, str) for item in required
        ):
            raise ConfigError(f"{context}.required_fields must be a list of strings")
        if not isinstance(mappings, dict) or not all(
            isinstance(name, str) and isinstance(column, str)
            for name, column in mappings.items()
        ):
            raise ConfigError(
                f"{context}.mappings must map canonical names to source columns"
            )
        if (
            not isinstance(key, list)
            or not key
            or not all(isinstance(item, str) for item in key)
        ):
            raise ConfigError(
                f"{context}.key must be a nonempty list of canonical fields"
            )
        if not isinstance(limitations, list) or not all(
            isinstance(item, str) for item in limitations
        ):
            raise ConfigError(
                f"{context}.accepted_limitations must be a list of strings"
            )
        date_field = raw.get("date_field", "date")
        if not isinstance(date_field, str):
            raise ConfigError(f"{context}.date_field must be a string")
        return cls(
            dataset_id=dataset_id,
            kind=str(raw.get("kind", "table")),
            source=SourceRef.from_dict(
                {
                    **raw.get("source", {}),
                    "dataset_id": dataset_id,
                },
                context=f"{context}.source",
            ),
            required_fields=tuple(required),
            mappings=dict(mappings),
            mapping_confirmed=raw.get("mapping_confirmed") is True,
            key=tuple(key),
            date_field=date_field,
            date_format=str(raw.get("date_format", "%Y%m%d")),
            accepted_limitations=tuple(limitations),
        )


@dataclass(frozen=True)
class RegistrationBundle:
    output_dir: str
    datasets: tuple[DatasetRegistrationSpec, ...]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> RegistrationBundle:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Unable to read registration bundle: {path}") from exc
        if not isinstance(raw, dict) or raw.get("schema") != REGISTRATION_BUNDLE_SCHEMA:
            raise ConfigError(
                f"Registration schema must be {REGISTRATION_BUNDLE_SCHEMA}"
            )
        datasets = raw.get("datasets")
        if not isinstance(datasets, list) or not datasets:
            raise ConfigError("Registration bundle must contain datasets")
        specs = tuple(
            DatasetRegistrationSpec.from_dict(item, index)
            for index, item in enumerate(datasets)
        )
        identifiers = [item.dataset_id for item in specs]
        if len(identifiers) != len(set(identifiers)):
            raise ConfigError("Dataset IDs must be unique within a registration bundle")
        output_dir = raw.get("output_dir", "data/qlibx/registry")
        if not isinstance(output_dir, str):
            raise ConfigError("output_dir must be a string")
        return cls(output_dir=output_dir, datasets=specs, raw=raw)


def _resolved_mapping(
    spec: DatasetRegistrationSpec, available: tuple[str, ...]
) -> dict[str, str]:
    proposal = propose_mapping(available, spec.required_fields)
    mapping = {**proposal["proposed"], **spec.mappings}
    absent_sources = sorted(set(mapping.values()) - set(available))
    missing = sorted(set(spec.required_fields) - set(mapping))
    if absent_sources or missing:
        raise DataContractError(
            f"Registration mapping is incomplete for {spec.dataset_id}",
            details={
                "missing_canonical_fields": missing,
                "unknown_source_columns": absent_sources,
                "available_columns": list(available),
            },
        )
    unresolved_ambiguity = {
        field: candidates
        for field, candidates in proposal["ambiguous"].items()
        if field not in spec.mappings
    }
    if unresolved_ambiguity:
        raise MappingConfirmationRequired(
            f"Ambiguous column mappings require user confirmation for {spec.dataset_id}",
            details={"ambiguous": unresolved_ambiguity},
        )
    if not spec.mapping_confirmed:
        raise MappingConfirmationRequired(
            f"Column mappings are not user-confirmed for {spec.dataset_id}",
            details={"proposed_mapping": mapping},
        )
    if not set(spec.key).issubset(mapping):
        raise ConfigError(
            f"Registration key contains unmapped fields for {spec.dataset_id}"
        )
    if spec.date_field not in mapping:
        raise ConfigError(f"date_field is not mapped for {spec.dataset_id}")
    return mapping


def _relation_sql(project_root: Path, source: SourceRef) -> str:
    path = _project_path(
        project_root, source.path, context=f"source {source.dataset_id}.path"
    )
    escaped = str(path).replace("'", "''")
    if source.type == "csv":
        return f"read_csv('{escaped}', header=true, all_varchar=true)"
    if source.type == "parquet":
        return f"read_parquet('{escaped}')"
    assert source.table is not None
    return '"' + source.table.replace('"', '""') + '"'


def _profile_source(
    project_root: Path, spec: DatasetRegistrationSpec, mapping: dict[str, str]
) -> dict[str, Any]:
    relation = _relation_sql(project_root, spec.source)
    connection = (
        duckdb.connect(
            str(_project_path(project_root, spec.source.path, context="source.path")),
            read_only=True,
        )
        if spec.source.type == "duckdb"
        else duckdb.connect(":memory:")
    )
    quote = lambda value: '"' + value.replace('"', '""') + '"'
    key_columns = [mapping[field] for field in spec.key]
    required_columns = [mapping[field] for field in spec.required_fields]
    date_column = mapping[spec.date_field]
    null_expression = " + ".join(
        f"sum(case when {quote(column)} is null or trim(cast({quote(column)} as varchar)) = '' then 1 else 0 end)"
        for column in required_columns
    )
    key_expression = ", ".join(quote(column) for column in key_columns)
    try:
        row_count, required_nulls, minimum_date, maximum_date = connection.execute(
            f"select count(*), {null_expression}, min(cast({quote(date_column)} as varchar)), "
            f"max(cast({quote(date_column)} as varchar)) from {relation}"
        ).fetchone()
        duplicate_groups = connection.execute(
            f"select count(*) from (select {key_expression}, count(*) n from {relation} "
            f"group by {key_expression} having count(*) > 1)"
        ).fetchone()[0]
    except duckdb.Error as exc:
        raise DataContractError(f"Unable to profile {spec.dataset_id}: {exc}") from exc
    finally:
        connection.close()
    return {
        "rows": int(row_count),
        "required_field_nulls": int(required_nulls),
        "duplicate_key_groups": int(duplicate_groups),
        "minimum_date": minimum_date,
        "maximum_date": maximum_date,
    }


def inspect_registration_bundle(
    config_path: Path,
    *,
    project_root: Path,
    actor_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    config_path = config_path.resolve()
    relative_config = str(config_path.relative_to(project_root))
    journal = ActionJournal(project_root, actor_id=actor_id, session_id=session_id)
    with journal.operation(
        "data.inspect",
        read_only=True,
        inputs={"parameters": {"config": relative_config}},
    ) as operation:
        bundle = RegistrationBundle.load(config_path)
        datasets = []
        for spec in bundle.datasets:
            reader = SourceReader(project_root, spec.source)
            columns = reader.column_names()
            mapping = _resolved_mapping(spec, columns)
            datasets.append(
                {
                    "dataset_id": spec.dataset_id,
                    "kind": spec.kind,
                    "source": spec.source.path,
                    "available_columns": list(columns),
                    "resolved_mapping": mapping,
                    "mapping_confirmed": True,
                }
            )
        result = {"status": "passed", "datasets": datasets}
        operation.succeed(outputs={"result_summary": result})
        return result


def register_bundle(
    config_path: Path,
    *,
    project_root: Path,
    actor_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    config_path = config_path.resolve()
    relative_config = str(config_path.relative_to(project_root))
    bundle = RegistrationBundle.load(config_path)
    output = _project_path(project_root, bundle.output_dir, context="output_dir")
    journal = ActionJournal(project_root, actor_id=actor_id, session_id=session_id)
    with journal.operation(
        "data.registration.create",
        read_only=False,
        inputs={"parameters": {"config": relative_config}},
    ) as operation:
        results = []
        changed_paths: list[str] = []
        for spec in bundle.datasets:
            reader = SourceReader(project_root, spec.source)
            mapping = _resolved_mapping(spec, reader.column_names())
            source_path = reader.path
            source_identity = {
                "type": spec.source.type,
                "path": spec.source.path,
                "table": spec.source.table,
                "size": source_path.stat().st_size,
                "sha256": _file_hash(source_path),
            }
            profile = _profile_source(project_root, spec, mapping)
            payload = {
                "schema": REGISTRATION_SCHEMA,
                "producer": {
                    "id": REGISTRATION_PRODUCER,
                    "implementation_sha256": _file_hash(Path(__file__)),
                },
                "dataset_id": spec.dataset_id,
                "kind": spec.kind,
                "source": source_identity,
                "canonical_mapping": mapping,
                "mapping_confirmed": True,
                "key": list(spec.key),
                "date_field": spec.date_field,
                "date_format": spec.date_format,
                "profile": profile,
                "accepted_limitations": list(spec.accepted_limitations),
            }
            registration_id = _json_hash(payload)
            registration = {
                **payload,
                "registration_id": registration_id,
                "registered_at": _utc_now(),
            }
            destination = output / _registry_filename(spec.dataset_id)
            reused = False
            if destination.exists():
                existing = json.loads(destination.read_text(encoding="utf-8"))
                if existing.get("registration_id") != registration_id:
                    raise DataContractError(
                        f"Dataset ID already has different registered content: {spec.dataset_id}"
                    )
                registration = existing
                reused = True
            else:
                _atomic_json(destination, registration)
                changed_paths.append(str(destination.relative_to(project_root)))
            results.append(
                {
                    "dataset_id": spec.dataset_id,
                    "registration_id": registration_id,
                    "reused": reused,
                    "profile": profile,
                }
            )
        index_datasets = sorted(
            [
                {
                    "dataset_id": item["dataset_id"],
                    "registration_id": item["registration_id"],
                    "path": _registry_filename(item["dataset_id"]),
                }
                for item in results
            ],
            key=lambda item: item["dataset_id"],
        )
        index_path = output / "index.json"
        existing_index = (
            json.loads(index_path.read_text(encoding="utf-8"))
            if index_path.is_file()
            else None
        )
        if not existing_index or existing_index.get("datasets") != index_datasets:
            index = {
                "schema": REGISTRY_INDEX_SCHEMA,
                "updated_at": _utc_now(),
                "datasets": index_datasets,
            }
            _atomic_json(index_path, index)
            changed_paths.append(str(index_path.relative_to(project_root)))
        result = {
            "status": "succeeded",
            "registry": bundle.output_dir,
            "datasets": results,
        }
        operation.succeed(
            outputs={
                "artifacts": [
                    {"id": item["registration_id"], "type": "dataset_registration"}
                    for item in results
                ],
                "result_summary": result,
            },
            side_effects={"changed_paths": changed_paths},
            accepted_limitations=[
                limitation
                for spec in bundle.datasets
                for limitation in spec.accepted_limitations
            ],
        )
        return result


def load_registry(
    project_root: Path, registry_dir: str = "data/qlibx/registry"
) -> dict[str, Any]:
    root = _project_path(project_root.resolve(), registry_dir, context="registry_dir")
    index_path = root / "index.json"
    if not index_path.is_file():
        raise ConfigError(f"Registry does not exist: {registry_dir}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    registrations = {}
    for item in index.get("datasets", []):
        registration = json.loads((root / item["path"]).read_text(encoding="utf-8"))
        registrations[registration["dataset_id"]] = registration
    return {"index": index, "datasets": registrations}
