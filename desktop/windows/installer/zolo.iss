; ZoloSetup.exe — the Windows twin of the Mac DMG (zOS #33, alpha Windows track).
; Wraps dist\Zolo.exe (the doorman built by ..\build.ps1) into the "installed
; app" feel the bare exe can't give: Start Menu + desktop, the .zolo file
; association, a WebView2 rescue for machines missing the runtime, and a real
; uninstall entry. Per-user install — NO admin prompt, dad never sees UAC.
;
; Build (Windows, Inno Setup 6): ISCC.exe installer\zolo.iss
; Input:  dist\Zolo.exe (x64) — arm64 users are served by x64 emulation for now
; Output: dist\ZoloSetup.exe
;
; Signing: unsigned for the alpha preview (SmartScreen shows More info → Run
; anyway; coached on Foundations). When Artifact Signing lands, sign BOTH
; dist\Zolo.exe and dist\ZoloSetup.exe — see ..\build.ps1 -Sign.

#define AppName "Zolo"
#define AppVersion "1.0.0"
#define AppPublisher "Zolo Media"
#define AppURL "https://zolo.media"

[Setup]
AppId={{7A31F9E2-5C84-4D8B-9F1E-3C0A2B41D907}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/zStack/zOS/Foundations
DefaultDirName={localappdata}\Programs\Zolo
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ZoloSetup
SetupIconFile=..\assets\zolo.ico
UninstallDisplayIcon={app}\Zolo.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes

[Files]
Source: "..\dist\Zolo.exe"; DestDir: "{app}"; Flags: ignoreversion
; WebView2 Evergreen bootstrapper (~2 MB) — only runs when the runtime is
; genuinely absent (rare on consumer Win 10/11; ships with Win 11).
Source: "MicrosoftEdgeWebView2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{userprograms}\Zolo"; Filename: "{app}\Zolo.exe"
Name: "{userdesktop}\Zolo"; Filename: "{app}\Zolo.exe"

[Registry]
; .zolo double-click → Zolo.exe (per-user classes; no admin needed)
Root: HKCU; Subkey: "Software\Classes\.zolo"; ValueType: string; ValueData: "Zolo.File"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Zolo.File"; ValueType: string; ValueData: "Zolo App"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Zolo.File\DefaultIcon"; ValueType: string; ValueData: "{app}\Zolo.exe,0"
Root: HKCU; Subkey: "Software\Classes\Zolo.File\shell\open\command"; ValueType: string; ValueData: """{app}\Zolo.exe"" ""%1"""

[Run]
; WebView2 runtime rescue — silent, per-user scope not offered by MS, so the
; bootstrapper elevates only on machines that actually lack the runtime.
Filename: "{tmp}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; \
    Check: not WebView2Present; StatusMsg: "Installing the Microsoft WebView2 runtime..."; Flags: waituntilterminated
; The DMG moment: installer closes, Zolo opens, the doorman takes over
; (installs the engine in its own progress window, then shows zRM sign-in).
Filename: "{app}\Zolo.exe"; Description: "Open Zolo now"; Flags: nowait postinstall skipifsilent

[Code]
function WebView2Present: Boolean;
var
  V: string;
begin
  // Evergreen runtime leaves a pv value under EdgeUpdate\Clients — per-machine
  // (WOW6432Node on x64) or per-user. Any non-empty, non-0.0.0.0 value counts.
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0'));
end;
