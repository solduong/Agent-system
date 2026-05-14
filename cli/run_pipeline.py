#!/usr/bin/env python3
"""CLI entrypoint for running an agent workflow against the Anthropic API.

Two modes:

  --workflow  Run a named workflow YAML directly.
  --task      Describe a goal in plain language. The system routes it through
              manager → workflow_planner → engine automatically.
              If the goal is about improving an agent, the manager detects this
              and routes to the interactive self-improvement pipeline instead
              (human approval required for every change).

  When --project / --sub-task are omitted the system prompts interactively.

──────────────────────────────────────────────────────────────────────────────
WORKFLOW MODE  (explicit pipeline)
──────────────────────────────────────────────────────────────────────────────

  # Dry-run
  python3 cli/run_pipeline.py --project qbus3600 --workflow glm_modeling_pipeline \\
      --inputs '{"data_path": "/path/to/data.csv", "response_variable": "y"}' \\
      --working-dir /path/to/outputs --dry-run

  # Real run
  python3 cli/run_pipeline.py --project qbus3600 --workflow glm_modeling_pipeline \\
      --inputs-file ./inputs.json --working-dir /path/to/outputs

  # Resume from a specific step
  python3 cli/run_pipeline.py --project qbus3600 --workflow glm_modeling_pipeline \\
      --working-dir /path/to/outputs --resume-from optimize_macro_f1

──────────────────────────────────────────────────────────────────────────────
TASK MODE  (front-door routing)
──────────────────────────────────────────────────────────────────────────────

  Input a free-form task. The manager plans the steps, workflow_planner writes
  the YAML, and the engine executes it — all in one call.

  # Basic (project + sub-task selected interactively)
  python3 cli/run_pipeline.py \\
      --task "Analyse the donor conversion dataset and produce an EDA report" \\
      --working-dir /path/to/outputs

  # With a project context (loads project-specific agents into the roster)
  python3 cli/run_pipeline.py --project qbus3600 \\
      --task "Run the GLM modeling pipeline on the cleaned dataset at /data/clean.csv" \\
      --working-dir /path/to/outputs

  # Dry-run (prints resolved prompts, no API calls, skips execution)
  python3 cli/run_pipeline.py \\
      --task "Produce a research report on donor fatigue" \\
      --working-dir /path/to/outputs --dry-run
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time, uuid
from pathlib import Path

BASE = Path(__file__).parent.parent          # cli/ → agent-system/ root
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "system_improvement"))  # agent_registry, run_self_improve

# ── .env loader ───────────────────────────────────────────────────────────────

def _load_dotenv():
    env = BASE / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_dotenv()

from agent_registry import AgentRegistry, ProjectContext
from interactive_prompt import (
    prompt_mode,
    prompt_task_text,
    prompt_dry_run,
    prompt_improvement_finding,
    prompt_workflow_details,
    prompt_resume_from,
    prompt_project,
    prompt_sub_task,
    prompt_working_dir,
    prompt_max_parallel,
    prompt_use_cache,
)
from runtime.telemetry import save_run_record, SYSTEM_DIR, AGENT_LOGS_DIR, RUNS_HISTORY
from runtime.improvement_trigger import post_run_check

# workflow_engine lives in workflows/ — load via explicit path
import importlib.util as _ilu
_wf_spec = _ilu.spec_from_file_location(
    "workflow_engine", BASE / "workflows" / "workflow_engine.py"
)
_wf_mod = _ilu.module_from_spec(_wf_spec)
_wf_spec.loader.exec_module(_wf_mod)
WorkflowEngine     = _wf_mod.WorkflowEngine
WorkflowDefinition = _wf_mod.WorkflowDefinition
DISPATCH_AVAILABLE = _wf_mod.DISPATCH_AVAILABLE


# ── Shared helpers ────────────────────────────────────────────────────────────

def _slugify(text: str, fallback: str = "no-subtask") -> str:
    """Turn a sub-task label into a filesystem-safe slug for log folder names."""
    if not text or not text.strip() or text.strip().lower() == "nan":
        return fallback
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    s = re.sub(r"-+", "-", s).strip("-").lower()
    return s[:60] or fallback


def _new_session_log_dir(group: str | None) -> tuple[str, Path]:
    """Generate a unique run_id and return (run_id, per-run agent log directory).

    Folder name follows the convention {run_id}_{sub-task-slug} so each run's
    logs are isolated under System_logs/_agent_logs/.
    """
    run_id = uuid.uuid4().hex[:12]
    folder = AGENT_LOGS_DIR / f"{run_id}_{_slugify(group or '')}"
    folder.mkdir(parents=True, exist_ok=True)
    return run_id, folder


def _print_step(name, rec):
    status = rec.get("status", "?")
    secs   = rec.get("duration_seconds", 0)
    in_t   = rec.get("input_tokens", 0)
    out_t  = rec.get("output_tokens", 0)
    extra  = []
    if rec.get("agent"): extra.append(f"agent={rec['agent']}")
    if secs:             extra.append(f"{secs}s")
    if in_t or out_t:    extra.append(f"in={in_t} out={out_t}")
    if rec.get("error"): extra.append(f"err={rec['error'][:100]}")
    print(f"  [{status:>14s}] {name:30s}  " + "  ".join(extra))


def _print_totals(steps):
    total_in   = sum(s.get("input_tokens",    0) for s in steps)
    total_out  = sum(s.get("output_tokens",   0) for s in steps)
    total_secs = sum(s.get("duration_seconds", 0) for s in steps)
    print(f"tokens in/out={total_in:,}/{total_out:,}  total {total_secs:.1f}s")
    return total_in, total_out, total_secs


def _format_roster(registry: AgentRegistry) -> str:
    """Return a verbose name+description roster — used only for prompt_engineer
    and registry_auditor, where descriptions matter for de-duplication checks.
    Manager and workflow_planner now use the compact builders below."""
    lines = []
    for name, cfg in sorted(registry.agents.items()):
        source = "[project]" if "project:" in cfg.get("_source", "") else "[general]"
        lines.append(f"  {source} {name}: {cfg.get('description', '')}")
    return "\n".join(lines)


def _categorize_agents(registry: AgentRegistry) -> tuple[dict, dict]:
    """Group agents by category folder (general) or project_id (project agents).

    Returns (general_by_category, project_agents_by_id). Category for general
    agents = the immediate parent folder of the agent's directory under
    Employees/General Agents/<category>/<name>/.
    """
    general: dict[str, list[str]] = {}
    projects: dict[str, list[str]] = {}
    for name, cfg in registry.agents.items():
        prompt_path = Path(cfg.get("_prompt_path", ""))
        parts = prompt_path.parts
        if "General Agents" in parts:
            i = parts.index("General Agents")
            category = parts[i + 1] if i + 1 < len(parts) else "(uncategorised)"
            general.setdefault(category, []).append(name)
        elif "Projects-Specific Agents and Workflows" in parts:
            i = parts.index("Projects-Specific Agents and Workflows")
            project_id = parts[i + 1] if i + 1 < len(parts) else "(unknown)"
            projects.setdefault(project_id, []).append(name)
        else:
            general.setdefault("(uncategorised)", []).append(name)
    return general, projects


def _format_roster_tree(registry: AgentRegistry) -> str:
    """Compact category-grouped roster for the manager.

    Shows category + agent names only — no descriptions. Saves ~75% of roster
    tokens versus _format_roster(). Manager has Read access and is instructed
    to inspect a specific agent's config.json on demand if it needs the
    one-line description before deciding. It must NOT read system_prompt.md
    (those are the expensive files).
    """
    general, projects = _categorize_agents(registry)
    lines: list[str] = []
    if general:
        lines.append("## General agents")
        col_w = max((len(c) for c in general), default=0)
        for cat in sorted(general):
            names = ", ".join(sorted(general[cat]))
            lines.append(f"  {cat.ljust(col_w)} : {names}")
    for project_id in sorted(projects):
        lines.append("")
        lines.append(f"## Project: {project_id}")
        names = ", ".join(sorted(projects[project_id]))
        lines.append(f"  agents : {names}")
    lines.append("")
    lines.append("To get an agent's description, Read its config.json:")
    lines.append("  Employees/General Agents/<category>/<agent>/config.json")
    lines.append("  Employees/Projects-Specific Agents and Workflows/<project>/agents/<agent>/config.json")
    lines.append("Do NOT read system_prompt.md — config.json holds the description.")
    return "\n".join(lines)


def _format_roster_names_only(registry: AgentRegistry) -> str:
    """Flat name-only list for workflow_planner — used to validate that every
    agent name in the plan exists in the registry. No descriptions needed
    because workflow_planner does not choose agents, it transcribes a plan."""
    general, projects = _categorize_agents(registry)
    lines: list[str] = []
    if general:
        all_general = sorted(n for ns in general.values() for n in ns)
        lines.append("Valid general agents: " + ", ".join(all_general))
    for project_id in sorted(projects):
        lines.append(f"Valid project agents ({project_id}): " + ", ".join(sorted(projects[project_id])))
    return "\n".join(lines)


# ── Generated-workflow cache ──────────────────────────────────────────────────
# When a user repeats a task (same goal text, same project), skip the
# manager + workflow_planner round-trip and reuse the previously generated
# YAML. Cache key is derived from the normalised task + project so trivial
# whitespace/casing differences still hit the cache.

_WORKFLOW_CACHE_DIR  = SYSTEM_DIR / "_workflow_cache"
_CANONICAL_CACHE_PATH = _WORKFLOW_CACHE_DIR / "_canonicalisation.json"

# Agents whose system prompts directly produced the cached YAML — if either
# of these prompts changes, all cached entries should be invalidated.
_PLANNING_AGENTS = ("manager", "workflow_planner")


def _normalise_text(s: str) -> str:
    """Collapse whitespace and lowercase. Used as fallback when canonicalisation fails."""
    return re.sub(r"\s+", " ", s.strip().lower())


async def _haiku_canonicalise(task: str) -> str:
    """One-shot Haiku call. Returns the model's canonical restatement.

    System prompt is tight — Haiku is told to output ONLY the canonical form
    on one line. Empty allowed_tools so the model can't wander.
    """
    from claude_agent_sdk import (
        query, ClaudeAgentOptions, AssistantMessage, TextBlock,
    )
    sys_prompt = (
        "You are a task canonicaliser. Restate the user's task in 12 words or "
        "fewer, lowercase, no punctuation, focusing on the action verb and the "
        "primary target/object. Strip filler words like 'please', 'can you', "
        "'i want to'. Output ONLY the canonical form on a single line — no "
        "preamble, no quotes, no explanation."
    )
    options = ClaudeAgentOptions(
        system_prompt=sys_prompt,
        model="claude-haiku-4-5-20251001",
        max_turns=1,
        allowed_tools=[],
        permission_mode="acceptEdits",
    )
    parts: list[str] = []
    async for msg in query(prompt=task, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return "".join(parts).strip()


def _canonicalise_task(task: str) -> str:
    """Return the canonical form of a task string.

    Cached on md5(raw_task) in _canonicalisation.json so identical raw inputs
    don't re-call Haiku. On any failure (SDK missing, no API key, network),
    falls back to plain whitespace+case normalisation.
    """
    raw = task.strip()
    raw_hash = hashlib.md5(raw.encode()).hexdigest()

    # Read the canonicalisation memo
    memo: dict[str, str] = {}
    if _CANONICAL_CACHE_PATH.exists():
        try:
            memo = json.loads(_CANONICAL_CACHE_PATH.read_text())
        except Exception:
            memo = {}

    if raw_hash in memo:
        return memo[raw_hash]

    # Try the Haiku call
    try:
        import asyncio as _asyncio
        canonical = _asyncio.run(_haiku_canonicalise(raw))
    except Exception as e:
        print(f"  [cache] canonicalisation failed ({e}); falling back to plain normalisation")
        return _normalise_text(raw)

    canonical = _normalise_text(canonical)
    if not canonical:
        # Model returned empty — fall back
        return _normalise_text(raw)

    # Persist the memo
    memo[raw_hash] = canonical
    try:
        _CANONICAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CANONICAL_CACHE_PATH.write_text(json.dumps(memo, indent=2, sort_keys=True))
    except Exception:
        pass   # memo write failure is non-fatal
    return canonical


def _task_cache_key(canonical_task: str, project: str | None) -> str:
    """Stable 12-hex hash of (canonical_task, project).

    Caller is responsible for canonicalisation. Pass _canonicalise_task(raw)
    or _normalise_text(raw) — never the raw text directly, otherwise
    paraphrases produce different keys.
    """
    payload = f"{canonical_task}|{(project or '').lower()}"
    return hashlib.md5(payload.encode()).hexdigest()[:12]


def _cached_workflow_path(cache_key: str) -> Path:
    _WORKFLOW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _WORKFLOW_CACHE_DIR / f"{cache_key}.yaml"


def _cache_meta_path(cache_key: str) -> Path:
    return _WORKFLOW_CACHE_DIR / f"{cache_key}.meta.json"


def _prompt_fingerprint(registry: AgentRegistry, agent_names) -> dict[str, str]:
    """Return {agent_name: 8-hex md5 of its system_prompt.md content}.
    Skips agents not in the registry or whose prompt cannot be read."""
    out: dict[str, str] = {}
    for name in agent_names:
        cfg = registry.agents.get(name)
        if not cfg:
            continue
        try:
            content = Path(cfg["_prompt_path"]).read_text()
            out[name] = hashlib.md5(content.encode()).hexdigest()[:8]
        except Exception:
            continue
    return out


def _write_cache_meta(cache_key: str, *, raw_task: str, canonical: str,
                      project: str | None, registry: AgentRegistry) -> None:
    """Persist metadata used for prompt-hash invalidation."""
    meta = {
        "raw_task":   raw_task,
        "canonical":  canonical,
        "project":    project or "",
        "created_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "planning_agents_fingerprint": _prompt_fingerprint(registry, _PLANNING_AGENTS),
    }
    try:
        _cache_meta_path(cache_key).write_text(json.dumps(meta, indent=2, sort_keys=True))
    except Exception as e:
        print(f"  [cache] could not write metadata: {e}")


def _is_cache_valid(cached_path: Path, registry: AgentRegistry) -> tuple[bool, str]:
    """A cached YAML is valid when:
      1. It parses and contains steps
      2. Every agent it references still exists in the registry
      3. The planning agents (manager, workflow_planner) have not had their
         system_prompt.md edited since the cache was written. (If meta is
         missing — e.g. legacy cache — only checks 1 and 2 apply.)
    Returns (valid, reason)."""
    if not cached_path.exists():
        return False, "no cache entry"
    try:
        import yaml as _yaml
        data = _yaml.safe_load(cached_path.read_text())
    except Exception as e:
        return False, f"YAML parse error: {e}"
    steps = data.get("steps", []) if isinstance(data, dict) else []
    if not steps:
        return False, "cached YAML has no steps"
    for step in steps:
        agent_name = step.get("agent")
        if agent_name and agent_name not in registry.agents:
            return False, f"cached workflow references missing agent '{agent_name}'"

    # Prompt-hash invalidation
    cache_key = cached_path.stem
    meta_path = _cache_meta_path(cache_key)
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            return True, "ok"   # meta corrupt — be lenient
        cached_fp  = meta.get("planning_agents_fingerprint", {}) or {}
        if cached_fp:
            current_fp = _prompt_fingerprint(registry, list(cached_fp.keys()))
            for name, cached_hash in cached_fp.items():
                if current_fp.get(name) != cached_hash:
                    return False, f"'{name}' system_prompt.md changed since cache written"
    return True, "ok"


# ── Task mode helpers ─────────────────────────────────────────────────────────

def _parse_gaps(transcript: str) -> list[dict]:
    """Parse gap declarations from manager transcript.
    Looks for lines under '## NEW AGENTS NEEDED' matching:
      - name: foo | purpose: bar | category: baz
    Returns [] if STATUS is READY or no gaps section found.
    """
    if "GAPS_DETECTED" not in transcript:
        return []
    gaps, in_section = [], False
    for line in transcript.splitlines():
        stripped = line.strip()
        if "## NEW AGENTS NEEDED" in stripped:
            in_section = True
            continue
        if in_section:
            if stripped.startswith("##"):          # next section — stop
                break
            if stripped.startswith("-") and "|" in stripped:
                parts = {}
                for part in stripped.lstrip("- ").split("|"):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        parts[k.strip()] = v.strip()
                if "name" in parts and "purpose" in parts:
                    gaps.append(parts)
    return gaps


def _parse_verdict(transcript: str) -> str:
    """Return 'APPROVE' or 'REJECT' from registry_auditor transcript.
    Looks for a bare APPROVE or REJECT line (the structured verdict block).
    Falls back to searching for REJECT first — a false REJECT is safer than
    a false APPROVE that lets a bad agent into the registry.
    """
    for line in transcript.splitlines():
        upper = line.strip().upper()
        if upper == "APPROVE":
            return "APPROVE"
        if upper == "REJECT":
            return "REJECT"
    # Fallback: check REJECT before APPROVE — safer default
    if "REJECT" in transcript.upper():
        return "REJECT"
    if "APPROVE" in transcript.upper():
        return "APPROVE"
    return "REJECT"  # no verdict found — treat as rejected, do not let unreviewed agents in


def _parse_reject_reason(transcript: str) -> str:
    """Extract the first Reason: line from a REJECT verdict."""
    for line in transcript.splitlines():
        if line.strip().lower().startswith("reason:"):
            return line.split(":", 1)[1].strip()
    return "(no reason given)"


# ── Self-improvement routing helpers ────────────────────────────────────────

def _parse_task_type(transcript: str) -> str:
    """Return 'SELF_IMPROVE' if manager flagged a self-improvement task, else 'EXECUTE'."""
    match = re.search(r"## TASK_TYPE\s*\n\s*(\w+)", transcript)
    if match and match.group(1).strip().upper() == "SELF_IMPROVE":
        return "SELF_IMPROVE"
    return "EXECUTE"


def _parse_improvement_targets(transcript: str) -> list[dict]:
    """Parse agent/finding pairs from the ## IMPROVEMENT_TARGETS section."""
    match = re.search(r"## IMPROVEMENT_TARGETS\s*(.*?)(?=\n##|\Z)", transcript, re.DOTALL)
    if not match:
        return []
    targets: list[dict] = []
    current: dict = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if line.startswith("- agent:"):
            if current.get("agent"):
                targets.append(current)
            current = {"agent": line.split(":", 1)[1].strip(), "type": "prompt_rewrite"}
        elif line.startswith("finding:") and current:
            current["finding"] = line.split(":", 1)[1].strip().strip('"').strip("'")
    if current.get("agent"):
        targets.append(current)
    return targets


def _run_targeted_improvement(
    targets: list[dict],
    registry: AgentRegistry,
    dry_run: bool,
    dispatch_log: list,
) -> dict:
    """
    Run the interactive improvement loop for a specific list of agent targets.
    Imports and reuses _run_one_finding from run_self_improve.py.
    Human approval gate is always active — no automated writes.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_self_improve", BASE / "system_improvement" / "run_self_improve.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.WORKING_DIR.mkdir(parents=True, exist_ok=True)

    counts = {"applied": 0, "blocked": 0, "skipped": 0, "unresolved": 0}
    skip_remaining = False

    for target in targets:
        if skip_remaining:
            print(f"  [skipped] {target.get('agent')}")
            counts["skipped"] += 1
            continue
        result = mod._run_one_finding(target, registry, dry_run)
        status = result.get("final_status", "")
        if status == "applied":
            counts["applied"] += 1
        elif status == "blocked":
            counts["blocked"] += 1
        elif status == "skipped_by_user":
            counts["skipped"] += 1
            skip_remaining = True
        else:
            counts["unresolved"] += 1

    print(f"\n  Applied: {counts['applied']}  Blocked: {counts['blocked']}  "
          f"Skipped: {counts['skipped']}  Unresolved: {counts['unresolved']}")
    print(f"  Log: {mod.LOG_PATH}")

    return {
        "success": True,
        "mode": "task_self_improve",
        "steps": dispatch_log,
        "improvement_summary": counts,
    }


def _resolve_gaps(gaps: list[dict], registry: AgentRegistry, working_dir: Path,
                  dry_run: bool, dispatch_log: list, base_dir: Path,
                  session_log_dir: Path | None = None) -> list[str]:
    """For each gap: run prompt_engineer → registry_auditor → reload registry.
    Returns list of successfully resolved agent names.
    """
    import shutil
    from runtime.dispatcher import run_step

    resolved = []
    roster   = _format_roster(registry)

    for gap in gaps:
        name     = gap.get("name", "unknown_agent")
        purpose  = gap.get("purpose", "")
        category = gap.get("category", "auto_generated")
        save_dir = base_dir / "Employees" / "General Agents" / category / name

        # ── prompt_engineer ───────────────────────────────────────────────
        print(f"\n    → prompt_engineer: creating '{name}'")
        pe_task = (
            f"AUTOMATED GAP FILL — do not ask clarifying questions.\n\n"
            f"A new agent is needed:\n"
            f"  Name:    {name}\n"
            f"  Purpose: {purpose}\n\n"
            f"Existing agent roster (do not duplicate any of these):\n{roster}\n\n"
            f"Write both files directly to disk:\n"
            f"  {save_dir / 'config.json'}\n"
            f"  {save_dir / 'system_prompt.md'}\n"
            f"Create the directory if it does not exist. "
            f"Also print both files as code blocks in your transcript."
        )
        try:
            pe_cfg    = registry.load_agent("prompt_engineer")
            pe_result = run_step(pe_cfg, pe_task, working_dir, dry_run=dry_run,
                                 log_dir=session_log_dir)
        except Exception as e:
            print(f"    [skip] prompt_engineer error: {e}")
            continue

        rec = {
            "step": f"prompt_engineer:{name}", "agent": "prompt_engineer",
            "mode": "gap_resolution", "status": pe_result.status,
            "duration_seconds": round(pe_result.duration_seconds, 2),
            "input_tokens": pe_result.input_tokens,
            "output_tokens": pe_result.output_tokens,
            "log_path": pe_result.log_path,
        }
        if pe_result.error: rec["error"] = pe_result.error
        dispatch_log.append(rec)
        _print_step(f"prompt_engineer:{name}", rec)

        if pe_result.status == "error":
            print(f"    [skip] prompt_engineer failed for '{name}'")
            continue

        # In dry-run, files aren't written — mark resolved and continue
        if dry_run:
            resolved.append(name)
            continue

        if not save_dir.exists() or not (save_dir / "config.json").exists():
            print(f"    [skip] prompt_engineer did not write files to {save_dir}")
            continue

        # ── registry_auditor (new agent review) ───────────────────────────
        print(f"    → registry_auditor: reviewing '{name}'")
        try:
            new_config = (save_dir / "config.json").read_text()
            new_prompt = (save_dir / "system_prompt.md").read_text()
        except Exception as e:
            print(f"    [skip] could not read new agent files: {e}")
            continue

        audit_task = (
            f"NEW AGENT REVIEW\n\n"
            f"An auto-generated agent needs review before entering the registry.\n\n"
            f"## New agent: {name}\n\n"
            f"config.json:\n```json\n{new_config}\n```\n\n"
            f"system_prompt.md:\n```markdown\n{new_prompt}\n```\n\n"
            f"## Existing registry\n{roster}"
        )
        try:
            auditor_cfg  = registry.load_agent("registry_auditor")
            audit_result = run_step(auditor_cfg, audit_task, working_dir, dry_run=dry_run,
                                    log_dir=session_log_dir)
        except Exception as e:
            print(f"    [skip] registry_auditor error: {e}")
            continue

        rec = {
            "step": f"registry_auditor:{name}", "agent": "registry_auditor",
            "mode": "gap_resolution", "status": audit_result.status,
            "duration_seconds": round(audit_result.duration_seconds, 2),
            "input_tokens": audit_result.input_tokens,
            "output_tokens": audit_result.output_tokens,
            "log_path": audit_result.log_path,
        }
        if audit_result.error: rec["error"] = audit_result.error
        dispatch_log.append(rec)
        _print_step(f"registry_auditor:{name}", rec)

        verdict = _parse_verdict(audit_result.transcript)
        if verdict == "APPROVE":
            registry.reload()
            resolved.append(name)
            print(f"    [approved] '{name}' loaded into registry")
        else:
            shutil.rmtree(save_dir, ignore_errors=True)
            reason = _parse_reject_reason(audit_result.transcript)
            print(f"    [rejected] '{name}': {reason}")

    return resolved


def _execute_cached_workflow(args, registry: AgentRegistry, engine: WorkflowEngine,
                              yaml_path: Path, working_dir: Path,
                              initial_inputs: dict,
                              session_log_dir: Path | None = None) -> dict:
    """Cache-hit path — load the cached YAML and run engine.execute directly.
    Skips manager + workflow_planner entirely. Returns the same dict shape as
    _run_task_mode for consistency with the caller."""
    try:
        cached_wf = WorkflowDefinition.from_yaml(yaml_path)
    except Exception as e:
        print(f"[error] could not parse cached YAML {yaml_path}: {e}")
        return {"success": False, "mode": "task", "error": str(e), "steps": []}

    print(f"Cached workflow: {cached_wf.name}  ({len(cached_wf.steps)} steps)")
    print()

    ctx = ProjectContext(args.project or "ad_hoc", registry=registry)
    exec_result = engine.execute(
        cached_wf, ctx,
        initial_inputs=initial_inputs,
        working_dir=working_dir,
        dry_run=args.dry_run,
        state_path=SYSTEM_DIR / "_workflow_state.json",
        log_dir=session_log_dir or AGENT_LOGS_DIR,
        on_step_done=_print_step,
        max_parallel=getattr(args, "max_parallel", 4),
    )
    exec_result["mode"]           = "task"
    exec_result["generated_yaml"] = str(yaml_path)
    exec_result["cache_hit"]      = True
    return exec_result


# ── Task mode ─────────────────────────────────────────────────────────────────

MAX_GAP_ITERATIONS = 3   # cap the manager → gap-resolution loop


def _run_task_mode(args, registry: AgentRegistry, engine: WorkflowEngine,
                   working_dir: Path, initial_inputs: dict,
                   session_log_dir: Path | None = None) -> dict:
    """
    Front-door routing:
      Phase 1 (loop up to MAX_GAP_ITERATIONS):
        manager detects gaps → prompt_engineer creates agents →
        registry_auditor approves/rejects → registry reloads → manager re-plans
      Phase 2:
        workflow_planner formalises the plan as YAML
      Phase 3:
        engine executes the generated YAML
    """
    from runtime.dispatcher import run_step

    use_cache = not bool(getattr(args, "no_cache", False))

    # Cache key derivation. With caching enabled we run a Haiku canonicalisation
    # pass so paraphrases of the same intent share a key. With --no-cache we
    # skip that to avoid the small extra Haiku call.
    canonical: str | None = None
    cache_key:  str | None = None
    cached_yaml: Path | None = None

    if use_cache:
        print(f"\n── canonicalising task for cache lookup ──")
        canonical = _canonicalise_task(args.task)
        print(f"  Canonical: \"{canonical}\"")
        cache_key   = _task_cache_key(canonical, args.project)
        cached_yaml = _cached_workflow_path(cache_key)

        valid, reason = _is_cache_valid(cached_yaml, registry)
        if valid:
            print(f"\n── cache hit — skipping manager + workflow_planner ──")
            print(f"  Cached: {cached_yaml.relative_to(BASE)}")
            print(f"  Use --no-cache to force a fresh plan.")
            return _execute_cached_workflow(args, registry, engine, cached_yaml,
                                             working_dir, initial_inputs,
                                             session_log_dir=session_log_dir)
        elif cached_yaml.exists():
            print(f"  [cache] entry exists but invalid: {reason} — re-planning")
        else:
            print(f"  [cache] no entry yet for key {cache_key} — planning fresh")

    # No cache hit — generate the workflow YAML directly into the cache slot
    # (planner writes there; if it succeeds it becomes the cached entry)
    yaml_path    = cached_yaml if use_cache else (SYSTEM_DIR / "_generated_workflow.yaml")
    dispatch_log: list[dict] = []
    manager_result = None

    # ── Phase 1: manager + gap resolution loop ────────────────────────────────
    for iteration in range(MAX_GAP_ITERATIONS + 1):
        roster = _format_roster_tree(registry)   # compact tree; manager Reads config.json on demand
        label  = f"planning" if iteration == 0 else f"re-planning (iteration {iteration})"
        print(f"\n── manager ({label}) ──")

        manager_task = (
            f"Goal: {args.task}\n\n"
            f"Available agent roster:\n{roster}\n\n"
            f"Produce a complete workflow plan for this goal. "
            f"For each step specify: agent, task instruction, input_keys, output_key, dependencies. "
            f"Check every step against the roster. "
            f"If any step requires a capability not in the roster, declare it under "
            f"'## NEW AGENTS NEEDED' and set '## STATUS' to GAPS_DETECTED. "
            f"If all steps are covered, set '## STATUS' to READY."
        )
        if initial_inputs:
            manager_task += f"\n\nInitial inputs available: {list(initial_inputs.keys())}"

        try:
            manager_cfg    = registry.load_agent("manager")
            manager_result = run_step(manager_cfg, manager_task, working_dir,
                                      dry_run=args.dry_run, log_dir=session_log_dir)
        except Exception as e:
            print(f"[error] manager failed: {e}")
            return {"success": False, "mode": "task", "error": str(e), "steps": dispatch_log}

        rec = {
            "step": f"manager" if iteration == 0 else f"manager:iter{iteration}",
            "agent": "manager", "mode": "task_dispatch",
            "status": manager_result.status,
            "duration_seconds": round(manager_result.duration_seconds, 2),
            "input_tokens": manager_result.input_tokens,
            "output_tokens": manager_result.output_tokens,
            "log_path": manager_result.log_path,
        }
        if manager_result.error: rec["error"] = manager_result.error
        dispatch_log.append(rec)
        _print_step(rec["step"], rec)

        if manager_result.status == "error":
            print("[error] manager returned an error — aborting.")
            return {"success": False, "mode": "task", "steps": dispatch_log}

        gaps = _parse_gaps(manager_result.transcript)

        if not gaps:
            break   # no gaps — proceed to Phase 2

        if iteration == MAX_GAP_ITERATIONS:
            print(f"[warning] Reached max gap resolution iterations ({MAX_GAP_ITERATIONS}). "
                  f"Proceeding with unresolved gaps — workflow_planner will flag invalid agents.")
            break

        print(f"  {len(gaps)} gap(s) detected: {[g['name'] for g in gaps]}")
        resolved = _resolve_gaps(gaps, registry, working_dir, args.dry_run,
                                  dispatch_log, BASE, session_log_dir=session_log_dir)

        if not resolved:
            print("[warning] No gaps were resolved — proceeding with current roster.")
            break

    # ── Routing check: self-improvement vs execution ───────────────────────────
    task_type = _parse_task_type(manager_result.transcript)

    if task_type == "SELF_IMPROVE":
        targets = _parse_improvement_targets(manager_result.transcript)
        if not targets:
            print("[error] manager returned SELF_IMPROVE but no targets found in output")
            return {"success": False, "mode": "task", "steps": dispatch_log,
                    "error": "SELF_IMPROVE declared but no IMPROVEMENT_TARGETS parsed"}
        print(f"\n── self-improvement routing ({len(targets)} target(s)) ──")
        for t in targets:
            print(f"  • {t.get('agent')}: {t.get('finding', '')}")
        return _run_targeted_improvement(targets, registry, args.dry_run, dispatch_log)

    # ── Phase 2: workflow_planner ─────────────────────────────────────────────
    roster = _format_roster_names_only(registry)   # name-only — planner just validates names
    print("\n── workflow_planner (formalising YAML) ──")

    wfp_task = (
        f"Formalise the following plan as a workflow YAML file.\n\n"
        f"Plan from manager:\n{manager_result.transcript}\n\n"
        f"Agent roster (validate all agent names against this list):\n{roster}\n\n"
        f"save_path: {yaml_path}\n"
        f"workflow_name: generated_task_workflow"
    )
    try:
        wfp_cfg    = registry.load_agent("workflow_planner")
        wfp_result = run_step(wfp_cfg, wfp_task, working_dir, dry_run=args.dry_run,
                              log_dir=session_log_dir)
    except Exception as e:
        print(f"[error] workflow_planner failed: {e}")
        return {"success": False, "mode": "task", "error": str(e), "steps": dispatch_log}

    rec = {
        "step": "workflow_planner", "agent": "workflow_planner", "mode": "task_dispatch",
        "status": wfp_result.status,
        "duration_seconds": round(wfp_result.duration_seconds, 2),
        "input_tokens": wfp_result.input_tokens,
        "output_tokens": wfp_result.output_tokens,
        "log_path": wfp_result.log_path,
    }
    if wfp_result.error: rec["error"] = wfp_result.error
    dispatch_log.append(rec)
    _print_step("workflow_planner", rec)

    if wfp_result.status == "error":
        print("[error] workflow_planner returned an error — aborting.")
        return {"success": False, "mode": "task", "steps": dispatch_log}

    if args.dry_run:
        print(f"\n[dry-run] Skipping execution — no YAML written.")
        print(f"          Generated YAML would be at: {yaml_path}")
        return {
            "success": True, "mode": "task", "dry_run": True,
            "generated_yaml": str(yaml_path), "steps": dispatch_log,
        }

    # ── Phase 3: execute generated YAML ──────────────────────────────────────
    if not yaml_path.exists():
        print(f"[error] workflow_planner did not write a YAML file to {yaml_path}")
        print(f"        Check log: {wfp_result.log_path}")
        return {"success": False, "mode": "task", "steps": dispatch_log}

    # Write cache metadata so prompt-hash invalidation works on future hits
    if use_cache and cache_key and canonical is not None:
        _write_cache_meta(cache_key, raw_task=args.task, canonical=canonical,
                          project=args.project, registry=registry)

    print(f"\n── engine (executing {yaml_path.name}) ──")
    try:
        generated_wf = WorkflowDefinition.from_yaml(yaml_path)
    except Exception as e:
        print(f"[error] Could not parse generated YAML: {e}")
        return {"success": False, "mode": "task", "steps": dispatch_log, "error": str(e)}

    print(f"Generated workflow: {generated_wf.name}  ({len(generated_wf.steps)} steps)")
    print()

    ctx        = ProjectContext(args.project or "ad_hoc", registry=registry)
    exec_result = engine.execute(
        generated_wf, ctx,
        initial_inputs=initial_inputs,
        working_dir=working_dir,
        dry_run=args.dry_run,
        state_path=SYSTEM_DIR / "_workflow_state.json",
        log_dir=session_log_dir or AGENT_LOGS_DIR,
        on_step_done=_print_step,
        max_parallel=getattr(args, "max_parallel", 4),
    )

    all_steps = dispatch_log + exec_result.get("steps", [])
    exec_result["steps"]          = all_steps
    exec_result["mode"]           = "task"
    exec_result["generated_yaml"] = str(yaml_path)
    return exec_result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Run an agent workflow against the Anthropic API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mode — mutually exclusive; all optional when running interactively
    mode = ap.add_mutually_exclusive_group(required=False)
    mode.add_argument("--workflow",        help="Workflow YAML name (without .yaml) — explicit pipeline mode")
    mode.add_argument("--task",            help="Free-form task description — front-door routing mode (manager → workflow_planner → engine)")
    mode.add_argument("--system-improve",  action="store_true", default=False,
                      help="Audit and improve the agent system’s own prompts (human approval required)")

    ap.add_argument("--project",     default=None, help="Project ID — loads project-specific agents into the registry. Prompted interactively if omitted.")
    ap.add_argument("--sub-task",    default=None, dest="group", help="Optional label grouping related runs (e.g. 'EDA Phase 1', 'CFO Brief Q2') — recorded in system_history.csv. Prompted interactively if omitted; press Enter to skip (logged as NaN).")
    ap.add_argument("--working-dir", default=None, help="Directory where task outputs are saved (prompted if not provided)")
    ap.add_argument("--inputs",      help="JSON literal: initial inputs dict")
    ap.add_argument("--inputs-file", help="Path to JSON file with initial inputs")
    ap.add_argument("--resume-from", help="[workflow mode] Step name to resume from")
    ap.add_argument("--state-file",  help="[workflow mode] Override state file path")
    ap.add_argument("--dry-run",     action="store_true", help="Don't call API; print resolved prompts/tasks")
    # Tri-state cache flag: None = ask interactively in task mode, True = force re-plan, False = use cache silently
    cache_group = ap.add_mutually_exclusive_group()
    cache_group.add_argument("--no-cache", dest="no_cache", action="store_const", const=True, default=None,
                             help="[task mode] Force re-planning even if a cached workflow exists. Prompted if neither --no-cache nor --use-cache is supplied.")
    cache_group.add_argument("--use-cache", dest="no_cache", action="store_const", const=False,
                             help="[task mode] Reuse cached workflow if a paraphrase-equivalent task ran before. Prompted if neither flag supplied.")
    ap.add_argument("--max-parallel", type=int, default=None, dest="max_parallel",
                    help="Maximum concurrent agent steps when input_keys allow it (default: 4 if not prompted). "
                         "Prompted interactively when omitted. "
                         "Steps with parallel_safe: false in YAML, plus planner/dynamic steps, run as barriers. "
                         "--resume-from forces this to 1.")
    ap.add_argument("--list",        action="store_true", help="List agents + workflows for the project and exit")
    args = ap.parse_args()

    # ────────────────────────────────────────────────────────────────────────────
    # Interactive vs command-line logic:
    #   • Any flag supplied on the command line is used as-is (silent).
    #   • Any flag that is missing is filled in interactively.
    # Both paths ultimately produce the same set of variables.
    # ────────────────────────────────────────────────────────────────────────────

    # ── Step 1: mode selection (interactive only when no mode flag given) ─────
    no_mode_flag = not args.workflow and not args.task and not args.system_improve
    if no_mode_flag:
        selected_mode = prompt_mode()   # 'task' | 'workflow' | 'system_improve'
    else:
        selected_mode = (
            "task"           if args.task            else
            "workflow"       if args.workflow        else
            "system_improve"
        )

    # ── Step 2: system-improve — ask for finding, then re-route as a task ────
    # No project prompt — the improvement pipeline does not require one.
    # The finding is prefixed with SELF_IMPROVE: and injected as args.task so
    # the normal task-mode routing (manager → _run_targeted_improvement) handles it.
    if selected_mode == "system_improve":
        if args.task is None:
            args.task = prompt_improvement_finding()
        elif not args.task.startswith("SELF_IMPROVE:"):
            args.task = f"SELF_IMPROVE: {args.task}"
        if not args.dry_run and no_mode_flag:
            args.dry_run = prompt_dry_run()
        selected_mode = "task"   # fall through to the standard task pipeline

    # ── Step 3: project (interactive only when --project not given) ──────────
    # SELF_IMPROVE tasks don't need a project — skip the prompt.
    _is_self_improve = args.task and args.task.startswith("SELF_IMPROVE:")
    if args.project is None and not _is_self_improve:
        args.project = prompt_project(BASE)

    # ── Step 4: sub-task (interactive only when --sub-task not given) ─────────
    if args.group is None:
        sub_task_value = prompt_sub_task(BASE)
        args.group = sub_task_value if sub_task_value is not None else "NaN"

    # ── Step 5: working directory ─────────────────────────────────────────────
    if args.working_dir:
        working_dir = Path(args.working_dir).resolve()
        working_dir.mkdir(parents=True, exist_ok=True)
    else:
        working_dir = prompt_working_dir(BASE)
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 5b: concurrency (interactive only when --max-parallel not given) ──
    # Resume mode forces sequential — skip the prompt in that case.
    if args.max_parallel is None:
        if args.resume_from:
            args.max_parallel = 1
        else:
            args.max_parallel = prompt_max_parallel(default=4)

    # Per-run agent log folder, named {run_id}_{sub-task-slug}.
    # Same run_id is reused for the run record, so logs and telemetry line up.
    session_run_id, session_log_dir = _new_session_log_dir(args.group)
    print(f"Session log dir: {session_log_dir.relative_to(BASE)}")

    registry = AgentRegistry(base_dir=BASE, project_id=args.project)
    engine   = WorkflowEngine(registry, base_dir=BASE)

    # ── Step 6: mode-specific prompts (interactive only) ─────────────────────
    if selected_mode == "task":
        if args.task is None:
            args.task = prompt_task_text()
            # dry-run: use --dry-run flag if given; otherwise ask
            if not args.dry_run:
                args.dry_run = prompt_dry_run()
        # Cache prompt — fires whenever neither --no-cache nor --use-cache was supplied.
        # Skip during SELF_IMPROVE (caching irrelevant — the run mutates the system).
        if args.no_cache is None and not (args.task or "").startswith("SELF_IMPROVE:"):
            use_cache = prompt_use_cache(default=True)
            args.no_cache = not use_cache

    elif selected_mode == "workflow":
        # Workflow name — only prompt if not supplied as a flag
        if args.workflow is None:
            wf_details    = prompt_workflow_details(engine.list_workflows())
            args.workflow = wf_details["name"]
        # Resume-from — prompt whenever it wasn't supplied as a flag
        if args.resume_from is None:
            args.resume_from = prompt_resume_from()

    # ── --list ────────────────────────────────────────────────────────────────
    if args.list:
        print(registry.describe())
        print()
        print("Workflows:")
        for wf in engine.list_workflows():
            print(f"  [{wf['source']}] {wf['name']}")
        sys.exit(0)

    # ── Initial inputs ────────────────────────────────────────────────────────
    initial_inputs: dict = {}
    if args.inputs_file:
        initial_inputs.update(json.loads(Path(args.inputs_file).read_text()))
    if args.inputs:
        initial_inputs.update(json.loads(args.inputs))

    # ── TASK MODE ─────────────────────────────────────────────────────────────
    if args.task:
        print(f"Mode:            task (front-door routing)")
        print(f"Project:         {args.project or '(none — general agents only)'}")
        print(f"Working dir:     {working_dir}")
        cache_label = "off" if bool(args.no_cache) else "on"
        print(f"Dispatch ready:  {DISPATCH_AVAILABLE}  |  dry-run: {args.dry_run}  |  max-parallel: {args.max_parallel}  |  cache: {cache_label}")
        print(f"Task:            {args.task[:120]}{'...' if len(args.task) > 120 else ''}")
        if initial_inputs:
            print(f"Initial inputs:  {list(initial_inputs.keys())}")

        result = _run_task_mode(args, registry, engine, working_dir, initial_inputs,
                                session_log_dir=session_log_dir)

        print()
        if result.get("generated_yaml"):
            label = "Cached YAML:" if result.get("cache_hit") else "Generated YAML:"
            print(f"{label:20s}{result['generated_yaml']}")
        _print_totals(result.get("steps", []))
        print(f"Success:            {result['success']}")


        if not args.dry_run:
            rec = save_run_record(
                task=args.task,
                project=args.project,
                task_group=args.group,
                run_result=result,
                working_dir=working_dir,
                log_dir=session_log_dir,
                run_id=session_run_id,
            )
            print(f"Run record saved:   {rec['run_id']}  ({RUNS_HISTORY})")
            post_run_check(registry, working_dir, dry_run=args.dry_run,
                           run_id=rec['run_id'], task=args.task,
                           task_group=args.group or "")

        sys.exit(0 if result["success"] else 1)

    # ── WORKFLOW MODE ─────────────────────────────────────────────────────────
    workflow = engine.load_workflow(args.workflow)
    ctx      = ProjectContext(args.project or "default", registry=registry)

    print(f"Mode:            workflow (explicit pipeline)")
    print(f"Project:         {args.project or '(none)'}")
    print(f"Workflow:        {workflow.name}  ({len(workflow.steps)} steps)")
    print(f"Working dir:     {working_dir}")
    print(f"Dispatch ready:  {DISPATCH_AVAILABLE}  |  dry-run: {args.dry_run}  |  resume-from: {args.resume_from or '-'}  |  max-parallel: {args.max_parallel}")
    if initial_inputs:
        print(f"Initial inputs:  {list(initial_inputs.keys())}")
    print()

    result = engine.execute(
        workflow, ctx,
        initial_inputs=initial_inputs,
        working_dir=working_dir,
        dry_run=args.dry_run,
        resume_from=args.resume_from,
        state_path=args.state_file or str(SYSTEM_DIR / "_workflow_state.json"),
        log_dir=session_log_dir,
        on_step_done=_print_step,
        max_parallel=args.max_parallel,
    )

    print()
    _print_totals(result.get("steps", []))
    print(f"Success:            {result['success']}")

    if not args.dry_run:
        rec = save_run_record(
            task=f"workflow:{args.workflow}",
            project=args.project,
            task_group=args.group,
            run_result={**result, "workflow": args.workflow},
            working_dir=working_dir,
            log_dir=session_log_dir,
            run_id=session_run_id,
        )
        print(f"Run record saved:   {rec['run_id']}  ({RUNS_HISTORY})")
        post_run_check(registry, working_dir, dry_run=args.dry_run,
                       run_id=rec['run_id'], task=f"workflow:{args.workflow}",
                       task_group=args.group or "")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
