#!/usr/bin/env python3
"""
Feedback-Driven Autonomous Improvement Loop
============================================

  Agent runs a task
       ↓
  Output is scored by output_evaluator (quality 0–10)
       ↓
  Run record saved to runs_history.jsonl
       ↓  [every N runs OR quality drops below threshold]
  performance_analyzer reads history → produces improvement targets
       ↓
  prompt_engineer rewrites flagged agent prompts
       ↓  [human approval gate — configurable]
  registry_auditor validates → approved changes written to disk
       ↓
  Repeat with updated agents (compounding improvement)

Usage
─────
  # Run task once, score it, save telemetry:
  python3 cli/run_feedback_loop.py \\
      --task "..." --project qbus3600 --working-dir ./outputs

  # Run task + trigger analysis after every 3 runs:
  python3 cli/run_feedback_loop.py \\
      --task "..." --working-dir ./outputs --analyze-every 3

  # Run analysis only (no new task):
  python3 cli/run_feedback_loop.py --analyze-only --project qbus3600

  # Fully autonomous (no human approval gate on prompt changes):
  python3 cli/run_feedback_loop.py \\
      --task "..." --working-dir ./outputs --auto-approve

  # Dry run (no API calls, no writes):
  python3 cli/run_feedback_loop.py \\
      --task "..." --working-dir ./outputs --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.parent          # cli/ → agent-system/ root
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "system_improvement"))

from agent_registry import AgentRegistry
from runtime.telemetry import (
    save_run_record, load_recent_runs, summarise_history, RUNS_HISTORY
)
from runtime.dispatcher import run_step
from runtime.notifier import notify
from runtime.improvement_trigger import (
    should_analyze as _should_analyze,
    last_analysis_ts as _last_analysis_ts,
    run_analysis as _run_analysis,
)

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

# ── Lazy import of run_pipeline pieces ───────────────────────────────────────

import importlib.util as _ilu

_wf_spec = _ilu.spec_from_file_location(
    "workflow_engine", BASE / "workflows" / "workflow_engine.py"
)
_wf_mod = _ilu.module_from_spec(_wf_spec)
_wf_spec.loader.exec_module(_wf_mod)
WorkflowEngine     = _wf_mod.WorkflowEngine
WorkflowDefinition = _wf_mod.WorkflowDefinition

# ── Constants ─────────────────────────────────────────────────────────────────

SYSTEM_AGENTS = {"manager", "prompt_engineer", "registry_auditor", "workflow_planner",
                 "output_evaluator", "performance_analyzer"}

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Step 1: run the task ──────────────────────────────────────────────────────

def _run_task(args, registry, engine) -> dict:
    """Delegate to the existing task-mode runner in run_pipeline.py."""
    # Import lazily to avoid circular issues
    import run_pipeline as rp
    working_dir = Path(args.working_dir).resolve()
    working_dir.mkdir(parents=True, exist_ok=True)
    initial_inputs: dict = {}
    if getattr(args, "inputs_file", None):
        initial_inputs.update(json.loads(Path(args.inputs_file).read_text()))
    if getattr(args, "inputs", None):
        initial_inputs.update(json.loads(args.inputs))
    return rp._run_task_mode(args, registry, engine, working_dir, initial_inputs)


# ── Step 2: evaluate output quality ──────────────────────────────────────────

def _evaluate_output(task: str, run_result: dict, working_dir: Path,
                     registry: AgentRegistry, dry_run: bool) -> tuple[float | None, str | None]:
    """
    Call output_evaluator on the run result. Returns (quality_score, quality_notes).
    Returns (None, None) if evaluation cannot run.
    """
    steps = run_result.get("steps", [])
    # Collect final step outputs from the workflow state
    state_path = working_dir / "_workflow_state.json"
    outputs_summary = ""
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            memory = state.get("shared_memory", {})
            # Show last 2 output values (truncated)
            for k, v in list(memory.items())[-2:]:
                preview = str(v)[:600]
                outputs_summary += f"\n### {k}\n{preview}\n"
        except Exception:
            outputs_summary = "(could not read workflow state)"

    step_log = "\n".join(
        f"  {s.get('step', s.get('agent','?'))}: {s.get('status','?')}  "
        f"{s.get('duration_seconds', 0):.1f}s  agent={s.get('agent','?')}"
        for s in steps
    )

    eval_task = (
        f"TASK: {task[:400]}\n\n"
        f"SUCCESS: {run_result.get('success', False)}\n\n"
        f"STEP_LOG:\n{step_log}\n\n"
        f"OUTPUTS:{outputs_summary}"
    )

    try:
        cfg    = registry.load_agent("output_evaluator")
        result = run_step(cfg, eval_task, working_dir, dry_run=dry_run)
    except Exception as e:
        print(f"  [evaluator] error: {e}")
        return None, None

    transcript = result.transcript or ""

    # Parse QUALITY_SCORE
    score_match = re.search(r"QUALITY_SCORE:\s*(\d+(?:\.\d+)?)", transcript)
    score = float(score_match.group(1)) if score_match else None

    # Parse FAILURE_POINTS + IMPROVEMENT_HINTS as notes
    notes_parts = []
    for section in ("FAILURE_POINTS", "IMPROVEMENT_HINTS"):
        m = re.search(rf"### {section}\n(.*?)(?=\n###|\Z)", transcript, re.DOTALL)
        if m:
            content = m.group(1).strip()
            if content and content.lower() != "none":
                notes_parts.append(f"{section}:\n{content}")
    notes = "\n\n".join(notes_parts) or None

    return score, notes


# ── Step 3 & 4: analysis helpers (shared via runtime/improvement_trigger) ─────
# _should_analyze, _last_analysis_ts, _run_analysis imported at top of file


# ── Step 5: apply improvements ────────────────────────────────────────────────

def _apply_improvements(targets: list[dict], registry: AgentRegistry,
                        working_dir: Path, dry_run: bool,
                        auto_approve: bool) -> dict:
    """
    Feed improvement targets into the existing _run_one_finding from run_self_improve.
    Returns summary counts.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_self_improve", BASE / "system_improvement" / "run_self_improve.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.WORKING_DIR.mkdir(parents=True, exist_ok=True)

    counts = {"applied": 0, "blocked": 0, "skipped": 0, "unresolved": 0}
    skip_remaining = False

    for target in targets:
        agent = target.get("agent", "?")
        finding = target.get("finding", "")
        signal = target.get("signal", "")
        metric = target.get("metric", "")

        if skip_remaining:
            print(f"  [skipped] {agent}")
            counts["skipped"] += 1
            continue

        # Enrich the finding with signal context
        enriched_target = {
            **target,
            "type": "prompt_rewrite",
            "finding": f"[{signal} signal: {metric}] {finding}",
        }

        if auto_approve:
            # Patch the approval function to always approve
            original_gate = getattr(mod, "_human_approval_gate", None)
            if original_gate:
                mod._human_approval_gate = lambda *a, **kw: ("approve", "")
            result = mod._run_one_finding(enriched_target, registry, dry_run)
            if original_gate:
                mod._human_approval_gate = original_gate
        else:
            result = mod._run_one_finding(enriched_target, registry, dry_run)

        status = result.get("final_status", "")
        if status == "applied":
            counts["applied"] += 1
            print(f"  {GREEN}[applied]{RESET}  {agent}: {finding[:80]}")
        elif status == "blocked":
            counts["blocked"] += 1
            print(f"  {RED}[blocked]{RESET} {agent}: {finding[:80]}")
        elif status == "skipped_by_user":
            counts["skipped"] += 1
            skip_remaining = True
        else:
            counts["unresolved"] += 1

    return counts


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Feedback-driven autonomous improvement loop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # Task args (mirrors run_pipeline.py)
    ap.add_argument("--task",         help="Task description to run")
    ap.add_argument("--project",      default=None)
    ap.add_argument("--working-dir",  default="./outputs")
    ap.add_argument("--inputs",       help="JSON literal: initial inputs dict")
    ap.add_argument("--inputs-file",  help="Path to JSON file with initial inputs")

    # Feedback loop controls
    ap.add_argument("--analyze-every",   type=int,   default=5,
                    help="Run performance analysis every N task runs (0 = never, default: 5)")
    ap.add_argument("--quality-threshold", type=float, default=6.0,
                    help="Also trigger analysis if rolling avg quality < this (default: 6.0)")
    ap.add_argument("--analyze-only",    action="store_true",
                    help="Skip task execution — run performance analysis on existing history only")
    ap.add_argument("--skip-eval",       action="store_true",
                    help="Skip output evaluation (no quality score this run)")
    ap.add_argument("--auto-approve",    action="store_true",
                    help="Apply prompt improvements without human approval gate (dangerous)")
    ap.add_argument("--dry-run",         action="store_true",
                    help="No API calls, no writes to disk")

    args = ap.parse_args()

    registry = AgentRegistry(base_dir=BASE, project_id=args.project)
    engine   = WorkflowEngine(registry, base_dir=BASE)
    working_dir = Path(args.working_dir).resolve()
    working_dir.mkdir(parents=True, exist_ok=True)

    # ── Analyze-only mode ─────────────────────────────────────────────────────
    if args.analyze_only:
        print(f"\n{BOLD}── performance analysis (analyze-only) ──{RESET}")
        summary = summarise_history()
        print(f"  Runs in history:  {summary['run_count']}")
        print(f"  Success rate:     {summary.get('success_rate', 'n/a')}")
        print(f"  Avg quality:      {summary.get('avg_quality_score', 'n/a')}")
        print(f"  Avg cost:         ${summary.get('avg_cost_usd', 0):.4f}")
        print()

        targets = _run_analysis(registry, working_dir, args.dry_run)
        if not targets:
            print("  No improvement targets found.")
            return

        print(f"\n  {len(targets)} target(s) identified:")
        for t in targets:
            priority_color = GREEN if t.get("priority") == "low" else \
                             YELLOW if t.get("priority") == "medium" else RED
            print(f"  {priority_color}[{t.get('priority','?')}]{RESET} "
                  f"{t.get('agent','?')}: {t.get('finding','')[:100]}")

        print()
        counts = _apply_improvements(targets, registry, working_dir,
                                     args.dry_run, args.auto_approve)
        print(f"\n  Applied: {counts['applied']}  Blocked: {counts['blocked']}  "
              f"Skipped: {counts['skipped']}  Unresolved: {counts['unresolved']}")
        return

    # ── Task required for all other modes ─────────────────────────────────────
    if not args.task:
        ap.error("--task is required unless --analyze-only is set")

    # ── Step 1: run the task ──────────────────────────────────────────────────
    print(f"\n{BOLD}── step 1/4: task execution ──{RESET}")
    run_result = _run_task(args, registry, engine)
    success = run_result.get("success", False)
    print(f"  {'✓' if success else '✗'} task {'succeeded' if success else 'failed'}")

    # ── Step 2: evaluate output ───────────────────────────────────────────────
    quality_score, quality_notes = None, None
    if not args.skip_eval and not args.dry_run:
        print(f"\n{BOLD}── step 2/4: output evaluation ──{RESET}")
        quality_score, quality_notes = _evaluate_output(
            args.task, run_result, working_dir, registry, args.dry_run
        )
        if quality_score is not None:
            color = GREEN if quality_score >= 7 else YELLOW if quality_score >= 5 else RED
            print(f"  Quality score: {color}{quality_score}/10{RESET}")
            if quality_notes:
                for line in quality_notes.splitlines()[:4]:
                    print(f"  {line}")
        else:
            print("  (evaluation did not return a score)")
    else:
        print(f"\n{BOLD}── step 2/4: output evaluation — skipped ──{RESET}")

    # ── Step 3: save telemetry ────────────────────────────────────────────────
    print(f"\n{BOLD}── step 3/4: telemetry ──{RESET}")
    if not args.dry_run:
        record = save_run_record(
            task=args.task,
            project=args.project,
            run_result=run_result,
            quality_score=quality_score,
            quality_notes=quality_notes,
            working_dir=working_dir,
        )
        print(f"  Run record saved: {record['run_id']}  →  {RUNS_HISTORY.name}")
        print(f"  Total runs in history: {len(load_recent_runs(n=1000))}")
    else:
        print("  [dry-run] telemetry skipped")

    # ── Notify on run failure ─────────────────────────────────────────────
    if not success:
        notify(
            event   = "run_error",
            summary = f"Pipeline failed — task: {args.task[:120]}",
            details = {
                "task":    args.task[:200],
                "project": args.project or "(none)",
                "steps":   len(run_result.get("steps", [])),
            },
        )

    # ── Notify on quality alert ───────────────────────────────────────────
    if quality_score is not None and quality_score < args.quality_threshold:
        notify(
            event   = "quality_alert",
            summary = f"Quality score {quality_score}/10 is below threshold {args.quality_threshold}",
            details = {
                "quality_score":     f"{quality_score}/10",
                "threshold":         args.quality_threshold,
                "notes":             (quality_notes or "")[:300],
            },
        )

    # ── Step 4: check improvement trigger ────────────────────────────────────
    print(f"\n{BOLD}── step 4/4: improvement trigger check ──{RESET}")
    should_run, reason = _should_analyze(
        args.analyze_every, args.quality_threshold,
    )
    print(f"  Trigger: {'YES' if should_run else 'no'}  ({reason})")

    if should_run and not args.dry_run:
        print(f"\n  {CYAN}Running performance analysis...{RESET}")
        targets = _run_analysis(registry, working_dir, args.dry_run)

        if targets:
            print(f"\n  {len(targets)} improvement target(s):")
            for t in targets:
                priority_color = GREEN if t.get("priority") == "low" else \
                                 YELLOW if t.get("priority") == "medium" else RED
                print(f"  {priority_color}[{t.get('priority','?')}]{RESET} "
                      f"{t.get('agent','?')}: {t.get('finding','')[:100]}")

            # Notify that analysis found targets
            target_lines = "\n".join(
                f"• [{t.get('priority','?')}] {t.get('agent','?')}: {t.get('finding','')[:80]}"
                for t in targets
            )
            notify(
                event   = "improvement_triggered",
                summary = f"{len(targets)} improvement target(s) found ({reason})",
                details = {
                    "trigger":  reason,
                    "targets":  target_lines,
                    "auto_approve": args.auto_approve,
                },
            )

            print()
            counts = _apply_improvements(targets, registry, working_dir,
                                         args.dry_run, args.auto_approve)
            print(f"\n  Applied: {counts['applied']}  Blocked: {counts['blocked']}  "
                  f"Skipped: {counts['skipped']}  Unresolved: {counts['unresolved']}")

            # Notify on outcomes
            if counts["applied"] > 0:
                notify(
                    event   = "improvement_applied",
                    summary = f"{counts['applied']} agent prompt(s) updated and reloaded",
                    details = {"applied": counts["applied"], "blocked": counts["blocked"],
                               "skipped": counts["skipped"]},
                )
            if counts["blocked"] > 0:
                notify(
                    event   = "improvement_blocked",
                    summary = f"{counts['blocked']} proposed change(s) were rejected — review needed",
                    details = {"blocked": counts["blocked"]},
                )
        else:
            print("  No improvement targets found — system is healthy.")
            notify(
                event   = "health_ok",
                summary = f"Performance analysis ran — no issues found ({reason})",
            )

    print()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
