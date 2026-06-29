from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


ABILITY_MODULE_NAMES = ("config", "main", "background")


def install_openhome_stubs() -> None:
    src_module = types.ModuleType("src")
    agent_module = types.ModuleType("src.agent")
    capability_module = types.ModuleType("src.agent.capability")
    capability_worker_module = types.ModuleType("src.agent.capability_worker")
    main_module = types.ModuleType("src.main")

    class MatchingCapability:
        pass

    class CapabilityWorker:
        def __init__(self, capability):
            self.capability = capability

    class AgentWorker:
        pass

    capability_module.MatchingCapability = MatchingCapability
    capability_worker_module.CapabilityWorker = CapabilityWorker
    main_module.AgentWorker = AgentWorker

    sys.modules.setdefault("src", src_module)
    sys.modules.setdefault("src.agent", agent_module)
    sys.modules.setdefault("src.agent.capability", capability_module)
    sys.modules.setdefault("src.agent.capability_worker", capability_worker_module)
    sys.modules.setdefault("src.main", main_module)


def import_ability_modules(ability_dir: Path):
    ability_path = str(ability_dir)
    if ability_path not in sys.path:
        sys.path.insert(0, ability_path)
    install_openhome_stubs()
    for module_name in ABILITY_MODULE_NAMES:
        sys.modules.pop(module_name, None)
    ability_config = importlib.import_module("config")
    main_module = importlib.import_module("main")
    background_module = importlib.import_module("background")
    return ability_config, main_module, background_module
