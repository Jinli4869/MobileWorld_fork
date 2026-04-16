"""Protocol package for framework adapters and canonical trajectory contracts."""

from mobile_world.runtime.protocol.adapter import (
    AdapterArtifactsResult,
    AdapterFinalizeInput,
    AdapterFinalizeResult,
    AdapterInitializeInput,
    AdapterInitializeResult,
    AdapterProfile,
    AdapterStepInput,
    AdapterStepResult,
    ArtifactRecord,
    FrameworkAdapter,
    LegacyAgentAdapter,
)
from mobile_world.runtime.protocol.events import (
    CANONICAL_TRAJECTORY_SCHEMA_VERSION,
    CanonicalScoreEvent,
    CanonicalStepEvent,
    CanonicalTrajectoryHeader,
    MetricsQualityFlags,
)
from mobile_world.runtime.protocol.registry import (
    AdapterRegistration,
    clear_adapters,
    get_adapter_registration,
    has_adapter,
    list_adapters,
    list_registrations,
    register_adapter,
)
from mobile_world.runtime.protocol.validation import (
    ProtocolValidationError,
    ValidationIssue,
    ValidationReport,
    run_protocol_preflight,
    validate_adapter_contracts,
    validate_canonical_schema,
)

__all__ = [
    "AdapterArtifactsResult",
    "AdapterFinalizeInput",
    "AdapterFinalizeResult",
    "AdapterInitializeInput",
    "AdapterInitializeResult",
    "AdapterProfile",
    "AdapterRegistration",
    "AdapterStepInput",
    "AdapterStepResult",
    "ArtifactRecord",
    "CANONICAL_TRAJECTORY_SCHEMA_VERSION",
    "CanonicalScoreEvent",
    "CanonicalStepEvent",
    "CanonicalTrajectoryHeader",
    "FrameworkAdapter",
    "LegacyAgentAdapter",
    "MetricsQualityFlags",
    "ProtocolValidationError",
    "ValidationIssue",
    "ValidationReport",
    "clear_adapters",
    "get_adapter_registration",
    "has_adapter",
    "list_adapters",
    "list_registrations",
    "register_adapter",
    "run_protocol_preflight",
    "validate_adapter_contracts",
    "validate_canonical_schema",
]

