; ====================================================================
; OpenCivil Installer Script (Windows 11 Style - Final)
; ====================================================================

#define MyAppName "OpenCivil"
#define MyAppVersion "0.65 (Stable)"
#define MyAppPublisher "OpenCivil"
#define MyAppExeName "OpenCivil.exe"
#define MyAppAssocName "Open Civil Model"
#define MyAppAssocExt ".mf"
#define MyAppAssocKey StringChange(MyAppAssocName, " ", "") + MyAppAssocExt

; --------------------------------------------------------------------
; SETUP
; --------------------------------------------------------------------
[Setup]
PrivilegesRequired=lowest
AppId={{CFB760FC-A702-4F1E-864E-79088FEF3B6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

; Default install location
DefaultDirName={autopf}\{#MyAppName}

; Icon settings
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=E:\MetuFire\OpenCivil\graphic\logo.ico

; System settings
ChangesAssociations=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SolidCompression=yes
WizardStyle=modern

; --- FIXES FOR DIRECTORY SELECTION ---
; This forces the installer to ignore previous install locations 
; and always show the "Select Destination" page.
DisableDirPage=no
UsePreviousAppDir=no

; We keep the "Start Menu Folder" selection hidden for a cleaner look
DisableProgramGroupPage=yes

OutputBaseFilename=OpenCivil_Setup_v{#MyAppVersion}

; --------------------------------------------------------------------
; LANGUAGES
; --------------------------------------------------------------------
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; --------------------------------------------------------------------
; INSTALL TYPES
; --------------------------------------------------------------------
[Types]
Name: "full"; Description: "Full installation"
Name: "compact"; Description: "Compact installation"
Name: "custom"; Description: "Custom installation"

; --------------------------------------------------------------------
; COMPONENTS
; --------------------------------------------------------------------
[Components]
Name: "core"; Description: "OpenCivil (Required)"; Types: full compact custom; Flags: fixed
Name: "desktopicon"; Description: "Create Desktop Shortcut"; Types: full custom
Name: "fileassoc"; Description: "Associate .mf files with OpenCivil"; Types: full custom

; --------------------------------------------------------------------
; FILES
; --------------------------------------------------------------------
[Files]
Source: "E:\MetuFire\OpenCivil\app\dist\OpenCivil\*"; \
DestDir: "{app}"; \
Flags: ignoreversion recursesubdirs createallsubdirs; \
Components: core

; --------------------------------------------------------------------
; REGISTRY (FILE ASSOCIATION)
; --------------------------------------------------------------------
[Registry]
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocExt}\OpenWithProgids"; \
ValueType: string; ValueName: "{#MyAppAssocKey}"; ValueData: ""; \
Flags: uninsdeletevalue; Components: fileassoc

Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}"; \
ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocName}"; \
Flags: uninsdeletekey; Components: fileassoc

Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\DefaultIcon"; \
ValueType: string; ValueName: ""; \
ValueData: "{app}\{#MyAppExeName},0"; \
Components: fileassoc

Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\shell\open\command"; \
ValueType: string; ValueName: ""; \
ValueData: """{app}\{#MyAppExeName}"" ""%1"""; \
Components: fileassoc

; --------------------------------------------------------------------
; SHORTCUTS
; --------------------------------------------------------------------
[Icons]
; 1. The main program shortcut in Start Menu
Name: "{autoprograms}\{#MyAppName}"; \
Filename: "{app}\{#MyAppExeName}"; Components: core

; 2. The desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; \
Filename: "{app}\{#MyAppExeName}"; Components: desktopicon

; 3. The Uninstaller shortcut in Start Menu (Added this for you)
Name: "{autoprograms}\Uninstall OpenCivil"; \
Filename: "{uninstallexe}"; Components: core

; --------------------------------------------------------------------
; RUN AFTER INSTALL
; --------------------------------------------------------------------
[Run]
Filename: "{app}\{#MyAppExeName}"; \
Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
Flags: nowait postinstall skipifsilent