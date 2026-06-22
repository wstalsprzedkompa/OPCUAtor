#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x ".opcuator-venv/bin/python" ]]; then
  PYTHON_BIN=".opcuator-venv/bin/python"
elif [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

export PYTHONPATH="${PYTHONPATH:-src}"

exec "$PYTHON_BIN" -m uvicorn opcuator.main:app \
  --host "${REST_HOST:-0.0.0.0}" \
  --port "${REST_PORT:-9500}"
