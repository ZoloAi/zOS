# zOS installer — Windows (PowerShell)
#
#   irm https://raw.githubusercontent.com/ZoloAi/zOS/main/install.ps1 | iex
#
# What it does (and nothing more):
#   1. Confirms this OS/arch is a supported zOS platform
#   2. Finds a CPython 3.10-3.12 (the range zGuard ships binaries for)
#   3. Creates an isolated venv at %USERPROFILE%\.zolo\venv
#   4. Installs zolo-os from PyPI into it
#   5. Adds the venv Scripts dir to your user PATH (for the `z` CLI)
#
# Re-running is safe: the venv is reused and zolo-os is upgraded in place.

$ErrorActionPreference = "Stop"

$ZoloHome = if ($env:ZOLO_HOME) { $env:ZOLO_HOME } else { Join-Path $env:USERPROFILE ".zolo" }
$Venv     = Join-Path $ZoloHome "venv"
$Scripts  = Join-Path $Venv "Scripts"

function Say($msg)  { Write-Host $msg -ForegroundColor White }
function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# -- 1. platform check ---------------------------------------------------------
$arch = $env:PROCESSOR_ARCHITECTURE
if ($arch -notin @("AMD64", "ARM64")) {
    Fail "unsupported architecture: $arch (zOS alpha supports AMD64 + ARM64)"
}
Say "-> platform: Windows/$arch - supported"

# -- 2. find CPython 3.10-3.12 --------------------------------------------------
$Py = $null
foreach ($cand in @("py -3.12", "py -3.11", "py -3.10", "python")) {
    try {
        $parts = $cand.Split(" ")
        $ver = & $parts[0] @($parts[1..($parts.Length-1)] + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")) 2>$null
        if ($ver -in @("3.10", "3.11", "3.12")) { $Py = $cand; break }
    } catch { continue }
}
if (-not $Py) {
    Fail "no CPython 3.10-3.12 found. Install one from https://www.python.org/downloads/ (check 'Add to PATH') and re-run."
}
Say "-> python: $Py"

# -- 3. venv --------------------------------------------------------------------
if (-not (Test-Path (Join-Path $Scripts "pip.exe"))) {
    Say "-> creating venv: $Venv"
    $parts = $Py.Split(" ")
    & $parts[0] @($parts[1..($parts.Length-1)] + @("-m", "venv", $Venv))
} else {
    Say "-> reusing venv: $Venv"
}

# -- 4. install -----------------------------------------------------------------
# python -m pip, NOT pip.exe: on Windows pip refuses to upgrade itself while
# its own exe is the running process.
Say "-> installing zolo-os from PyPI"
& (Join-Path $Scripts "python.exe") -m pip install --quiet --upgrade pip zolo-os
if ($LASTEXITCODE -ne 0) { Fail "pip install failed (see output above)" }

# -- 5. PATH --------------------------------------------------------------------
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$Scripts*") {
    [Environment]::SetEnvironmentVariable("Path", "$Scripts;$userPath", "User")
    $env:Path = "$Scripts;$env:Path"
    Say "-> added to user PATH: $Scripts"
}

# -- 6. git courtesy bootstrap ----------------------------------------------------
# zOS never needs git, but Claude Code / Cursor workflows assume it. Bootstrap
# via winget (ships with Win 10/11); NON-FATAL - never fail the zOS install.
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Say "-> git not found - installing via winget (your AI partner will want it)"
        try {
            winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
        } catch {
            Say "WARN git install failed - grab it later from https://git-scm.com/download/win"
        }
    } else {
        Say "WARN git not found - your AI partner will want it: https://git-scm.com/download/win"
    }
}

$version = & (Join-Path $Scripts "z.exe") --version 2>$null
Say ""
Say "OK installed: $version"
Say ""
Say "Get started (new terminals pick up the PATH automatically):"
Say "    z --version"
Say "    git clone https://github.com/ZoloAi/zOS.git; cd zOS\zDemos\zHello; z zSpark.zhello.zolo"
