# Agent system map — for AI agents working on this codebase

Read this file first. It tells you where things live so you don't read files
speculatively. Keep this file under 200 lines; if it grows beyond that, trim
it back rather than letting it drift into prose.

## Which docs to read

| File              | When to read it |
|-------------------|---|
| `AGENTS.md`       | Always — this is your map |
| `README.md`       | Only if you need conceptual context the map doesn't cover, or you've been asked to update README itself |
| `SETUP.md`        | Only if explicitly asked to update setup instructions |
| `USER_GUIDE.txt`  | Only if explicitly asked to update the user guide |

`README.md`, `SETUP.md`, and `USER_GUIDE.txt` are written for humans. They
overlap heavily and contain narrative prose. Loading them speculatively wastes
tokens — every fact you need to operate is in this file or in the source.

---

## Top-level layout

```
agent-system/
├── cli/                 ← entry-point scripts; always invoke from here
├── runtime/             ← dispatcher, telemetry, notifier, improvement_trigger
├── workflows/           ← shared workflow YAMLs + workflow_engine.py
├── system_improvement/  ← agent_registry.py + self-improvement runners
├── Employees/           ← agent definitions (general + project-specific)
├── outputs/             ← deliverables, one subfolder per task
├── System_logs/         ← all runtime logs and state (never inside working_dir)
├── Others/              ← LICENSE, requirements.txt, deploy scripts
├── .env, .env.example
└── README.md, SETUP.md, USER_GUIDE.txt, AGENTS.md
```

Folders matching `*_legacy_skel/`, the root-level `_system/`, and root-level
`__pycache__/` are leftover and inert. Ignore them.

---

## Entry points

```
python3 cli/run_pipeline.py           ← main; --task | --workflow | --system-improve
python3 cli/run_feedback_loop.py      ← run-task + evaluation + improvement loop
python3 cli/check_status.py           ← read-only health snapshot (no API calls)
python3 cli/check_status.py --short   ← one-line summary

python3 system_improvement/run_self_improve.py            ← routine audit (descriptions only)
python3 system_improvement/run_self_improve.py --deep     ← deep audit (full prompts; ~5x cost)
python3 system_improvement/run_registry_audit.py
python3 system_improvement/agent_registry.py [project_id] ← dump roster
```

There are no `.py` files at the agent-system root. Never invoke one from the root.

---

## Path constants (the most-asked question)

If asked to relocate any runtime/log file, edit the constant — do NOT search
for the literal filename across the codebase.

| What                            | Defined in                                  | Resolves to |
|---------------------------------|---------------------------------------------|---|
| `BASE`                          | runtime/telemetry.py                        | `agent-system/` |
| `SYSTEM_DIR`                    | runtime/telemetry.py                        | `System_logs/` |
| `RUNS_HISTORY`                  | runtime/telemetry.py                        | `System_logs/runs_history.jsonl` |
| `SYSTEM_CSV`                    | runtime/telemetry.py                        | `System_logs/system_history.csv` |
| `AGENT_LOGS_DIR`                | runtime/telemetry.py                        | `System_logs/_agent_logs/` |
| `WORKFLOW_STATE`                | runtime/telemetry.py                        | `System_logs/_workflow_state.json` |
| `_WORKFLOW_CACHE_DIR`           | cli/run_pipeline.py                         | `System_logs/_workflow_cache/` |
| `NOTIFY_LOG`                    | runtime/notifier.py                         | `System_logs/notification_log.jsonl` |
| `_TRIGGER_SESSION_FILE`         | runtime/improvement_trigger.py              | `System_logs/_improvement_session.json` |
| `LOG_PATH` (improvement log)    | system_improvement/run_self_improve.py      | `System_logs/improvement_log.jsonl` |
| `PENDING_DIR`                   | system_improvement/run_self_improve.py      | `System_logs/_pending/` |
| `WORKING_DIR` (self-improve)    | system_improvement/run_self_improve.py      | `System_logs/_improve_workdir/` |

Each CLI script computes `BASE = Path(__file__).parent.parent` because they
live in `cli/`. The runtime modules use `Path(__file__).parent.parent` from
`runtime/`. Don't change these without updating both.

---

## Parallel execution

`WorkflowEngine.execute(..., max_parallel=4)` runs as a DAG-driven scheduler.
A step is ready as soon as every artefact in its `input_keys` is present in
`context.shared_memory`. Up to `max_parallel` agent steps run concurrently in
a `ThreadPoolExecutor`; `run_step` is thread-safe (each call spawns its own
asyncio event loop).

Barriers — must run alone (drain in-flight first, run sequentially):
- `type: planner` and `type: dynamic` (they mutate the queue)
- Any step with `parallel_safe: false` in its YAML

On step error: the failed step's output_key plus all transitive dependents
are marked `cancelled_upstream_failure` and dropped from `pending`.
Non-dependent steps continue. `--resume-from` forces `max_parallel=1`.

CLI flag: `--max-parallel N` on `cli/run_pipeline.py` (default 4).

Implementation: `WorkflowEngine.execute` (scheduler) +
`WorkflowEngine._run_one_step` (thread-safe per-step worker) in
`workflows/workflow_engine.py`.

---

## Semantic workflow cache

Task-mode runs (`cli/run_pipeline.py --task ...`) cache the workflow YAML
produced by `manager` + `workflow_planner`, keyed by a hash of the
**canonical form** of the task (paraphrase-resistant), not the raw text.

Lookup pipeline:
1. Run the raw task through Haiku with a tight system prompt: "Restate in
   ≤12 words, lowercase, no punctuation, action verb + primary target."
2. Hash `(canonical, project)` into a 12-hex key.
3. Look up `System_logs/_workflow_cache/<key>.yaml` and its sibling
   `<key>.meta.json`.
4. On hit, skip `manager` and `workflow_planner` entirely.

The Haiku canonicalisation result is itself memoised in
`System_logs/_workflow_cache/_canonicalisation.json` keyed by md5(raw),
so identical raw strings never re-call Haiku. Falls back to plain
whitespace+case normalisation if the SDK or API key is unavailable.

**Invalidation rules** — entry becomes invalid when:
- Any agent it references no longer exists in the registry, OR
- `manager` or `workflow_planner` `system_prompt.md` has changed since the
  cache was written (8-hex hashes stored in `<key>.meta.json` under
  `planning_agents_fingerprint`).

Legacy entries (no `.meta.json`) only get the agent-existence check.

`--no-cache` forces fresh planning. `--use-cache` forces silent reuse.
If neither is supplied in task mode, the user is prompted interactively
via `prompt_use_cache()` with educational text explaining the tradeoff.
SELF_IMPROVE tasks skip the prompt (caching irrelevant — they mutate the
system).

Implementation: `_canonicalise_task`, `_haiku_canonicalise`,
`_task_cache_key`, `_cached_workflow_path`, `_cache_meta_path`,
`_prompt_fingerprint`, `_write_cache_meta`, `_is_cache_valid`,
`_execute_cached_workflow` in `cli/run_pipeline.py`.

---

## Per-run log naming

Each pipeline invocation generates a `run_id` (12-hex uuid) at startup and
writes that run's agent logs into:

```
System_logs/_agent_logs/{run_id}_{sub-task-slug}/<agent>.jsonl
```

Same `run_id` is used in `runs_history.jsonl` and as `trigger_id` in
`system_history.csv`, so logs and telemetry line up. Slug is built from
`--sub-task` (lowercase, non-alphanumerics → `-`); empty/`NaN` → `no-subtask`.

Helpers: `cli/run_pipeline.py:_slugify`, `cli/run_pipeline.py:_new_session_log_dir`.
The session run_id is threaded into `engine.execute(..., log_dir=...)`,
every `run_step(..., log_dir=...)` call, and `save_run_record(..., run_id=...)`.

---

## Adding things

| Add a...                | Drop it at...                                                                                     | Then... |
|-------------------------|---------------------------------------------------------------------------------------------------|---|
| General agent           | `Employees/General Agents/<category>/<name>/{config.json, system_prompt.md}`                      | Auto-discovered; no registration |
| Project-specific agent  | `Employees/Projects-Specific Agents and Workflows/<project_id>/agents/<name>/...`                 | Overrides general agent of same name for that project only |
| Shared workflow YAML    | `workflows/<name>.yaml`                                                                           | `cli/run_pipeline.py --workflow <name>` |
| Project workflow YAML   | `Employees/Projects-Specific Agents and Workflows/<project_id>/workflows/<name>.yaml`             | Engine resolves project first, then shared |
| New CLI flag            | `cli/run_pipeline.py:main()` argparse block                                                        | Thread through `_run_task_mode` or the workflow-mode branch |

---

## Conventions

- Folder names with spaces are forbidden. Use `snake_case`.
- Path constants live in `runtime/telemetry.py` (or `runtime/notifier.py` for `NOTIFY_LOG`). Don't introduce new ad-hoc paths in scripts.
- All runtime/log files live under `System_logs/`. Never write log/state files into `working_dir`.
- `working_dir` is the user-supplied task sandbox. It can point anywhere on disk and is purely for task outputs.
- Tools in `config.json`: `"tools": []` = text-only; `"tools": null`/absent = full default (`Read, Write, Edit, Glob, Grep, Bash`).
- Six "system" agents are protected from automated modification: `manager`, `prompt_engineer`, `registry_auditor`, `workflow_planner`, `output_evaluator`, `performance_analyzer`.
- **Model tiering** — orchestration/audit agents (`manager`, `workflow_planner`, `output_evaluator`, `performance_analyzer`) run on `claude-sonnet-4-5` because they do bookkeeping. Reserve `claude-opus-4-6` for specialist agents that produce deliverables. Don't promote an orchestration agent to opus without a token-cost justification.
- When editing telemetry, run `python3 cli/check_status.py --short` afterwards to confirm the new path resolves.

---

## Schemas

| File                              | Schema location |
|-----------------------------------|---|
| `runs_history.jsonl` record       | docstring at top of `runtime/telemetry.py` |
| `system_history.csv` columns      | `_CSV_COLUMNS` in `runtime/telemetry.py` |
| Agent `config.json` shape         | README.md §3 — or look at any existing agent's `config.json` |

---

## Where common operations are implemented

| Operation                          | File:symbol |
|------------------------------------|---|
| Execute a workflow                 | `workflows/workflow_engine.py:WorkflowEngine.execute` |
| Dispatch a single agent step       | `runtime/dispatcher.py:run_step` |
| Persist a run record               | `runtime/telemetry.py:save_run_record` |
| Append CSV row                     | `runtime/telemetry.py:append_run_to_csv` / `append_improvement_to_csv` |
| Post-run improvement check         | `runtime/improvement_trigger.py:post_run_check` |
| Resolve registry gaps inline       | `cli/run_pipeline.py:_resolve_gaps` |
| Self-improve one finding           | `system_improvement/run_self_improve.py:_run_one_finding` |
| Full registry audit                | `system_improvement/run_self_improve.py:main` (interactive) or `system_improvement/run_registry_audit.py` (one-shot) |

---

## When in doubt

1. `cli/check_status.py --short` — confirms history files resolve.
2. `python3 system_improvement/agent_registry.py [project_id]` — prints loaded agents.
3. `python3 cli/run_pipeline.py --list --project <id>` — lists workflows.
4. Use `--dry-run` on any `run_pipeline.py` call to inspect resolved prompts without spending tokens.
