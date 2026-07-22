#!/usr/bin/env bash
set -e

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

if [[ -x ".venv/bin/python" ]]; then
    exec .venv/bin/python -m app.ai.intent_benchmark "$@"
fi

if ! command -v poetry &> /dev/null; then
    echo "[ERROR] Python environment not found." >&2
    echo "Create .venv or install Poetry: pip install poetry" >&2
    exit 1
fi

exec poetry run python -m app.ai.intent_benchmark "$@"
