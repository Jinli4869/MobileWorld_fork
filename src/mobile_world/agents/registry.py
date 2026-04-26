"""
Agent registry and configuration management.
"""

import importlib.util
import inspect
import os
import sys
from pathlib import Path

from loguru import logger

from mobile_world.agents.base import BaseAgent
from mobile_world.agents.implementations.gelab_agent import GelabAgent
from mobile_world.agents.implementations.general_e2e_agent import GeneralE2EAgentMCP
from mobile_world.agents.implementations.gui_owl_1_5 import GUIOWL15AgentMCP
from mobile_world.agents.implementations.mai_ui_agent import MAIUINaivigationAgent
from mobile_world.agents.implementations.planner_executor import PlannerExecutorAgentMCP
from mobile_world.agents.implementations.qwen3vl import Qwen3VLAgentMCP
from mobile_world.agents.implementations.seed_agent import SeedAgent
from mobile_world.agents.implementations.ui_venus_agent import VenusNaviAgent
from mobile_world.runtime.adapters.nanobot_opengui import NanobotOpenGUIAdapter
from mobile_world.runtime.protocol.adapter import (
    AdapterProfile,
    FrameworkAdapter,
    LegacyAgentAdapter,
)
from mobile_world.runtime.protocol.registry import (
    get_adapter_registration,
    has_adapter,
)
from mobile_world.runtime.protocol.registry import (
    list_adapters as list_protocol_adapters,
)
from mobile_world.runtime.protocol.registry import (
    register_adapter as register_protocol_adapter,
)

AGENT_CONFIGS = {
    "qwen3vl": {
        "class": Qwen3VLAgentMCP,
    },
    "planner_executor": {
        "class": PlannerExecutorAgentMCP,
    },
    "mai_ui_agent": {
        "class": MAIUINaivigationAgent,
    },
    "general_e2e": {
        "class": GeneralE2EAgentMCP,
    },
    "seed_agent": {
        "class": SeedAgent,
    },
    "gelab_agent": {
        "class": GelabAgent,
    },
    "ui_venus_agent": {
        "class": VenusNaviAgent,
    },
    "gui_owl_1_5": {
        "class": GUIOWL15AgentMCP,
    },
}


def register_adapter_profile(
    profile_name: str,
    *,
    framework: str,
    adapter_class: type[FrameworkAdapter],
    factory=None,
    capabilities: list[str] | None = None,
    metadata: dict | None = None,
    overwrite: bool = False,
) -> None:
    """Register one protocol adapter profile."""
    profile = AdapterProfile(
        name=profile_name,
        framework=framework,
        capabilities=capabilities or [],
        metadata=metadata or {},
    )
    register_protocol_adapter(
        profile=profile,
        adapter_class=adapter_class,
        factory=factory,
        overwrite=overwrite,
    )


def register_builtin_protocol_adapters() -> None:
    """Register all built-in agents into the protocol adapter registry."""
    for agent_name in AGENT_CONFIGS:
        if has_adapter(agent_name):
            continue
        register_adapter_profile(
            agent_name,
            framework="mobile_world_builtin",
            adapter_class=LegacyAgentAdapter,
            capabilities=["legacy_agent", "gui_action"],
            metadata={"source": "mobile_world.agents.registry"},
        )


def _nanobot_opengui_factory(**kwargs) -> FrameworkAdapter:
    return NanobotOpenGUIAdapter(
        model_name=kwargs.get("model_name"),
        llm_base_url=kwargs.get("llm_base_url"),
        api_key=kwargs.get("api_key"),
        nanobot_fork_path=kwargs.get("nanobot_fork_path"),
        nanobot_config_path=kwargs.get("nanobot_config_path"),
        gui_claw_path=kwargs.get("gui_claw_path"),
        evaluation_mode=kwargs.get("evaluation_mode"),
        allow_adb_bypass=kwargs.get("allow_adb_bypass"),
        nanobot_max_steps=kwargs.get("nanobot_max_steps"),
        nanobot_timeout_seconds=kwargs.get("nanobot_timeout_seconds"),
        nanobot_enable_planner=kwargs.get("nanobot_enable_planner"),
        nanobot_enable_router=kwargs.get("nanobot_enable_router"),
        nanobot_gui_task_max_steps=kwargs.get("nanobot_gui_task_max_steps"),
        nanobot_gui_task_max_calls=kwargs.get("nanobot_gui_task_max_calls"),
    )


def register_reference_framework_adapters() -> None:
    """Register reference external framework adapters."""
    if not has_adapter("nanobot_opengui"):
        register_adapter_profile(
            "nanobot_opengui",
            framework="nanobot_opengui",
            adapter_class=NanobotOpenGUIAdapter,
            factory=_nanobot_opengui_factory,
            capabilities=["gui_action", "mixed_mode"],
            metadata={"source": "mobile_world.runtime.adapters.nanobot_opengui", "execution": "mixed"},
        )


def list_framework_profiles() -> list[str]:
    """List registered protocol adapter profile names."""
    return [profile.name for profile in list_protocol_adapters()]


def create_framework_adapter(
    profile_name: str,
    model_name: str,
    llm_base_url: str,
    api_key: str = "empty",
    **kwargs,
) -> FrameworkAdapter:
    """Create framework adapter instance from profile."""
    registration = get_adapter_registration(profile_name)
    if registration.factory is not None:
        return registration.factory(
            model_name=model_name,
            llm_base_url=llm_base_url,
            api_key=api_key,
            **kwargs,
        )

    legacy_agent = create_agent(
        profile_name,
        model_name=model_name,
        llm_base_url=llm_base_url,
        api_key=api_key,
        **kwargs,
    )
    return registration.adapter_class(legacy_agent)


def load_agent_from_file(file_path: str) -> type[BaseAgent]:
    """Load an agent class from a Python file.

    Args:
        file_path: Path to the Python file containing the agent class

    Returns:
        The agent class that inherits from BaseAgent

    Raises:
        ValueError: If no agent class is found or multiple are found
        FileNotFoundError: If the file doesn't exist
    """
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Agent file not found: {file_path}")

    if not file_path.endswith(".py"):
        raise ValueError(f"Agent file must be a Python file (.py): {file_path}")

    # Load the module from file
    module_name = Path(file_path).stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)

    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # Find all classes that inherit from BaseAgent
    agent_classes = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        # Check if it's a subclass of BaseAgent but not BaseAgent itself
        if issubclass(obj, BaseAgent) and obj is not BaseAgent:
            agent_classes.append((name, obj))

    if len(agent_classes) == 0:
        raise ValueError(f"No class inheriting from BaseAgent found in {file_path}")

    if len(agent_classes) > 1:
        class_names = [name for name, _ in agent_classes]
        logger.warning(
            f"Multiple agent classes found in {file_path}: {class_names}. Using the first one: {class_names[0]}"
        )

    agent_name, agent_class = agent_classes[0]
    logger.info(f"Loaded agent class '{agent_name}' from {file_path}")

    return agent_class


def create_agent(
    agent_type: str, model_name: str, llm_base_url: str, api_key: str = "empty", **kwargs
):
    """Create an agent instance based on the agent type.

    Args:
        agent_type: Either a registered agent type name or path to a Python file containing an agent class
        model_name: Name of the model to use
        llm_base_url: Base URL for the LLM service
        api_key: API key for the LLM service
        **kwargs: Additional keyword arguments to pass to the agent

    Returns:
        An instance of the agent
    """
    skill_config_payload = kwargs.pop("skill_config", None)
    if agent_type.endswith(".py") or os.path.exists(agent_type):
        agent_class = load_agent_from_file(agent_type)
        try:
            agent = agent_class(
                model_name=model_name,
                llm_base_url=llm_base_url,
                api_key=api_key,
                **kwargs,
            )
            return _maybe_wrap_with_skills(agent, skill_config_payload)
        except Exception as e:
            raise ValueError(f"Error creating agent: {e}")

    # Otherwise, use the registry
    if agent_type not in AGENT_CONFIGS:
        raise ValueError(f"Unsupported agent type: {agent_type}")

    agent = AGENT_CONFIGS[agent_type]["class"](
        model_name=model_name,
        llm_base_url=llm_base_url,
        tools=kwargs["env"].tools,
        api_key=api_key,
        **kwargs,
    )
    return _maybe_wrap_with_skills(agent, skill_config_payload)


def _maybe_wrap_with_skills(agent: BaseAgent, skill_config_payload) -> BaseAgent:
    if not skill_config_payload:
        return agent
    from mobile_world.skills.agent import SkillAugmentedAgent
    from mobile_world.skills.config import SkillConfig

    skill_config = SkillConfig.from_payload(skill_config_payload)
    if not skill_config.enabled or skill_config.mode == "off":
        return agent
    return SkillAugmentedAgent(agent, skill_config)


register_builtin_protocol_adapters()
register_reference_framework_adapters()
