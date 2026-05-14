#!/usr/bin/env bash
# deploy_to_github.sh
#
# One-shot deploy of the agent-system to a fresh GitHub repo.
#
# Usage:
#   bash deploy_to_github.sh https://github.com/<user>/agent-system.git
#
# Pre-requisite: create the empty private repo on GitHub first
#   (https://github.com/new — do NOT tick "add README/.gitignore/license").

set -euo pipefail

REPO_URL="${1:-}"

if [[ -z "$REPO_URL" ]]; then
  echo "Error: missing repo URL." >&2
  echo "" >&2
  echo "Usage:" >&2
  echo "  bash deploy_to_github.sh https://github.com/<user>/agent-system.git" >&2
  exit 1
fi

# Always run from the script's own directory (so it works no matter where you call it from).
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo ">> Working in: $ROOT"
echo ">> Target repo: $REPO_URL"
echo ""

# 1. Wipe any stale .git directory (e.g. from a prior partial init).
if [[ -d .git ]]; then
  echo ">> Removing stale .git folder..."
  rm -rf .git
fi

# 2. Use the user's existing global git identity if set, else a sensible default.
USER_NAME="$(git config --global user.name  || true)"
USER_EMAIL="$(git config --global user.email || true)"
if [[ -z "$USER_NAME"  ]]; then USER_NAME="Sol"; fi
if [[ -z "$USER_EMAIL" ]]; then USER_EMAIL="dgh.giang@gmail.com"; fi

echo ">> Committing as: $USER_NAME <$USER_EMAIL>"

# 3. Init fresh on main.
git init -b main >/dev/null

# 4. Stage everything (.gitignore handles the exclusions).
git add .

# 5. Sanity-check that no secrets are about to be committed.
if git ls-files --cached | grep -E '^\.env$' >/dev/null 2>&1; then
  echo "!! Refusing to commit: .env is staged. Check your .gitignore." >&2
  exit 1
fi

STAGED=$(git ls-files --cached | wc -l | tr -d ' ')
echo ">> Files staged: $STAGED"

# 6. First commit.
git -c user.name="$USER_NAME" -c user.email="$USER_EMAIL" \
    commit -q -m "Initial commit: multi-agent system framework"

# 7. Wire up remote (idempotent — replace if it exists).
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPO_URL"
else
  git remote add origin "$REPO_URL"
fi

# 8. Push.
echo ""
echo ">> Pushing to $REPO_URL ..."
echo ">> (If prompted for credentials: GitHub no longer accepts your password —"
echo ">>  use a Personal Access Token from https://github.com/settings/tokens"
echo ">>  with 'repo' scope, OR install the GitHub CLI and run 'gh auth login' once.)"
echo ""

git push -u origin main

echo ""
echo ">> Done. Repo is live at: ${REPO_URL%.git}"
echo ">> Next: invite teammates at ${REPO_URL%.git}/settings/access"
