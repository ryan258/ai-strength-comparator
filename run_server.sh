#!/usr/bin/env bash
set -euo pipefail

select_python() {
  local candidates=(".venv/bin/python" "venv/bin/python")
  local candidate

  for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ] && "$candidate" -c 'import uvicorn' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "No project virtual environment with uvicorn found in .venv/ or venv/." >&2
  return 1
}

PYTHON_BIN="$(select_python)"
exec "$PYTHON_BIN" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
