# Setup & How-To

## Installation

```bash
git clone <repo-url> agent-system
cd agent-system
pip install -r requirements.txt
cp .env.example .env
# Open .env and add your ANTHROPIC_API_KEY
```

Verify the registry loads:
```bash
python3 system_improvement/agent_registry.py
# Prints all [general] agents
```

---

## How the interactive / CLI system works

Every flag in `cli/run_pipeline.py` is optional. The rule is:

- **Flag supplied on the command line** → used silently, no prompt shown
- **Flag omitted** → the terminal prompts you interactively for that value

This means you can run fully interactively, fully from flags, or any mix.

**Fully interactive (recommended for most runs):**
```bash
python3 cli/run_pipeline.py
```
The terminal will walk you through: mode → project → sub-task → output directory → mode-specific details.

**Partially flagged (remaining fields prompted):**
```bash
python3 cli/run_pipeline.py --workflow eda_report_pipeline
```

**Fully flagged (no prompts, good for scripting):**
```bash
python3 cli/run_pipeline.py --workflow eda_report_pipeline --project qbus3600 --sub-task "EDA Phase 1" --working-dir outputs
```

> **Shell tip:** When chaining multiple flags in one command, write them on **one line**. If you must break across lines, make sure there is **no space after the `\`** — a trailing space stops the line continuation and zsh will treat the next line as a separate command.

---

## Configuring notifications (optional)

Open `.env` and add any channels you want:

```bash
# macOS desktop — always active on macOS, no config needed

# Email (Gmail example — use an App Password, not your real password)
NOTIFY_EMAIL_TO=you@gmail.com
NOTIFY_EMAIL_FROM=you@gmail.com
NOTIFY_SMTP_HOST=smtp.gmail.com
NOTIFY_SMTP_PORT=587
NOTIFY_SMTP_USER=you@gmail.com
NOTIFY_SMTP_PASS=your-16-char-app-password

# Slack (create an Incoming Webhook at api.slack.com/apps)
NOTIFY_SLACK_WEBHOOK=https://hooks.slack.com/services/xxx/yyy/zzz
```

Any channel left unconfigured is silently skipped.

---

## Running a task (Task Mode)

### Interactive (simplest)
```bash
python3 cli/run_pipeline.py
```
Select **1 — Task Mode**, then answer the prompts.

At the dry-run prompt:
- `1` = Live run — makes real API calls
- `2` = Dry run — prints the plan, no API calls, no charges

### With flags
```bash
python3 cli/run_pipeline.py --task "Analyse the donor dataset and produce an EDA report" --project qbus3600 --sub-task "EDA Phase 1" --working-dir outputs
```

All task outputs (documents, notebooks, CSVs) go to the specified folder.
System files (logs, history, state) always stay inside the agent-system folder.

### Dry-run via flag
```bash
python3 cli/run_pipeline.py --task "Produce a research report on donor fatigue" --dry-run
```

---

## Running a named pipeline (Workflow Mode)

### Interactive (simplest)
```bash
python3 cli/run_pipeline.py
```
Select **2 — Workflow Mode**. The terminal shows all available workflows numbered. Pick one, then answer the resume-from prompt (press Enter to start fresh).

### With flags
```bash
python3 cli/run_pipeline.py --workflow eda_report_pipeline --project qbus3600 --inputs-file ./inputs.json
```

### Resuming after a failure
The system saves progress after every step. To resume:

**Interactive** — just run `python3 cli/run_pipeline.py`, select Workflow Mode, pick your workflow, and enter the step name at the resume prompt.



**Via flags:**
```bash
python3 cli/run_pipeline.py --workflow eda_report_pipeline --project qbus3600 --resume-from write_eda_sections --state-file System_logs/_workflow_state.json
```

---

## Improving the agent system (System-Improve Mode)

### Interactive
```bash
python3 cli/run_pipeline.py
```
Select **3 — System-Improve Mode**. Choose dry-run or live. The system runs a full audit and presents every proposed change for your approval.

### Via flag
```bash
python3 cli/run_pipeline.py --system-improve --project qbus3600
```

### Standalone script (same behaviour)
```bash
python3 system_improvement/run_self_improve.py
python3 system_improvement/run_self_improve.py --project qbus3600
python3 system_improvement/run_self_improve.py --dry-run
```

---

## The sub-task label

`--sub-task` (previously `--group`) is an optional human-readable label that groups related runs in `System_logs/system_history.csv` and is used to name the per-run log folder under `System_logs/_agent_logs/`. Use the same label across all runs that belong to one deliverable or phase.

In interactive mode the terminal shows your existing sub-tasks and lets you pick one, create a new one, or press **Enter** to skip (logged as `NaN`).

Via flag:
```bash
python3 cli/run_pipeline.py --task "..." --sub-task "UNICEF ML Notebook — Phase 3"
```

---

## Checking system health

```bash
python3 cli/check_status.py              # full dashboard
python3 cli/check_status.py --short      # one-line summary
python3 cli/check_status.py --notify     # push current status as a notification
python3 cli/check_status.py --json       # machine-readable JSON
```

No API calls are made. All data comes from `System_logs/runs_history.jsonl`.

---

## Understanding the automatic improvement trigger

After every run, the system silently checks whether 10 or more new runs have happened since the last performance analysis. When it fires:

1. `performance_analyzer` reads run history and identifies underperforming agents
2. The terminal prints specific findings and an exact command to action them
3. A macOS/email/Slack notification is sent

To action a finding, run System-Improve Mode:
```bash
python3 cli/run_pipeline.py --system-improve --project qbus3600
```

---

## Running a read-only audit

```bash
python3 system_improvement/run_registry_audit.py
# Report saved to: audit_output/audit_report.md
```

---

## Viewing performance history

```bash
# JSONL — full records
cat System_logs/runs_history.jsonl | python3 -m json.tool | head -100

# CSV — open in Excel or Numbers
open System_logs/system_history.csv
```

The CSV contains both run rows and improvement rows. Use `trigger_id` to join improvement rows back to the run that triggered the analysis. Use `task_group` to filter by sub-task label.

---

## Starting a new project

```bash
cp -r "Employees/Projects-Specific Agents and Workflows/_template" "Employees/Projects-Specific Agents and Workflows/your_project_id"
```

Edit `project.json`:
```json
{
  "id": "your_project_id",
  "name": "A readable name",
  "description": "What this project produces.",
  "version": "1.0",
  "workflow": "your_main_workflow",
  "extends": [],
  "context": {}
}
```

The `id` must exactly match the folder name. Once created, the project appears automatically in the interactive project list.

---

## Adding a project-specific agent

Create `Employees/Projects-Specific Agents and Workflows/<project_id>/agents/<agent_name>/`:

**`config.json`**
```json
{
  "name": "agent_name",
  "model": "claude-opus-4-6",
  "system_prompt": "system_prompt.md",
  "description": "One sentence.",
  "version": "1.0",
  "parameters": {},
  "tools": []
}
```

**Tools field:**
- `[]` — no tools (text only)
- `["Read"]` — read files only
- `["Read", "Write"]` — read and write
- absent or `null` — all defaults (Read, Write, Edit, Glob, Grep, Bash)

**`system_prompt.md`** — role statement, `## Input`, `## Your job`, `## Output`. Hardcoding project-specific paths and section names is expected and correct for project agents.

Auto-discovered — no registration step needed.

---

## Adding a general agent

Same structure, placed under `Employees/General Agents/<category>/<agent_name>/`.

Available categories: `analysis`, `assembly`, `auditing`, `design`, `documents`, `notebook_analysis`, `orchestration`, `planning`, `qa`, `research`, `tables`, `writing`.

Do not place new agents in `auditing/` or `orchestration/` — those hold system-layer agents only.

General agents must not hardcode paths, section names, or domain context — those arrive via the runtime task message.

---

## Adding a project workflow

Create `Employees/Projects-Specific Agents and Workflows/<project_id>/workflows/<name>.yaml`:

```yaml
name: my_workflow
description: "What this workflow does"
version: "1.0"

steps:
  - name: step_one
    agent: agent_name
    task: "Instruction to the agent at runtime"
    input_keys: []
    output_key: step_one_result
    retry_count: 1
    timeout_seconds: 300

  - name: step_two
    agent: another_agent
    task: "Use the output of step one to do X"
    input_keys: [step_one_result]
    output_key: step_two_result
    retry_count: 1
    timeout_seconds: 300
```

Project workflows take priority over general ones with the same name.

---

## Overriding a general agent for a project

Create a project agent with the **exact same name** as the general one. It shadows the general agent for that project only.

```
Employees/Projects-Specific Agents and Workflows/qbus3600/agents/table_maker/
```

All other projects continue using the general `table_maker`.

---

## Cost controls

| Control | How |
|---|---|
| Dry-run | `--dry-run` flag, or select "Dry run" at the interactive prompt |
| Cap turns per agent | `"max_turns": 20` in agent `config.json` |
| Use a cheaper model | `"model": "claude-haiku-4-5"` in agent `config.json` |
| Global model override | `DEFAULT_MODEL=claude-haiku-4-5` in `.env` |
| Restrict tools | `"tools": ["Read"]` in `config.json` |
| No tools | `"tools": []` in `config.json` |
