; ANTIVYRE — Inno Setup Installer Script
; Version 1.0.0
;
; Requirements:
;   1. Run PyInstaller first:  pyinstaller build.spec
;   2. Open this file in Inno Setup Compiler (https://jrsoftware.org/isinfo.php)
;   3. Click Build → Compile
;   Output: installer/Output/AntivyreSetup.exe

#define AppName        "ANTIVYRE"
#define AppVersion     "1.0.0"
#define AppPublisher   "FreddyDeveloper"
#define AppURL         "https://www.freddydeveloper.com"
#define AppExeName     "Antivyre.exe"
#define AppMutex       "AntivyreSingleInstance"

[Setup]
; ── Identity ──────────────────────────────────────────────────────────────
AppId                     = {{8F3A2C1D-4E5B-4F6A-9B8C-2D3E4F5A6B7C}
AppName                   = {#AppName}
AppVersion                = {#AppVersion}
AppVerName                = {#AppName} {#AppVersion}
AppPublisher              = {#AppPublisher}
AppPublisherURL           = {#AppURL}
AppSupportURL             = {#AppURL}
AppUpdatesURL             = {#AppURL}
AppCopyright              = Copyright © 2019–2025 FreddyDeveloper. GNU GPL v3.

; ── Installation paths ────────────────────────────────────────────────────
DefaultDirName            = {autopf}\{#AppName}
DefaultGroupName          = {#AppName}
AllowNoIcons              = no
PrivilegesRequired        = lowest
PrivilegesRequiredOverridesAllowed = dialog

; ── Output ────────────────────────────────────────────────────────────────
OutputDir                 = installer\Output
OutputBaseFilename        = AntivyreSetup
SetupIconFile             = assets\icon.ico
UninstallDisplayIcon      = {app}\{#AppExeName}
UninstallDisplayName      = {#AppName} {#AppVersion}

; ── Appearance ────────────────────────────────────────────────────────────
WizardStyle               = modern
WizardResizable           = no
; Custom banner and side image (optional — comment out if files don't exist)
; WizardImageFile         = installer\wizard_side.bmp
; WizardSmallImageFile    = installer\wizard_top.bmp

; ── Compression ───────────────────────────────────────────────────────────
Compression               = lzma2/ultra64
SolidCompression          = yes
LZMAUseSeparateProcess    = yes

; ── Windows version requirement ───────────────────────────────────────────
MinVersion                = 10.0

; ── Misc ──────────────────────────────────────────────────────────────────
ShowLanguageDialog        = auto
ChangesAssociations       = no
CloseApplications         = yes
RestartApplications       = no
DisableWelcomePage        = no
DisableDirPage            = no
DisableProgramGroupPage   = yes
DisableReadyPage          = no
DisableFinishedPage       = no
AlwaysRestart             = no

[Languages]
Name: "english";    MessagesFile: "compiler:Default.isl"
Name: "spanish";    MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french";     MessagesFile: "compiler:Languages\French.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon";     Description: "{cm:CreateDesktopIcon}";         GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon";     Description: "Launch ANTIVYRE at Windows startup"; GroupDescription: "Startup:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}";     GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; ── Main application (PyInstaller output folder) ──────────────────────────
Source: "dist\Antivyre\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Visual C++ Redistributable (bundled for safety) ──────────────────────
; Uncomment if you want to bundle VC++ redist:
; Source: "redist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
; Start Menu
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional task)
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

; Quick Launch (legacy, Windows XP/Vista)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Registry]
; Add/Remove Programs — display icon
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting('AppId')}_is1"; ValueType: string; ValueName: "DisplayIcon"; ValueData: "{app}\assets\icon.ico"; Flags: uninsdeletevalue

; Optional startup entry (only if task was selected)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
; Launch app after install finishes (checkbox shown to user)
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill the process before uninstalling
Filename: "taskkill.exe"; Parameters: "/F /IM {#AppExeName}"; Flags: runhidden; RunOnceId: "KillApp"

[Code]
// Prevent multiple instances of the installer running simultaneously
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

// Check if app is running before uninstall
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM {#AppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
