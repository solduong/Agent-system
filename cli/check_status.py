#!/usr/bin/env python3
"""
check_status.py — instant system health snapshot, no API calls.

Usage
─────
  python3 cli/check_status.py              # full health report
  python3 cli/check_status.py --short      # one-line summary only
  python3 cli/check_status.py --notify     # fire a macOS/email/Slack alert with the summary
  python3 cli/check_status.py --json       # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent          # cli/ → agent-system/ root
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "system_improvement"))

from runtime.telemetry   import summarise_history, load_recent_runs, RUNS_HISTORY
from runtime.notifier    import recent_notifications, NOTIFY_LOG

# ── ANSI ──────────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def _color(val, *, good, warn, bad=None, higher_is_better=True):
    """Return ANSI color code based on thresholds."""
    if bad is None:
        bad = warn
    if higher_is_better:
        if val >= good:  return GREEN
        if val >= warn:  return YELLOW
        return RED
    else:
        if val <= good:  return GREEN
        if val <= warn:  return YELLOW
        return RED


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ago(iso: str) -> str:
    """Human-readable time since an ISO-8601 timestamp."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        secs = int(diff.total_seconds())
        if secs < 60:     return f"{secs}s ago"
        if secs < 3600:   return f"{secs//60}m ago"
        if secs < 86400:  return f"{secs//3600}h ago"
        return f"{secs//86400}d ago"
    except Exception:
        return iso


def _improvement_log_summary(n: int = 10) -> list[dict]:
    log_path = BASE / "System_logs" / "improvement_log.jsonl"
    if not log_path.exists():
        return []
    lines = log_path.read_text().splitlines()
    records = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
        if len(records) >= n:
            break
    return list(reversed(records))


# ── Report sections ───────────────────────────────────────────────────────────

def _section_overview(summary: dict) -> str:
    if summary["run_count"] == 0:
        return f"\n{BOLD}No runs recorded yet.{RESET}\n"

    sr  = summary["success_rate"]
    qs  = summary.get("avg_quality_score")
    cost = summary["avg_cost_usd"]
    secs = summary["avg_total_secs"]

    sr_col  = _color(sr,  good=0.9, warn=0.7, higher_is_better=True)
    qs_col  = (_color(qs, good=7.0, warn=5.0, higher_is_better=True) if qs else DIM)
    cost_col= _color(cost, good=1.0, warn=3.0, higher_is_better=False)

    lines = [f"\n{BOLD}── Overview  (last {summary['run_count']} runs) ──{RESET}"]
    lines.append(f"  Success rate:    {sr_col}{sr*100:.0f}%{RESET}")
    lines.append(f"  Avg quality:     {qs_col}{qs if qs else 'n/a'}{RESET}/10")
    lines.append(f"  Avg cost/run:    {cost_col}${cost:.4f}{RESET}")
    lines.append(f"  Avg time/run:    {secs:.0f}s")
    return "\n".join(lines)


def _section_agents(summary: dict) -> str:
    agent_stats = summary.get("agent_stats", {})
    if not agent_stats:
        return ""

    lines = [f"\n{BOLD}── Per-Agent Health ──{RESET}"]
    lines.append(f"  {'Agent':<22} {'Calls':>5}  {'Errors':>6}  {'Err%':>5}  {'AvgCost':>8}  {'AvgTime':>8}  Status")
    lines.append("  " + "─" * 72)

    for agent, s in sorted(agent_stats.items()):
        er = s["error_rate"]
        er_col = GREEN if er == 0 else YELLOW if er < 0.1 else RED
        status = "✓ healthy" if er == 0 else \
                 f"{YELLOW}⚠ watch{RESET}" if er < 0.1 else \
                 f"{RED}✗ degraded{RESET}"
        lines.append(
            f"  {agent:<22} {s['calls']:>5}  {s['errors']:>6}  "
            f"{er_col}{er*100:>4.0f}%{RESET}  "
            f"${s['avg_cost_usd']:>7.3f}  "
            f"{s['avg_secs']:>7.1f}s  {status}"
        )
    return "\n".join(lines)


def _section_recent_runs(n: int = 5) -> str:
    runs = load_recent_runs(n=n)
    if not runs:
        return ""

    lines = [f"\n{BOLD}── Last {len(runs)} Runs ──{RESET}"]
    lines.append(f"  {'Run ID':<14} {'When':<12} {'OK':>4}  {'Quality':>8}  {'Cost':>8}  {'Time':>8}")
    lines.append("  " + "─" * 60)

    for r in reversed(runs):
        ok    = r.get("success", False)
        ok_s  = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        qs    = r.get("quality_score")
        qs_s  = f"{qs:.1f}/10" if qs is not None else "  n/a "
        qs_col= (_color(qs, good=7, warn=5, higher_is_better=True) if qs else DIM)
        when  = _ago(r.get("timestamp", ""))
        lines.append(
            f"  {r['run_id']:<14} {when:<12} {ok_s}   "
            f"{qs_col}{qs_s:>8}{RESET}  "
            f"${r.get('total_cost_usd', 0):>7.3f}  "
            f"{r.get('total_seconds', 0):>7.0f}s"
        )
    return "\n".join(lines)


def _section_improvements(n: int = 5) -> str:
    records = _improvement_log_summary(n)
    if not records:
        return f"\n{BOLD}── Improvement Log ──{RESET}\n  (no entries yet)"

    lines = [f"\n{BOLD}── Last {len(records)} Improvement Events ──{RESET}"]
    for r in records:
        status = r.get("final_status", r.get("status", "?"))
        col = GREEN if status == "applied" else \
              RED   if status in ("blocked", "validation_rejected") else DIM
        agent   = r.get("agent", "?")
        finding = r.get("finding", r.get("description", ""))[:80]
        ts      = _ago(r.get("timestamp", r.get("ts", "")))
        lines.append(f"  {col}[{status}]{RESET}  {agent:<22} {ts:<12}  {finding}")
    return "\n".join(lines)


def _section_notifications(n: int = 5) -> str:
    notes = recent_notifications(n)
    if not notes:
        return f"\n{BOLD}── Recent Alerts ──{RESET}\n  (none)"

    _event_col = {
        "improvement_applied":   GREEN,
        "health_ok":             GREEN,
        "improvement_triggered": CYAN,
        "improvement_blocked":   YELLOW,
        "quality_alert":         RED,
        "run_error":             RED,
    }
    lines = [f"\n{BOLD}── Recent Alerts ──{RESET}"]
    for n_ in reversed(notes):
        event   = n_.get("event", "?")
        col     = _event_col.get(event, DIM)
        summary = n_.get("summary", "")[:90]
        ts      = _ago(n_.get("ts", ""))
        lines.append(f"  {col}{event:<28}{RESET}  {ts:<12}  {summary}")
    return "\n".join(lines)


def _trigger_check(summary: dict, analyze_every: int = 5,
                   quality_threshold: float = 6.0) -> str:
    """Show whether the improvement trigger would fire right now."""
    from run_feedback_loop import _should_analyze, _last_analysis_ts
    should, reason = _should_analyze(analyze_every, quality_threshold)
    last_ts = _last_analysis_ts()
    if last_ts:
        from datetime import datetime, timezone
        iso = datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        last_s = _ago(iso)
    else:
        last_s = "never"
    col = RED if should else GREEN
    return (f"\n{BOLD}── Improvement Trigger ──{RESET}\n"
            f"  Last analysis:  {last_s}\n"
            f"  Would fire now: {col}{'YES — ' if should else 'no — '}{reason}{RESET}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Instant agent-system health snapshot.")
    ap.add_argument("--short",  action="store_true", help="One-line summary only")
    ap.add_argument("--notify", action="store_true", help="Also fire a notification")
    ap.add_argument("--json",   action="store_true", help="Machine-readable JSON output")
    ap.add_argument("--runs",   type=int, default=20, help="How many runs to include (default 20)")
    args = ap.parse_args()

    summary = summarise_history(n=args.runs)

    # ── JSON mode ─────────────────────────────────────────────────────────────
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
        return

    # ── Short mode ────────────────────────────────────────────────────────────
    if args.short:
        n    = summary["run_count"]
        sr   = f"{summary.get('success_rate',0)*100:.0f}%" if n else "n/a"
        qs   = f"{summary['avg_quality_score']}/10" if summary.get("avg_quality_score") else "n/a"
        cost = f"${summary.get('avg_cost_usd',0):.3f}" if n else "n/a"
        print(f"runs={n}  success={sr}  quality={qs}  avg_cost={cost}  history={RUNS_HISTORY}")
        return

    # ── Full report ───────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"{BOLD}  Agent System Status{RESET}  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  History: {RUNS_HISTORY}")
    print(f"{'='*60}")

    print(_section_overview(summary))
    print(_section_agents(summary))
    print(_section_recent_runs(n=5))
    print(_section_improvements(n=5))
    print(_section_notifications(n=5))
    print(_trigger_check(summary))
    print()

    # ── Optional notification ─────────────────────────────────────────────────
    if args.notify:
        from runtime.notifier import notify
        n    = summary["run_count"]
        sr   = f"{summary.get('success_rate',0)*100:.0f}%"
        qs   = summary.get("avg_quality_score")
        qs_s = f"{qs}/10" if qs else "n/a"
        notify(
            event   = "health_ok",
            summary = f"Status check — {n} runs, {sr} success, quality {qs_s}",
            details = {
                "runs":          n,
                "success_rate":  sr,
                "avg_quality":   qs_s,
                "avg_cost":      f"${summary.get('avg_cost_usd',0):.4f}",
            },
        )
        print(f"  {GREEN}Notification sent.{RESET}\n")


if __name__ == "__main__":
    main()
