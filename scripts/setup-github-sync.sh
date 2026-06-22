#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 2 ]]; then
  echo "Usage: $0 [github-remote-url] [branch]" >&2
  echo "Default remote: git@github.com:wstalsprzedkompa/OPCUAtor.git" >&2
  exit 2
fi

REMOTE_URL="${1:-git@github.com:wstalsprzedkompa/OPCUAtor.git}"
BRANCH="${2:-main}"

cd "$(dirname "$0")/.."

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init
fi

git branch -M "$BRANCH"

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

git add -A
if ! git diff --cached --quiet; then
  git commit -m "Initial OPCUAtor version"
fi

git push -u origin "$BRANCH"

echo "OPCUAtor is connected to $REMOTE_URL on branch $BRANCH."
