; HMS Hospital Management System — Windows installer

; Build:  powershell -File installer\build\build.ps1

; Client: double-click HMS-Setup.exe (fresh install OR upgrade — no CMD, no uninstall)



#ifndef AppVersion

  #define MyAppVersion "1.0.0"

#else

  #define MyAppVersion AppVersion

#endif



#define StageDir "stage"



[Setup]

AppId={{A7B3C9D1-4E2F-5A6B-8C9D-0E1F2A3B4C5D}

AppName=Hospital Management System

AppVersion={#MyAppVersion}

AppPublisher=HMS

DefaultDirName=D:\HMS

DisableDirPage=no

DisableProgramGroupPage=yes

UsePreviousAppDir=yes

; Always ask Server vs Client again — remembering Server on a client PC hangs setup.
UsePreviousTasks=no

OutputDir=release

OutputBaseFilename=HMS-Setup

Compression=lzma2

SolidCompression=yes

PrivilegesRequired=admin

ArchitecturesInstallIn64BitMode=x64compatible

; Python 3.12 / PySide6 need Windows 10+ (api-ms-win-core-path-l1-1-0.dll).
MinVersion=10.0

WizardStyle=modern



[Languages]

Name: "english"; MessagesFile: "compiler:Default.isl"



[Tasks]

Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: checkedonce

Name: "serverrole"; Description: "This PC is the &server (Backend + Desktop — PostgreSQL on this PC)"; GroupDescription: "Role (pick carefully):"; Flags: exclusive

Name: "clientrole"; Description: "This PC is a &client (Desktop only — connect to server IP)"; GroupDescription: "Role (pick carefully):"; Flags: exclusive unchecked



[Files]

; Excludes hms.env so the next entry can protect the customer's DB password / server IP.
Source: "{#StageDir}\*"; DestDir: "{app}"; Excludes: "config\hms.env"; Flags: ignoreversion recursesubdirs createallsubdirs

; Keep customer's database password and server IP — never overwrite on upgrade

Source: "{#StageDir}\config\hms.env"; DestDir: "{app}\config"; Flags: onlyifdoesntexist uninsneveruninstall



[Icons]

Name: "{group}\Start HMS (Server)"; Filename: "{app}\scripts\Start-HMS.bat"; Tasks: serverrole

Name: "{group}\HMS Desktop Only"; Filename: "{app}\scripts\Start-HMS-Desktop-Only.bat"; Tasks: clientrole

Name: "{group}\Edit Config"; Filename: "notepad.exe"; Parameters: """{app}\config\hms.env"""

Name: "{commondesktop}\HMS"; Filename: "{app}\scripts\Start-HMS.bat"; Tasks: desktopicon serverrole

Name: "{commondesktop}\HMS Desktop"; Filename: "{app}\scripts\Start-HMS-Desktop-Only.bat"; Tasks: desktopicon clientrole



[Run]

; Do NOT run DB migrations here — that hung the wizard when PostgreSQL was slow/offline.
; Migrations + menu seed run automatically when the server starts (Start HMS / backend lifespan).

Filename: "{app}\scripts\Start-HMS.bat"; Description: "Start HMS now"; Flags: postinstall nowait skipifsilent; Tasks: serverrole

; Client: ask for server IP and write config\hms.env before first launch
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\Configure-HMS-Client.ps1"" -InstallRoot ""{app}"""; StatusMsg: "Configuring client server address..."; Flags: waituntilterminated; Tasks: clientrole

Filename: "{app}\scripts\Start-HMS-Desktop-Only.bat"; Description: "Start HMS Desktop now"; Flags: postinstall nowait skipifsilent; Tasks: clientrole


