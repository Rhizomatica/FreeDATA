!include "MUI2.nsh"

; Request administrative rights
RequestExecutionLevel admin

; The name and file name of the installer
Name "FreeDATA Installer"
OutFile "FreeDATA-Installer.exe"

; Default installation directory for the server
InstallDir "$LOCALAPPDATA\FreeDATA"

; Registry key to store the installation directory
InstallDirRegKey HKCU "Software\FreeDATA" "Install_Dir"

; Modern UI settings
!define MUI_ABORTWARNING

; Installer interface settings
!define MUI_ICON "documentation\icon.ico"
!define MUI_UNICON "documentation\icon.ico" ; Icon for the uninstaller

; Define the welcome page text
!define MUI_WELCOMEPAGE_TEXT "Welcome to the FreeDATA Setup Wizard. This wizard will guide you through the installation process."
!define MUI_FINISHPAGE_TEXT "Folder: $INSTDIR"
!define MUI_DIRECTORYPAGE_TEXT_TOP "Please select the installation folder. It's recommended to use the suggested one to avoid permission problems."

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Language (you can choose and configure the language(s) you want)
!insertmacro MUI_LANGUAGE "English"

!define StartMenuFolder "FreeDATA"


; Installer Sections
Section "FreeData Server" SEC01
  ; Set output path to the installation directory
  SetOutPath $INSTDIR\freedata-server

  ; Check if "config.ini" exists and back it up
  IfFileExists $INSTDIR\freedata-server\config.ini backupConfig

doneBackup:
  ; Add your application files here
  File /r "modem\server.dist\*"

; Restore the original "config.ini" if it was backed up
  IfFileExists $INSTDIR\freedata-server\config.ini.bak restoreConfig

  ; Create a shortcut in the user's desktop
  CreateShortCut "$DESKTOP\FreeDATA Server.lnk" "$INSTDIR\freedata-server\freedata-server.exe"

  ; Create Uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Create a Start Menu directory
  CreateDirectory "$SMPROGRAMS\${StartMenuFolder}"

  ; Create shortcut in the Start Menu directory
  CreateShortCut "$SMPROGRAMS\${StartMenuFolder}\FreeDATA Server.lnk" "$INSTDIR\freedata-server\freedata-server.exe"

  ; Create an Uninstall shortcut
  CreateShortCut "$SMPROGRAMS\${StartMenuFolder}\Uninstall FreeDATA.lnk" "$INSTDIR\Uninstall.exe"


  ; Backup "config.ini" before overwriting files
backupConfig:
  Rename $INSTDIR\freedata-server\config.ini $INSTDIR\freedata-server\config.ini.bak
  Goto doneBackup

; Restore the original "config.ini"
restoreConfig:
  Delete $INSTDIR\freedata-server\config.ini
  Rename $INSTDIR\freedata-server\config.ini.bak $INSTDIR\freedata-server\config.ini



SectionEnd

Section "FreeData x64 GUI" SEC02
  ; Set output path to the GUI installation directory
  SetOutPath $INSTDIR\freedata-gui

  ; Add GUI files here
  File /r "gui\release\win-unpacked\*"

  ; Create a shortcut on the desktop for the GUI
  CreateShortCut "$DESKTOP\FreeDATA GUI.lnk" "$INSTDIR\freedata-gui\freedata.exe"

  ; Create a start menu shortcut
  CreateShortCut "$SMPROGRAMS\${StartMenuFolder}\FreeDATA GUI.lnk" "$INSTDIR\freedata-gui\freedata.exe"

  ; Create an Uninstall shortcut
  CreateShortCut "$SMPROGRAMS\${StartMenuFolder}\Uninstall FreeDATA.lnk" "$INSTDIR\Uninstall.exe"

SectionEnd

; Uninstaller Section
Section "Uninstall"
  ; Delete files and directories for the server
  Delete $INSTDIR\freedata-server\*.*
  RMDir /r $INSTDIR\freedata-server

  ; Delete files and directories for the GUI
  Delete $INSTDIR\freedata-gui\*.*
  RMDir /r $INSTDIR\freedata-gui

  ; Remove the desktop shortcuts
  Delete "$DESKTOP\FreeDATA Server.lnk"
  Delete "$DESKTOP\FreeDATA GUI.lnk"

; Remove Start Menu shortcuts
  Delete "$SMPROGRAMS\${StartMenuFolder}\*.*"
  RMDir "$SMPROGRAMS\${StartMenuFolder}"

  ; Attempt to delete the uninstaller itself
  Delete $EXEPATH

  ; Now remove the installation directory if it's empty
  RMDir /r $INSTDIR
SectionEnd
