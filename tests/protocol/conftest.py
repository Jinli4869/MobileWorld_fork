"""Shared fixtures for protocol baseline tests."""

import pytest

from mobile_world.agents.registry import register_builtin_protocol_adapters
from mobile_world.runtime.protocol.registry import clear_adapters


@pytest.fixture(autouse=True)
def reset_protocol_adapter_registry():
    """Reset adapter registry for deterministic test isolation."""
    clear_adapters()
    register_builtin_protocol_adapters()
    yield
    clear_adapters()

