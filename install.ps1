# kb-mcp installer — run once per machine
# Double-click or: right-click -> "Run with PowerShell"

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "   OK: $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "   ERROR: $msg" -ForegroundColor Red; Read-Host "Press Enter to exit"; exit 1 }

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  kb-mcp installer — Acumatica KB Search" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# ── 1. Locate the kb-mcp folder (script lives inside it) ─────────────────────
Write-Step "Locating kb-mcp folder"
$KbMcpDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path "$KbMcpDir\pyproject.toml")) {
    Write-Fail "Cannot find pyproject.toml in $KbMcpDir — make sure install.ps1 is inside the kb-mcp folder."
}
Write-OK $KbMcpDir

# ── 2. Locate the vault (sibling folder Acumatica-KB) ────────────────────────
Write-Step "Locating Acumatica-KB vault"
$VaultDir = Join-Path (Split-Path -Parent $KbMcpDir) "Acumatica-KB"
if (-not (Test-Path $VaultDir)) {
    Write-Fail "Cannot find Acumatica-KB at $VaultDir — make sure OneDrive has finished syncing."
}
Write-OK $VaultDir

# ── 3. Check Python ───────────────────────────────────────────────────────────
Write-Step "Checking Python"
try {
    $pyver = & python --version 2>&1
    Write-OK $pyver
} catch {
    Write-Fail "Python not found. Install Python 3.11+ from https://python.org and re-run."
}

# ── 4. Create venv if needed ──────────────────────────────────────────────────
Write-Step "Setting up virtual environment"
$VenvDir = "$KbMcpDir\.venv"
if (-not (Test-Path "$VenvDir\Scripts\python.exe")) {
    Write-Host "   Creating .venv …"
    & python -m venv $VenvDir
} else {
    Write-Host "   .venv already exists, skipping."
}
Write-OK ".venv ready"

# ── 5. Install package + dependencies ────────────────────────────────────────
Write-Step "Installing kb-mcp and dependencies (this may take a few minutes)"
$PipExe = "$VenvDir\Scripts\pip.exe"
& $PipExe install -e $KbMcpDir --quiet
if ($LASTEXITCODE -ne 0) { Write-Fail "pip install failed." }
Write-OK "Dependencies installed"

# ── 6. Build index if not already present ────────────────────────────────────
$IndexNpy  = "$KbMcpDir\src\kb_mcp\kb_index.npy"
$IndexMeta = "$KbMcpDir\src\kb_mcp\kb_meta.json"

if ((Test-Path $IndexNpy) -and (Test-Path $IndexMeta)) {
    Write-Step "Index already built — skipping (delete kb_index.npy to rebuild)"
    Write-OK "Using existing index"
} else {
    Write-Step "Building vector index from vault embeddings (~2 min)"
    $PythonExe = "$VenvDir\Scripts\python.exe"
    $env:KB_VAULT_DIR      = $VaultDir
    $env:KB_MCP_INDEX_DIR  = "$KbMcpDir\src\kb_mcp"
    & $PythonExe -m kb_mcp.build_index
    if ($LASTEXITCODE -ne 0) { Write-Fail "build_index failed." }
    Write-OK "Index built"
}

# ── 7. Patch claude_desktop_config.json ──────────────────────────────────────
Write-Step "Registering kb-mcp with Claude Desktop"

$ConfigPath = "$env:APPDATA\Claude\claude_desktop_config.json"
$PythonExe  = "$VenvDir\Scripts\python.exe"

$NewServer = [ordered]@{
    command = $PythonExe
    args    = @("-m", "kb_mcp.server")
    env     = [ordered]@{
        KB_VAULT_DIR     = $VaultDir
        KB_MCP_INDEX_DIR = "$KbMcpDir\src\kb_mcp"
    }
}

if (Test-Path $ConfigPath) {
    $raw     = Get-Content $ConfigPath -Raw -Encoding UTF8
    $config  = $raw | ConvertFrom-Json
} else {
    # Create minimal config if Claude Desktop hasn't been launched yet
    New-Item -ItemType Directory -Force -Path (Split-Path $ConfigPath) | Out-Null
    $config = [PSCustomObject]@{ mcpServers = [PSCustomObject]@{} }
}

# Ensure mcpServers key exists
if (-not (Get-Member -InputObject $config -Name "mcpServers" -MemberType NoteProperty)) {
    $config | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value ([PSCustomObject]@{})
}

# Add / overwrite kb-mcp entry
$config.mcpServers | Add-Member -MemberType NoteProperty -Name "kb-mcp" -Value $NewServer -Force

$config | ConvertTo-Json -Depth 10 | Set-Content $ConfigPath -Encoding UTF8
Write-OK "Config written to $ConfigPath"

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Next step: restart Claude Desktop." -ForegroundColor White
Write-Host "  The first search_kb call will download the ~45 MB model once." -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to exit"
