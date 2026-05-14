#!/usr/bin/env python3
"""
Agent Registry
Loads general agents from agents/ then merges project-specific agents on top.
Project agents with the same name as a general agent override the general one.
"""

import json
from pathlib import Path


class AgentRegistry:
    def __init__(self, base_dir=None, project_id=None):
        """
        base_dir:   root of the agent-system directory (default: directory of this file)
        project_id: if set, also loads agents from projects/<project_id>/agents/
        """
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.project_id = project_id
        self.agents = {}       # name → config dict
        self.agent_sources = {}  # name → "general" | "project:<id>"
        self._load()

    # ── Loading ──────────────────────────────────────────────────────────────

    GENERAL_AGENTS_DIR  = Path("Employees") / "General Agents"
    PROJECT_AGENTS_DIR  = Path("Employees") / "Projects-Specific Agents and Workflows"

    def _load(self):
        # 1. General agents
        self._load_from_dir(self.base_dir / self.GENERAL_AGENTS_DIR, source="general")

        # 2. Project-specific agents (override general agents with the same name)
        if self.project_id:
            project_agents = self.base_dir / self.PROJECT_AGENTS_DIR / self.project_id / "agents"
            self._load_from_dir(project_agents, source=f"project:{self.project_id}")

    def _load_from_dir(self, directory: Path, source: str):
        if not directory.exists():
            return
        for config_file in sorted(directory.rglob("config.json")):
            agent_dir = config_file.parent
            with open(config_file) as f:
                config = json.load(f)
            config["_prompt_path"] = str(agent_dir / "system_prompt.md")
            config["_source"] = source
            self.agents[agent_dir.name] = config
            self.agent_sources[agent_dir.name] = source

    # ── Public API ────────────────────────────────────────────────────────────

    def reload(self):
        """Rescan all agent directories and refresh the registry in place.
        Called after prompt_engineer writes a new agent to disk."""
        self.agents = {}
        self.agent_sources = {}
        self._load()

    def load_agent(self, name: str, overrides: dict = None) -> dict:
        if name not in self.agents:
            available = ", ".join(sorted(self.agents))
            raise ValueError(f"Agent '{name}' not found. Available: {available}")
        config = self.agents[name].copy()
        if overrides:
            config["parameters"] = {**config.get("parameters", {}), **overrides}
        return config

    def list_agents(self, source_filter: str = None) -> list:
        """
        source_filter: "general", "project:<id>", or None for all
        """
        return [
            cfg for name, cfg in self.agents.items()
            if source_filter is None or cfg.get("_source") == source_filter
        ]

    def describe(self) -> str:
        lines = [f"AgentRegistry (project={self.project_id or 'none'})"]
        for name, cfg in sorted(self.agents.items()):
            tag = "  [project]" if "project:" in cfg.get("_source", "") else "  [general]"
            lines.append(f"{tag} {name}: {cfg.get('description', '')}")
        return "\n".join(lines)


class ProjectContext:
    def __init__(self, project_id: str, registry: AgentRegistry = None):
        self.project_id = project_id
        self.registry = registry
        self.shared_memory = {}
        self.logs = []

    def save_artifact(self, key: str, value):
        self.shared_memory[key] = value

    def get_artifact(self, key: str):
        return self.shared_memory.get(key)

    # ── Persistence (used by WorkflowEngine for resumability) ─────────────
    def save_to_disk(self, path):
        """Persist artifacts + completed step log to disk as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "project_id": self.project_id,
            "shared_memory": {
                k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else repr(v))
                for k, v in self.shared_memory.items()
            },
            "logs": self.logs,
        }
        path.write_text(json.dumps(data, indent=2, default=str))

    @classmethod
    def load_from_disk(cls, path, registry: "AgentRegistry" = None):
        path = Path(path)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        ctx = cls(data["project_id"], registry=registry)
        ctx.shared_memory = data.get("shared_memory", {})
        ctx.logs = data.get("logs", [])
        return ctx


if __name__ == "__main__":
    import sys
    base = Path(__file__).parent
    project = sys.argv[1] if len(sys.argv) > 1 else None
    registry = AgentRegistry(base_dir=base, project_id=project)
    print(registry.describe())
