<#
.SYNOPSIS
    Единый гейт качества comfy-meta-viewer: ESLint, Node-тесты, контракты OpenAPI, pytest.

.DESCRIPTION
    Прогоняет все проверки, которые раньше делались вручную по отдельности:
      1. Web: eslint (npm run lint — app/static/js).
      2. Web: node-тесты (npm test — tests/test_*.mjs).
      3. Контракты: sync_contracts.ps1 -CheckOnly
         (Flask-маршруты app/main.py, app/ai/routes.py, app/comfyui/routes.py,
          app/comfyui/simple_routes.py, app/integrations/social/routes.py
          против site/api/openapi.json; проверка через
          tests/test_openapi_contract.py, ручная синхронизация).
      4. Полный pytest (tests/ через poetry).

    Гейт только проверяет и ничего не правит: openapi.json правится вручную
    (генератора нет), JS/питон-фиксы — осознанно по одному файлу.

    Совместим с Windows PowerShell 5.1 и PowerShell 7+.
    Нативные команды вызываются напрямую в теле скрипта (не в функциях):
    иначе их stdout попадет в возвращаемое значение функции и испортит
    код выхода. $LASTEXITCODE считывается сразу после вызова, без пайпов.

.EXAMPLE
    .\lint.ps1                    # полная проверка (в основном pytest)
    .\lint.ps1 -SkipTests         # только линтеры, node-тесты и контракты
    .\lint.ps1 -SkipWeb           # только Python-контур (контракты + pytest)
#>

param(
    [switch]$SkipTests,
    [switch]$SkipWeb
)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$script:Results = @()

function Write-StepHeader($text) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Register-Result($name, $status, $detail) {
    $script:Results += [PSCustomObject]@{
        Step = $name
        Status = $status
        Detail = $detail
    }
    if ($status -eq "OK") {
        Write-Host "  [OK] $name" -ForegroundColor Green
    } elseif ($status -eq "SKIPPED") {
        Write-Host "  [SKIP] $name — $detail" -ForegroundColor Yellow
    } else {
        Write-Host "  [FAIL] $name — $detail" -ForegroundColor Red
    }
}

$hasNodeModules = Test-Path (Join-Path $ProjectRoot "node_modules")
$poetryCmd = Get-Command "poetry" -ErrorAction SilentlyContinue

# ── 1-2. Web: eslint + node-тесты ──────────────────────────────────
if ($SkipWeb) {
    Register-Result "eslint" "SKIPPED" "-SkipWeb"
    Register-Result "node tests" "SKIPPED" "-SkipWeb"
} elseif (-not $hasNodeModules) {
    Register-Result "eslint" "SKIPPED" "нет node_modules — выполнить npm ci"
    Register-Result "node tests" "SKIPPED" "нет node_modules — выполнить npm ci"
} else {
    Write-StepHeader "[1/4] ESLint (npm run lint)"
    Push-Location $ProjectRoot
    try {
        npm run lint
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
    } finally {
        Pop-Location
    }
    if ($code -eq 0) {
        Register-Result "eslint" "OK" ""
    } else {
        Register-Result "eslint" "FAIL" "exit $code — чинить errors; warnings по мере чистки (см. eslint.config.js)"
    }

    Write-StepHeader "[2/4] Node-тесты (npm test)"
    Push-Location $ProjectRoot
    try {
        npm test
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
    } finally {
        Pop-Location
    }
    if ($code -eq 0) {
        Register-Result "node tests" "OK" ""
    } else {
        Register-Result "node tests" "FAIL" "exit $code"
    }
}

# ── 3. Контракты (только проверка, без автообновления) ─────────────
Write-StepHeader "[3/4] Контракты (sync_contracts -CheckOnly)"
& (Join-Path $ProjectRoot "sync_contracts.ps1") -CheckOnly
$code = $LASTEXITCODE
if ($null -eq $code) { $code = 0 }
if ($code -eq 0) {
    Register-Result "contracts" "OK" ""
} else {
    Register-Result "contracts" "FAIL" "exit $code — внести маршрут в site/api/openapi.json вручную (см. подсказку sync_contracts.ps1)"
}

# ── 4. Полный pytest ───────────────────────────────────────────────
if ($SkipTests) {
    Register-Result "pytest" "SKIPPED" "-SkipTests"
} elseif (-not $poetryCmd) {
    Register-Result "pytest" "SKIPPED" "poetry не найден в PATH — установить poetry и выполнить poetry install --no-root --with dev"
} else {
    Write-StepHeader "[4/4] Полный pytest (tests/)"
    Push-Location $ProjectRoot
    try {
        poetry run python -m pytest tests -q
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
    } finally {
        Pop-Location
    }
    if ($code -eq 0) {
        Register-Result "pytest" "OK" ""
    } else {
        Register-Result "pytest" "FAIL" "exit $code"
    }
}

# ── Итог ───────────────────────────────────────────────────────────
Write-StepHeader "Итог проверки"
$script:Results | Format-Table -AutoSize | Out-Host
$failed = @($script:Results | Where-Object { $_.Status -eq "FAIL" }).Count
if ($failed -gt 0) {
    Write-Host "  Гейт НЕ пройден: FAIL шагов: $failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Гейт пройден: все проверки OK (SKIP — только явно пропущенные)." -ForegroundColor Green
exit 0
