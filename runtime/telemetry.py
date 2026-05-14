"""
Telemetry — persists a structured record for every pipeline run.

Each record is one JSONL line appended to:
    <agent-system-root>/runs_history.jsonl

Record schema
─────────────
{
  "run_id":              str   — uuid4 hex
  "timestamp":           str   — ISO-8601 UTC
  "task_preview":        str   — first 300 chars of task
  "task_full":           str   — complete task prompt, untruncated
  "task_hash":           str   — md5 of full task (8 chars) for deduplication
  "task_group":          str | null — user-supplied label (--group flag)
  "project":             str | null
  "workflow":            str   — generated YAML path or named workflow
  "success":             bool
  "quality_score":       float | null  — 0–10, filled by output_evaluator
  "quality_notes":       str | null    — evaluator findings
  "total_input_tokens":  int
  "total_output_tokens": int
  "total_cost_usd":      float
  "total_seconds":       float
  "steps": [
    {
      "agent":            str
      "status":           str   — "ok" | "error" | "dry_run" | "skipped_resume"
      "input_tokens":     int
      "output_tokens":    int
      "cost_usd":         float
      "duration_seconds": float
    }
  ]
}
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent.parent          # agent-system root
SYSTEM_DIR   = BASE / "System_logs"          # all runtime/log files — never inside working_dir
RUNS_HISTORY = SYSTEM_DIR / "runs_history.jsonl"
SYSTEM_CSV   = SYSTEM_DIR / "system_history.csv"
AGENT_LOGS_DIR  = SYSTEM_DIR / "_agent_logs"
WORKFLOW_STATE  = SYSTEM_DIR / "_workflow_state.json"

# Approximate cost per token for each model family (USD).
# Used only when the SDK does not return total_cost_usd directly.
_COST_PER_1K = {
    "claude-opus-4":    {"in": 0.015,  "out": 0.075},
    "claude-sonnet-4":  {"in": 0.003,  "out": 0.015},
    "claude-haiku-3":   {"in": 0.00025,"out": 0.00125},
}
_DEFAULT_COST = {"in": 0.003, "out": 0.015}   # sonnet fallback


def _estimate_cost(model: str, in_tok: int, out_tok: int) -> float:
    rates = _DEFAULT_COST
    for prefix, r in _COST_PER_1K.items():
        if model.startswith(prefix):
            rates = r
            break
    return round(in_tok / 1000 * rates["in"] + out_tok / 1000 * rates["out"], 6)


def _read_cost_from_log(agent_name: str, log_dir: Path | None = None) -> float | None:
    """Read the most recent total_cost_usd from an agent's JSONL log.

    Lookup order:
      1. log_dir / <agent>.jsonl                   (per-run session dir)
      2. log_dir / _agent_logs / <agent>.jsonl     (parent dir of session)
      3. recursive search under log_dir for <agent>.jsonl  (fallback)
    """
    base_dir = Path(log_dir) if log_dir else AGENT_LOGS_DIR
    candidates = [
        base_dir / f"{agent_name}.jsonl",
        base_dir / "_agent_logs" / f"{agent_name}.jsonl",
    ]
    log_file = next((p for p in candidates if p.exists()), None)
    if log_file is None and base_dir.exists():
        # Fallback — scan subfolders (per-run session dirs) for a matching log
        try:
            log_file = next(base_dir.rglob(f"{agent_name}.jsonl"), None)
        except Exception:
            log_file = None
    if log_file is None or not log_file.exists():
        return None
    try:
        lines = log_file.read_text().splitlines()
        for line in reversed(lines):
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("type") == "result" and entry.get("total_cost_usd") is not None:
                return float(entry["total_cost_usd"])
    except Exception:
        pass
    return None


def _step_cost(step: dict, log_dir: Path | None = None) -> float:
    """Extract or estimate cost for a single step record.
    Priority: explicit cost_usd (non-None) > agent log > token estimation.
    """
    explicit = step.get("cost_usd")
    if explicit is not None:
        return float(explicit)
    if log_dir is not None:
        agent = step.get("agent", "")
        from_log = _read_cost_from_log(agent, log_dir)
        if from_log is not None:
            return from_log
    model = step.get("model", "claude-sonnet-4")
    return _estimate_cost(model, step.get("input_tokens", 0),
                          step.get("output_tokens", 0))


def save_run_record(
    *,
    task: str,
    project: str | None,
    task_group: str | None = None,
    run_result: dict,
    quality_score: float | None = None,
    quality_notes: str | None = None,
    history_path: Path | None = None,
    working_dir: Path | None = None,
    log_dir: Path | None = None,
    run_id: str | None = None,
) -> dict:
    """Build and append a run record. Returns the record dict.

    log_dir : preferred path to the per-run agent log folder (where dispatcher
              wrote <agent>.jsonl files). Falls back to working_dir for back-
              compat, then to AGENT_LOGS_DIR via _read_cost_from_log.
    run_id  : optional pre-generated run identifier so the run record can be
              correlated with a per-run log folder named <run_id>_<task_group>.
              If not provided, a fresh uuid4 hex is generated.
    """
    history_path = Path(history_path or RUNS_HISTORY)
    steps = run_result.get("steps", [])

    # Filter to actual agent steps (skip orchestration meta-steps)
    agent_steps = [
        s for s in steps
        if s.get("agent") and s.get("status") not in ("skipped_resume", "expanded")
    ]

    cost_log_dir = Path(log_dir) if log_dir else (Path(working_dir) if working_dir else None)

    step_records = []
    for s in agent_steps:
        cost = _step_cost(s, log_dir=cost_log_dir)
        step_records.append({
            "agent":            s.get("agent", "unknown"),
            "status":           s.get("status", "unknown"),
            "input_tokens":     s.get("input_tokens", 0),
            "output_tokens":    s.get("output_tokens", 0),
            "cost_usd":         cost,
            "duration_seconds": round(s.get("duration_seconds", 0), 2),
        })

    total_in   = sum(s["input_tokens"]    for s in step_records)
    total_out  = sum(s["output_tokens"]   for s in step_records)
    total_cost = round(sum(s["cost_usd"]  for s in step_records), 6)
    total_secs = round(sum(s["duration_seconds"] for s in step_records), 2)

    record: dict[str, Any] = {
        "run_id":              run_id or uuid.uuid4().hex[:12],
        "timestamp":           time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task_preview":        task[:300],
        "task_full":           task,
        "task_hash":           hashlib.md5(task.encode()).hexdigest()[:8],
        "task_group":          task_group or "",
        "project":             project,
        "workflow":            run_result.get("generated_yaml", run_result.get("workflow", "")),
        "success":             bool(run_result.get("success", False)),
        "quality_score":       quality_score,
        "quality_notes":       quality_notes,
        "total_input_tokens":  total_in,
        "total_output_tokens": total_out,
        "total_cost_usd":      total_cost,
        "total_seconds":       total_secs,
        "steps":               step_records,
    }

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    # Mirror to CSV — append-only, never deletes historical rows
    append_run_to_csv(record)

    return record


def load_recent_runs(n: int = 20, history_path: Path | None = None) -> list[dict]:
    """Return the last *n* run records, newest last."""
    history_path = Path(history_path or RUNS_HISTORY)
    if not history_path.exists():
        return []
    lines = history_path.read_text().splitlines()
    records = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records[-n:]


def load_runs_for_agent(agent_name: str, n: int = 50,
                        history_path: Path | None = None) -> list[dict]:
    """Return step-level records for a specific agent across recent runs."""
    runs = load_recent_runs(n=n, history_path=history_path)
    results = []
    for run in runs:
        for step in run.get("steps", []):
            if step.get("agent") == agent_name:
                results.append({
                    "run_id":       run["run_id"],
                    "timestamp":    run["timestamp"],
                    "task_hash":    run["task_hash"],
                    "run_success":  run["success"],
                    "quality_score": run.get("quality_score"),
                    **step,
                })
    return results


def summarise_history(n: int = 20, history_path: Path | None = None) -> dict:
    """
    Return aggregate stats over the last *n* runs — used by performance_analyzer.
    """
    runs = load_recent_runs(n=n, history_path=history_path)
    if not runs:
        return {"run_count": 0}

    success_count = sum(1 for r in runs if r["success"])
    scored = [r for r in runs if r.get("quality_score") is not None]

    # Per-agent aggregates
    agent_stats: dict[str, dict] = {}
    for run in runs:
        for step in run.get("steps", []):
            a = step.get("agent", "unknown")
            if a not in agent_stats:
                agent_stats[a] = {
                    "calls": 0, "errors": 0,
                    "total_tokens": 0, "total_cost": 0.0, "total_secs": 0.0,
                }
            s = agent_stats[a]
            s["calls"]        += 1
            s["errors"]       += 1 if step.get("status") == "error" else 0
            s["total_tokens"] += step.get("input_tokens", 0) + step.get("output_tokens", 0)
            s["total_cost"]   += step.get("cost_usd", 0)
            s["total_secs"]   += step.get("duration_seconds", 0)

    # Compute averages
    for a, s in agent_stats.items():
        calls = s["calls"] or 1
        s["error_rate"]      = round(s["errors"] / calls, 3)
        s["avg_tokens"]      = round(s["total_tokens"] / calls)
        s["avg_cost_usd"]    = round(s["total_cost"] / calls, 4)
        s["avg_secs"]        = round(s["total_secs"] / calls, 1)

    return {
        "run_count":          len(runs),
        "success_rate":       round(success_count / len(runs), 3),
        "avg_quality_score":  round(sum(r["quality_score"] for r in scored) / len(scored), 2)
                              if scored else None,
        "avg_cost_usd":       round(sum(r["total_cost_usd"] for r in runs) / len(runs), 4),
        "avg_total_secs":     round(sum(r["total_seconds"] for r in runs) / len(runs), 1),
        "agent_stats":        agent_stats,
        "recent_runs":        [
            {k: r[k] for k in ("run_id","timestamp","success","quality_score",
                                "total_cost_usd","total_seconds")}
            for r in runs
        ],
    }


# ── CSV history ───────────────────────────────────────────────────────────────
# system_history.csv — one file, append-only, never truncated.
# Two row types share the same columns; unused columns are left blank.
#
#   event_type = "run"         — produced by append_run_to_csv()
#   event_type = "improvement" — produced by append_improvement_to_csv()

_CSV_COLUMNS = [
    "event_type",         # "run" | "improvement"
    "timestamp",
    "trigger_id",         # groups related rows: run rows = own run_id;
                          #                      improvement rows = run_id that triggered analysis
    "task_group",         # user-supplied label (--group flag) grouping related runs
                          #   e.g. "UNICEF Phase 3", "CFO Brief Q1" — same value on improvement rows
    # ── run fields ──────────────────────────────────────────
    "run_id",
    "task",               # short preview for quick scanning
    "task_prompt",        # full task prompt, untruncated
    "project",
    "success",
    "quality_score",
    "total_cost_usd",
    "total_seconds",
    "total_input_tokens",
    "total_output_tokens",
    "agents_used",        # comma-separated list of agents that ran
    "step_errors",        # number of steps that returned status=error
    # ── improvement fields ───────────────────────────────────
    "agent",              # agent whose prompt was changed
    "finding",            # one-sentence description of the issue
    "improvement_status", # applied | blocked | validation_rejected | skipped_by_user | ...
    "note",               # extra context (rejection reason, editor note, etc.)
]


def _csv_path(path: Path | None = None) -> Path:
    return Path(path or SYSTEM_CSV)


def _ensure_csv_header(path: Path) -> None:
    """Write the header row if the file does not yet exist."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_CSV_COLUMNS).writeheader()


def append_run_to_csv(
    record: dict,
    csv_path: Path | None = None,
) -> None:
    """
    Append one run record (from save_run_record) to system_history.csv.
    Called automatically by save_run_record — no manual call needed.
    """
    path = _csv_path(csv_path)
    _ensure_csv_header(path)

    steps      = record.get("steps", [])
    agents     = ", ".join(dict.fromkeys(s["agent"] for s in steps if s.get("agent")))
    step_errors = sum(1 for s in steps if s.get("status") == "error")

    run_id = record.get("run_id", "")
    row = {
        "event_type":          "run",
        "timestamp":           record.get("timestamp", ""),
        "trigger_id":          run_id,   # self-referential — links improvement rows back here
        "task_group":          record.get("task_group") or "",
        "run_id":              run_id,
        "task":                record.get("task_preview", "")[:120],
        "task_prompt":         record.get("task_full", record.get("task_preview", "")),
        "project":             record.get("project") or "",
        "success":             record.get("success", ""),
        "quality_score":       record.get("quality_score") if record.get("quality_score") is not None else "",
        "total_cost_usd":      record.get("total_cost_usd", ""),
        "total_seconds":       record.get("total_seconds", ""),
        "total_input_tokens":  record.get("total_input_tokens", ""),
        "total_output_tokens": record.get("total_output_tokens", ""),
        "agents_used":         agents,
        "step_errors":         step_errors,
        # improvement columns blank
        "agent": "", "finding": "", "improvement_status": "", "note": "",
    }
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=_CSV_COLUMNS).writerow(row)


def append_improvement_to_csv(
    *,
    agent: str,
    finding: str,
    status: str,
    note: str = "",
    trigger_id: str = "",
    task_group: str = "",
    csv_path: Path | None = None,
) -> None:
    """
    Append one improvement event to system_history.csv.
    Called from run_self_improve._log() whenever a finding is resolved.
    Historical run rows are never modified — this is a new row appended after them.
    """
    path = _csv_path(csv_path)
    _ensure_csv_header(path)

    row = {
        "event_type":          "improvement",
        "timestamp":           time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "trigger_id":          trigger_id,
        "task_group":          task_group,
        # run columns blank
        "run_id": "", "task": "", "task_prompt": "", "project": "", "success": "",
        "quality_score": "", "total_cost_usd": "", "total_seconds": "",
        "total_input_tokens": "", "total_output_tokens": "",
        "agents_used": "", "step_errors": "",
        # improvement columns
        "agent":              agent,
        "finding":            finding,
        "improvement_status": status,
        "note":               note,
    }
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=_CSV_COLUMNS).writerow(row)
