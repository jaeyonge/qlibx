from __future__ import annotations

from typing import Any


class QlibxError(Exception):
    """Base error with a stable machine-readable code."""

    code = "qlibx_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ConfigError(QlibxError):
    code = "invalid_config"


class DataContractError(QlibxError):
    code = "data_contract_violation"


class MaterializationError(QlibxError):
    code = "materialization_failed"


class ValidationError(QlibxError):
    code = "validation_failed"


class MappingConfirmationRequired(QlibxError):
    code = "mapping_confirmation_required"


class ResearchError(QlibxError):
    code = "research_failed"
