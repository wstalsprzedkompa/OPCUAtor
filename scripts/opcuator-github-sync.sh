#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BRANCH="${OPCUATOR_GIT_BRANCH:-main}"
COMMIT_MESSAGE="${OPCUATOR_GIT_COMMIT_MESSAGE:-Auto-sync OPCUAtor changes}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "This directory is not a Git repository. Run scripts/setup-github-sync.sh first." >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Remote 'origin' is not configured. Run scripts/setup-github-sync.sh first." >&2
  exit 1
fi

git branch -M "$BRANCH"

if git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >/dev/null 2>&1; then
  git pull --rebase --autostash
fi

git add -A
if ! git diff --cached --quiet; then
  git commit -m "$COMMIT_MESSAGE"
fi

git push -u origin "$BRANCH"
