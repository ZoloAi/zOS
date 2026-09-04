# zOS installer — Windows (PowerShell)
#
#   irm https://raw.githubusercontent.com/ZoloAi/zOS/main/install.ps1 | iex
#
# What it does (and nothing more):
#   1. Confirms this OS/arch is a supported zOS platform
#   2. Finds a CPython 3.10-3.13 (the range zGuard ships binaries for) —
#      or provisions Python 3.12 via uv when none exists (fresh-PC path)
#   3. Creates an isolated venv at %USERPROFILE%\.zolo\venv
#   4. Installs zolo-os from PyPI into it
#   5. Adds the venv Scripts dir to your user PATH (for the `z` CLI)
#   6. Gives .zolo files an identity (icon + double-click open), per-user
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

# -- 2. find CPython 3.10-3.13 --------------------------------------------------
# 3.13 included since zGuard ships cp313 binaries (PYMESS sim, 2026-09-04).
# Ceiling stays BELOW 3.14 (no zGuard binaries there).
# $Py ends up as a launcher spec ("py -3.12"), a bare command ("python"), or a
# full interpreter path (the uv rescue below) — which may contain spaces.
# All invocations go through this ONE helper (the old Split(" ") slice broke
# on single-token candidates and can't survive spaced paths).
function Invoke-Py {
    param([string]$Spec, [string[]]$PyArgs)
    if ($Spec -like "py -*") { & py $Spec.Split(" ")[1] @PyArgs }
    else                     { & $Spec @PyArgs }
}

$Py = $null
foreach ($cand in @("py -3.13", "py -3.12", "py -3.11", "py -3.10", "python")) {
    try {
        $ver = Invoke-Py $cand @("-c", "import sys; print('%d.%d' % sys.version_info[:2])") 2>$null
        if ($ver -in @("3.10", "3.11", "3.12", "3.13")) { $Py = $cand; break }
    } catch { continue }
}
# No suitable CPython? Provision one with uv (standalone builds, no admin) —
# the fresh-PC path: store-Python is often 3.13/3.14, above zGuard's ceiling,
# and "go install Python 3.12" is exactly the wall this installer removes.
# (The same rescue z patch itself performs — kept here so the FIRST install
# never needs a human to fix Python.)
if (-not $Py) {
    Say "-> no CPython 3.10-3.12 found - provisioning Python 3.12 via uv"
    $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (-not (Test-Path $uv)) {
        $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
        if ($uvCmd) { $uv = $uvCmd.Source }
        else {
            try {
                Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression | Out-Null
            } catch {
                Fail "could not install uv. Install Python 3.10-3.12 manually (https://www.python.org/downloads/) and re-run."
            }
            if (-not (Test-Path $uv)) { Fail "uv installed but not found at $uv - open a NEW terminal and re-run this installer." }
        }
    }
    & $uv python install 3.12 | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "uv could not install Python 3.12 - re-run, or install Python manually and re-run." }
    $found = (& $uv python find 3.12 2>$null | Select-Object -First 1)
    if (-not $found -or -not (Test-Path $found)) { Fail "uv installed Python 3.12 but it can't be located - re-run this installer." }
    $Py = "$found"
}
Say "-> python: $Py"

# -- 3. venv --------------------------------------------------------------------
# A reused venv must actually RUN, not merely exist: a venv whose base python
# was uninstalled still has its files, but every exe in it is dead (PYMESS sim
# GAP-2, 2026-09-04). Probe the interpreter; rebuild on failure.
$VenvPy = Join-Path $Scripts "python.exe"
if ((Test-Path (Join-Path $Scripts "pip.exe"))) {
    & $VenvPy -c "" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Say "-> existing venv is broken (its Python was removed) - rebuilding"
        Remove-Item -Recurse -Force $Venv
    }
}
if (-not (Test-Path (Join-Path $Scripts "pip.exe"))) {
    Say "-> creating venv: $Venv"
    Invoke-Py $Py @("-m", "venv", $Venv)
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

# -- 5b. stale z sweep ------------------------------------------------------------
# A prior bare `pip install zolo-os` into some other Python (store 3.13/3.14,
# an all-users python.org install, ...) leaves z.exe/zolo.exe shims that can
# SHADOW ours forever: machine PATH outranks user PATH on Windows, so
# prepending our Scripts dir is not enough. Evict them.
$env:Path = "$Scripts;" + [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
foreach ($name in @("z", "zolo")) {
    foreach ($stale in @(Get-Command $name -CommandType Application -All -ErrorAction SilentlyContinue)) {
        $src = $stale.Source
        if (-not $src -or $src -like "$Scripts*") { continue }
        Say "-> found another $name from a previous pip install: $src"
        try {
            # uninstall from that interpreter if we can find it (removes all its shims)
            $stalePy = Join-Path (Split-Path (Split-Path $src)) "python.exe"
            if (Test-Path $stalePy) { & $stalePy -m pip uninstall --quiet --yes zolo-os 2>$null | Out-Null }
            if (Test-Path $src) { Remove-Item $src -Force -ErrorAction Stop }
            Say "   removed - the fresh zOS now answers to $name"
        } catch {
            Say "WARN could not remove it (an admin-installed Python?). Run this once in an"
            Say "     Administrator terminal, then reopen your terminal:"
            Say "     & `"$stalePy`" -m pip uninstall -y zolo-os"
        }
    }
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

# -- 7. .zolo file identity -------------------------------------------------------
# Parity with the macOS app bundle's UTI: icon + double-click open, per-user
# (HKCU — no admin, no machine-wide writes). Double-click hands the file to
# the venv z.exe with ZOS_DESKTOP=1 via a tiny shim (a registry command can't
# set env vars itself). NON-FATAL: cosmetics must never fail an install.
try {
    $icon = Join-Path $ZoloHome "zolo.ico"
    if (-not (Test-Path $icon)) {
        Invoke-WebRequest -UseBasicParsing -OutFile $icon `
            https://raw.githubusercontent.com/ZoloAi/zOS/main/desktop/windows/assets/zolo.ico
    }

    $shim = Join-Path $ZoloHome "zolo-open.cmd"
    @(
        "@echo off"
        "set ZOS_DESKTOP=1"
        "cd /d ""%~dp1"""
        """$Scripts\z.exe"" ""%~nx1"""
    ) | Set-Content -Path $shim -Encoding ASCII

    New-Item -Path "HKCU:\Software\Classes\.zolo" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Classes\.zolo" -Name "(default)" -Value "Zolo.File"
    New-Item -Path "HKCU:\Software\Classes\Zolo.File\DefaultIcon" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Classes\Zolo.File\DefaultIcon" -Name "(default)" -Value $icon
    New-Item -Path "HKCU:\Software\Classes\Zolo.File\shell\open\command" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Classes\Zolo.File\shell\open\command" -Name "(default)" `
        -Value """$shim"" ""%1"""
    Say "-> .zolo files: icon + double-click open registered (this user)"
} catch {
    Say "WARN .zolo file association skipped ($($_.Exception.Message)) - zOS itself is unaffected"
}

$version = & (Join-Path $Scripts "z.exe") --version 2>$null
Say ""
Say "OK installed: $version"
Say ""
Say "Get started (new terminals pick up the PATH automatically):"
Say "    z --version"
Say "    git clone https://github.com/ZoloAi/zOS.git; cd zOS\zDemos\zHello; z zSpark.zhello.zolo"
