@echo off
setlocal EnableDelayedExpansion
title ComfyUI Meta Viewer Benchmarks
cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Failed to open the application directory.
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m app.ai.intent_benchmark %*
    exit /b !errorlevel!
)

where poetry >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python environment not found.
    echo Create .venv or install Poetry: pip install poetry
    exit /b 1
)

call poetry run python -m app.ai.intent_benchmark %*
exit /b %errorlevel%
