"""
Improvement trigger — called automatically after every run_pipeline.py run.

Checks whether performance analysis should fire, runs performance_analyzer
if so, and sends a notification with the findings. Does NOT apply any changes.
The user decides what to do next.

This module has no dependency on run_pipeline or run_feedback_loop,
so it can be safely imported from either.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent   # agent-system root


# ── Timestamp helpers ─────────────────────────────────────────────────────────

def _iso_to_ts(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0


def last_analysis_ts() -> float:
    """
    Return unix timestamp of the last time performance analysis ran.
    Anchors on notification_log entries for improvement_triggered or health_ok —
    both are written whenever analysis runs regardless of outcome.
    Returns 0.0 if analysis has never run.
    """
    from runtime.notifier import NOTIFY_LOG
    if not NOTIFY_LOG.exists():
        return 0.0
    for line in reversed(NOTIFY_LOG.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if entry.get("event") in ("improvement_triggered", "health_ok"):
                return _iso_to_ts(entry.get("ts", ""))
        except Exception:
            pass
    return 0.0


# ── Trigger check ─────────────────────────────────────────────────────────────

def should_analyze(analyze_every: int = 10) -> tuple[bool, str]:
    """
    Returns (should_run, reason).

    Fires when analyze_every or more runs have completed since the last
    analysis run. Anchors on last analysis (not last applied improvement)
    so blocked/rejected targets don't cause it to fire on every subsequent run.
    Window is max(analyze_every × 3, 20) so it always covers enough history.
    """
    from runtime.telemetry import load_recent_runs

    if analyze_every <= 0:
        return False, "analyze_every=0, disabled"

    window = max(analyze_every * 3, 20)
    runs   = load_recent_runs(n=window)
    if not runs:
        return False, "no history yet"

    last_ts     = last_analysis_ts()
    runs_since  = sum(
        1 for r in runs
        if _iso_to_ts(r.get("timestamp", "")) > last_ts
    )

    if runs_since >= analyze_every:
        return True, f"{runs_since} new run(s) since last analysis (every {analyze_every})"

    return False, f"{runs_since}/{analyze_every} runs since last analysis"


# ── Performance analysis ──────────────────────────────────────────────────────

def _parse_targets(transcript: str) -> list[dict]:
    """Parse IMPROVEMENT_TARGETS from performance_analyzer output."""
    match = re.search(r"### IMPROVEMENT_TARGETS\n(.*?)(?=\n###|\Z)",
                      transcript, re.DOTALL)
    if not match:
        return []
    block = match.group(1).strip()
    if block.lower() == "none":
        return []

    targets, current = [], {}
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("- agent:"):
            if current.get("agent"):
                targets.append(current)
            current = {"agent": line.split(":", 1)[1].strip()}
        elif ":" in line and current:
            k, v = line.split(":", 1)
            current[k.strip()] = v.strip().strip('"')
    if current.get("agent"):
        targets.append(current)

    # Never suggest improvements to system agents
    protected = {"manager", "prompt_engineer", "registry_auditor",
                 "workflow_planner", "output_evaluator", "performance_analyzer"}
    return [t for t in targets if t.get("agent") not in protected]


def run_analysis(registry, working_dir: Path) -> list[dict]:
    """
    Call performance_analyzer on recent history.
    Returns list of improvement target dicts.
    """
    from runtime.telemetry   import summarise_history
    from runtime.dispatcher  import run_step
    from runtime.notifier    import NOTIFY_LOG

    summary = summarise_history(n=20)
    if summary["run_count"] == 0:
        return []

    recent_improvements: list[str] = []
    log_path = BASE / "System_logs" / "improvement_log.jsonl"
    if log_path.exists():
        for line in log_path.read_text().splitlines()[-20:]:
            try:
                e = json.loads(line)
                if e.get("agent") and e.get("finding"):
                    recent_improvements.append(
                        f"  - {e['agent']}: {e['finding'][:100]}"
                    )
            except Exception:
                pass

    task = (
        f"RUN_SUMMARY:\n{json.dumps(summary, indent=2)}\n\n"
        f"RECENT_RUNS:\n{json.dumps(summary.get('recent_runs', []), indent=2)}\n\n"
        f"IMPROVEMENT_LOG (last 20):\n" +
        ("\n".join(recent_improvements) or "  (none)") +
        "\n\nTHRESHOLD_CONFIG:\n"
        "  error_rate_threshold: 0.10\n"
        "  token_efficiency_multiplier: 3.0\n"
        "  speed_multiplier: 2.0\n"
    )

    try:
        cfg    = registry.load_agent("performance_analyzer")
        result = run_step(cfg, task, working_dir)
        return _parse_targets(result.transcript or "")
    except Exception as e:
        print(f"  [improvement_trigger] performance_analyzer error: {e}")
        return []


# ── Main entry point called from run_pipeline ─────────────────────────────────

# Written by post_run_check, read by run_self_improve._log to stamp trigger_id on CSV rows
_TRIGGER_SESSION_FILE = BASE / "System_logs" / "_improvement_session.json"


def _write_trigger_session(run_id: str, task: str, reason: str,
                           task_group: str = "") -> None:
    _TRIGGER_SESSION_FILE.write_text(
        json.dumps({"trigger_run_id": run_id, "trigger_task": task[:200],
                    "reason": reason, "task_group": task_group})
    )


def read_trigger_session() -> dict:
    """Read the active trigger session. Returns {} if none exists."""
    if not _TRIGGER_SESSION_FILE.exists():
        return {}
    try:
        return json.loads(_TRIGGER_SESSION_FILE.read_text())
    except Exception:
        return {}


def post_run_check(
    registry,
    working_dir: Path,
    analyze_every: int = 10,
    dry_run: bool = False,
    run_id: str = "",
    task: str = "",
    task_group: str = "",
) -> None:
    """
    Called automatically after every successful run_pipeline save.

    1. Checks if analyze_every runs have passed since last analysis.
    2. If yes: runs performance_analyzer (one API call, sonnet-class model).
    3. Fires macOS / email / Slack notification with findings.
    4. Does NOT apply any changes — that is the user's decision.

    If dry_run=True the trigger check still runs but no API call is made.
    """
    from runtime.notifier import notify

    should, reason = should_analyze(analyze_every)
    if not should:
        return   # silent — nothing to report

    print(f"\n── improvement trigger ──")
    print(f"  {reason}")

    # Write session file so improvement events can link back to this run
    if run_id:
        _write_trigger_session(run_id, task, reason, task_group=task_group)

    if dry_run:
        notify(
            event   = "health_ok",
            summary = f"[dry-run] Trigger would fire — {reason}",
        )
        return

    print(f"  Running performance_analyzer...")
    targets = run_analysis(registry, working_dir)

    if not targets:
        print(f"  No issues found — system is healthy.")
        notify(
            event   = "health_ok",
            summary = f"Performance check passed — no improvements needed ({reason})",
            details = {"trigger": reason},
        )
        return

    # Format the findings for the notification
    lines = []
    for t in targets:
        pri   = t.get("priority", "?")
        agent = t.get("agent", "?")
        find  = t.get("finding", "")[:120]
        sig   = t.get("signal", "")
        metric = t.get("metric", "")
        lines.append(f"[{pri}] {agent} ({sig}: {metric})\n  → {find}")

    findings_text = "\n\n".join(lines)

    # Build the self-improvement task the user can paste directly
    improvement_task = (
        "Review the following agent performance findings and improve the "
        "underperforming agents:\n\n" + findings_text
    )

    print(f"\n  {len(targets)} improvement target(s) found:")
    for t in targets:
        print(f"    [{t.get('priority','?'):>6}] {t.get('agent','?')}: {t.get('finding','')[:80]}")

    # ── Notify first (non-blocking) ─────────────────────────────────────────
    notify(
        event   = "improvement_triggered",
        summary = f"{len(targets)} agent(s) need improvement — check terminal for details",
        details = {
            "trigger":  reason,
            "findings": findings_text[:800],
            "next_step": "Review and action findings in terminal",
        },
    )

    # ── Offer inline approval loop ─────────────────────────────────────────
    print()
    print("  ──────────────────────────────────────────────────────────────────")
    print("  Action these findings now? [Y/n]  ", end="", flush=True)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer in ("", "y", "yes"):
        # ── Load run_self_improve without argparse conflicts ──────────────────
        import importlib.util as _ilu
        _si_path = BASE / "system_improvement" / "run_self_improve.py"
        _si_spec = _ilu.spec_from_file_location("run_self_improve", _si_path)
        _si_mod  = _ilu.module_from_spec(_si_spec)
        _si_spec.loader.exec_module(_si_mod)
        _si_mod.WORKING_DIR.mkdir(parents=True, exist_ok=True)

        counts = {"applied": 0, "blocked": 0, "skipped": 0, "unresolved": 0}
        skip_remaining = False

        print()
        for target in targets:
            if skip_remaining:
                print(f"  [skipped] {target.get('agent')}")
                counts["skipped"] += 1
                continue

            finding = {
                "agent":   target.get("agent", ""),
                "finding": target.get("finding", ""),
                "type":    "prompt_rewrite",
            }
            result = _si_mod._run_one_finding(finding, registry, dry_run)
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

        print()
        print(f"  Applied: {counts['applied']}  "
              f"Blocked: {counts['blocked']}  "
              f"Skipped: {counts['skipped']}  "
              f"Unresolved: {counts['unresolved']}")
        print(f"  Log: {_si_mod.LOG_PATH}")

    else:
        print()
        print("  To action later, run System-Improve Mode:")
        print("    python3 run_pipeline.py --system-improve")
