# Build Zolo.exe — the thin Windows launcher (twin of desktop/macos/build.sh).
#
#   .\build.ps1              unsigned single-file publish (local testing)
#   .\build.ps1 -Sign        signed via Azure Trusted Signing (cert pending —
#                            fill the placeholders below when the account lands)
#
# Requires: .NET 8 SDK on a Windows box (or the ONE batched CI windows runner —
# never incremental tag pushes; see the alpha CI budget).
# Output: dist\Zolo.exe (win-x64) + dist\arm64\Zolo.exe (win-arm64)

param([switch]$Sign)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Say($msg) { Write-Host "-> $msg" -ForegroundColor White }

# -- 1. publish: self-contained single-file, both arches ------------------------
foreach ($rid in @("win-x64", "win-arm64")) {
    Say "publishing ZoloLauncher ($rid)"
    $out = if ($rid -eq "win-x64") { "dist" } else { "dist\arm64" }
    dotnet publish ZoloLauncher\ZoloLauncher.csproj -c Release -r $rid -o $out `
        /p:PublishSingleFile=true /p:SelfContained=true | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed for $rid" }
}

# -- 2. sign (Azure Trusted Signing) ---------------------------------------------
# Pending the Trusted Signing account (the alpha signing-gap track). When it
# lands: install the TrustedSigning dlib, fill endpoint/account/profile, and
# SmartScreen trusts the binary near-immediately (Microsoft-vouched identity).
if ($Sign) {
    Say "signing via Azure Trusted Signing"
    $dlib = "$env:USERPROFILE\.azure-codesigning\bin\x64\Azure.CodeSigning.Dlib.dll"
    $meta = "$PSScriptRoot\signing-metadata.json"   # { Endpoint, CodeSigningAccountName, CertificateProfileName }
    if (-not (Test-Path $dlib) -or -not (Test-Path $meta)) {
        throw "Trusted Signing not configured yet - see the signing-gap track (dlib: $dlib, metadata: $meta)"
    }
    foreach ($exe in @("dist\Zolo.exe", "dist\arm64\Zolo.exe")) {
        signtool sign /v /fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 `
            /dlib $dlib /dmdf $meta $exe
        if ($LASTEXITCODE -ne 0) { throw "signtool failed for $exe" }
    }
    Say "signed + timestamped"
}

Say "done: dist\Zolo.exe (+ dist\arm64\Zolo.exe)"
