<#
.SYNOPSIS
    Проверяет синхронизацию Flask-маршрутов и site/api/openapi.json.

.DESCRIPTION
    В этом репозитории контракт — ручной (генератора OpenAPI нет):
      1. Flask-маршруты из PUBLIC_ROUTE_FILES (см. tests/test_openapi_contract.py):
         app/main.py, app/ai/routes.py, app/comfyui/routes.py,
         app/comfyui/simple_routes.py, app/integrations/social/routes.py
      2. Документ site/api/openapi.json (OpenAPI 3.1.0, рендерится через Scalar
         в site/api/index.html).

    Проверка выполняется через tests/test_openapi_contract.py:
      - каждый маршрут /api/* из кода есть в openapi.json и наоборот;
      - у каждой операции есть summary/tags/operationId (уникальный);
      - path-параметры в пути совпадают с declared parameters;
      - нет битых ссылок на компоненты (пустой ключ вместо $ref).

    Автообновления нет: расхождение правится вручную в site/api/openapi.json.
    Флаг -CheckOnly оставлен для совместимости с lint.ps1 (поведение одинаковое:
    скрипт никогда ничего не переписывает).

.EXAMPLE
    .\sync_contracts.ps1             # проверить контракт
    .\sync_contracts.ps1 -CheckOnly  # то же (для вызова из lint.ps1)
#>

param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Script lives in the repository root, so PSScriptRoot is the project root.
$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$OpenApiJson = Join-Path $ProjectRoot "site\api\openapi.json"
$ContractTest = Join-Path $ProjectRoot "tests\test_openapi_contract.py"

# ── colours ────────────────────────────────────────────────────────
function Write-Header($text) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Write-Step($icon, $text, $color = "White") {
    Write-Host "  $icon " -NoNewline -ForegroundColor $color
    Write-Host $text
}

# ── preflight ──────────────────────────────────────────────────────
Write-Header "Contract Sync - comfy-meta-viewer"

if (-not (Test-Path $OpenApiJson)) {
    Write-Step "X" "openapi.json not found: $OpenApiJson" "Red"
    exit 1
}
if (-not (Test-Path $ContractTest)) {
    Write-Step "X" "Contract test not found: $ContractTest" "Red"
    exit 1
}
$poetryCmd = Get-Command "poetry" -ErrorAction SilentlyContinue
if (-not $poetryCmd) {
    Write-Step "X" "poetry is not installed or not in PATH." "Red"
    Write-Host "    Install poetry and run: poetry install --no-root --with dev" -ForegroundColor DarkGray
    exit 1
}

# ── step 1: Flask routes vs openapi.json ───────────────────────────
Write-Host ""
Write-Step "1." "Checking Flask routes vs site/api/openapi.json..." "Yellow"
Write-Host ""

Push-Location $ProjectRoot
try {
    poetry run python -m pytest tests/test_openapi_contract.py -q
    $contractCode = $LASTEXITCODE
    if ($null -eq $contractCode) { $contractCode = 0 }
} finally {
    Pop-Location
}

# Exit codes: 0 = in sync, 1 = error, 2 = drift detected
if ($contractCode -eq 0) {
    Write-Host ""
    Write-Step "OK" "Everything is in sync. No action needed." "Green"
    exit 0
}

# pytest возвращает 1 и при drift, и при ошибке — различаем по выводу выше.
# Для совместимости с lint.ps1 маппим любой не-0 на drift (2): это сигнал
# "контракт требует ручной правки", а не инфраструктурная поломка гейта.
Write-Host ""
Write-Step "!" "Flask/OpenAPI drift detected (см. Missing/Stale списки выше)." "Yellow"
Write-Host "    Как синхронизировать вручную:" -ForegroundColor DarkGray
Write-Host "      1. Найди маршрут в Missing/Stale: метод + путь /api/*." -ForegroundColor DarkGray
Write-Host "      2. Missing (есть в коде, нет в json): добавь операцию в site/api/openapi.json" -ForegroundColor DarkGray
Write-Host "         (paths -> путь -> метод: operationId уникальный, summary, tags, параметры пути)." -ForegroundColor DarkGray
Write-Host "      3. Stale (есть в json, нет в коде): удали операцию из site/api/openapi.json" -ForegroundColor DarkGray
Write-Host "         (или верни удалённый Flask-маршрут, если удаление было случайным)." -ForegroundColor DarkGray
Write-Host "      4. Повтори: poetry run python -m pytest tests/test_openapi_contract.py -q" -ForegroundColor DarkGray
if ($CheckOnly) {
    Write-Host "    (режим -CheckOnly: файлы не трогаем, только проверка)." -ForegroundColor DarkGray
}
Write-Host ""
exit 2
