#!/usr/bin/env bash
# deploy_to_team_repo.sh
#
# Add this agent-system into your team's existing GitHub repo as a subfolder,
# on a feature branch, ready for a Pull Request review.
#
# What it does:
#   1. Clones the team repo to a sibling folder (../<repo-name>).
#   2. Creates a feature branch (default: feat/add-agent-system).
#   3. Copies the agent-system files into <repo>/<subfolder>/, excluding
#      .env, .git, .DS_Store, __pycache__, runtime artefacts, etc.
#   4. Commits and pushes the branch.
#   5. Prints a link to open the Pull Request.
#
# Usage:
#   bash deploy_to_team_repo.sh <repo-url> [subfolder] [branch]
#
# Examples:
#   bash deploy_to_team_repo.sh https://github.com/teamorg/team-repo.git
#   bash deploy_to_team_repo.sh git@github.com:teamorg/team-repo.git agents feat/agent-system-v1

set -euo pipefail

REPO_URL="${1:-}"
SUBFOLDER="${2:-agent-system}"
BRANCH="${3:-feat/add-agent-system}"

if [[ -z "$REPO_URL" ]]; then
  cat >&2 <<'USAGE'
Error: missing repo URL.

Usage:
  bash deploy_to_team_repo.sh <repo-url> [subfolder] [branch]

Example:
  bash deploy_to_team_repo.sh https://github.com/teamorg/team-repo.git
USAGE
  exit 1
fi

# This script lives inside the agent-system folder.
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SOURCE_DIR")"

# Derive a local clone folder name from the repo URL.
REPO_NAME="$(basename "$REPO_URL" .git)"
CLONE_DIR="$PARENT_DIR/$REPO_NAME"

echo ">> Source (this agent-system): $SOURCE_DIR"
echo ">> Team repo URL:              $REPO_URL"
echo ">> Will clone to:              $CLONE_DIR"
echo ">> Subfolder inside repo:      $SUBFOLDER"
echo ">> Feature branch:             $BRANCH"
echo ""

# 1. Clone (or refresh) the team repo.
if [[ -d "$CLONE_DIR/.git" ]]; then
  echo ">> Existing clone found at $CLONE_DIR — refreshing..."
  cd "$CLONE_DIR"
  git fetch --all --prune
  # Move to default branch (main, then master) and pull.
  if git show-ref --verify --quiet refs/remotes/origin/main; then
    git checkout main
    git pull --ff-only
    DEFAULT_BRANCH="main"
  elif git show-ref --verify --quiet refs/remotes/origin/master; then
    git checkout master
    git pull --ff-only
    DEFAULT_BRANCH="master"
  else
    DEFAULT_BRANCH="$(git symbolic-ref --short HEAD)"
  fi
else
  echo ">> Cloning $REPO_URL ..."
  git clone "$REPO_URL" "$CLONE_DIR"
  cd "$CLONE_DIR"
  DEFAULT_BRANCH="$(git symbolic-ref --short HEAD)"
fi

echo ">> Default branch: $DEFAULT_BRANCH"

# 2. Create or switch to the feature branch.
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo ">> Switching to existing local branch $BRANCH"
  git checkout "$BRANCH"
elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  echo ">> Checking out remote branch $BRANCH"
  git checkout -b "$BRANCH" "origin/$BRANCH"
else
  echo ">> Creating fresh branch $BRANCH from $DEFAULT_BRANCH"
  git checkout -b "$BRANCH"
fi

# 3. Copy agent-system into the subfolder, excluding cruft.
TARGET="$CLONE_DIR/$SUBFOLDER"
mkdir -p "$TARGET"

echo ">> Copying files into $TARGET ..."
# Use rsync if available (cleaner exclusions); otherwise fall back to cp+find.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='.env.local' \
    --exclude='.DS_Store' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.venv/' \
    --exclude='venv/' \
    --exclude='_workflow_state.json' \
    --exclude='_agent_logs/' \
    --exclude='outputs/' \
    --exclude='scratch/' \
    --exclude='tmp/' \
    --exclude='*.log' \
    --exclude='.idea/' \
    --exclude='.vscode/' \
    "$SOURCE_DIR/" "$TARGET/"
else
  # Fallback: clear target then cp, then prune cruft.
  rm -rf "$TARGET"
  mkdir -p "$TARGET"
  cp -R "$SOURCE_DIR"/. "$TARGET"/
  find "$TARGET" \( \
       -name '.git' -o \
       -name '.env' -o \
       -name '.DS_Store' -o \
       -name '__pycache__' -o \
       -name '*.pyc' -o \
       -name '.venv' -o \
       -name '_workflow_state.json' -o \
       -name '_agent_logs' \
    \) -prune -exec rm -rf {} + 2>/dev/null || true
fi

# 4. Sanity check — never commit a real .env.
if [[ -f "$TARGET/.env" ]]; then
  echo "!! Aborting: $TARGET/.env exists. Remove it before re-running." >&2
  exit 1
fi

# 5. Stage, check there's something to commit, commit, push.
cd "$CLONE_DIR"
git add "$SUBFOLDER"

if git diff --cached --quiet; then
  echo ">> No changes to commit. The team repo already has identical contents under $SUBFOLDER/."
  exit 0
fi

STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
echo ">> Files staged: $STAGED"

USER_NAME="$(git config --global user.name  || echo "Sol")"
USER_EMAIL="$(git config --global user.email || echo "dgh.giang@gmail.com")"

git -c user.name="$USER_NAME" -c user.email="$USER_EMAIL" \
    commit -q -m "Add multi-agent system framework under $SUBFOLDER/

- General Agents library (writing, research, planning, qa, etc.)
- Project-specific agents (qbus3600 example)
- Workflow engine + cli/run_pipeline.py entrypoint
- Setup docs: README.md, SETUP.md, USER_GUIDE.txt"

echo ">> Pushing branch $BRANCH to origin..."
git push -u origin "$BRANCH"

# 6. Print PR link.
# Convert SSH URL to HTTPS for the PR link.
HTTPS_URL="$REPO_URL"
if [[ "$HTTPS_URL" =~ ^git@github\.com:(.+)\.git$ ]]; then
  HTTPS_URL="https://github.com/${BASH_REMATCH[1]}"
fi
HTTPS_URL="${HTTPS_URL%.git}"

cat <<DONE

>> Done.

Open a Pull Request:
  $HTTPS_URL/pull/new/$BRANCH

Local clone is at:
  $CLONE_DIR

To make follow-up edits:
  cd "$CLONE_DIR"
  git pull
  # ... edit files in $SUBFOLDER/ ...
  git add $SUBFOLDER && git commit -m "..." && git push
DONE
