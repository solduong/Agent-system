#!/usr/bin/env python3
"""
One-shot runner: invokes the registry_auditor agent against the full
current state of the system — all agents + all workflow YAMLs.
"""
import json, os, sys
from pathlib import Path

BASE = Path(__file__).parent.parent  # agent-system root
_SI = Path(__file__).parent       # system_improvement/
sys.path.insert(0, str(_SI))        # find agent_registry here

# Load .env if present
def _load_dotenv():
    env = BASE / ".env"
    if not env.exists(): return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
_load_dotenv()

from agent_registry import AgentRegistry
from runtime.dispatcher import run_step

# ── 1. Build the task message ──────────────────────────────────────────────

registry = AgentRegistry(base_dir=BASE)

# All agents: description + full system prompt
agent_sections = []
for name, cfg in sorted(registry.agents.items()):
    prompt = Path(cfg["_prompt_path"]).read_text().strip()
    agent_sections.append(
        f"### {name}\n"
        f"**Config description:** {cfg.get('description', '(none)')}\n"
        f"**Model:** {cfg.get('model', 'default')}\n\n"
        f"**system_prompt.md:**\n```\n{prompt}\n```"
    )

agents_block = "\n\n---\n\n".join(agent_sections)

# All workflow YAMLs
wf_files = []
wf_dir = BASE / "workflows"
if wf_dir.exists():
    wf_files += sorted(wf_dir.glob("*.yaml"))
for proj_dir in sorted((BASE / "Employees" / "Projects-Specific Agents and Workflows").iterdir()):
    pd = proj_dir / "workflows"
    if pd.exists():
        wf_files += sorted(pd.glob("*.yaml"))

wf_sections = []
for f in wf_files:
    source = f.relative_to(BASE)
    content = f.read_text().strip()
    wf_sections.append(f"### {f.stem}  (`{source}`)\n```yaml\n{content}\n```")

workflows_block = "\n\n---\n\n".join(wf_sections)

task = f"""Perform a full audit of the agent system in its current state.

## All agents (general only — no project loaded)

{agents_block}

---

## All workflow YAMLs (general + all projects)

{workflows_block}

---

## Instructions

Audit every agent against every workflow it appears in.
- Flag stale descriptions, role overlaps, gaps, and any agent that exists but is referenced in no workflow.
- Flag any workflow step whose `agent:` field references an agent that does not exist in the registry.
- Do not propose renaming any agent.
- Save your full audit report to: audit_report.md in the working directory.
- Print a summary to stdout when done.
"""

# ── 2. Load the agent config ───────────────────────────────────────────────

agent_config = registry.load_agent("registry_auditor")

# ── 3. Run ─────────────────────────────────────────────────────────────────

working_dir = BASE / "audit_output"
working_dir.mkdir(exist_ok=True)

print(f"Running registry_auditor  model={agent_config['model']}")
print(f"Working dir: {working_dir}")
print(f"Agents loaded: {len(registry.agents)}")
print(f"Workflows found: {len(wf_files)}")
print()

result = run_step(agent_config, task, working_dir)

print(f"\nStatus:   {result.status}")
print(f"Duration: {result.duration_seconds:.1f}s")
print(f"Tokens:   in={result.input_tokens:,}  out={result.output_tokens:,}")
print(f"Log:      {result.log_path}")

if result.status == "ok":
    report = working_dir / "audit_report.md"
    if report.exists():
        print(f"\nAudit report saved to: {report}")
    else:
        print("\n[transcript — audit_report.md not written by agent, printing transcript]")
        print(result.transcript)
elif result.error:
    print(f"\nError: {result.error}")
