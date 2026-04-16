"""Registry for framework adapter profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mobile_world.runtime.protocol.adapter import AdapterProfile, FrameworkAdapter


AdapterFactory = Callable[..., FrameworkAdapter]


@dataclass(frozen=True)
class AdapterRegistration:
    """Immutable adapter registration record."""

    profile: AdapterProfile
    adapter_class: type[FrameworkAdapter]
    factory: AdapterFactory | None = None


_ADAPTER_REGISTRY: dict[str, AdapterRegistration] = {}


def register_adapter(
    profile: AdapterProfile,
    adapter_class: type[FrameworkAdapter],
    factory: AdapterFactory | None = None,
    *,
    overwrite: bool = False,
) -> None:
    """Register one framework adapter profile."""
    key = profile.name.strip()
    if not key:
        raise ValueError("Adapter profile name cannot be empty")
    if key in _ADAPTER_REGISTRY and not overwrite:
        raise ValueError(
            f"Adapter profile '{key}' already registered. Use overwrite=True to replace it."
        )
    _ADAPTER_REGISTRY[key] = AdapterRegistration(
        profile=profile,
        adapter_class=adapter_class,
        factory=factory,
    )


def has_adapter(profile_name: str) -> bool:
    """Return whether one adapter profile is registered."""
    return profile_name in _ADAPTER_REGISTRY


def get_adapter_registration(profile_name: str) -> AdapterRegistration:
    """Get one adapter registration by profile name."""
    try:
        return _ADAPTER_REGISTRY[profile_name]
    except KeyError as exc:
        available = ", ".join(sorted(_ADAPTER_REGISTRY.keys())) or "(none)"
        raise ValueError(
            f"Unknown adapter profile '{profile_name}'. Available profiles: {available}"
        ) from exc


def list_adapters() -> list[AdapterProfile]:
    """List all registered adapter profiles."""
    return [entry.profile for _, entry in sorted(_ADAPTER_REGISTRY.items(), key=lambda kv: kv[0])]


def list_registrations() -> list[AdapterRegistration]:
    """List full registration entries."""
    return [entry for _, entry in sorted(_ADAPTER_REGISTRY.items(), key=lambda kv: kv[0])]


def clear_adapters() -> None:
    """Clear adapter registry (used by tests)."""
    _ADAPTER_REGISTRY.clear()
