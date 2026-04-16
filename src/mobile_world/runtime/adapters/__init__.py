"""Reference framework adapter implementations."""

from mobile_world.runtime.adapters.hermes_template import HermesTemplateAdapter
from mobile_world.runtime.adapters.nanobot_opengui import NanobotOpenGUIAdapter
from mobile_world.runtime.adapters.openclaw_template import OpenClawTemplateAdapter

__all__ = [
    "NanobotOpenGUIAdapter",
    "OpenClawTemplateAdapter",
    "HermesTemplateAdapter",
]
