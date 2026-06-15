#!/usr/bin/env bash
cd "$(dirname "$0")"

if ! command -v poetry &> /dev/null; then
    echo "[ERROR] Poetry not found. Install: pip install poetry"
    exit 1
fi

echo "Installing dependencies..."
poetry install --no-root --quiet

echo "Starting ComfyUI Meta Viewer..."
poetry run python -m app.main "$@"
