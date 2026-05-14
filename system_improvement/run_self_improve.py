#!/usr/bin/env python3
"""
Self-improvement runner — interactive, human-in-the-loop only.

Audits the full agent system, presents each proposed prompt change to the
user for approval, and applies only what you explicitly approve.

Flow per finding:
  registry_auditor (Mode A)
    → prompt_engineer [improve mode] (proposes change)
    → human approval gate: [A]pprove / [R]eject (reason required) / [E]dit
        → Reject: reason fed back to prompt_engineer, retries (max 2)
        → Edit:   opens $EDITOR, optional note recorded
        → Approve/Edit: registry_auditor (IMPROVEMENT REVIEW) validates
          → APPROVE: write to disk, registry.reload()
          → REJECT:  logged as validation_rejected, not applied

System agents (manager, prompt_engineer, registry_auditor, workflow_planner,
are permanently blocked from automated modification.

All decisions are logged to: improvement_log.jsonl

Usage:
    python3 run_self_improve.py
    python3 run_self_improve.py --project qbus3600
    python3 run_self_improve.py --dry-run   # full run, no writes to disk
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

BASE = Path(__file__).parent.parent  # agent-system root
_SI = Path(__file__).parent       # system_improvement/
sys.path.insert(0, str(_SI))         # find agent_registry here
sys.path.insert(0, str(BASE))        # find runtime.* here when invoked standalone

from agent_registry import AgentRegistry
from runtime.dispatcher import run_step

# ── Paths ─────────────────────────────────────────────────────────────────────

PENDING_DIR = BASE / "System_logs" / "_pending"
LOG_PATH    = BASE / "System_logs" / "improvement_log.jsonl"
WORKING_DIR = BASE / "System_logs" / "_improve_workdir"

# ── Constants ─────────────────────────────────────────────────────────────────

SYSTEM_AGENTS = {
    "manager", "prompt_engineer", "registry_auditor", "workflow_planner",
}
MAX_RETRIES = 2   # prompt_engineer retries after rejection before giving up

# ── ANSI colours ──────────────────────────────────────────────────────────────

RED   = "\033[91m"
GREEN = "\033[92m"
CYAN  = "\033[96m"
BOLD  = "\033[1m"
DIM   = "\033[2m"
RESET = "\033[0m"


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


# ── Audit task builder ────────────────────────────────────────────────────────

def _build_audit_task(registry: AgentRegistry, *, deep: bool = False) -> str:
    """Build the full-system audit task for registry_auditor Mode A.

    By default (routine pass) the auditor sees descriptions only. Most
    findings (role overlaps, gaps, unreferenced agents, broken workflow
    references) can be detected from descriptions + workflow YAMLs alone,
    which keeps the audit cheap. The auditor is told it can Read individual
    `system_prompt.md` files on demand if a description-level finding warrants
    a closer look.

    Pass `deep=True` to include every agent's full system_prompt.md in the
    task body — needed for stale-description detection (where the prompt has
    drifted from the description). Costs ~5–10× more tokens.
    """
    def _pretty_path(p: Path) -> str:
        """Return path relative to BASE if possible; else as stored."""
        try:
            return str(p.resolve().relative_to(BASE.resolve()))
        except (ValueError, OSError):
            return str(p)

    agent_sections = []
    for name, cfg in sorted(registry.agents.items()):
        prompt_path = Path(cfg["_prompt_path"])
        section = (
            f"### {name}\n"
            f"**Config description:** {cfg.get('description', '(none)')}\n"
            f"**Prompt path:** `{_pretty_path(prompt_path)}`"
        )
        if deep:
            prompt = prompt_path.read_text().strip()
            section += f"\n\n**system_prompt.md:**\n```\n{prompt}\n```"
        agent_sections.append(section)
    agents_block = "\n\n---\n\n".join(agent_sections)

    wf_files: list[Path] = []
    wf_dir = BASE / "workflows"
    if wf_dir.is_dir():
        wf_files += sorted(wf_dir.glob("*.yaml"))
    proj_agents = BASE / "Employees" / "Projects-Specific Agents and Workflows"
    if proj_agents.is_dir():
        for proj_dir in sorted(proj_agents.iterdir()):
            pd = proj_dir / "workflows"
            if pd.exists():
                wf_files += sorted(pd.glob("*.yaml"))

    wf_sections = [
        f"### {f.stem}  (`{f.relative_to(BASE)}`)\n```yaml\n{f.read_text().strip()}\n```"
        for f in wf_files
    ]
    workflows_block = "\n\n---\n\n".join(wf_sections)

    mode_label = "deep audit (descriptions + full prompts)" if deep else "routine audit (descriptions only)"

    if deep:
        protocol_note = (
            "\n\nDeep mode: every agent's full system_prompt.md is inlined above. "
            "Read each prompt against its description to detect stale-description "
            "drift, in addition to the standard overlap/gap checks."
        )
    else:
        protocol_note = (
            "\n\n## Reading protocol (routine pass)\n\n"
            "You see descriptions only above. Follow the similarity-triggered "
            "drill-in rule from your system prompt:\n\n"
            "1. Scan the description list for overlap indicators (similar verbs, "
            "objects, or domain language; near-identical phrasing).\n"
            "2. For each suspect pair or cluster, **Read each agent's "
            "`system_prompt.md` using the `Prompt path` listed next to its "
            "description** before deciding whether the overlap is real.\n"
            "3. Also Read a prompt when a description sounds vague or when a "
            "workflow step's task does not match what the description claims.\n"
            "4. Do NOT bulk-read prompts. On a healthy system, expect to Read "
            "no more than ~20% of agents. If you'd want to Read more, recommend "
            "the user re-run with `--deep` and stop the routine pass."
        )

    return (
        f"Registry Audit — {mode_label}\n\n"
        "## All agents\n\n"
        f"{agents_block}\n\n"
        "---\n\n"
        "## All workflow YAMLs\n\n"
        f"{workflows_block}\n\n"
        "---\n\n"
        "## Instructions\n\n"
        "Audit every agent against every workflow it appears in.\n"
        "Flag: stale descriptions, role overlaps, gaps, agents not referenced\n"
        "in any workflow, workflow steps referencing non-existent agents.\n"
        f"Do not propose renaming any agent.{protocol_note}\n\n"
        "Save your full audit report to audit_report.md in the working directory.\n"
        "Then append the STRUCTURED_FINDINGS section as specified in your instructions."
    )


# ── Findings parser ───────────────────────────────────────────────────────────

def _parse_structured_findings(transcript: str) -> list[dict]:
    """Extract the STRUCTURED_FINDINGS YAML block from the audit transcript."""
    match = re.search(
        r"## STRUCTURED_FINDINGS\s*```ya?ml\s*(.*?)```",
        transcript,
        re.DOTALL,
    )
    if not match:
        return []
    try:
        data = yaml.safe_load(match.group(1))
        if isinstance(data, dict):
            return [f for f in data.get("findings", []) if isinstance(f, dict)]
    except Exception:
        pass
    return []


# ── Task builders ─────────────────────────────────────────────────────────────

def _build_improver_task(
    agent_name: str,
    current_prompt: str,
    finding: str,
    save_path: Path,
    rejection_reason: str | None = None,
) -> str:
    task = (
        f"IMPROVE EXISTING AGENT\n\n"
        f"Agent: {agent_name}\n\n"
        f"## Current system_prompt.md\n```\n{current_prompt}\n```\n\n"
        f"## Audit finding\n{finding}\n"
    )
    if rejection_reason:
        task += (
            f"\n## Rejection feedback from previous attempt\n"
            f"{rejection_reason}\n\n"
            f"Apply this feedback precisely. Do not make changes beyond what\n"
            f"the rejection feedback specifies.\n"
        )
    task += (
        f"\n## Save path\n{save_path}\n\n"
        f"Write the improved prompt to the save path and print it as a code block."
    )
    return task


def _build_mode_b_task(
    agent_name: str,
    config_content: str,
    new_prompt: str,
    roster: str,
) -> str:
    return (
        f"IMPROVEMENT REVIEW\n\n"
        f"An existing agent's system prompt has been revised by prompt_engineer\n"
        f"and approved by the system owner. Validate quality and scope before\n"
        f"it is written to disk.\n\n"
        f"## Revised agent: {agent_name}\n\n"
        f"config.json:\n```json\n{config_content}\n```\n\n"
        f"system_prompt.md (revised):\n```markdown\n{new_prompt}\n```\n\n"
        f"## Checks required\n"
        f"1. Prompt quality — clear role statement, input spec, methodology, output spec.\n"
        f"2. Scope preservation — core responsibility unchanged from config description.\n"
        f"3. Config description still accurate against revised prompt.\n\n"
        f"Do NOT check for naming overlap (this is an existing agent, not a new one).\n\n"
        f"## Registry (for scope reference only)\n{roster}"
    )


# ── Diff display ──────────────────────────────────────────────────────────────

def _show_diff(
    agent_name: str,
    finding: str,
    current: str,
    proposed: str,
    attempt: int,
):
    diff = list(difflib.unified_diff(
        current.splitlines(keepends=True),
        proposed.splitlines(keepends=True),
        fromfile=f"{agent_name}/current",
        tofile=f"{agent_name}/proposed",
        n=3,
    ))

    if attempt == 1:
        label = f"PROPOSED CHANGE — {agent_name}"
    else:
        label = f"REVISED CHANGE — {agent_name}  [attempt {attempt}/{MAX_RETRIES + 1}]"

    print(f"\n{'═' * 70}")
    print(f"{BOLD}{label}{RESET}")
    print(f"{DIM}Finding: {finding}{RESET}\n")

    if not diff:
        print(f"  {DIM}(no textual changes detected in proposed prompt){RESET}")
    else:
        print("─── Diff " + "─" * 61)
        for line in diff:
            if line.startswith(("+++", "---")):
                print(f"{CYAN}{line}{RESET}", end="")
            elif line.startswith("+"):
                print(f"{GREEN}{line}{RESET}", end="")
            elif line.startswith("-"):
                print(f"{RED}{line}{RESET}", end="")
            elif line.startswith("@@"):
                print(f"{CYAN}{line}{RESET}", end="")
            else:
                print(line, end="")
        print("\n" + "─" * 70)


# ── Extract prompt from transcript (fallback) ─────────────────────────────────

def _extract_prompt_from_transcript(transcript: str) -> str | None:
    """Pull content from the first markdown/plain code block in the transcript."""
    match = re.search(r"```(?:markdown)?\s*\n(.*?)```", transcript, re.DOTALL)
    return match.group(1).strip() if match else None


# ── Editor ────────────────────────────────────────────────────────────────────

def _edit_in_editor(path: Path) -> str:
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
    subprocess.call([editor, str(path)])
    return path.read_text()


# ── Decision log ──────────────────────────────────────────────────────────────

def _log(record: dict):
    entry = {**record, "ts": datetime.now(timezone.utc).isoformat()}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Mirror to system_history.csv if this entry has a final resolution
    status = record.get("final_status")
    if status:  # skip intermediate/partial log entries
        try:
            from runtime.telemetry import append_improvement_to_csv
            from runtime.improvement_trigger import read_trigger_session
            session    = read_trigger_session()
            trigger_id = session.get("trigger_run_id", "")
            task_group = session.get("task_group", "")
            append_improvement_to_csv(
                agent      = record.get("agent", ""),
                finding    = record.get("finding", ""),
                status     = status,
                note       = record.get("rejection_reason", record.get("note", "")),
                trigger_id = trigger_id,
                task_group = task_group,
            )
        except Exception:
            pass   # CSV write failure must never break the improvement flow


# ── Human approval gate ───────────────────────────────────────────────────────

def _human_gate(
    agent_name: str,
    finding: str,
    current: str,
    proposed: str,
    attempt: int,
) -> tuple[str, str]:
    """
    Display diff and collect user decision.

    Returns (decision, payload) where decision is one of:
      'approve'   — payload is ''
      'reject'    — payload is the rejection reason (always non-empty)
      'edit'      — payload is ''  (edit handled by caller)
      'skip_all'  — payload is ''
    """
    _show_diff(agent_name, finding, current, proposed, attempt)
    print(
        f"\n{BOLD}[A]{RESET}pprove   "
        f"{BOLD}[R]{RESET}eject   "
        f"{BOLD}[E]{RESET}dit in editor   "
        f"{BOLD}[S]{RESET}kip all remaining"
    )

    while True:
        raw = input("Decision: ").strip().lower()

        if raw in ("a", "approve"):
            return "approve", ""

        if raw in ("s", "skip", "skip_all"):
            return "skip_all", ""

        if raw in ("r", "reject"):
            print(
                f"\n{BOLD}Rejection reason{RESET} "
                f"(required — fed back to prompt_engineer):"
            )
            reason = input("> ").strip()
            while not reason:
                print("  Reason cannot be empty. Please explain what needs to change.")
                reason = input("> ").strip()
            return "reject", reason

        if raw in ("e", "edit"):
            return "edit", ""

        print("  Enter A, R, E, or S.")


# ── Core loop for one finding ─────────────────────────────────────────────────

def _run_one_finding(
    finding: dict,
    registry: AgentRegistry,
    dry_run: bool,
) -> dict:
    agent_name   = finding.get("agent", "unknown")
    finding_text = finding.get("finding", "(no finding text)")
    confidence   = finding.get("confidence", "medium")
    tier         = 3 if agent_name in SYSTEM_AGENTS else 2

    record: dict = {
        "agent":      agent_name,
        "finding":    finding_text,
        "confidence": confidence,
        "tier":       tier,
        "decision":   None,
        "retries":    0,
        "final_status": None,
    }

    # ── Tier 3: system agents are permanently blocked ─────────────────────────
    if tier == 3:
        print(f"\n  {RED}[BLOCKED]{RESET}  {agent_name} — system agent, permanently protected")
        record["decision"]     = "blocked"
        record["final_status"] = "blocked"
        _log(record)
        return record

    # ── Load current prompt and config ────────────────────────────────────────
    cfg = registry.agents.get(agent_name)
    if not cfg:
        print(f"\n  {RED}[SKIP]{RESET}  {agent_name} — not found in registry")
        record["final_status"] = "agent_not_found"
        _log(record)
        return record

    prompt_path    = Path(cfg["_prompt_path"])
    current_prompt = prompt_path.read_text()
    config_path    = prompt_path.parent / "config.json"
    config_content = config_path.read_text() if config_path.exists() else "{}"

    # ── Pending directory for proposed file ───────────────────────────────────
    pending       = PENDING_DIR / agent_name
    pending.mkdir(parents=True, exist_ok=True)
    proposed_path = pending / "system_prompt.proposed.md"
    (pending / "finding.txt").write_text(finding_text)

    # ── Roster string for Mode B ──────────────────────────────────────────────
    roster = "\n".join(
        f"  {n}: {c.get('description', '')}"
        for n, c in sorted(registry.agents.items())
    )

    rejection_reason: str | None = None

    for attempt in range(1, MAX_RETRIES + 2):   # 1, 2, 3

        # ── Run prompt_engineer (improve mode) ─────────────────────────────────────────
        label = "── prompt_engineer [improve]" if attempt == 1 else f"── prompt_engineer [improve] (retry {attempt - 1}/{MAX_RETRIES})"
        print(f"\n  {label} ──")

        improver_task = _build_improver_task(
            agent_name, current_prompt, finding_text,
            proposed_path, rejection_reason,
        )
        try:
            improver_cfg    = registry.load_agent("prompt_engineer")
            improver_result = run_step(improver_cfg, improver_task, WORKING_DIR, dry_run=dry_run)
        except Exception as e:
            print(f"  {RED}[error]{RESET} prompt_engineer: {e}")
            record["final_status"] = "improver_error"
            _log(record)
            return record

        # ── Guard: ensure prompt_engineer only wrote to the expected path ────────
        unexpected = [
            p for p in PENDING_DIR.rglob("*")
            if p.is_file()
            and p != proposed_path
            and p != pending / "finding.txt"
            and p.stat().st_mtime > (time.time() - 30)
        ]
        if unexpected:
            print(f"  {RED}[guard]{RESET} prompt_engineer wrote to unexpected path(s):")
            for u in unexpected:
                print(f"    {u}")
                u.unlink()   # remove stray files
            print(f"  Stray files removed. Proceeding with pending output only.")

        # ── Read proposed content (file first, transcript fallback) ───────────
        if proposed_path.exists():
            proposed_prompt = proposed_path.read_text().strip()
        else:
            proposed_prompt = _extract_prompt_from_transcript(improver_result.transcript) or ""

        if not proposed_prompt:
            print(f"  {RED}[error]{RESET} prompt_engineer produced no output")
            record["final_status"] = "no_output"
            _log(record)
            return record

        # ── Dry-run: show diff and skip the rest ──────────────────────────────
        if dry_run:
            _show_diff(agent_name, finding_text, current_prompt, proposed_prompt, attempt)
            print(f"\n  {DIM}[dry-run] approval gate and write skipped{RESET}")
            record["decision"]     = "dry_run"
            record["final_status"] = "dry_run"
            _log(record)
            return record

        # ── Human approval gate ───────────────────────────────────────────────
        decision, payload = _human_gate(
            agent_name, finding_text, current_prompt, proposed_prompt, attempt
        )
        record["retries"] = attempt - 1

        # ── Skip all ──────────────────────────────────────────────────────────
        if decision == "skip_all":
            record["decision"]     = "skipped"
            record["final_status"] = "skipped_by_user"
            _log(record)
            return record

        # ── Reject ────────────────────────────────────────────────────────────
        if decision == "reject":
            record["decision"]        = "rejected"
            record["rejection_reason"] = payload
            if attempt > MAX_RETRIES:
                print(f"\n  {RED}[unresolved]{RESET} max retries ({MAX_RETRIES}) reached for {agent_name}")
                record["final_status"] = "unresolved"
                _log(record)
                return record
            rejection_reason = payload
            print(f"\n  Retrying with your feedback...")
            continue

        # ── Edit ──────────────────────────────────────────────────────────────
        if decision == "edit":
            proposed_path.write_text(proposed_prompt)
            print(f"\n  Opening {proposed_path.name} in editor...")
            proposed_prompt = _edit_in_editor(proposed_path)
            # Show diff between original and what the user edited
            _show_diff(agent_name, finding_text, current_prompt, proposed_prompt, attempt)
            print(f"\n{BOLD}Note{RESET} (optional — what did you change? press Enter to skip):")
            note = input("> ").strip()
            if note:
                record["edit_note"] = note
            record["decision"] = "edited"

        # ── Approve (direct or post-edit) ─────────────────────────────────────
        if decision == "approve":
            record["decision"] = "approved"

        # ── registry_auditor Mode B: IMPROVEMENT REVIEW ───────────────────────
        print(f"\n  ── registry_auditor (IMPROVEMENT REVIEW) ──")
        mode_b_task = _build_mode_b_task(
            agent_name, config_content, proposed_prompt, roster
        )
        try:
            auditor_cfg  = registry.load_agent("registry_auditor")
            audit_result = run_step(auditor_cfg, mode_b_task, WORKING_DIR)
        except Exception as e:
            print(f"  {RED}[error]{RESET} registry_auditor: {e}")
            record["final_status"] = "auditor_error"
            _log(record)
            return record

        # Parse verdict — REJECT takes priority over APPROVE
        t_upper = audit_result.transcript.upper()
        verdict = "REJECT" if "REJECT" in t_upper else ("APPROVE" if "APPROVE" in t_upper else "REJECT")

        if verdict == "REJECT":
            for line in audit_result.transcript.splitlines():
                if line.strip().lower().startswith("reason:"):
                    print(f"  {RED}[validation rejected]{RESET} {line.split(':', 1)[1].strip()}")
                    break
            else:
                print(f"  {RED}[validation rejected]{RESET} see log for details")
            record["final_status"]    = "validation_rejected"
            record["auditor_verdict"] = "REJECT"
            _log(record)
            return record

        # ── Write to disk and reload ──────────────────────────────────────────
        print(f"  {GREEN}✓ Validated{RESET} — writing to disk")
        prompt_path.write_text(proposed_prompt)
        registry.reload()
        print(f"  {GREEN}✓ Registry reloaded{RESET}")

        record["final_status"]    = "applied"
        record["auditor_verdict"] = "APPROVE"
        _log(record)
        return record

    # Exceeded retries without resolving (shouldn't reach here normally)
    record["final_status"] = "unresolved"
    _log(record)
    return record



# ── Callable entry point (importable without argparse conflicts) ──────────────

def run(project: str | None = None, dry_run: bool = False, deep: bool = False) -> None:
    """
    Core system-improvement routine.  Callable directly from other modules
    (e.g. run_pipeline.py) without argparse conflicts.

    Parameters
    ----------
    project : str | None  — project ID; includes project-specific agents
    dry_run : bool        — run full audit + show diffs, but write nothing
    deep    : bool        — include every agent's full system_prompt.md in the
                            audit task body. Routine pass (deep=False) sends
                            descriptions only and lets the auditor Read full
                            prompts on demand. Pass deep=True when you suspect
                            stale-description drift.
    """
    _load_dotenv()
    WORKING_DIR.mkdir(parents=True, exist_ok=True)

    registry = AgentRegistry(base_dir=BASE, project_id=project)

    print(f"\n{'═' * 70}")
    print(f"{BOLD}SYSTEM-IMPROVE RUN{RESET}")
    print(f"  Project:  {project or '(general agents only)'}")
    print(f"  Agents:   {len(registry.agents)}")
    print(f"  Mode:     {'deep (full prompts)' if deep else 'routine (descriptions only)'}")
    print(f"  Log:      {LOG_PATH}")
    if dry_run:
        print(f"  {DIM}Dry-run: no files will be written{RESET}")
    print(f"{'═' * 70}\n")

    # ── Phase 1: full audit ───────────────────────────────────────────────────
    label = "deep audit — descriptions + full prompts" if deep else "routine audit — descriptions only, drill-in on demand"
    print(f"── registry_auditor (Mode A — {label}) ──")

    audit_task = _build_audit_task(registry, deep=deep)
    try:
        auditor_cfg  = registry.load_agent("registry_auditor")
        audit_result = run_step(auditor_cfg, audit_task, WORKING_DIR)
    except Exception as e:
        print(f"\n{RED}[fatal]{RESET} registry_auditor failed: {e}")
        sys.exit(1)

    report_path = WORKING_DIR / "audit_report.md"
    if report_path.exists():
        print(f"  Audit report saved: {report_path}")
    print(f"  Tokens: in={audit_result.input_tokens:,}  out={audit_result.output_tokens:,}")

    findings = _parse_structured_findings(audit_result.transcript)

    actionable = [
        f for f in findings
        if f.get("type") in ("prompt_rewrite",)
    ]
    description_only = [
        f for f in findings
        if f.get("type") == "description_update"
    ]

    print(f"\n  Total findings:     {len(findings)}")
    print(f"  Prompt rewrites:    {len(actionable)}")
    if description_only:
        print(
            f"  Description-only:   {len(description_only)}  "
            f"{DIM}(manual — edit config.json description field directly){RESET}"
        )
        for d in description_only:
            print(f"    {DIM}• {d.get('agent')}: {d.get('finding')}{RESET}")

    if not actionable:
        print(f"\n{GREEN}No prompt rewrites needed. System is clean.{RESET}")
        return  # clean exit — no sys.exit so callers stay alive

    # ── Phase 2: human approval loop ─────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print(f"Presenting {len(actionable)} prompt rewrite(s) for your review.\n")

    counts = {"applied": 0, "rejected": 0, "blocked": 0,
              "skipped": 0, "errors": 0, "dry_run": 0}
    skip_remaining = False

    for finding in actionable:
        if skip_remaining:
            print(f"  {DIM}[skipped] {finding.get('agent')}{RESET}")
            counts["skipped"] += 1
            continue

        result = _run_one_finding(finding, registry, dry_run)
        status = result.get("final_status", "")

        if status == "applied":
            counts["applied"] += 1
        elif status == "blocked":
            counts["blocked"] += 1
        elif status == "skipped_by_user":
            counts["skipped"] += 1
            skip_remaining = True
        elif status == "dry_run":
            counts["dry_run"] += 1
        elif status in ("unresolved", "validation_rejected",
                        "improver_error", "no_output", "auditor_error"):
            counts["errors"] += 1
        else:
            counts["rejected"] += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═' * 70}")
    print(f"{BOLD}RUN COMPLETE{RESET}")
    if dry_run:
        print(f"  {DIM}(dry-run — no changes written){RESET}")
    print(f"  {GREEN}Applied:   {counts['applied']}{RESET}")
    print(f"  {RED}Unresolved:{counts['errors']}{RESET}  (validation failures, max retries)")
    print(f"  Rejected:  {counts['rejected']}")
    print(f"  Blocked:   {counts['blocked']}  (system agents)")
    print(f"  Skipped:   {counts['skipped']}")
    if dry_run:
        print(f"  Previewed: {counts['dry_run']}")
    print(f"\n  Log: {LOG_PATH}")
    print(f"{'═' * 70}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    """Thin argparse wrapper — delegates entirely to run()."""
    ap = argparse.ArgumentParser(
        description="Interactive system-improvement runner — human approval required for all changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--project", default=None,
                    help="Project ID — includes project-specific agents in the audit")
    ap.add_argument("--dry-run", action="store_true",
                    help="Run full audit and show diffs, but do not write any files to disk")
    ap.add_argument("--deep", action="store_true",
                    help="Include every agent's full system_prompt.md in the audit task body. "
                         "Costs ~5-10x more tokens. Use when you suspect stale-description drift; "
                         "the routine pass sends descriptions only and lets the auditor Read prompts on demand.")
    args = ap.parse_args()
    run(project=args.project, dry_run=args.dry_run, deep=args.deep)


if __name__ == "__main__":
    main()
