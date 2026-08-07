from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from .errors import ConfigError, ResearchError, ValidationError
from .journal import ActionJournal
from .materialization import _json_hash, _project_path, validate_qlib_store
from .registration import load_registry

STUDY_SCHEMA = "qlibx.research_study/v1"
RUN_SCHEMA = "qlibx.research_run/v1"
AUDIT_SCHEMA = "qlibx.eligibility_audit/v1"
DECISION_SCHEMA = "qlibx.research_decision/v1"
RESEARCH_PRODUCER = "qlibx.monthly_cross_sectional_research/v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _package_version() -> str:
    try:
        return version("qlibx")
    except PackageNotFoundError:
        return "0+unknown"


def _finite_or_none(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _finite_or_none(value.item())
    if isinstance(value, np.ndarray):
        return [_finite_or_none(item) for item in value.tolist()]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _finite_or_none(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_or_none(item) for item in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_finite_or_none(value), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_iso(value: Any, context: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigError(f"{context} must use YYYY-MM-DD") from exc


@dataclass(frozen=True)
class StudyConfig:
    path: Path
    raw: dict[str, Any]
    study_id: str
    provider_dir: str
    registry_dir: str
    output_dir: str
    audit_output: str
    discovery: tuple[date, date]
    confirmation: tuple[date, date]
    reserved_from: date

    @classmethod
    def load(cls, path: Path) -> StudyConfig:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Unable to read study config: {path}") from exc
        if not isinstance(raw, dict) or raw.get("schema") != STUDY_SCHEMA:
            raise ConfigError(f"Study config schema must be {STUDY_SCHEMA}")
        periods = raw.get("periods")
        if not isinstance(periods, dict):
            raise ConfigError("periods must be an object")

        def period(name: str) -> tuple[date, date]:
            values = periods.get(name)
            if not isinstance(values, list) or len(values) != 2:
                raise ConfigError(f"periods.{name} must contain start and end dates")
            result = (_parse_iso(values[0], name), _parse_iso(values[1], name))
            if result[0] > result[1]:
                raise ConfigError(f"periods.{name} start must not exceed end")
            return result

        required_strings = (
            "study_id",
            "provider_dir",
            "registry_dir",
            "output_dir",
            "audit_output",
        )
        if any(not isinstance(raw.get(key), str) for key in required_strings):
            raise ConfigError("Study identifiers and paths must be strings")
        portfolio = raw.get("portfolio", {})
        statistics = raw.get("statistics", {})
        if portfolio.get("weighting") != "equal":
            raise ConfigError("The first-cycle engine supports equal weighting only")
        tail_fraction = portfolio.get("tail_fraction")
        if not isinstance(tail_fraction, (int, float)) or not 0 < tail_fraction <= 0.5:
            raise ConfigError("portfolio.tail_fraction must be in (0, 0.5]")
        if statistics.get("confidence_interval") != "moving_block_bootstrap":
            raise ConfigError("Unsupported confidence-interval method")
        return cls(
            path=path.resolve(),
            raw=raw,
            study_id=raw["study_id"],
            provider_dir=raw["provider_dir"],
            registry_dir=raw["registry_dir"],
            output_dir=raw["output_dir"],
            audit_output=raw["audit_output"],
            discovery=period("discovery"),
            confirmation=period("confirmation"),
            reserved_from=_parse_iso(periods.get("reserved_from"), "reserved_from"),
        )


@dataclass(frozen=True)
class HoldingSchedule:
    holding_month: str
    observation_index: int
    entry_index: int
    exit_index: int


class QlibBinaryStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        calendar_path = self.root / "calendars" / "day.txt"
        self.calendar = tuple(
            date.fromisoformat(line)
            for line in calendar_path.read_text(encoding="utf-8").splitlines()
            if line
        )
        self.index = {current: index for index, current in enumerate(self.calendar)}
        self.instruments, self.membership = self._load_membership("k200")
        self.instrument_index = {
            instrument: index for index, instrument in enumerate(self.instruments)
        }
        self._features: dict[str, np.ndarray] = {}

    def _load_membership(self, name: str) -> tuple[tuple[str, ...], np.ndarray]:
        rows = []
        instruments = set()
        path = self.root / "instruments" / f"{name}.txt"
        for line in path.read_text(encoding="utf-8").splitlines():
            instrument, start, end = line.split("\t")
            instruments.add(instrument)
            rows.append(
                (instrument, date.fromisoformat(start), date.fromisoformat(end))
            )
        names = tuple(sorted(instruments))
        name_index = {instrument: index for index, instrument in enumerate(names)}
        membership = np.zeros((len(names), len(self.calendar)), dtype=bool)
        for instrument, start, end in rows:
            membership[
                name_index[instrument], self.index[start] : self.index[end] + 1
            ] = True
        return names, membership

    def feature_matrix(self, field: str) -> np.ndarray:
        if field in self._features:
            return self._features[field]
        matrix = np.full(
            (len(self.instruments), len(self.calendar)), np.nan, dtype=np.float64
        )
        for instrument_index, instrument in enumerate(self.instruments):
            path = self.root / "features" / instrument.lower() / f"{field}.day.bin"
            if not path.is_file():
                continue
            raw = np.fromfile(path, dtype="<f4")
            if len(raw) < 2 or not float(raw[0]).is_integer():
                raise ValidationError(f"Invalid Qlib feature binary: {path}")
            start = int(raw[0])
            end = start + len(raw) - 1
            if start < 0 or end > len(self.calendar):
                raise ValidationError(f"Qlib feature binary exceeds calendar: {path}")
            matrix[instrument_index, start:end] = raw[1:]
        self._features[field] = matrix
        return matrix


def _month_end_indexes(calendar: Sequence[date]) -> list[int]:
    result = []
    for index, current in enumerate(calendar):
        if index == len(calendar) - 1 or calendar[index + 1].strftime(
            "%Y-%m"
        ) != current.strftime("%Y-%m"):
            result.append(index)
    return result


def build_holding_schedule(
    store: QlibBinaryStore, config: StudyConfig
) -> list[HoldingSchedule]:
    month_ends = _month_end_indexes(store.calendar)
    schedules = []
    for position in range(len(month_ends) - 1):
        observation = month_ends[position]
        next_observation = month_ends[position + 1]
        entry = observation + 1
        exit_index = next_observation + 1
        if entry >= len(store.calendar) or exit_index >= len(store.calendar):
            continue
        holding_month = store.calendar[entry].strftime("%Y-%m")
        holding_date = date.fromisoformat(f"{holding_month}-01")
        if holding_date < config.discovery[0].replace(day=1):
            continue
        if holding_date >= config.reserved_from.replace(day=1):
            continue
        schedules.append(
            HoldingSchedule(
                holding_month=holding_month,
                observation_index=observation,
                entry_index=entry,
                exit_index=exit_index,
            )
        )
    return schedules


def _period_name(config: StudyConfig, holding_month: str) -> str | None:
    current = date.fromisoformat(f"{holding_month}-01")
    if (
        config.discovery[0].replace(day=1)
        <= current
        <= config.discovery[1].replace(day=1)
    ):
        return "discovery"
    if (
        config.confirmation[0].replace(day=1)
        <= current
        <= config.confirmation[1].replace(day=1)
    ):
        return "confirmation"
    return None


def _registration(registry: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    try:
        return registry["datasets"][dataset_id]
    except KeyError as exc:
        raise ConfigError(f"Required dataset is not registered: {dataset_id}") from exc


def _source_relation(project_root: Path, registration: dict[str, Any]) -> str:
    source = registration["source"]
    path = _project_path(project_root, source["path"], context="registered source")
    escaped = str(path).replace("'", "''")
    if source["type"] == "csv":
        return f"read_csv('{escaped}', header=true, all_varchar=true)"
    if source["type"] == "parquet":
        return f"read_parquet('{escaped}')"
    table = source.get("table")
    return '"' + str(table).replace('"', '""') + '"'


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _load_auxiliary_diagnostics(
    project_root: Path,
    registry: dict[str, Any],
    observation_dates: Sequence[date],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], str]]:
    date_values = ",".join(
        f"'{current.strftime('%Y%m%d')}'" for current in observation_dates
    )
    market_registration = _registration(registry, "k200_membership_local/v1")
    market_map = market_registration["canonical_mapping"]
    market_relation = _source_relation(project_root, market_registration)
    connection = duckdb.connect(":memory:")
    try:
        market_rows = connection.execute(
            f"select cast({_quote(market_map['date'])} as varchar), "
            f"cast({_quote(market_map['instrument'])} as varchar), "
            f"try_cast(replace(cast({_quote(market_map['market_cap'])} as varchar), ',', '') as double) "
            f"from {market_relation} where cast({_quote(market_map['date'])} as varchar) in ({date_values})"
        ).fetchall()
        sector_registration = _registration(registry, "fgsc_classification_local/v1")
        sector_map = sector_registration["canonical_mapping"]
        sector_relation = _source_relation(project_root, sector_registration)
        sector_rows = connection.execute(
            f"select cast({_quote(sector_map['date'])} as varchar), "
            f"cast({_quote(sector_map['instrument'])} as varchar), "
            f"cast({_quote(sector_map['sector_code'])} as varchar) "
            f"from {sector_relation} where cast({_quote(sector_map['date'])} as varchar) in ({date_values})"
        ).fetchall()
    finally:
        connection.close()
    market_caps = {
        (current, instrument): float(value)
        for current, instrument, value in market_rows
        if value is not None and value > 0
    }
    sectors = {
        (current, instrument): code.split(".")[1]
        for current, instrument, code in sector_rows
        if code and len(code.split(".")) > 1
    }
    return market_caps, sectors


def _raw_corporate_action_audit(
    project_root: Path,
    registry: dict[str, Any],
    start: date,
    end: date,
    threshold: float,
) -> dict[str, Any]:
    prices = _registration(registry, "dataguide_daily_prices_local/v1")
    members = _registration(registry, "k200_membership_local/v1")
    pmap = prices["canonical_mapping"]
    mmap = members["canonical_mapping"]
    price_relation = _source_relation(project_root, prices)
    member_relation = _source_relation(project_root, members)
    number = lambda name: (
        f"try_cast(replace(cast(p.{_quote(pmap[name])} as varchar), ',', '') as double)"
    )
    start_text = start.strftime("%Y%m%d")
    end_text = end.strftime("%Y%m%d")
    connection = duckdb.connect(":memory:")
    try:
        row = connection.execute(
            f"""
            with joined as (
                select {number("close")} close_value,
                       {number("reference_price")} reference_value,
                       {number("previous_close")} previous_value,
                       {number("adjustment_factor")} factor_value
                from {price_relation} p
                inner join {member_relation} m
                  on cast(p.{_quote(pmap["date"])} as varchar) = cast(m.{_quote(mmap["date"])} as varchar)
                 and cast(p.{_quote(pmap["instrument"])} as varchar) = cast(m.{_quote(mmap["instrument"])} as varchar)
                where cast(p.{_quote(pmap["date"])} as varchar) between '{start_text}' and '{end_text}'
            ), valid as (
                select *, close_value / reference_value - 1 adjusted_return,
                       close_value * factor_value / previous_value - 1 factor_return
                from joined
            )
            select count(*),
                   count(*) filter (where close_value <= 0 or reference_value <= 0
                                          or close_value is null or reference_value is null),
                   count(*) filter (where factor_value is not null and abs(factor_value - 1) > 1e-12),
                   count(*) filter (where abs(adjusted_return) > {float(threshold)}),
                   count(*) filter (where close_value > 0 and reference_value > 0
                                          and previous_value > 0 and factor_value > 0
                                          and abs(adjusted_return - factor_return) > 1e-5),
                   max(abs(adjusted_return))
            from valid
            """
        ).fetchone()
    except duckdb.Error as exc:
        raise ResearchError(f"Corporate-action audit query failed: {exc}") from exc
    finally:
        connection.close()
    return {
        "member_price_rows": int(row[0]),
        "invalid_positive_inputs": int(row[1]),
        "adjustment_factor_events": int(row[2]),
        "absolute_returns_above_threshold": int(row[3]),
        "return_formula_mismatches": int(row[4]),
        "maximum_absolute_adjusted_return": float(row[5])
        if row[5] is not None
        else None,
        "extreme_return_threshold": threshold,
    }


def _select_portfolios(
    store: QlibBinaryStore,
    pbr: np.ndarray,
    schedule: HoldingSchedule,
    tail_fraction: float,
) -> tuple[dict[str, list[int]], dict[str, Any]]:
    member_indexes = np.flatnonzero(store.membership[:, schedule.observation_index])
    values = pbr[member_indexes, schedule.observation_index]
    positive_mask = np.isfinite(values) & (values > 0)
    eligible = member_indexes[positive_mask]
    ordered = sorted(
        eligible.tolist(),
        key=lambda item: (
            pbr[item, schedule.observation_index],
            store.instruments[item],
        ),
    )
    tail_count = max(1, math.floor(len(ordered) * tail_fraction)) if ordered else 0
    portfolios = {
        "low_pbr": ordered[:tail_count],
        "high_pbr": ordered[-tail_count:] if tail_count else [],
        "baseline": ordered,
    }
    summary = {
        "members": len(member_indexes),
        "pbr_missing": int(np.count_nonzero(~np.isfinite(values))),
        "pbr_zero": int(np.count_nonzero(np.isfinite(values) & (values == 0))),
        "pbr_negative": int(np.count_nonzero(np.isfinite(values) & (values < 0))),
        "eligible": len(ordered),
        "tail_count": tail_count,
    }
    return portfolios, summary


def _last_observation_lag(
    matrix: np.ndarray, instrument: int, index: int
) -> int | None:
    available = np.flatnonzero(np.isfinite(matrix[instrument, :index]))
    return index - int(available[-1]) if len(available) else None


def build_eligibility_audit(
    project_root: Path,
    config: StudyConfig,
    store: QlibBinaryStore,
    registry: dict[str, Any],
) -> dict[str, Any]:
    schedules = build_holding_schedule(store, config)
    pbr = store.feature_matrix("pbr")
    returns = store.feature_matrix("adjusted_daily_return")
    tail_fraction = float(config.raw["portfolio"]["tail_fraction"])
    months = []
    total_entry_unavailable = 0
    total_holding_missing = 0
    holding_missing_cases: list[dict[str, Any]] = []
    stale_candidates = 0
    maximum_staleness = 0
    previous_members: set[int] | None = None
    additions = removals = 0
    for schedule in schedules:
        portfolios, summary = _select_portfolios(store, pbr, schedule, tail_fraction)
        current_members = set(
            np.flatnonzero(store.membership[:, schedule.observation_index]).tolist()
        )
        if previous_members is not None:
            additions += len(current_members - previous_members)
            removals += len(previous_members - current_members)
        previous_members = current_members
        for instrument in current_members:
            if not math.isfinite(pbr[instrument, schedule.observation_index]):
                lag = _last_observation_lag(pbr, instrument, schedule.observation_index)
                if lag is not None:
                    stale_candidates += 1
                    maximum_staleness = max(maximum_staleness, lag)
        portfolio_quality = {}
        for name, selected in portfolios.items():
            entry_unavailable = sum(
                not math.isfinite(returns[instrument, schedule.entry_index])
                for instrument in selected
            )
            missing_instruments = []
            for instrument in selected:
                if not math.isfinite(returns[instrument, schedule.entry_index]):
                    continue
                missing_offsets = np.flatnonzero(
                    np.isnan(
                        returns[
                            instrument,
                            schedule.entry_index + 1 : schedule.exit_index + 1,
                        ]
                    )
                )
                if len(missing_offsets):
                    case = {
                        "holding_month": schedule.holding_month,
                        "portfolio": name,
                        "instrument": store.instruments[instrument],
                        "missing_dates": [
                            store.calendar[
                                schedule.entry_index + 1 + int(offset)
                            ].isoformat()
                            for offset in missing_offsets
                        ],
                    }
                    missing_instruments.append(case)
                    holding_missing_cases.append(case)
            holding_missing = len(missing_instruments)
            total_entry_unavailable += entry_unavailable
            total_holding_missing += holding_missing
            portfolio_quality[name] = {
                "selected": len(selected),
                "entry_unavailable": entry_unavailable,
                "holding_return_missing": holding_missing,
                "holding_missing_cases": missing_instruments,
            }
        months.append(
            {
                "holding_month": schedule.holding_month,
                "observation_date": store.calendar[
                    schedule.observation_index
                ].isoformat(),
                "entry_date": store.calendar[schedule.entry_index].isoformat(),
                "exit_date": store.calendar[schedule.exit_index].isoformat(),
                **summary,
                "portfolios": portfolio_quality,
            }
        )
    duplicate_datasets = {
        dataset_id: registration["profile"]["duplicate_key_groups"]
        for dataset_id, registration in registry["datasets"].items()
        if registration["profile"]["duplicate_key_groups"]
    }
    threshold = float(config.raw["diagnostics"]["extreme_return_threshold"])
    raw_action_audit = _raw_corporate_action_audit(
        project_root,
        registry,
        config.discovery[0],
        min(config.reserved_from, store.calendar[-1]),
        threshold,
    )
    minimum_coverage = min(
        month["eligible"] / month["members"] for month in months if month["members"]
    )
    failures = []
    warnings = []
    if duplicate_datasets:
        failures.append(
            {"code": "duplicate_registered_keys", "datasets": duplicate_datasets}
        )
    if any(month["tail_count"] == 0 for month in months):
        failures.append({"code": "empty_portfolio_tail"})
    if total_holding_missing:
        failures.append(
            {
                "code": "missing_selected_holding_returns",
                "security_months": total_holding_missing,
                "cases": holding_missing_cases,
            }
        )
    if raw_action_audit["return_formula_mismatches"]:
        failures.append(
            {
                "code": "adjusted_return_formula_mismatch",
                "rows": raw_action_audit["return_formula_mismatches"],
            }
        )
    if minimum_coverage < 0.95:
        warnings.append(
            {
                "code": "positive_pbr_coverage_below_95_percent",
                "minimum": minimum_coverage,
            }
        )
    if total_entry_unavailable:
        warnings.append(
            {
                "code": "selected_entry_unavailable_cash_allocations",
                "security_months": total_entry_unavailable,
            }
        )
    if raw_action_audit["absolute_returns_above_threshold"]:
        warnings.append(
            {
                "code": "extreme_adjusted_returns_observed",
                "rows": raw_action_audit["absolute_returns_above_threshold"],
            }
        )
    return {
        "schema": AUDIT_SCHEMA,
        "study_id": config.study_id,
        "status": "failed"
        if failures
        else "passed_with_warnings"
        if warnings
        else "passed",
        "calendar": {
            "start": store.calendar[0].isoformat(),
            "end": store.calendar[-1].isoformat(),
            "dates": len(store.calendar),
        },
        "summary": {
            "holding_months": len(months),
            "minimum_positive_pbr_coverage": minimum_coverage,
            "selected_entry_unavailable_security_months": total_entry_unavailable,
            "selected_holding_missing_security_months": total_holding_missing,
            "stale_pbr_candidates_excluded": stale_candidates,
            "maximum_prior_pbr_lag_trading_days": maximum_staleness,
            "membership_additions": additions,
            "membership_removals": removals,
        },
        "source_key_duplicates": duplicate_datasets,
        "holding_missing_cases": holding_missing_cases,
        "corporate_action_diagnostics": raw_action_audit,
        "failures": failures,
        "warnings": warnings,
        "months": months,
        "accepted_limitations": config.raw.get("accepted_limitations", []),
    }


def run_eligibility_audit(
    config_path: Path,
    *,
    project_root: Path,
    actor_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    config = StudyConfig.load(config_path.resolve())
    provider = _project_path(project_root, config.provider_dir, context="provider_dir")
    validate_qlib_store(provider)
    registry = load_registry(project_root, config.registry_dir)
    journal = ActionJournal(project_root, actor_id=actor_id, session_id=session_id)
    with journal.operation(
        "research.eligibility.audit",
        read_only=False,
        inputs={"parameters": {"config": str(config.path.relative_to(project_root))}},
        context={"run_id": config.study_id},
    ) as operation:
        audit = build_eligibility_audit(
            project_root, config, QlibBinaryStore(provider), registry
        )
        destination = _project_path(
            project_root, config.audit_output, context="audit_output"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        _write_json(destination, audit)
        operation.succeed(
            outputs={
                "result_summary": {
                    "status": audit["status"],
                    "summary": audit["summary"],
                }
            },
            side_effects={"changed_paths": [config.audit_output]},
            warnings=audit["warnings"],
            accepted_limitations=config.raw.get("accepted_limitations", []),
        )
        return audit


def _compound(values: np.ndarray) -> float:
    return float(np.prod(1.0 + values) - 1.0)


def _momentum(
    returns: np.ndarray, observation: int, lookback: int, skip: int
) -> float | None:
    start = observation - lookback + 1
    end = observation - skip + 1
    if start < 0 or end <= start:
        return None
    window = returns[start:end]
    if len(window) != lookback - skip or np.isnan(window).any():
        return None
    return _compound(window)


def _weighted_mean(values: Iterable[tuple[float, float]]) -> float | None:
    pairs = [
        (value, weight)
        for value, weight in values
        if math.isfinite(value) and weight > 0
    ]
    total = sum(weight for _, weight in pairs)
    return sum(value * weight for value, weight in pairs) / total if total else None


def _portfolio_month(
    name: str,
    selected: list[int],
    schedule: HoldingSchedule,
    store: QlibBinaryStore,
    pbr: np.ndarray,
    returns: np.ndarray,
    market_caps: dict[tuple[str, str], float],
    sectors: dict[tuple[str, str], str],
    config: StudyConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    weight = 1.0 / len(selected)
    observation_text = store.calendar[schedule.observation_index].strftime("%Y%m%d")
    tradable = [
        item for item in selected if math.isfinite(returns[item, schedule.entry_index])
    ]
    cash_weight = weight * (len(selected) - len(tradable))
    invalid = [
        item
        for item in tradable
        if np.isnan(
            returns[item, schedule.entry_index + 1 : schedule.exit_index + 1]
        ).any()
    ]
    holdings = []
    daily_rows = []
    target_weights: dict[str, float] = {
        store.instruments[item]: weight for item in tradable
    }
    if cash_weight:
        target_weights["__CASH__"] = cash_weight
    asset_returns: dict[str, float] = {}
    contributions = []
    daily_returns: list[float] | None = None
    monthly_return: float | None = None
    end_weights: dict[str, float] | None = None
    if not invalid:
        values = {store.instruments[item]: weight for item in tradable}
        cash_value = cash_weight
        daily_returns = []
        for day_index in range(schedule.entry_index + 1, schedule.exit_index + 1):
            previous_total = cash_value + sum(values.values())
            for instrument_index in tradable:
                instrument = store.instruments[instrument_index]
                values[instrument] *= 1.0 + returns[instrument_index, day_index]
            current_total = cash_value + sum(values.values())
            daily_return = current_total / previous_total - 1.0
            daily_returns.append(daily_return)
            daily_rows.append(
                {
                    "holding_month": schedule.holding_month,
                    "date": store.calendar[day_index].isoformat(),
                    "portfolio": name,
                    "return": daily_return,
                }
            )
        final_total = cash_value + sum(values.values())
        monthly_return = final_total - 1.0
        end_weights = {
            instrument: value / final_total for instrument, value in values.items()
        }
        if cash_value:
            end_weights["__CASH__"] = cash_value / final_total
        for instrument_index in tradable:
            instrument = store.instruments[instrument_index]
            asset_return = _compound(
                returns[
                    instrument_index, schedule.entry_index + 1 : schedule.exit_index + 1
                ]
            )
            asset_returns[instrument] = asset_return
            contributions.append(
                {
                    "holding_month": schedule.holding_month,
                    "portfolio": name,
                    "instrument": instrument,
                    "contribution": weight * asset_return,
                }
            )
    lookback = int(config.raw["diagnostics"]["momentum_lookback_days"])
    skip = int(config.raw["diagnostics"]["momentum_skip_days"])
    momentum_values = []
    size_values = []
    sector_weights: dict[str, float] = defaultdict(float)
    for instrument_index in selected:
        instrument = store.instruments[instrument_index]
        momentum_value = _momentum(
            returns[instrument_index], schedule.observation_index, lookback, skip
        )
        if momentum_value is not None:
            momentum_values.append((momentum_value, weight))
        market_cap = market_caps.get((observation_text, instrument))
        if market_cap and market_cap > 0:
            size_values.append((math.log(market_cap), weight))
        sector = sectors.get((observation_text, instrument))
        if sector:
            sector_weights[sector] += weight
        holdings.append(
            {
                "holding_month": schedule.holding_month,
                "observation_date": store.calendar[
                    schedule.observation_index
                ].isoformat(),
                "entry_date": store.calendar[schedule.entry_index].isoformat(),
                "exit_date": store.calendar[schedule.exit_index].isoformat(),
                "portfolio": name,
                "instrument": instrument,
                "pbr": float(pbr[instrument_index, schedule.observation_index]),
                "target_weight": weight,
                "entry_available": instrument_index in tradable,
                "holding_return_complete": instrument_index not in invalid,
                "security_holding_return": asset_returns.get(instrument),
                "contribution": weight * asset_returns[instrument]
                if instrument in asset_returns
                else None,
            }
        )
    return (
        {
            "portfolio": name,
            "selected": len(selected),
            "entry_unavailable": len(selected) - len(tradable),
            "holding_missing": len(invalid),
            "return": monthly_return,
            "daily_returns": daily_returns,
            "target_weights": target_weights,
            "end_weights": end_weights,
            "momentum": _weighted_mean(momentum_values),
            "log_market_cap": _weighted_mean(size_values),
            "sector_weights": dict(sorted(sector_weights.items())),
        },
        holdings,
        daily_rows + contributions,
    )


def _turnover(
    target: dict[str, float], previous_end: dict[str, float] | None
) -> float | None:
    if previous_end is None:
        return None
    keys = sorted(set(target) | set(previous_end))
    return 0.5 * math.fsum(
        abs(target.get(key, 0.0) - previous_end.get(key, 0.0)) for key in keys
    )


def _annualized_return(
    values: Sequence[float], periods_per_year: int = 252
) -> float | None:
    if not values:
        return None
    return float(
        np.prod(1.0 + np.asarray(values)) ** (periods_per_year / len(values)) - 1.0
    )


def _maximum_drawdown(values: Sequence[float]) -> float | None:
    if not values:
        return None
    nav = np.cumprod(1.0 + np.asarray(values))
    peak = np.maximum.accumulate(np.concatenate(([1.0], nav)))[1:]
    return float(np.min(nav / peak - 1.0))


def _beta(portfolio: Sequence[float], baseline: Sequence[float]) -> float | None:
    if len(portfolio) < 2 or len(portfolio) != len(baseline):
        return None
    x = np.asarray(baseline)
    y = np.asarray(portfolio)
    variance = float(np.var(x, ddof=1))
    return float(np.cov(x, y, ddof=1)[0, 1] / variance) if variance > 0 else None


def _bootstrap_ci(
    values: Sequence[float], config: StudyConfig
) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    statistics = config.raw["statistics"]
    block = min(int(statistics["bootstrap_block_months"]), len(values))
    resamples = int(statistics["bootstrap_resamples"])
    rng = np.random.default_rng(int(statistics["seed"]))
    array = np.asarray(values, dtype=np.float64)
    starts = np.arange(len(array) - block + 1)
    blocks_needed = math.ceil(len(array) / block)
    means = np.empty(resamples, dtype=np.float64)
    for sample_index in range(resamples):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate([array[start : start + block] for start in chosen])[
            : len(array)
        ]
        means[sample_index] = np.mean(sample)
    alpha = 1.0 - float(statistics["confidence_level"])
    return (
        float(np.quantile(means, alpha / 2)),
        float(np.quantile(means, 1 - alpha / 2)),
    )


def _portfolio_metrics(
    portfolio: str,
    months: Sequence[dict[str, Any]],
    daily: Sequence[dict[str, Any]],
    period: str,
    annualization: int,
) -> dict[str, Any]:
    period_months = [item for item in months if item["period"] == period]
    monthly_values = [item[portfolio]["return"] for item in period_months]
    valid_monthly = [float(value) for value in monthly_values if value is not None]
    daily_values = [
        float(item["return"])
        for item in daily
        if item["portfolio"] == portfolio
        and any(
            month["holding_month"] == item["holding_month"] for month in period_months
        )
    ]
    turnovers = [
        item[portfolio]["turnover"]
        for item in period_months
        if item[portfolio]["turnover"] is not None
    ]
    yearly: dict[str, list[float]] = defaultdict(list)
    for month in period_months:
        value = month[portfolio]["return"]
        if value is not None:
            yearly[month["holding_month"][:4]].append(float(value))
    return {
        "months": len(period_months),
        "valid_months": len(valid_monthly),
        "annualized_return": _annualized_return(daily_values, annualization),
        "annualized_volatility": float(
            np.std(daily_values, ddof=1) * math.sqrt(annualization)
        )
        if len(daily_values) > 1
        else None,
        "maximum_drawdown": _maximum_drawdown(daily_values),
        "positive_month_percentage": sum(value > 0 for value in valid_monthly)
        / len(valid_monthly)
        if valid_monthly
        else None,
        "average_one_way_turnover": float(np.mean(turnovers)) if turnovers else None,
        "year_returns": {
            year: float(np.prod(1.0 + np.asarray(values)) - 1.0)
            for year, values in sorted(yearly.items())
        },
    }


def _comparison_metrics(
    left: str,
    right: str,
    months: Sequence[dict[str, Any]],
    config: StudyConfig,
    period: str,
) -> dict[str, Any]:
    values = []
    for month in months:
        if month["period"] != period:
            continue
        left_value = month[left]["return"]
        right_value = month[right]["return"]
        if left_value is not None and right_value is not None:
            values.append(float(left_value - right_value))
    interval = _bootstrap_ci(values, config)
    return {
        "months": len(values),
        "average_monthly_return": float(np.mean(values)) if values else None,
        "confidence_interval_95": list(interval) if interval else None,
        "positive_month_percentage": sum(value > 0 for value in values) / len(values)
        if values
        else None,
    }


def _active_exposure(
    months: Sequence[dict[str, Any]], portfolio: str, field: str, period: str
) -> dict[str, Any]:
    values = []
    for month in months:
        if month["period"] != period:
            continue
        portfolio_value = month[portfolio].get(field)
        baseline_value = month["baseline"].get(field)
        if portfolio_value is not None and baseline_value is not None:
            values.append(float(portfolio_value - baseline_value))
    return {
        "months": len(values),
        "mean_active": float(np.mean(values)) if values else None,
    }


def _sector_exposure(
    months: Sequence[dict[str, Any]], portfolio: str, period: str
) -> dict[str, Any]:
    concentrations = []
    maximum_active = []
    for month in months:
        if month["period"] != period:
            continue
        left = month[portfolio]["sector_weights"]
        baseline = month["baseline"]["sector_weights"]
        if not left or not baseline:
            continue
        keys = sorted(set(left) | set(baseline))
        active = [left.get(key, 0.0) - baseline.get(key, 0.0) for key in keys]
        concentrations.append(0.5 * math.fsum(abs(value) for value in active))
        maximum_active.append(max(abs(value) for value in active))
    return {
        "months": len(concentrations),
        "mean_active_weight_distance": float(np.mean(concentrations))
        if concentrations
        else None,
        "maximum_single_sector_active_weight": max(maximum_active)
        if maximum_active
        else None,
    }


def _compute_study(
    project_root: Path,
    config: StudyConfig,
    store: QlibBinaryStore,
    registry: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    schedules = build_holding_schedule(store, config)
    observation_dates = [store.calendar[item.observation_index] for item in schedules]
    market_caps, sectors = _load_auxiliary_diagnostics(
        project_root, registry, observation_dates
    )
    pbr = store.feature_matrix("pbr")
    returns = store.feature_matrix("adjusted_daily_return")
    tail_fraction = float(config.raw["portfolio"]["tail_fraction"])
    months: list[dict[str, Any]] = []
    holdings: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    contributions: list[dict[str, Any]] = []
    previous_ends: dict[str, dict[str, float] | None] = {
        "low_pbr": None,
        "high_pbr": None,
        "baseline": None,
    }
    for schedule in schedules:
        period = _period_name(config, schedule.holding_month)
        if period is None:
            continue
        selected, eligibility = _select_portfolios(store, pbr, schedule, tail_fraction)
        month: dict[str, Any] = {
            "holding_month": schedule.holding_month,
            "period": period,
            "observation_date": store.calendar[schedule.observation_index].isoformat(),
            "entry_date": store.calendar[schedule.entry_index].isoformat(),
            "exit_date": store.calendar[schedule.exit_index].isoformat(),
            "members": eligibility["members"],
            "eligible": eligibility["eligible"],
        }
        for portfolio in ("low_pbr", "high_pbr", "baseline"):
            result, portfolio_holdings, mixed_rows = _portfolio_month(
                portfolio,
                selected[portfolio],
                schedule,
                store,
                pbr,
                returns,
                market_caps,
                sectors,
                config,
            )
            result["turnover"] = _turnover(
                result["target_weights"], previous_ends[portfolio]
            )
            previous_ends[portfolio] = result["end_weights"]
            month[portfolio] = result
            holdings.extend(portfolio_holdings)
            for row in mixed_rows:
                if "date" in row:
                    daily_rows.append(row)
                else:
                    contributions.append(row)
        baseline_daily = month["baseline"]["daily_returns"]
        month["baseline_realized_volatility"] = (
            float(np.std(baseline_daily, ddof=1) * math.sqrt(252))
            if baseline_daily and len(baseline_daily) > 1
            else None
        )
        month["market_direction"] = (
            "rising"
            if month["baseline"]["return"] is not None
            and month["baseline"]["return"] > 0
            else "falling"
        )
        months.append(month)
    discovery_volatility = [
        month["baseline_realized_volatility"]
        for month in months
        if month["period"] == "discovery"
        and month["baseline_realized_volatility"] is not None
    ]
    volatility_threshold = float(np.median(discovery_volatility))
    for month in months:
        volatility = month["baseline_realized_volatility"]
        month["volatility_regime"] = (
            "high"
            if volatility is not None and volatility > volatility_threshold
            else "low"
        )
    annualization = int(config.raw["statistics"]["annualization_days"])
    metrics: dict[str, Any] = {
        "volatility_threshold": volatility_threshold,
        "portfolios": {},
        "comparisons": {},
        "exposures": {},
        "regimes": {},
    }
    for period in ("discovery", "confirmation"):
        metrics["portfolios"][period] = {
            portfolio: _portfolio_metrics(
                portfolio, months, daily_rows, period, annualization
            )
            for portfolio in ("low_pbr", "high_pbr", "baseline")
        }
        metrics["comparisons"][period] = {
            "low_minus_baseline": _comparison_metrics(
                "low_pbr", "baseline", months, config, period
            ),
            "low_minus_high": _comparison_metrics(
                "low_pbr", "high_pbr", months, config, period
            ),
        }
        period_days: dict[str, dict[str, float]] = defaultdict(dict)
        for row in daily_rows:
            if _period_name(config, row["holding_month"]) == period:
                period_days[row["date"]][row["portfolio"]] = row["return"]
        aligned = [values for values in period_days.values() if len(values) == 3]
        baseline_daily = [values["baseline"] for values in aligned]
        metrics["exposures"][period] = {}
        for portfolio in ("low_pbr", "high_pbr"):
            metrics["exposures"][period][portfolio] = {
                "market_beta": _beta(
                    [values[portfolio] for values in aligned], baseline_daily
                ),
                "momentum": _active_exposure(months, portfolio, "momentum", period),
                "log_market_cap": _active_exposure(
                    months, portfolio, "log_market_cap", period
                ),
                "sector": _sector_exposure(months, portfolio, period),
            }
        metrics["regimes"][period] = {}
        for dimension in ("market_direction", "volatility_regime"):
            labels = sorted(
                {month[dimension] for month in months if month["period"] == period}
            )
            metrics["regimes"][period][dimension] = {}
            for label in labels:
                subset = [
                    month
                    for month in months
                    if month["period"] == period and month[dimension] == label
                ]
                low_baseline = [
                    month["low_pbr"]["return"] - month["baseline"]["return"]
                    for month in subset
                    if month["low_pbr"]["return"] is not None
                    and month["baseline"]["return"] is not None
                ]
                low_high = [
                    month["low_pbr"]["return"] - month["high_pbr"]["return"]
                    for month in subset
                    if month["low_pbr"]["return"] is not None
                    and month["high_pbr"]["return"] is not None
                ]
                metrics["regimes"][period][dimension][label] = {
                    "months": len(subset),
                    "valid_low_minus_baseline_months": len(low_baseline),
                    "valid_low_minus_high_months": len(low_high),
                    "low_minus_baseline_mean": float(np.mean(low_baseline))
                    if low_baseline
                    else None,
                    "low_minus_high_mean": float(np.mean(low_high))
                    if low_high
                    else None,
                }
    concentration = {}
    for portfolio in ("low_pbr", "high_pbr"):
        totals: dict[str, float] = defaultdict(float)
        for row in contributions:
            if row["portfolio"] == portfolio:
                totals[row["instrument"]] += row["contribution"]
        ordered = sorted(totals.items(), key=lambda item: abs(item[1]), reverse=True)
        absolute_total = sum(abs(value) for value in totals.values())
        concentration[portfolio] = {
            "top_5_absolute_contribution_share": sum(
                abs(value) for _, value in ordered[:5]
            )
            / absolute_total
            if absolute_total
            else None,
            "top_contributors": [
                {"instrument": instrument, "summed_monthly_contribution": value}
                for instrument, value in ordered[:10]
            ],
        }
    metrics["concentration"] = concentration
    invalid = audit["status"] == "failed"
    discovery = metrics["comparisons"]["discovery"]
    confirmation = metrics["comparisons"]["confirmation"]
    comparisons = ("low_minus_baseline", "low_minus_high")
    if invalid:
        classification = "invalid"
        affected = sorted(
            {case["instrument"] for case in audit.get("holding_missing_cases", [])}
        )
        rationale = (
            "Selected holding returns are unresolved for "
            f"{', '.join(affected) if affected else 'one or more securities'}; "
            "without a registered successor/corporate-action mapping, the preregistered test is unreliable."
        )
    elif all(
        discovery[name]["average_monthly_return"] > 0
        and confirmation[name]["average_monthly_return"] > 0
        and confirmation[name]["confidence_interval_95"][0] > 0
        for name in comparisons
    ):
        classification = "supported"
        rationale = "Both preregistered comparisons are positive in both periods and confirmation intervals exclude zero."
    elif all(confirmation[name]["average_monthly_return"] <= 0 for name in comparisons):
        classification = "challenged"
        rationale = "Both confirmation-period comparison means are nonpositive."
    else:
        classification = "inconclusive"
        rationale = (
            "The preregistered comparisons are mixed, unstable, or too uncertain."
        )
    decision = {
        "schema": DECISION_SCHEMA,
        "study_id": config.study_id,
        "classification": classification,
        "rationale": rationale,
        "execution_completed": True,
        "gross_research_only": True,
    }
    return {
        "months": months,
        "holdings": holdings,
        "daily": daily_rows,
        "contributions": contributions,
        "metrics": metrics,
        "decision": decision,
    }


def _write_csv(
    path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_finite_or_none(row))


def _format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _evidence_report(
    config: StudyConfig, audit: dict[str, Any], result: dict[str, Any], run_id: str
) -> str:
    metrics = result["metrics"]
    lines = [
        "# KOSPI 200 Low-P/B First-Cycle Evidence Report",
        "",
        f"Run ID: `{run_id}`  ",
        f"Decision: **{result['decision']['classification'].upper()}**  ",
        "Returns are gross, research-only, and not evidence of investability.",
        "",
        "## Research result",
        "",
        result["decision"]["rationale"],
        "",
        "| Period | Portfolio | Annualized return | Volatility | Max drawdown | Positive months | Turnover |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for period in ("discovery", "confirmation"):
        for portfolio in ("low_pbr", "baseline", "high_pbr"):
            item = metrics["portfolios"][period][portfolio]
            lines.append(
                f"| {period} | {portfolio} | {_format_percent(item['annualized_return'])} | "
                f"{_format_percent(item['annualized_volatility'])} | {_format_percent(item['maximum_drawdown'])} | "
                f"{_format_percent(item['positive_month_percentage'])} | {_format_percent(item['average_one_way_turnover'])} |"
            )
    lines.extend(
        [
            "",
            "## Primary comparisons",
            "",
            "| Period | Comparison | N | Average monthly return | 95% moving-block bootstrap interval | Positive months |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for period in ("discovery", "confirmation"):
        for name in ("low_minus_baseline", "low_minus_high"):
            item = metrics["comparisons"][period][name]
            interval = item["confidence_interval_95"]
            interval_text = (
                f"[{_format_percent(interval[0])}, {_format_percent(interval[1])}]"
                if interval
                else "n/a"
            )
            lines.append(
                f"| {period} | {name} | {item['months']} | {_format_percent(item['average_monthly_return'])} | "
                f"{interval_text} | {_format_percent(item['positive_month_percentage'])} |"
            )
    lines.extend(["", "## Annual portfolio returns", ""])
    for period in ("discovery", "confirmation"):
        lines.extend(
            [
                f"### {period.title()}",
                "",
                "| Year | Low P/B | Baseline | High P/B |",
                "|---|---:|---:|---:|",
            ]
        )
        years = metrics["portfolios"][period]["baseline"]["year_returns"]
        for year in years:
            lines.append(
                f"| {year} | {_format_percent(metrics['portfolios'][period]['low_pbr']['year_returns'].get(year))} | "
                f"{_format_percent(metrics['portfolios'][period]['baseline']['year_returns'].get(year))} | "
                f"{_format_percent(metrics['portfolios'][period]['high_pbr']['year_returns'].get(year))} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Exposure diagnostics",
            "",
            "| Period | Portfolio | Market beta | Active momentum | Active log market cap | Sector active-weight distance |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for period in ("discovery", "confirmation"):
        for portfolio in ("low_pbr", "high_pbr"):
            exposure = metrics["exposures"][period][portfolio]
            lines.append(
                f"| {period} | {portfolio} | {exposure['market_beta']:.3f} | "
                f"{exposure['momentum']['mean_active']:.3f} | "
                f"{exposure['log_market_cap']['mean_active']:.3f} | "
                f"{exposure['sector']['mean_active_weight_distance']:.2%} |"
            )
    lines.extend(
        [
            "",
            "## Regime diagnostics",
            "",
            "| Period | Dimension | Regime | N | Low minus baseline | Low minus high |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for period in ("discovery", "confirmation"):
        for dimension in ("market_direction", "volatility_regime"):
            for label, values in metrics["regimes"][period][dimension].items():
                lines.append(
                    f"| {period} | {dimension} | {label} | {values['months']} | "
                    f"{_format_percent(values['low_minus_baseline_mean'])} | "
                    f"{_format_percent(values['low_minus_high_mean'])} |"
                )
    lines.extend(["", "## Concentration diagnostics", ""])
    for portfolio in ("low_pbr", "high_pbr"):
        concentration = metrics["concentration"][portfolio]
        top = ", ".join(
            item["instrument"] for item in concentration["top_contributors"][:5]
        )
        lines.append(
            f"- {portfolio}: top-five absolute contribution share "
            f"{_format_percent(concentration['top_5_absolute_contribution_share'])}; "
            f"largest absolute contributors: {top}."
        )
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            (
                f"- Eligibility audit: **{audit['status']}**; minimum positive-P/B coverage "
                f"{audit['summary']['minimum_positive_pbr_coverage']:.2%}."
            ),
            (
                f"- Unresolved selected holding-return cases: "
                f"{audit['summary']['selected_holding_missing_security_months']}. "
                "These invalidate the evidence decision under the frozen rule."
            ),
            f"- Discovery-period high-volatility threshold: {metrics['volatility_threshold']:.2%} annualized.",
            "- Market beta is measured against the eligible equal-weight baseline; it is diagnostic, not hedged.",
            "- Momentum and log-market-cap values are active weighted means versus the baseline.",
            "- Sector diagnostics use unlabeled FGSC level-1 codes and are available only from 2020.",
            "- Detailed regime, exposure, concentration, eligibility, and contribution results are preserved in the JSON/CSV artifacts.",
        ]
    )
    for case in audit.get("holding_missing_cases", []):
        lines.append(
            f"- Missing case: {case['instrument']} in {case['portfolio']} for "
            f"{case['holding_month']}; first missing date {case['missing_dates'][0]}."
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in config.raw.get("accepted_limitations", []))
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "A completed run and an evidence classification are separate. This report does not model taxes, costs, "
                "spreads, market impact, shorting, hedging, or live execution. No parameter was changed after inspecting performance."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_rows(
    result: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    monthly_rows = []
    for month in result["months"]:
        low_return = month["low_pbr"]["return"]
        baseline_return = month["baseline"]["return"]
        high_return = month["high_pbr"]["return"]
        monthly_rows.append(
            {
                "holding_month": month["holding_month"],
                "period": month["period"],
                "observation_date": month["observation_date"],
                "entry_date": month["entry_date"],
                "exit_date": month["exit_date"],
                "members": month["members"],
                "eligible": month["eligible"],
                "low_pbr_return": low_return,
                "baseline_return": baseline_return,
                "high_pbr_return": high_return,
                "low_minus_baseline": low_return - baseline_return
                if low_return is not None and baseline_return is not None
                else None,
                "low_minus_high": low_return - high_return
                if low_return is not None and high_return is not None
                else None,
                "low_pbr_turnover": month["low_pbr"]["turnover"],
                "baseline_turnover": month["baseline"]["turnover"],
                "high_pbr_turnover": month["high_pbr"]["turnover"],
                "market_direction": month["market_direction"],
                "volatility_regime": month["volatility_regime"],
                "baseline_realized_volatility": month["baseline_realized_volatility"],
            }
        )
    contribution_rows = sorted(
        result["contributions"],
        key=lambda row: (row["holding_month"], row["portfolio"], row["instrument"]),
    )
    return monthly_rows, contribution_rows


def _render_artifacts(
    directory: Path,
    config: StudyConfig,
    audit: dict[str, Any],
    result: dict[str, Any],
    run_id: str,
) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    monthly_rows, contribution_rows = _artifact_rows(result)
    _write_json(directory / "eligibility-audit.json", audit)
    _write_json(directory / "metrics.json", result["metrics"])
    _write_json(directory / "decision.json", result["decision"])
    _write_csv(directory / "monthly-results.csv", monthly_rows, tuple(monthly_rows[0]))
    _write_csv(
        directory / "portfolio-holdings.csv",
        result["holdings"],
        (
            "holding_month",
            "observation_date",
            "entry_date",
            "exit_date",
            "portfolio",
            "instrument",
            "pbr",
            "target_weight",
            "entry_available",
            "holding_return_complete",
            "security_holding_return",
            "contribution",
        ),
    )
    _write_csv(
        directory / "daily-portfolio-returns.csv",
        result["daily"],
        ("holding_month", "date", "portfolio", "return"),
    )
    _write_csv(
        directory / "security-contributions.csv",
        contribution_rows,
        ("holding_month", "portfolio", "instrument", "contribution"),
    )
    (directory / "evidence-report.md").write_text(
        _evidence_report(config, audit, result, run_id), encoding="utf-8"
    )
    return sorted(path.name for path in directory.iterdir() if path.is_file())


def run_study(
    config_path: Path,
    *,
    project_root: Path,
    actor_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    config = StudyConfig.load(config_path.resolve())
    provider = _project_path(project_root, config.provider_dir, context="provider_dir")
    validation = validate_qlib_store(provider)
    manifest = json.loads(
        (provider / "qlibx-manifest.json").read_text(encoding="utf-8")
    )
    registry = load_registry(project_root, config.registry_dir)
    producer = {
        "id": RESEARCH_PRODUCER,
        "package_version": _package_version(),
        "implementation_sha256": _sha256(Path(__file__)),
    }
    run_id = _json_hash(
        {
            "producer": producer,
            "config": config.raw,
            "materialization_id": manifest["materialization_id"],
            "registrations": {
                name: item["registration_id"]
                for name, item in registry["datasets"].items()
            },
        }
    )
    journal = ActionJournal(project_root, actor_id=actor_id, session_id=session_id)
    with journal.operation(
        "research.run.execute",
        read_only=False,
        inputs={
            "effective_config_id": _json_hash(config.raw),
            "artifacts": [manifest["materialization_id"]],
            "parameters": {"config": str(config.path.relative_to(project_root))},
        },
        context={"run_id": run_id},
    ) as operation:
        store = QlibBinaryStore(provider)
        audit = build_eligibility_audit(project_root, config, store, registry)
        result = _compute_study(project_root, config, store, registry, audit)
        target = _project_path(project_root, config.output_dir, context="output_dir")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent)
        )
        try:
            artifact_names = _render_artifacts(temporary, config, audit, result, run_id)
            artifact_hashes = {
                name: _sha256(temporary / name) for name in artifact_names
            }
            reproduced = False
            if target.exists():
                existing_manifest_path = target / "run-manifest.json"
                if not existing_manifest_path.is_file():
                    raise ResearchError(
                        f"Existing research output has no manifest: {config.output_dir}"
                    )
                existing_manifest = json.loads(
                    existing_manifest_path.read_text(encoding="utf-8")
                )
                existing_hashes = existing_manifest.get("artifact_sha256", {})
                if (
                    existing_manifest.get("run_id") != run_id
                    or existing_hashes != artifact_hashes
                ):
                    raise ResearchError(
                        "Reproduction differs from the existing frozen research run"
                    )
                reproduced = True
                shutil.rmtree(temporary)
            else:
                run_manifest = {
                    "schema": RUN_SCHEMA,
                    "run_id": run_id,
                    "created_at": _utc_now(),
                    "study_id": config.study_id,
                    "producer": producer,
                    "config_sha256": _json_hash(config.raw),
                    "materialization_id": manifest["materialization_id"],
                    "registration_ids": {
                        name: item["registration_id"]
                        for name, item in registry["datasets"].items()
                    },
                    "provider_validation": validation,
                    "artifact_sha256": artifact_hashes,
                    "decision": result["decision"],
                    "accepted_limitations": config.raw.get("accepted_limitations", []),
                }
                _write_json(temporary / "run-manifest.json", run_manifest)
                temporary.rename(target)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
            raise
        summary = {
            "status": "succeeded",
            "run_id": run_id,
            "output_dir": config.output_dir,
            "reproduced": reproduced,
            "audit_status": audit["status"],
            "decision": result["decision"],
        }
        operation.succeed(
            outputs={
                "artifacts": [{"id": run_id, "type": "research_run"}],
                "result_summary": summary,
            },
            side_effects={"changed_paths": [] if reproduced else [config.output_dir]},
            warnings=audit["warnings"],
            accepted_limitations=config.raw.get("accepted_limitations", []),
        )
        return summary
