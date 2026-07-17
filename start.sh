#!/usr/bin/env bash
set -e

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

if ! command -v poetry &> /dev/null; then
    echo "[ERROR] Poetry not found. Install: pip install poetry"
    exit 1
fi

echo "Installing dependencies..."
poetry install --no-root --quiet

echo "Starting ComfyUI Meta Viewer..."
exec poetry run python -m app.main "$@"
