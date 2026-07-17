@echo off
title ComfyUI Meta Viewer
cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Failed to open the application directory.
    pause
    exit /b 1
)

where poetry >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Poetry not found. Install: pip install poetry
    pause
    exit /b 1
)

echo Installing dependencies...
call poetry install --no-root --quiet

echo Starting ComfyUI Meta Viewer...
call poetry run python -m app.main %*
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start. Try: poetry install
    pause
)
