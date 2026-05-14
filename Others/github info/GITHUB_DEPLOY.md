# Deploying to GitHub

This guide walks through publishing the agent system to a private GitHub repo and onboarding teammates.

---

## A. One-time setup (you do this once)

### 1. Make sure git is configured

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

### 2. Create the empty private repo on GitHub

Go to https://github.com/new and:

- **Repository name:** `agent-system` (or whatever you prefer)
- **Visibility:** Private
- **Do NOT** check "Add a README", "Add .gitignore", or "Add a license" — we already have those locally.

Click **Create repository**. GitHub will show you a URL that looks like:

```
https://github.com/<your-username>/agent-system.git
```

Copy it. You'll paste it in step 4.

### 3. Initialise the local repo

From a terminal:

```bash
cd "/Users/ADMIN/Documents/Claude/agent-system"

# If a stale .git folder exists (e.g. from a prior init), wipe it first:
rm -rf .git

git init -b main
git add .
git status        # sanity-check: .env should NOT appear; .DS_Store should NOT appear
git commit -m "Initial commit: multi-agent system framework"
```

If `.env` or `__pycache__` shows up in `git status`, stop and check `.gitignore` is at the repo root.

### 4. Connect to GitHub and push

Replace the URL with the one GitHub gave you:

```bash
git remote add origin https://github.com/<your-username>/agent-system.git
git push -u origin main
```

GitHub will prompt you for credentials. If you have 2FA on, use a [Personal Access Token](https://github.com/settings/tokens) (classic, with `repo` scope) as the password — not your GitHub password. Easier: install the [GitHub CLI](https://cli.github.com) and run `gh auth login` once; git will then authenticate automatically.

### 5. Invite your teammates

On the repo page on github.com:

1. Settings → Collaborators → **Add people**
2. Enter their GitHub usernames or emails
3. They'll get an email invite

---

## B. Onboarding a new teammate

Send them this block. They paste it into a terminal:

```bash
# 1. Clone the repo (replace <username>)
git clone https://github.com/<your-username>/agent-system.git
cd agent-system

# 2. Create a Python virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add their own API key
cp .env.example .env
# Edit .env and paste their ANTHROPIC_API_KEY
# (each teammate uses their OWN key — never share keys)

# 5. Verify the registry loads
python3 system_improvement/agent_registry.py qbus3600

# 6. Dry-run a workflow (no API calls, no cost)
python3 cli/run_pipeline.py \
  --project qbus3600 \
  --workflow eda_report_pipeline \
  --working-dir ./scratch \
  --inputs '{}' \
  --dry-run
```

If step 5 prints a list like `[general] notebook_mapper: …` and `[project] a1_structural_mapper: …`, the system is wired up correctly.

---

## C. Day-to-day workflow for the team

### Pulling the latest changes

```bash
cd agent-system
git pull
```

### Making a change (recommended: feature branches)

```bash
# Start from a clean main
git checkout main
git pull

# Create a branch for your change
git checkout -b feat/new-research-agent

# ... edit files, add/modify agents or workflows ...

# Stage and commit
git add .
git commit -m "Add new academic researcher variant"

# Push the branch up
git push -u origin feat/new-research-agent
```

Then on GitHub, open a **Pull Request** from your branch → `main`. A teammate reviews, then merges.

### What NOT to commit

The `.gitignore` already blocks these, but worth knowing:

- **`.env`** — your API key. Never commit. Each teammate keeps their own.
- **`__pycache__/`, `*.pyc`** — Python bytecode.
- **`.DS_Store`** — macOS folder metadata.
- **`_workflow_state.json`, `_agent_logs/`** — runtime artefacts produced inside `--working-dir`. These are output from running pipelines, not source.
- **Local outputs / scratch dirs** — anything under `outputs/`, `scratch/`, `tmp/`.

If you accidentally committed `.env` or any secret, rotate the API key immediately on the Anthropic console, then [scrub it from history](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

---

## D. Quick reference

| Action | Command |
|---|---|
| Pull latest | `git pull` |
| New feature branch | `git checkout -b feat/<name>` |
| Stage all changes | `git add .` |
| See what's staged | `git status` |
| Commit | `git commit -m "<message>"` |
| Push branch first time | `git push -u origin <branch>` |
| Push subsequent times | `git push` |
| Switch branch | `git checkout <branch>` |
| Discard local edits to a file | `git checkout -- <file>` |
| See history | `git log --oneline -20` |

---

## E. Troubleshooting

**`fatal: remote origin already exists`** — you ran `git remote add origin` twice. Fix:

```bash
git remote set-url origin https://github.com/<your-username>/agent-system.git
```

**`Permission denied (publickey)` on push** — you're pushing over SSH but haven't added an SSH key. Easiest fix: use the HTTPS URL instead, or run `gh auth login`.

**Teammate gets "Repository not found"** — they haven't been added as a collaborator, or they're authenticated as the wrong GitHub user.

**`.env` shows up in `git status`** — `.gitignore` isn't being read. Make sure `.gitignore` sits at the repo root (`agent-system/.gitignore`), not inside a subfolder.

**Want to test the deploy without affecting the real repo?** Create a throwaway repo first (e.g. `agent-system-test`), push to it, delete it, then redo with the real repo.
