"""interactive_prompt.py
Handles the interactive terminal prompts shown at startup when the user
does not supply --project / --sub-task via CLI flags.

Exposed API
-----------
  gather_existing_projects(base_dir)    → list[str]
  gather_existing_sub_tasks(base_dir)   → list[str]
  prompt_mode()                         → str   ('task' | 'workflow' | 'system_improve')
  prompt_task_text()                    → str
  prompt_dry_run()                      → bool
  prompt_improvement_finding()          → str   (the finding to action, prefixed with SELF_IMPROVE:)
  prompt_workflow_details(workflows)    → dict  {'name': str}
  prompt_resume_from()                  → str | None
  prompt_project(base_dir)              → str
  prompt_sub_task(base_dir)             → str | None   (None == not supplied == logged as NaN)
  prompt_working_dir(base_dir)          → Path  (defaults to <base_dir>/outputs if Enter is pressed)
"""
from __future__ import annotations

import json
from pathlib import Path
import os


# ── Helpers ───────────────────────────────────────────────────────────────────

# ── Mode-selection prompts ───────────────────────────────────────────────────

_MODES = [
    ("task",           "Task Mode",          "describe a goal in plain language; the system plans and executes it"),
    ("workflow",       "Workflow Mode",       "run a named pipeline directly  (resume from failed runs supported)"),
    ("system_improve", "System-Improve Mode", "audit and improve the agent system's own prompts"),
]


def prompt_mode() -> str:
    """
    Ask the user to choose a run mode.

    Returns
    -------
    'task' | 'workflow' | 'system_improve'
    """
    print()
    print("┌─────────────────────────────────────────┐")
    print("│              SELECT MODE               │")
    print("└─────────────────────────────────────────┘")
    print()
    for i, (_, label, desc) in enumerate(_MODES, start=1):
        print(f"  {i}.  {label}")
        print(f"       {desc}")
        print()

    while True:
        raw = input("  Mode › ").strip()

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(_MODES):
                key, label, _ = _MODES[idx]
                print(f"  ✔  {label}")
                print()
                return key
            print(f"  ⚠  Enter a number between 1 and {len(_MODES)}.")
            continue

        # Accept the key word directly
        for key, label, _ in _MODES:
            if raw.lower() in (key, label.lower()):
                print(f"  ✔  {label}")
                print()
                return key

        print(f"  ⚠  Please enter 1, 2, or 3.")


def prompt_improvement_finding() -> str:
    """
    Ask the user to paste the specific improvement finding they want to action.
    Returns the full task string already prefixed with 'SELF_IMPROVE:' so it
    can be passed directly as args.task to the pipeline.
    """
    print("┌─────────────────────────────────────────┐")
    print("│          IMPROVEMENT FINDING           │")
    print("└─────────────────────────────────────────┘")
    print()
    print("  Paste the finding from the performance notification.")
    print("  Example:  reviewer prompt lacks structured output spec")
    print()

    while True:
        raw = input("  Finding › ").strip()
        if raw:
            # Strip any existing SELF_IMPROVE prefix the user may have pasted
            clean = raw.removeprefix("SELF_IMPROVE:").strip()
            full  = f"SELF_IMPROVE: {clean}"
            print(f"  ✔  {full}")
            print()
            return full
        print("  ⚠  Finding cannot be empty.")


def prompt_task_text() -> str:
    """Ask the user to describe their task goal. Returns a non-empty string."""
    print("┌─────────────────────────────────────────┐")
    print("│              TASK DESCRIPTION          │")
    print("└─────────────────────────────────────────┘")
    print()
    print("  Describe the goal you want the agent system to achieve.")
    print("  Be as specific as possible — include file paths, data sources,")
    print("  and desired output format where relevant.")
    print()

    while True:
        raw = input("  Task › ").strip()
        if raw:
            print()
            return raw
        print("  ⚠  Task cannot be empty. Please describe what you want done.")


def prompt_dry_run() -> bool:
    """
    Ask whether to make a real API call or do a dry run.

    Returns True for dry-run, False for real API call.
    """
    print("┌─────────────────────────────────────────┐")
    print("│             DRY RUN OR LIVE RUN?       │")
    print("└─────────────────────────────────────────┘")
    print()
    print("  1.  Live run  — makes real API calls  (costs tokens)")
    print("  2.  Dry run   — prints resolved prompts / plan, no API calls")
    print()

    while True:
        raw = input("  Choice › ").strip().lower()
        if raw in ("1", "live", "live run", "real"):
            print("  ✔  Live run — real API calls will be made.")
            print()
            return False
        if raw in ("2", "dry", "dry run", "dry-run"):
            print("  ✔  Dry run — no API calls will be made.")
            print()
            return True
        print("  ⚠  Please enter 1 (live) or 2 (dry run).")


def prompt_use_cache(default: bool = True) -> bool:
    """
    Ask whether to use the workflow cache for this task-mode run.

    Returns True (use cache) or False (force fresh planning).
    """
    print("┌─────────────────────────────────────────┐")
    print("│            WORKFLOW CACHE               │")
    print("└─────────────────────────────────────────┘")
    print()
    print("  Every task-mode run starts with TWO planning calls:")
    print("    • manager           — picks which specialists to involve")
    print("    • workflow_planner  — orders them into a YAML plan")
    print("  Together these cost roughly $0.10–0.30 per run before any work starts.")
    print()
    print("  The cache saves the YAML plans from past runs. On a new task the")
    print("  system canonicalises your goal (one cheap Haiku call ~$0.001) and")
    print("  reuses the cached plan if it's the same intent — even if you've")
    print("  paraphrased it. Both planning calls are skipped on a hit.")
    print()
    print("  1.  Use cache (recommended)")
    print("        Reuse a cached plan if a similar task ran before.")
    print("        Falls through to fresh planning if no match or invalid.")
    print()
    print("  2.  No cache")
    print("        Force fresh planning every time. Pick this when:")
    print("          • you've changed an agent's prompt or role and want the")
    print("            manager to re-evaluate which agents to use")
    print("          • you want a fresh plan to compare against the cached one")
    print("          • you don't trust the cached plan for this run")
    print()
    print("  (The cache also auto-invalidates if manager or workflow_planner")
    print("   prompts have changed since the entry was written.)")
    print()

    while True:
        raw = input(f"  Choice [{1 if default else 2}] › ").strip().lower()
        if raw == "":
            choice = default
            label  = "Use cache" if default else "No cache"
            print(f"  ✔  {label} (default).")
            print()
            return choice
        if raw in ("1", "use", "cache", "yes", "y"):
            print(f"  ✔  Use cache — paraphrases of past tasks will hit.")
            print()
            return True
        if raw in ("2", "no", "no cache", "no-cache", "fresh", "n"):
            print(f"  ✔  No cache — manager and workflow_planner will run fresh.")
            print()
            return False
        print("  ⚠  Enter 1 (use cache) or 2 (no cache).")


def prompt_max_parallel(default: int = 4) -> int:
    """
    Ask whether to run agent steps in parallel where dependencies allow.

    Returns the chosen max_parallel value (>=1). Default 4 if user hits Enter.
    """
    print("┌─────────────────────────────────────────┐")
    print("│            CONCURRENCY                  │")
    print("└─────────────────────────────────────────┘")
    print()
    print(f"  Run independent agent steps in parallel where input_keys allow.")
    print(f"  Steps with parallel_safe: false in the YAML (and planner/dynamic")
    print(f"  steps) always run alone.")
    print()
    print(f"  1.  Parallel  ({default} concurrent — recommended default)")
    print(f"  2.  Sequential (1 at a time — safest, slowest)")
    print(f"  3.  Custom    (enter a number)")
    print()

    while True:
        raw = input(f"  Choice [1] › ").strip().lower()
        if raw == "" or raw in ("1", "parallel", "p", "y", "yes"):
            print(f"  ✔  Parallel — up to {default} concurrent.")
            print()
            return default
        if raw in ("2", "sequential", "seq", "s", "n", "no"):
            print(f"  ✔  Sequential — one step at a time.")
            print()
            return 1
        if raw in ("3", "custom", "c"):
            while True:
                num = input("  Max concurrent (integer ≥1) › ").strip()
                try:
                    n = int(num)
                    if n < 1:
                        print("  ⚠  Must be at least 1.")
                        continue
                    print(f"  ✔  Up to {n} concurrent.")
                    print()
                    return n
                except ValueError:
                    print("  ⚠  Please enter a positive integer.")
        # Allow direct integer input as a shortcut
        try:
            n = int(raw)
            if n >= 1:
                label = "Parallel" if n > 1 else "Sequential"
                print(f"  ✔  {label} — up to {n} concurrent.")
                print()
                return n
        except ValueError:
            pass
        print("  ⚠  Enter 1 (parallel), 2 (sequential), 3 (custom), or a positive integer.")


def prompt_workflow_details(workflows: list[dict]) -> dict:
    """
    Show available workflows and ask the user to pick one.
    Also asks whether to resume from a failed run.

    Parameters
    ----------
    workflows : list of {'name': str, 'source': str}
        As returned by WorkflowEngine.list_workflows().

    Returns
    -------
    dict with keys:
        'name'        : str            — chosen workflow name (stem, no .yaml)
        'resume_from' : str | None     — step name to resume from, or None
    """
    print("┌─────────────────────────────────────────┐")
    print("│            SELECT WORKFLOW             │")
    print("└─────────────────────────────────────────┘")
    print()

    if not workflows:
        print("  ⚠  No workflows found for the selected project.")
        print()
    else:
        for i, wf in enumerate(workflows, start=1):
            src_tag = f"[{wf['source']}]"
            print(f"  {i:>2}.  {wf['name']:<40} {src_tag}")
        print()

    while True:
        raw = input("  Workflow › ").strip()
        if not raw:
            print("  ⚠  Workflow name cannot be empty.")
            continue

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(workflows):
                chosen = workflows[idx]["name"]
                print(f"  ✔  Selected workflow: {chosen}")
                print()
                break
            print(f"  ⚠  Number out of range (1–{len(workflows)}).")
            continue

        # Direct name
        names = [w["name"] for w in workflows]
        if raw not in names and workflows:
            print(f"  ⚠  '{raw}' not found. Enter a number or exact workflow name.")
            continue
        chosen = raw
        print(f"  ✔  Workflow: {chosen}")
        print()
        break

    return {"name": chosen}


def prompt_resume_from() -> str | None:
    """
    Ask whether to resume a workflow from a specific step.
    Always shown in workflow mode when --resume-from was not supplied as a flag.

    Returns the step name string, or None to start from the beginning.
    """
    print("┌─────────────────────────────────────────┐")
    print("│          RESUME FROM FAILED RUN?       │")
    print("└─────────────────────────────────────────┘")
    print()
    print("  Enter the step name to restart from (e.g. phase8_qa_audit).")
    print("  Press Enter to start fresh from the beginning.")
    print()

    raw = input("  Resume from step › ").strip()

    if raw:
        print(f"  ✔  Will resume from: {raw}")
    else:
        print("  ✔  Starting from the beginning.")
    print()

    return raw if raw else None


# ── Project / sub-task / working-dir prompts ──────────────────────────────────

def gather_existing_projects(base_dir: Path) -> list[str]:  # noqa: E302
    """
    Collect known project IDs from two sources and return a de-duplicated,
    sorted list (excluding the reserved '_template' placeholder).

    Sources
    -------
    1. Sub-folder names under  Employees/Projects-Specific Agents and Workflows/
    2. Unique 'project' values recorded in  System_logs/runs_history.jsonl
    """
    seen: set[str] = set()

    # Source 1 — project-specific agent folders
    ps_root = base_dir / "Employees" / "Projects-Specific Agents and Workflows"
    if ps_root.is_dir():
        for child in ps_root.iterdir():
            if child.is_dir() and child.name != "_template":
                seen.add(child.name)

    # Source 2 — runs history log
    history_file = base_dir / "System_logs" / "runs_history.jsonl"
    if history_file.exists():
        for raw in history_file.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
                proj = rec.get("project", "").strip()
                if proj:
                    seen.add(proj)
            except json.JSONDecodeError:
                pass

    return sorted(seen)


def gather_existing_sub_tasks(base_dir: Path) -> list[str]:
    """
    Collect known sub-task labels from two sources and return a de-duplicated,
    sorted list.

    Sources
    -------
    1. 'task_group' values recorded in  System_logs/runs_history.jsonl
    2. 'task_group' column in  System_logs/system_history.csv
    """
    import csv

    seen: set[str] = set()

    # Source 1 — runs history (JSONL)
    history_file = base_dir / "System_logs" / "runs_history.jsonl"
    if history_file.exists():
        for raw in history_file.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
                tg = rec.get("task_group", "").strip()
                if tg and tg.lower() != "nan":
                    seen.add(tg)
            except json.JSONDecodeError:
                pass

    # Source 2 — system history (CSV)
    sys_csv = base_dir / "System_logs" / "system_history.csv"
    if sys_csv.exists():
        try:
            with sys_csv.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tg = row.get("task_group", "").strip()
                    if tg and tg.lower() != "nan":
                        seen.add(tg)
        except Exception:
            pass

    return sorted(seen)


def _print_project_list(projects: list[str]) -> None:
    """Pretty-print the known project list."""
    if not projects:
        print("  (no existing projects found)")
        return
    for i, name in enumerate(projects, start=1):
        print(f"  {i:>2}.  {name}")


# ── Public prompt functions ───────────────────────────────────────────────────

def prompt_project(base_dir: Path) -> str:
    """
    Interactively ask the user to pick an existing project or create a new one.

    Returns the chosen / new project ID as a non-empty string.
    """
    existing = gather_existing_projects(base_dir)

    print()
    print("┌─────────────────────────────────────────┐")
    print("│            PROJECT SELECTION            │")
    print("└─────────────────────────────────────────┘")

    if existing:
        print()
        print("  Existing projects:")
        print()
        _print_project_list(existing)
        print()
        print("  Type a project name / number from the list above,")
        print("  or type  new  to create a new project.")
    else:
        print()
        print("  No existing projects found.")
        print("  Type a name to create your first project.")

    print()

    while True:
        raw = input("  Project › ").strip()

        if not raw:
            print("  ⚠  Project name cannot be empty. Please enter a name.")
            continue

        # Allow the user to pick by number
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(existing):
                chosen = existing[idx]
                print(f"  ✔  Selected existing project: {chosen}")
                print()
                return chosen
            else:
                print(f"  ⚠  Number out of range (1–{len(existing)}). Try again.")
                continue

        # "new" keyword → ask for a name
        if raw.lower() == "new":
            print()
            while True:
                name = input("  New project name › ").strip()
                if not name:
                    print("  ⚠  Project name cannot be empty.")
                    continue
                print(f"  ✔  New project: {name}")
                print()
                return name

        # Treat the input as a direct project name (new or existing match)
        if raw in existing:
            print(f"  ✔  Selected existing project: {raw}")
        else:
            print(f"  ✔  New project: {raw}")
        print()
        return raw


def prompt_sub_task(base_dir: Path) -> str | None:
    """
    Interactively ask the user for an optional sub-task label.

    Mirrors the project prompt:
      • Shows existing sub-tasks from history
      • User can pick an existing one (by number or name),
        type  new  to name a brand-new label,
        or press Enter to skip (logged as NaN).

    Returns
    -------
    str   – the label the user chose / created
    None  – user pressed Enter (no sub-task; caller logs as NaN)
    """
    existing = gather_existing_sub_tasks(base_dir)

    print("┌─────────────────────────────────────────┐")
    print("│              SUB-TASK LABEL             │")
    print("└─────────────────────────────────────────┘")
    print()
    print("  A sub-task groups related runs under one label")
    print("  (e.g. 'EDA Phase 1', 'CFO Brief Q2').")
    print()

    if existing:
        print("  Existing sub-tasks:")
        print()
        for i, name in enumerate(existing, start=1):
            print(f"  {i:>2}.  {name}")
        print()
        print("  Type a sub-task name / number from the list above,")
        print("  type  new  to create a new one,")
        print("  or press Enter to skip  (logged as NaN).")
    else:
        print("  No existing sub-tasks found.")
        print("  Type a name to create one, or press Enter to skip (logged as NaN).")

    print()

    while True:
        raw = input("  Sub-task › ").strip()

        # ── Enter with nothing → NaN ──────────────────────────────────────
        if not raw:
            print("  ✔  No sub-task — will be logged as NaN.")
            print()
            return None

        # ── Pick by number ────────────────────────────────────────────────
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(existing):
                chosen = existing[idx]
                print(f"  ✔  Selected existing sub-task: {chosen}")
                print()
                return chosen
            else:
                print(f"  ⚠  Number out of range (1–{len(existing)}). Try again.")
                continue

        # ── 'new' keyword → ask for a name ────────────────────────────────
        if raw.lower() == "new":
            print()
            while True:
                name = input("  New sub-task name › ").strip()
                if not name:
                    print("  ⚠  Sub-task name cannot be empty. "
                          "Press Enter at the Sub-task prompt to skip instead.")
                    continue
                print(f"  ✔  New sub-task: {name}")
                print()
                return name

        # ── Direct name (existing match or brand-new) ─────────────────────
        if raw in existing:
            print(f"  ✔  Selected existing sub-task: {raw}")
        else:
            print(f"  ✔  New sub-task: {raw}")
        print()
        return raw


def prompt_working_dir(base_dir: Path) -> Path:
    """
    Interactively ask the user where task outputs should be saved.

    The default is  <base_dir>/outputs  (the agent-system outputs folder).
    If the user just presses Enter, that default is used and they are told
    exactly where their files will land.

    Accepts absolute paths, paths relative to the current working directory,
    and  ~  expansion.

    Returns a resolved, absolute Path (directory is created if needed).
    """
    default_dir = (base_dir / "outputs").resolve()

    print("\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510")
    print("\u2502           OUTPUT DIRECTORY              \u2502")
    print("\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518")
    print()
    print("  Where should this task's output files be saved?")
    print()
    print(f"  Default  →  {default_dir}")
    print("  (Press Enter to use the default, or type a custom path.)")
    print()

    while True:
        raw = input("  Output directory \u203a ").strip()

        if not raw:
            # Use the default agent-system outputs folder
            resolved = default_dir
            resolved.mkdir(parents=True, exist_ok=True)
            print(f"  \u2714  Saving to default: {resolved}")
            print()
            return resolved

        # Expand ~ and resolve relative paths from cwd
        candidate = Path(os.path.expanduser(raw))
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        resolved = candidate.resolve()

        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"  \u26a0  Cannot create directory: {exc}")
            print("  Please enter a valid path and try again.")
            continue

        print(f"  \u2714  Output directory: {resolved}")
        print()
        return resolved
