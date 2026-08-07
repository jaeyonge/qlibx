from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .errors import ConfigError


@dataclass(frozen=True)
class FeatureContract:
    name: str
    semantic: str
    dtype: str = "float32"
    missing_policy: str = "preserve"
    allowed_transforms: tuple[str, ...] = ("field",)


@dataclass(frozen=True)
class QlibTargetProfile:
    profile_id: str
    schema_version: int
    frequency: str
    timezone: str
    required_universes: tuple[str, ...]
    features: tuple[FeatureContract, ...]
    capabilities: tuple[str, ...]
    excluded_capabilities: tuple[str, ...]
    description: str

    @property
    def feature_map(self) -> dict[str, FeatureContract]:
        return {feature.name: feature for feature in self.features}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


RESEARCH_DAILY_V1 = QlibTargetProfile(
    profile_id="qlib.research_daily/v1",
    schema_version=1,
    frequency="day",
    timezone="Asia/Seoul",
    required_universes=("k200",),
    features=(
        FeatureContract(
            name="pbr",
            semantic="observed price-to-book ratio",
            allowed_transforms=("field",),
        ),
        FeatureContract(
            name="adjusted_daily_return",
            semantic="corporate-action-adjusted daily return",
            allowed_transforms=("ratio_minus_one",),
        ),
    ),
    capabilities=(
        "calendar",
        "dynamic_instruments",
        "feature_retrieval",
        "eligibility_audit",
        "signal_analysis",
    ),
    excluded_capabilities=(
        "order_execution",
        "trade_unit_rounding",
        "price_limit_simulation",
        "volume_capacity",
        "transaction_costs",
    ),
    description=(
        "Research-only daily Qlib dataset. It exposes point-in-time universe "
        "membership, P/B, and an empirically supported adjusted daily return. "
        "It intentionally does not publish Qlib execution price or factor fields."
    ),
)


_PROFILES = {RESEARCH_DAILY_V1.profile_id: RESEARCH_DAILY_V1}


def list_profiles() -> tuple[QlibTargetProfile, ...]:
    return tuple(_PROFILES[key] for key in sorted(_PROFILES))


def get_profile(profile_id: str) -> QlibTargetProfile:
    try:
        return _PROFILES[profile_id]
    except KeyError as exc:
        raise ConfigError(
            f"Unknown target profile: {profile_id}",
            details={"available_profiles": sorted(_PROFILES)},
        ) from exc
