; ANTIVYRE — NSIS Installer Script
; License: zlib (free for commercial use)
;
; Requirements:
;   1. Install NSIS 3.x from https://nsis.sourceforge.io
;   2. Install the following NSIS plugins (copy to NSIS/Plugins/x86-unicode/):
;      - NsisMultiUser:  https://github.com/Drizin/NsisMultiUser
;      - nsProcess:      https://nsis.sourceforge.io/NsProcess_plugin
;   3. Run PyInstaller first:  pyinstaller build.spec
;   4. Right-click antivyre.nsi → "Compile NSIS Script"
;   Output: installer/Output/AntivyreSetup.exe

Unicode True

; ── Definitions ─────────────────────────────────────────────────────────────
!define APP_ROOT        ".."
!define APP_NAME        "ANTIVYRE"
!define APP_VERSION     "1.2.1"
!define APP_PUBLISHER   "FreddyDeveloper"
!define APP_URL         "https://www.antivyre.com"
!define APP_EXE         "ANTIVYRE.exe"
!define APP_MUTEX       "AntivyreSingleInstance"
!define INSTALL_DIR     "$PROGRAMFILES64\${APP_NAME}"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
!define STARTUP_KEY     "Software\Microsoft\Windows\CurrentVersion\Run"
!define REG_ROOT        "HKCU"

; ── Compression ──────────────────────────────────────────────────────────────
SetCompressor /SOLID lzma
SetCompressorDictSize 64

; ── Metadata ─────────────────────────────────────────────────────────────────
Name                "${APP_NAME} ${APP_VERSION}"
OutFile             "Output\AntivyreSetup.exe"
InstallDir          "${INSTALL_DIR}"
InstallDirRegKey    ${REG_ROOT} "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin
ShowInstDetails     show
ShowUninstDetails   show

; ── Version info (shown in Properties → Details) ─────────────────────────────
VIProductVersion    "${APP_VERSION}.0"
VIAddVersionKey     "ProductName"      "${APP_NAME}"
VIAddVersionKey     "ProductVersion"   "${APP_VERSION}"
VIAddVersionKey     "CompanyName"      "${APP_PUBLISHER}"
VIAddVersionKey     "LegalCopyright"   "Copyright © 2021–2026 FreddyDeveloper. GNU GPL v3."
VIAddVersionKey     "FileDescription"  "${APP_NAME} Installer"
VIAddVersionKey     "FileVersion"      "${APP_VERSION}.0"

; ── Modern UI ────────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"

!define MUI_ICON                    "H:\Database\Coding\Python\ANTIVYRE\antivyre\assets\icon.ico"
!define MUI_UNICON                  "H:\Database\Coding\Python\ANTIVYRE\antivyre\assets\icon.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH

; Welcome page
!define MUI_WELCOMEPAGE_TITLE       "Welcome to ${APP_NAME} ${APP_VERSION}"
!define MUI_WELCOMEPAGE_TEXT        "This wizard will install ${APP_NAME} - the free AI-powered antivirus.$\r$\n$\r$\nBuilt with Google Magika AI engine.$\r$\n$\r$\nClick Next to continue."
!insertmacro MUI_PAGE_WELCOME

; License page
!insertmacro MUI_PAGE_LICENSE       "${APP_ROOT}\LICENSE"

; Directory page
!insertmacro MUI_PAGE_DIRECTORY

; Components page (desktop shortcut + startup)
!insertmacro MUI_PAGE_COMPONENTS

; Install files page
!insertmacro MUI_PAGE_INSTFILES

; Finish page — offer to launch the app
!define MUI_FINISHPAGE_RUN          "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT     "Launch ${APP_NAME} now"
!define MUI_FINISHPAGE_LINK         "Visit ${APP_URL}"
!define MUI_FINISHPAGE_LINK_LOCATION "${APP_URL}"
!insertmacro MUI_PAGE_FINISH

; Uninstall pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; ── Languages ────────────────────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "PortugueseBR"

; ── Installer sections ───────────────────────────────────────────────────────

Section "-Core" SecCore
    SectionIn RO

    ; Kill any running instance before installing
    nsProcess::_FindProcess "${APP_EXE}"
    Pop $R0
    ${If} $R0 == 0
        nsProcess::_KillProcess "${APP_EXE}"
        Sleep 1000
    ${EndIf}

    SetOutPath "$INSTDIR"
    SetOverwrite on

    ; Copy all PyInstaller output
    File /r "${APP_ROOT}\dist\ANTIVYRE\*.*"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Add/Remove Programs entry
    WriteRegStr   ${REG_ROOT} "${UNINSTALL_KEY}" "DisplayName"      "${APP_NAME}"
    WriteRegStr   ${REG_ROOT} "${UNINSTALL_KEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr   ${REG_ROOT} "${UNINSTALL_KEY}" "Publisher"        "${APP_PUBLISHER}"
    WriteRegStr   ${REG_ROOT} "${UNINSTALL_KEY}" "URLInfoAbout"     "${APP_URL}"
    WriteRegStr   ${REG_ROOT} "${UNINSTALL_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr   ${REG_ROOT} "${UNINSTALL_KEY}" "UninstallString"  "$INSTDIR\Uninstall.exe"
    WriteRegStr   ${REG_ROOT} "${UNINSTALL_KEY}" "DisplayIcon"      "$INSTDIR\_internal\assets\icon.ico"
    WriteRegDWORD ${REG_ROOT} "${UNINSTALL_KEY}" "NoModify"         1
    WriteRegDWORD ${REG_ROOT} "${UNINSTALL_KEY}" "NoRepair"         1

    ; Refresh Windows icon cache
    System::Call 'shell32.dll::SHChangeNotify(l, l, i, i) v (0x08000000, 0, 0, 0)'

    ; Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                    "$INSTDIR\${APP_EXE}" "" \
                    "$INSTDIR\_internal\assets\icon.ico" 0
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" \
                    "$INSTDIR\Uninstall.exe" "" \
                    "$INSTDIR\_internal\assets\icon.ico" 0

SectionEnd

Section "Desktop shortcut" SecDesktop
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
                   "$INSTDIR\${APP_EXE}" "" \
                   "$INSTDIR\_internal\assets\icon.ico" 0
    System::Call 'shell32.dll::SHChangeNotify(l, l, i, i) v (0x08000000, 0, 0, 0)'
SectionEnd

Section "Launch at Windows startup" SecStartup
    WriteRegStr ${REG_ROOT} "${STARTUP_KEY}" "${APP_NAME}" \
                '"$INSTDIR\${APP_EXE}" --startup'
SectionEnd

; ── Section descriptions (shown in Components page) ──────────────────────────
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecCore}    \
        "${APP_NAME} core files — required."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} \
        "Add a shortcut to your Desktop."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartup} \
        "Start ${APP_NAME} automatically when Windows starts."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ── Installer init — prevent multiple instances ───────────────────────────────
Function .onInit
    System::Call 'kernel32::CreateMutex(p 0, i 1, t "${APP_MUTEX}") p.r1 ?e'
    Pop $R0
    ${If} $R0 == 183
        MessageBox MB_OK|MB_ICONEXCLAMATION \
            "${APP_NAME} installer is already running."
        Abort
    ${EndIf}
FunctionEnd

; ── Uninstaller ───────────────────────────────────────────────────────────────
Section "Uninstall"

    nsProcess::_FindProcess "${APP_EXE}"
    Pop $R0
    ${If} $R0 == 0
        nsProcess::_KillProcess "${APP_EXE}"
        Sleep 3000
    ${EndIf}

    nsProcess::_FindProcess "${APP_EXE}"
    Pop $R0
    ${If} $R0 == 0
        nsProcess::_KillProcess "${APP_EXE}"
        Sleep 2000
    ${EndIf}

    nsExec::ExecToLog 'taskkill /F /IM "${APP_EXE}" /T'
    Sleep 1000

    RMDir /r "$INSTDIR\_internal"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR"

    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"

    Delete "$DESKTOP\${APP_NAME}.lnk"
    Delete "$QUICKLAUNCH\${APP_NAME}.lnk"

    DeleteRegKey   ${REG_ROOT} "${UNINSTALL_KEY}"
    DeleteRegValue ${REG_ROOT} "${STARTUP_KEY}" "${APP_NAME}"

    System::Call 'shell32.dll::SHChangeNotify(l, l, i, i) v (0x08000000, 0, 0, 0)'

SectionEnd
