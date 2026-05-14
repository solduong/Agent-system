# Multi-Agent System — Technical Reference

> **Audience:** Developers who need a complete, authoritative description of this system's architecture, components, and runtime behaviour.
>
> **For AI agents working on this codebase:** start with [`AGENTS.md`](AGENTS.md) — a terse navigation map that tells you where things live without forcing you to read this whole document. Read this README only if AGENTS.md doesn't cover what you need.

---

## 1. System Purpose

A file-based multi-agent orchestration framework built on the Anthropic Claude API. Agents are defined as folders containing a `config.json` and `system_prompt.md`. Pipelines are defined as YAML files. The runtime dispatches agents sequentially, passing artefacts between steps via a shared context store.

Three execution modes — selectable interactively at startup or via CLI flags:

| Mode | Flag | Description |
|---|---|---|
| **Task mode** | `--task` | Free-form goal; `manager` → `workflow_planner` → engine; auto-creates missing agents |
| **Workflow mode** | `--workflow` | Run a named, predefined YAML pipeline directly; supports resume from failed steps |
| **System-Improve mode** | `--system-improve` | Full agent audit + interactive human-approval improvement loop |

**Interactive vs CLI:** Every flag is optional. If omitted, the system prompts interactively. Any flag supplied on the command line is used silently — the corresponding prompt is skipped.

---

## 2. Directory Structure

```
agent-system/
├── Employees/
│   ├── General Agents/
│   │   ├── auditing/
│   │   │   ├── prompt_engineer/
│   │   │   ├── registry_auditor/
│   │   │   ├── output_evaluator/       ← scores pipeline output quality (0–10)
│   │   │   └── performance_analyzer/   ← reads run history, finds degraded agents
│   │   ├── orchestration/
│   │   │   ├── manager/                ← tools: ["Read"] only
│   │   │   └── workflow_planner/
│   │   ├── analysis/data_analyzer/
│   │   ├── assembly/report_generator/
│   │   ├── design/frontend-design/
│   │   ├── documents/docx|xlsx|pdf|pdf-reading|file-reading|pptx/
│   │   ├── notebook_analysis/notebook_mapper|chunk_extractor/
│   │   ├── planning/report_planner|research_task_planner/
│   │   ├── qa/reviewer|citation_verifier/
│   │   ├── research/academic_researcher|research_question_refiner|product-knowledge/
│   │   ├── tables/table_maker/
│   │   └── writing/section_writer|business_insights_writer|writer/
│   └── Projects-Specific Agents and Workflows/
│       ├── _template/
│       └── <project_id>/
│           ├── project.json
│           ├── agents/<agent_name>/
│           └── workflows/<name>.yaml
│
├── workflows/
│   └── workflow_engine.py
│
├── runtime/
│   ├── dispatcher.py               ← Anthropic API bridge
│   ├── telemetry.py                ← run record persistence (JSONL + CSV)
│   ├── improvement_trigger.py      ← post-run analysis trigger
│   └── notifier.py                 ← macOS / email / Slack alerts
│
├── system_improvement/
│   ├── agent_registry.py
│   ├── run_self_improve.py         ← exposes run(project, dry_run) + CLI main()
│   └── run_registry_audit.py
│
├── cli/
│   ├── run_pipeline.py             ← main CLI (all modes)
│   ├── run_feedback_loop.py        ← advanced: task + evaluation + loop control
│   ├── check_status.py             ← instant health snapshot, no API calls
│   └── interactive_prompt.py       ← all interactive terminal prompt functions
│
├── outputs/                        ← deliverables, organised per task
│   ├── nsw_drought_fund/
│   └── unification/
│
├── System_logs/                    ← runtime files (never inside working_dir)
│   ├── _agent_logs/{run_id}_{sub-task}/<agent>.jsonl ← per-run API logs, one folder per pipeline run
│   ├── _agent_logs_legacy/         ← logs from before the per-run folder layout
│   ├── _workflow_state.json        ← step resume state
│   ├── _generated_workflow.yaml    ← YAML produced by workflow_planner
│   ├── _improvement_session.json   ← links improvement events to trigger run
│   ├── runs_history.jsonl          ← append-only performance record (every run)
│   ├── system_history.csv          ← human-readable history: runs + improvements
│   ├── improvement_log.jsonl       ← every self-improvement decision
│   └── notification_log.jsonl      ← every alert fired
│
└── .env                            ← API keys and notification config
```

> **Category folders are organisational only.** The registry keys agents by leaf folder name and scans recursively — category subfolders have no effect on agent loading.

---

## 3. Agent Anatomy

Every agent is a folder with exactly two files:

**`config.json`**
```json
{
  "name": "agent_name",
  "model": "claude-opus-4-6",
  "system_prompt": "system_prompt.md",
  "description": "One sentence.",
  "version": "1.0",
  "parameters": {},
  "tools": ["Read", "Write"]
}
```

**Tools field behaviour:**
- `"tools": ["Read", "Write"]` — agent gets only those tools
- `"tools": []` — agent gets **no tools** (text-only, no file/bash access)
- `"tools": null` or key absent — agent gets all defaults: `Read, Write, Edit, Glob, Grep, Bash`

Tool scope is always restricted to `working_dir` at runtime.

**`system_prompt.md`**
Contains: role statement (one line), `## Input`, `## Your job`, `## Output`. General agent prompts must not hardcode paths or domain context. Project-specific agents may hardcode project context.

---

## 4. Registry — Agent Loading and Merging

`system_improvement/agent_registry.py` → class `AgentRegistry`

**Load order:**
1. Scan `Employees/General Agents/` recursively — label `"general"`
2. If `project_id` set, scan `Employees/Projects-Specific Agents/<project_id>/agents/` — label `"project:<id>"`
3. Project agents with the same folder name **override** the general one for that project only

**Key methods:**
- `AgentRegistry(base_dir, project_id=None)` — load agents
- `registry.load_agent(name)` — return merged config dict
- `registry.reload()` — rescan and refresh; called after `prompt_engineer` writes new agent files
- `registry.describe()` — formatted string listing all loaded agents

`ProjectContext` — holds `shared_memory` (key→value artefact store) and `logs`. Serialisable to/from `System_logs/_workflow_state.json`.

---

## 5. Workflow Anatomy

```yaml
name: workflow_name
description: "What this workflow does"
version: "1.0"

steps:
  - name: step_one
    agent: agent_name
    task: "Runtime instruction"
    input_keys: []
    output_key: step_one_result
    parameters: {}
    retry_count: 1
    timeout_seconds: 300
    continue_on_error: false
```

`input_keys` artefacts are appended to the task message as `## Upstream artefacts`. The full agent transcript is stored under `output_key`.

---

## 6. Dispatcher — API Bridge

`runtime/dispatcher.py` → `run_step(agent_config, task, working_dir, inputs, dry_run, log_dir)`

- `working_dir` — task sandbox; where agents read/write files for the task. Can be any path.
- `log_dir` — where API logs are written. CLI entrypoints generate a per-run folder `System_logs/_agent_logs/{run_id}_{sub-task}/` and pass it as `log_dir`, so each pipeline run's logs are isolated and never mix with task output regardless of where `working_dir` points. If omitted, defaults to `AGENT_LOGS_DIR` (`System_logs/_agent_logs/`).
- Returns `DispatchResult(agent, status, transcript, error, duration_seconds, input_tokens, output_tokens, log_path)`

**Status values:** `"ok"` | `"error"` | `"dry_run"`

---

## 7. Workflow Engine

`workflows/workflow_engine.py` → `engine.execute(workflow, context, ..., working_dir, log_dir, state_path, ...)`

- `working_dir` — task sandbox only; agents read/write here
- `log_dir` — defaults to `AGENT_LOGS_DIR`; overridable
- `state_path` — defaults to `System_logs/_workflow_state.json`; overridable via `--state-file`

---

## 8. CLI Reference

### Startup logic

`run_pipeline.py` uses a **mixed interactive/CLI** startup. The rule is simple:

- **Flag supplied** → used silently, prompt skipped
- **Flag omitted** → interactive prompt shown

The prompts run in this fixed order:

```
1. Mode            (--workflow | --task | --system-improve)
2. Project         (--project)
3. System-Improve short-circuit — asks dry-run only, then exits
4. Sub-task        (--sub-task)
5. Working dir     (--working-dir)
6. Mode-specific:
     Task mode     → task description + dry-run or live
     Workflow mode → workflow name (if needed) + resume-from step
```

### Fully interactive (no flags)

```bash
python3 cli/run_pipeline.py
```

### Partially flagged (remaining fields prompted)

```bash
# Workflow already known; project/sub-task/working-dir/resume-from prompted
python3 cli/run_pipeline.py --workflow eda_report_pipeline

# Task and project known; sub-task/working-dir prompted; dry-run flag skips that prompt
python3 cli/run_pipeline.py --task "Analyse the donor dataset" --project qbus3600 --dry-run
```

### Fully flagged (no prompts)

```bash
# Task mode
python3 cli/run_pipeline.py --task "Analyse the donor dataset and produce an EDA report" --project qbus3600 --sub-task "EDA Phase 1" --working-dir outputs

# Workflow mode with resume
python3 cli/run_pipeline.py --workflow _generated_workflow --project qbus3600 --sub-task "UNICEF ML Notebook" --working-dir outputs/unification --resume-from phase8_qa_audit --state-file System_logs/_workflow_state.json

# System-Improve mode
python3 cli/run_pipeline.py --system-improve --project qbus3600
```

> **Shell tip:** When using multiple flags, write them on **one line** or ensure there is **no space after each `\`** in multi-line commands. A trailing space after `\` causes zsh to treat the next line as a separate command.

### All flags

| Flag | Mode | Description |
|---|---|---|
| `--workflow <name>` | Workflow | YAML name without `.yaml` |
| `--task <text>` | Task | Free-form goal description |
| `--system-improve` | System-Improve | Run full agent audit + approval loop |
| `--project <id>` | All | Load project-specific agents into registry |
| `--sub-task <label>` | All | Human label grouping related runs — recorded in `System_logs/system_history.csv` and used to name the per-run log folder; press Enter to skip (logged as `NaN`) |
| `--working-dir <path>` | All | Task output directory; defaults to `<agent-system>/outputs` |
| `--inputs <json>` | Both | JSON literal of initial inputs dict |
| `--inputs-file <path>` | Both | Path to JSON file with initial inputs |
| `--resume-from <step>` | Workflow | Step name to restart from after a failure |
| `--state-file <path>` | Workflow | Override state file path (default: `System_logs/_workflow_state.json`) |
| `--dry-run` | All | No API calls; prints resolved prompts/plan |
| `--no-cache` | Task | Force a fresh `manager` + `workflow_planner` plan even if a cached YAML exists for this task. Prompted interactively if omitted. See §13 Workflow Cache. |
| `--use-cache` | Task | Reuse a paraphrase-equivalent cached plan silently, no prompt. Mutually exclusive with `--no-cache`. |
| `--max-parallel <N>` | All | Maximum concurrent agent steps when `input_keys` allow it (default 4). `--resume-from` forces this to 1. See §13 Parallel Execution. |
| `--list` | All | List agents and workflows for the project and exit |

### `interactive_prompt.py` — module API

| Function | Returns | Description |
|---|---|---|
| `prompt_mode()` | `str` | Asks user to select Task / Workflow / System-Improve |
| `prompt_task_text()` | `str` | Asks for free-form task description |
| `prompt_dry_run()` | `bool` | Asks Live run vs Dry run |
| `prompt_workflow_details(workflows)` | `dict` | Shows workflow list, returns `{'name': str}` |
| `prompt_resume_from()` | `str \| None` | Asks for step name to resume from; Enter = start fresh |
| `prompt_project(base_dir)` | `str` | Shows existing projects; accepts number, name, or `new` |
| `prompt_sub_task(base_dir)` | `str \| None` | Shows existing sub-tasks; Enter = NaN |
| `prompt_working_dir(base_dir)` | `Path` | Shows default path; Enter = `<base_dir>/outputs` |
| `prompt_max_parallel(default=4)` | `int` | Asks Parallel / Sequential / Custom; accepts a positive integer directly |
| `prompt_use_cache(default=True)` | `bool` | Asks Use cache / No cache; explains the tradeoff (skip planning vs fresh plan after agent edits) |
| `gather_existing_projects(base_dir)` | `list[str]` | Scans folder structure + `System_logs/runs_history.jsonl` |
| `gather_existing_sub_tasks(base_dir)` | `list[str]` | Scans `System_logs/runs_history.jsonl` + `System_logs/system_history.csv` |

### `check_status.py` — instant health snapshot (no API calls)

```bash
python3 cli/check_status.py              # full dashboard
python3 cli/check_status.py --short      # one-line summary
python3 cli/check_status.py --notify     # push current status as a notification
python3 cli/check_status.py --json       # machine-readable JSON
```

### `run_feedback_loop.py` — advanced loop control

```bash
python3 cli/run_feedback_loop.py --task "..." --project qbus3600 --working-dir ./outputs --analyze-every 10 --quality-threshold 6.0

python3 cli/run_feedback_loop.py --analyze-only --project qbus3600

python3 cli/run_feedback_loop.py --task "..." --working-dir ./outputs --auto-approve
```

### `run_self_improve.py` — standalone system audit

```bash
python3 system_improvement/run_self_improve.py            # routine pass — descriptions only, ~16k tokens
python3 system_improvement/run_self_improve.py --project qbus3600
python3 system_improvement/run_self_improve.py --dry-run  # show diffs, write nothing
python3 system_improvement/run_self_improve.py --deep     # full prompts inlined — ~50k tokens
```

**Routine vs. deep audit.** By default the auditor sees descriptions only.
It uses a similarity-triggered drill-in protocol: when two descriptions look
alike (similar verbs / objects / domain language) it `Read`s those agents'
`system_prompt.md` files to confirm the overlap. Most audits read 0–3 prompts
on demand. Use `--deep` only when you suspect stale-description drift across
many agents — it costs ~5× more tokens.

Also callable from Python without argparse conflicts:
```python
from system_improvement.run_self_improve import run
run(project="qbus3600", dry_run=False, deep=False)
```

---

## 9. Task Mode — Three-Phase Routing

### Phase 1 — Gap resolution loop (max 3 iterations)

```
manager (Read tool only — plans, does not execute)
  ↓ STATUS: GAPS_DETECTED
  → prompt_engineer [AUTOMATED GAP FILL] → writes files to disk
  → registry_auditor [NEW AGENT REVIEW] → APPROVE / REJECT
  → registry.reload() if approved
  ↓ STATUS: READY
```

**Manager gap output format** (exact — parser is strict):
```
## STATUS
GAPS_DETECTED

## NEW AGENTS NEEDED
- name: <name> | purpose: <one sentence> | category: <folder>
```

### Routing check — SELF_IMPROVE vs EXECUTE

After Phase 1, if manager transcript contains `## TASK_TYPE\nSELF_IMPROVE`, the system routes to the interactive improvement pipeline instead of Phases 2–3.

### Phase 2 — Workflow formalisation

`workflow_planner` writes `System_logs/_generated_workflow.yaml`.

### Phase 3 — Execution

Engine executes the generated YAML.

---

## 10. General Agent Catalogue

### Auditing layer — `auditing/`

| Agent | Tools | Role |
|---|---|---|
| `prompt_engineer` | `Read, Write` | Create and improve agent prompts. Three modes: interactive create, automated gap fill, improve existing. |
| `registry_auditor` | `Read` | Quality gate. Two modes: full system audit (Mode A), new agent / improvement review (Mode B). |
| `output_evaluator` | none | Scores a completed pipeline run 0–10 across five dimensions. Used by `run_feedback_loop.py`. |
| `performance_analyzer` | none | Reads `System_logs/runs_history.jsonl`, identifies degraded agents. Triggered automatically every 10 runs. |

### Orchestration layer — `orchestration/`

| Agent | Tools | Role |
|---|---|---|
| `manager` | `Read` | Strategic coordinator: reads goal + roster, plans steps, detects gaps, detects self-improve intent. Never executes work directly. |
| `workflow_planner` | `Write` | Formalises manager's plan as executable YAML. |

### Worker agents

`report_planner`, `research_task_planner`, `section_writer`, `business_insights_writer`, `writer`, `academic_researcher`, `research_question_refiner`, `product-knowledge`, `data_analyzer`, `notebook_mapper`, `chunk_extractor`, `table_maker`, `report_generator`, `reviewer`, `citation_verifier`, `docx`, `xlsx`, `pdf`, `pdf-reading`, `file-reading`, `pptx`, `frontend-design`

---

## 11. Performance & Feedback Loop

### Automatic telemetry — every run

After every non-dry run, `save_run_record()` appends one record to:
- `System_logs/runs_history.jsonl` — full JSONL record including `task_full`, `task_group`, per-step token/cost/duration
- `System_logs/system_history.csv` — human-readable CSV with `trigger_id` and `task_group` columns

### CSV schema — `system_history.csv`

| Column | `run` rows | `improvement` rows |
|---|---|---|
| `event_type` | `run` | `improvement` |
| `trigger_id` | own `run_id` | `run_id` that triggered analysis |
| `task_group` | `--sub-task` value or `NaN` | inherited from trigger session |
| `run_id` | unique hex | blank |
| `task` | 120-char preview | blank |
| `project` | `--project` value | blank |
| `success` | `True`/`False` | blank |
| `quality_score` | 0–10 (if evaluated) | blank |
| `total_cost_usd` | sum of steps | blank |
| `agents_used` | comma-separated | blank |
| `agent` | blank | agent whose prompt changed |
| `finding` | blank | one-sentence finding |
| `improvement_status` | blank | `applied` / `blocked` / `validation_rejected` / … |
| `note` | blank | rejection reason or edit note |

### Automatic improvement trigger

After every run, `post_run_check()` is called silently. When 10+ runs have completed since the last analysis: `performance_analyzer` runs → findings printed → notification fired → no changes applied.

---

## 12. File Locations

| File | Location | Moves with `--working-dir`? |
|---|---|---|
| Task outputs (docx, csv, notebooks…) | `working_dir/` | ✅ Yes |
| `_agent_logs/{run_id}_{sub-task}/<agent>.jsonl` | `System_logs/_agent_logs/` | ❌ Always in agent-system |
| `_workflow_state.json` | `System_logs/` | ❌ Always in agent-system |
| `_generated_workflow.yaml` | `System_logs/` | ❌ Always in agent-system |
| `runs_history.jsonl` | `System_logs/` | ❌ Always in agent-system |
| `system_history.csv` | `System_logs/` | ❌ Always in agent-system |
| `improvement_log.jsonl` | `System_logs/` | ❌ Always in agent-system |
| `notification_log.jsonl` | `System_logs/` | ❌ Always in agent-system |

**`working_dir` is purely a task sandbox.** All system and history files are fixed inside the agent-system folder and are never affected by the `--working-dir` value.

---

## 13. State and Cost Controls

| Control | How |
|---|---|
| Dry-run | `--dry-run` flag — or select "Dry run" at the interactive prompt in task/system-improve mode |
| Cap turns | `"max_turns": N` in `config.json` (default 40) |
| Cheaper model | `"model": "claude-haiku-4-5"` in `config.json` |
| Global model override | `DEFAULT_MODEL=claude-haiku-4-5` in `.env` |
| Restrict tools | `"tools": ["Read"]` in `config.json` |
| No tools | `"tools": []` in `config.json` |
| Skip planning on repeats | Workflow cache (auto, see below) — disable with `--no-cache` |
| Cheaper audit | Routine audit by default; `--deep` only when needed |
| Reduce wall time | `--max-parallel N` (default 4) — runs independent steps concurrently |
| Force a step to be serial | Add `parallel_safe: false` to that step in the YAML |

### Model tiering (orchestration vs. specialists)

Bookkeeping agents (`manager`, `workflow_planner`, `output_evaluator`,
`performance_analyzer`) run on `claude-sonnet-4-5`. Reserve
`claude-opus-4-6` for specialist agents that produce deliverables.
Don't promote an orchestration agent to opus without a token-cost
justification.

### Compact roster — manager and workflow_planner

The roster handed to `manager` is **category-grouped, names only** (no
descriptions). The manager has `Read` access and is instructed to inspect
a specific agent's `config.json` on demand if it needs the one-line
description before deciding. It must never read `system_prompt.md` files
during planning.

The roster handed to `workflow_planner` is a **flat name list** — it just
validates that every agent name in the plan exists in the registry; it does
not pick agents.

Helpers in `cli/run_pipeline.py`:
- `_format_roster()` — verbose name+description, used only by `prompt_engineer` / `registry_auditor` in gap resolution
- `_format_roster_tree()` — compact category-grouped view for `manager`
- `_format_roster_names_only()` — flat name list for `workflow_planner`

Token impact (qbus3600 project, 55 agents): manager call drops from ~2,629
to ~389 input tokens for the roster portion; workflow_planner from ~2,629
to ~255.

### Parallel execution

`WorkflowEngine.execute()` is a DAG-driven scheduler. A step becomes ready
as soon as every artefact named in its `input_keys` is present in
`context.shared_memory`. Up to `max_parallel` agent steps run concurrently
in a `ThreadPoolExecutor` (default 4). The dispatcher's `run_step` is
thread-safe — each call spawns its own asyncio event loop.

**Barrier steps** — run alone (scheduler drains in-flight before submitting,
then runs the barrier alone, then resumes parallel scheduling):

- Any step with `type: planner` or `type: dynamic` (they mutate the queue)
- Any step that sets `parallel_safe: false` in YAML — author opt-out for
  cases like file-locking or external rate limits

**Cascade-cancel on failure** — when a step errors, every queued step that
transitively depends on its `output_key` is marked
`cancelled_upstream_failure` (with an `upstream` field naming the failed
step) and dropped from the queue. Steps that don't depend on the failure
continue normally. Already-running steps are not interrupted.

**Resume mode** — `--resume-from` forces `max_parallel=1`. Mixing partial
state with concurrent execution is risky; resumes always run sequentially.

**Per-step opt-out** — add to a step's YAML to force serial execution:

```yaml
- name: write_output
  agent: writer
  parallel_safe: false   # this step never runs alongside others
  ...
```

Wall-time impact depends on workflow shape. On a fan-out where N
independent steps wait for the same upstream, parallelism cuts the wall
time of that section from `N × step_time` to `ceil(N / max_parallel) × step_time`.

Implementation: `WorkflowEngine.execute` and `WorkflowEngine._run_one_step`
in `workflows/workflow_engine.py`.

### Workflow cache (semantic)

Task-mode runs (`cli/run_pipeline.py --task ...`) cache the YAML produced by
`manager` + `workflow_planner`. The cache is **semantic**: it canonicalises
the raw task text via a one-shot Haiku call before hashing, so paraphrases of
the same intent share a key. Three of these all hit the same entry:

- *"forecast NSW drought outcomes"*
- *"predict drought outcomes for NSW"*
- *"build a drought forecasting model for NSW"*

Files:

```
System_logs/_workflow_cache/<key>.yaml             ← cached workflow
System_logs/_workflow_cache/<key>.meta.json        ← raw_task, canonical, fingerprints
System_logs/_workflow_cache/_canonicalisation.json ← memo: md5(raw) → canonical
```

The Haiku call itself is cheap (~$0.001) and its output is memoised, so
identical raw strings never re-call Haiku — the cost only applies on first
encounter of a new phrasing. If the SDK or `ANTHROPIC_API_KEY` is missing,
canonicalisation falls back to plain whitespace+case normalisation (i.e. old
string-equality behaviour).

**Invalidation triggers**:

1. The cached YAML references an agent that no longer exists in the registry.
2. `manager` or `workflow_planner` `system_prompt.md` has changed since the
   cache was written. The 8-hex content hashes are stored under
   `planning_agents_fingerprint` in the meta file and compared on every
   lookup.
3. Manual: `--no-cache` flag.

Other changes (worker agent prompt edits, description tweaks) do **not**
invalidate — those affect deliverable quality, not workflow structure.

**Interactive prompt** — task mode now prompts `prompt_use_cache()` when
neither `--no-cache` nor `--use-cache` is supplied. The prompt explains the
tradeoff (skip ~$0.10–0.30 of planning vs force fresh planning after agent
edits) so users can choose deliberately.

`--sub-task` and `--inputs` are intentionally **not** part of the key — they
don't change workflow structure and you usually want to reuse the cached
plan across runs that differ only in label or input dict.

Implementation: `_canonicalise_task`, `_haiku_canonicalise`,
`_task_cache_key`, `_cached_workflow_path`, `_cache_meta_path`,
`_prompt_fingerprint`, `_write_cache_meta`, `_is_cache_valid`,
`_execute_cached_workflow` in `cli/run_pipeline.py`.

### Per-run log naming

Every pipeline run generates a `run_id` (12-hex uuid) at startup and writes
that run's agent logs into:

```
System_logs/_agent_logs/{run_id}_{sub-task-slug}/<agent>.jsonl
```

The same `run_id` is used in `runs_history.jsonl` and as `trigger_id` in
`system_history.csv`, so logs and telemetry line up. Sub-task labels are
slugified (lowercased, non-alphanumerics → `-`); empty/`NaN` becomes
`no-subtask`.

### Routine vs. deep registry audit

`run_self_improve.py` defaults to a **routine audit**: the auditor receives
descriptions only plus each agent's prompt path, and uses a similarity-
triggered drill-in to `Read` `system_prompt.md` files only when descriptions
look alike. ~16k input tokens for a healthy audit.

Pass `--deep` when you suspect stale-description drift across many agents.
Deep mode inlines every agent's full system_prompt.md in the task body
(~50k input tokens) so the auditor doesn't need to drill in.

---

## 14. System-Improve Pipeline

Human approval required for every change. System agents (`manager`, `prompt_engineer`, `registry_auditor`, `workflow_planner`, `output_evaluator`, `performance_analyzer`) are permanently protected.

```
registry_auditor (Mode A) → STRUCTURED_FINDINGS
  → for each finding:
      prompt_engineer [IMPROVE EXISTING AGENT] → proposed prompt in _pending/
      diff shown in terminal
      [A] Approve / [R] Reject (reason→retry, max 2) / [E] Edit / [S] Skip
      → registry_auditor [IMPROVEMENT REVIEW]
        APPROVE → write to disk → registry.reload()
        REJECT  → logged, not applied
```

All decisions logged to `System_logs/improvement_log.jsonl` and mirrored as `improvement` rows in `System_logs/system_history.csv`.

Can be triggered three ways:
1. **Interactive mode:** `python3 cli/run_pipeline.py` → select mode 3
2. **CLI flag:** `python3 cli/run_pipeline.py --system-improve --project qbus3600`
3. **Standalone script:** `python3 system_improvement/run_self_improve.py`

---

## 15. Project Schema (`project.json`)

```json
{
  "id": "project_id",
  "name": "Human-readable name",
  "description": "One sentence.",
  "version": "1.0",
  "workflow": "default_workflow_name",
  "available_workflows": [],
  "extends": [],
  "context": {}
}
```
