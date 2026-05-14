#!/usr/bin/env python3
"""
Workflow Engine
Resolves and executes agent workflows.

Two execution modes:
  • dispatch (default if claude-agent-sdk + ANTHROPIC_API_KEY are present):
      each step runs as a real Claude API call via runtime/dispatcher.run_step
  • queue (fallback, also when --dry-run): records intended calls without
      contacting the API. Useful for sanity-checking the workflow YAML.

Looks for a workflow YAML in projects/<project_id>/workflows/ first,
then falls back to the shared workflows/ directory.
"""

import os
import sys
import time
import json
import yaml
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait as _futures_wait

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "system_improvement"))  # agent_registry lives here
from agent_registry import AgentRegistry, ProjectContext

try:
    from runtime.dispatcher import run_step, DispatchResult, DispatcherUnavailable
    DISPATCH_AVAILABLE = True
except ImportError:
    DISPATCH_AVAILABLE = False


class WorkflowDefinition:
    @classmethod
    def from_yaml(cls, filepath: Path):
        with open(filepath) as f:
            data = yaml.safe_load(f)
        return cls(data, source=str(filepath))

    def __init__(self, data: dict, source: str = ""):
        self.name = data.get("name", "unnamed")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0")
        self.steps = data.get("steps", [])
        self.source = source

    def __repr__(self):
        return f"<WorkflowDefinition name={self.name} steps={len(self.steps)} source={self.source}>"


class WorkflowEngine:
    PROJECT_AGENTS_DIR = Path("Employees") / "Projects-Specific Agents and Workflows"
    SHARED_WORKFLOWS_DIR = Path("workflows")

    def __init__(self, registry: AgentRegistry, base_dir: Path = None):
        self.registry = registry
        self.base_dir = base_dir or Path(__file__).parent.parent

    # ── Planner helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_steps_from_text(text: str) -> list:
        """Extract a YAML step list from an agent transcript.

        Accepts three formats (tried in order):
          1. A fenced ```yaml ... ``` block containing a list or {steps: [...]}
          2. The entire text parsed as YAML list or {steps: [...]}
          3. Raises ValueError if neither works.
        """
        import re

        def _parse(raw: str) -> list:
            data = yaml.safe_load(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "steps" in data:
                return data["steps"]
            raise ValueError(f"parsed YAML is {type(data).__name__}, expected list or {{steps: [...]}}")

        # Try fenced block first
        match = re.search(r"```(?:yaml)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return _parse(match.group(1))
            except Exception:
                pass

        # Fall back to full text
        return _parse(text)

    def _resolve_planner_save_path(self, workflow_name: str) -> Path:
        """Return the path where the planner should save the generated workflow YAML.

        Prefers the project workflows dir; falls back to the shared workflows dir.
        """
        if self.registry.project_id:
            project_wf_dir = (
                self.base_dir / self.PROJECT_AGENTS_DIR / self.registry.project_id / "workflows"
            )
            project_wf_dir.mkdir(parents=True, exist_ok=True)
            return project_wf_dir / f"{workflow_name}.yaml"

        shared_dir = self.base_dir / self.SHARED_WORKFLOWS_DIR
        shared_dir.mkdir(parents=True, exist_ok=True)
        return shared_dir / f"{workflow_name}.yaml"

    # ── Workflow resolution ───────────────────────────────────────────────────

    def load_workflow(self, name: str) -> WorkflowDefinition:
        """
        Resolve a workflow by name.
        Search order:
          1. projects/<project_id>/workflows/<name>.yaml  (project-specific)
          2. workflows/<name>.yaml                        (shared)
        """
        candidates = []

        if self.registry.project_id:
            project_wf = (
                self.base_dir / self.PROJECT_AGENTS_DIR / self.registry.project_id
                / "workflows" / f"{name}.yaml"
            )
            candidates.append(project_wf)

        candidates.append(self.base_dir / self.SHARED_WORKFLOWS_DIR / f"{name}.yaml")

        for path in candidates:
            if path.exists():
                return WorkflowDefinition.from_yaml(path)

        searched = "\n  ".join(str(c) for c in candidates)
        raise FileNotFoundError(
            f"Workflow '{name}' not found. Searched:\n  {searched}"
        )

    def list_workflows(self) -> list:
        """Return all available workflow names visible to this engine."""
        seen = {}

        if self.registry.project_id:
            project_dir = (
                self.base_dir / self.PROJECT_AGENTS_DIR / self.registry.project_id / "workflows"
            )
            if project_dir.exists():
                for f in sorted(project_dir.glob("*.yaml")):
                    seen[f.stem] = f"project:{self.registry.project_id}"

        shared_dir = self.base_dir / self.SHARED_WORKFLOWS_DIR
        if shared_dir.exists():
            for f in sorted(shared_dir.glob("*.yaml")):
                if f.stem not in seen:
                    seen[f.stem] = "general"

        return [{"name": k, "source": v} for k, v in seen.items()]

    # ── Execution ─────────────────────────────────────────────────────────────

    def execute(
        self,
        workflow: WorkflowDefinition,
        context: ProjectContext,
        initial_inputs: dict = None,
        *,
        working_dir=None,
        dry_run: bool = False,
        resume_from: str = None,
        state_path=None,
        log_dir=None,
        on_step_done=None,
        max_parallel: int = 4,
    ) -> dict:
        """Run a workflow.

        working_dir: task sandbox — where agents read/write task files.
                     Can be any path on disk (e.g. ~/Documents/my_project/outputs).
        log_dir:     where API logs (_agent_logs/) and workflow state are written.
                     Defaults to SYSTEM_DIR inside the agent-system folder so
                     system files never mix with task output.
        dry_run:     don't call the API, just print resolved prompts
        resume_from: skip steps until this step name; restore prior artefacts
                     from state_path if provided. Forces max_parallel=1.
        state_path:  override for _workflow_state.json location
        on_step_done: optional callback fn(step_name, result_dict). Called from
                     the main thread, so does not need to be thread-safe.
        max_parallel: maximum concurrent agent steps (default 4). Steps run as
                     soon as their input_keys are all satisfied. Steps with
                     parallel_safe: false in the YAML, plus all planner and
                     dynamic step types, run as barriers (drained alone).
        """
        from runtime.telemetry import SYSTEM_DIR, AGENT_LOGS_DIR
        working_dir = Path(working_dir or os.getcwd())
        _log_dir    = Path(log_dir) if log_dir else AGENT_LOGS_DIR
        if state_path is None:
            state_path = SYSTEM_DIR / "_workflow_state.json"
        else:
            state_path = Path(state_path)

        # Resume: load prior artefacts from disk if present
        if resume_from and state_path.exists():
            prior = ProjectContext.load_from_disk(state_path, registry=self.registry)
            if prior is not None:
                context.shared_memory.update(prior.shared_memory)
                context.logs.extend(prior.logs)
                print(f"[engine] resumed state from {state_path} "
                      f"({len(prior.shared_memory)} artefacts, {len(prior.logs)} prior steps)")

        if initial_inputs:
            for key, value in initial_inputs.items():
                context.save_artifact(key, value)

        # Resume + parallelism is too risky to mix — force sequential when resuming.
        if resume_from and max_parallel > 1:
            print(f"[engine] --resume-from set; forcing max_parallel=1")
            max_parallel = 1
        max_parallel = max(1, int(max_parallel))

        execution_log: list[dict] = []
        pending: list[dict]       = list(workflow.steps)
        in_flight: dict           = {}    # step_name -> Future
        completed: set            = set() # step names that ran (any terminal status)
        cancelled: set            = set() # step names cancelled because an upstream failed

        # ── Helpers ──────────────────────────────────────────────────────────────

        def _input_keys_ready(step: dict) -> bool:
            return all(k in context.shared_memory for k in step.get("input_keys", []))

        def _is_barrier(step: dict) -> bool:
            """Barriers run alone — no other step in flight at the same time.
            Planner and dynamic steps mutate the queue; parallel_safe=false is
            an explicit author opt-out (e.g. file-locking concerns)."""
            return (
                step.get("type", "agent") in ("planner", "dynamic")
                or step.get("parallel_safe", True) is False
            )

        def _cascade_cancel(failed_step: dict) -> None:
            """Mark queued steps that transitively depend on the failed step's
            output_key as cancelled, and drop them from `pending` so the
            scheduler doesn't keep re-considering them. Steps that don't depend
            on the failure stay queued and will run as soon as their inputs
            are ready."""
            nonlocal pending
            failed_key = failed_step.get("output_key")
            if not failed_key:
                return
            cancelled_keys = {failed_key}
            changed = True
            while changed:
                changed = False
                for s in pending:
                    if s["name"] in cancelled or s["name"] in completed:
                        continue
                    if s["name"] == failed_step["name"]:
                        continue
                    if any(k in cancelled_keys for k in s.get("input_keys", [])):
                        cancelled.add(s["name"])
                        if s.get("output_key"):
                            cancelled_keys.add(s["output_key"])
                        rec = {"step": s["name"], "status": "cancelled_upstream_failure",
                               "upstream": failed_step["name"]}
                        execution_log.append(rec)
                        if on_step_done:
                            on_step_done(s["name"], rec)
                        changed = True
            # Drop cancelled steps from pending so the scheduler terminates
            pending = [s for s in pending if s["name"] not in cancelled]

        # ── Resume: skip steps before the resume target ──────────────────────────

        if resume_from:
            skip_idx = next((i for i, s in enumerate(pending) if s["name"] == resume_from), None)
            if skip_idx is None:
                print(f"[engine] resume target '{resume_from}' not found in workflow")
            else:
                for s in pending[:skip_idx]:
                    rec = {"step": s["name"], "status": "skipped_resume"}
                    execution_log.append(rec)
                    completed.add(s["name"])
                    if on_step_done:
                        on_step_done(s["name"], rec)
                pending = pending[skip_idx:]

        # ── Scheduler loop ───────────────────────────────────────────────────────

        with ThreadPoolExecutor(max_workers=max_parallel) as pool:
            while pending or in_flight:
                # 1. Try to submit ready steps (subject to barriers and concurrency)
                made_progress = False
                for step in list(pending):
                    name = step["name"]
                    if name in in_flight or name in completed or name in cancelled:
                        continue
                    if not _input_keys_ready(step):
                        continue

                    # Dynamic steps are pure queue mutations — handle inline (no API call)
                    if step.get("type") == "dynamic":
                        if in_flight:
                            continue   # barrier: wait for in-flight to drain
                        source_key = step.get("input_keys", ["planned_steps"])[0]
                        raw = context.get_artifact(source_key)
                        if raw is None:
                            rec = {"step": name, "status": "error",
                                   "error": f"dynamic step: artifact '{source_key}' not found in context"}
                            execution_log.append(rec)
                            if on_step_done: on_step_done(name, rec)
                            completed.add(name)
                            pending = [s for s in pending if s["name"] != name]
                            _cascade_cancel(step)
                            made_progress = True
                            break
                        try:
                            injected = yaml.safe_load(raw) if isinstance(raw, str) else raw
                            if not isinstance(injected, list):
                                raise ValueError("expected a list of step dicts")
                            pending = injected + [s for s in pending if s["name"] != name]
                            rec = {"step": name, "status": "expanded",
                                   "injected_steps": len(injected)}
                            execution_log.append(rec)
                            if on_step_done: on_step_done(name, rec)
                            completed.add(name)
                            made_progress = True
                            break  # restart scheduling with new pending list
                        except Exception as e:
                            rec = {"step": name, "status": "error",
                                   "error": f"dynamic step: could not parse planned steps — {e}"}
                            execution_log.append(rec)
                            if on_step_done: on_step_done(name, rec)
                            completed.add(name)
                            pending = [s for s in pending if s["name"] != name]
                            if not step.get("continue_on_error"):
                                _cascade_cancel(step)
                            made_progress = True
                            break

                    # Barrier handling: only submit alone
                    if _is_barrier(step):
                        if in_flight:
                            continue   # wait for current in-flight to drain
                        future = pool.submit(self._run_one_step,
                                              step, context, working_dir, _log_dir, dry_run)
                        in_flight[name] = future
                        made_progress = True
                        break          # don't co-submit anything else with a barrier

                    # Regular agent step
                    if len(in_flight) >= max_parallel:
                        break          # full
                    future = pool.submit(self._run_one_step,
                                          step, context, working_dir, _log_dir, dry_run)
                    in_flight[name] = future
                    made_progress = True

                # 2. If nothing is in flight and we made no progress, we're stuck or done
                if not in_flight:
                    if pending:
                        stuck = [s["name"] for s in pending
                                 if s["name"] not in completed and s["name"] not in cancelled]
                        if stuck and not made_progress:
                            print(f"[engine] WARNING: cannot make progress — pending steps with unmet input_keys: {stuck}")
                            for n in stuck:
                                rec = {"step": n, "status": "error",
                                       "error": "input_keys never satisfied"}
                                execution_log.append(rec)
                                if on_step_done: on_step_done(n, rec)
                                completed.add(n)
                            break
                    if not pending:
                        break
                    continue   # next iteration may submit something now that pending shrank

                # 3. Wait for at least one in-flight to finish
                done, _ = _futures_wait(list(in_flight.values()), return_when=FIRST_COMPLETED)
                for fut in done:
                    name = next(n for n, f in in_flight.items() if f is fut)
                    step = next(s for s in pending if s["name"] == name)
                    in_flight.pop(name)

                    try:
                        rec, artefact = fut.result()
                    except Exception as e:
                        rec = {"step": name, "status": "error",
                               "error": f"worker exception: {e}"}
                        artefact = None

                    # Persist artefact under main-thread control
                    if rec.get("status") in ("ok", "dry_run") and step.get("output_key"):
                        if artefact is not None:
                            context.save_artifact(step["output_key"], artefact)

                    execution_log.append(rec)
                    if on_step_done:
                        on_step_done(name, rec)

                    # Planner step injection — parse output for new steps
                    if step.get("type") == "planner" and rec.get("status") in ("ok", "dry_run"):
                        inject_key = step.get("output_key", f"{name}_steps")
                        raw = context.get_artifact(inject_key) or artefact or ""
                        try:
                            parsed = self._extract_steps_from_text(raw)
                            # Insert at the front of pending so they run before anything queued behind
                            pending = parsed + [s for s in pending if s["name"] != name]
                            rec["injected_steps"] = len(parsed)
                            print(f"[engine] planner '{name}' injected {len(parsed)} step(s)")
                        except Exception as e:
                            rec["planner_parse_error"] = str(e)
                            print(f"[engine] WARNING: planner '{name}' output could not be parsed as steps — {e}")

                    completed.add(name)
                    pending = [s for s in pending if s["name"] != name]

                    if rec.get("status") in ("ok", "dry_run"):
                        context.logs.append(rec)
                        context.save_to_disk(state_path)
                    else:
                        if not step.get("continue_on_error"):
                            _cascade_cancel(step)

        return {
            "success": all(
                r["status"] in ("ok", "dry_run", "skipped_resume", "queued", "expanded")
                for r in execution_log
            ),
            "workflow":     workflow.name,
            "project":      context.project_id,
            "working_dir":  str(working_dir),
            "state_path":   str(state_path),
            "steps":        execution_log,
            "artifacts":    context.shared_memory,
            "max_parallel": max_parallel,
        }

    # ── Per-step worker (thread-safe) ─────────────────────────────────────────────

    def _run_one_step(
        self,
        step: dict,
        context: ProjectContext,
        working_dir: Path,
        log_dir: Path,
        dry_run: bool,
    ) -> tuple[dict, str | None]:
        """Run a single agent step. Returns (rec_dict, artefact_value).

        Thread-safe: does not mutate context, execution_log, or pending. The
        scheduler stores the artefact in context.shared_memory under main-thread
        control after this returns.
        """
        step_name = step["name"]
        step_type = step.get("type", "agent")
        agent_name = step.get("agent")

        if not agent_name:
            return {"step": step_name, "status": "error",
                    "error": "step has no 'agent' field"}, None

        try:
            agent_config = self.registry.load_agent(
                agent_name, overrides=step.get("parameters")
            )
        except ValueError as e:
            return {"step": step_name, "status": "error", "error": str(e)}, None

        # Snapshot upstream artefacts (read-only across threads — dict reads are safe)
        inputs = {k: context.get_artifact(k) for k in step.get("input_keys", [])}

        task_text = step["task"]
        if step_type == "planner":
            workflow_name = step.get("workflow_name") or f"generated_{step_name}"
            save_path = self._resolve_planner_save_path(workflow_name)
            task_text = (
                f"{task_text}\n\n"
                f"save_path: {save_path}\n"
                f"workflow_name: {workflow_name}"
            )

        mode = "dispatch"
        if not DISPATCH_AVAILABLE or dry_run:
            mode = "dry_run" if dry_run else "queue"

        if mode == "queue":
            return {"step": step_name, "agent": agent_name,
                    "source": agent_config.get("_source", "unknown"),
                    "status": "queued",
                    "note": "claude-agent-sdk not installed; install + set ANTHROPIC_API_KEY to dispatch."}, None

        t0 = time.time()
        try:
            res: DispatchResult = run_step(
                agent_config, task_text, working_dir,
                inputs=inputs, dry_run=(mode == "dry_run"),
                log_dir=log_dir,
            )
        except DispatcherUnavailable as e:
            return {"step": step_name, "agent": agent_name,
                    "status": "error", "error": f"dispatcher unavailable: {e}"}, None
        except Exception as e:
            return {"step": step_name, "agent": agent_name,
                    "status": "error", "error": str(e),
                    "duration_seconds": round(time.time() - t0, 2)}, None

        rec = {
            "step": step_name, "agent": agent_name,
            "source": agent_config.get("_source", "unknown"),
            "status": res.status,
            "duration_seconds": round(res.duration_seconds, 2),
            "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens,
            "log_path": res.log_path,
            "mode": mode,
            **({"step_type": step_type} if step_type != "agent" else {}),
        }
        if res.error:
            rec["error"] = res.error

        artefact = res.transcript if step.get("output_key") else None
        return rec, artefact


if __name__ == "__main__":
    base = Path(__file__).parent.parent
    project = sys.argv[1] if len(sys.argv) > 1 else None
    workflow_name = sys.argv[2] if len(sys.argv) > 2 else "data_analysis_report_pipeline"

    registry = AgentRegistry(base_dir=base, project_id=project)
    engine = WorkflowEngine(registry, base_dir=base)

    print(registry.describe())
    print()
    print("Available workflows:")
    for wf in engine.list_workflows():
        print(f"  [{wf['source']}] {wf['name']}")
    print()

    wf = engine.load_workflow(workflow_name)
    print(f"Loaded: {wf}")
    print(f"Dispatch available: {DISPATCH_AVAILABLE}")
